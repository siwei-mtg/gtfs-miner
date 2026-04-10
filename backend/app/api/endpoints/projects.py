from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List
import io
import shutil
import asyncio
import zipfile
from pathlib import Path

from ...db.database import get_db
from ...db.models import Project, User
from ...schemas.project import ProjectCreate, ProjectResponse
from ...services.worker import run_project_task_sync
from ...core.config import settings, TEMP_DIR, PROJECT_DIR
from ...api.deps import get_current_active_user

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
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

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
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only ZIP files are supported")

    project.status = "uploading"
    db.commit()

    # Save to temp area
    temp_zip_path = TEMP_DIR / f"{project_id}_{file.filename}"
    with temp_zip_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    project.status = "pending"
    db.commit()

    # Pass the current event loop for asyncio coroutine threadsafe calls inside sync worker
    loop = asyncio.get_running_loop()

    # Dispatch to background wrapper
    background_tasks.add_task(
        run_project_task_sync,
        project_id=project_id,
        zip_path=str(temp_zip_path),
        parameters=project.parameters,
        loop=loop
    )

    return {"msg": "Upload successful, processing started.", "project_id": project_id}

@router.get("/{project_id}/tables/{table_name}")
def get_table_data(
    project_id: str,
    table_name: str,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    获取项目处理完成后的特定 CSV 表格的分页数据
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project or project.status != "completed":
        raise HTTPException(status_code=400, detail="Project data not ready")

    # TODO: Read from SQLite result tables or CSV file.
    # This is a stub for frontend testing.
    return {"total": 0, "page": skip, "limit": limit, "data": []}

@router.get("/{project_id}/download")
def download_results(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    下载整体处理结果的 ZIP 归档
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.status != "completed":
        raise HTTPException(status_code=400, detail="Project not ready for download")

    out_dir = PROJECT_DIR / project_id / "output"
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
