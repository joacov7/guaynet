import asyncio
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.security import decrypt_value, encrypt_value
from app.models.client import Client
from app.models.router import DeviceStatus, MikrotikRouter, UbiquitiDevice
from app.schemas.router import (
    MikrotikQueueItem,
    RouterCreate,
    RouterResponse,
    RouterStats,
    RouterUpdate,
    UbiquitiDeviceCreate,
    UbiquitiDeviceResponse,
)
from app.services.mikrotik import MikrotikError, MikrotikService, build_service_from_router

router = APIRouter()


async def _router_response(rt: MikrotikRouter, db: AsyncSession) -> RouterResponse:
    count_result = await db.execute(select(func.count()).where(Client.router_id == rt.id))
    count = count_result.scalar_one()
    data = RouterResponse.model_validate(rt)
    data.client_count = count
    return data


@router.get("/", response_model=List[RouterResponse])
async def list_routers(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(MikrotikRouter).order_by(MikrotikRouter.name))
    routers = result.scalars().all()
    return [await _router_response(r, db) for r in routers]


@router.post("/", response_model=RouterResponse, status_code=201)
async def create_router(
    body: RouterCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    rt = MikrotikRouter(
        name=body.name,
        host=body.host,
        port=body.port,
        username=body.username,
        password_encrypted=encrypt_value(body.password),
        location=body.location,
        notes=body.notes,
    )
    db.add(rt)
    await db.commit()
    await db.refresh(rt)
    return await _router_response(rt, db)


@router.get("/{router_id}", response_model=RouterResponse)
async def get_router(router_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    rt = await db.get(MikrotikRouter, router_id)
    if not rt:
        raise HTTPException(status_code=404, detail="Router no encontrado")
    return await _router_response(rt, db)


@router.put("/{router_id}", response_model=RouterResponse)
async def update_router(
    router_id: int,
    body: RouterUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    rt = await db.get(MikrotikRouter, router_id)
    if not rt:
        raise HTTPException(status_code=404, detail="Router no encontrado")

    updates = body.model_dump(exclude_unset=True)
    if "password" in updates:
        rt.password_encrypted = encrypt_value(updates.pop("password"))
    for field, value in updates.items():
        setattr(rt, field, value)

    db.add(rt)
    await db.commit()
    await db.refresh(rt)
    return await _router_response(rt, db)


@router.delete("/{router_id}", status_code=204)
async def delete_router(
    router_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    rt = await db.get(MikrotikRouter, router_id)
    if not rt:
        raise HTTPException(status_code=404, detail="Router no encontrado")

    count_result = await db.execute(select(func.count()).where(Client.router_id == router_id))
    if count_result.scalar_one() > 0:
        raise HTTPException(status_code=400, detail="No se puede eliminar un router con clientes asignados")

    await db.delete(rt)
    await db.commit()


@router.post("/{router_id}/test", response_model=RouterStats)
async def test_router_connection(
    router_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    rt = await db.get(MikrotikRouter, router_id)
    if not rt:
        raise HTTPException(status_code=404, detail="Router no encontrado")

    def _test():
        svc = build_service_from_router(rt)
        with svc:
            return svc.get_system_info()

    try:
        info = await asyncio.to_thread(_test)
        rt.status = DeviceStatus.online
        rt.last_seen = datetime.now(timezone.utc)
        db.add(rt)
        await db.commit()
        return RouterStats(**info)
    except MikrotikError as e:
        rt.status = DeviceStatus.offline
        db.add(rt)
        await db.commit()
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/{router_id}/queues", response_model=List[MikrotikQueueItem])
async def get_router_queues(
    router_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    rt = await db.get(MikrotikRouter, router_id)
    if not rt:
        raise HTTPException(status_code=404, detail="Router no encontrado")

    def _get_queues():
        svc = build_service_from_router(rt)
        with svc:
            return svc.get_simple_queues()

    try:
        queues = await asyncio.to_thread(_get_queues)
        return [
            MikrotikQueueItem(
                id=q["id"],
                name=q["name"],
                target=q["target"],
                max_limit=q["max_limit"],
                burst_limit=q.get("burst_limit") or None,
                disabled=q["disabled"],
                comment=q.get("comment") or None,
                bytes=q.get("bytes"),
                packets=q.get("packets"),
            )
            for q in queues
        ]
    except MikrotikError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/{router_id}/sync-clients", status_code=200)
async def sync_clients_to_router(
    router_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    rt = await db.get(MikrotikRouter, router_id)
    if not rt:
        raise HTTPException(status_code=404, detail="Router no encontrado")

    result = await db.execute(
        select(Client).where(Client.router_id == router_id, Client.status != "cancelled")
    )
    clients = result.scalars().all()

    plan_ids = {c.plan_id for c in clients}
    from app.models.plan import Plan
    plan_result = await db.execute(select(Plan).where(Plan.id.in_(plan_ids)))
    plans = {p.id: p for p in plan_result.scalars().all()}

    def _sync():
        svc = build_service_from_router(rt)
        with svc:
            existing = {q["name"]: q for q in svc.get_simple_queues()}
            synced = 0
            errors = []
            for client in clients:
                plan = plans.get(client.plan_id)
                if not plan:
                    continue
                qname = client.mikrotik_queue_name
                disabled = client.status == "suspended"
                params = dict(
                    name=qname,
                    target=client.mikrotik_target,
                    max_limit=plan.mikrotik_max_limit,
                    burst_limit=plan.mikrotik_burst_limit,
                    burst_threshold=plan.mikrotik_burst_threshold,
                    burst_time=plan.mikrotik_burst_time if plan.mikrotik_burst_limit else None,
                    comment=f"guaynet:{client.id}|{client.full_name}",
                    disabled=disabled,
                )
                try:
                    if qname in existing:
                        svc.update_simple_queue(existing[qname]["id"], **{
                            k: v for k, v in params.items()
                            if k not in ("name", "target") and v is not None
                        })
                    else:
                        svc.add_simple_queue(**params)
                    synced += 1
                except Exception as e:
                    errors.append({"client_id": client.id, "error": str(e)})
            return {"synced": synced, "errors": errors}

    try:
        result = await asyncio.to_thread(_sync)
        return result
    except MikrotikError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/ubiquiti/", response_model=List[UbiquitiDeviceResponse])
async def list_ubiquiti_devices(
    router_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    q = select(UbiquitiDevice)
    if router_id:
        q = q.where(UbiquitiDevice.mikrotik_router_id == router_id)
    result = await db.execute(q.order_by(UbiquitiDevice.name))
    return result.scalars().all()


@router.post("/ubiquiti/", response_model=UbiquitiDeviceResponse, status_code=201)
async def create_ubiquiti_device(
    body: UbiquitiDeviceCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    data = body.model_dump()
    if data.get("password"):
        data["password_encrypted"] = encrypt_value(data.pop("password"))
    else:
        data.pop("password", None)
        data["password_encrypted"] = None

    device = UbiquitiDevice(**data)
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return device
