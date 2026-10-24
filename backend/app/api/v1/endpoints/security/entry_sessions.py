"""
Entry sessions (Entrada Segura) endpoints — Stage 2 implementation pending.
"""
from typing import List

from fastapi import APIRouter, Depends

from app.core.deps import get_current_user, get_db
from app.schemas.security.entry_session import EntrySessionCreate, EntrySessionResponse

router = APIRouter()


@router.post("/", response_model=EntrySessionResponse, status_code=201)
async def start_entry_session(
    body: EntrySessionCreate,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    raise NotImplementedError("Stage 2")


@router.get("/active", response_model=List[EntrySessionResponse])
async def list_active_sessions(
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    raise NotImplementedError("Stage 2")


@router.post("/{session_id}/cancel", response_model=EntrySessionResponse)
async def cancel_entry_session(
    session_id: int,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    raise NotImplementedError("Stage 2")
