from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_user, get_db
from app.models.security.event import SecurityEventType
from app.schemas.security.event import SecurityEventResponse
from app.services.security import events as svc

router = APIRouter()


@router.get("/", response_model=List[SecurityEventResponse])
async def list_events(
    subscription_id: int = Query(...),
    event_type: Optional[SecurityEventType] = Query(default=None),
    from_date: Optional[datetime] = Query(default=None),
    to_date: Optional[datetime] = Query(default=None),
    limit: int = Query(default=200, le=500),
    _=Depends(get_current_user),
    db=Depends(get_db),
):
    return await svc.list_events(
        db,
        subscription_id=subscription_id,
        limit=limit,
        event_type=event_type,
        from_date=from_date,
        to_date=to_date,
    )
