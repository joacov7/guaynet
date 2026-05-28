import ipaddress
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.audit import AuditLog
from app.models.bandwidth import BandwidthSample
from app.models.client import Client
from app.models.user import User

router = APIRouter()


# ── Audit log ─────────────────────────────────────────────────────────────────

@router.get("/audit-logs")
async def list_audit_logs(
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if entity_type:
        q = q.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        q = q.where(AuditLog.entity_id == entity_id)
    rows = (await db.execute(q)).scalars().all()
    return [
        {
            "id": r.id,
            "username": r.username,
            "action": r.action,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "entity_name": r.entity_name,
            "details": r.details,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


# ── IP pool ───────────────────────────────────────────────────────────────────

@router.get("/ip-pool")
async def ip_pool(
    subnet: str = Query(..., description="CIDR subnet, e.g. 192.168.1.0/24"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        network = ipaddress.ip_network(subnet, strict=False)
    except ValueError:
        return {"error": "Subnet inválida. Usá formato CIDR, ej: 192.168.1.0/24"}

    hosts = [str(ip) for ip in network.hosts()]
    clients = (await db.execute(select(Client))).scalars().all()
    used = {
        c.ip_address: {"client_id": c.id, "client_name": c.full_name, "status": c.status}
        for c in clients
        if c.ip_address in hosts
    }

    return {
        "subnet": subnet,
        "total_hosts": len(hosts),
        "used": len(used),
        "free": len(hosts) - len(used),
        "ips": [
            {
                "ip": ip,
                "free": ip not in used,
                **(used[ip] if ip in used else {}),
            }
            for ip in hosts
        ],
    }


# ── Bandwidth history ─────────────────────────────────────────────────────────

@router.get("/bandwidth-history")
async def bandwidth_history(
    router_id: int,
    hours: int = Query(default=24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = (await db.execute(
        select(BandwidthSample)
        .where(BandwidthSample.router_id == router_id, BandwidthSample.sampled_at >= since)
        .order_by(asc(BandwidthSample.sampled_at))
    )).scalars().all()

    # Group by (client_id or ip, sampled_at bucket per 5-min)
    result = []
    for r in rows:
        result.append({
            "sampled_at": r.sampled_at.isoformat(),
            "client_id": r.client_id,
            "ip_address": r.ip_address,
            "queue_name": r.queue_name,
            "upload_bytes": r.upload_bytes,
            "download_bytes": r.download_bytes,
        })
    return result


# ── Map data ──────────────────────────────────────────────────────────────────

@router.get("/map-data")
async def map_data(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from app.models.router import MikrotikRouter, UbiquitiDevice

    routers = (await db.execute(select(MikrotikRouter))).scalars().all()
    aps = (await db.execute(select(UbiquitiDevice))).scalars().all()
    clients = (await db.execute(
        select(Client).where(
            Client.latitude.isnot(None),
            Client.longitude.isnot(None),
        )
    )).scalars().all()

    return {
        "routers": [
            {
                "id": r.id, "name": r.name, "host": r.host,
                "status": r.status, "location": r.location,
                "latitude": r.latitude, "longitude": r.longitude,
                "client_count": len(r.clients) if hasattr(r, "clients") else 0,
            }
            for r in routers if r.latitude and r.longitude
        ],
        "access_points": [
            {
                "id": a.id, "name": a.name, "host": a.host,
                "device_type": a.device_type, "status": a.status,
                "latitude": a.latitude, "longitude": a.longitude,
                "ssid": a.ssid, "frequency_mhz": a.frequency_mhz,
            }
            for a in aps if a.latitude and a.longitude
        ],
        "clients": [
            {
                "id": c.id, "full_name": c.full_name, "ip_address": c.ip_address,
                "status": c.status, "latitude": c.latitude, "longitude": c.longitude,
            }
            for c in clients
        ],
    }
