"""add_text_field_to_chunks

Revision ID: a1e0558e0a10
Revises: 001_initial_schema
Create Date: 2026-04-09 17:58:43.298525

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1e0558e0a10'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add text column to chunks table
    op.add_column('chunks', sa.Column('text', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove text column from chunks table
    op.drop_column('chunks', 'text')
