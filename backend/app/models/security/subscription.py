import enum
from datetime import date
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Date, Enum as SAEnum, ForeignKey, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.security.property import Property
    from app.models.security.device import SecurityDevice
    from app.models.security.alert import SecurityAlert
    from app.models.security.event import SecurityEvent


class SecuritySubscriptionStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"
    cancelled = "cancelled"
    pending_install = "pending_install"


class SecurityFeatureName(str, enum.Enum):
    """All toggleable features of the security service."""
    entry_secure = "entry_secure"         # Entrada Segura timers
    panic_button = "panic_button"         # Botón de pánico
    duress_pin = "duress_pin"             # PIN de coacción
    safe_word = "safe_word"               # Palabra segura (phone verification)
    vacation_mode = "vacation_mode"       # Modo ausencia / viaje
    member_access = "member_access"       # Invitación de miembros
    camera_access = "camera_access"       # Acceso a cámaras
    elderly_care = "elderly_care"         # Cuidado de adultos mayores
    schedule_alerts = "schedule_alerts"   # Alertas de apertura/cierre comercial
    alert_confirmation = "alert_confirmation"  # Cliente confirma "estoy bien"
    equipment_status = "equipment_status"      # Estado de equipos visible
    monitoring_certificate = "monitoring_certificate"  # Certificado PDF para seguros
    tech_survey = "tech_survey"           # Encuesta post visita técnica
    event_history = "event_history"       # Historial de eventos para el cliente
    monthly_report = "monthly_report"     # Reporte mensual automático
    digital_contract = "digital_contract" # Firma digital del contrato


class SecurityPlan(Base, TimestampMixin):
    """
    Commercial plan for the security service.
    Defines the default features included and the monthly price.
    """
    __tablename__ = "sec_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # JSON list of SecurityFeatureName values included in this plan by default.
    default_features: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)

    subscriptions: Mapped[List["SecuritySubscription"]] = relationship(
        "SecuritySubscription", back_populates="plan"
    )


class SecuritySubscription(Base, TimestampMixin):
    """
    Active security service contract for a property.
    One property can have at most one active subscription at a time.
    """
    __tablename__ = "sec_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("sec_properties.id"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("sec_plans.id"))
    status: Mapped[SecuritySubscriptionStatus] = mapped_column(
        SAEnum(SecuritySubscriptionStatus, native_enum=False),
        default=SecuritySubscriptionStatus.pending_install,
        index=True,
    )

    # BEAT central monitoring account identifier for this property
    beat_account_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    contract_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    contract_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    billing_day: Mapped[int] = mapped_column(default=1)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    property: Mapped["Property"] = relationship("Property", back_populates="subscriptions")
    plan: Mapped["SecurityPlan"] = relationship("SecurityPlan", back_populates="subscriptions")
    features: Mapped[List["SecurityFeature"]] = relationship(
        "SecurityFeature", back_populates="subscription", cascade="all, delete-orphan"
    )
    devices: Mapped[List["SecurityDevice"]] = relationship(
        "SecurityDevice", back_populates="subscription", cascade="all, delete-orphan"
    )
    alerts: Mapped[List["SecurityAlert"]] = relationship(
        "SecurityAlert", back_populates="subscription"
    )
    events: Mapped[List["SecurityEvent"]] = relationship(
        "SecurityEvent", back_populates="subscription"
    )

    def has_feature(self, feature: SecurityFeatureName) -> bool:
        for f in self.features:
            if f.feature_name == feature:
                return f.enabled
        return False


class SecurityFeature(Base):
    """
    Per-subscription feature toggle.
    Overrides the plan's default_features for this specific subscription.
    Admin can enable or disable any feature independently of the plan.
    """
    __tablename__ = "sec_features"
    __table_args__ = (
        UniqueConstraint("subscription_id", "feature_name", name="uq_sec_feature"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("sec_subscriptions.id", ondelete="CASCADE"), index=True
    )
    feature_name: Mapped[SecurityFeatureName] = mapped_column(
        SAEnum(SecurityFeatureName, native_enum=False)
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    subscription: Mapped["SecuritySubscription"] = relationship(
        "SecuritySubscription", back_populates="features"
    )
