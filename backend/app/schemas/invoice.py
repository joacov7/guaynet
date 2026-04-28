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


class InvoiceCreate(BaseModel):
    client_id: int
    period: str
    amount: float
    issue_date: date
    due_date: date
    notes: Optional[str] = None


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
    created_at: datetime
