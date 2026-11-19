revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "alarms",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("router_id", sa.Integer(), sa.ForeignKey("mikrotik_routers.id"), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alarms_router_id", "alarms", ["router_id"])
    op.create_index("ix_alarms_type", "alarms", ["type"])
    op.create_index("ix_alarms_status", "alarms", ["status"])


def downgrade():
    op.drop_index("ix_alarms_status", table_name="alarms")
    op.drop_index("ix_alarms_type", table_name="alarms")
    op.drop_index("ix_alarms_router_id", table_name="alarms")
    op.drop_table("alarms")
