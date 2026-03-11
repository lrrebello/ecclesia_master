"""Add devotional theme fields to ChurchTheme

Revision ID: e18eaa16e127
Revises: 4ee5cd28887c
Create Date: 2026-03-11 08:22:03.767187

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e18eaa16e127'
down_revision = '4ee5cd28887c'
branch_labels = None
depends_on = None


def upgrade():
    # Alterar campos de overlay de String(7) para Text
    op.alter_column('church_themes', 'devotional_overlay_light',
                    existing_type=sa.String(7),
                    type_=sa.Text(),
                    existing_nullable=True)
    op.alter_column('church_themes', 'devotional_overlay_dark',
                    existing_type=sa.String(7),
                    type_=sa.Text(),
                    existing_nullable=True)

def downgrade():
    # Voltar para String(7) se precisar reverter
    op.alter_column('church_themes', 'devotional_overlay_light',
                    existing_type=sa.Text(),
                    type_=sa.String(7),
                    existing_nullable=True)
    op.alter_column('church_themes', 'devotional_overlay_dark',
                    existing_type=sa.Text(),
                    type_=sa.String(7),
                    existing_nullable=True)