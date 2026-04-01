"""add source_type and saved_queries

Revision ID: d4b925b11670
Revises: c2c4a6f7d890
Create Date: 2026-04-01 01:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4b925b11670"
down_revision: Union[str, Sequence[str], None] = "c2c4a6f7d890"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "expenses", "source_type"):
        op.add_column("expenses", sa.Column("source_type", sa.String(), nullable=True))
    op.execute("UPDATE expenses SET source_type = COALESCE(NULLIF(source_type, ''), 'manual')")
    op.alter_column("expenses", "source_type", existing_type=sa.String(), nullable=False)

    inspector = sa.inspect(bind)
    if not _has_table(inspector, "saved_queries"):
        op.create_table(
            "saved_queries",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("owner_email", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("sql_query", sa.Text(), nullable=False),
            sa.Column("chart_type", sa.String(), nullable=False),
            sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.PrimaryKeyConstraint("id"),
        )
    inspector = sa.inspect(bind)
    if not _has_index(inspector, "saved_queries", "ix_saved_queries_owner_email"):
        op.create_index("ix_saved_queries_owner_email", "saved_queries", ["owner_email"], unique=False)
    if not _has_index(inspector, "saved_queries", "ix_saved_queries_id"):
        op.create_index("ix_saved_queries_id", "saved_queries", ["id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_index(inspector, "saved_queries", "ix_saved_queries_id"):
        op.drop_index("ix_saved_queries_id", table_name="saved_queries")
    if _has_index(inspector, "saved_queries", "ix_saved_queries_owner_email"):
        op.drop_index("ix_saved_queries_owner_email", table_name="saved_queries")
    inspector = sa.inspect(bind)
    if _has_table(inspector, "saved_queries"):
        op.drop_table("saved_queries")
    inspector = sa.inspect(bind)
    if _has_column(inspector, "expenses", "source_type"):
        op.drop_column("expenses", "source_type")
