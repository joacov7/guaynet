import ipaddress
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import effective_permissions, get_current_user, get_db, require_admin, require_permission
from app.core.security import get_password_hash
from app.models.audit import AuditLog
from app.models.bandwidth import BandwidthSample
from app.models.client import Client
from app.models.config import SystemConfig
from app.models.user import User

router = APIRouter()

VALID_ROLES = {"admin", "operator", "technician"}


# ── Users ─────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    full_name: str = ""
    password: str
    role: str = "operator"


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    rows = (await db.execute(select(User).order_by(User.id))).scalars().all()
    return [
        {
            "id": u.id, "username": u.username, "email": u.email,
            "full_name": u.full_name, "role": u.role,
            "is_active": u.is_active, "is_superuser": u.is_superuser,
        }
        for u in rows
    ]


@router.get("/users/assignable")
async def list_assignable_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Active users to assign tickets / work orders (only name and role)."""
    if current_user.role != "admin" and not current_user.is_superuser:
        perms = await effective_permissions(db, current_user)
        if not any(perms.get(s, (False, False))[0] for s in ("tickets", "work_orders")):
            raise HTTPException(status_code=403, detail="No tenés permiso para ver esta sección")
    rows = (await db.execute(select(User).where(User.is_active.is_(True)).order_by(User.full_name))).scalars().all()
    return [{"id": u.id, "username": u.username, "full_name": u.full_name, "role": u.role} for u in rows]


@router.post("/users", status_code=201)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    if body.role not in VALID_ROLES:
        raise HTTPException(400, f"Rol inválido. Válidos: {sorted(VALID_ROLES)}")
    existing = (await db.execute(select(User).where(User.username == body.username))).scalar_one_or_none()
    if existing:
        raise HTTPException(400, "El nombre de usuario ya existe")
    user = User(
        username=body.username,
        email=body.email,
        full_name=body.full_name,
        hashed_password=get_password_hash(body.password),
        role=body.role,
        is_active=True,
        is_superuser=(body.role == "admin"),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"id": user.id, "username": user.username, "role": user.role}


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "Usuario no encontrado")
    if body.role is not None:
        if body.role not in VALID_ROLES:
            raise HTTPException(400, f"Rol inválido. Válidos: {sorted(VALID_ROLES)}")
        user.role = body.role
        user.is_superuser = (body.role == "admin")
    if body.email is not None:
        user.email = body.email
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.password:
        user.hashed_password = get_password_hash(body.password)
    await db.commit()
    await db.refresh(user)
    return {
        "id": user.id, "username": user.username, "email": user.email,
        "full_name": user.full_name, "role": user.role,
        "is_active": user.is_active, "is_superuser": user.is_superuser,
    }


# ── System config ─────────────────────────────────────────────────────────────

# Managed from Seguridad → Configuración; never returned here (secret, encrypted)
_PANEL_ONLY_KEYS = {"telegram_bot_token", "beat_api_key", "beat_webhook_secret"}


class ConfigUpdate(BaseModel):
    suspension_action: Optional[str] = None
    suspension_speed: Optional[str] = None
    # Overdue-notice page for suspended clients (see services/provisioning.py)
    suspension_notice_ip: Optional[str] = None
    suspension_notice_port: Optional[str] = None
    suspension_payment_hosts: Optional[str] = None
    # WhatsApp / Twilio
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_whatsapp_from: Optional[str] = None
    whatsapp_reminder_template: Optional[str] = None
    # SMTP email alerts
    smtp_host: Optional[str] = None
    smtp_port: Optional[str] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None
    alert_email: Optional[str] = None
    # MercadoPago
    mp_access_token: Optional[str] = None
    mp_public_key: Optional[str] = None
    mp_webhook_secret: Optional[str] = None  # "Clave secreta" of the webhook in MercadoPago
    # AFIP / ARCA electronic invoicing
    afip_cuit: Optional[str] = None
    afip_punto_venta: Optional[str] = None
    afip_cbte_tipo: Optional[str] = None
    afip_cert_pem: Optional[str] = None
    afip_key_pem: Optional[str] = None
    afip_production: Optional[str] = None
    # Router monitoring thresholds
    cpu_alert_threshold: Optional[str] = None
    cpu_consecutive_checks: Optional[str] = None
    uplink_saturation_threshold: Optional[str] = None
    ram_alert_threshold: Optional[str] = None
    # Company data for invoice PDFs
    company_name: Optional[str] = None
    company_address: Optional[str] = None
    company_cuit: Optional[str] = None
    company_phone: Optional[str] = None  # shown on the overdue notice page

    @field_validator(
        "afip_punto_venta", "cpu_alert_threshold", "cpu_consecutive_checks",
        "uplink_saturation_threshold", "ram_alert_threshold", "suspension_notice_port",
        mode="before",
    )
    @classmethod
    def _numbers_as_text(cls, v):
        # Stored as text in SystemConfig; the form sends InputNumber values as numbers
        return None if v is None else str(v)


def _validate_suspension(updates: dict) -> None:
    import ipaddress

    from app.services.provisioning import parse_suspension_config

    ip = updates.get("suspension_notice_ip")
    if ip:
        try:
            ipaddress.IPv4Address(ip.strip())
        except ValueError:
            raise HTTPException(400, "La IP del servidor de avisos no es válida (ej: 192.168.88.10)")
        updates["suspension_notice_ip"] = ip.strip()
    port = updates.get("suspension_notice_port")
    if port and not (port.isdigit() and 1 <= int(port) <= 65535):
        raise HTTPException(400, "El puerto de avisos debe estar entre 1 y 65535")
    if "suspension_payment_hosts" in updates:
        cfg = parse_suspension_config({"suspension_payment_hosts": updates["suspension_payment_hosts"]})
        updates["suspension_payment_hosts"] = ", ".join(cfg.payment_hosts)


def _config_payload(rows) -> dict:
    """Config for the panel. Secrets are never sent back: only whether each is set."""
    from app.services.config_secrets import SECRET_KEYS

    out = {r.key: r.value for r in rows if r.key not in _PANEL_ONLY_KEYS and r.key not in SECRET_KEYS}
    stored = {r.key for r in rows if r.value}
    out["secrets_configured"] = {k: k in stored for k in sorted(SECRET_KEYS)}
    return out


@router.get("/config")
async def get_config(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    rows = (await db.execute(select(SystemConfig))).scalars().all()
    return _config_payload(rows)


@router.put("/config")
async def update_config(
    body: ConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    updates = body.model_dump(exclude_none=True)
    if "suspension_action" in updates and updates["suspension_action"] not in ("block", "disable", "throttle"):
        raise HTTPException(400, "suspension_action debe ser 'block' o 'throttle'")
    if updates.get("suspension_action") == "disable":
        updates["suspension_action"] = "block"  # "disable" never cut anyone (see provisioning.py)
    _validate_suspension(updates)
    from app.services.config_secrets import SECRET_KEYS, seal

    for key, value in updates.items():
        if key in SECRET_KEYS:
            if not value.strip():
                continue  # empty = keep the stored secret (the panel never receives it)
            value = seal(value.strip())
        row = await db.get(SystemConfig, key)
        if row:
            row.value = value
        else:
            db.add(SystemConfig(key=key, value=value))
    await db.commit()
    rows = (await db.execute(select(SystemConfig))).scalars().all()
    return _config_payload(rows)


@router.post("/test-email")
async def test_email(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    from app.services.email import test_email_config
    result = await test_email_config(db)
    if not result["ok"]:
        raise HTTPException(400, result["message"])
    return result


# ── Audit log ─────────────────────────────────────────────────────────────────

@router.get("/audit-logs")
async def list_audit_logs(
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("audit")),
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
    _: User = Depends(require_permission("ip_pool")),
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
    _: User = Depends(require_permission("bandwidth")),
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
    _: User = Depends(require_permission("map")),
):
    from app.models.router import MikrotikRouter, UbiquitiDevice

    routers = (await db.execute(select(MikrotikRouter))).scalars().all()
    aps = (await db.execute(select(UbiquitiDevice))).scalars().all()
    from sqlalchemy.orm import selectinload
    clients = (await db.execute(
        select(Client)
        .options(selectinload(Client.plan))
        .where(
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
                "plan_name": c.plan.name if c.plan else None,
                "address": c.address,
            }
            for c in clients
        ],
    }
