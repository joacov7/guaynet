"""permissions: roles defined by the admin (Usuarios → Permisos)

Roles were fixed in the code (operator, technician). Now they live in the
"roles" table; users.role keeps holding the key, so nobody loses access.
Adds "cobranza" and "atencion" with starting permissions the admin can change.

Revision ID: 051
Revises: 050
Create Date: 2026-11-22
"""
from alembic import op
import sqlalchemy as sa

revision = "051"
down_revision = "050"
branch_labels = None
depends_on = None

ROLES = [
    ("operator", "Operador", "Rol general de antes: clientes, facturación y red en modo consulta."),
    ("technician", "Técnico", "Red, tickets, órdenes de trabajo e inventario. Sin facturación."),
    ("cobranza", "Cobranza", "Facturación y pagos, cortar y reactivar, recordatorios."),
    ("atencion", "Atención al cliente", "Datos de clientes, tickets y órdenes; ve facturas sin cobrar."),
]

V, E = (True, False), (True, True)  # view only / view + edit
PERMS = {
    "cobranza": {
        "clients": E, "plans": V, "zones": V, "billing": E, "reports": V, "tickets": V, "monitoring": V,
        "act_client_service": V, "act_payments": V, "act_invoice_afip": V, "act_billing_bulk": V, "act_export": V,
    },
    "atencion": {
        "clients": E, "plans": V, "zones": V, "billing": V, "tickets": E, "work_orders": E,
        "monitoring": V, "alarms": V, "inventory": V, "map": V,
    },
}


def upgrade() -> None:
    roles = op.create_table(
        "roles",
        sa.Column("key", sa.String(20), primary_key=True),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.bulk_insert(roles, [{"key": k, "name": n, "description": d} for k, n, d in ROLES])

    conn = op.get_bind()
    for role, perms in PERMS.items():
        for section, (view, edit) in perms.items():
            conn.execute(sa.text(
                # Explicit casts: asyncpg refuses a parameter whose type it deduces twice
                "INSERT INTO role_permissions (role, section, can_view, can_edit) "
                "SELECT CAST(:r AS VARCHAR), CAST(:s AS VARCHAR), CAST(:v AS BOOLEAN), CAST(:e AS BOOLEAN) "
                "WHERE NOT EXISTS (SELECT 1 FROM role_permissions "
                "WHERE role = CAST(:r AS VARCHAR) AND section = CAST(:s AS VARCHAR))"
            ), {"r": role, "s": section, "v": view, "e": edit})

    # Roles users already have but that were never in the code list
    conn.execute(sa.text(
        "INSERT INTO roles (key, name) SELECT DISTINCT role, role FROM users "
        "WHERE role <> 'admin' AND role NOT IN (SELECT key FROM roles)"
    ))


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE role IN ('cobranza', 'atencion')")
    op.drop_table("roles")
