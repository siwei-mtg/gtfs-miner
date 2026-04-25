"""add_progress_events_table

Revision ID: 05aaeef5dcad
Revises: 65dc0a60ef68
Create Date: 2026-04-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '05aaeef5dcad'
down_revision: Union[str, None] = '65dc0a60ef68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'progress_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('seq', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('step', sa.String(), nullable=False),
        sa.Column('time_elapsed', sa.Float(), nullable=False),
        sa.Column('error', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_progress_events_project_id'),
        'progress_events', ['project_id'], unique=False,
    )
    op.create_index(
        op.f('ix_progress_events_created_at'),
        'progress_events', ['created_at'], unique=False,
    )
    op.create_index(
        'ix_progress_events_project_seq',
        'progress_events', ['project_id', 'seq'], unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_progress_events_project_seq', table_name='progress_events')
    op.drop_index(op.f('ix_progress_events_created_at'), table_name='progress_events')
    op.drop_index(op.f('ix_progress_events_project_id'), table_name='progress_events')
    op.drop_table('progress_events')
