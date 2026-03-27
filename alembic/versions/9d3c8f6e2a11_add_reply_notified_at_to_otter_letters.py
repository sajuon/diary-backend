"""add reply_notified_at to otter_letters

Revision ID: 9d3c8f6e2a11
Revises: 4b8b6dbb3a66
Create Date: 2026-03-14 08:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9d3c8f6e2a11"
down_revision: Union[str, None] = "4b8b6dbb3a66"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "otter_letters",
        sa.Column("reply_notified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_otter_letters_reply_notified_at",
        "otter_letters",
        ["reply_notified_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_otter_letters_reply_notified_at", table_name="otter_letters")
    op.drop_column("otter_letters", "reply_notified_at")
