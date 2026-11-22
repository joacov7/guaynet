"""MercadoPago payment integration."""
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.portal import get_current_portal_client
from app.core.database import AsyncSessionLocal
from app.core.deps import require_permission, get_db
from app.models.client import Client
from app.models.config import SystemConfig
from app.models.invoice import Invoice, InvoiceStatus, Payment, PaymentMethod

logger = logging.getLogger(__name__)
router = APIRouter()


async def _get_mp_access_token(db: AsyncSession) -> str:
    from app.services.config_secrets import config_value
    token = await config_value(db, "mp_access_token")
    if not token:
        raise HTTPException(status_code=503, detail="MercadoPago no configurado")
    return token


class MpPreferenceResponse(BaseModel):
    init_point: str
    sandbox_init_point: str
    preference_id: str


@router.post("/mp-preference/{invoice_id}", response_model=MpPreferenceResponse)
async def create_mp_preference(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("billing", "edit")),
):
    """Create a MercadoPago payment preference for an invoice (admin/staff use)."""
    return await _build_preference(invoice_id, db)


@router.post("/portal/mp-preference/{invoice_id}", response_model=MpPreferenceResponse)
async def portal_create_mp_preference(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    client: Client = Depends(get_current_portal_client),
):
    """Create a MercadoPago preference — called by the client portal, for its own invoices only."""
    invoice = await db.get(Invoice, invoice_id)
    if not invoice or invoice.client_id != client.id:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    return await _build_preference(invoice_id, db)


def _public_url(path: str) -> Optional[str]:
    """Absolute URL MercadoPago can reach, or None while PUBLIC_URL is the sample value
    (MercadoPago rejects relative URLs)."""
    from app.core.config import settings
    base = (settings.PUBLIC_URL or "").rstrip("/")
    if not base.startswith(("https://", "http://")) or "guaynet.local" in base:
        return None
    return base + path


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
            "payer": {"name": client_name, **({"email": client.email} if client and client.email else {})},
            "external_reference": str(invoice_id),
        }
        notify = _public_url("/api/v1/payments/mp-webhook")
        if notify:
            preference_data["notification_url"] = notify
            preference_data["back_urls"] = {
                k: _public_url(f"/portal/invoices?payment={k}") for k in ("success", "failure", "pending")
            }
            preference_data["auto_return"] = "approved"
        else:
            logger.warning("PUBLIC_URL is not set: MercadoPago will only notify payments "
                           "if the webhook is configured in the MercadoPago panel")
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
async def mp_webhook(request: Request, background: BackgroundTasks):
    """Receive MercadoPago notifications. The payment is always re-read from the
    MercadoPago API (a forged notification cannot mark anything paid); when a
    webhook secret is configured the x-signature header is checked too."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    topic = body.get("type") or body.get("topic") or request.query_params.get("type") or request.query_params.get("topic")
    resource_id = (body.get("data") or {}).get("id") or request.query_params.get("data.id") or request.query_params.get("id")
    if topic != "payment" or not resource_id or not str(resource_id).isdigit():
        return {"ok": True}

    from app.services.config_secrets import config_value
    async with AsyncSessionLocal() as db:
        secret = await config_value(db, "mp_webhook_secret")
    if secret and not _valid_signature(request, str(resource_id), secret):
        logger.warning("MercadoPago webhook with invalid signature for payment %s", resource_id)
        raise HTTPException(status_code=401, detail="Firma inválida")

    # Own session: the request's session is closed once the response is sent
    background.add_task(process_mp_payment, str(resource_id))
    return {"ok": True}


def _valid_signature(request: Request, data_id: str, secret: str) -> bool:
    """MercadoPago x-signature: "ts=...,v1=<hmac-sha256 of id:<id>;request-id:<x-request-id>;ts:<ts>;>"."""
    import hashlib
    import hmac

    parts = dict(p.split("=", 1) for p in request.headers.get("x-signature", "").split(",") if "=" in p)
    ts, v1 = parts.get("ts", "").strip(), parts.get("v1", "").strip()
    if not ts or not v1:
        return False
    manifest = f"id:{data_id.lower()};request-id:{request.headers.get('x-request-id', '')};ts:{ts};"
    expected = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)


def _fetch_mp_payment(access_token: str, payment_id: str) -> dict:
    import mercadopago
    return mercadopago.SDK(access_token).payment().get(payment_id).get("response", {}) or {}


async def process_mp_payment(payment_id: str) -> Optional[str]:
    """Register an approved MercadoPago payment once, for the amount actually paid,
    and reconnect the client when nothing is overdue anymore. Returns what happened."""
    import asyncio

    from app.services.billing import reactivate_if_settled, today_ar

    async with AsyncSessionLocal() as db:
        try:
            from app.services.config_secrets import config_value
            token = await config_value(db, "mp_access_token")
            if not token:
                return "sin token"
            data = await asyncio.to_thread(_fetch_mp_payment, token, payment_id)
            if data.get("status") != "approved":
                return f"estado {data.get('status')}"
            ref = str(data.get("external_reference") or "")
            if not ref.isdigit():
                return "sin referencia"

            # Lock the invoice: two notifications of the same payment can arrive together
            invoice = (await db.execute(
                select(Invoice).where(Invoice.id == int(ref)).with_for_update()
            )).scalar_one_or_none()
            if not invoice:
                return "factura inexistente"
            duplicate = (await db.execute(
                select(Payment.id).where(Payment.reference == str(payment_id), Payment.method == PaymentMethod.mercadopago)
            )).first()
            if duplicate:
                await db.rollback()
                return "ya registrado"

            amount = float(data.get("transaction_amount") or 0)
            if amount <= 0:
                await db.rollback()
                return "monto inválido"
            paid_before = float((await db.execute(
                select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.invoice_id == invoice.id)
            )).scalar() or 0)
            db.add(Payment(
                invoice_id=invoice.id, amount=amount, payment_date=today_ar(),
                method=PaymentMethod.mercadopago, reference=str(payment_id),
            ))
            if paid_before + amount + 0.005 >= float(invoice.amount) and invoice.status != InvoiceStatus.paid:
                invoice.status = InvoiceStatus.paid
                invoice.paid_date = today_ar()
                invoice.mp_payment_id = str(payment_id)
            await db.commit()
            logger.info("MercadoPago payment %s: $%s on invoice %s", payment_id, amount, invoice.id)

            if invoice.status == InvoiceStatus.paid:
                await reactivate_if_settled(db, invoice.client_id)
            return "registrado"
        except Exception as exc:
            await db.rollback()
            logger.exception("Error processing MP payment %s: %s", payment_id, exc)
            return "error"
