import enum
from datetime import date
from typing import Optional

from sqlalchemy import Date, Enum as SAEnum, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ExpenseCategory(str, enum.Enum):
    hosting = "hosting"
    equipment = "equipment"
    energy = "energy"
    labor = "labor"
    internet = "internet"
    transport = "transport"
    software = "software"
    maintenance = "maintenance"
    other = "other"


class Expense(Base, TimestampMixin):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    description: Mapped[str] = mapped_column(String(255))
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    category: Mapped[ExpenseCategory] = mapped_column(SAEnum(ExpenseCategory), default=ExpenseCategory.other)
    expense_date: Mapped[date] = mapped_column(Date, index=True)
    vendor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    invoice_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
