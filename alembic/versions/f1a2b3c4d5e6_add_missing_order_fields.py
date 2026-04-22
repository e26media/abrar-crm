"""add missing order fields

Revision ID: f1a2b3c4d5e6
Revises: eba60c2f033d
Create Date: 2026-04-22 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'eba60c2f033d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use batch_op for SQLite compatibility if needed, but Render uses Postgres
    # For Postgres, just add columns. We check if they exist to be safe.
    
    # Get current connection
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('orders')]
    
    if 'venue' not in columns:
        op.add_column('orders', sa.Column('venue', sa.String(length=255), nullable=True))
    
    if 'manual_total' not in columns:
        op.add_column('orders', sa.Column('manual_total', sa.Float(), nullable=True))
        
    if 'manual_price_per_plate' not in columns:
        op.add_column('orders', sa.Column('manual_price_per_plate', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('orders', 'manual_price_per_plate')
    op.drop_column('orders', 'manual_total')
    op.drop_column('orders', 'venue')
