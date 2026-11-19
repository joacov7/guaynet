revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column("clients", sa.Column("pppoe_username", sa.String(100), nullable=True))
    op.add_column("clients", sa.Column("pppoe_password_encrypted", sa.String(500), nullable=True))
    op.create_index("ix_clients_pppoe_username", "clients", ["pppoe_username"], unique=True)


def downgrade():
    op.drop_index("ix_clients_pppoe_username", table_name="clients")
    op.drop_column("clients", "pppoe_password_encrypted")
    op.drop_column("clients", "pppoe_username")
