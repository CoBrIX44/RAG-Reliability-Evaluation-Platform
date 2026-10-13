"""Enable vector support and service heartbeats without speculative application tables."""

import sqlalchemy as sa
from alembic import op

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "service_heartbeats",
        sa.Column("service", sa.String(length=64), primary_key=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("service_heartbeats")
    # The extension may be used by other schemas; do not remove it automatically.
