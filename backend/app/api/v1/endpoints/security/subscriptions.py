from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.core.deps import get_current_user, get_db
from app.schemas.security.beat import BeatAccountStatusResponse
from app.schemas.security.subscription import (
    SecurityFeatureToggle,
    SecuritySubscriptionCreate,
    SecuritySubscriptionResponse,
    SecuritySubscriptionUpdate,
)
from app.services.security import subscriptions as svc

router = APIRouter()


@router.get("/", response_model=List[SecuritySubscriptionResponse])
async def list_subscriptions(
    property_id: Optional[int] = Query(default=None),
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    return await svc.list_subscriptions(db, property_id=property_id)


@router.post("/", response_model=SecuritySubscriptionResponse, status_code=201)
async def create_subscription(
    body: SecuritySubscriptionCreate,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    return await svc.create_subscription(db, body)


@router.get("/{subscription_id}", response_model=SecuritySubscriptionResponse)
async def get_subscription(
    subscription_id: int,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    return await svc.get_subscription(db, subscription_id)


@router.patch("/{subscription_id}", response_model=SecuritySubscriptionResponse)
async def update_subscription(
    subscription_id: int,
    body: SecuritySubscriptionUpdate,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    return await svc.update_subscription(db, subscription_id, body)


@router.post("/{subscription_id}/features", response_model=SecuritySubscriptionResponse)
async def toggle_feature(
    subscription_id: int,
    body: SecurityFeatureToggle,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    return await svc.toggle_feature(db, subscription_id, body)


@router.get("/{subscription_id}/beat-status", response_model=BeatAccountStatusResponse)
async def get_beat_status(
    subscription_id: int,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    status = await svc.get_beat_status(db, subscription_id)
    return BeatAccountStatusResponse(
        account_id=status.account_id,
        armed=status.armed,
        last_event_at=status.last_event_at,
        signal_ok=status.signal_ok,
        battery_ok=status.battery_ok,
        power_ok=status.power_ok,
        available=status.available,
        error_message=status.error_message,
        is_simulated=status.is_simulated,
    )


class RegenerateTokenResponse(BaseModel):
    portal_token: str
    portal_url: str


@router.post("/{subscription_id}/regenerate-portal-token", response_model=RegenerateTokenResponse)
async def regenerate_portal_token(
    subscription_id: int,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Generate a new portal access token for the subscription.
    Invalidates the previous token immediately.
    If client_telegram_id is set, sends the new link via Telegram.
    """
    import uuid
    from sqlalchemy import select
    from app.models.security.subscription import SecuritySubscription
    from app.core.config import settings

    result = await db.execute(
        select(SecuritySubscription).where(SecuritySubscription.id == subscription_id)
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")

    sub.portal_token = uuid.uuid4().hex
    await db.commit()

    portal_url = f"{settings.PUBLIC_URL}/seguridad?token={sub.portal_token}"

    if sub.client_telegram_id:
        from app.services.telegram import send_telegram_to
        await send_telegram_to(
            sub.client_telegram_id,
            f"🔐 *Tu acceso al portal de seguridad*\n\n"
            f"Podés ver el estado de tu alarma, eventos recientes y más en:\n"
            f"{portal_url}\n\n"
            f"_Guardá este enlace. Si lo perdés, tu operador puede generar uno nuevo._",
        )

    return RegenerateTokenResponse(portal_token=sub.portal_token, portal_url=portal_url)
