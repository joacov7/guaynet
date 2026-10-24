from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from app.core.deps import get_current_user, get_db
from app.models.security.pin import PinType
from app.services.security import pins as svc

router = APIRouter()


class SetPinRequest(BaseModel):
    subscription_id: int
    pin_type: PinType
    new_pin: str
    current_pin: Optional[str] = None
    expires_at: Optional[datetime] = None  # required for pin_type=temporary
    label: Optional[str] = None


class SetSafeWordRequest(BaseModel):
    subscription_id: int
    word: str


class PinStatusResponse(BaseModel):
    has_normal_pin: bool
    has_duress_pin: bool
    has_safe_word: bool


class TemporaryPinResponse(BaseModel):
    id: int
    label: Optional[str]
    expires_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/set", status_code=status.HTTP_204_NO_CONTENT)
async def set_pin(
    body: SetPinRequest,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    await svc.set_pin(
        db,
        body.subscription_id,
        body.pin_type,
        body.new_pin,
        body.current_pin,
        body.expires_at,
        body.label,
    )


@router.post("/safe-word", status_code=status.HTTP_204_NO_CONTENT)
async def set_safe_word(
    body: SetSafeWordRequest,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    await svc.set_safe_word(db, body.subscription_id, body.word)


@router.get("/status/{subscription_id}", response_model=PinStatusResponse)
async def pin_status(
    subscription_id: int,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    has_normal = await svc.has_pin(db, subscription_id, PinType.normal)
    has_duress = await svc.has_pin(db, subscription_id, PinType.duress)

    from sqlalchemy import select
    from app.models.security.pin import SafeWord
    result = await db.execute(
        select(SafeWord).where(SafeWord.subscription_id == subscription_id)
    )
    has_safe_word = result.scalar_one_or_none() is not None

    return PinStatusResponse(
        has_normal_pin=has_normal,
        has_duress_pin=has_duress,
        has_safe_word=has_safe_word,
    )


@router.get("/temporary/{subscription_id}", response_model=List[TemporaryPinResponse])
async def list_temporary_pins(
    subscription_id: int,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    """List all temporary PINs for a subscription, ordered by expiry."""
    pins = await svc.list_temporary_pins(db, subscription_id)
    return [
        TemporaryPinResponse(
            id=p.id,
            label=p.label,
            expires_at=p.expires_at,
            created_at=p.created_at,
        )
        for p in pins
    ]


@router.delete("/temporary/{pin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_temporary_pin(
    pin_id: int,
    subscription_id: int = Query(..., description="Subscription that owns the PIN"),
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    """Revoke a temporary PIN."""
    await svc.delete_temporary_pin(db, pin_id, subscription_id)
