"""add section_heading to chunks

Revision ID: 004_add_section_heading
Revises: 003_add_author_field
Create Date: 2026-04-12 20:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004_add_section_heading'
down_revision = '003_add_author_field'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add section_heading column to chunks table
    op.add_column('chunks', sa.Column('section_heading', sa.String(length=500), nullable=True))

    # Add index for faster filtering by section
    op.create_index('idx_chunks_section_heading', 'chunks', ['section_heading'])


def downgrade() -> None:
    # Drop index first
    op.drop_index('idx_chunks_section_heading', table_name='chunks')

    # Drop column
    op.drop_column('chunks', 'section_heading')
