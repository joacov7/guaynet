import calendar
import csv
import io
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user, get_db
from app.models.client import Client, ClientStatus
from app.models.invoice import Invoice, InvoiceItem, InvoiceStatus, Payment
from app.schemas.invoice import InvoiceCreate, InvoiceResponse, InvoiceUpdate, PaymentCreate, PaymentResponse
from app.services.telegram import send_telegram as _send_telegram

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
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.payments)).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    payment = Payment(invoice_id=invoice_id, **body.model_dump())
    db.add(payment)

    # Mark invoice as paid if amount covers total
    total_paid = sum(p.amount for p in invoice.payments) + body.amount
    newly_paid = False
    if total_paid >= float(invoice.amount):
        invoice.status = InvoiceStatus.paid
        invoice.paid_date = body.payment_date
        db.add(invoice)
        newly_paid = True

    await db.commit()
    await db.refresh(payment)

    # Auto-reactivate suspended client when this payment makes the invoice fully paid
    if newly_paid and invoice.client_id:
        client = await db.get(Client, invoice.client_id)
        if client and client.status == ClientStatus.suspended:
            # Check whether any other overdue invoice remains
            other_overdue = await db.execute(
                select(Invoice.id).where(
                    Invoice.client_id == invoice.client_id,
                    Invoice.id != invoice_id,
                    Invoice.status == InvoiceStatus.overdue,
                )
            )
            if not other_overdue.scalar_one_or_none():
                client.status = ClientStatus.active
                db.add(client)
                await db.commit()

                # Re-enable MikroTik queue
                import asyncio
                from app.models.router import MikrotikRouter
                from app.services.mikrotik import build_service_from_router, MikrotikError
                rt = await db.get(MikrotikRouter, client.router_id)
                if rt:
                    def _enable(router=rt, qname=client.mikrotik_queue_name):
                        svc = build_service_from_router(router)
                        with svc:
                            q = svc.get_queue_by_name(qname)
                            if q:
                                svc.enable_queue(q["id"])
                    try:
                        await asyncio.to_thread(_enable)
                    except MikrotikError:
                        pass

                try:
                    await _send_telegram(
                        f"✅ Cliente reactivado automáticamente: {client.full_name} (pago factura #{invoice_id})"
                    )
                except Exception:
                    pass

    return payment


def _build_invoice_pdf(invoice: Invoice, client: Client) -> bytes:
    """Build a simple PDF receipt using reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    c.setFont("Helvetica-Bold", 18)
    c.drawString(20 * mm, h - 25 * mm, "Factura de servicio")

    c.setFont("Helvetica", 11)
    c.drawString(20 * mm, h - 35 * mm, f"N° {invoice.id}  |  Período: {invoice.period}")
    c.drawString(20 * mm, h - 42 * mm, f"Cliente: {client.full_name}")
    if client.dni:
        c.drawString(20 * mm, h - 49 * mm, f"DNI/CUIT: {client.dni}")
    if client.address:
        c.drawString(20 * mm, h - 56 * mm, f"Dirección: {client.address}")
    if client.phone:
        c.drawString(20 * mm, h - 63 * mm, f"Teléfono: {client.phone}")

    c.line(20 * mm, h - 68 * mm, w - 20 * mm, h - 68 * mm)

    y = h - 78 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(20 * mm, y, "Descripción")
    c.drawString(100 * mm, y, "Cant.")
    c.drawString(130 * mm, y, "P. Unit.")
    c.drawString(160 * mm, y, "Subtotal")
    y -= 7 * mm

    c.setFont("Helvetica", 10)
    if invoice.items:
        for item in invoice.items:
            c.drawString(20 * mm, y, item.description[:55])
            c.drawRightString(115 * mm, y, str(item.quantity))
            c.drawRightString(148 * mm, y, f"${item.unit_price:,.2f}")
            c.drawRightString(178 * mm, y, f"${item.subtotal:,.2f}")
            y -= 6 * mm
    else:
        c.drawString(20 * mm, y, f"Servicio de internet — {invoice.period}")
        c.drawRightString(178 * mm, y, f"${invoice.amount:,.2f}")
        y -= 6 * mm

    c.line(20 * mm, y, w - 20 * mm, y)
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(130 * mm, y, "Total:")
    c.drawRightString(178 * mm, y, f"${invoice.amount:,.2f}")

    y -= 15 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"Emisión: {invoice.issue_date}  |  Vencimiento: {invoice.due_date}  |  Estado: {invoice.status.value}")
    if invoice.paid_date:
        y -= 6 * mm
        c.drawString(20 * mm, y, f"Fecha de pago: {invoice.paid_date}")

    c.save()
    return buf.getvalue()


@router.get("/{invoice_id}/pdf")
async def invoice_pdf(invoice_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.items), selectinload(Invoice.payments)).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    client = await db.get(Client, invoice.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    pdf_bytes = _build_invoice_pdf(invoice, client)
    filename = f"factura_{invoice_id}_{invoice.period}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )


@router.post("/{invoice_id}/mp-link")
async def create_mp_link(invoice_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.items)).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    if invoice.status in (InvoiceStatus.paid, InvoiceStatus.cancelled):
        raise HTTPException(status_code=400, detail="La factura ya está pagada o cancelada")

    client = await db.get(Client, invoice.client_id)

    # Load MP access token from SystemConfig
    from app.models.config import SystemConfig
    cfg_result = await db.execute(select(SystemConfig).where(SystemConfig.key == "mp_access_token"))
    cfg = cfg_result.scalar_one_or_none()
    if not cfg or not cfg.value:
        raise HTTPException(status_code=400, detail="No se configuró el access token de MercadoPago (Configuración → MercadoPago)")

    import mercadopago
    sdk = mercadopago.SDK(cfg.value)

    title = f"Factura #{invoice_id} — {invoice.period}"
    if invoice.items:
        items = [{"title": it.description, "quantity": int(it.quantity), "unit_price": float(it.unit_price)} for it in invoice.items]
    else:
        items = [{"title": title, "quantity": 1, "unit_price": float(invoice.amount)}]

    preference_data = {
        "items": items,
        "external_reference": str(invoice_id),
        "statement_descriptor": "Guaynet WISP",
    }
    if client and client.email:
        preference_data["payer"] = {"email": client.email}

    response = sdk.preference().create(preference_data)
    if response["status"] not in (200, 201):
        raise HTTPException(status_code=502, detail=f"Error MercadoPago: {response.get('response', {})}")

    init_point = response["response"]["init_point"]
    return {"init_point": init_point, "preference_id": response["response"]["id"]}


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
