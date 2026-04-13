"""Initial schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable UUID extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # Create documents table
    op.create_table('documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(length=500), nullable=False),
        sa.Column('file_hash', sa.String(length=64), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('chunk_count', sa.Integer(), server_default='0'),
        sa.Column('status', sa.String(length=20), server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed')", name='check_status'),
    )

    # Create indexes for documents
    op.create_index('idx_documents_name', 'documents', ['name'])
    op.create_index('idx_documents_hash', 'documents', ['file_hash'])
    op.create_index('idx_documents_uploaded', 'documents', ['uploaded_at'], postgresql_ops={'uploaded_at': 'DESC'})
    op.create_index('idx_documents_status', 'documents', ['status'])

    # Create tags table
    op.create_table('tags',
        sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column('name', sa.String(length=100), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )

    # Create index for tags
    op.create_index('idx_tags_name', 'tags', ['name'])

    # Create document_tags junction table
    op.create_table('document_tags',
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('tag_id', sa.Integer(), sa.ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )

    # Create indexes for document_tags
    op.create_index('idx_document_tags_document', 'document_tags', ['document_id'])
    op.create_index('idx_document_tags_tag', 'document_tags', ['tag_id'])

    # Create chunks table
    op.create_table('chunks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('chunk_type', sa.String(length=10), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('text_preview', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.CheckConstraint("chunk_type IN ('text', 'table', 'image')", name='check_chunk_type'),
        sa.UniqueConstraint('document_id', 'chunk_index', name='unique_chunk'),
    )

    # Create indexes for chunks
    op.create_index('idx_chunks_document', 'chunks', ['document_id'])
    op.create_index('idx_chunks_type', 'chunks', ['chunk_type'])

    # Create upload_tasks table
    op.create_table('upload_tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='queued'),
        sa.Column('progress', sa.Integer(), server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.CheckConstraint("status IN ('queued', 'processing', 'completed', 'failed')", name='check_upload_status'),
        sa.CheckConstraint("progress >= 0 AND progress <= 100", name='check_progress_range'),
    )

    # Create indexes for upload_tasks
    op.create_index('idx_upload_tasks_status', 'upload_tasks', ['status'])
    op.create_index('idx_upload_tasks_created', 'upload_tasks', ['created_at'], postgresql_ops={'created_at': 'DESC'})

    # Create trigger for auto-updating updated_at
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    op.execute("""
        CREATE TRIGGER update_documents_updated_at
        BEFORE UPDATE ON documents
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    # Drop trigger
    op.execute('DROP TRIGGER IF EXISTS update_documents_updated_at ON documents')
    op.execute('DROP FUNCTION IF EXISTS update_updated_at_column()')

    # Drop tables in reverse order
    op.drop_table('upload_tasks')
    op.drop_table('chunks')
    op.drop_table('document_tags')
    op.drop_table('tags')
    op.drop_table('documents')

    # Drop UUID extension
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
