"""add author field to documents

Revision ID: 003_add_author_field
Revises: 002_add_multiformat_support
Create Date: 2026-04-11 19:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003_add_author_field'
down_revision = '002_add_multiformat_support'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add author column to documents table
    op.add_column('documents', sa.Column('author', sa.String(length=200), nullable=True))


def downgrade() -> None:
    # Remove author column
    op.drop_column('documents', 'author')
