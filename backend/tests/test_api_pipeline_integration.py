"""
test_api_pipeline_integration.py — 端到端联调测试

验证三个维度：
  A. REST API 流程：创建项目 → 上传文件 → 状态轮询
  B. 文件持久化：output/ 目录下的 CSV 报表是否齐全
  C. 数据库状态：projects 表的 status 是否正确变为 'completed'
  D. (Task 8) 完整 E2E：以上三步 + 下载验证（ZIP 内含 15 个分号分隔 CSV）

运行方式（在 backend/ 目录下）：
  python -m pytest tests/test_api_pipeline_integration.py -v -s
"""
import io
import time
import zipfile

import pytest

from app.db.database import SessionLocal
from app.db.models import Project
from app.core.config import PROJECT_DIR
from .conftest import GTFS_ZIP, EXPECTED_CSVS

# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def wait_for_completion(client_authed, project_id: str, timeout: int = 300) -> str:
    """Poll GET /status until status is 'completed' or 'failed'."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client_authed.get(f"/api/v1/projects/{project_id}")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        status = data["status"]
        print(f"  [poll] status={status}")
        if status in ("completed", "failed"):
            return status
        time.sleep(3)
    return "timeout"


# ──────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────

def test_gtfs_zip_exists():
    """前提条件：测试 GTFS 数据文件必须存在。"""
    assert GTFS_ZIP.exists(), f"Test data not found: {GTFS_ZIP}"


def test_create_project(client_authed):
    """A-1. POST /projects/ 应该返回 201 和一个 project_id。"""
    payload = {
        "hpm_debut": "07:00",
        "hpm_fin": "09:00",
        "hps_debut": "17:00",
        "hps_fin": "19:30",
        "vacances": "A",
        "pays": "法国",
    }
    resp = client_authed.post("/api/v1/projects/", json=payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "id" in data
    assert data["status"] == "pending"
    test_create_project.project_id = data["id"]
    print(f"  Created project: {data['id']}")


def test_upload_and_wait(client_authed):
    """A-2 + B + C.  上传 → 等待完成 → 验证文件 + DB 状态。"""
    project_id = getattr(test_create_project, "project_id", None)
    assert project_id, "test_create_project must run first"

    # ── A-2: Upload ────────────────────────────────────────────────
    with open(GTFS_ZIP, "rb") as f:
        resp = client_authed.post(
            f"/api/v1/projects/{project_id}/upload",
            files={"file": ("SEM-GTFS.zip", f, "application/zip")},
        )
    assert resp.status_code == 200, resp.text
    print(f"  Upload response: {resp.json()}")

    # ── A-3: Poll until done ────────────────────────────────────────
    print("  Waiting for pipeline to complete (may take several minutes)...")
    final_status = wait_for_completion(client_authed, project_id, timeout=600)
    assert final_status == "completed", \
        f"Pipeline ended with status '{final_status}'. Check the 'error_message' in DB."

    # ── B: File persistence ─────────────────────────────────────────
    out_dir = PROJECT_DIR / project_id / "output"
    print(f"  Checking output dir: {out_dir}")
    assert out_dir.exists(), f"Output directory not found: {out_dir}"

    missing = [f for f in EXPECTED_CSVS if not (out_dir / f).exists()]
    assert not missing, f"Missing output files: {missing}"
    print(f"  ✓ All {len(EXPECTED_CSVS)} expected CSVs are present.")

    # ── C: DB status ───────────────────────────────────────────────
    db = SessionLocal()
    project = db.query(Project).filter(Project.id == project_id).first()
    db.close()
    assert project is not None
    assert project.status == "completed", \
        f"DB status is '{project.status}', error: {project.error_message}"
    print(f"  ✓ DB status = 'completed'.")


def test_get_project_list(client_authed):
    """应返回非空的项目列表。"""
    resp = client_authed.get("/api/v1/projects/")
    assert resp.status_code == 200
    projects = resp.json()
    assert isinstance(projects, list)
    assert len(projects) >= 1
    print(f"  Found {len(projects)} project(s).")


# ──────────────────────────────────────────────────────────────────
# Task 8: Full E2E — upload → process → download
# ──────────────────────────────────────────────────────────────────

def test_full_e2e_upload_process_download(client_authed):
    """完整 E2E：创建 → 上传 → 轮询至 completed → 下载 → 验证 ZIP 内 15 个 CSV。"""
    # ── 创建项目 ───────────────────────────────────────────────────
    payload = {
        "hpm_debut": "07:00", "hpm_fin": "09:00",
        "hps_debut": "17:00", "hps_fin": "19:30",
        "vacances": "A", "pays": "法国",
    }
    resp = client_authed.post("/api/v1/projects/", json=payload)
    assert resp.status_code == 201, resp.text
    project_id = resp.json()["id"]
    print(f"  E2E project: {project_id}")

    # ── 上传 ───────────────────────────────────────────────────────
    with open(GTFS_ZIP, "rb") as f:
        resp = client_authed.post(
            f"/api/v1/projects/{project_id}/upload",
            files={"file": ("SEM-GTFS.zip", f, "application/zip")},
        )
    assert resp.status_code == 200, resp.text

    # ── 轮询完成 ───────────────────────────────────────────────────
    print("  Waiting for pipeline to complete...")
    final_status = wait_for_completion(client_authed, project_id, timeout=600)
    assert final_status == "completed", f"Pipeline ended with '{final_status}'"

    # ── 下载 ZIP ───────────────────────────────────────────────────
    resp = client_authed.get(f"/api/v1/projects/{project_id}/download")
    assert resp.status_code == 200, resp.text
    assert "application/zip" in resp.headers["content-type"]

    # ── 验证 ZIP 内容 ──────────────────────────────────────────────
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        zip_names = zf.namelist()
        assert sorted(zip_names) == sorted(EXPECTED_CSVS), \
            f"ZIP contents mismatch:\n  expected: {sorted(EXPECTED_CSVS)}\n  got:      {sorted(zip_names)}"
        for name in zip_names:
            data = zf.read(name).decode("utf-8-sig")
            assert len(data) > 0,   f"{name} is empty"
            assert ";" in data,     f"{name} is not semicolon-separated"
    print(f"  ✓ Downloaded ZIP contains {len(zip_names)} valid semicolon-delimited CSVs.")
