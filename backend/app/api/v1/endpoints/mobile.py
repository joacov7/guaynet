"""
Mobile app (Android, Capacitor) endpoints.

The app reuses the portal endpoints (/portal/security/...) by sending its device
credential in `Authorization: Device <id>.<secret>`; the ones here only cover
linking, push registration and the summary screen.
"""
from datetime import datetime
from typing import List, Optional
from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.security.app_device import SecurityAppDevice
from app.services.security import app_devices as svc

router = APIRouter()
admin_router = APIRouter()


class PairRequest(BaseModel):
    # The portal link the client received, or just its token
    portal_link: str = Field(min_length=8, max_length=500)
    pin: str = Field(min_length=1, max_length=12)
    device_name: str = Field(default="Teléfono", max_length=100)
    platform: str = Field(default="android", pattern="^(android|ios|web)$")


class PushTokenRequest(BaseModel):
    push_token: str = Field(min_length=10, max_length=512)


class AppDeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subscription_id: int
    device_name: str
    platform: str
    has_push: bool = False
    last_seen_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_at: datetime

    @classmethod
    def from_model(cls, d: SecurityAppDevice) -> "AppDeviceResponse":
        r = cls.model_validate(d)
        r.has_push = bool(d.push_token)
        return r


def _extract_token(link: str) -> str:
    link = link.strip()
    if "token=" in link:
        values = parse_qs(urlparse(link).query).get("token")
        if values:
            return values[0]
    return link


async def _require_device(request: Request, db: AsyncSession):
    auth = await svc.authenticate_device(db, request.headers.get("Authorization"))
    if auth is None:
        raise HTTPException(
            status_code=401, detail="Falta la credencial del dispositivo", headers={"X-Device-Revoked": "1"}
        )
    return auth


@router.post("/pair")
async def pair(body: PairRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Link a phone: valid portal link + alarm PIN. Returns the device credential
    once; the app must store it. A duress PIN links normally but raises a
    silent DURESS alert.
    """
    from datetime import timezone
    from app.api.v1.endpoints.portal import _resolve_portal_subscription
    from app.models.security.alert import SecurityAlert, SecurityAlertStatus, SecurityAlertType
    from app.models.security.pin import PinType
    from app.services.security.notifications import dispatch_alert
    from app.services.security.pins import verify_owner_pin

    token = _extract_token(body.portal_link)
    sub = await _resolve_portal_subscription(token, request, db, allow_device=False)
    pin_type = await verify_owner_pin(db, sub.id, body.pin)
    device, secret = await svc.pair_device(db, sub.id, body.device_name, body.platform)

    if pin_type == PinType.duress:
        alert = SecurityAlert(
            subscription_id=sub.id,
            alert_type=SecurityAlertType.DURESS,
            status=SecurityAlertStatus.new,
            triggered_at=datetime.now(timezone.utc),
            idempotency_key=f"duress_app_pair:{device.id}",
            operator_notes="PIN de coacción usado al vincular un teléfono a la app",
        )
        db.add(alert)
        await db.commit()
        await db.refresh(alert)
        await dispatch_alert(alert, db)

    return {"device_id": device.id, "credential": f"{device.id}.{secret}"}


@router.get("/security")
async def app_security(request: Request, db: AsyncSession = Depends(get_db)):
    from app.api.v1.endpoints.portal import _security_payload
    from app.models.security.property import Property

    _, sub = await _require_device(request, db)
    prop = await db.get(Property, sub.property_id)
    return await _security_payload(sub, prop, db)


@router.put("/push-token", status_code=204)
async def set_push_token(body: PushTokenRequest, request: Request, db: AsyncSession = Depends(get_db)):
    device, _ = await _require_device(request, db)
    device.push_token = body.push_token
    await db.commit()


@router.delete("/device", status_code=204)
async def unlink_self(request: Request, db: AsyncSession = Depends(get_db)):
    device, _ = await _require_device(request, db)
    await svc.revoke_device(db, device)


# ── Admin ─────────────────────────────────────────────────────────────────────

@admin_router.get("/subscriptions/{subscription_id}/app-devices", response_model=List[AppDeviceResponse])
async def list_app_devices(
    subscription_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return [AppDeviceResponse.from_model(d) for d in await svc.list_devices(db, subscription_id)]


@admin_router.post("/app-devices/{device_id}/revoke", response_model=AppDeviceResponse)
async def revoke_app_device(
    device_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    device = await db.get(SecurityAppDevice, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    return AppDeviceResponse.from_model(await svc.revoke_device(db, device))
