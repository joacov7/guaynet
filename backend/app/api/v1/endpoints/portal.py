"""Client self-service portal — separate auth from staff users."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.core.deps import get_db
from app.core.security import create_access_token, get_password_hash, verify_password, decode_token
from app.models.client import Client, ClientStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.ticket import Ticket, TicketCategory, TicketComment, TicketPriority, TicketStatus

router = APIRouter()

portal_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/portal/login", auto_error=False)

PREFIX = "portal:"


async def get_current_portal_client(
    token: str = Depends(portal_oauth2),
    db: AsyncSession = Depends(get_db),
) -> Client:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise exc
    sub = decode_token(token)
    if not sub or not sub.startswith(PREFIX):
        raise exc
    client_id = int(sub[len(PREFIX):])
    client = await db.get(Client, client_id)
    if not client or not client.portal_enabled:
        raise exc
    return client


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class PortalLoginRequest(BaseModel):
    email: str
    password: str


class PortalClientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    status: ClientStatus
    plan_name: Optional[str] = None
    ip_address: str


@router.post("/login")
async def portal_login(body: PortalLoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Client).options(selectinload(Client.plan)).where(Client.email == body.email)
    )
    client = result.scalar_one_or_none()
    if (
        not client
        or not client.portal_enabled
        or not client.portal_password_hash
        or not verify_password(body.password, client.portal_password_hash)
    ):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    token = create_access_token(f"{PREFIX}{client.id}")
    return {
        "access_token": token,
        "token_type": "bearer",
        "client": PortalClientResponse(
            id=client.id,
            full_name=client.full_name,
            email=client.email,
            phone=client.phone,
            address=client.address,
            status=client.status,
            plan_name=client.plan.name if client.plan else None,
            ip_address=client.ip_address,
        ),
    }


@router.get("/me", response_model=PortalClientResponse)
async def portal_me(
    client: Client = Depends(get_current_portal_client),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Client).options(selectinload(Client.plan)).where(Client.id == client.id)
    )
    c = result.scalar_one()
    return PortalClientResponse(
        id=c.id,
        full_name=c.full_name,
        email=c.email,
        phone=c.phone,
        address=c.address,
        status=c.status,
        plan_name=c.plan.name if c.plan else None,
        ip_address=c.ip_address,
    )


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------

class PortalInvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    period: Optional[str]
    amount: float
    status: InvoiceStatus
    issue_date: Optional[datetime]
    due_date: Optional[datetime]
    paid_date: Optional[datetime]


@router.get("/invoices", response_model=List[PortalInvoiceResponse])
async def portal_invoices(
    client: Client = Depends(get_current_portal_client),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Invoice)
        .where(Invoice.client_id == client.id)
        .order_by(Invoice.due_date.desc())
        .limit(24)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------

class PortalTicketCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category: TicketCategory = TicketCategory.other


class PortalTicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: Optional[str]
    status: TicketStatus
    priority: TicketPriority
    category: TicketCategory
    created_at: datetime
    comment_count: int = 0


@router.get("/tickets", response_model=List[PortalTicketResponse])
async def portal_tickets(
    client: Client = Depends(get_current_portal_client),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Ticket)
        .options(selectinload(Ticket.comments))
        .where(Ticket.client_id == client.id)
        .order_by(Ticket.created_at.desc())
    )
    tickets = result.scalars().all()
    return [
        PortalTicketResponse(
            id=t.id,
            title=t.title,
            description=t.description,
            status=t.status,
            priority=t.priority,
            category=t.category,
            created_at=t.created_at,
            comment_count=len(t.comments),
        )
        for t in tickets
    ]


@router.post("/tickets", status_code=201)
async def portal_create_ticket(
    body: PortalTicketCreate,
    client: Client = Depends(get_current_portal_client),
    db: AsyncSession = Depends(get_db),
):
    ticket = Ticket(
        client_id=client.id,
        title=body.title,
        description=body.description,
        category=body.category,
        priority=TicketPriority.medium,
        status=TicketStatus.open,
    )
    db.add(ticket)
    await db.commit()
    return {"id": ticket.id}


# ---------------------------------------------------------------------------
# Admin: set portal password for a client
# ---------------------------------------------------------------------------

class SetPortalPassword(BaseModel):
    password: str
    enabled: bool = True


@router.put("/clients/{client_id}/portal-password")
async def set_portal_password(
    client_id: int,
    body: SetPortalPassword,
    db: AsyncSession = Depends(get_db),
):
    from app.core.deps import require_admin
    client = await db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    client.portal_password_hash = get_password_hash(body.password)
    client.portal_enabled = body.enabled
    await db.commit()
    return {"ok": True}
