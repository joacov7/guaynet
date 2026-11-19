import enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Enum as SAEnum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.client import Client
    from app.models.security.subscription import SecuritySubscription
    from app.models.security.member import PropertyMember


class PropertyType(str, enum.Enum):
    home = "home"
    commercial = "commercial"
    industrial = "industrial"
    other = "other"


class Property(Base, TimestampMixin):
    """
    Physical location monitored by Guaynet Seguridad.

    A property belongs to one User (security_client role or existing staff user).
    It may optionally link to an internet Client record when the same person has both services.
    A property can have multiple security subscriptions over time (only one active at a time).
    """
    __tablename__ = "sec_properties"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Owner: a User account. Security-only clients get a User with role="security_client".
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    # Optional link to the internet Client record (same person, both services).
    internet_client_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True
    )

    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(String(500))
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    province: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    property_type: Mapped[PropertyType] = mapped_column(
        SAEnum(PropertyType, native_enum=False), default=PropertyType.home
    )
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_user_id], lazy="select")
    internet_client: Mapped[Optional["Client"]] = relationship(
        "Client", foreign_keys=[internet_client_id], lazy="select"
    )
    subscriptions: Mapped[List["SecuritySubscription"]] = relationship(
        "SecuritySubscription", back_populates="property", cascade="all, delete-orphan"
    )
    members: Mapped[List["PropertyMember"]] = relationship(
        "PropertyMember", back_populates="property", cascade="all, delete-orphan"
    )
