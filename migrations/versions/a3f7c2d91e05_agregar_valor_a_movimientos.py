"""agregar valor a movimientos

Revision ID: a3f7c2d91e05
Revises: 158e15b3392f
Create Date: 2026-03-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3f7c2d91e05'
down_revision = '1290c49de14f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('movimientos', schema=None) as batch_op:
        batch_op.add_column(sa.Column('valor', sa.Numeric(14, 2), nullable=False, server_default='0'))


def downgrade():
    with op.batch_alter_table('movimientos', schema=None) as batch_op:
        batch_op.drop_column('valor')
