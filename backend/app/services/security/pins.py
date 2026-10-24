"""
PIN and safe word management.

Security rules enforced here:
- PIN is never stored in plain text (bcrypt via passlib).
- Duress PIN must be different from normal PIN (checked at set time).
- Safe word is stored as bcrypt hash.
- Verification is constant-time (passlib handles this).
- Temporary PINs require expires_at; normal/duress cannot have expires_at.
- Multiple temporary PINs allowed per subscription.
"""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security.pin import PinCredential, PinType, SafeWord
from app.core.security import get_password_hash, verify_password


async def set_pin(
    db: AsyncSession,
    subscription_id: int,
    pin_type: PinType,
    new_pin: str,
    current_pin: str | None = None,
    expires_at: datetime | None = None,
    label: str | None = None,
) -> PinCredential:
    """
    Set or replace a PIN for a subscription.

    Temporary PINs:
    - expires_at required; multiple allowed per subscription.
    - current_pin not required (admin action).

    Normal / duress PINs:
    - One per subscription; current_pin required to replace an existing one.
    - expires_at forbidden.
    - Normal and duress must differ.
    """
    if len(new_pin) < 4 or not new_pin.isdigit():
        raise HTTPException(status_code=422, detail="El PIN debe tener al menos 4 dígitos numéricos")

    if pin_type == PinType.temporary:
        if not expires_at:
            raise HTTPException(status_code=422, detail="PIN temporal requiere fecha de expiración")
        if expires_at <= datetime.now(timezone.utc):
            raise HTTPException(status_code=422, detail="La fecha de expiración debe ser futura")
        # Temporary PINs are always new — no replacement logic
        pin = PinCredential(
            subscription_id=subscription_id,
            pin_type=PinType.temporary,
            pin_hash=get_password_hash(new_pin),
            expires_at=expires_at,
            label=label,
        )
        db.add(pin)
        await db.commit()
        await db.refresh(pin)
        return pin

    # Normal / duress path
    if expires_at is not None:
        raise HTTPException(status_code=422, detail="Solo los PINs temporales pueden tener fecha de expiración")

    result = await db.execute(
        select(PinCredential).where(
            PinCredential.subscription_id == subscription_id,
            PinCredential.pin_type.in_([PinType.normal, PinType.duress]),
        )
    )
    all_pins = result.scalars().all()

    existing = next((p for p in all_pins if p.pin_type == pin_type), None)
    other = next((p for p in all_pins if p.pin_type != pin_type), None)

    if existing is not None:
        if current_pin is None:
            raise HTTPException(status_code=422, detail="Se requiere el PIN actual para cambiarlo")
        if not verify_password(current_pin, existing.pin_hash):
            raise HTTPException(status_code=401, detail="PIN actual incorrecto")

    if other is not None and verify_password(new_pin, other.pin_hash):
        raise HTTPException(
            status_code=422,
            detail="El PIN de coacción y el PIN normal no pueden ser iguales",
        )

    new_hash = get_password_hash(new_pin)
    if existing is not None:
        existing.pin_hash = new_hash
        existing.failed_attempts = 0
        existing.locked_until = None
        await db.commit()
        return existing
    else:
        pin = PinCredential(
            subscription_id=subscription_id,
            pin_type=pin_type,
            pin_hash=new_hash,
            label=label,
        )
        db.add(pin)
        await db.commit()
        await db.refresh(pin)
        return pin


async def list_temporary_pins(
    db: AsyncSession,
    subscription_id: int,
) -> List[PinCredential]:
    """Return all temporary PINs for a subscription, ordered by expiry."""
    result = await db.execute(
        select(PinCredential)
        .where(
            PinCredential.subscription_id == subscription_id,
            PinCredential.pin_type == PinType.temporary,
        )
        .order_by(PinCredential.expires_at)
    )
    return result.scalars().all()


async def delete_temporary_pin(
    db: AsyncSession,
    pin_id: int,
    subscription_id: int,
) -> None:
    """Revoke a temporary PIN. Verifies ownership via subscription_id."""
    result = await db.execute(
        select(PinCredential).where(
            PinCredential.id == pin_id,
            PinCredential.subscription_id == subscription_id,
            PinCredential.pin_type == PinType.temporary,
        )
    )
    pin = result.scalar_one_or_none()
    if pin is None:
        raise HTTPException(status_code=404, detail="PIN temporal no encontrado")
    await db.delete(pin)
    await db.commit()


async def set_safe_word(
    db: AsyncSession,
    subscription_id: int,
    word: str,
) -> None:
    """Set or replace the safe word for a subscription."""
    word = word.strip()
    if len(word) < 3:
        raise HTTPException(status_code=422, detail="La palabra segura debe tener al menos 3 caracteres")

    result = await db.execute(
        select(SafeWord).where(SafeWord.subscription_id == subscription_id)
    )
    existing = result.scalar_one_or_none()

    word_hash = get_password_hash(word)
    if existing is not None:
        existing.word_hash = word_hash
    else:
        db.add(SafeWord(subscription_id=subscription_id, word_hash=word_hash))
    await db.commit()


async def has_pin(db: AsyncSession, subscription_id: int, pin_type: PinType) -> bool:
    result = await db.execute(
        select(PinCredential).where(
            PinCredential.subscription_id == subscription_id,
            PinCredential.pin_type == pin_type,
        )
    )
    return result.scalar_one_or_none() is not None
