"""add canal tubewell other irrigation types

Revision ID: 916f8297b1b4
Revises: d8ca07977247
Create Date: 2026-08-14 08:36:23.303782

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '916f8297b1b4'
down_revision: Union[str, Sequence[str], None] = 'd8ca07977247'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Alembic autogenerate does not detect new PostgreSQL enum values, so
    these ALTER TYPE statements are written by hand. Each must run in its
    own transaction/statement (not batched) -- PostgreSQL does not allow
    ALTER TYPE ... ADD VALUE to run inside the same transaction as a
    statement that uses the new value.
    """
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE irrigation_type ADD VALUE IF NOT EXISTS 'CANAL'")
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE irrigation_type ADD VALUE IF NOT EXISTS 'TUBEWELL'")
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE irrigation_type ADD VALUE IF NOT EXISTS 'OTHER'")


def downgrade() -> None:
    """Downgrade schema.

    PostgreSQL does not support removing a value from an enum type. A true
    downgrade would require creating a new enum type without the removed
    values, migrating the column over, and dropping the old type -- which
    also requires deciding what happens to any rows already using the
    removed values. Left as a no-op since this migration is purely additive
    and non-destructive; do not run this downgrade in an environment where
    CANAL/TUBEWELL/OTHER are already in use.
    """
    pass
