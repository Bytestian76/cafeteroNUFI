"""agregar trabajadores y jornales

Revision ID: f1a2b3c4d5e6
Revises: d4e5f6a7b8c9
Create Date: 2026-03-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f1a2b3c4d5e6'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('trabajadores',
        sa.Column('id',        sa.Integer(),     nullable=False),
        sa.Column('nombre',    sa.String(150),   nullable=False),
        sa.Column('documento', sa.String(20),    nullable=True),
        sa.Column('telefono',  sa.String(20),    nullable=True),
        sa.Column('activo',    sa.Boolean(),     nullable=False, server_default='1'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('jornales',
        sa.Column('id',                sa.Integer(),          nullable=False),
        sa.Column('trabajador_id',     sa.Integer(),          nullable=False),
        sa.Column('campana_id',        sa.Integer(),          nullable=False),
        sa.Column('fecha',             sa.Date(),             nullable=False),
        sa.Column('cantidad_jornales', sa.Numeric(6, 2),      nullable=False),
        sa.Column('valor_jornal',      sa.Numeric(10, 2),     nullable=False),
        sa.Column('total',             sa.Numeric(14, 2),     nullable=False),
        sa.Column('observacion',       sa.Text(),             nullable=True),
        sa.Column('usuario_id',        sa.Integer(),          nullable=False),
        sa.ForeignKeyConstraint(['trabajador_id'], ['trabajadores.id']),
        sa.ForeignKeyConstraint(['campana_id'],    ['campanas.id']),
        sa.ForeignKeyConstraint(['usuario_id'],    ['usuarios.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('jornales')
    op.drop_table('trabajadores')
