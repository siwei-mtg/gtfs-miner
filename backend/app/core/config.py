from pydantic_settings import BaseSettings
from pathlib import Path
from functools import lru_cache

# Local-dev default storage path (overridden by STORAGE_PATH env var in Docker)
_LOCAL_STORAGE = str(Path(__file__).resolve().parent.parent.parent / "storage")


class Settings(BaseSettings):
    PROJECT_NAME: str = "GTFS Miner"
    API_V1_STR: str = "/api/v1"

    STORAGE_PATH: str = _LOCAL_STORAGE
    DATABASE_URL: str = f"sqlite:///{_LOCAL_STORAGE}/miner_app.db"
    CORS_ORIGINS: str = "*"

    # Cloudflare R2
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "gtfs-miner"
    R2_ENDPOINT_URL: str = ""

    # Celery / Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Phase 1 预留
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True

    @property
    def cors_origins_list(self) -> list[str]:
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    @property
    def storage_dir(self) -> Path:
        return Path(self.STORAGE_PATH)

    @property
    def temp_dir(self) -> Path:
        return self.storage_dir / "temp"

    @property
    def project_dir(self) -> Path:
        return self.storage_dir / "projects"

    @property
    def use_r2(self) -> bool:
        return bool(self.R2_ENDPOINT_URL and self.R2_BUCKET_NAME)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

settings.storage_dir.mkdir(parents=True, exist_ok=True)
settings.temp_dir.mkdir(parents=True, exist_ok=True)
settings.project_dir.mkdir(parents=True, exist_ok=True)

STORAGE_DIR = settings.storage_dir
TEMP_DIR = settings.temp_dir
PROJECT_DIR = settings.project_dir
