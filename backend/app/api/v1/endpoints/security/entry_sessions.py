from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_user, get_db
from app.schemas.security.entry_session import (
    EntrySessionCancel,
    EntrySessionCreate,
    EntrySessionResponse,
)
from app.services.security import entry_sessions as svc

router = APIRouter()


@router.post("/", response_model=EntrySessionResponse, status_code=201)
async def start_entry_session(
    body: EntrySessionCreate,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    return await svc.start_entry_session(db, body, activated_by_user_id=current_user.id)


@router.get("/active", response_model=List[EntrySessionResponse])
async def list_active_sessions(
    subscription_id: Optional[int] = Query(default=None),
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    return await svc.list_active_sessions(db, subscription_id=subscription_id)


@router.post("/{session_id}/cancel", response_model=EntrySessionResponse)
async def cancel_entry_session(
    session_id: int,
    body: EntrySessionCancel,
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    return await svc.cancel_entry_session(db, session_id, pin=body.pin)
