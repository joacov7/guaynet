"""
PIN and safe word management.

Security rules enforced here:
- PIN is never stored in plain text (bcrypt via passlib).
- Duress PIN must be different from normal PIN (checked at set time).
- Safe word is stored as bcrypt hash.
- Verification is constant-time (passlib handles this).
"""
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
) -> None:
    """
    Set or replace a PIN for a subscription.
    If a PIN of the same type already exists, current_pin is required to replace it.
    Normal and duress PINs must be different.
    """
    if len(new_pin) < 4 or not new_pin.isdigit():
        raise HTTPException(status_code=422, detail="El PIN debe tener al menos 4 dígitos numéricos")

    result = await db.execute(
        select(PinCredential).where(PinCredential.subscription_id == subscription_id)
    )
    all_pins = result.scalars().all()

    existing = next((p for p in all_pins if p.pin_type == pin_type), None)
    other = next((p for p in all_pins if p.pin_type != pin_type), None)

    # Verify current PIN if one exists
    if existing is not None:
        if current_pin is None:
            raise HTTPException(status_code=422, detail="Se requiere el PIN actual para cambiarlo")
        if not verify_password(current_pin, existing.pin_hash):
            raise HTTPException(status_code=401, detail="PIN actual incorrecto")

    # Duress and normal PINs must differ
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
    else:
        db.add(PinCredential(
            subscription_id=subscription_id,
            pin_type=pin_type,
            pin_hash=new_hash,
        ))
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
