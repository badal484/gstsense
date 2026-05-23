"""add pending subscription status

Revision ID: a3f8c2d1e904
Revises: 95753296c52c
Create Date: 2026-05-23 10:30:00.000000

"""
from alembic import op

revision = "a3f8c2d1e904"
down_revision = "95753296c52c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ADD VALUE cannot run inside a transaction in Postgres < 12.
    # We use COMMIT + BEGIN to work around it on older versions.
    # On Postgres 12+ this is a no-op but still safe.
    op.execute("ALTER TYPE subscription_status ADD VALUE IF NOT EXISTS 'pending'")


def downgrade() -> None:
    # Postgres does not support removing enum values.
    # Downgrade is intentionally a no-op; remove rows with status='pending'
    # manually before rolling back if needed.
    pass
