"""create_weather_platform_tables

Revision ID: e1b82c3f9104
Revises: ccae73151272
Create Date: 2026-09-04 16:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry

# revision identifiers, used by Alembic.
revision: str = 'e1b82c3f9104'
down_revision: Union[str, Sequence[str], None] = 'ccae73151272'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create weather_reports table
    op.create_table(
        'weather_reports',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('report_id', UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column('source', sa.String(length=32), nullable=False, server_default='citizen'),
        sa.Column('source_report_id', sa.String(length=256), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('event_time', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('city', sa.String(length=128), nullable=False, server_default='Unknown'),
        sa.Column('state', sa.String(length=128), nullable=False, server_default='India'),
        sa.Column('district', sa.String(length=128), nullable=True),
        sa.Column('country', sa.String(length=64), nullable=False, server_default='India'),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('geometry', Geometry(geometry_type='POINT', srid=4326), nullable=False),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('media_urls', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('image_hash', sa.String(length=128), nullable=True),
        sa.Column('video_reference', sa.String(length=256), nullable=True),
        sa.Column('hashtags', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('event_category', sa.String(length=64), nullable=False, server_default='other'),
        sa.Column('event_confidence', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('classification_model', sa.String(length=128), nullable=True),
        sa.Column('verification_status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('source_trust_score', sa.Float(), nullable=False, server_default='50.0'),
        sa.Column('misinformation_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('trust_reasons', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('duplicate_of', UUID(as_uuid=True), nullable=True),
        sa.Column('is_synthetic', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('processing_status', sa.String(length=32), nullable=False, server_default='processed'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_weather_reports_report_id', 'weather_reports', ['report_id'])
    op.create_index('ix_weather_reports_city', 'weather_reports', ['city'])
    op.create_index('ix_weather_reports_state', 'weather_reports', ['state'])
    op.create_index('ix_weather_reports_event_category', 'weather_reports', ['event_category'])
    op.create_index('ix_weather_reports_verification_status', 'weather_reports', ['verification_status'])
    op.create_index('ix_weather_reports_submitted_at', 'weather_reports', ['submitted_at'])
    op.create_index('ix_weather_reports_duplicate_of', 'weather_reports', ['duplicate_of'])

    # 2. Create weather_incidents table
    op.create_table(
        'weather_incidents',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('incident_id', UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column('event_category', sa.String(length=64), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('centroid', Geometry(geometry_type='POINT', srid=4326), nullable=False),
        sa.Column('radius_km', sa.Float(), nullable=False, server_default='5.0'),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('report_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('verified_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('severity', sa.String(length=32), nullable=False, server_default='moderate'),
        sa.Column('impact_score', sa.Float(), nullable=False, server_default='50.0'),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.8'),
        sa.Column('city', sa.String(length=128), nullable=False),
        sa.Column('state', sa.String(length=128), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_weather_incidents_incident_id', 'weather_incidents', ['incident_id'])
    op.create_index('ix_weather_incidents_event_category', 'weather_incidents', ['event_category'])
    op.create_index('ix_weather_incidents_city', 'weather_incidents', ['city'])
    op.create_index('ix_weather_incidents_state', 'weather_incidents', ['state'])
    op.create_index('ix_weather_incidents_start_time', 'weather_incidents', ['start_time'])

    # 3. Drop foreign key constraint on verification_audit so audits apply to weather reports
    try:
        op.drop_constraint('verification_audit_report_id_fkey', 'verification_audit', type_='foreignkey')
    except Exception:
        pass


def downgrade() -> None:
    op.drop_table('weather_incidents')
    op.drop_table('weather_reports')
