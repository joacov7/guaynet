from datetime import date, datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict

from app.models.invoice import InvoiceStatus, PaymentMethod


class PaymentCreate(BaseModel):
    amount: float
    payment_date: date
    method: PaymentMethod
    reference: Optional[str] = None
    notes: Optional[str] = None


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount: float
    payment_date: date
    method: PaymentMethod
    reference: Optional[str]
    notes: Optional[str]
    created_at: datetime


class InvoiceItemCreate(BaseModel):
    description: str
    quantity: float = 1.0
    unit_price: float

    @property
    def subtotal(self) -> float:
        return round(self.quantity * self.unit_price, 2)


class InvoiceItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    description: str
    quantity: float
    unit_price: float
    subtotal: float


class InvoiceCreate(BaseModel):
    client_id: int
    period: str
    amount: Optional[float] = None   # auto-calculated from items if provided
    issue_date: date
    due_date: date
    notes: Optional[str] = None
    items: List["InvoiceItemCreate"] = []


class InvoiceUpdate(BaseModel):
    status: Optional[InvoiceStatus] = None
    paid_date: Optional[date] = None
    notes: Optional[str] = None
    afip_cae: Optional[str] = None
    afip_cae_expiry: Optional[date] = None


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    period: str
    amount: float
    issue_date: date
    due_date: date
    paid_date: Optional[date]
    status: InvoiceStatus
    notes: Optional[str]
    afip_cae: Optional[str]
    invoice_number: Optional[int]
    payments: List[PaymentResponse] = []
    items: List[InvoiceItemResponse] = []
    created_at: datetime
