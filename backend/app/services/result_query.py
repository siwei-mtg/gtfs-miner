"""
result_query.py — Service layer for querying GTFS Miner result tables (Task 19).

Provides TABLE_REGISTRY mapping short table keys to SQLAlchemy model classes,
and query_table() which handles pagination, sorting, and text search.
"""
from sqlalchemy import String, asc, desc, or_
from sqlalchemy.orm import Session

from ..db.result_models import (
    ResultA1ArretGenerique,
    ResultA2ArretPhysique,
    ResultB1Ligne,
    ResultB2SousLigne,
    ResultC1Course,
    ResultC2Itineraire,
    ResultC3ItineraireArc,
    ResultD1ServiceDate,
    ResultD2ServiceJourtype,
    ResultE1PassageAG,
    ResultE4PassageArc,
    ResultF1CourseLigne,
    ResultF2CaractSL,
    ResultF3KCCLigne,
    ResultF4KCCSL,
)

TABLE_REGISTRY: dict[str, type] = {
    "a1": ResultA1ArretGenerique,
    "a2": ResultA2ArretPhysique,
    "b1": ResultB1Ligne,
    "b2": ResultB2SousLigne,
    "c1": ResultC1Course,
    "c2": ResultC2Itineraire,
    "c3": ResultC3ItineraireArc,
    "d1": ResultD1ServiceDate,
    "d2": ResultD2ServiceJourtype,
    "e1": ResultE1PassageAG,
    "e4": ResultE4PassageArc,
    "f1": ResultF1CourseLigne,
    "f2": ResultF2CaractSL,
    "f3": ResultF3KCCLigne,
    "f4": ResultF4KCCSL,
}

_INTERNAL_COLS = {"id", "project_id"}


def query_table(
    db: Session,
    model: type,
    project_id: str,
    skip: int,
    limit: int,
    sort_by: str | None,
    sort_order: str,
    q: str | None,
) -> dict:
    """Query a result table with pagination, sorting, and text search.

    Returns:
        {"total": int, "rows": list[dict], "columns": list[str]}
        columns and row dicts exclude internal fields (id, project_id).
    """
    limit = min(limit, 200)

    query = db.query(model).filter(model.project_id == project_id)

    if q:
        str_cols = [
            col for col in model.__table__.columns
            if isinstance(col.type, String) and col.name not in _INTERNAL_COLS
        ]
        if str_cols:
            query = query.filter(
                or_(*[col.like(f"%{q}%") for col in str_cols])
            )

    if sort_by and sort_by in model.__table__.columns:
        col = model.__table__.columns[sort_by]
        query = query.order_by(desc(col) if sort_order == "desc" else asc(col))

    total: int = query.count()
    rows_orm = query.offset(skip).limit(limit).all()

    columns = [
        col.name
        for col in model.__table__.columns
        if col.name not in _INTERNAL_COLS
    ]
    rows = [
        {col: getattr(row, col) for col in columns}
        for row in rows_orm
    ]

    return {"total": total, "rows": rows, "columns": columns}
