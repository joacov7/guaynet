import asyncio
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user, get_db
from app.models.client import Client, ClientStatus
from app.models.invoice import Invoice
from app.models.plan import Plan
from app.models.router import MikrotikRouter
from app.schemas.client import ClientCreate, ClientListResponse, ClientResponse, ClientUpdate
from app.schemas.invoice import InvoiceResponse
from app.services.mikrotik import MikrotikError, build_service_from_router

router = APIRouter()


async def _push_to_mikrotik(client: Client, router_obj: MikrotikRouter, db):
    """Sync a single client's queue to its Mikrotik router."""
    plan = await db.get(Plan, client.plan_id)
    if not plan:
        return

    disabled = client.status == ClientStatus.suspended

    def _sync():
        svc = build_service_from_router(router_obj)
        with svc:
            existing = svc.get_queue_by_name(client.mikrotik_queue_name)
            params = dict(
                name=client.mikrotik_queue_name,
                target=client.mikrotik_target,
                max_limit=plan.mikrotik_max_limit,
                burst_limit=plan.mikrotik_burst_limit,
                burst_threshold=plan.mikrotik_burst_threshold,
                burst_time=plan.mikrotik_burst_time if plan.mikrotik_burst_limit else None,
                comment=f"guaynet:{client.id}|{client.full_name}",
                disabled=disabled,
            )
            if existing:
                svc.update_simple_queue(existing["id"], **{
                    k: v for k, v in params.items()
                    if k not in ("name", "target") and v is not None
                })
            else:
                svc.add_simple_queue(**params)

    await asyncio.to_thread(_sync)


@router.get("/", response_model=List[ClientListResponse])
async def list_clients(
    status: Optional[ClientStatus] = None,
    router_id: Optional[int] = None,
    plan_id: Optional[int] = None,
    search: Optional[str] = Query(None, description="Busca por nombre, IP o teléfono"),
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    q = (
        select(Client)
        .options(selectinload(Client.plan), selectinload(Client.router))
        .order_by(Client.last_name, Client.first_name)
    )
    if status:
        q = q.where(Client.status == status)
    if router_id:
        q = q.where(Client.router_id == router_id)
    if plan_id:
        q = q.where(Client.plan_id == plan_id)
    if search:
        term = f"%{search}%"
        q = q.where(
            or_(
                func.lower(Client.first_name + " " + Client.last_name).like(func.lower(term)),
                Client.ip_address.like(term),
                Client.phone.like(term),
                Client.dni.like(term),
            )
        )
    q = q.offset(skip).limit(limit)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/", response_model=ClientResponse, status_code=201)
async def create_client(
    body: ClientCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    # Check IP uniqueness
    existing_ip = await db.execute(select(Client).where(Client.ip_address == body.ip_address))
    if existing_ip.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"La IP {body.ip_address} ya está en uso")

    # Validate plan and router exist
    plan = await db.get(Plan, body.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    rt = await db.get(MikrotikRouter, body.router_id)
    if not rt:
        raise HTTPException(status_code=404, detail="Router no encontrado")

    client = Client(**body.model_dump())
    db.add(client)
    await db.commit()
    await db.refresh(client)

    # Push to Mikrotik (best-effort, don't fail the creation)
    try:
        await _push_to_mikrotik(client, rt, db)
    except MikrotikError:
        pass

    return await db.get(
        Client,
        client.id,
        options=[selectinload(Client.plan), selectinload(Client.router)],
    )


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.plan), selectinload(Client.router))
        .where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return client


@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int,
    body: ClientUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.plan), selectinload(Client.router))
        .where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    updates = body.model_dump(exclude_unset=True)

    if "ip_address" in updates and updates["ip_address"] != client.ip_address:
        dup = await db.execute(select(Client).where(Client.ip_address == updates["ip_address"]))
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"La IP {updates['ip_address']} ya está en uso")

    for field, value in updates.items():
        setattr(client, field, value)

    db.add(client)
    await db.commit()

    rt = await db.get(MikrotikRouter, client.router_id)
    if rt:
        try:
            await _push_to_mikrotik(client, rt, db)
        except MikrotikError:
            pass

    await db.refresh(client)
    return client


@router.delete("/{client_id}", status_code=204)
async def delete_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    client = await db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    rt = await db.get(MikrotikRouter, client.router_id)
    if rt:
        def _remove():
            from app.services.mikrotik import build_service_from_router
            svc = build_service_from_router(rt)
            with svc:
                q = svc.get_queue_by_name(client.mikrotik_queue_name)
                if q:
                    svc.remove_queue(q["id"])
        try:
            await asyncio.to_thread(_remove)
        except MikrotikError:
            pass

    await db.delete(client)
    await db.commit()


@router.post("/{client_id}/suspend", response_model=ClientResponse)
async def suspend_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(
        select(Client).options(selectinload(Client.plan), selectinload(Client.router)).where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    client.status = ClientStatus.suspended
    db.add(client)
    await db.commit()

    rt = await db.get(MikrotikRouter, client.router_id)
    if rt:
        def _disable():
            svc = build_service_from_router(rt)
            with svc:
                q = svc.get_queue_by_name(client.mikrotik_queue_name)
                if q:
                    svc.disable_queue(q["id"])
        try:
            await asyncio.to_thread(_disable)
        except MikrotikError:
            pass

    await db.refresh(client)
    return client


@router.post("/{client_id}/activate", response_model=ClientResponse)
async def activate_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(
        select(Client).options(selectinload(Client.plan), selectinload(Client.router)).where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    client.status = ClientStatus.active
    db.add(client)
    await db.commit()

    rt = await db.get(MikrotikRouter, client.router_id)
    if rt:
        try:
            await _push_to_mikrotik(client, rt, db)
        except MikrotikError:
            pass

    await db.refresh(client)
    return client


@router.post("/{client_id}/sync-mikrotik", status_code=200)
async def sync_client_mikrotik(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Force-push this client's queue config to its router."""
    client = await db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    rt = await db.get(MikrotikRouter, client.router_id)
    if not rt:
        raise HTTPException(status_code=404, detail="Router no encontrado")

    try:
        await _push_to_mikrotik(client, rt, db)
        return {"ok": True, "message": "Queue sincronizada correctamente"}
    except MikrotikError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/{client_id}/invoices", response_model=List[InvoiceResponse])
async def get_client_invoices(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    client = await db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    result = await db.execute(
        select(Invoice)
        .where(Invoice.client_id == client_id)
        .order_by(Invoice.due_date.desc())
    )
    return result.scalars().all()
