# 云端部署指南 — GTFS Miner（Phase 0/1，国内可访问）

## 为什么选择 Zeabur

| 原方案 | 问题 |
|---|---|
| Fly.io `cdg`（巴黎） | 国内 IP 路由不通 |
| Cloudflare 强制反代后端 | 额外配置、WebSocket 需手动开启 |
| DigitalOcean Droplet | 需 SSH 手动构建镜像、运维成本高 |

**Zeabur 解法：** Zeabur 香港 / 新加坡节点国内直连，延迟约 30–60 ms，无需 Cloudflare 作为后端代理。前端仍使用 Cloudflare Pages（全球 CDN，免费）。

---

## 目标架构

```
[浏览器 — 国内或海外]
    │
    ├─ HTTPS ──> [Cloudflare Pages]        React 静态构建
    │            app.yourdomain.com         全球 CDN，免费
    │
    └─ HTTPS/WS ─> [Zeabur — 香港]        FastAPI + Uvicorn（Docker）
                   api.yourdomain.com       自定义域名 + 自动 TLS
                       │                   WebSocket 原生支持，无需额外配置
                       ├─ [Supabase ap-southeast-1]   PostgreSQL 托管数据库
                       │   后端 → Supabase 服务端直连（浏览器不接触 Supabase）
                       │
                       ├─ [Cloudflare R2]              S3 兼容对象存储
                       │   上传 ZIP + 输出 CSV
                       │   boto3 已在 requirements.txt
                       │   下载通过 api.yourdomain.com/download/... 代理
                       │
                       └─ [Upstash Redis — 新加坡]     Celery Broker（Phase 1）
```

### 组件选型

| 组件 | 平台 | 理由 |
|---|---|---|
| 后端 | **Zeabur 香港**（1 vCPU / 1 GB，按量计费） | Docker 部署，国内直连，WebSocket 原生支持 |
| 前端 | **Cloudflare Pages** | 全球 CDN，自定义域名，免费 |
| 数据库 | **Supabase ap-southeast-1** | 托管 PostgreSQL，免费 500 MB |
| 文件存储 | **Cloudflare R2** | S3 兼容，boto3 原生，10 GB 免费，CF 代理可达 |
| Redis | **Upstash Redis 新加坡** | 免费 256 MB，Celery Broker |
| 代理 | **Cloudflare**（自定义域名） | 前端必须；后端**可选**（推荐，增强稳定性） |

**Phase 0 保持 `--workers 1`：**
`ConnectionManager` 将 WebSocket 存于内存。Phase 1 切换至 Celery + Redis pub/sub 后可扩展多 Worker。

---

## 需要创建 / 修改的文件

### 1. `backend/app/core/config.py`

```python
from pydantic_settings import BaseSettings
from pathlib import Path
from functools import lru_cache


class Settings(BaseSettings):
    PROJECT_NAME: str = "GTFS Miner"
    API_V1_STR: str = "/api/v1"

    # 本地存储（开发回退）— 生产环境由 R2 替代
    STORAGE_PATH: str = "/app/storage"

    # Supabase PostgreSQL
    DATABASE_URL: str = "sqlite:////app/storage/miner_app.db"

    # CORS — 生产环境填写 "https://app.yourdomain.com"
    CORS_ORIGINS: str = "*"

    # Cloudflare R2（S3 兼容）
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "gtfs-miner"
    R2_ENDPOINT_URL: str = ""          # https://<account_id>.r2.cloudflarestorage.com

    # Celery / Redis
    REDIS_URL: str = "redis://localhost:6379/0"

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

# 创建本地目录（仅开发环境，R2 启用后忽略）
settings.storage_dir.mkdir(parents=True, exist_ok=True)
settings.temp_dir.mkdir(parents=True, exist_ok=True)
settings.project_dir.mkdir(parents=True, exist_ok=True)

# 向后兼容导出
STORAGE_DIR = settings.storage_dir
TEMP_DIR = settings.temp_dir
PROJECT_DIR = settings.project_dir
```

### 2. `backend/app/db/database.py`

```python
# SQLite 专用参数，迁移至 PostgreSQL 时删除
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
```

### 3. `backend/app/main.py`

- 将 `allow_origins=["*"]` 替换为 `allow_origins=settings.cors_origins_list`
- 删除 `Base.metadata.create_all(bind=engine)` — 改由 Alembic 管理迁移

### 4. `backend/app/db/models.py`

```python
output_path = Column(String, nullable=True)  # R2 key 或本地路径
```

### 5. `backend/app/services/storage.py`（新建）

本地 / R2 存储抽象 — Worker 调用 `storage.upload()` / `storage.download_url()`。

```python
import boto3
from pathlib import Path
from app.core.config import settings


def _r2_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def upload_file(local_path: Path, key: str) -> str:
    """上传至 R2（生产）或本地复制（开发）。返回 key / 路径。"""
    if settings.use_r2:
        _r2_client().upload_file(str(local_path), settings.R2_BUCKET_NAME, key)
        return key
    dest = settings.project_dir / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(local_path.read_bytes())
    return str(dest)


def generate_presigned_url(key: str, expires: int = 3600) -> str:
    """生成 R2 签名下载 URL（开发环境返回本地路径）。"""
    if settings.use_r2:
        return _r2_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.R2_BUCKET_NAME, "Key": key},
            ExpiresIn=expires,
        )
    return f"/api/v1/projects/download/{key}"
```

### 6. `backend/Dockerfile`

多阶段构建，包含 geopandas / scipy 所需系统库：

```dockerfile
# 阶段 1：构建依赖
FROM python:3.11-slim AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libgeos-dev libproj-dev gdal-bin libgdal-dev \
    libatlas-base-dev liblapack-dev libblas-dev libffi-dev libpq-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# 阶段 2：运行时
FROM python:3.11-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgeos-c1v5 libproj25 libgdal32 libatlas3-base liblapack3 libpq5 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /install /usr/local
WORKDIR /app
COPY . .
RUN mkdir -p storage/temp storage/projects
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"]
```

### 7. `backend/zeabur.json`（可选，Zeabur 自动检测 Dockerfile 时可省略）

```json
{
  "name": "gtfs-miner-api",
  "build": { "type": "dockerfile" },
  "ports": [{ "port": 8000, "type": "HTTP" }]
}
```

### 8. Alembic — `backend/alembic.ini` + `backend/alembic/env.py`

**`alembic.ini`**：
```ini
[alembic]
script_location = alembic
prepend_sys_path = .
```

**`alembic/env.py`**：
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.core.config import settings
from app.db.database import Base
from app.db.models import Project  # noqa: F401

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
target_metadata = Base.metadata
```

### 9. `backend/.env.example`

```env
# PostgreSQL — Supabase
DATABASE_URL=postgresql+psycopg2://postgres.[ref]:[password]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres

# Cloudflare R2
R2_ACCOUNT_ID=xxxxxxxxxxxx
R2_ACCESS_KEY_ID=xxxxxxxxxxxx
R2_SECRET_ACCESS_KEY=xxxxxxxxxxxx
R2_BUCKET_NAME=gtfs-miner
R2_ENDPOINT_URL=https://xxxxxxxxxxxx.r2.cloudflarestorage.com

# Upstash Redis
REDIS_URL=rediss://default:xxxx@ap1.upstash.io:6379

# CORS — Cloudflare Pages 域名
CORS_ORIGINS=https://app.yourdomain.com

# 本地开发（SQLite）
# DATABASE_URL=sqlite:////app/storage/miner_app.db
# R2_ENDPOINT_URL=   ← 留空 = 使用本地存储
```

### 10. `frontend/vite.config.ts`

```typescript
server: {
  proxy: {
    '/api': { target: process.env.VITE_API_URL ?? 'http://localhost:8000', changeOrigin: true },
    '/ws':  { target: process.env.VITE_API_URL ?? 'http://localhost:8000', ws: true }
  }
}
```

Cloudflare Pages 部署时设置环境变量 `VITE_API_URL=https://api.yourdomain.com`。

---

## 部署步骤

### 步骤 0 — 本地准备

```bash
# 1. 应用上述所有文件变更
# 2. 生成 Alembic 初始迁移
cd backend
alembic revision --autogenerate -m "initial_schema"
alembic upgrade head    # 本地 SQLite 测试
```

### 步骤 1 — Supabase（数据库）

```
1. 创建 Supabase 项目 → 区域选 "Southeast Asia (Singapore)"
2. Settings → Database → Connection string（Mode: Session）→ 复制 DATABASE_URL
3. Settings → API → 复制 SUPABASE_URL 和 SUPABASE_ANON_KEY（Phase 1 备用）
```

### 步骤 2 — Cloudflare R2（文件存储）

```
1. CF Dashboard → R2 → Create bucket "gtfs-miner"
2. Manage R2 API Tokens → Create token（Object Read & Write）
3. 复制 Account ID、Access Key ID、Secret Access Key
4. R2_ENDPOINT_URL = https://<account_id>.r2.cloudflarestorage.com
```

R2 签名 URL 国内可达配置：
```
R2 → Bucket settings → Custom domain → r2.yourdomain.com（通过 Cloudflare）
→ 签名 URL 基于 r2.yourdomain.com（CF 代理 = 国内可达）
```

### 步骤 3 — Upstash Redis

```
1. console.upstash.com → Create Database → Region: Singapore
2. 复制 Redis URL（格式 rediss://...）
```

### 步骤 4 — Zeabur（后端）

```
1. zeabur.com → New Project → Deploy from GitHub
2. 选择 repo → 指定目录 backend/
3. Zeabur 自动检测 Dockerfile 并构建
4. Environment → 粘贴 .env.example 中的真实变量值
5. Networking → Generate Domain 或 Custom Domain → api.yourdomain.com
6. Region → Hong Kong（或 Singapore）
7. [Phase 0 SQLite 时] Storage → Add Volume → 挂载路径 /app/storage
   [切换 Supabase 后无需此步骤]
```

推送代码后 Zeabur 自动重新部署，无需 SSH 操作。

### 步骤 5 — Cloudflare DNS（可选但推荐）

```
CF Dashboard → 你的域名 → DNS → Add record
  Type : A
  Name : api
  IPv4 : Zeabur 服务 IP（Zeabur Networking 页面查看）
  Proxy : ON（橙色云朵）← 推荐开启，增强国内稳定性
```

> **注意**：与原方案不同，Cloudflare 代理对后端**不是强制要求**。
> Zeabur 香港节点国内已可直连。开启 CF 代理可进一步提升稳定性并隐藏真实 IP。
> WebSocket 无需在 CF 单独开启（Zeabur 原生支持）。

```
CF → SSL/TLS → Full (strict)
```

测试：
```bash
curl https://api.yourdomain.com/docs     # Swagger UI
```

### 步骤 6 — Cloudflare Pages（前端）

```
1. CF Dashboard → Pages → Connect to Git → 选择 repo
2. Build command    : npm run build
3. Output directory : dist
4. 环境变量         :
     VITE_API_URL = https://api.yourdomain.com
5. Custom domain    : app.yourdomain.com
```

---

## 端到端验证

```bash
# 查看 Zeabur 日志
# Zeabur Dashboard → 服务 → Logs

# 验证 Alembic 迁移已执行
# Zeabur → Runtime → Terminal
alembic current

# 从国内浏览器测试
# → https://app.yourdomain.com → 上传 GTFS ZIP → 观察进度条
```

---

## 文件变更汇总

| 文件 | 操作 |
|---|---|
| `backend/app/core/config.py` | 修改 — 添加 R2、Redis、CORS list、`use_r2` 属性 |
| `backend/app/db/database.py` | 修改 — 条件化 `connect_args` |
| `backend/app/main.py` | 修改 — CORS 从 config 读取，删除 `create_all` |
| `backend/app/db/models.py` | 修改 — 添加 `output_path` 列 |
| `backend/app/services/storage.py` | 新建 — 本地 / R2 存储抽象 |
| `backend/Dockerfile` | 新建 — 多阶段构建，含 geopandas/scipy 系统库 |
| `backend/zeabur.json` | 新建（可选）— Zeabur 服务配置 |
| `backend/alembic.ini` | 新建 — Alembic 配置 |
| `backend/alembic/env.py` | 新建 — `DATABASE_URL` 从 Settings 读取 |
| `backend/alembic/versions/*.py` | 生成 — `alembic revision --autogenerate` |
| `backend/.env.example` | 新建 — 环境变量模板 |
| `frontend/vite.config.ts` | 修改 — 支持 `VITE_API_URL` 生产环境变量 |

## 月度费用估算

| 服务 | 套餐 | 费用 |
|---|---|---|
| Zeabur（1 vCPU / 1 GB，香港） | Hobby，按量 | ~$5–8/月 |
| Supabase | Free（500 MB，2 GB 流量） | $0 |
| Cloudflare R2 | Free 10 GB 存储 + 1000 万次操作 | $0 |
| Upstash Redis | Free 256 MB，50 万次命令/天 | $0 |
| Cloudflare Pages | Free | $0 |
| **Phase 0 合计** | | **~$5–8/月** |
