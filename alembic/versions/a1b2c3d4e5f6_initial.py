"""initial tables for logs and metrics

Revision ID: a1b2c3d4e5f6
Revises: 
Create Date: 2025-09-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'deid_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('request_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('num_entities', sa.Integer(), nullable=False),
        sa.Column('time_ms', sa.Float(), nullable=False),
        sa.Column('input_len', sa.Integer(), nullable=False),
        sa.Column('output_len', sa.Integer(), nullable=False),
        sa.Column('policy_version', sa.String(length=64), nullable=False),
        sa.Column('lang_hint', sa.String(length=8), nullable=True),
        sa.Column('sample_preview', sa.Text(), nullable=True),
    )

    op.create_table(
        'metric_runs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('dataset_name', sa.String(length=255), nullable=False),
        sa.Column('precision', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('recall', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('f1', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('docs_per_sec', sa.Float(), nullable=True),
        sa.Column('false_negative_rate', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('metric_runs')
    op.drop_table('deid_logs')

