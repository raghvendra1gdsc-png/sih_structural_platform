"""add_clip_classification_fields

Revision ID: 7a82b9e14c33
Revises: auto_phase1
Create Date: 2026-09-04

Adds CLIP zero-shot classification audit fields to the reports table:
- classification_score: Float (top softmax heuristic confidence score [0, 1])
- classification_model: String(128) (model architecture identifier)
- classified_at: DateTime(timezone=True) (UTC classification timestamp)
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '7a82b9e14c33'
down_revision = 'auto_phase1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'reports',
        sa.Column(
            'classification_score',
            sa.Float(),
            nullable=True,
            comment='CLIP zero-shot top softmax score [0, 1]. Heuristic score, not probability.',
        ),
    )
    op.add_column(
        'reports',
        sa.Column(
            'classification_model',
            sa.String(length=128),
            nullable=True,
            comment='Pretrained CLIP model identifier used for classification.',
        ),
    )
    op.add_column(
        'reports',
        sa.Column(
            'classified_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='UTC timestamp when classified by CLIP.',
        ),
    )


def downgrade() -> None:
    op.drop_column('reports', 'classified_at')
    op.drop_column('reports', 'classification_model')
    op.drop_column('reports', 'classification_score')
