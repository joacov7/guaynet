from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user, get_db
from app.models.ticket import Ticket, TicketComment, TicketCategory, TicketPriority, TicketStatus
from app.models.user import User

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class TicketCreate(BaseModel):
    title: str
    description: Optional[str] = None
    client_id: Optional[int] = None
    assigned_to_id: Optional[int] = None
    priority: TicketPriority = TicketPriority.medium
    category: TicketCategory = TicketCategory.other


class TicketUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TicketStatus] = None
    priority: Optional[TicketPriority] = None
    category: Optional[TicketCategory] = None
    assigned_to_id: Optional[int] = None
    client_id: Optional[int] = None


class CommentCreate(BaseModel):
    body: str


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ticket_id: int
    author_id: Optional[int]
    author_name: Optional[str] = None
    body: str
    created_at: datetime

    @classmethod
    def from_orm_with_author(cls, c: TicketComment) -> "CommentResponse":
        return cls(
            id=c.id,
            ticket_id=c.ticket_id,
            author_id=c.author_id,
            author_name=c.author.full_name if c.author else None,
            body=c.body,
            created_at=c.created_at,
        )


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    client_id: Optional[int]
    client_name: Optional[str] = None
    assigned_to_id: Optional[int]
    assigned_to_name: Optional[str] = None
    title: str
    description: Optional[str]
    status: TicketStatus
    priority: TicketPriority
    category: TicketCategory
    created_at: datetime
    comments: List[CommentResponse] = []

    @classmethod
    def from_orm_full(cls, t: Ticket) -> "TicketResponse":
        return cls(
            id=t.id,
            client_id=t.client_id,
            client_name=t.client.full_name if t.client else None,
            assigned_to_id=t.assigned_to_id,
            assigned_to_name=t.assigned_to.full_name if t.assigned_to else None,
            title=t.title,
            description=t.description,
            status=t.status,
            priority=t.priority,
            category=t.category,
            created_at=t.created_at,
            comments=[CommentResponse.from_orm_with_author(c) for c in t.comments],
        )


def _ticket_options():
    return [
        selectinload(Ticket.client),
        selectinload(Ticket.assigned_to),
        selectinload(Ticket.comments).selectinload(TicketComment.author),
    ]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[TicketResponse])
async def list_tickets(
    status: Optional[TicketStatus] = None,
    priority: Optional[TicketPriority] = None,
    category: Optional[TicketCategory] = None,
    client_id: Optional[int] = None,
    assigned_to_id: Optional[int] = None,
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    q = select(Ticket).options(*_ticket_options()).order_by(Ticket.created_at.desc())
    if status:
        q = q.where(Ticket.status == status)
    if priority:
        q = q.where(Ticket.priority == priority)
    if category:
        q = q.where(Ticket.category == category)
    if client_id:
        q = q.where(Ticket.client_id == client_id)
    if assigned_to_id is not None:
        q = q.where(Ticket.assigned_to_id == assigned_to_id)
    result = await db.execute(q.offset(skip).limit(limit))
    return [TicketResponse.from_orm_full(t) for t in result.scalars().all()]


@router.post("/", response_model=TicketResponse, status_code=201)
async def create_ticket(
    body: TicketCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    ticket = Ticket(**body.model_dump())
    db.add(ticket)
    await db.commit()
    result = await db.execute(select(Ticket).options(*_ticket_options()).where(Ticket.id == ticket.id))
    return TicketResponse.from_orm_full(result.scalar_one())


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(select(Ticket).options(*_ticket_options()).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    return TicketResponse.from_orm_full(ticket)


@router.put("/{ticket_id}", response_model=TicketResponse)
async def update_ticket(
    ticket_id: int,
    body: TicketUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    ticket = await db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(ticket, field, value)
    db.add(ticket)
    await db.commit()
    result = await db.execute(select(Ticket).options(*_ticket_options()).where(Ticket.id == ticket_id))
    return TicketResponse.from_orm_full(result.scalar_one())


@router.delete("/{ticket_id}", status_code=204)
async def delete_ticket(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    ticket = await db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    await db.delete(ticket)
    await db.commit()


@router.post("/{ticket_id}/comments", response_model=CommentResponse, status_code=201)
async def add_comment(
    ticket_id: int,
    body: CommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = await db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    comment = TicketComment(ticket_id=ticket_id, author_id=current_user.id, body=body.body)
    db.add(comment)
    await db.commit()
    result = await db.execute(
        select(TicketComment).options(selectinload(TicketComment.author)).where(TicketComment.id == comment.id)
    )
    c = result.scalar_one()
    return CommentResponse.from_orm_with_author(c)
