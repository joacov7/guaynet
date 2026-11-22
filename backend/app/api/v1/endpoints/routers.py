import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
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
from app.services.mikrotik import MikrotikError, build_service_from_router

logger = logging.getLogger(__name__)

router = APIRouter()


async def _router_response(rt: MikrotikRouter, db: AsyncSession) -> RouterResponse:
    count_result = await db.execute(select(func.count()).where(Client.router_id == rt.id))
    count = count_result.scalar_one()
    data = RouterResponse.model_validate(rt)
    data.client_count = count
    return data


# ── Mikrotik Routers ──────────────────────────────────────────────────────────

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
    """Push all active clients assigned to this router into Mikrotik Simple Queues."""
    rt = await db.get(MikrotikRouter, router_id)
    if not rt:
        raise HTTPException(status_code=404, detail="Router no encontrado")

    result = await db.execute(
        select(Client).where(Client.router_id == router_id, Client.status != "cancelled")
    )
    clients = result.scalars().all()

    if not clients:
        logger.warning("sync router=%d: no clients assigned to this router", router_id)
        return {"synced": 0, "skipped": 0, "errors": [], "clients_found": 0,
                "warning": "No hay clientes asignados a este router"}

    # One connection, same rules as everywhere else (services/provisioning.py)
    from app.services.provisioning import provision_clients

    results = await provision_clients(db, clients)
    errors = [
        {"client_id": c.id, "name": c.full_name, "error": results[c.id].message}
        for c in clients if c.id in results and not results[c.id].ok
    ]
    if errors and len(errors) == len(clients) and all("router" in e["error"].lower() for e in errors):
        raise HTTPException(status_code=503, detail=errors[0]["error"])
    synced = sum(1 for c in clients if c.id in results and results[c.id].ok and results[c.id].message != "sin cambios")
    skipped = sum(1 for c in clients if c.id in results and results[c.id].ok and results[c.id].message == "sin cambios")
    logger.info("sync router=%d: %d updated, %d unchanged, %d errors", router_id, synced, skipped, len(errors))
    return {"synced": synced, "skipped": skipped, "errors": errors, "clients_found": len(clients)}


@router.get("/{router_id}/bandwidth")
async def get_router_bandwidth(
    router_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Queue byte/packet stats crossed with registered clients."""
    rt = await db.get(MikrotikRouter, router_id)
    if not rt:
        raise HTTPException(status_code=404, detail="Router no encontrado")

    result = await db.execute(
        select(Client).where(Client.router_id == router_id, Client.status != "cancelled")
    )
    client_map = {c.mikrotik_queue_name: c for c in result.scalars().all()}

    def _get():
        svc = build_service_from_router(rt)
        with svc:
            return svc.get_simple_queues()

    try:
        queues = await asyncio.to_thread(_get)
    except MikrotikError as e:
        raise HTTPException(status_code=503, detail=str(e))

    queue_names_on_router = {q["name"] for q in queues}
    items = []
    for q in queues:
        client = client_map.get(q["name"])
        parts = (q.get("bytes") or "0/0").split("/")
        upload_bytes = int(parts[0]) if parts[0].isdigit() else 0
        download_bytes = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        items.append({
            "queue_name": q["name"],
            "client_id": client.id if client else None,
            "client_name": client.full_name if client else None,
            "ip_address": client.ip_address if client else q.get("target", ""),
            "max_limit": q["max_limit"],
            "disabled": q["disabled"],
            "upload_bytes": upload_bytes,
            "download_bytes": download_bytes,
            "missing_queue": False,
        })

    # Append DB clients whose queue no longer exists on the router
    for qname, client in client_map.items():
        if qname not in queue_names_on_router:
            items.append({
                "queue_name": qname,
                "client_id": client.id,
                "client_name": client.full_name,
                "ip_address": client.ip_address,
                "max_limit": "—",
                "disabled": False,
                "upload_bytes": 0,
                "download_bytes": 0,
                "missing_queue": True,
            })

    items.sort(key=lambda x: (x["missing_queue"], -(x["download_bytes"] + x["upload_bytes"])))
    return items


@router.get("/{router_id}/online-clients")
async def get_online_clients(
    router_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Cross ARP table with registered clients to show who is currently online."""
    rt = await db.get(MikrotikRouter, router_id)
    if not rt:
        raise HTTPException(status_code=404, detail="Router no encontrado")

    result = await db.execute(
        select(Client).where(Client.router_id == router_id, Client.status != "cancelled")
    )
    client_map = {c.ip_address: c for c in result.scalars().all()}

    def _get_arp():
        svc = build_service_from_router(rt)
        with svc:
            return svc.get_arp_table()

    try:
        arp_table = await asyncio.to_thread(_get_arp)
    except MikrotikError as e:
        raise HTTPException(status_code=503, detail=str(e))

    online_ips: dict = {}   # {ip: mac}
    online_macs: dict = {}  # {mac_upper: ip}
    for e in arp_table:
        if e.get("address") and e.get("complete", "true") != "false":
            ip = e["address"]
            mac = (e.get("mac-address") or "").upper()
            online_ips[ip] = mac
            if mac:
                online_macs[mac] = ip

    mac_to_client = {
        c.mac_address.upper(): c
        for c in client_map.values()
        if c.mac_address
    }

    items = []
    handled_ips: set = set()
    handled_client_ids: set = set()

    for ip, client in client_map.items():
        if ip in online_ips:
            items.append({
                "client_id": client.id,
                "client_name": client.full_name,
                "ip_address": ip,
                "mac_address": online_ips[ip] or client.mac_address or "",
                "status": client.status,
                "online": True,
                "ip_changed": False,
            })
            handled_ips.add(ip)
        else:
            stored_mac = (client.mac_address or "").upper()
            if stored_mac and stored_mac in online_macs:
                new_ip = online_macs[stored_mac]
                items.append({
                    "client_id": client.id,
                    "client_name": client.full_name,
                    "ip_address": ip,
                    "new_ip": new_ip,
                    "mac_address": stored_mac,
                    "status": client.status,
                    "online": True,
                    "ip_changed": True,
                })
                handled_ips.add(new_ip)
            else:
                items.append({
                    "client_id": client.id,
                    "client_name": client.full_name,
                    "ip_address": ip,
                    "mac_address": client.mac_address or "",
                    "status": client.status,
                    "online": False,
                    "ip_changed": False,
                })
        handled_client_ids.add(client.id)

    # Unregistered devices in ARP not matched to any client
    for ip, mac in online_ips.items():
        if ip in handled_ips:
            continue
        if mac and mac in mac_to_client and mac_to_client[mac].id in handled_client_ids:
            continue
        items.append({
            "client_id": None,
            "client_name": None,
            "ip_address": ip,
            "mac_address": mac,
            "status": None,
            "online": True,
            "ip_changed": False,
        })

    items.sort(key=lambda x: (not x["online"], x["ip_address"]))
    return items


@router.post("/{router_id}/clients/{client_id}/update-ip")
async def update_client_ip(
    router_id: int,
    client_id: int,
    new_ip: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    import ipaddress

    from app.services.provisioning import provision_client

    client = await db.get(Client, client_id)
    if not client or client.router_id != router_id:
        raise HTTPException(status_code=404)
    try:
        new_ip = str(ipaddress.IPv4Address(new_ip.strip()))
    except ValueError:
        raise HTTPException(status_code=422, detail="IP inválida")
    dup = (await db.execute(select(Client.id).where(Client.ip_address == new_ip, Client.id != client_id))).first()
    if dup:
        raise HTTPException(status_code=400, detail=f"La IP {new_ip} ya está en uso")
    old_ip = client.ip_address
    client.ip_address = new_ip
    await db.commit()

    # Moves the queue target and, if the client is suspended, the block too
    result = await provision_client(db, client)
    return {"updated": True, "old_ip": old_ip, "new_ip": new_ip,
            "mikrotik": result.message, "mikrotik_ok": result.ok}


@router.post("/{router_id}/setup-qos")
async def setup_qos(
    router_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Apply PCQ queue types + mangle QoS prioritization rules."""
    rt = await db.get(MikrotikRouter, router_id)
    if not rt:
        raise HTTPException(status_code=404, detail="Router no encontrado")

    def _setup():
        svc = build_service_from_router(rt)
        with svc:
            pcq_added = svc.setup_pcq()
            sfq_added = svc.setup_sfq()
            counts = svc.apply_template("qos_prioritization")
            tree_result = {}
            if rt.uplink_interface:
                tree_result = svc.setup_queue_tree(
                    rt.uplink_interface,
                    rt.lan_interface,
                    rt.uplink_upload_mbps,
                    rt.uplink_download_mbps,
                )
            return {"pcq_added": pcq_added, "sfq_added": sfq_added, **counts, "tree": tree_result}

    try:
        return await asyncio.to_thread(_setup)
    except MikrotikError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/{router_id}/utilization")
async def get_utilization(
    router_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Interface stats + queue byte totals for utilization monitoring."""
    rt = await db.get(MikrotikRouter, router_id)
    if not rt:
        raise HTTPException(status_code=404, detail="Router no encontrado")

    def _get():
        svc = build_service_from_router(rt)
        with svc:
            interfaces = svc.get_interface_stats()
            queues = svc.get_simple_queues()
            resources = svc.get_system_resources()
            return interfaces, queues, resources

    try:
        interfaces, queues, resources = await asyncio.to_thread(_get)
    except MikrotikError as e:
        raise HTTPException(status_code=503, detail=str(e))

    total_dl_bytes = 0
    total_ul_bytes = 0
    for q in queues:
        if q["name"] == "guaynet-uplink":
            continue
        parts = (q.get("bytes") or "0/0").split("/")
        total_ul_bytes += int(parts[0]) if parts[0].isdigit() else 0
        total_dl_bytes += int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0

    return {
        "interfaces": interfaces,
        "uplink_download_mbps": rt.uplink_download_mbps,
        "uplink_upload_mbps": rt.uplink_upload_mbps,
        "queue_total_download_bytes": total_dl_bytes,
        "queue_total_upload_bytes": total_ul_bytes,
        **resources,
    }


# ── Ubiquiti Devices ──────────────────────────────────────────────────────────

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


@router.post("/{router_id}/sync-pppoe")
async def sync_all_pppoe(
    router_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Sync all PPPoE secrets for clients assigned to this router."""
    router_obj = await db.get(MikrotikRouter, router_id)
    if not router_obj:
        raise HTTPException(status_code=404, detail="Router not found")

    result = await db.execute(
        select(Client).where(Client.router_id == router_id, Client.pppoe_username.isnot(None))
    )
    clients = result.scalars().all()

    synced = 0
    errors = []

    for client in clients:
        if not client.pppoe_password_encrypted:
            continue
        pppoe_password = decrypt_value(client.pppoe_password_encrypted)
        disabled = client.status != "active"

        def _sync(c=client, pw=pppoe_password, dis=disabled):
            svc = build_service_from_router(router_obj)
            with svc:
                existing = svc.get_pppoe_secrets()
                found = next((s for s in existing if s.get("name") == c.pppoe_username), None)
                if found:
                    return svc.update_pppoe_secret(c.pppoe_username, password=pw, ip_address=c.ip_address, disabled=dis)
                else:
                    return svc.add_pppoe_secret(c.pppoe_username, pw, c.ip_address, comment=f"guaynet-client-{c.id}")

        try:
            ok = await asyncio.to_thread(_sync)
            if ok:
                synced += 1
            else:
                errors.append(client.pppoe_username)
        except Exception as e:
            errors.append(f"{client.pppoe_username}: {e}")

    return {"synced": synced, "errors": errors}
