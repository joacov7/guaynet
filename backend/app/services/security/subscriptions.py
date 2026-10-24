import asyncio
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security.subscription import (
    SecuritySubscription,
    SecuritySubscriptionStatus,
    SecurityFeature,
    SecurityFeatureName,
)
from app.schemas.security.subscription import (
    SecuritySubscriptionCreate,
    SecuritySubscriptionUpdate,
    SecurityFeatureToggle,
)
from app.services.security import get_beat_adapter


async def _get_with_features(db: AsyncSession, subscription_id: int) -> SecuritySubscription:
    result = await db.execute(
        select(SecuritySubscription)
        .options(selectinload(SecuritySubscription.features))
        .where(SecuritySubscription.id == subscription_id)
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")
    return sub


async def list_subscriptions(
    db: AsyncSession,
    property_id: Optional[int] = None,
    status: Optional[SecuritySubscriptionStatus] = None,
) -> List[SecuritySubscription]:
    q = (
        select(SecuritySubscription)
        .options(selectinload(SecuritySubscription.features))
        .order_by(SecuritySubscription.id.desc())
    )
    if property_id is not None:
        q = q.where(SecuritySubscription.property_id == property_id)
    if status is not None:
        q = q.where(SecuritySubscription.status == status)
    result = await db.execute(q)
    return result.scalars().all()


async def get_subscription(db: AsyncSession, subscription_id: int) -> SecuritySubscription:
    return await _get_with_features(db, subscription_id)


async def create_subscription(
    db: AsyncSession, body: SecuritySubscriptionCreate
) -> SecuritySubscription:
    # Enforce one active subscription per property
    existing = await db.execute(
        select(SecuritySubscription).where(
            SecuritySubscription.property_id == body.property_id,
            SecuritySubscription.status == SecuritySubscriptionStatus.active,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Ya existe una suscripción activa para esta propiedad",
        )

    sub = SecuritySubscription(**body.model_dump())
    db.add(sub)
    await db.flush()  # get sub.id before creating features

    # Seed features from plan defaults (all disabled by default — admin enables individually)
    from app.models.security.subscription import SecurityPlan
    plan = await db.get(SecurityPlan, body.plan_id)
    default_names = plan.default_features or [] if plan else []
    for fname in SecurityFeatureName:
        feature = SecurityFeature(
            subscription_id=sub.id,
            feature_name=fname,
            enabled=fname.value in default_names,
        )
        db.add(feature)

    await db.commit()
    return await _get_with_features(db, sub.id)


async def update_subscription(
    db: AsyncSession, subscription_id: int, body: SecuritySubscriptionUpdate
) -> SecuritySubscription:
    sub = await _get_with_features(db, subscription_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(sub, field, value)
    await db.commit()
    await db.refresh(sub)
    return await _get_with_features(db, sub.id)


async def toggle_feature(
    db: AsyncSession, subscription_id: int, body: SecurityFeatureToggle
) -> SecuritySubscription:
    await _get_with_features(db, subscription_id)  # existence check
    result = await db.execute(
        select(SecurityFeature).where(
            SecurityFeature.subscription_id == subscription_id,
            SecurityFeature.feature_name == body.feature_name,
        )
    )
    feature = result.scalar_one_or_none()
    if feature is None:
        raise HTTPException(status_code=404, detail="Feature no encontrada en esta suscripción")
    feature.enabled = body.enabled
    await db.commit()
    return await _get_with_features(db, subscription_id)


async def get_beat_status(db: AsyncSession, subscription_id: int):
    sub = await _get_with_features(db, subscription_id)
    if not sub.beat_account_id:
        raise HTTPException(
            status_code=422,
            detail="Esta suscripción no tiene beat_account_id configurado",
        )
    adapter = get_beat_adapter()
    status = await asyncio.to_thread(adapter.get_account_status, sub.beat_account_id)
    return status
