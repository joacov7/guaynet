"""
Security events endpoints — Stage 2 implementation pending.
"""
from typing import List

from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_user, get_db
from app.schemas.security.event import SecurityEventResponse

router = APIRouter()


@router.get("/", response_model=List[SecurityEventResponse])
async def list_events(
    subscription_id: int = Query(...),
    limit: int = Query(default=50, le=200),
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    raise NotImplementedError("Stage 2")
