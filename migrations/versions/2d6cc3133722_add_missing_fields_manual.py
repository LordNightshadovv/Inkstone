"""add missing fields manual

Revision ID: 2d6cc3133722
Revises: 54d1f05b3f53
Create Date: 2026-02-19 13:40:39.767455

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2d6cc3133722'
down_revision = '54d1f05b3f53'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('post', schema=None) as batch_op:
        # batch_op.add_column(sa.Column('is_initiative', sa.Boolean(), server_default='0', nullable=True))
        # batch_op.add_column(sa.Column('frame_color', sa.String(length=7), server_default='#2563eb', nullable=True))
        batch_op.add_column(sa.Column('translated_by', sa.String(length=200), nullable=True))

    with op.batch_alter_table('theme', schema=None) as batch_op:
        # batch_op.add_column(sa.Column('is_initiative', sa.Boolean(), server_default='0', nullable=True))
        pass


def downgrade():
    with op.batch_alter_table('theme', schema=None) as batch_op:
        batch_op.drop_column('is_initiative')

    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.drop_column('translated_by')
        batch_op.drop_column('frame_color')
        batch_op.drop_column('is_initiative')
