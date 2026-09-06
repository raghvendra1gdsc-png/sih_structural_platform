"""add_verification_audit_and_performance_indexes

Revision ID: ccae73151272
Revises: 7a82b9e14c33
Create Date: 2026-09-04 15:34:31.903764

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'ccae73151272'
down_revision: Union[str, Sequence[str], None] = '7a82b9e14c33'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Create verification_audit table
    op.create_table(
        'verification_audit',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('report_id', UUID(as_uuid=True), sa.ForeignKey('reports.report_id', ondelete='CASCADE'), nullable=False),
        sa.Column('previous_status', sa.String(length=32), nullable=False),
        sa.Column('new_status', sa.String(length=32), nullable=False),
        sa.Column('action', sa.String(length=32), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('merged_into', UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_verification_audit_report_id', 'verification_audit', ['report_id'])
    op.create_index('ix_verification_audit_created_at', 'verification_audit', ['created_at'])

    # 2. Add performance query indexes on reports
    op.create_index('ix_reports_submitted_at', 'reports', ['submitted_at'])
    op.create_index('ix_reports_damage_type', 'reports', ['damage_type'])
    op.create_index('ix_reports_severity', 'reports', ['severity'])
    op.create_index('ix_reports_source', 'reports', ['source'])
    op.create_index('ix_reports_duplicate_of', 'reports', ['duplicate_of'])

    # 3. Add performance index on earthquake_events
    op.create_index('ix_earthquake_events_event_time', 'earthquake_events', ['event_time'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_earthquake_events_event_time', table_name='earthquake_events')
    op.drop_index('ix_reports_duplicate_of', table_name='reports')
    op.drop_index('ix_reports_source', table_name='reports')
    op.drop_index('ix_reports_severity', table_name='reports')
    op.drop_index('ix_reports_damage_type', table_name='reports')
    op.drop_index('ix_reports_submitted_at', table_name='reports')
    op.drop_index('ix_verification_audit_created_at', table_name='verification_audit')
    op.drop_index('ix_verification_audit_report_id', table_name='verification_audit')
    op.drop_table('verification_audit')
