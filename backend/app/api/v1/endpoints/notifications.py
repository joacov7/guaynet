from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.client import Client, ClientStatus
from app.models.config import SystemConfig
from app.models.invoice import Invoice, InvoiceStatus

router = APIRouter()


async def _get_config(db: AsyncSession, key: str, default: str = "") -> str:
    row = await db.get(SystemConfig, key)
    return row.value if row else default


async def _send_whatsapp(to_number: str, body: str, db: AsyncSession) -> dict:
    """Send a WhatsApp message via Twilio."""
    account_sid = await _get_config(db, "twilio_account_sid")
    auth_token = await _get_config(db, "twilio_auth_token")
    from_number = await _get_config(db, "twilio_whatsapp_from", "whatsapp:+14155238886")

    if not account_sid or not auth_token:
        raise HTTPException(status_code=400, detail="Twilio no configurado. Configurá las credenciales en Configuración.")

    # Normalize number: add whatsapp: prefix and country code if needed
    if not to_number.startswith("whatsapp:"):
        cleaned = to_number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if not cleaned.startswith("+"):
            cleaned = "+54" + cleaned.lstrip("0")
        to_number = f"whatsapp:{cleaned}"

    try:
        from twilio.rest import Client as TwilioClient
        client = TwilioClient(account_sid, auth_token)
        msg = client.messages.create(from_=from_number, to=to_number, body=body)
        return {"sid": msg.sid, "status": msg.status, "to": to_number}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error Twilio: {str(e)}")


class SendOneRequest(BaseModel):
    client_id: Optional[int] = None
    phone: Optional[str] = None
    message: str


class BulkReminderRequest(BaseModel):
    template: Optional[str] = None
    min_days_overdue: int = 0
    dry_run: bool = False


class BulkResult(BaseModel):
    sent: int
    failed: int
    skipped_no_phone: int
    details: List[dict]


@router.post("/whatsapp/send")
async def send_whatsapp_message(
    body: SendOneRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    if body.phone:
        phone = body.phone
    elif body.client_id:
        client = await db.get(Client, body.client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        if not client.phone:
            raise HTTPException(status_code=400, detail="El cliente no tiene teléfono registrado")
        phone = client.phone
    else:
        raise HTTPException(status_code=400, detail="Se requiere client_id o phone")

    result = await _send_whatsapp(phone, body.message, db)
    return result


@router.post("/whatsapp/bulk-reminder", response_model=BulkResult)
async def send_bulk_reminder(
    body: BulkReminderRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    from datetime import date
    today = date.today()

    default_template = await _get_config(
        db, "whatsapp_reminder_template",
        "Hola {nombre}, te recordamos que tenés una factura de ${monto} con vencimiento {vencimiento} pendiente de pago. Comunicate con nosotros para regularizar tu situación."
    )
    template = body.template or default_template

    result_q = await db.execute(
        select(
            Client.id,
            Client.first_name,
            Client.phone,
            Invoice.id.label("invoice_id"),
            Invoice.amount,
            Invoice.due_date,
        )
        .join(Invoice, Invoice.client_id == Client.id)
        .where(Invoice.status == InvoiceStatus.overdue)
        .order_by(Invoice.due_date)
    )
    rows = result_q.all()

    details = []
    sent = 0
    failed = 0
    skipped_no_phone = 0

    for row in rows:
        days = (today - row.due_date).days
        if days < body.min_days_overdue:
            continue

        if not row.phone:
            skipped_no_phone += 1
            details.append({"client_id": row.id, "status": "skipped", "reason": "sin teléfono"})
            continue

        msg = (
            template
            .replace("{nombre}", row.first_name)
            .replace("{monto}", f"{float(row.amount):,.2f}")
            .replace("{vencimiento}", row.due_date.strftime("%d/%m/%Y"))
        )

        if body.dry_run:
            details.append({"client_id": row.id, "phone": row.phone, "status": "dry_run", "message": msg})
            sent += 1
            continue

        try:
            r = await _send_whatsapp(row.phone, msg, db)
            details.append({"client_id": row.id, "phone": row.phone, "status": "sent", "sid": r.get("sid")})
            sent += 1
        except HTTPException as e:
            details.append({"client_id": row.id, "phone": row.phone, "status": "failed", "error": e.detail})
            failed += 1

    return BulkResult(sent=sent, failed=failed, skipped_no_phone=skipped_no_phone, details=details)
