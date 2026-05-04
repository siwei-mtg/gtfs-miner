"""
add_e1_indexes.py — One-shot migration that adds the composite indexes used
by the E1 pie-chart map endpoint to an existing miner_app.db.

Why a script instead of relying on Base.metadata.create_all()?
SQLAlchemy's create_all is "create if missing" but only at the **table** level.
On an existing SQLite file the result tables already exist, so newly declared
``Index`` rows in result_models.py are silently ignored. This script issues
``CREATE INDEX IF NOT EXISTS`` directly so the optimisation lands on legacy
DBs without touching data.

Usage (from project root):
    backend/venv/Scripts/python.exe -m backend.scripts.add_e1_indexes
or:
    cd backend && venv/Scripts/python.exe -m scripts.add_e1_indexes
"""
from __future__ import annotations

import sys

from app.db.database import engine
from sqlalchemy import text


# Keep this list in sync with the ``__table_args__`` declarations in
# backend/app/db/result_models.py.
INDEX_DDL: list[str] = [
    "CREATE INDEX IF NOT EXISTS ix_e1_project_jour "
    "ON result_e1_passage_ag (project_id, type_jour)",
    "CREATE INDEX IF NOT EXISTS ix_c2_project_ligne_service "
    "ON result_c2_itineraire (project_id, id_ligne_num, id_service_num)",
    "CREATE INDEX IF NOT EXISTS ix_c2_project_ag "
    "ON result_c2_itineraire (project_id, id_ag_num)",
    "CREATE INDEX IF NOT EXISTS ix_d2_project_ligne_service_jour "
    "ON result_d2_service_jourtype (project_id, id_ligne_num, id_service_num, Type_Jour)",
    "CREATE INDEX IF NOT EXISTS ix_b1_project_ligne "
    "ON result_b1_lignes (project_id, id_ligne_num)",
]


def main() -> int:
    print(f"Adding E1 pie-chart indexes to: {engine.url}")
    with engine.begin() as conn:
        for ddl in INDEX_DDL:
            print(f"  · {ddl}")
            conn.execute(text(ddl))
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
