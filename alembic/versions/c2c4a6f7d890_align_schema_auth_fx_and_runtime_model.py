"""align schema auth fx and runtime model

Revision ID: c2c4a6f7d890
Revises: 1f6e7b9a2c4d
Create Date: 2026-04-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c2c4a6f7d890"
down_revision: Union[str, Sequence[str], None] = "1f6e7b9a2c4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "expenses", "owner_email"):
        op.add_column("expenses", sa.Column("owner_email", sa.String(), nullable=True))
    if not _has_column(inspector, "expenses", "base_currency"):
        op.add_column("expenses", sa.Column("base_currency", sa.String(length=3), nullable=True))
    if not _has_column(inspector, "expenses", "fx_rate"):
        op.add_column("expenses", sa.Column("fx_rate", sa.Float(), nullable=True))
    if not _has_column(inspector, "expenses", "base_currency_amount"):
        op.add_column("expenses", sa.Column("base_currency_amount", sa.Float(), nullable=True))

    op.execute("UPDATE expenses SET vendor = COALESCE(NULLIF(vendor, ''), 'Unknown')")
    op.execute("UPDATE expenses SET date = COALESCE(date, CURRENT_DATE)")
    op.execute("UPDATE expenses SET owner_email = COALESCE(NULLIF(owner_email, ''), 'anonymous@local')")
    op.execute("UPDATE expenses SET base_currency = COALESCE(NULLIF(base_currency, ''), 'EUR')")
    op.execute("UPDATE expenses SET fx_rate = COALESCE(fx_rate, 1.0)")
    op.execute("UPDATE expenses SET base_currency_amount = COALESCE(base_currency_amount, amount)")

    # Keep legacy column for backward compatibility but allow nulls.
    inspector = sa.inspect(bind)
    if _has_column(inspector, "expenses", "date_incurred"):
        op.alter_column("expenses", "date_incurred", existing_type=sa.Date(), nullable=True)

    op.alter_column("expenses", "vendor", existing_type=sa.String(), nullable=False)
    op.alter_column("expenses", "date", existing_type=sa.Date(), nullable=False)
    op.alter_column("expenses", "amount", existing_type=sa.Float(), nullable=False)
    op.alter_column("expenses", "currency", existing_type=sa.String(length=3), nullable=False)
    op.alter_column("expenses", "owner_email", existing_type=sa.String(), nullable=False)
    op.alter_column("expenses", "base_currency", existing_type=sa.String(length=3), nullable=False)
    op.alter_column("expenses", "fx_rate", existing_type=sa.Float(), nullable=False)
    op.alter_column("expenses", "base_currency_amount", existing_type=sa.Float(), nullable=False)

    inspector = sa.inspect(bind)
    if not _has_index(inspector, "expenses", "ix_expenses_owner_email"):
        op.create_index("ix_expenses_owner_email", "expenses", ["owner_email"], unique=False)
    if not _has_index(inspector, "expenses", "ix_expenses_date"):
        op.create_index("ix_expenses_date", "expenses", ["date"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_index(inspector, "expenses", "ix_expenses_date"):
        op.drop_index("ix_expenses_date", table_name="expenses")
    if _has_index(inspector, "expenses", "ix_expenses_owner_email"):
        op.drop_index("ix_expenses_owner_email", table_name="expenses")

    inspector = sa.inspect(bind)
    if _has_column(inspector, "expenses", "base_currency_amount"):
        op.drop_column("expenses", "base_currency_amount")
    if _has_column(inspector, "expenses", "fx_rate"):
        op.drop_column("expenses", "fx_rate")
    if _has_column(inspector, "expenses", "base_currency"):
        op.drop_column("expenses", "base_currency")
    if _has_column(inspector, "expenses", "owner_email"):
        op.drop_column("expenses", "owner_email")
