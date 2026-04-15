"""
One-time script: re-persist results for a project whose E1/E4
were stored with NULL type_jour (legacy string-column CSV format).

Usage:  python repersist_project.py <project_id>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.db.database import SessionLocal
from app.db.models import Project
from app.services.worker import _persist_results_to_db
from app.core.config import PROJECT_DIR

project_id = sys.argv[1]
db = SessionLocal()
try:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        print(f"Project {project_id} not found")
        sys.exit(1)
    out_dir = PROJECT_DIR / project.tenant_id / project_id / "output"
    if not out_dir.exists():
        print(f"Output dir not found: {out_dir}")
        sys.exit(1)
    print(f"Re-persisting {project_id} from {out_dir}...")
    _persist_results_to_db(project_id, out_dir, db)
    print("Done.")
finally:
    db.close()
