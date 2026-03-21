"""align expenses schema with runtime model

Revision ID: 1f6e7b9a2c4d
Revises: 30eb4843fa0b
Create Date: 2026-03-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1f6e7b9a2c4d"
down_revision: Union[str, Sequence[str], None] = "30eb4843fa0b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "expenses", "vendor"):
        op.add_column("expenses", sa.Column("vendor", sa.String(), nullable=True))

    if not _has_column(inspector, "expenses", "date"):
        op.add_column("expenses", sa.Column("date", sa.Date(), nullable=True))

    inspector = sa.inspect(bind)
    if _has_column(inspector, "expenses", "date_incurred"):
        op.execute("UPDATE expenses SET date = COALESCE(date, date_incurred)")

    op.execute("UPDATE expenses SET vendor = COALESCE(NULLIF(vendor, ''), 'Unknown')")
    op.execute("UPDATE expenses SET date = COALESCE(date, CURRENT_DATE)")

    inspector = sa.inspect(bind)
    if not _has_index(inspector, "expenses", "ix_expenses_vendor"):
        op.create_index("ix_expenses_vendor", "expenses", ["vendor"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_index(inspector, "expenses", "ix_expenses_vendor"):
        op.drop_index("ix_expenses_vendor", table_name="expenses")

    inspector = sa.inspect(bind)
    if _has_column(inspector, "expenses", "vendor"):
        op.drop_column("expenses", "vendor")
    if _has_column(inspector, "expenses", "date"):
        op.drop_column("expenses", "date")
