from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.security.elderly import SecurityElderlyConfig

router = APIRouter()


class ElderlyConfigRequest(BaseModel):
    check_from: str = "07:00"
    check_until: str = "10:00"
    notify_telegram_id: Optional[str] = None
    enabled: bool = True

    @field_validator("check_from", "check_until")
    @classmethod
    def validate_time(cls, v: str) -> str:
        parts = v.split(":")
        if len(parts) != 2:
            raise ValueError("Formato de hora inválido, use HH:MM")
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError("Hora fuera de rango")
        return f"{h:02d}:{m:02d}"


class ElderlyConfigResponse(BaseModel):
    id: int
    subscription_id: int
    check_from: str
    check_until: str
    notify_telegram_id: Optional[str]
    enabled: bool

    class Config:
        from_attributes = True


@router.get("/{subscription_id}/elderly-config", response_model=ElderlyConfigResponse)
async def get_elderly_config(
    subscription_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SecurityElderlyConfig).where(
            SecurityElderlyConfig.subscription_id == subscription_id
        )
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="Configuración no encontrada")
    return config


@router.put("/{subscription_id}/elderly-config", response_model=ElderlyConfigResponse)
async def upsert_elderly_config(
    subscription_id: int,
    body: ElderlyConfigRequest,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or replace the elderly check-in config for a subscription."""
    result = await db.execute(
        select(SecurityElderlyConfig).where(
            SecurityElderlyConfig.subscription_id == subscription_id
        )
    )
    config = result.scalar_one_or_none()

    if config is None:
        config = SecurityElderlyConfig(subscription_id=subscription_id)
        db.add(config)

    config.check_from = body.check_from
    config.check_until = body.check_until
    config.notify_telegram_id = body.notify_telegram_id
    config.enabled = body.enabled

    await db.commit()
    await db.refresh(config)
    return config


@router.delete("/{subscription_id}/elderly-config", status_code=status.HTTP_204_NO_CONTENT)
async def delete_elderly_config(
    subscription_id: int,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SecurityElderlyConfig).where(
            SecurityElderlyConfig.subscription_id == subscription_id
        )
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="Configuración no encontrada")
    await db.delete(config)
    await db.commit()
