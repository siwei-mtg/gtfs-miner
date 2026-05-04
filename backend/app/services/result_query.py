"""
result_query.py — Service layer for querying GTFS Miner result tables (Task 19).

Provides TABLE_REGISTRY mapping short table keys to SQLAlchemy model classes,
and query_table() which handles pagination, sorting, text search, and
(since Task 38A) per-column enum multi-select + numeric range filtering.

Task 38B extends this with a generic ``filters`` list shape that lets the
frontend Excel-style header popovers combine arbitrary per-column filters
(``in`` / ``range`` / ``contains``) AND-ed together, plus column metadata
(type + total_distinct) for layout auto-detection.
"""
from typing import Any, Literal, TypedDict

from sqlalchemy import Float, Integer, Numeric, String, asc, desc, distinct, func, or_
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

# Heuristic threshold: columns with ≤ this many distinct values are exposed as
# 'enum' (checklist) in the column-filter popover.  Beyond this they switch to
# 'text' (contains + lazy-loaded distinct list).  Numeric columns short-circuit
# the count and are always 'numeric'.
ENUM_CARDINALITY_LIMIT = 50


# ── Public filter shape (Task 38B) ─────────────────────────────────────────

FilterOp = Literal["in", "range", "contains"]


class ColumnFilter(TypedDict, total=False):
    """One per-column filter clause emitted by the frontend popover.

    Exactly one operator-specific field is meaningful per ``op``:
      * ``in``       → ``values`` (list of raw strings, coerced to col type)
      * ``range``    → ``min`` / ``max`` (either may be None for open-ended)
      * ``contains`` → ``term`` (case-insensitive, % and _ escaped)
    """

    column: str
    op: FilterOp
    values: list[str]
    min: float | None
    max: float | None
    term: str


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


def _coerce_range_bound(col, raw: float | None) -> Any:
    """Cast a numeric range bound to the column's Python type, or pass-through
    None.  Reuses _coerce_filter_values' error semantics.

    Integer columns are special-cased: the URL parser parses range bounds as
    ``float`` (so ``range:1:2`` yields ``1.0``/``2.0``), and routing that
    through ``_coerce_filter_values`` would call ``int("1.0")`` which raises
    ValueError.  We round-trip through ``int(raw)`` instead.
    """
    if raw is None:
        return None
    if isinstance(col.type, Integer):
        return int(raw)
    return _coerce_filter_values(col, [str(raw)])[0]


def _escape_like(term: str) -> str:
    """Escape SQL LIKE wildcards (%, _) and the escape char (\\) itself so a
    user typing ``50%`` does not match every row.  Paired with ``escape='\\'``
    on the SQLAlchemy ``.like()`` call site."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _is_numeric_column(col) -> bool:
    """Cheap type check used by both filter coercion (range/in on int/float)
    and column-metadata layout selection."""
    return isinstance(col.type, (Integer, Float, Numeric))


def _apply_column_filter(query, col, flt: ColumnFilter):
    """Add one ColumnFilter clause to the query.  Returns the new query."""
    op = flt.get("op")
    if op == "in":
        raw_values = flt.get("values") or []
        if not raw_values:  # empty → no-op (matches legacy behavior)
            return query
        coerced = _coerce_filter_values(col, raw_values)
        return query.filter(col.in_(coerced))

    if op == "range":
        lo = _coerce_range_bound(col, flt.get("min"))
        hi = _coerce_range_bound(col, flt.get("max"))
        if lo is not None:
            query = query.filter(col >= lo)
        if hi is not None:
            query = query.filter(col <= hi)
        return query

    if op == "contains":
        term = flt.get("term") or ""
        if not term:
            return query
        # case-insensitive, Postgres + SQLite friendly (no ILIKE on SQLite).
        pattern = f"%{_escape_like(term).lower()}%"
        return query.filter(func.lower(col).like(pattern, escape="\\"))

    raise ResultQueryError(f"Unknown filter op: {op!r}")


def compute_column_meta(
    db: Session, model: type, project_id: str
) -> dict[str, dict[str, Any]]:
    """Return ``{col: {"type": "enum"|"numeric"|"text", "total_distinct": int}}``.

    Numeric columns short-circuit (always 'numeric').  For others we run a
    bounded ``SELECT COUNT(*) FROM (SELECT DISTINCT col … LIMIT 51)`` so the
    cost is O(distinct), capped: low-cardinality enums stay cheap, large text
    columns stop counting at 51.  ``total_distinct`` is the real count when
    ≤ 50, otherwise 51 as a sentinel meaning "more than the enum threshold".
    """
    meta: dict[str, dict[str, Any]] = {}
    for col in model.__table__.columns:
        if col.name in _INTERNAL_COLS:
            continue
        if _is_numeric_column(col):
            meta[col.name] = {"type": "numeric", "total_distinct": -1}
            continue
        sub = (
            db.query(distinct(col))
            .filter(model.project_id == project_id)
            .limit(ENUM_CARDINALITY_LIMIT + 1)
            .subquery()
        )
        n = db.query(func.count()).select_from(sub).scalar() or 0
        meta[col.name] = {
            "type": "enum" if n <= ENUM_CARDINALITY_LIMIT else "text",
            "total_distinct": int(n),
        }
    return meta


class ResolveResult(TypedDict):
    ligne_ids: list[int]
    route_types: list[str]
    ag_ids: list[int]


def resolve_table_filters(
    db: Session,
    model: type,
    project_id: str,
    filters: list[ColumnFilter] | None,
) -> ResolveResult:
    """Translate per-row column filters into the canonical IDs other dashboard
    panes (map, KPI ribbon, charts, sibling tables) consume.

    Strategy (bidirectional, single network round-trip):

    1. Apply ``filters`` to the source ``model`` once.
    2. From the filtered source query, project whichever of
       ``id_ligne_num`` / ``id_ag_num`` the source actually carries.  These
       are the "primary" canonicals — they're definitive for this filter.
    3. Cross-derive the missing canonical via ``ResultC2Itineraire`` (the
       only model that has BOTH columns):
         - source has lines but not stops → distinct C_2.id_ag_num served by
           those lines.
         - source has stops but not lines → distinct C_2.id_ligne_num passing
           through those stops.
       This lets a filter on B_1/B_2 (lines) propagate to A_1/A_2/E_1 (stops),
       AND vice-versa.
    4. Resolve ``route_types`` from the FINAL set of ligne_ids via B_1.  This
       gives a coherent route-type set even when the source (e.g. B_2) doesn't
       carry route_type itself.

    Returns empty lists for canonicals the source has no path to (e.g. D_1
    has neither id_ligne_num nor id_ag_num — purely calendar data).
    """
    query = db.query(model).filter(model.project_id == project_id)
    for flt in filters or []:
        col = _resolve_column(model, flt["column"])
        query = _apply_column_filter(query, col, flt)

    cols = model.__table__.columns
    src_ligne_ids: list[int] | None = None
    src_ag_ids: list[int] | None = None

    if "id_ligne_num" in cols:
        rows = (
            query.with_entities(distinct(cols["id_ligne_num"]))
            .filter(cols["id_ligne_num"].isnot(None))
            .all()
        )
        src_ligne_ids = [int(r[0]) for r in rows]

    if "id_ag_num" in cols:
        rows = (
            query.with_entities(distinct(cols["id_ag_num"]))
            .filter(cols["id_ag_num"].isnot(None))
            .all()
        )
        src_ag_ids = [int(r[0]) for r in rows]

    final_ligne_ids: set[int] = set(src_ligne_ids or [])
    final_ag_ids: set[int] = set(src_ag_ids or [])

    # Cross-derive via C_2 (id_ligne_num × id_ag_num bridge).  Only one
    # direction fires per call — we never want to "expand" both back into
    # each other (that would just yield the source set anyway).
    if src_ligne_ids is not None and src_ag_ids is None and src_ligne_ids:
        rows = (
            db.query(distinct(ResultC2Itineraire.id_ag_num))
            .filter(ResultC2Itineraire.project_id == project_id)
            .filter(ResultC2Itineraire.id_ligne_num.in_(src_ligne_ids))
            .filter(ResultC2Itineraire.id_ag_num.isnot(None))
            .all()
        )
        final_ag_ids = {int(r[0]) for r in rows}
    elif src_ag_ids is not None and src_ligne_ids is None and src_ag_ids:
        rows = (
            db.query(distinct(ResultC2Itineraire.id_ligne_num))
            .filter(ResultC2Itineraire.project_id == project_id)
            .filter(ResultC2Itineraire.id_ag_num.in_(src_ag_ids))
            .filter(ResultC2Itineraire.id_ligne_num.isnot(None))
            .all()
        )
        final_ligne_ids = {int(r[0]) for r in rows}

    # Route types: prefer the direct source column if present (B_1 case);
    # otherwise derive from the final ligne set via B_1.  Either way the
    # output reflects the FILTERED row set, not the project total.
    route_types: list[str] = []
    if "route_type" in cols:
        rows = (
            query.with_entities(distinct(cols["route_type"]))
            .filter(cols["route_type"].isnot(None))
            .all()
        )
        route_types = sorted(str(r[0]) for r in rows)
    elif final_ligne_ids:
        rows = (
            db.query(distinct(ResultB1Ligne.route_type))
            .filter(ResultB1Ligne.project_id == project_id)
            .filter(ResultB1Ligne.id_ligne_num.in_(final_ligne_ids))
            .filter(ResultB1Ligne.route_type.isnot(None))
            .all()
        )
        route_types = sorted(str(r[0]) for r in rows)

    return {
        "ligne_ids": sorted(final_ligne_ids),
        "route_types": route_types,
        "ag_ids": sorted(final_ag_ids),
    }


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
    filters: list[ColumnFilter] | None = None,
    include_column_meta: bool = False,
) -> dict:
    """Query a result table with pagination, sorting, text search, and
    optional column-level filters.

    Args:
        filter_field / filter_values (legacy, Task 38A):
            SQL `IN (...)` on an enum-like column.  Values are cast to the
            column's Python type (e.g. "3" → int(3) on a route_type column).
        range_field / range_min / range_max (legacy, Task 38A):
            Numeric range [min, max] inclusive.  Either bound may be omitted
            to apply only a lower or upper bound.
        filters (Task 38B):
            Generic per-column filter list (``in`` / ``range`` / ``contains``)
            AND-ed with each other and with the legacy filters.  Empty / None
            is a no-op.
        include_column_meta:
            When True, ``column_meta`` is added to the response.  The caller
            (typically the router) only needs this on first page load; it is
            slightly costly (one bounded distinct query per non-numeric col).

    Returns:
        {"total": int, "rows": list[dict], "columns": list[str],
         "column_meta"?: dict[str, {"type": str, "total_distinct": int}]}
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

    for flt in filters or []:
        col = _resolve_column(model, flt["column"])
        query = _apply_column_filter(query, col, flt)

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

    response: dict[str, Any] = {"total": total, "rows": rows, "columns": columns}
    if include_column_meta:
        response["column_meta"] = compute_column_meta(db, model, project_id)
    return response
