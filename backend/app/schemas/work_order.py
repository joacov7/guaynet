from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.models.work_order import WorkOrderStatus, WorkOrderType


class WorkOrderBase(BaseModel):
    title: str
    description: Optional[str] = None
    type: WorkOrderType = WorkOrderType.other
    priority: str = "medium"
    client_id: Optional[int] = None
    assigned_to_id: Optional[int] = None
    scheduled_date: Optional[datetime] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class WorkOrderCreate(WorkOrderBase):
    pass


class WorkOrderUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[WorkOrderType] = None
    status: Optional[WorkOrderStatus] = None
    priority: Optional[str] = None
    client_id: Optional[int] = None
    assigned_to_id: Optional[int] = None
    scheduled_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    completion_notes: Optional[str] = None


class WorkOrderResponse(WorkOrderBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: WorkOrderStatus
    completion_notes: Optional[str] = None
    completed_at: Optional[datetime] = None
    photo_urls: Optional[List[str]] = None
    client_name: Optional[str] = None
    assigned_to_name: Optional[str] = None
    created_at: datetime
