"""permissions: split security_subscriptions into plans/contracts/settings/devices

Until now one permission ("security_subscriptions") covered subscriptions,
security plans, contracts, security settings and devices. Each now has its own
section; whoever had security_subscriptions (by role or per user) keeps the same
access on the new sections. Data-only migration.

Revision ID: 044
Revises: 043
Create Date: 2026-11-01
"""
from alembic import op

revision = "044"
down_revision = "043"
branch_labels = None
depends_on = None

NEW_SECTIONS = ("security_plans", "security_contracts", "security_settings", "security_devices")


def upgrade() -> None:
    for section in NEW_SECTIONS:
        op.execute(f"""
            INSERT INTO role_permissions (role, section, can_view, can_edit)
            SELECT rp.role, '{section}', rp.can_view, rp.can_edit
            FROM role_permissions rp
            WHERE rp.section = 'security_subscriptions'
              AND NOT EXISTS (
                SELECT 1 FROM role_permissions x WHERE x.role = rp.role AND x.section = '{section}'
              )
        """)
        op.execute(f"""
            INSERT INTO user_permissions (user_id, section, can_view, can_edit)
            SELECT up.user_id, '{section}', up.can_view, up.can_edit
            FROM user_permissions up
            WHERE up.section = 'security_subscriptions'
              AND NOT EXISTS (
                SELECT 1 FROM user_permissions x WHERE x.user_id = up.user_id AND x.section = '{section}'
              )
        """)


def downgrade() -> None:
    sections = ", ".join(f"'{s}'" for s in NEW_SECTIONS)
    op.execute(f"DELETE FROM role_permissions WHERE section IN ({sections})")
    op.execute(f"DELETE FROM user_permissions WHERE section IN ({sections})")
