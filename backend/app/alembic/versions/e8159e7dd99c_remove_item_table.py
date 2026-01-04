"""remove item table

Revision ID: e8159e7dd99c
Revises: 266850f94457
Create Date: 2026-01-04 22:10:32.264883

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'e8159e7dd99c'
down_revision = '266850f94457'
branch_labels = None
depends_on = None


def upgrade():
    # Drop the item table
    op.drop_table('item')


def downgrade():
    # Recreate the item table with the final structure (as of migration 1a31ce608336)
    op.create_table(
        'item',
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('owner_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
