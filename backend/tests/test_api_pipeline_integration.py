"""
test_api_pipeline_integration.py — 端到端联调测试

验证三个维度：
  A. REST API 流程：创建项目 → 上传文件 → 状态轮询
  B. 文件持久化：output/ 目录下的 CSV 报表是否齐全
  C. 数据库状态：projects 表的 status 是否正确变为 'completed'

运行方式（在仓库根目录下）：
  $env:PYTHONPATH="c:\\Users\\wei.si\\Projets\\GTFS Miner\\backend"
  python -m pytest backend/tests/test_api_pipeline_integration.py -v -s
"""
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Pre-set PYTHONPATH entry
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app
from app.db.database import Base, engine, SessionLocal, get_db
from app.db.models import Project
from app.core.config import PROJECT_DIR

# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def client():
    """Shared TestClient across the test session."""
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c


GTFS_ZIP = Path(__file__).parent / "Resources" / "raw" / "SEM-GTFS(2).zip"
EXPECTED_CSVS = [
    "A_1_Arrets_Generiques.csv",
    "A_2_Arrets_Physiques.csv",
    "B_1_Lignes.csv",
    "B_2_Sous_Lignes.csv",
    "C_1_Courses.csv",
    "C_2_Itineraire.csv",
    "C_3_Itineraire_Arc.csv",
    "D_1_Service_Dates.csv",
    "D_2_Service_Jourtype.csv",
    "E_1_Nombre_Passage_AG.csv",
    "E_4_Nombre_Passage_Arc.csv",
    "F_1_Nombre_Courses_Lignes.csv",
    "F_2_Caract_SousLignes.csv",
    "F_3_KCC_Lignes.csv",
    "F_4_KCC_Sous_Ligne.csv",
]

# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def wait_for_completion(client, project_id: str, timeout: int = 300) -> str:
    """Poll GET /status until status is 'completed' or 'failed'."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"/api/v1/projects/{project_id}")
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


def test_create_project(client):
    """A-1. POST /projects/ 应该返回 201 和一个 project_id。"""
    payload = {
        "hpm_debut": "07:00",
        "hpm_fin": "09:00",
        "hps_debut": "17:00",
        "hps_fin": "19:30",
        "vacances": "A",
        "pays": "法国",
    }
    resp = client.post("/api/v1/projects/", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "id" in data
    assert data["status"] == "pending"
    # Store project id for next tests
    test_create_project.project_id = data["id"]
    print(f"  Created project: {data['id']}")


def test_upload_and_wait(client):
    """A-2 + B + C.  上传 → 等待完成 → 验证文件 + DB 状态。"""
    # Depend on previous test
    project_id = getattr(test_create_project, "project_id", None)
    assert project_id, "test_create_project must run first"

    # ── A-2: Upload ────────────────────────────────────────────────
    with open(GTFS_ZIP, "rb") as f:
        resp = client.post(
            f"/api/v1/projects/{project_id}/upload",
            files={"file": ("SEM-GTFS.zip", f, "application/zip")},
        )
    assert resp.status_code == 200, resp.text
    print(f"  Upload response: {resp.json()}")

    # ── A-3: Poll until done ────────────────────────────────────────
    print("  Waiting for pipeline to complete (may take several minutes)...")
    final_status = wait_for_completion(client, project_id, timeout=600)
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


def test_get_project_list(client):
    """应返回非空的项目列表。"""
    resp = client.get("/api/v1/projects/")
    assert resp.status_code == 200
    projects = resp.json()
    assert isinstance(projects, list)
    assert len(projects) >= 1
    print(f"  Found {len(projects)} project(s).")
