from typing import List, Optional
from datetime import datetime, timezone
import ipaddress
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import asyncio

from app.core.deps import get_current_user, get_db
from app.models.router import MikrotikRouter
from app.models.client import Client, ClientStatus, ClientDeviceHistory
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


def normalize_mac(value: Optional[str]) -> str:
    """Return canonical AA:BB:CC:DD:EE:FF form; empty string for invalid input."""
    raw = (value or "").strip()
    if not raw or not re.fullmatch(r"[0-9a-fA-F:.-]+", raw):
        return ""
    compact = re.sub(r"[:.-]", "", raw)
    if len(compact) != 12 or not re.fullmatch(r"[0-9a-fA-F]{12}", compact):
        return ""
    compact = compact.lower()
    return ":".join(compact[i:i + 2] for i in range(0, 12, 2))


async def _get_router_or_404(router_id: int, db: AsyncSession) -> MikrotikRouter:
    result = await db.execute(select(MikrotikRouter).where(MikrotikRouter.id == router_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "Router no encontrado")
    return r


# ── DHCP Scan ─────────────────────────────────────────────────────────────────

@router.get("/{router_id}/dhcp-scan")
async def dhcp_scan(router_id: int, db: AsyncSession = Depends(get_db)):
    mt_router = await _get_router_or_404(router_id, db)
    svc = build_service_from_router(mt_router)

    def _scan():
        with svc:
            return svc.get_dhcp_leases()

    try:
        leases_raw = await asyncio.to_thread(_scan)
    except MikrotikError as e:
        return DHCPScanResponse(total=0, registered=0, unregistered=0, leases=[], error=str(e))
    except Exception as e:
        return DHCPScanResponse(total=0, registered=0, unregistered=0, leases=[], error=f"Error inesperado: {e}")

    rows = await db.execute(
        select(Client.id, Client.ip_address, Client.mac_address, Client.first_name, Client.last_name)
        .where(Client.router_id == router_id)
    )
    clients = list(rows)
    by_ip = {row.ip_address: row for row in clients if row.ip_address}
    history_rows = await db.execute(select(ClientDeviceHistory.client_id, ClientDeviceHistory.mac_address, ClientDeviceHistory.ended_at).where(ClientDeviceHistory.router_id == router_id))
    historical_mac_clients = {}
    for client_id, historical_mac, ended_at in history_rows:
        key = normalize_mac(historical_mac)
        if key and ended_at is not None:
            historical_mac_clients.setdefault(key, set()).add(client_id)

    by_mac = {}
    for client in clients:
        mac = normalize_mac(client.mac_address)
        if mac:
            by_mac.setdefault(mac, []).append(client)

    def normalize_name(value: Optional[str]) -> str:
        return " ".join((value or "").strip().lower().replace("_", " ").replace("-", " ").split())

    leases: List[DHCPLease] = []
    for raw in leases_raw:
        ip = raw.get("address", "")
        mac = normalize_mac(raw.get("mac-address", ""))
        hostname = raw.get("host-name", "") or None
        matched = None
        match_reason = None
        replacement_candidate = None

        # Stable device identity: MAC within the selected MikroTik router.
        mac_matches = by_mac.get(mac, []) if mac else []
        historical_ids = historical_mac_clients.get(mac, set()) if mac else set()
        candidate_ids = {c.id for c in mac_matches} | historical_ids
        if len(candidate_ids) == 1:
            candidate_id = next(iter(candidate_ids))
            matched = next((c for c in clients if c.id == candidate_id), None)
            match_reason = "mac" if any(c.id == candidate_id for c in mac_matches) else "historical_mac"
        elif len(candidate_ids) > 1:
            match_reason = "ambiguous_mac"
        elif ip in by_ip:
            ip_client = by_ip[ip]
            stored_mac = normalize_mac(ip_client.mac_address)
            # An IP collision with a different known MAC is not proof of identity.
            if not mac or not stored_mac:
                matched = ip_client
                match_reason = "ip"
            else:
                match_reason = "ip_conflict"
                replacement_candidate = ip_client

        # Hostname is only a hint for a possible antenna replacement, never proof.
        if matched is None and hostname:
            wanted = normalize_name(hostname)
            candidates = [
                c for c in clients
                if normalize_name(f"{c.first_name} {c.last_name}") == wanted
            ]
            if len(candidates) == 1:
                replacement_candidate = candidates[0]

        leases.append(
            DHCPLease(
                address=ip,
                mac_address=raw.get("mac-address", ""),
                hostname=hostname,
                comment=raw.get("comment", "") or None,
                status=raw.get("status", ""),
                is_registered=matched is not None,
                client_id=matched.id if matched else None,
                client_name=f"{matched.first_name} {matched.last_name}" if matched else None,
                match_reason=match_reason,
                ip_changed=bool(matched and matched.ip_address != ip),
                replacement_client_id=replacement_candidate.id if replacement_candidate else None,
                replacement_client_name=(
                    f"{replacement_candidate.first_name} {replacement_candidate.last_name}"
                    if replacement_candidate else None
                ),
            )
        )

    registered_count = sum(1 for le in leases if le.is_registered)
    return DHCPScanResponse(
        total=len(leases),
        registered=registered_count,
        unregistered=len(leases) - registered_count,
        leases=leases,
    )



class DHCPDeviceReplacement(BaseModel):
    client_id: int
    mac_address: str
    ip_address: str
    hostname: Optional[str] = None


@router.post("/{router_id}/dhcp-confirm-device")
async def confirm_dhcp_device_replacement(
    router_id: int,
    body: DHCPDeviceReplacement,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Confirm an operator-approved CPE replacement and preserve the old MAC."""
    client = await db.get(Client, body.client_id)
    if not client or client.router_id != router_id:
        raise HTTPException(404, "Cliente no encontrado en este router")

    mac = normalize_mac(body.mac_address)
    if not mac:
        raise HTTPException(400, "MAC inválida. Usá formato AA:BB:CC:DD:EE:FF")

    try:
        normalized_ip = str(ipaddress.ip_address(body.ip_address.strip()))
    except ValueError:
        raise HTTPException(400, "Dirección IP inválida")

    if normalized_ip != body.ip_address.strip():
        body.ip_address = normalized_ip

    router_clients = await db.execute(
        select(Client.id, Client.mac_address).where(
            Client.router_id == router_id,
            Client.id != client.id,
        )
    )
    if any(normalize_mac(existing_mac) == mac for _, existing_mac in router_clients):
        raise HTTPException(409, "Esa MAC ya está asignada a otro cliente")

    duplicate_ip = await db.execute(
        select(Client.id).where(Client.ip_address == body.ip_address, Client.id != client.id)
    )
    if duplicate_ip.first():
        raise HTTPException(409, "Esa IP ya está asignada a otro cliente")

    now = datetime.now(timezone.utc)
    active_history = await db.execute(
        select(ClientDeviceHistory).where(
            ClientDeviceHistory.client_id == client.id,
            ClientDeviceHistory.ended_at.is_(None),
        )
    )
    for device in active_history.scalars().all():
        device.ended_at = now

    old_mac = normalize_mac(client.mac_address)
    if old_mac and old_mac != mac:
        db.add(ClientDeviceHistory(
            client_id=client.id,
            router_id=router_id,
            mac_address=old_mac,
            ip_address=client.ip_address,
            change_reason="replaced",
            ended_at=now,
        ))

    client.mac_address = mac
    client.ip_address = body.ip_address
    db.add(ClientDeviceHistory(
        client_id=client.id,
        router_id=router_id,
        mac_address=mac,
        ip_address=body.ip_address,
        hostname=body.hostname,
        change_reason="replacement",
    ))
    add_audit_log(
        db, current_user, "replace_device", "client", client.id, client.full_name,
        details=f"Reemplazo CPE: MAC {old_mac or 'sin registro'} -> {mac}; IP {client.ip_address} -> {body.ip_address}",
    )
    await db.commit()
    return {
        "updated": True,
        "client_id": client.id,
        "mac_address": mac,
        "ip_address": body.ip_address,
        "router_sync_required": True,
        "message": "Ficha actualizada en Guaynet. Verificá/sincronizá el router por separado.",
    }


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

@router.get("/{router_id}/filter")
async def get_filter_rules(router_id: int, db: AsyncSession = Depends(get_db)):
    mt_router = await _get_router_or_404(router_id, db)
    svc = build_service_from_router(mt_router)

    def _get():
        with svc:
            return svc.get_firewall_filter_rules()

    try:
        rules = await asyncio.to_thread(_get)
        return {"rules": [FirewallRule(**r) for r in rules], "error": None}
    except MikrotikError as e:
        return {"rules": [], "error": str(e)}
    except Exception as e:
        return {"rules": [], "error": f"Error inesperado: {e}"}


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

@router.get("/{router_id}/mangle")
async def get_mangle_rules(router_id: int, db: AsyncSession = Depends(get_db)):
    mt_router = await _get_router_or_404(router_id, db)
    svc = build_service_from_router(mt_router)

    def _get():
        with svc:
            return svc.get_mangle_rules()

    try:
        rules = await asyncio.to_thread(_get)
        return {"rules": [MangleRule(**r) for r in rules], "error": None}
    except MikrotikError as e:
        return {"rules": [], "error": str(e)}
    except Exception as e:
        return {"rules": [], "error": f"Error inesperado: {e}"}


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
        counts = await asyncio.to_thread(_apply)
    except MikrotikError as e:
        raise HTTPException(502, str(e))
    added = counts.get("added", 0)
    enabled = counts.get("enabled", 0)
    skipped = counts.get("skipped", 0)
    msg = f"{added} agregadas, {enabled} reactivadas, {skipped} ya existían"
    return TemplateResult(template=template, rules_added=added, rules_enabled=enabled, rules_skipped=skipped, message=msg)


# ── Queue Tree with stats ─────────────────────────────────────────────────

@router.get("/{router_id}/queue-tree-stats")
async def get_queue_tree_stats(router_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    mt_router = await _get_router_or_404(router_id, db)
    svc = build_service_from_router(mt_router)

    def _get():
        with svc:
            return svc.get_queue_tree_with_stats()

    try:
        entries = await asyncio.to_thread(_get)
        return {"entries": entries, "error": None}
    except MikrotikError as e:
        return {"entries": [], "error": str(e)}
    except Exception as e:
        return {"entries": [], "error": f"Error inesperado: {e}"}


class ProfessionalTreeRequest(BaseModel):
    download_mbps: int
    upload_mbps: int


@router.post("/{router_id}/queue-tree-professional")
async def apply_professional_tree(
    router_id: int,
    body: ProfessionalTreeRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    mt_router = await _get_router_or_404(router_id, db)
    svc = build_service_from_router(mt_router)

    def _apply():
        with svc:
            return svc.apply_professional_qos_tree(body.download_mbps, body.upload_mbps)

    try:
        result = await asyncio.to_thread(_apply)
        return {**result, "message": f"Arbol QoS profesional aplicado ({result['added']} entradas creadas)"}
    except MikrotikError as e:
        raise HTTPException(502, str(e))
    except Exception as e:
        raise HTTPException(502, f"Error inesperado: {e}")


# ── PCQ ───────────────────────────────────────────────────────────────────────

@router.get("/{router_id}/pcq")
async def get_pcq_queues(router_id: int, db: AsyncSession = Depends(get_db)):
    mt_router = await _get_router_or_404(router_id, db)
    svc = build_service_from_router(mt_router)

    def _get():
        with svc:
            return svc.get_pcq_queues()

    try:
        queues = await asyncio.to_thread(_get)
        return {"queues": [PCQQueue(**q) for q in queues], "error": None}
    except MikrotikError as e:
        return {"queues": [], "error": str(e)}
    except Exception as e:
        return {"queues": [], "error": f"Error inesperado: {e}"}


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
