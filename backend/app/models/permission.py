from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


SECTIONS = [
    "clients", "plans", "routers", "billing", "firewall",
    "monitoring", "ubiquiti", "users", "map", "ip_pool", "audit", "bandwidth",
    # Guaynet Seguridad sections
    "security_properties", "security_subscriptions", "security_alerts",
    "security_entry_sessions", "security_events", "security_reports",
    "security_members", "security_neighborhood",
    # Etapa 2: modules that were open to any logged-in user
    "zones", "expenses", "alarms", "tickets", "work_orders", "inventory", "reports",
    # Etapa 2: split out of security_subscriptions (migration 044 copies its grants)
    "security_plans", "security_contracts", "security_settings", "security_devices",
]

# Etapa 3: sensitive actions. Stored like sections (can_view = allowed) and
# checked on top of "editar" of their section. Both non-admin roles start denied;
# an administrator can grant each action explicitly in Usuarios → Permisos.
ACTIONS = [
    "act_client_service",   # cortar / reactivar / dar de baja el servicio
    "act_client_delete",    # borrar clientes
    "act_payments",         # registrar pagos
    "act_invoice_afip",     # emitir factura electrónica (AFIP)
    "act_billing_bulk",     # generar facturas del mes, marcar vencidas, corte masivo, recordatorios masivos
    "act_export",           # exportar datos (CSV)
    "act_device_ssh",       # SSH y firmware en equipos Ubiquiti
    "act_alert_close",      # resolver alertas o marcarlas como falsa alarma
    "act_security_pins",    # cambiar PINs y palabra segura de abonados
    "act_access_links",     # generar enlaces del portal y de Telegram
]
SECTIONS += ACTIONS


ROLES = ["operator", "technician"]

DEFAULTS: list[tuple[str, str, bool, bool]] = [
    # (role, section, can_view, can_edit)
    ("operator",   "clients",    True,  True),
    ("operator",   "plans",      True,  False),
    ("operator",   "routers",    True,  False),
    ("operator",   "billing",    True,  True),
    ("operator",   "firewall",   False, False),
    ("operator",   "monitoring", True,  False),
    ("operator",   "ubiquiti",   False, False),
    ("operator",   "users",      False, False),
    ("operator",   "map",        True,  False),
    ("operator",   "ip_pool",    True,  False),
    ("operator",   "audit",      True,  False),
    ("operator",   "bandwidth",  True,  False),
    ("technician", "clients",    True,  False),
    ("technician", "plans",      False, False),
    ("technician", "routers",    True,  True),
    ("technician", "billing",    False, False),
    ("technician", "firewall",   True,  True),
    ("technician", "monitoring", True,  False),
    ("technician", "ubiquiti",   True,  True),
    ("technician", "users",      False, False),
    ("technician", "map",        True,  False),
    ("technician", "ip_pool",    True,  False),
    ("technician", "audit",      False, False),
    ("technician", "bandwidth",  True,  False),
    # Etapa 2: these modules had no permission check, so both roles start with
    # full access (same as before); tighten them in Usuarios → Permisos.
    *[(role, section, True, True)
      for role in ("operator", "technician")
      for section in ("zones", "expenses", "alarms", "tickets", "work_orders", "inventory", "reports")],
    *[(role, action, False, False) for role in ("operator", "technician") for action in ACTIONS],
]


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role", "section", name="uq_role_section"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(String(20), index=True)
    section: Mapped[str] = mapped_column(String(50))
    can_view: Mapped[bool] = mapped_column(Boolean, default=False)
    can_edit: Mapped[bool] = mapped_column(Boolean, default=False)
