from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.expense import Expense, ExpenseCategory
from app.schemas.expense import ExpenseCreate, ExpenseResponse, ExpenseUpdate

router = APIRouter()


@router.get("/", response_model=List[ExpenseResponse])
async def list_expenses(
    category: Optional[ExpenseCategory] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    skip: int = 0,
    limit: int = Query(default=200, le=1000),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    q = select(Expense).order_by(Expense.expense_date.desc())
    if category:
        q = q.where(Expense.category == category)
    if date_from:
        q = q.where(Expense.expense_date >= date_from)
    if date_to:
        q = q.where(Expense.expense_date <= date_to)
    result = await db.execute(q.offset(skip).limit(limit))
    return result.scalars().all()


@router.post("/", response_model=ExpenseResponse, status_code=201)
async def create_expense(
    body: ExpenseCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    expense = Expense(**body.model_dump())
    db.add(expense)
    await db.commit()
    await db.refresh(expense)
    return expense


@router.get("/summary")
async def expense_summary(
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Return total and per-category breakdown for a given period."""
    q = select(Expense.category, func.sum(Expense.amount).label("total")).group_by(Expense.category)
    if year:
        q = q.where(extract("year", Expense.expense_date) == year)
    if month:
        q = q.where(extract("month", Expense.expense_date) == month)
    result = await db.execute(q)
    rows = result.all()
    by_category = {row.category: float(row.total) for row in rows}
    grand_total = sum(by_category.values())
    return {"total": grand_total, "by_category": by_category}


@router.get("/monthly-totals")
async def monthly_totals(
    year: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Return monthly expense totals for charting (defaults to current year)."""
    import datetime as _dt
    y = year or _dt.date.today().year
    q = (
        select(
            extract("month", Expense.expense_date).label("month"),
            func.sum(Expense.amount).label("total"),
        )
        .where(extract("year", Expense.expense_date) == y)
        .group_by(extract("month", Expense.expense_date))
        .order_by(extract("month", Expense.expense_date))
    )
    result = await db.execute(q)
    rows = result.all()
    return {"year": y, "months": [{"month": int(r.month), "total": float(r.total)} for r in rows]}


@router.get("/{expense_id}", response_model=ExpenseResponse)
async def get_expense(
    expense_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    expense = await db.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    return expense


@router.put("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: int,
    body: ExpenseUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    expense = await db.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(expense, field, value)
    db.add(expense)
    await db.commit()
    await db.refresh(expense)
    return expense


@router.delete("/{expense_id}", status_code=204)
async def delete_expense(
    expense_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    expense = await db.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    await db.delete(expense)
    await db.commit()
