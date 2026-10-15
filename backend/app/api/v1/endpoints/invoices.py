import calendar
import csv
import io
import logging
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user, get_db
from app.models.client import Client, ClientStatus
from app.models.config import SystemConfig
from app.models.invoice import Invoice, InvoiceItem, InvoiceStatus, Payment
from app.schemas.invoice import InvoiceCreate, InvoiceResponse, InvoiceUpdate, PaymentCreate, PaymentResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=List[InvoiceResponse])
async def list_invoices(
    status: Optional[InvoiceStatus] = None,
    period: Optional[str] = None,
    client_id: Optional[int] = None,
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    q = select(Invoice).options(selectinload(Invoice.payments), selectinload(Invoice.items)).order_by(Invoice.due_date.desc())
    if status:
        q = q.where(Invoice.status == status)
    if period:
        q = q.where(Invoice.period == period)
    if client_id:
        q = q.where(Invoice.client_id == client_id)
    result = await db.execute(q.offset(skip).limit(limit))
    return result.scalars().all()


@router.post("/", response_model=InvoiceResponse, status_code=201)
async def create_invoice(
    body: InvoiceCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    items_data = body.items or []
    if items_data and body.amount is None:
        total = sum(round(i.quantity * i.unit_price, 2) for i in items_data)
    else:
        total = body.amount or 0.0

    invoice = Invoice(
        client_id=body.client_id,
        period=body.period,
        amount=total,
        issue_date=body.issue_date,
        due_date=body.due_date,
        notes=body.notes,
    )
    db.add(invoice)
    await db.flush()

    for item in items_data:
        subtotal = round(item.quantity * item.unit_price, 2)
        db.add(InvoiceItem(
            invoice_id=invoice.id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            subtotal=subtotal,
        ))

    await db.commit()
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.payments), selectinload(Invoice.items)).where(Invoice.id == invoice.id)
    )
    return result.scalar_one()


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(invoice_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.payments), selectinload(Invoice.items)).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    return invoice


@router.put("/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: int,
    body: InvoiceUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    invoice = await db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(invoice, field, value)

    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)
    return invoice


@router.post("/{invoice_id}/payments", response_model=PaymentResponse, status_code=201)
async def add_payment(
    invoice_id: int,
    body: PaymentCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    invoice = await db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    payment = Payment(invoice_id=invoice_id, **body.model_dump())
    db.add(payment)

    # Mark invoice as paid if amount covers total
    total_paid = sum(p.amount for p in invoice.payments) + body.amount
    if total_paid >= float(invoice.amount):
        invoice.status = InvoiceStatus.paid
        invoice.paid_date = body.payment_date
        db.add(invoice)

    await db.commit()
    await db.refresh(payment)
    return payment


@router.post("/mark-overdue", status_code=200)
async def mark_overdue_invoices(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    """Mark all pending invoices past due_date as overdue."""
    today = date.today()
    result = await db.execute(
        select(Invoice).where(Invoice.status == InvoiceStatus.pending, Invoice.due_date < today)
    )
    invoices = result.scalars().all()
    for inv in invoices:
        inv.status = InvoiceStatus.overdue
        db.add(inv)
    await db.commit()
    return {"updated": len(invoices)}


@router.post("/trigger-suspend", status_code=200)
async def trigger_auto_suspend(_=Depends(get_current_user)):
    """Manually trigger the auto-suspend billing task."""
    from app.tasks.billing import mark_overdue_and_suspend
    task = mark_overdue_and_suspend.delay()
    return {"task_id": task.id, "status": "queued"}


@router.post("/trigger-generate", status_code=200)
async def trigger_generate_invoices(_=Depends(get_current_user)):
    """Manually trigger monthly invoice generation."""
    from app.tasks.billing import generate_monthly_invoices
    task = generate_monthly_invoices.delay()
    return {"task_id": task.id, "status": "queued"}


def _parse_period(period: str):
    try:
        year, month = int(period[:4]), int(period[5:7])
        if not (1 <= month <= 12):
            raise ValueError
        return year, month
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="El período debe tener formato YYYY-MM")


@router.get("/generate-monthly/preview")
async def preview_monthly_generation(
    period: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    if not period:
        period = date.today().strftime("%Y-%m")
    year, month = _parse_period(period)

    clients_result = await db.execute(
        select(Client).options(selectinload(Client.plan)).where(Client.status == ClientStatus.active)
    )
    clients = clients_result.scalars().all()

    existing_result = await db.execute(
        select(Invoice.client_id).where(Invoice.period == period)
    )
    existing_ids = set(existing_result.scalars().all())

    last_day = calendar.monthrange(year, month)[1]
    today = date.today()
    items = []
    for c in clients:
        if c.id in existing_ids or not c.plan:
            continue
        billing_day = min(c.billing_day or 1, last_day)
        items.append({
            "client_id": c.id,
            "client_name": c.full_name,
            "plan_name": c.plan.name,
            "amount": float(c.plan.price),
            "due_date": date(year, month, billing_day).isoformat(),
            "issue_date": today.isoformat(),
        })

    return {
        "period": period,
        "count": len(items),
        "skipped": len(clients) - len(items),
        "items": items,
    }


class GenerateMonthlyRequest(BaseModel):
    period: str


@router.post("/generate-monthly")
async def generate_monthly_invoices_direct(
    body: GenerateMonthlyRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    year, month = _parse_period(body.period)

    clients_result = await db.execute(
        select(Client).options(selectinload(Client.plan)).where(Client.status == ClientStatus.active)
    )
    clients = clients_result.scalars().all()

    existing_result = await db.execute(
        select(Invoice.client_id).where(Invoice.period == body.period)
    )
    existing_ids = set(existing_result.scalars().all())

    last_day = calendar.monthrange(year, month)[1]
    today = date.today()
    created = 0
    skipped = 0

    for c in clients:
        if c.id in existing_ids or not c.plan:
            skipped += 1
            continue
        billing_day = min(c.billing_day or 1, last_day)
        db.add(Invoice(
            client_id=c.id,
            period=body.period,
            amount=float(c.plan.price),
            issue_date=today,
            due_date=date(year, month, billing_day),
            status=InvoiceStatus.pending,
        ))
        created += 1

    await db.commit()
    return {"period": body.period, "created": created, "skipped": skipped}


@router.get("/overdue-report")
async def overdue_report(
    format: str = Query(default="json", pattern="^(json|csv)$"),
    min_days_overdue: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Report of all overdue invoices with client info and days overdue."""
    today = date.today()

    result = await db.execute(
        select(
            Client.id.label("client_id"),
            Client.first_name,
            Client.last_name,
            Client.phone,
            Client.email,
            Client.address,
            Invoice.id.label("invoice_id"),
            Invoice.period,
            Invoice.amount,
            Invoice.due_date,
        )
        .join(Invoice, Invoice.client_id == Client.id)
        .where(Invoice.status == InvoiceStatus.overdue)
        .order_by(Invoice.due_date)
    )

    rows = result.all()
    data = []
    for row in rows:
        days = (today - row.due_date).days
        if days < min_days_overdue:
            continue
        data.append({
            "client_id": row.client_id,
            "client_name": f"{row.first_name} {row.last_name}",
            "phone": row.phone or "",
            "email": row.email or "",
            "address": row.address or "",
            "invoice_id": row.invoice_id,
            "period": row.period,
            "amount": float(row.amount),
            "due_date": row.due_date.isoformat(),
            "days_overdue": days,
        })

    if format == "csv":
        output = io.StringIO()
        fields = ["client_id", "client_name", "phone", "email", "address",
                  "invoice_id", "period", "amount", "due_date", "days_overdue"]
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(data)
        output.seek(0)
        filename = f"morosidad_{today}.csv"
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    total_amount = sum(r["amount"] for r in data)
    return {"total": len(data), "total_amount": total_amount, "items": data}


async def _build_invoice_pdf(invoice_id: int, db: AsyncSession) -> bytes:
    """Generate a PDF for the given invoice and return raw bytes."""
    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.items), selectinload(Invoice.client))
        .where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    # Load company info from SystemConfig
    async def cfg(key: str, default: str = "") -> str:
        r = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
        row = r.scalar_one_or_none()
        return row.value if row and row.value else default

    company_name = await cfg("company_name", "Guaynet")
    company_address = await cfg("company_address", "")
    company_cuit = await cfg("company_cuit", "")

    try:
        from fpdf import FPDF
    except ImportError:
        raise HTTPException(status_code=503, detail="PDF generation not available (fpdf2 not installed)")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)

    # Header
    pdf.cell(0, 10, company_name, ln=True)
    pdf.set_font("Helvetica", "", 10)
    if company_address:
        pdf.cell(0, 6, company_address, ln=True)
    if company_cuit:
        pdf.cell(0, 6, f"CUIT: {company_cuit}", ln=True)
    pdf.ln(4)

    # Invoice title
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, f"Factura #{invoice.id}", ln=True)
    pdf.set_font("Helvetica", "", 10)
    if invoice.period:
        pdf.cell(0, 6, f"Período: {invoice.period}", ln=True)
    pdf.cell(0, 6, f"Emisión: {invoice.issue_date}", ln=True)
    pdf.cell(0, 6, f"Vencimiento: {invoice.due_date}", ln=True)
    pdf.cell(0, 6, f"Estado: {invoice.status.value.upper()}", ln=True)
    pdf.ln(4)

    # Client info
    client = invoice.client
    if client:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, "Cliente", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, client.full_name, ln=True)
        if client.address:
            pdf.cell(0, 6, client.address, ln=True)
        if client.email:
            pdf.cell(0, 6, client.email, ln=True)
        pdf.ln(4)

    # Items table
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Detalle", ln=True)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(110, 7, "Descripción", border=1)
    pdf.cell(25, 7, "Cant.", border=1, align="C")
    pdf.cell(30, 7, "P. Unitario", border=1, align="R")
    pdf.cell(25, 7, "Subtotal", border=1, align="R", ln=True)

    pdf.set_font("Helvetica", "", 10)
    if invoice.items:
        for item in invoice.items:
            pdf.cell(110, 7, str(item.description)[:60], border=1)
            pdf.cell(25, 7, str(float(item.quantity)), border=1, align="C")
            pdf.cell(30, 7, f"${float(item.unit_price):.2f}", border=1, align="R")
            pdf.cell(25, 7, f"${float(item.subtotal):.2f}", border=1, align="R", ln=True)
    else:
        pdf.cell(110, 7, "Servicio de internet", border=1)
        pdf.cell(25, 7, "1", border=1, align="C")
        pdf.cell(30, 7, f"${float(invoice.amount):.2f}", border=1, align="R")
        pdf.cell(25, 7, f"${float(invoice.amount):.2f}", border=1, align="R", ln=True)

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"Total: ${float(invoice.amount):.2f}", ln=True, align="R")

    return pdf.output()


@router.get("/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    pdf_bytes = await _build_invoice_pdf(invoice_id, db)
    filename = f"factura_{invoice_id}.pdf"
    return Response(
        content=bytes(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
