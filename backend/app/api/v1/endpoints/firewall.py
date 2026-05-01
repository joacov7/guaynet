from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import asyncio

from app.core.deps import get_db
from app.models.router import MikrotikRouter
from app.models.client import Client
from app.services.mikrotik import build_service_from_router, MikrotikError
from app.schemas.firewall import (
    DHCPScanResponse,
    DHCPLease,
    FirewallRule,
    MangleRule,
    PCQQueue,
    TemplateResult,
)

router = APIRouter()


async def _get_router_or_404(router_id: int, db: AsyncSession) -> MikrotikRouter:
    result = await db.execute(select(MikrotikRouter).where(MikrotikRouter.id == router_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "Router no encontrado")
    return r


# ── DHCP Scan ─────────────────────────────────────────────────────────────────

@router.get("/{router_id}/dhcp-scan", response_model=DHCPScanResponse)
async def dhcp_scan(router_id: int, db: AsyncSession = Depends(get_db)):
    mt_router = await _get_router_or_404(router_id, db)
    svc = build_service_from_router(mt_router)

    def _scan():
        with svc:
            return svc.get_dhcp_leases()

    try:
        leases_raw = await asyncio.to_thread(_scan)
    except MikrotikError as e:
        raise HTTPException(502, str(e))

    rows = await db.execute(
        select(Client.ip_address, Client.id, Client.first_name, Client.last_name)
        .where(Client.router_id == router_id)
    )
    registered = {
        row.ip_address: (row.id, f"{row.first_name} {row.last_name}")
        for row in rows
    }

    leases: List[DHCPLease] = []
    for raw in leases_raw:
        ip = raw.get("address", "")
        is_reg = ip in registered
        leases.append(
            DHCPLease(
                address=ip,
                mac_address=raw.get("mac-address", ""),
                hostname=raw.get("host-name", "") or None,
                comment=raw.get("comment", "") or None,
                status=raw.get("status", ""),
                is_registered=is_reg,
                client_id=registered[ip][0] if is_reg else None,
                client_name=registered[ip][1] if is_reg else None,
            )
        )

    registered_count = sum(1 for le in leases if le.is_registered)
    return DHCPScanResponse(
        total=len(leases),
        registered=registered_count,
        unregistered=len(leases) - registered_count,
        leases=leases,
    )


# ── Firewall Filter ───────────────────────────────────────────────────────────

@router.get("/{router_id}/filter", response_model=List[FirewallRule])
async def get_filter_rules(router_id: int, db: AsyncSession = Depends(get_db)):
    mt_router = await _get_router_or_404(router_id, db)
    svc = build_service_from_router(mt_router)

    def _get():
        with svc:
            return svc.get_firewall_filter_rules()

    try:
        rules = await asyncio.to_thread(_get)
    except MikrotikError as e:
        raise HTTPException(502, str(e))
    return [FirewallRule(**r) for r in rules]


@router.delete("/{router_id}/filter/{rule_id}")
async def delete_filter_rule(
    router_id: int, rule_id: str, db: AsyncSession = Depends(get_db)
):
    mt_router = await _get_router_or_404(router_id, db)
    svc = build_service_from_router(mt_router)

    def _del():
        with svc:
            svc.remove_firewall_filter_rule(rule_id)

    try:
        await asyncio.to_thread(_del)
    except MikrotikError as e:
        raise HTTPException(502, str(e))
    return {"ok": True}


# ── Mangle ────────────────────────────────────────────────────────────────────

@router.get("/{router_id}/mangle", response_model=List[MangleRule])
async def get_mangle_rules(router_id: int, db: AsyncSession = Depends(get_db)):
    mt_router = await _get_router_or_404(router_id, db)
    svc = build_service_from_router(mt_router)

    def _get():
        with svc:
            return svc.get_mangle_rules()

    try:
        rules = await asyncio.to_thread(_get)
    except MikrotikError as e:
        raise HTTPException(502, str(e))
    return [MangleRule(**r) for r in rules]


@router.delete("/{router_id}/mangle/{rule_id}")
async def delete_mangle_rule(
    router_id: int, rule_id: str, db: AsyncSession = Depends(get_db)
):
    mt_router = await _get_router_or_404(router_id, db)
    svc = build_service_from_router(mt_router)

    def _del():
        with svc:
            svc.remove_mangle_rule(rule_id)

    try:
        await asyncio.to_thread(_del)
    except MikrotikError as e:
        raise HTTPException(502, str(e))
    return {"ok": True}


# ── Templates ─────────────────────────────────────────────────────────────────

@router.post("/{router_id}/templates/{template}", response_model=TemplateResult)
async def apply_template(
    router_id: int, template: str, db: AsyncSession = Depends(get_db)
):
    mt_router = await _get_router_or_404(router_id, db)
    svc = build_service_from_router(mt_router)

    def _apply():
        with svc:
            return svc.apply_template(template)

    try:
        count = await asyncio.to_thread(_apply)
    except MikrotikError as e:
        raise HTTPException(502, str(e))
    return TemplateResult(template=template, rules_added=count, message=f"{count} reglas aplicadas")


# ── PCQ ───────────────────────────────────────────────────────────────────────

@router.get("/{router_id}/pcq", response_model=List[PCQQueue])
async def get_pcq_queues(router_id: int, db: AsyncSession = Depends(get_db)):
    mt_router = await _get_router_or_404(router_id, db)
    svc = build_service_from_router(mt_router)

    def _get():
        with svc:
            return svc.get_pcq_queues()

    try:
        queues = await asyncio.to_thread(_get)
    except MikrotikError as e:
        raise HTTPException(502, str(e))
    return [PCQQueue(**q) for q in queues]


@router.post("/{router_id}/pcq/setup")
async def setup_pcq(router_id: int, db: AsyncSession = Depends(get_db)):
    mt_router = await _get_router_or_404(router_id, db)
    svc = build_service_from_router(mt_router)

    def _setup():
        with svc:
            return svc.setup_pcq()

    try:
        added = await asyncio.to_thread(_setup)
    except MikrotikError as e:
        raise HTTPException(502, str(e))
    return {"added": added}
