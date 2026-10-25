import os
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user, get_db
from app.models.ticket import Ticket, TicketComment, TicketCategory, TicketPriority, TicketStatus
from app.models.user import User

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "../../../../uploads/tickets")
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

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
    t = result.scalar_one()
    if t.assigned_to_id:
        from app.api.v1.endpoints.push import send_push_to_user
        await send_push_to_user(
            t.assigned_to_id,
            "Nuevo ticket asignado",
            f"#{t.id} {t.title}",
            f"/tech/tickets/{t.id}",
            db,
        )
    from app.services.telegram import send_telegram
    client_label = f"Cliente #{t.client_id}" if t.client_id else "Sin cliente"
    priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(t.priority, "⚪")
    await send_telegram(
        f"{priority_emoji} *Nuevo ticket #{t.id}*\n"
        f"Título: {t.title}\n"
        f"Categoría: {t.category}\n"
        f"{client_label}"
    )
    return TicketResponse.from_orm_full(t)


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
    prev_assigned = ticket.assigned_to_id
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(ticket, field, value)
    db.add(ticket)
    await db.commit()
    result = await db.execute(select(Ticket).options(*_ticket_options()).where(Ticket.id == ticket_id))
    t = result.scalar_one()
    # Notify technician if newly assigned
    if body.assigned_to_id and body.assigned_to_id != prev_assigned:
        from app.api.v1.endpoints.push import send_push_to_user
        await send_push_to_user(
            body.assigned_to_id,
            "Ticket asignado",
            f"#{t.id} {t.title}",
            f"/tech/tickets/{t.id}",
            db,
        )
    return TicketResponse.from_orm_full(t)


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


@router.post("/{ticket_id}/attachments")
async def upload_attachment(
    ticket_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    ticket = await db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Solo se permiten imágenes (JPEG, PNG, WebP, GIF)")

    ext = (file.filename or "img").rsplit(".", 1)[-1].lower()
    if ext not in ("jpg", "jpeg", "png", "webp", "gif"):
        ext = "jpg"

    dest_dir = os.path.join(UPLOAD_DIR, str(ticket_id))
    os.makedirs(dest_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(dest_dir, filename)

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Imagen demasiado grande (máx 10 MB)")

    with open(path, "wb") as f:
        f.write(contents)

    return {"url": f"/uploads/tickets/{ticket_id}/{filename}"}


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
