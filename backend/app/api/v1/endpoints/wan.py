import asyncio
import logging
import traceback
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user, get_db
from app.models.router import MikrotikRouter
from app.models.wan import WanInterface, WanSchedule
from app.services.mikrotik import MikrotikError, build_service_from_router

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class WanInterfaceCreate(BaseModel):
    interface_name: str
    display_name: Optional[str] = None
    weight: int = 1
    cap_gb: Optional[int] = None
    enabled: bool = True


class WanInterfaceUpdate(BaseModel):
    display_name: Optional[str] = None
    weight: Optional[int] = None
    cap_gb: Optional[int] = None
    enabled: Optional[bool] = None


class WanScheduleCreate(BaseModel):
    action: str  # "enable" | "disable"
    days: str = "mon,tue,wed,thu,fri,sat,sun"
    time_start: str
    time_end: str


class LbWanConfig(BaseModel):
    wan_interface_id: int
    gateway: str


class ApplyLbRequest(BaseModel):
    wans: List[LbWanConfig]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _wan_to_dict(w: WanInterface, live: Optional[dict] = None) -> dict:
    cap_bytes = (w.cap_gb or 0) * 1024 ** 3
    used_bytes = (w.accumulated_rx_bytes or 0) + (w.accumulated_tx_bytes or 0)
    return {
        "id": w.id,
        "router_id": w.router_id,
        "interface_name": w.interface_name,
        "display_name": w.display_name or w.interface_name,
        "weight": w.weight,
        "cap_gb": w.cap_gb,
        "manual_override": w.manual_override,
        "enabled": w.enabled,
        "accumulated_rx_bytes": w.accumulated_rx_bytes or 0,
        "accumulated_tx_bytes": w.accumulated_tx_bytes or 0,
        "used_bytes": used_bytes,
        "cap_bytes": cap_bytes,
        "cap_pct": round(used_bytes / cap_bytes * 100, 1) if cap_bytes > 0 else None,
        "schedules": [_sched_to_dict(s) for s in (w.schedules or [])],
        "live": live,
    }


def _sched_to_dict(s: WanSchedule) -> dict:
    return {
        "id": s.id,
        "wan_interface_id": s.wan_interface_id,
        "action": s.action,
        "days": s.days,
        "time_start": s.time_start,
        "time_end": s.time_end,
    }


def _scheduler_name(wan_id: int, sched_id: int, action: str) -> str:
    return f"guaynet-wan{wan_id}-{action}-{sched_id}"


# ── WAN Interface CRUD ────────────────────────────────────────────────────────

@router.get("/{router_id}/wan")
async def list_wan_interfaces(
    router_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    rt = await db.get(MikrotikRouter, router_id)
    if not rt:
        raise HTTPException(status_code=404, detail="Router no encontrado")
    result = await db.execute(
        select(WanInterface)
        .where(WanInterface.router_id == router_id)
        .options(selectinload(WanInterface.schedules))
    )
    wans = result.scalars().all()

    # Fetch live stats from MikroTik
    def _get_live(iface_name: str):
        svc = build_service_from_router(rt)
        with svc:
            return svc.get_interface_bytes(iface_name)

    items = []
    for w in wans:
        try:
            live = await asyncio.to_thread(_get_live, w.interface_name)
        except Exception:
            live = None
        items.append(_wan_to_dict(w, live))
    return items


@router.post("/{router_id}/wan", status_code=201)
async def create_wan_interface(
    router_id: int,
    body: WanInterfaceCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    rt = await db.get(MikrotikRouter, router_id)
    if not rt:
        raise HTTPException(status_code=404, detail="Router no encontrado")
    w = WanInterface(
        router_id=router_id,
        interface_name=body.interface_name,
        display_name=body.display_name,
        weight=body.weight,
        cap_gb=body.cap_gb,
        enabled=body.enabled,
    )
    db.add(w)
    await db.commit()
    result2 = await db.execute(
        select(WanInterface).where(WanInterface.id == w.id).options(selectinload(WanInterface.schedules))
    )
    w = result2.scalar_one()
    return _wan_to_dict(w)


@router.put("/{router_id}/wan/{wan_id}")
async def update_wan_interface(
    router_id: int,
    wan_id: int,
    body: WanInterfaceUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    w = await db.get(WanInterface, wan_id)
    if not w or w.router_id != router_id:
        raise HTTPException(status_code=404)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(w, field, value)
    await db.commit()
    result2 = await db.execute(
        select(WanInterface).where(WanInterface.id == wan_id).options(selectinload(WanInterface.schedules))
    )
    w = result2.scalar_one()
    return _wan_to_dict(w)


@router.delete("/{router_id}/wan/{wan_id}", status_code=204)
async def delete_wan_interface(
    router_id: int,
    wan_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(
        select(WanInterface).where(WanInterface.id == wan_id).options(selectinload(WanInterface.schedules))
    )
    w = result.scalar_one_or_none()
    if not w or w.router_id != router_id:
        raise HTTPException(status_code=404)
    # Remove scheduler entries from MikroTik
    rt = await db.get(MikrotikRouter, router_id)
    if rt:
        schedules_snapshot = [(s.id,) for s in w.schedules]
        def _remove_schedules():
            svc = build_service_from_router(rt)
            with svc:
                for (sid,) in schedules_snapshot:
                    for act in ("start", "end"):
                        svc.remove_scheduler_entry(_scheduler_name(wan_id, sid, act))
        try:
            await asyncio.to_thread(_remove_schedules)
        except Exception:
            pass
    await db.delete(w)
    await db.commit()


# ── Manual Toggle ─────────────────────────────────────────────────────────────

@router.post("/{router_id}/wan/{wan_id}/toggle")
async def toggle_wan_interface(
    router_id: int,
    wan_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    w = await db.get(WanInterface, wan_id)
    if not w or w.router_id != router_id:
        raise HTTPException(status_code=404)
    rt = await db.get(MikrotikRouter, router_id)
    if not rt:
        raise HTTPException(status_code=404)

    new_state = not w.enabled

    def _toggle():
        svc = build_service_from_router(rt)
        with svc:
            if new_state:
                svc.enable_interface(w.interface_name)
            else:
                svc.disable_interface(w.interface_name)

    try:
        await asyncio.to_thread(_toggle)
    except MikrotikError as e:
        raise HTTPException(status_code=503, detail=str(e))

    w.enabled = new_state
    w.manual_override = True
    await db.commit()
    return {"enabled": new_state, "manual_override": True}


@router.post("/{router_id}/wan/{wan_id}/clear-override")
async def clear_manual_override(
    router_id: int,
    wan_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Re-enable scheduled control for this interface."""
    w = await db.get(WanInterface, wan_id)
    if not w or w.router_id != router_id:
        raise HTTPException(status_code=404)
    w.manual_override = False
    await db.commit()
    return {"manual_override": False}


# ── Schedules ─────────────────────────────────────────────────────────────────

@router.post("/{router_id}/wan/{wan_id}/schedules", status_code=201)
async def create_wan_schedule(
    router_id: int,
    wan_id: int,
    body: WanScheduleCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    w = await db.get(WanInterface, wan_id)
    if not w or w.router_id != router_id:
        raise HTTPException(status_code=404)
    rt = await db.get(MikrotikRouter, router_id)
    if not rt:
        raise HTTPException(status_code=404)

    s = WanSchedule(
        wan_interface_id=wan_id,
        action=body.action,
        days=body.days,
        time_start=body.time_start,
        time_end=body.time_end,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)

    # Write to MikroTik scheduler
    iface = w.interface_name
    action_script = f"/interface {'enable' if body.action == 'enable' else 'disable'} {iface}"
    inverse_action = "disable" if body.action == "enable" else "enable"
    inverse_script = f"/interface {inverse_action} {iface}"

    def _write_schedules():
        svc = build_service_from_router(rt)
        with svc:
            # Start entry
            svc.set_scheduler_entry(
                _scheduler_name(wan_id, s.id, "start"),
                body.time_start,
                "1:00:00:00",
                action_script,
                body.days,
            )
            # End entry
            svc.set_scheduler_entry(
                _scheduler_name(wan_id, s.id, "end"),
                body.time_end,
                "1:00:00:00",
                inverse_script,
                body.days,
            )

    try:
        await asyncio.to_thread(_write_schedules)
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"[wan] schedule error: {type(e).__name__}: {e}\n{tb}")
        raise HTTPException(status_code=503, detail=f"{type(e).__name__}: {e}")

    return _sched_to_dict(s)


@router.delete("/{router_id}/wan/{wan_id}/schedules/{sched_id}", status_code=204)
async def delete_wan_schedule(
    router_id: int,
    wan_id: int,
    sched_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    s = await db.get(WanSchedule, sched_id)
    if not s or s.wan_interface_id != wan_id:
        raise HTTPException(status_code=404)
    rt = await db.get(MikrotikRouter, router_id)
    if rt:
        def _remove():
            svc = build_service_from_router(rt)
            with svc:
                svc.remove_scheduler_entry(_scheduler_name(wan_id, sched_id, "start"))
                svc.remove_scheduler_entry(_scheduler_name(wan_id, sched_id, "end"))
        try:
            await asyncio.to_thread(_remove)
        except Exception:
            pass
    await db.delete(s)
    await db.commit()


# ── Load Balancing Wizard ─────────────────────────────────────────────────────

@router.post("/{router_id}/wan/apply-load-balance")
async def apply_load_balance(
    router_id: int,
    body: ApplyLbRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    rt = await db.get(MikrotikRouter, router_id)
    if not rt:
        raise HTTPException(status_code=404)

    wan_configs = []
    for item in body.wans:
        w = await db.get(WanInterface, item.wan_interface_id)
        if not w or w.router_id != router_id:
            raise HTTPException(status_code=400, detail=f"WAN {item.wan_interface_id} no pertenece a este router")
        wan_configs.append({"interface": w.interface_name, "gateway": item.gateway, "weight": w.weight})

    def _apply():
        svc = build_service_from_router(rt)
        with svc:
            svc.remove_pcc_load_balance()
            return svc.apply_pcc_load_balance(wan_configs)

    try:
        result = await asyncio.to_thread(_apply)
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"[wan] load-balance error: {type(e).__name__}: {e}\n{tb}")
        raise HTTPException(status_code=503, detail=f"{type(e).__name__}: {e}")

    return result


@router.post("/{router_id}/wan/remove-load-balance")
async def remove_load_balance(
    router_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    rt = await db.get(MikrotikRouter, router_id)
    if not rt:
        raise HTTPException(status_code=404)

    def _remove():
        svc = build_service_from_router(rt)
        with svc:
            svc.remove_pcc_load_balance()

    try:
        await asyncio.to_thread(_remove)
    except MikrotikError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return {"removed": True}
