from pydantic_settings import BaseSettings
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
STORAGE_DIR = BASE_DIR / "storage"
TEMP_DIR = STORAGE_DIR / "temp"
PROJECT_DIR = STORAGE_DIR / "projects"

class Settings(BaseSettings):
    PROJECT_NAME: str = "GTFS Miner"
    API_V1_STR: str = "/api/v1"
    
    # Storage settings
    STORAGE_PATH: str = str(STORAGE_DIR)
    
    # SQLite Database URI for MVP
    DATABASE_URL: str = f"sqlite:///{STORAGE_DIR}/miner_app.db"
    
    class Config:
        case_sensitive = True

# Ensure directories exist
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)
PROJECT_DIR.mkdir(parents=True, exist_ok=True)

settings = Settings()
