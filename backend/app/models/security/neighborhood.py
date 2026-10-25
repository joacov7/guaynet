from typing import Optional

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SecurityNeighborhoodGroup(Base, TimestampMixin):
    __tablename__ = "sec_neighborhood_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    telegram_group_id: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class SecurityNeighborhoodMembership(Base, TimestampMixin):
    """Associates a subscription with a neighborhood group (one group per subscription)."""
    __tablename__ = "sec_neighborhood_memberships"
    __table_args__ = (
        UniqueConstraint("subscription_id", name="uq_neighborhood_membership_subscription"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("sec_neighborhood_groups.id", ondelete="CASCADE"))
    subscription_id: Mapped[int] = mapped_column(ForeignKey("sec_subscriptions.id", ondelete="CASCADE"))
