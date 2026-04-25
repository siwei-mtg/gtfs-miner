"""add_reseau_validite_to_project

Revision ID: 72dc08b741eb
Revises: 05aaeef5dcad
Create Date: 2026-04-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "72dc08b741eb"
down_revision: Union[str, None] = "05aaeef5dcad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("reseau", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("validite_debut", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("validite_fin", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_column("validite_fin")
        batch_op.drop_column("validite_debut")
        batch_op.drop_column("reseau")
