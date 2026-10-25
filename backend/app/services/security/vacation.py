import logging
from datetime import date
from typing import List, Optional

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security.contract import VacationMode

logger = logging.getLogger(__name__)


class VacationModeCreate(BaseModel):
    subscription_id: int
    start_date: date
    end_date: date
    notes: Optional[str] = None


async def list_vacation_modes(
    db: AsyncSession, subscription_id: int
) -> List[VacationMode]:
    result = await db.execute(
        select(VacationMode)
        .where(VacationMode.subscription_id == subscription_id)
        .order_by(VacationMode.start_date.desc())
    )
    return result.scalars().all()


async def create_vacation_mode(
    db: AsyncSession, body: VacationModeCreate, created_by_user_id: Optional[int]
) -> VacationMode:
    if body.end_date <= body.start_date:
        raise HTTPException(
            status_code=422,
            detail="La fecha de fin debe ser posterior a la fecha de inicio",
        )

    # Only one active vacation mode at a time
    result = await db.execute(
        select(VacationMode).where(
            VacationMode.subscription_id == body.subscription_id,
            VacationMode.active == True,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Ya hay un modo ausencia activo para esta suscripción",
        )

    vm = VacationMode(
        subscription_id=body.subscription_id,
        start_date=body.start_date,
        end_date=body.end_date,
        notes=body.notes,
        created_by_user_id=created_by_user_id,
        active=True,
    )
    db.add(vm)
    await db.commit()
    await db.refresh(vm)

    # Notify client via Telegram
    try:
        from app.models.security.subscription import SecuritySubscription
        from app.services.telegram import send_telegram_to
        sub = await db.get(SecuritySubscription, body.subscription_id)
        if sub and sub.client_telegram_id:
            await send_telegram_to(
                sub.client_telegram_id,
                f"🏖️ *Modo ausencia activado*\n"
                f"Tu propiedad quedará bajo monitoreo elevado desde el "
                f"{body.start_date.strftime('%d/%m/%Y')} hasta el "
                f"{body.end_date.strftime('%d/%m/%Y')}.\n"
                f"Cualquier movimiento detectado generará una alerta inmediata.",
            )
    except Exception as exc:
        logger.warning("Could not send vacation mode Telegram notification: %s", exc)

    return vm


_CANCEL_SOURCE_LABELS = {
    "panel": "panel de administración",
    "portal": "portal del cliente",
}


async def cancel_vacation_mode(
    db: AsyncSession, vacation_id: int, source: str = "panel"
) -> VacationMode:
    vm = await db.get(VacationMode, vacation_id)
    if vm is None:
        raise HTTPException(status_code=404, detail="Modo ausencia no encontrado")
    if not vm.active:
        raise HTTPException(status_code=409, detail="El modo ausencia ya está cancelado")
    vm.active = False
    await db.commit()
    await db.refresh(vm)

    # Every cancellation lowers protection on an empty home: always tell both
    # the client and the monitoring central, so an unauthorized one is noticed.
    from datetime import datetime
    from app.models.security.subscription import SecuritySubscription
    from app.services.telegram import send_telegram, send_telegram_to

    source_label = _CANCEL_SOURCE_LABELS.get(source, source)
    when = datetime.now().strftime("%d/%m/%Y %H:%M")
    sub = await db.get(SecuritySubscription, vm.subscription_id)

    try:
        if sub and sub.client_telegram_id:
            await send_telegram_to(
                sub.client_telegram_id,
                "✅ *Modo ausencia cancelado*\n"
                f"Cancelado desde el {source_label} el {when}.\n"
                "El monitoreo volvió a su configuración normal.\n"
                "_Si no fuiste vos, comunicate con la central de inmediato._",
            )
    except Exception as exc:
        logger.warning("Could not send vacation cancel notification to client: %s", exc)

    try:
        await send_telegram(
            f"🏖️ *Modo ausencia cancelado* — Suscripción #{vm.subscription_id}\n"
            f"Origen: {source_label} · {when}\n"
            f"Período previsto: {vm.start_date.strftime('%d/%m/%Y')} → {vm.end_date.strftime('%d/%m/%Y')}"
        )
    except Exception as exc:
        logger.warning("Could not send vacation cancel notification to operators: %s", exc)

    return vm


async def get_active_vacation(
    db: AsyncSession, subscription_id: int
) -> Optional[VacationMode]:
    today = date.today()
    result = await db.execute(
        select(VacationMode).where(
            VacationMode.subscription_id == subscription_id,
            VacationMode.active == True,
            VacationMode.start_date <= today,
            VacationMode.end_date >= today,
        )
    )
    return result.scalar_one_or_none()
