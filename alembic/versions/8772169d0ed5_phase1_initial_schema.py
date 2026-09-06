"""phase1_initial_schema

Revision ID: auto_phase1
Revises: 
Create Date: 2026-09-04

Creates:
  - earthquake_events table (USGS events + PostGIS POINT geometry)
  - reports table (normalised citizen/synthetic reports + PostGIS POINT geometry)

All PostgreSQL ENUM types are created before table creation.
Migrations are idempotent via IF NOT EXISTS and CREATE TYPE IF NOT EXISTS patterns.
"""

from alembic import op
import sqlalchemy as sa
import geoalchemy2
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'auto_phase1'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable PostGIS extension (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # Create ENUM types (idempotent)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE magnitude_type_enum AS ENUM (
                'ml', 'mb', 'ms', 'mw', 'mww', 'mwr', 'mwb', 'mwc', 'md', 'mi', 'unknown'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE geographic_scope_enum AS ENUM ('india', 'regional', 'other');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE report_source_enum AS ENUM (
                'usgs', 'synthetic', 'reddit', 'citizen_api', 'unknown'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE damage_type_enum AS ENUM (
                'structural_crack', 'partial_collapse', 'complete_collapse',
                'facade_damage', 'debris', 'non_structural_damage', 'unknown'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE damage_severity_enum AS ENUM (
                'unknown', 'none', 'minor', 'moderate', 'severe', 'destroyed'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE verification_status_enum AS ENUM (
                'pending', 'verified', 'rejected', 'merged'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)

    # earthquake_events table
    op.create_table(
        'earthquake_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('event_id', sa.String(64), nullable=False, unique=True,
                  comment='USGS feature ID. Never fabricate.'),
        sa.Column('source', sa.String(32), nullable=False, server_default='usgs'),
        sa.Column('magnitude', sa.Float(), nullable=False),
        sa.Column('magnitude_type', sa.Text(), nullable=False,
                  server_default='unknown'),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('depth_km', sa.Float(), nullable=False),
        sa.Column('geometry',
                  geoalchemy2.types.Geometry(geometry_type='POINT', srid=4326),
                  nullable=False),
        sa.Column('place', sa.Text(), nullable=False,
                  comment='USGS place string, verbatim.'),
        sa.Column('event_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('geographic_scope', sa.Text(), nullable=False,
                  server_default='other'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
    )
    op.create_index('ix_earthquake_events_event_id', 'earthquake_events', ['event_id'])
    # PostGIS spatial index
    op.execute(
        "CREATE INDEX ix_earthquake_events_geom ON earthquake_events "
        "USING GIST (geometry)"
    )

    # reports table
    op.create_table(
        'reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('report_id', postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column('source', sa.Text(), nullable=False),
        sa.Column('source_record_id', sa.String(256), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('geometry',
                  geoalchemy2.types.Geometry(geometry_type='POINT', srid=4326),
                  nullable=False),
        sa.Column('location_text', sa.Text(), nullable=True),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('image_reference', sa.Text(), nullable=True),
        sa.Column('earthquake_event_id', sa.String(64), nullable=True),
        sa.Column('damage_type', sa.Text(), nullable=False, server_default='unknown'),
        sa.Column('severity', sa.Text(), nullable=False, server_default='unknown'),
        sa.Column('verification_status', sa.Text(), nullable=False,
                  server_default='pending'),
        sa.Column('trust_score', sa.Float(), nullable=True,
                  comment='None until Phase 4 trust-scoring. Never hardcode.'),
        sa.Column('duplicate_of', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_synthetic', sa.Boolean(), nullable=False,
                  comment='True = synthetic demo data. Never show as real.'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(
            ['earthquake_event_id'], ['earthquake_events.event_id'],
            ondelete='SET NULL',
        ),
    )
    op.create_index('ix_reports_report_id', 'reports', ['report_id'])
    op.create_index('ix_reports_earthquake_event_id', 'reports', ['earthquake_event_id'])
    op.create_index('ix_reports_verification_status', 'reports', ['verification_status'])
    # PostGIS spatial index
    op.execute(
        "CREATE INDEX ix_reports_geom ON reports USING GIST (geometry)"
    )


def downgrade() -> None:
    op.drop_table('reports')
    op.drop_table('earthquake_events')
    # Drop ENUM types
    for t in [
        'verification_status_enum', 'damage_severity_enum', 'damage_type_enum',
        'report_source_enum', 'geographic_scope_enum', 'magnitude_type_enum',
    ]:
        op.execute(f"DROP TYPE IF EXISTS {t}")
