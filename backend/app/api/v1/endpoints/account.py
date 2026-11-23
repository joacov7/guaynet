"""
Cuenta corriente (Facturación): statement of a client, collecting money, voiding a
collection, and the list of collections ("Cobros", the daily cash check).
Rules live in app/services/account.py. Mounted under section "billing".
"""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_action
from app.models.client import Client
from app.models.invoice import Invoice, Payment, PaymentMethod
from app.services import account
from app.services.billing import reactivate_if_settled, today_ar

router = APIRouter()


async def _client(db: AsyncSession, client_id: int) -> Client:
    client = await db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return client


@router.get("/clients/{client_id:int}/statement")
async def client_statement(client_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    await _client(db, client_id)
    return await account.statement(db, client_id)


class CobroIn(BaseModel):
    amount: float = Field(gt=0)
    payment_date: Optional[date] = None
    method: PaymentMethod
    reference: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = Field(default=None, max_length=2000)
    # Pay this invoice first; without it, the oldest unpaid invoices first
    invoice_id: Optional[int] = None


@router.post("/clients/{client_id:int}/payments", status_code=201, dependencies=[Depends(require_action("act_payments"))])
async def collect(client_id: int, body: CobroIn, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    """A cobro: pays the client's unpaid invoices (the chosen one first, then the oldest)
    and leaves the rest as saldo a favor."""
    await _client(db, client_id)
    when = body.payment_date or today_ar()
    if when > today_ar() + timedelta(days=1):
        raise HTTPException(status_code=422, detail="La fecha del pago no puede ser futura")
    if body.invoice_id is not None:
        inv = await db.get(Invoice, body.invoice_id)
        if not inv or inv.client_id != client_id:
            raise HTTPException(status_code=404, detail="La factura no es de este cliente")
    rows = await account.register_payment(
        db, client_id=client_id, invoice_id=body.invoice_id, amount=body.amount, payment_date=when,
        method=body.method, reference=body.reference or None, notes=body.notes or None,
        received_by_id=current_user.id, received_by_name=current_user.full_name or current_user.username,
    )
    await account.audit_cobro(db, rows, user_id=current_user.id, username=current_user.username)
    await db.commit()

    applied = []
    for r in rows:
        if r.invoice_id:
            inv = await db.get(Invoice, r.invoice_id)
            applied.append({"invoice_id": r.invoice_id, "period": inv.period if inv else "",
                            "amount": float(r.amount), "invoice_status": inv.status.value if inv else None})
    reactivation = await reactivate_if_settled(db, client_id)
    bal = await account.client_balance(db, client_id)
    return {
        "group_id": rows[0].group_id,
        "total": float(body.amount),
        "applied": applied,
        "to_credit": round(sum(float(r.amount) for r in rows if not r.invoice_id), 2),
        "balance": bal.balance,
        "credit": bal.credit,
        "reactivated": reactivation is not None,
        "router_message": None if reactivation is None else reactivation.message,
        "router_ok": None if reactivation is None else reactivation.ok,
    }


class VoidIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


@router.post("/payments/{payment_id:int}/void", dependencies=[Depends(require_action("act_payment_void"))])
async def void(payment_id: int, body: VoidIn, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    """Void the whole cobro this payment belongs to. The service is not cut here: the
    automatic cut decides with its usual rules."""
    payment = await db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    if payment.voided_at:
        raise HTTPException(status_code=409, detail="Ese pago ya está anulado")
    name = current_user.full_name or current_user.username
    rows = await account.void_cobro(db, payment, reason=body.reason.strip(), by_name=name)
    await account.audit_cobro(db, rows, user_id=current_user.id, username=current_user.username,
                              voided=True, reason=body.reason.strip())
    await db.commit()
    bal = await account.client_balance(db, payment.client_id)
    return {"voided": len(rows), "total": round(sum(float(r.amount) for r in rows), 2),
            "balance": bal.balance, "credit": bal.credit}


@router.get("/payments")
async def cobros(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    method: Optional[PaymentMethod] = None,
    received_by: Optional[str] = Query(default=None, max_length=100),
    client_id: Optional[int] = None,
    include_voided: bool = True,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Cobros in a date range (default: today), one line per cobro, with totals by
    method and by who collected (voided ones listed apart, not in the totals)."""
    date_to = date_to or today_ar()
    date_from = date_from or date_to
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="La fecha 'desde' es posterior a 'hasta'")
    if (date_to - date_from).days > 370:
        raise HTTPException(status_code=422, detail="Elegí un rango de hasta un año")
    q = select(Payment).where(Payment.payment_date >= date_from, Payment.payment_date <= date_to)
    if method:
        q = q.where(Payment.method == method)
    if client_id:
        q = q.where(Payment.client_id == client_id)
    if received_by:
        q = q.where(Payment.received_by_name == received_by)
    if not include_voided:
        q = q.where(Payment.voided_at.is_(None))
    rows = (await db.execute(q.order_by(Payment.payment_date.desc(), Payment.id.desc()).limit(5000))).scalars().all()

    client_ids = {r.client_id for r in rows}
    invoice_ids = {r.invoice_id for r in rows if r.invoice_id}
    names = {c.id: c.full_name for c in (await db.execute(select(Client).where(Client.id.in_(client_ids)))).scalars()} if client_ids else {}
    periods = {i.id: i.period for i in (await db.execute(select(Invoice).where(Invoice.id.in_(invoice_ids)))).scalars()} if invoice_ids else {}

    groups: dict[str, dict] = {}
    for r in rows:
        key = r.group_id or f"p{r.id}"
        g = groups.get(key)
        if not g:
            g = groups[key] = {
                "group_id": key, "payment_id": r.id, "date": r.payment_date.isoformat(),
                "client_id": r.client_id, "client_name": names.get(r.client_id, ""),
                "method": r.method.value, "reference": r.reference, "notes": r.notes,
                "received_by": r.received_by_name, "total": 0.0, "invoices": [], "to_credit": 0.0,
                "voided": r.voided_at is not None, "voided_by": r.voided_by_name, "void_reason": r.void_reason,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
        g["total"] = round(g["total"] + float(r.amount), 2)
        if r.invoice_id:
            g["invoices"].append(periods.get(r.invoice_id, ""))
        else:
            g["to_credit"] = round(g["to_credit"] + float(r.amount), 2)

    items = list(groups.values())
    valid = [g for g in items if not g["voided"]]
    by_method: dict[str, float] = {}
    by_collector: dict[str, float] = {}
    for g in valid:
        by_method[g["method"]] = round(by_method.get(g["method"], 0) + g["total"], 2)
        who = g["received_by"] or "Sin dato"
        by_collector[who] = round(by_collector.get(who, 0) + g["total"], 2)
    collectors = sorted({g["received_by"] for g in items if g["received_by"]})
    return {
        "date_from": date_from.isoformat(), "date_to": date_to.isoformat(),
        "total": round(sum(g["total"] for g in valid), 2), "count": len(valid),
        "voided_count": len(items) - len(valid),
        "by_method": by_method, "by_collector": by_collector, "collectors": collectors,
        "items": items,
    }
