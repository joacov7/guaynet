"""
Cuenta corriente del cliente.

Rules (every way money comes in goes through here: panel, ficha, MercadoPago):
  - A collection ("cobro") pays the chosen invoice first (if any), then the client's
    other unpaid invoices from the oldest due date; what is left becomes saldo a
    favor (a payment row without invoice).
  - Saldo a favor is applied to invoices as they are created (and when an invoice is
    cancelled, what was paid on it goes back to saldo a favor).
  - Voiding a cobro voids all its rows; the invoices it paid become unpaid again
    (overdue if past due). Voiding never cuts the service by itself: the automatic
    cut does it with its usual rules (días de gracia).
  - Balance = what is owed on pending/overdue invoices − saldo a favor.
    Positive: debt. Negative: the client has money in favor.
Callers commit; nothing here commits except where stated.
"""
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import Invoice, InvoiceStatus, Payment, PaymentMethod

UNPAID = (InvoiceStatus.pending, InvoiceStatus.overdue)
CENT = 0.005


def _r(x: float) -> float:
    return round(float(x) + 0.0, 2)


def _today() -> date:
    from app.services.billing import today_ar
    return today_ar()


async def paid_on(db: AsyncSession, invoice_ids: Iterable[int]) -> dict[int, float]:
    """Valid (not voided) money on each invoice."""
    ids = list(invoice_ids)
    if not ids:
        return {}
    rows = (await db.execute(
        select(Payment.invoice_id, func.coalesce(func.sum(Payment.amount), 0))
        .where(Payment.invoice_id.in_(ids), Payment.voided_at.is_(None))
        .group_by(Payment.invoice_id)
    )).all()
    out = {i: 0.0 for i in ids}
    out.update({inv_id: float(total) for inv_id, total in rows})
    return out


async def credit_of(db: AsyncSession, client_id: int) -> float:
    """Saldo a favor: valid payments not applied to any invoice."""
    return float((await db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .where(Payment.client_id == client_id, Payment.invoice_id.is_(None), Payment.voided_at.is_(None))
    )).scalar() or 0)


async def unpaid_invoices(db: AsyncSession, client_id: int, *, lock: bool = False) -> list[Invoice]:
    q = (select(Invoice).where(Invoice.client_id == client_id, Invoice.status.in_(UNPAID))
         .order_by(Invoice.due_date, Invoice.id))
    if lock:
        q = q.with_for_update()
    return list((await db.execute(q)).scalars().all())


@dataclass
class Balance:
    debt: float      # owed on pending/overdue invoices
    credit: float    # saldo a favor
    unpaid_count: int
    overdue_count: int

    @property
    def balance(self) -> float:
        return _r(self.debt - self.credit)


async def client_balance(db: AsyncSession, client_id: int) -> Balance:
    unpaid = await unpaid_invoices(db, client_id)
    paid = await paid_on(db, [i.id for i in unpaid])
    debt = sum(max(0.0, float(i.amount) - paid[i.id]) for i in unpaid)
    return Balance(
        debt=_r(debt),
        credit=_r(await credit_of(db, client_id)),
        unpaid_count=len(unpaid),
        overdue_count=sum(1 for i in unpaid if i.status == InvoiceStatus.overdue),
    )


async def refresh_invoice_status(db: AsyncSession, invoice: Invoice, *, today: Optional[date] = None) -> None:
    """Paid when its valid payments cover it; otherwise pending/overdue by due date.
    Drafts and cancelled invoices are left alone."""
    if invoice.status in (InvoiceStatus.draft, InvoiceStatus.cancelled):
        return
    paid = (await paid_on(db, [invoice.id]))[invoice.id]
    if paid + CENT >= float(invoice.amount):
        if invoice.status != InvoiceStatus.paid:
            last = (await db.execute(
                select(func.max(Payment.payment_date))
                .where(Payment.invoice_id == invoice.id, Payment.voided_at.is_(None))
            )).scalar()
            invoice.status = InvoiceStatus.paid
            invoice.paid_date = last or (today or _today())
    elif invoice.status == InvoiceStatus.paid or invoice.status in UNPAID:
        invoice.status = InvoiceStatus.overdue if invoice.due_date < (today or _today()) else InvoiceStatus.pending
        invoice.paid_date = None


async def register_payment(
    db: AsyncSession,
    *,
    client_id: int,
    amount: float,
    payment_date: date,
    method: PaymentMethod,
    reference: Optional[str] = None,
    notes: Optional[str] = None,
    invoice_id: Optional[int] = None,
    received_by_id: Optional[int] = None,
    received_by_name: Optional[str] = None,
) -> list[Payment]:
    """Record one cobro and spread it (see module doc). Returns the rows created,
    the one for `invoice_id` first. Flushes, does not commit."""
    amount = _r(amount)
    if amount <= 0:
        raise ValueError("El monto tiene que ser mayor a cero")
    unpaid = await unpaid_invoices(db, client_id, lock=True)
    if invoice_id is not None:
        target = next((i for i in unpaid if i.id == invoice_id), None)
        if target:
            unpaid = [target] + [i for i in unpaid if i.id != invoice_id]
    paid = await paid_on(db, [i.id for i in unpaid])

    group = str(uuid.uuid4())
    common = dict(client_id=client_id, payment_date=payment_date, method=method, reference=reference,
                  notes=notes, group_id=group, received_by_id=received_by_id, received_by_name=received_by_name)
    rows: list[Payment] = []
    left = amount
    for inv in unpaid:
        if left <= CENT:
            break
        due = _r(float(inv.amount) - paid[inv.id])
        if due <= CENT:
            continue
        part = min(left, due)
        rows.append(Payment(invoice_id=inv.id, amount=_r(part), **common))
        left = _r(left - part)
    if left > CENT:
        rows.append(Payment(invoice_id=None, amount=left, **common))
    db.add_all(rows)
    await db.flush()
    for inv in unpaid:
        if any(r.invoice_id == inv.id for r in rows):
            await refresh_invoice_status(db, inv)
    if invoice_id is not None:
        rows.sort(key=lambda r: r.invoice_id != invoice_id)
    return rows


async def apply_credit(db: AsyncSession, client_id: int) -> float:
    """Use saldo a favor on the client's unpaid invoices (oldest first). A credit row
    larger than what an invoice needs is split; both parts keep the cobro's group,
    date, method and collector. Returns the amount applied. Flushes, does not commit."""
    credits = list((await db.execute(
        select(Payment).where(Payment.client_id == client_id, Payment.invoice_id.is_(None), Payment.voided_at.is_(None))
        .order_by(Payment.payment_date, Payment.id).with_for_update()
    )).scalars().all())
    if not credits:
        return 0.0
    unpaid = await unpaid_invoices(db, client_id, lock=True)
    paid = await paid_on(db, [i.id for i in unpaid])
    applied = 0.0
    for inv in unpaid:
        due = _r(float(inv.amount) - paid[inv.id])
        while due > CENT and credits:
            c = credits[0]
            amt = float(c.amount)
            if amt <= due + CENT:
                c.invoice_id = inv.id
                credits.pop(0)
                used = amt
            else:
                db.add(Payment(
                    client_id=c.client_id, invoice_id=inv.id, amount=_r(due), payment_date=c.payment_date,
                    method=c.method, reference=c.reference, notes=c.notes, group_id=c.group_id,
                    received_by_id=c.received_by_id, received_by_name=c.received_by_name,
                ))
                c.amount = _r(amt - due)
                used = due
            due = _r(due - used)
            applied = _r(applied + used)
        await db.flush()
        if applied:
            await refresh_invoice_status(db, inv)
        if not credits:
            break
    await db.flush()
    return applied


async def apply_credits_for(db: AsyncSession, client_ids: Iterable[int]) -> None:
    """apply_credit for the clients of a batch that have saldo a favor (e.g. after the
    monthly invoices are created)."""
    ids = list(client_ids)
    if not ids:
        return
    with_credit = (await db.execute(
        select(Payment.client_id).where(Payment.client_id.in_(ids), Payment.invoice_id.is_(None),
                                        Payment.voided_at.is_(None)).distinct()
    )).scalars().all()
    for cid in with_credit:
        await apply_credit(db, cid)


async def release_to_credit(db: AsyncSession, invoice: Invoice) -> float:
    """An invoice that is cancelled gives its valid payments back as saldo a favor."""
    rows = (await db.execute(
        select(Payment).where(Payment.invoice_id == invoice.id, Payment.voided_at.is_(None))
    )).scalars().all()
    for p in rows:
        p.invoice_id = None
    await db.flush()
    return _r(sum(float(p.amount) for p in rows))


async def void_cobro(db: AsyncSession, payment: Payment, *, reason: str, by_name: str) -> list[Payment]:
    """Void every row of the cobro `payment` belongs to and recompute the invoices it
    paid. Flushes, does not commit."""
    q = select(Payment).where(Payment.voided_at.is_(None))
    q = q.where(Payment.group_id == payment.group_id) if payment.group_id else q.where(Payment.id == payment.id)
    rows = list((await db.execute(q.with_for_update())).scalars().all())
    now = datetime.now(timezone.utc)
    for p in rows:
        p.voided_at, p.voided_by_name, p.void_reason = now, by_name, reason
    await db.flush()
    for inv_id in {p.invoice_id for p in rows if p.invoice_id}:
        inv = await db.get(Invoice, inv_id)
        if inv:
            await refresh_invoice_status(db, inv)
    await db.flush()
    return rows


async def statement(db: AsyncSession, client_id: int) -> dict:
    """Movements of the account, oldest first, with running balance.
    Debits: invoices (not drafts or cancelled). Credits: cobros (one line per cobro,
    with the invoices it paid). Voided cobros are listed but do not move the balance."""
    invoices = (await db.execute(
        select(Invoice).where(Invoice.client_id == client_id,
                              Invoice.status.notin_([InvoiceStatus.draft, InvoiceStatus.cancelled]))
    )).scalars().all()
    payments = (await db.execute(
        select(Payment).where(Payment.client_id == client_id).order_by(Payment.id)
    )).scalars().all()
    periods = {i.id: i.period for i in invoices}

    moves = [{
        "kind": "invoice", "date": i.issue_date.isoformat(), "sort": (i.issue_date, 0, i.id),
        "concept": f"Factura {i.period}", "invoice_id": i.id, "status": i.status.value,
        "due_date": i.due_date.isoformat(), "debit": float(i.amount), "credit": 0.0,
    } for i in invoices]

    # Records from before the cuenta corriente: invoices marked paid by hand without a
    # payment, or paid in excess. Shown as adjustments so the running balance matches.
    paid = await paid_on(db, [i.id for i in invoices])
    for i in invoices:
        gap = _r(float(i.amount) - paid[i.id])
        when = i.paid_date or i.issue_date
        if i.status == InvoiceStatus.paid and gap > CENT:
            moves.append({"kind": "adjust", "date": when.isoformat(), "sort": (when, 2, i.id), "invoice_id": i.id,
                          "concept": f"Factura {i.period} marcada como pagada sin pago registrado",
                          "debit": 0.0, "credit": gap})
        elif gap < -CENT:
            moves.append({"kind": "adjust", "date": when.isoformat(), "sort": (when, 2, i.id), "invoice_id": i.id,
                          "concept": f"Pagado de más en la factura {i.period} (no quedó como saldo a favor)",
                          "debit": -gap, "credit": 0.0})
    cancelled = (await db.execute(
        select(Invoice).where(Invoice.client_id == client_id, Invoice.status == InvoiceStatus.cancelled)
    )).scalars().all()
    on_cancelled = await paid_on(db, [i.id for i in cancelled])
    for i in cancelled:
        if on_cancelled[i.id] > CENT:
            moves.append({"kind": "adjust", "date": i.issue_date.isoformat(), "sort": (i.issue_date, 2, i.id),
                          "invoice_id": i.id, "concept": f"Pagos sobre la factura anulada {i.period} (no cuentan)",
                          "debit": on_cancelled[i.id], "credit": 0.0})

    groups: dict[str, list[Payment]] = {}
    for p in payments:
        groups.setdefault(p.group_id or f"p{p.id}", []).append(p)
    for gid, rows in groups.items():
        first = rows[0]
        total = _r(sum(float(r.amount) for r in rows))
        applied = [periods.get(r.invoice_id, "") for r in rows if r.invoice_id]
        in_favor = _r(sum(float(r.amount) for r in rows if not r.invoice_id))
        parts = ([f"aplicado a {', '.join(sorted(set(a for a in applied if a)))}"] if applied else []) \
            + ([f"saldo a favor ${in_favor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")] if in_favor else [])
        voided = first.voided_at is not None
        moves.append({
            "kind": "payment", "date": first.payment_date.isoformat(), "sort": (first.payment_date, 1, first.id),
            "concept": f"Pago ({first.method.value})" + (f" — {'; '.join(parts)}" if parts else ""),
            "group_id": gid, "payment_id": first.id, "method": first.method.value,
            "reference": first.reference, "received_by": first.received_by_name,
            "debit": 0.0, "credit": total, "voided": voided,
            "voided_by": first.voided_by_name, "void_reason": first.void_reason,
            "voided_at": first.voided_at.isoformat() if first.voided_at else None,
        })

    moves.sort(key=lambda m: m.pop("sort"))
    running = 0.0
    for m in moves:
        if not m.get("voided"):
            running = _r(running + m["debit"] - m["credit"])
        m["balance"] = running
    b = await client_balance(db, client_id)
    return {"balance": b.balance, "debt": b.debt, "credit": b.credit, "movements": moves}



def _money(x: float) -> str:
    return f"${x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


METHOD_LABEL = {"cash": "efectivo", "transfer": "transferencia", "mercadopago": "MercadoPago", "other": "otro"}


async def audit_cobro(db: AsyncSession, rows: list[Payment], *, user_id: Optional[int], username: str,
                      voided: bool = False, reason: str = "") -> None:
    """One line in Auditoría (and in the client's history) per cobro or annulment."""
    from app.models.audit import AuditLog
    from app.models.client import Client

    if not rows:
        return
    first = rows[0]
    client = await db.get(Client, first.client_id)
    total = sum(float(r.amount) for r in rows)
    periods = {}
    for r in rows:
        if r.invoice_id:
            inv = await db.get(Invoice, r.invoice_id)
            if inv:
                periods[inv.period] = periods.get(inv.period, 0) + float(r.amount)
    favor = sum(float(r.amount) for r in rows if not r.invoice_id)
    detail = f"{_money(total)} en {METHOD_LABEL.get(first.method.value, first.method.value)}"
    if periods:
        detail += " — " + ", ".join(f"{p}: {_money(a)}" for p, a in sorted(periods.items()))
    if favor:
        detail += f" — a favor: {_money(favor)}"
    if voided:
        detail = f"Anulado {detail}. Motivo: {reason}"
    elif first.received_by_name:
        detail += f" — cobró {first.received_by_name}"
    db.add(AuditLog(
        user_id=user_id, username=(username or "sistema")[:50], action="payment_void" if voided else "payment",
        entity_type="client", entity_id=first.client_id, entity_name=client.full_name if client else "",
        details=detail,
    ))
