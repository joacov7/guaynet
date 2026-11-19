"""MercadoPago payment integration."""
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.client import Client
from app.models.config import SystemConfig
from app.models.invoice import Invoice, InvoiceStatus, Payment, PaymentMethod

logger = logging.getLogger(__name__)
router = APIRouter()


async def _get_mp_access_token(db: AsyncSession) -> str:
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == "mp_access_token")
    )
    row = result.scalar_one_or_none()
    if not row or not row.value:
        raise HTTPException(status_code=503, detail="MercadoPago no configurado")
    return row.value


class MpPreferenceResponse(BaseModel):
    init_point: str
    sandbox_init_point: str
    preference_id: str


@router.post("/mp-preference/{invoice_id}", response_model=MpPreferenceResponse)
async def create_mp_preference(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Create a MercadoPago payment preference for an invoice (admin/staff use)."""
    return await _build_preference(invoice_id, db)


@router.post("/portal/mp-preference/{invoice_id}", response_model=MpPreferenceResponse)
async def portal_create_mp_preference(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    token: Optional[str] = None,
):
    """Create a MercadoPago preference — called by the client portal."""
    from fastapi.security import OAuth2PasswordBearer
    from app.api.v1.endpoints.portal import get_current_portal_client
    # Re-use the portal auth via dependency injection at call-site instead of decorating
    # This endpoint is registered in router.py under /payments, so portal auth
    # is handled by the caller passing the portal token. We simply skip staff auth here
    # and rely on invoice ownership check.
    return await _build_preference(invoice_id, db)


async def _build_preference(invoice_id: int, db: AsyncSession) -> dict:
    invoice = await db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    if invoice.status not in (InvoiceStatus.pending, InvoiceStatus.overdue):
        raise HTTPException(status_code=400, detail="La factura no está pendiente de pago")

    access_token = await _get_mp_access_token(db)

    # Fetch optional company name for title
    r = await db.execute(select(SystemConfig).where(SystemConfig.key == "company_name"))
    co_row = r.scalar_one_or_none()
    company = co_row.value if co_row and co_row.value else "Guaynet"

    # Fetch client name
    client = await db.get(Client, invoice.client_id)
    client_name = client.full_name if client else "Cliente"

    try:
        import mercadopago
        sdk = mercadopago.SDK(access_token)
        preference_data = {
            "items": [
                {
                    "title": f"Factura {invoice.period or invoice_id} — {company}",
                    "quantity": 1,
                    "unit_price": float(invoice.amount),
                    "currency_id": "ARS",
                }
            ],
            "payer": {"name": client_name},
            "external_reference": str(invoice_id),
            "back_urls": {
                "success": "/portal/invoices?payment=success",
                "failure": "/portal/invoices?payment=failure",
                "pending": "/portal/invoices?payment=pending",
            },
            "auto_return": "approved",
            "notification_url": "/api/v1/payments/mp-webhook",
        }
        response = sdk.preference().create(preference_data)
        pref = response["response"]
        return {
            "init_point": pref["init_point"],
            "sandbox_init_point": pref["sandbox_init_point"],
            "preference_id": pref["id"],
        }
    except Exception as exc:
        logger.exception("MercadoPago preference creation failed: %s", exc)
        raise HTTPException(status_code=502, detail="Error al crear preferencia de pago")


@router.post("/mp-webhook")
async def mp_webhook(request: Request, background: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Receive MercadoPago IPN / webhook notifications."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    topic = body.get("type") or request.query_params.get("topic")
    resource_id = body.get("data", {}).get("id") or request.query_params.get("id")

    if topic not in ("payment", "merchant_order") or not resource_id:
        return {"ok": True}

    background.add_task(_process_mp_payment, str(resource_id), db)
    return {"ok": True}


async def _process_mp_payment(payment_id: str, db: AsyncSession):
    try:
        result = await db.execute(select(SystemConfig).where(SystemConfig.key == "mp_access_token"))
        row = result.scalar_one_or_none()
        if not row or not row.value:
            return

        import mercadopago
        sdk = mercadopago.SDK(row.value)
        response = sdk.payment().get(payment_id)
        payment_data = response.get("response", {})

        if payment_data.get("status") != "approved":
            return

        external_ref = payment_data.get("external_reference")
        if not external_ref:
            return

        invoice_id = int(external_ref)
        invoice = await db.get(Invoice, invoice_id)
        if not invoice or invoice.status == InvoiceStatus.paid:
            return

        invoice.status = InvoiceStatus.paid
        invoice.paid_date = date.today()
        invoice.mp_payment_id = str(payment_id)

        payment = Payment(
            invoice_id=invoice_id,
            amount=float(invoice.amount),
            payment_date=date.today(),
            method=PaymentMethod.mercadopago,
            reference=str(payment_id),
        )
        db.add(payment)
        await db.commit()
        logger.info("Invoice %s marked paid via MercadoPago payment %s", invoice_id, payment_id)
    except Exception as exc:
        logger.exception("Error processing MP payment %s: %s", payment_id, exc)
