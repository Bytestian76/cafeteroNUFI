"""rename campanas to temporadas

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-03-25 00:00:00.000000

"""
from alembic import op

revision = 'a1b2c3d4e5f6'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    # MySQL actualiza automáticamente las FK que apuntan a la tabla renombrada
    op.rename_table('campanas', 'temporadas')


def downgrade():
    op.rename_table('temporadas', 'campanas')
