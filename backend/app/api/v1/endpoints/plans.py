from typing import List

import asyncio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.client import Client
from app.models.plan import Plan
from app.models.router import MikrotikRouter
from app.schemas.plan import PlanCreate, PlanResponse, PlanUpdate
from app.services.mikrotik import MikrotikError, build_service_from_router

router = APIRouter()


async def _plan_response(plan: Plan, db: AsyncSession) -> PlanResponse:
    count_result = await db.execute(select(func.count()).where(Client.plan_id == plan.id))
    count = count_result.scalar_one()
    data = PlanResponse.model_validate(plan)
    data.client_count = count
    return data


@router.get("/", response_model=List[PlanResponse])
async def list_plans(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    q = select(Plan)
    if active_only:
        q = q.where(Plan.is_active == True)
    result = await db.execute(q.order_by(Plan.price))
    plans = result.scalars().all()
    return [await _plan_response(p, db) for p in plans]


@router.post("/", response_model=PlanResponse, status_code=201)
async def create_plan(
    body: PlanCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    plan = Plan(**body.model_dump())
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return await _plan_response(plan, db)


@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(plan_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    plan = await db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    return await _plan_response(plan, db)


@router.put("/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: int,
    body: PlanUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    plan = await db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)

    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return await _plan_response(plan, db)


@router.post("/{plan_id}/sync-all")
async def sync_plan_to_all_routers(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Re-push queue limits for all clients on this plan to their routers."""
    plan = await db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    result = await db.execute(
        select(Client).where(Client.plan_id == plan_id, Client.status != "cancelled")
    )
    clients = result.scalars().all()

    from collections import defaultdict
    by_router: dict = defaultdict(list)
    for c in clients:
        by_router[c.router_id].append(c)

    synced = 0
    errors = []

    for router_id, router_clients in by_router.items():
        rt = await db.get(MikrotikRouter, router_id)
        if not rt:
            continue

        def _sync(router=rt, cls=router_clients, p=plan):
            svc = build_service_from_router(router)
            with svc:
                existing = {q["name"]: q for q in svc.get_simple_queues()}
                count = 0
                errs = []
                for client in cls:
                    qname = client.mikrotik_queue_name
                    try:
                        if qname in existing:
                            svc.update_simple_queue(
                                existing[qname]["id"],
                                max_limit=p.mikrotik_max_limit,
                                burst_limit=p.mikrotik_burst_limit,
                                burst_threshold=p.mikrotik_burst_threshold,
                                burst_time=p.mikrotik_burst_time if p.mikrotik_burst_limit else None,
                            )
                        else:
                            svc.add_simple_queue(
                                name=qname,
                                target=client.mikrotik_target,
                                max_limit=p.mikrotik_max_limit,
                                burst_limit=p.mikrotik_burst_limit,
                                burst_threshold=p.mikrotik_burst_threshold,
                                burst_time=p.mikrotik_burst_time if p.mikrotik_burst_limit else None,
                                comment=f"guaynet:{client.id}|{client.full_name}",
                                disabled=(client.status == "suspended"),
                            )
                        count += 1
                    except Exception as e:
                        errs.append({"client_id": client.id, "error": str(e)})
                return count, errs

        try:
            c, e = await asyncio.to_thread(_sync)
            synced += c
            errors.extend(e)
        except MikrotikError as e:
            errors.append({"router_id": router_id, "error": str(e)})

    return {"synced": synced, "errors": errors, "plan": plan.name}


@router.delete("/{plan_id}", status_code=204)
async def delete_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    plan = await db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    count_result = await db.execute(select(func.count()).where(Client.plan_id == plan_id))
    if count_result.scalar_one() > 0:
        raise HTTPException(status_code=400, detail="No se puede eliminar un plan con clientes activos")

    await db.delete(plan)
    await db.commit()
