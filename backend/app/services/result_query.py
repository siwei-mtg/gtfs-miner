"""
result_query.py — Service layer for querying GTFS Miner result tables (Task 19).

Provides TABLE_REGISTRY mapping short table keys to SQLAlchemy model classes,
and query_table() which handles pagination, sorting, text search, and
(since Task 38A) per-column enum multi-select + numeric range filtering.
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


class ResultQueryError(ValueError):
    """Raised when caller-supplied query arguments refer to unknown columns
    or otherwise cannot be honored.  Callers translate this to HTTP 400."""


def _resolve_column(model: type, field: str):
    """Return the SQLAlchemy Column for `field`, or raise ResultQueryError.

    Internal columns (`id`, `project_id`) are refused so tenants cannot be
    tricked into filtering across foreign projects via the public API.
    """
    if field in _INTERNAL_COLS or field not in model.__table__.columns:
        raise ResultQueryError(f"Unknown field: {field}")
    return model.__table__.columns[field]


def _coerce_filter_values(col, values: list[str]) -> list:
    """Cast raw string query values to the column's Python type.

    SQLAlchemy types expose `python_type`; we catch conversion errors and
    re-raise them as ResultQueryError so the endpoint returns 400 instead
    of leaking a generic 500.
    """
    try:
        py_type = col.type.python_type
    except NotImplementedError:
        py_type = str
    coerced: list = []
    for raw in values:
        try:
            coerced.append(py_type(raw))
        except (ValueError, TypeError) as exc:
            raise ResultQueryError(
                f"Invalid value {raw!r} for {col.name}: {exc}"
            ) from exc
    return coerced


def query_table(
    db: Session,
    model: type,
    project_id: str,
    skip: int,
    limit: int,
    sort_by: str | None,
    sort_order: str,
    q: str | None,
    *,
    filter_field: str | None = None,
    filter_values: list[str] | None = None,
    range_field: str | None = None,
    range_min: float | None = None,
    range_max: float | None = None,
) -> dict:
    """Query a result table with pagination, sorting, text search, and
    optional column-level filters (Task 38A).

    Args:
        filter_field / filter_values:
            SQL `IN (...)` on an enum-like column.  Values are cast to the
            column's Python type (e.g. "3" → int(3) on a route_type column).
        range_field / range_min / range_max:
            Numeric range [min, max] inclusive.  Either bound may be omitted
            to apply only a lower or upper bound.

    Returns:
        {"total": int, "rows": list[dict], "columns": list[str]}
        columns and row dicts exclude internal fields (id, project_id).

    Raises:
        ResultQueryError: unknown column name or bad value coercion.  Callers
        should translate to HTTP 400.
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

    if filter_field is not None:
        col = _resolve_column(model, filter_field)
        if filter_values:  # empty list → no-op (return everything)
            coerced = _coerce_filter_values(col, filter_values)
            query = query.filter(col.in_(coerced))

    if range_field is not None:
        col = _resolve_column(model, range_field)
        if range_min is not None:
            query = query.filter(col >= range_min)
        if range_max is not None:
            query = query.filter(col <= range_max)

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
