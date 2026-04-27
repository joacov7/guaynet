from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user, get_db
from app.models.invoice import Invoice, InvoiceStatus, Payment
from app.schemas.invoice import InvoiceCreate, InvoiceResponse, InvoiceUpdate, PaymentCreate, PaymentResponse

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
    q = select(Invoice).options(selectinload(Invoice.payments)).order_by(Invoice.due_date.desc())
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
    invoice = Invoice(**body.model_dump())
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)
    return invoice


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(invoice_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.payments)).where(Invoice.id == invoice_id)
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
