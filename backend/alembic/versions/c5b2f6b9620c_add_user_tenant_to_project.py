"""add_user_tenant_to_project

Revision ID: c5b2f6b9620c
Revises: a678bbea4aaf
Create Date: 2026-04-09 22:56:02.643972

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5b2f6b9620c'
down_revision: Union[str, None] = 'a678bbea4aaf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tenants',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('plan', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_tenants_id'), 'tenants', ['id'], unique=False)

    op.create_table(
        'users',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_tenant_id'), 'users', ['tenant_id'], unique=False)

    # SQLite requires batch mode to alter existing tables
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tenant_id', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('owner_id', sa.String(), nullable=True))
        batch_op.create_index(batch_op.f('ix_projects_tenant_id'), ['tenant_id'], unique=False)
        batch_op.create_foreign_key('fk_projects_tenant_id', 'tenants', ['tenant_id'], ['id'])
        batch_op.create_foreign_key('fk_projects_owner_id', 'users', ['owner_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_constraint('fk_projects_owner_id', type_='foreignkey')
        batch_op.drop_constraint('fk_projects_tenant_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_projects_tenant_id'))
        batch_op.drop_column('owner_id')
        batch_op.drop_column('tenant_id')

    op.drop_index(op.f('ix_users_tenant_id'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_tenants_id'), table_name='tenants')
    op.drop_table('tenants')
