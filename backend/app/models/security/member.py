import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.security.property import Property
    from app.models.user import User


class PropertyMemberRole(str, enum.Enum):
    owner = "owner"         # Full control, can invite
    family = "family"       # Can arm/disarm, limited settings
    employee = "employee"   # Restricted hours, no settings
    trusted = "trusted"     # Custom permissions


class PropertyMember(Base, TimestampMixin):
    """
    A person with access to a property's security features.
    May or may not have a User account (user_id nullable for external contacts).
    """
    __tablename__ = "sec_property_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("sec_properties.id", ondelete="CASCADE"), index=True)
    # User account if this member has app access. Null = external contact only.
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[PropertyMemberRole] = mapped_column(
        SAEnum(PropertyMemberRole, native_enum=False), default=PropertyMemberRole.family
    )

    # Permissions
    can_arm: Mapped[bool] = mapped_column(Boolean, default=False)
    can_disarm: Mapped[bool] = mapped_column(Boolean, default=False)
    can_invite: Mapped[bool] = mapped_column(Boolean, default=False)
    can_view_cameras: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_on_alarm: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_on_entry: Mapped[bool] = mapped_column(Boolean, default=False)

    # Optional schedule restriction: {"days": [1,2,3,4,5], "start": "08:00", "end": "20:00"}
    schedule_restricted: Mapped[bool] = mapped_column(Boolean, default=False)
    schedule_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="active")  # active | revoked
    invited_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    property: Mapped["Property"] = relationship("Property", back_populates="members")
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id], lazy="select")


class EmergencyContact(Base):
    """
    Emergency contacts notified when an alert triggers.
    Ordered by priority. Separate from PropertyMember because
    contacts may not have app access.
    """
    __tablename__ = "sec_emergency_contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("sec_subscriptions.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(50))
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    relation: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    priority_order: Mapped[int] = mapped_column(default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
