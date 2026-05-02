"""
table_distinct.py — Distinct-values service for the per-column filter popover.

Returns the distinct values of a single column on a single result table
(scoped by project_id), with optional case-insensitive substring search and
a hard limit so a 30k-row text column cannot OOM the wire.

This backs the ``GET /projects/{pid}/tables/{name}/columns/{col}/distinct``
endpoint that powers the Excel-style header filter dropdown.  Response shape::

    {
      "values":         [{"value": "Bus", "count": 142}, ...],   # ORDER BY count DESC, value
      "total_distinct": int,                                     # ignoring `q`
      "truncated":      bool,                                    # len(values) was capped
    }
"""
from typing import Any

from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from .result_query import _escape_like, _resolve_column

DEFAULT_LIMIT = 200
HARD_MAX_LIMIT = 1000


def list_distinct_values(
    db: Session,
    model: type,
    project_id: str,
    column: str,
    *,
    q: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    """List distinct values + occurrence counts for ``column`` in ``model``.

    Args:
        column:  must be a column on ``model`` and not internal (id / project_id).
                 Validation delegated to ``_resolve_column``.
        q:       case-insensitive substring search; ``%``/``_`` are escaped so
                 the user can't smuggle in SQL wildcards.  Whitespace-only is
                 treated as no filter.
        limit:   hard-capped at HARD_MAX_LIMIT (1000) to bound payload size.
    """
    col = _resolve_column(model, column)
    capped_limit = max(1, min(limit, HARD_MAX_LIMIT))

    base = db.query(model).filter(model.project_id == project_id)
    if q and q.strip():
        pattern = f"%{_escape_like(q.strip()).lower()}%"
        base = base.filter(func.lower(col).like(pattern, escape="\\"))

    rows = (
        base.with_entities(col.label("value"), func.count().label("cnt"))
        .group_by(col)
        .order_by(func.count().desc(), col.asc())
        .limit(capped_limit + 1)
        .all()
    )

    truncated = len(rows) > capped_limit
    values = [
        {"value": row.value, "count": int(row.cnt)}
        for row in rows[:capped_limit]
    ]

    # ``total_distinct`` is the unfiltered cardinality, used by the frontend to
    # auto-pick the popover layout.  Cheap: SELECT COUNT(DISTINCT col).
    total_distinct = (
        db.query(func.count(distinct(col)))
        .filter(model.project_id == project_id)
        .scalar()
    ) or 0

    return {
        "values": values,
        "total_distinct": int(total_distinct),
        "truncated": truncated,
    }
