"""agregar presupuesto_inicial a campanas

Revision ID: d4e5f6a7b8c9
Revises: c8d75935ca55
Create Date: 2026-03-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd4e5f6a7b8c9'
down_revision = 'c8d75935ca55'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('campanas', schema=None) as batch_op:
        batch_op.add_column(sa.Column('presupuesto_inicial', sa.Numeric(14, 2), nullable=False, server_default='0'))


def downgrade():
    with op.batch_alter_table('campanas', schema=None) as batch_op:
        batch_op.drop_column('presupuesto_inicial')
