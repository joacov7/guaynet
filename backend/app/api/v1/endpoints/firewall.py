from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import asyncio

from app.core.deps import get_current_user, get_db
from app.models.router import MikrotikRouter
from app.models.client import Client, ClientStatus
from app.models.plan import Plan
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


# ── DHCP Import ───────────────────────────────────────────────────────────────

class DHCPImportItem(BaseModel):
    address: str
    mac_address: str
    hostname: Optional[str] = None


class DHCPImportRequest(BaseModel):
    items: List[DHCPImportItem]
    plan_id: int


@router.post("/{router_id}/dhcp-import")
async def dhcp_import(
    router_id: int,
    body: DHCPImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.services.mikrotik import build_service_from_router, MikrotikError
    from app.api.v1.endpoints.clients import _push_to_mikrotik
    from app.core.deps import add_audit_log

    mt_router = await _get_router_or_404(router_id, db)
    plan = await db.get(Plan, body.plan_id)
    if not plan:
        raise HTTPException(404, "Plan no encontrado")

    existing_ips = {
        row[0] for row in (await db.execute(select(Client.ip_address))).all()
    }

    created, skipped = 0, 0
    for item in body.items:
        if item.address in existing_ips:
            skipped += 1
            continue

        # Derive name from hostname or IP last octet
        if item.hostname:
            name_parts = item.hostname.replace("-", " ").replace("_", " ").split()
            first = name_parts[0].capitalize() if name_parts else item.address
            last = " ".join(name_parts[1:]).capitalize() if len(name_parts) > 1 else "DHCP"
        else:
            first = f"Cliente-{item.address.split('.')[-1]}"
            last = "DHCP"

        client = Client(
            first_name=first,
            last_name=last,
            ip_address=item.address,
            mac_address=item.mac_address or None,
            plan_id=body.plan_id,
            router_id=router_id,
            status=ClientStatus.active,
            billing_day=1,
        )
        db.add(client)
        await db.flush()  # get client.id before commit

        add_audit_log(db, current_user, "create", "client", client.id, client.full_name,
                      details=f"Importado desde DHCP ({item.address})")

        existing_ips.add(item.address)
        created += 1

    await db.commit()

    # Push all new clients to MikroTik (best-effort)
    new_clients_r = await db.execute(
        select(Client).where(
            Client.router_id == router_id,
            Client.last_name == "DHCP",
        )
    )
    for client in new_clients_r.scalars().all():
        try:
            await _push_to_mikrotik(client, mt_router, db)
        except MikrotikError:
            pass

    return {"created": created, "skipped": skipped}


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
