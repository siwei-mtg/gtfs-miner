import re
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List
import io
import logging
import shutil
import asyncio
import zipfile
from pathlib import Path

from ...db.database import get_db
from ...db.models import Project, ProgressEvent, User
from ...db.result_models import ResultA1ArretGenerique, ResultE1PassageAG
from ...schemas.project import ProjectCreate, ProjectResponse
from ...services.worker import run_project_task_sync
from ...services import storage
from ...services.result_query import (
    TABLE_REGISTRY,
    ColumnFilter,
    ResultQueryError,
    query_table,
    resolve_table_filters,
)
from ...services.table_distinct import list_distinct_values
from ...services.map_builder import build_passage_ag_geojson, build_passage_arc_geojson, export_geopackage
from ...services.charts_builder import (
    build_courses_by_hour,
    build_courses_by_jour_type,
    build_kpis,
    build_peak_offpeak,
)
from ...services.gtfs_core.calendar_provider import TYPE_JOUR_VAC_LABELS
from ...core.config import settings, TEMP_DIR, PROJECT_DIR
from ...api.deps import get_current_active_user

# Reverse {label: value} → {value: label} for jour_type display.
_JOUR_TYPE_LABEL_BY_VALUE: dict[int, str] = {v: k for k, v in TYPE_JOUR_VAC_LABELS.items()}

router = APIRouter()

@router.post("/", response_model=ProjectResponse, status_code=201)
def create_project(
    project_in: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    创建一个新的项目（包含基础参数配置）
    """
    project = Project(
        parameters=project_in.model_dump(),
        tenant_id=current_user.tenant_id,
        owner_id=current_user.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

@router.get("/", response_model=List[ProjectResponse])
def list_projects(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    获取当前租户的项目历史记录
    """
    projects = (
        db.query(Project)
        .filter(Project.tenant_id == current_user.tenant_id)
        .order_by(Project.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return projects

@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    查询特定项目状态
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.tenant_id == current_user.tenant_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _purge_project_files(tenant_id: str | None, project_id: str) -> None:
    """Best-effort cleanup of on-disk artefacts for a deleted project.

    Missing paths are treated as normal; individual failures are logged but
    do not raise so a partial filesystem cleanup never rolls back the DB
    delete that has already committed.
    """
    log = logging.getLogger(__name__)
    if tenant_id:
        output_dir = PROJECT_DIR / tenant_id / project_id
        if output_dir.exists():
            try:
                shutil.rmtree(output_dir)
            except OSError as exc:
                log.warning("Failed to remove %s: %s", output_dir, exc)
    for leftover in TEMP_DIR.glob(f"{project_id}_*"):
        try:
            leftover.unlink(missing_ok=True)
        except OSError as exc:
            log.warning("Failed to remove %s: %s", leftover, exc)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    永久删除项目及其所有数据：

    - 15 张结果表的行（FK 无 CASCADE，必须显式删除）
    - progress_events 行（SQLite 默认不强制 FK，显式删除以确保跨数据库一致）
    - Project 行本身
    - ``PROJECT_DIR/<tenant_id>/<project_id>/`` 下的 output 目录
    - ``TEMP_DIR/<project_id>_*`` 下的残留 zip
    - 仍订阅该 project_id 的活跃 WebSocket

    正在处理中的项目禁止删除（返回 409），避免 worker 写入已删除的 project_id。
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.tenant_id == current_user.tenant_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.status == "processing":
        raise HTTPException(
            status_code=409,
            detail="Cannot delete a project while it is processing.",
        )

    tenant_id = project.tenant_id

    for model_cls in TABLE_REGISTRY.values():
        db.query(model_cls).filter(model_cls.project_id == project_id).delete(
            synchronize_session=False
        )
    db.query(ProgressEvent).filter(
        ProgressEvent.project_id == project_id
    ).delete(synchronize_session=False)
    db.delete(project)
    db.commit()

    _purge_project_files(tenant_id, project_id)

    from ..websockets.progress import manager
    await manager.close_project(project_id)
    return None

@router.post("/{project_id}/upload")
async def upload_gtfs(
    project_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    上传 GTFS 包并触发后台处理流程
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.tenant_id == current_user.tenant_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only ZIP files are supported")

    project.status = "uploading"
    db.commit()

    # Hand the upload off to shared storage so the Worker container can
    # fetch it (the API and Worker each have their own filesystem on
    # Zeabur). With R2 configured we stream straight to the bucket; in
    # local single-process dev we fall back to the on-disk TEMP_DIR.
    if settings.use_r2:
        zip_arg = f"{current_user.tenant_id}/projects/{project_id}/upload/{file.filename}"
        storage.upload_fileobj(file.file, zip_arg)
    else:
        temp_zip_path = TEMP_DIR / f"{project_id}_{file.filename}"
        with temp_zip_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        zip_arg = str(temp_zip_path)

    project.status = "pending"
    db.commit()

    if settings.REDIS_URL:
        # Celery mode: dispatch to worker queue
        from ...services.worker import process_project_task
        process_project_task.delay(project_id, zip_arg, project.parameters)
    else:
        # BackgroundTasks fallback (dev/test — no Redis required)
        loop = asyncio.get_running_loop()
        background_tasks.add_task(
            run_project_task_sync,
            project_id=project_id,
            zip_path=zip_arg,
            parameters=project.parameters,
            loop=loop,
        )

    return {"msg": "Upload successful, processing started.", "project_id": project_id}

# ── Task 38B: per-column filter parser ──────────────────────────────────────

# Matches the bracketed query-param syntax ``filter[<column>]=…`` that FastAPI
# does not parse natively.  Names are kept loose; column whitelisting happens
# downstream in result_query._resolve_column so unknown columns return 400.
_FILTER_KEY_RE = re.compile(r"^filter\[([^\]]+)\]$")

_LEGACY_FILTER_LOG = logging.getLogger(__name__)


def _parse_column_filters(query_params) -> list[ColumnFilter]:
    """Walk the request's query string and turn every ``filter[col]=op:val``
    into a :class:`ColumnFilter`.

    Encoded value formats (everything after the first ``:``):
      * ``in:a,b,c``         → enum multi-select
      * ``range:<lo>:<hi>``  → numeric range (either bound may be empty)
      * ``contains:<term>``  → case-insensitive substring search

    Unknown ops raise HTTP 422 right here so callers don't reach the service
    with an obviously malformed clause.  Empty / whitespace-only values are
    silently dropped (treated as 'no filter on this column').
    """
    out: list[ColumnFilter] = []
    for key, raw_value in query_params.multi_items():
        match = _FILTER_KEY_RE.match(key)
        if not match:
            continue
        column = match.group(1)
        if not raw_value or not raw_value.strip():
            continue
        if ":" not in raw_value:
            raise HTTPException(
                status_code=422,
                detail=f"filter[{column}] missing op:value separator",
            )
        op, _, payload = raw_value.partition(":")
        op = op.strip()
        if op == "in":
            values = [v for v in payload.split(",") if v != ""]
            if not values:
                continue
            out.append({"column": column, "op": "in", "values": values})
        elif op == "range":
            lo_str, _, hi_str = payload.partition(":")
            lo = float(lo_str) if lo_str.strip() else None
            hi = float(hi_str) if hi_str.strip() else None
            if lo is None and hi is None:
                continue
            out.append({"column": column, "op": "range", "min": lo, "max": hi})
        elif op == "contains":
            term = payload
            if not term.strip():
                continue
            out.append({"column": column, "op": "contains", "term": term})
        else:
            raise HTTPException(
                status_code=422,
                detail=f"filter[{column}] unknown op {op!r}",
            )
    return out


@router.get("/{project_id}/tables/{table_name}")
def get_table_data(
    project_id: str,
    table_name: str,
    request: Request,
    skip: int = 0,
    limit: int = 50,
    sort_by: str | None = None,
    sort_order: str = "asc",
    q: str | None = None,
    filter_field: str | None = None,
    filter_values: str | None = None,
    range_field: str | None = None,
    range_min: float | None = None,
    range_max: float | None = None,
    column_meta: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    获取项目处理完成后的特定 CSV 表格的分页数据。

    返回：{"total": int, "rows": list[dict], "columns": list[str],
            "column_meta"?: dict}

    Task 38A (legacy) — single-column filtering:
      - filter_field + filter_values (comma-separated): SQL IN (...)
      - range_field + range_min / range_max: numeric [min, max] inclusive

    Task 38B — generic per-column filters (Excel-style header popovers):
      - filter[<col>]=in:v1,v2,v3        → SQL IN (...)
      - filter[<col>]=range:<min>:<max>  → numeric [min, max] inclusive
      - filter[<col>]=contains:<term>    → case-insensitive substring (LIKE)

    Multiple ``filter[…]`` params combine with AND.  Legacy and new filters
    can coexist (also AND-ed) while the frontend migrates.

    ``column_meta=true`` adds a per-column type+cardinality map used by the
    frontend to pick the popover layout (enum / numeric / text).
    """
    if table_name not in TABLE_REGISTRY:
        raise HTTPException(status_code=404, detail="Table not found")

    project = db.query(Project).filter(
        Project.id == project_id,
        Project.tenant_id == current_user.tenant_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.status != "completed":
        raise HTTPException(status_code=400, detail="Project data not ready")

    values_list = filter_values.split(",") if filter_values else None
    if filter_field or range_field:
        _LEGACY_FILTER_LOG.warning(
            "legacy filter params used on table=%s; please migrate to filter[col]=…",
            table_name,
        )
    column_filters = _parse_column_filters(request.query_params)

    try:
        return query_table(
            db, TABLE_REGISTRY[table_name], project_id,
            skip, limit, sort_by, sort_order, q,
            filter_field=filter_field,
            filter_values=values_list,
            range_field=range_field,
            range_min=range_min,
            range_max=range_max,
            filters=column_filters,
            include_column_meta=column_meta,
        )
    except ResultQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/{project_id}/tables/{table_name}/columns/{column}/distinct",
)
def get_table_column_distinct(
    project_id: str,
    table_name: str,
    column: str,
    q: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List distinct values of one column for the Excel-style filter popover.

    Returns ``{"values": [{value, count}], "total_distinct": int, "truncated": bool}``.
    See :func:`app.services.table_distinct.list_distinct_values` for full
    semantics (q escaping, hard caps).
    """
    if table_name not in TABLE_REGISTRY:
        raise HTTPException(status_code=404, detail="Table not found")

    project = db.query(Project).filter(
        Project.id == project_id,
        Project.tenant_id == current_user.tenant_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.status != "completed":
        raise HTTPException(status_code=400, detail="Project data not ready")

    try:
        return list_distinct_values(
            db, TABLE_REGISTRY[table_name], project_id, column, q=q, limit=limit
        )
    except ResultQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.get("/{project_id}/tables/{table_name}/resolve")
def resolve_table(
    project_id: str,
    table_name: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Translate per-row filters on a result table into canonical IDs the rest
    of the dashboard understands.

    Same filter syntax as ``GET /tables/{name}`` (``filter[col]=op:value``).
    Returns ``{"ligne_ids": [...], "route_types": [...]}`` — each list is empty
    if the source table doesn't have the corresponding column.

    Used by the dashboard popup to propagate non-mapped column filters
    (e.g. ``route_long_name``) onto the map / KPI panes via SET_LIGNE_IDS /
    SET_ROUTE_TYPES.
    """
    if table_name not in TABLE_REGISTRY:
        raise HTTPException(status_code=404, detail="Table not found")

    project = db.query(Project).filter(
        Project.id == project_id,
        Project.tenant_id == current_user.tenant_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.status != "completed":
        raise HTTPException(status_code=400, detail="Project data not ready")

    filters = _parse_column_filters(request.query_params)
    try:
        return resolve_table_filters(
            db, TABLE_REGISTRY[table_name], project_id, filters
        )
    except ResultQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{project_id}/tables/{table_name}/download")
def download_table_csv(
    project_id: str,
    table_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """下载单张结果表为分号分隔的 UTF-8 BOM CSV。"""
    import csv

    if table_name not in TABLE_REGISTRY:
        raise HTTPException(status_code=404, detail="Table not found")

    project = db.query(Project).filter(
        Project.id == project_id,
        Project.tenant_id == current_user.tenant_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.status != "completed":
        raise HTTPException(status_code=400, detail="Project data not ready")

    model = TABLE_REGISTRY[table_name]
    _internal = {"id", "project_id"}
    columns = [col.name for col in model.__table__.columns if col.name not in _internal]
    rows_orm = db.query(model).filter(model.project_id == project_id).all()

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(columns)
    for row in rows_orm:
        writer.writerow([getattr(row, col) for col in columns])

    bytes_buf = io.BytesIO(buf.getvalue().encode("utf-8-sig"))
    filename = f"{table_name}_{project_id}.csv"
    return StreamingResponse(
        bytes_buf,
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _parse_ligne_ids(raw: str | None) -> list[int] | None:
    """Parse ``?ligne_ids=1,2,3``.  Empty / blank is treated as 'no filter'."""
    if not raw or not raw.strip():
        return None
    out: list[int] = []
    for tok in raw.split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            out.append(int(tok))
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail=f"Invalid ligne_ids token: {tok!r}"
            ) from exc
    return out or None


def _parse_sous_ligne_keys(raw: str | None) -> list[tuple[int, str]] | None:
    """Parse ``?sous_ligne_keys=1:A,1:B,2:R`` into ``[(1,'A'),(1,'B'),(2,'R')]``.

    Front-end is responsible for URL-encoding sous_ligne values that contain
    ``:`` or ``,``.  Empty input means 'no filter'.
    """
    if not raw or not raw.strip():
        return None
    out: list[tuple[int, str]] = []
    for tok in raw.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if ":" not in tok:
            raise HTTPException(
                status_code=422,
                detail=f"sous_ligne_keys token missing ':': {tok!r}",
            )
        ln_str, sl = tok.split(":", 1)
        try:
            out.append((int(ln_str), sl))
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid id_ligne_num in sous_ligne_keys token: {tok!r}",
            ) from exc
    return out or None


@router.get("/{project_id}/map/passage-ag")
def get_passage_ag(
    project_id: str,
    jour_type: int,
    ligne_ids: str | None = None,
    sous_ligne_keys: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    E_1 station passage GeoJSON — pie chart data per AG.

    Returns a GeoJSON FeatureCollection where each Point feature represents
    one generic stop (AG) with its total passage count and a breakdown by
    transport mode (route_type).

    Optional filters (AND-ed with jour_type):
      - ligne_ids: comma-separated ``id_ligne_num`` (e.g. ``1,2,3``)
      - sous_ligne_keys: comma-separated ``id_ligne_num:sous_ligne``
        pairs (e.g. ``1:A,1:B,2:R``)

    When either filter is present, totals are recomputed via C2 → B1 → D2
    instead of read from E_1.

    jour_type parameter is required; omitting it returns HTTP 422.
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.tenant_id == current_user.tenant_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return build_passage_ag_geojson(
        project_id,
        jour_type,
        db,
        ligne_ids=_parse_ligne_ids(ligne_ids),
        sous_ligne_keys=_parse_sous_ligne_keys(sous_ligne_keys),
    )


@router.get("/{project_id}/map/passage-arc")
def get_passage_arc(
    project_id: str,
    jour_type: int,
    split_by: str = "none",
    ligne_ids: str | None = None,
    sous_ligne_keys: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    E_4 arc passage GeoJSON — AequilibraE-style bandwidth data.

    split_by="none": one Feature per arc with weight (0–1 normalised).
    split_by="route_type": one Feature per (arc × route_type), includes
    fraction_of_direction and cumulative_fraction_start for stacked rendering.

    Optional filters (AND-ed with jour_type), same format as /map/passage-ag:
      - ligne_ids: ``1,2,3``
      - sous_ligne_keys: ``1:A,1:B,2:R``

    Frontend renders pixel-based bandwidth:
        line_width  = weight × max_width_px
        line_offset = ±(gap_px/2 + cumulative_start × weight × max_width_px + sub_width/2)
    max_width_px and gap_px are user-adjustable frontend sliders (default 40px / 4px).
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.tenant_id == current_user.tenant_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return build_passage_arc_geojson(
        project_id,
        jour_type,
        db,
        split_by,
        ligne_ids=_parse_ligne_ids(ligne_ids),
        sous_ligne_keys=_parse_sous_ligne_keys(sous_ligne_keys),
    )


@router.get("/{project_id}/map/bounds")
def get_map_bounds(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Bounding box of all generic stops (A1) for a project.

    Returns {min_lng, min_lat, max_lng, max_lat} so the frontend can
    initialise the map at the correct extent without a wasted flash of
    the default center (Paris).

    Returns HTTP 404 if the project has no A1 rows yet.
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.tenant_id == current_user.tenant_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    row = db.query(
        func.min(ResultA1ArretGenerique.stop_lon),
        func.min(ResultA1ArretGenerique.stop_lat),
        func.max(ResultA1ArretGenerique.stop_lon),
        func.max(ResultA1ArretGenerique.stop_lat),
    ).filter(ResultA1ArretGenerique.project_id == project_id).one()

    min_lng, min_lat, max_lng, max_lat = row
    if min_lng is None:
        raise HTTPException(status_code=404, detail="No A1 data for project")

    return {
        "min_lng": min_lng,
        "min_lat": min_lat,
        "max_lng": max_lng,
        "max_lat": max_lat,
    }


@router.get("/{project_id}/map/jour-types")
def list_jour_types(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    List jour_type values actually present in this project's E_1 data,
    paired with their French calendar labels (TYPE_JOUR_VAC_LABELS).

    Response: [{"value": 1, "label": "Lundi_Scolaire"}, ...]
    Only values with at least one E_1 row are returned so the UI does not
    offer empty options for this particular dataset.
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.tenant_id == current_user.tenant_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    rows = (
        db.query(ResultE1PassageAG.type_jour)
        .filter(ResultE1PassageAG.project_id == project_id)
        .distinct()
        .order_by(ResultE1PassageAG.type_jour)
        .all()
    )
    return [
        {"value": r[0], "label": _JOUR_TYPE_LABEL_BY_VALUE.get(r[0], str(r[0]))}
        for r in rows
        if r[0] is not None
    ]


@router.get("/{project_id}/charts/peak-offpeak")
def get_peak_offpeak(
    project_id: str,
    jour_type: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    AG passages bucketed into peak / off-peak for a given jour_type.

    Peak windows (French operations convention):
      07:00–09:00 (HPM) and 16:30–19:00 (HPS).
    Everything else (incl. FM / FS / HC midday) is off-peak.

    jour_type parameter is required; omitting it returns HTTP 422.

    DEPRECATED — scheduled for removal one release after the dashboard
    refonte lands; use `/charts/courses-by-hour` instead.
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.tenant_id == current_user.tenant_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return build_peak_offpeak(project_id, jour_type, db)


def _authorize_project(project_id: str, db: Session, current_user: User) -> Project:
    """Shared tenant/ownership check used by all analytical endpoints below."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.tenant_id == current_user.tenant_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/{project_id}/charts/courses-by-jour-type")
def get_courses_by_jour_type(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Global courses-per-jour_type breakdown (F_1), unfiltered."""
    _authorize_project(project_id, db, current_user)
    return build_courses_by_jour_type(project_id, db)


@router.get("/{project_id}/charts/courses-by-hour")
def get_courses_by_hour(
    project_id: str,
    jour_type: int,
    route_types: List[str] = Query(default_factory=list, alias="route_types"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """24-bucket hourly breakdown of C_1 courses for a jour_type."""
    _authorize_project(project_id, db, current_user)
    return build_courses_by_hour(project_id, jour_type, route_types, db)


@router.get("/{project_id}/kpis")
def get_kpis(
    project_id: str,
    jour_type: int,
    route_types: List[str] = Query(default_factory=list, alias="route_types"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Return 4 KPIs (nb_lignes, nb_arrets, nb_courses, kcc_total) in one call."""
    _authorize_project(project_id, db, current_user)
    return build_kpis(project_id, jour_type, route_types, db)


@router.get("/{project_id}/export/geopackage")
def export_geopackage_endpoint(
    project_id: str,
    jour_type: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Export all map layers to a single GeoPackage file.

    Layers: passage_ag (Point), passage_arc (LineString),
    arrets_generiques (Point), arrets_physiques (Point).

    passage_arc carries nb_passage, max_nb_passage, direction (AB/BA).
    Style in QGIS using data-defined line width and offset with
    scale_linear("nb_passage", 0, "max_nb_passage", 0, max_width_pixel).
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.tenant_id == current_user.tenant_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    gpkg_path = export_geopackage(project_id, jour_type, db)
    # Read into memory so the file handle is closed before deletion (avoids
    # Windows file-lock errors in the background task).
    data = gpkg_path.read_bytes()
    background_tasks.add_task(gpkg_path.unlink, missing_ok=True)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/geopackage+sqlite3",
        headers={
            "Content-Disposition": f'attachment; filename="{project_id}.gpkg"',
        },
    )


@router.get("/{project_id}/download")
def download_results(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    下载整体处理结果的 ZIP 归档
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.tenant_id == current_user.tenant_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.status != "completed":
        raise HTTPException(status_code=400, detail="Project not ready for download")

    out_dir = PROJECT_DIR / project.tenant_id / project_id / "output"
    if not out_dir.exists():
        raise HTTPException(status_code=404, detail="Output directory not found")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for csv_file in sorted(out_dir.glob("*.csv")):
            zf.write(csv_file, csv_file.name)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="gtfs_results_{project_id}.zip"'},
    )
