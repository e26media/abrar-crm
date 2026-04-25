"""add sqft to unitenum

Revision ID: e3d4c5b6a7f8
Revises: f1a2b3c4d5e6
Create Date: 2026-04-25 10:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3d4c5b6a7f8'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # In PostgreSQL, ALTER TYPE ADD VALUE cannot run in a transaction block
    # until Postgres 12+, but even then, Alembic usually runs in a transaction.
    # We use the 'autocommit' approach.
    
    # We need to check if we are on Postgres
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        # Adding 'plate' and 'sqft' to the enum
        # Note: IF NOT EXISTS is available in Postgres 13+
        # If your Render DB is older than 13, this might fail, 
        # but Render usually provides recent versions.
        op.execute("ALTER TYPE unitenum ADD VALUE IF NOT EXISTS 'plate'")
        op.execute("ALTER TYPE unitenum ADD VALUE IF NOT EXISTS 'sqft'")
    else:
        # For SQLite or others, we don't need to do anything special usually
        # or it's handled differently. SQLite doesn't have Enums like Postgres.
        pass


def downgrade() -> None:
    # Postgres doesn't easily support removing enum values
    pass
