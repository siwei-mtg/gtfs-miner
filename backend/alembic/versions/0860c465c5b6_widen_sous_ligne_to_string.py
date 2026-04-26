"""widen_sous_ligne_to_string

Six result tables declared `sous_ligne` as INTEGER, but the column actually
stores a composite identifier string of the form
"<id_ligne_num>_<direction>_<id_ag_debut>_<id_ag_terminus>_<nb_arrets>_<dist>"
(e.g. "1_0_10127_10465_31_12736.0"). SQLite's dynamic typing accepted the
mismatch silently; PostgreSQL rejected the first INSERT with
NumericValueOutOfRange and the worker crashed at the persist-results step.

Convert all six columns to VARCHAR. Tables are still empty in production
(every previous run failed before writing) so the cast is loss-free.

Revision ID: 0860c465c5b6
Revises: 72dc08b741eb
Create Date: 2026-04-26 13:53:11.035391

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0860c465c5b6'
down_revision: Union[str, None] = '72dc08b741eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLES_WITH_SOUS_LIGNE = (
    "result_b2_sous_lignes",
    "result_c1_courses",
    "result_c2_itineraire",
    "result_c3_itineraire_arc",
    "result_f2_caract_sous_lignes",
    "result_f4_kcc_sous_lignes",
)


def upgrade() -> None:
    for table in _TABLES_WITH_SOUS_LIGNE:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                "sous_ligne",
                existing_type=sa.Integer(),
                type_=sa.String(),
                existing_nullable=True,
                postgresql_using="sous_ligne::text",
            )


def downgrade() -> None:
    for table in _TABLES_WITH_SOUS_LIGNE:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                "sous_ligne",
                existing_type=sa.String(),
                type_=sa.Integer(),
                existing_nullable=True,
                postgresql_using="sous_ligne::integer",
            )
