"""add multi-format support

Revision ID: 002_add_multiformat_support
Revises: a1e0558e0a10
Create Date: 2026-04-11 18:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_add_multiformat_support'
down_revision = 'a1e0558e0a10'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add file_type column to documents table
    op.add_column('documents', sa.Column('file_type', sa.String(length=50), nullable=True))

    # Add has_embeddings column to documents table with default True
    op.add_column('documents', sa.Column('has_embeddings', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    # Remove columns in reverse order
    op.drop_column('documents', 'has_embeddings')
    op.drop_column('documents', 'file_type')
