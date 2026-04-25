"""add phone to quotation

Revision ID: f2b3c4d5e6f7
Revises: e3d4c5b6a7f8
Create Date: 2026-04-25 11:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2b3c4d5e6f7'
down_revision: Union[str, Sequence[str], None] = 'e3d4c5b6a7f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('quotations', sa.Column('customer_phone', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('quotations', 'customer_phone')
