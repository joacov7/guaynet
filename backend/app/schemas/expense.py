from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.expense import ExpenseCategory


class ExpenseCreate(BaseModel):
    description: str
    amount: float
    category: ExpenseCategory = ExpenseCategory.other
    expense_date: date
    vendor: Optional[str] = None
    invoice_number: Optional[str] = None
    notes: Optional[str] = None


class ExpenseUpdate(BaseModel):
    description: Optional[str] = None
    amount: Optional[float] = None
    category: Optional[ExpenseCategory] = None
    expense_date: Optional[date] = None
    vendor: Optional[str] = None
    invoice_number: Optional[str] = None
    notes: Optional[str] = None


class ExpenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    description: str
    amount: float
    category: ExpenseCategory
    expense_date: date
    vendor: Optional[str]
    invoice_number: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
