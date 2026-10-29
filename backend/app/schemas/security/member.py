from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.security.member import PropertyMemberRole


class PropertyMemberBase(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    role: PropertyMemberRole = PropertyMemberRole.family
    can_arm: bool = True
    can_disarm: bool = True
    can_invite: bool = False
    can_view_cameras: bool = False
    notify_on_alarm: bool = True
    notify_on_entry: bool = False


class PropertyMemberCreate(PropertyMemberBase):
    property_id: int


class PropertyMemberUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    role: Optional[PropertyMemberRole] = None
    can_arm: Optional[bool] = None
    can_disarm: Optional[bool] = None
    can_invite: Optional[bool] = None
    can_view_cameras: Optional[bool] = None
    notify_on_alarm: Optional[bool] = None
    notify_on_entry: Optional[bool] = None
    status: Optional[str] = None  # "active" | "revoked"


class PropertyMemberResponse(PropertyMemberBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    property_id: int
    status: str
    invited_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    telegram_linked_at: Optional[datetime] = None  # set while the member's Telegram is linked
