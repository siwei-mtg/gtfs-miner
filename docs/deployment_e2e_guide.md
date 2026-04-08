# 部署实操手册 — GTFS Miner（新手完整版）

> 本文档是 `deployment.md`（技术参考）的实操版本。假设你从未部署过任何 Web 应用。

---

## 读前须知

### 你需要准备什么

**本地已有（不需要安装）**
- Python 3.11、Node.js、Git、VS Code

**需要注册的账号**（全部免费注册，Phase 0 月费约 $5–8）

| 账号 | 注册地址 | 用途 |
|---|---|---|
| Supabase | supabase.com | 云端 PostgreSQL 数据库 |
| Cloudflare | cloudflare.com | 域名 DNS + Pages 前端托管 + R2 文件存储 |
| Upstash | upstash.com | Redis（Phase 1 用，现在先建好） |
| Zeabur | zeabur.com | 后端容器部署 |
| GitHub | github.com | 代码托管（Zeabur 从这里拉代码） |

**你需要一个域名**，例如 `gtfs-miner.com`（约 ¥60–80/年）。  
如果还没有，在阿里云万网、腾讯云等购买，然后把 DNS 托管到 Cloudflare（下面有详细步骤）。

### 你会用到的两类密码

- **凭据（Credentials）**：各平台给你生成的密钥，只显示一次，必须立刻保存。
- **环境变量（Environment Variables）**：你把这些凭据以变量名 = 值的形式告诉后端程序。

建议在本地新建一个 `secrets.txt`（**不要上传 Git**），把所有密钥临时记在里面。

---

## 第一步：整理代码并推送 GitHub

> 如果代码已在 GitHub 上，跳到第二步。

**1.1 在 GitHub 新建仓库**

1. 登录 github.com → 右上角 `+` → `New repository`
2. 仓库名：`gtfs-miner`，选 `Private`（私有）
3. 不勾选任何初始化选项，点 `Create repository`

**1.2 推送代码**

```bash
# 在项目根目录执行
git remote add origin https://github.com/你的用户名/gtfs-miner.git
git push -u origin main
```

---

## 第二步：修改代码（部署前必须）

> 以下文件改动让后端能读取云端配置。**按顺序做，每步完成后保存文件。**

### 2.1 修改 `backend/app/core/config.py`

用以下内容**完整替换**该文件（保留原有内容结构，增加 R2 / Redis / CORS 配置）：

```python
from pydantic_settings import BaseSettings
from pathlib import Path
from functools import lru_cache


class Settings(BaseSettings):
    PROJECT_NAME: str = "GTFS Miner"
    API_V1_STR: str = "/api/v1"

    STORAGE_PATH: str = "/app/storage"
    DATABASE_URL: str = "sqlite:////app/storage/miner_app.db"
    CORS_ORIGINS: str = "*"

    # Cloudflare R2
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "gtfs-miner"
    R2_ENDPOINT_URL: str = ""

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

settings.storage_dir.mkdir(parents=True, exist_ok=True)
settings.temp_dir.mkdir(parents=True, exist_ok=True)
settings.project_dir.mkdir(parents=True, exist_ok=True)

STORAGE_DIR = settings.storage_dir
TEMP_DIR = settings.temp_dir
PROJECT_DIR = settings.project_dir
```

### 2.2 修改 `backend/app/db/database.py`

找到 `create_engine(...)` 那一行，在它**上方**加一行：

```python
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
```

然后把 `create_engine(...)` 改成：

```python
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
```

### 2.3 修改 `backend/app/main.py`

找到 CORS 配置部分（有 `allow_origins` 的那几行），把 `allow_origins=["*"]` 改为：

```python
allow_origins=settings.cors_origins_list,
```

同时在文件顶部确认已导入 `settings`：

```python
from app.core.config import settings
```

如果有 `Base.metadata.create_all(bind=engine)` 这一行，**删掉它**（改用 Alembic 管理）。

### 2.4 修改 `backend/app/db/models.py`

在 `Project` 类的字段列表里增加一行（放在 `error_message` 附近）：

```python
output_path = Column(String, nullable=True)  # R2 key 或本地路径
```

### 2.5 新建 `backend/app/services/storage.py`

新建这个文件，内容如下：

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
    if settings.use_r2:
        _r2_client().upload_file(str(local_path), settings.R2_BUCKET_NAME, key)
        return key
    dest = settings.project_dir / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(local_path.read_bytes())
    return str(dest)


def generate_presigned_url(key: str, expires: int = 3600) -> str:
    if settings.use_r2:
        return _r2_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.R2_BUCKET_NAME, "Key": key},
            ExpiresIn=expires,
        )
    return f"/api/v1/projects/download/{key}"
```

### 2.6 新建 `backend/Dockerfile`

在 `backend/` 目录下新建文件名为 `Dockerfile`（无扩展名），内容：

```dockerfile
# 阶段 1：安装依赖
FROM python:3.11-slim AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libgeos-dev libproj-dev gdal-bin libgdal-dev \
    libatlas-base-dev liblapack-dev libblas-dev libffi-dev libpq-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# 阶段 2：运行时镜像
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

### 2.7 配置 Alembic（数据库迁移工具）

Alembic 负责在 Supabase 上自动建表，替代手动 SQL。

**安装 Alembic（如果还没装）：**

```bash
cd backend
pip install alembic
```

**初始化：**

```bash
alembic init alembic
```

这会在 `backend/` 下生成 `alembic/` 目录和 `alembic.ini` 文件。

**修改 `backend/alembic.ini`**，找到 `sqlalchemy.url =` 那行，改为：

```ini
sqlalchemy.url =
```

（留空，因为 URL 由代码动态读取）

**修改 `backend/alembic/env.py`**，在文件顶部加：

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.core.config import settings
from app.db.database import Base
from app.db.models import Project  # noqa: F401
```

然后找到 `config.set_main_option(...)` 那一行，替换为：

```python
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
```

找到 `target_metadata = None`，改为：

```python
target_metadata = Base.metadata
```

**本地测试 Alembic（用 SQLite，不连 Supabase）：**

```bash
cd backend
alembic revision --autogenerate -m "initial_schema"
alembic upgrade head
```

如果没有报错，说明配置正确。

### 2.8 新建 `backend/.env.example`

这是给自己看的模板，**不填真实值**：

```env
# PostgreSQL — Supabase
DATABASE_URL=postgresql+psycopg2://postgres.[ref]:[password]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres

# Cloudflare R2
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=gtfs-miner
R2_ENDPOINT_URL=https://你的AccountID.r2.cloudflarestorage.com

# Upstash Redis
REDIS_URL=rediss://default:你的密码@ap1.upstash.io:6379

# CORS
CORS_ORIGINS=https://app.yourdomain.com

# 本地开发（SQLite，不连云）
# DATABASE_URL=sqlite:////app/storage/miner_app.db
# R2_ENDPOINT_URL=
```

### 2.9 修改 `frontend/vite.config.ts`

在 `defineConfig({` 里找到或新增 `server` 配置块：

```typescript
server: {
  proxy: {
    '/api': {
      target: process.env.VITE_API_URL ?? 'http://localhost:8000',
      changeOrigin: true,
    },
    '/ws': {
      target: process.env.VITE_API_URL ?? 'http://localhost:8000',
      ws: true,
    },
  },
},
```

### 2.10 提交并推送所有改动

```bash
git add backend/app/core/config.py \
        backend/app/db/database.py \
        backend/app/main.py \
        backend/app/db/models.py \
        backend/app/services/storage.py \
        backend/Dockerfile \
        backend/alembic.ini \
        backend/alembic/ \
        backend/.env.example \
        frontend/vite.config.ts
git commit -m "feat: deployment config — R2, Alembic, Dockerfile, Zeabur"
git push
```

---

## 第三步：创建 Supabase 数据库

**3.1 注册并新建项目**

1. 打开 [supabase.com](https://supabase.com) → Sign Up（用 GitHub 账号登录最方便）
2. 点 `New project`
3. 填写：
   - **Name**：`gtfs-miner`
   - **Database Password**：生成一个强密码，**立刻保存到 secrets.txt**
   - **Region**：选 `Southeast Asia (Singapore)`（东南亚新加坡）
4. 点 `Create new project`，等待约 1 分钟

**3.2 获取数据库连接串**

1. 左侧菜单 → `Settings` → `Database`
2. 向下滚动找到 `Connection string`
3. Mode 切换为 **`Session`**（不是 Transaction）
4. 复制显示的 URI，格式类似：
   ```
   postgresql+psycopg2://postgres.xxxxxx:[YOUR-PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
   ```
5. 把 `[YOUR-PASSWORD]` 替换成你在 3.1 设置的密码
6. 保存到 secrets.txt，标注为 `DATABASE_URL`

**3.3 获取 API 密钥（Phase 1 备用）**

1. 左侧菜单 → `Settings` → `API`
2. 复制 `Project URL` 和 `anon public` 密钥
3. 保存到 secrets.txt，标注为 `SUPABASE_URL` 和 `SUPABASE_ANON_KEY`

---

## 第四步：创建 Cloudflare 账号并接管域名

> 如果你的域名已经在 Cloudflare 管理，跳到 4.3。

**4.1 注册 Cloudflare**

1. 打开 [cloudflare.com](https://cloudflare.com) → Sign Up
2. 验证邮箱

**4.2 将域名的 DNS 托管到 Cloudflare**

1. Cloudflare Dashboard → `Add a Site` → 输入你的域名 → `Add site`
2. 选免费套餐 `Free`
3. Cloudflare 会自动扫描你的现有 DNS 记录，直接点 `Continue`
4. 页面底部会显示两个 Cloudflare 名称服务器，例如：
   ```
   aria.ns.cloudflare.com
   bob.ns.cloudflare.com
   ```
5. 登录你购买域名的平台（阿里云/腾讯云）→ 域名管理 → 修改 DNS 服务器为上面两个
6. 回到 Cloudflare 点 `Done`，等待生效（最多 24 小时，通常几分钟）

**4.3 确认域名已激活**

Cloudflare Dashboard → 你的域名 → 如果显示 `Active`（绿色），说明 DNS 接管成功。

---

## 第五步：创建 Cloudflare R2 存储桶

**5.1 进入 R2**

Cloudflare Dashboard → 左侧菜单 → `R2 Object Storage`（如果没看到，点 `Workers & Pages` 下方）

**5.2 创建存储桶**

1. 点 `Create bucket`
2. **Bucket name**：`gtfs-miner`（必须和 `.env.example` 里一致）
3. **Location**：选 `Asia Pacific (APAC)` 或自动
4. 点 `Create bucket`

**5.3 获取 R2 API 密钥**

1. R2 首页（退出存储桶页面）→ 右上角 `Manage R2 API Tokens`
2. 点 `Create API Token`
3. 填写：
   - **Token name**：`gtfs-miner-backend`
   - **Permissions**：选 `Object Read & Write`
   - **Specify bucket**（可选）：选 `gtfs-miner`
4. 点 `Create API Token`
5. 页面显示三个值，**立刻保存**（离开后无法再看到）：
   - `Access Key ID` → 保存为 `R2_ACCESS_KEY_ID`
   - `Secret Access Key` → 保存为 `R2_SECRET_ACCESS_KEY`
   - 页面顶部还有 `Account ID` → 保存为 `R2_ACCOUNT_ID`

**5.4 构建 R2_ENDPOINT_URL**

```
https://你的R2_ACCOUNT_ID.r2.cloudflarestorage.com
```

例如：`https://abc123def456.r2.cloudflarestorage.com`

**5.5 （推荐）绑定自定义域名让下载链接国内可达**

1. 进入 `gtfs-miner` 存储桶 → `Settings` → `Custom Domains`
2. 点 `Connect Domain` → 输入 `r2.yourdomain.com`（你的域名）
3. Cloudflare 自动添加 DNS 记录，点确认

这样 R2 文件的下载链接会走 `r2.yourdomain.com`，经过 CF 代理，国内可访问。

---

## 第六步：创建 Upstash Redis

**6.1 注册并创建数据库**

1. 打开 [console.upstash.com](https://console.upstash.com) → Sign Up（用 GitHub 登录）
2. 点 `Create Database`
3. 填写：
   - **Name**：`gtfs-miner-redis`
   - **Type**：`Regional`
   - **Region**：`ap-southeast-1 (Singapore)`
4. 点 `Create`

**6.2 获取连接 URL**

1. 点击创建的数据库
2. 找到 `REST API` 下方的 `UPSTASH_REDIS_REST_URL` 旁边的连接信息
3. 切换到 `Details` 标签 → 找 `Redis Connection` → 复制 `rediss://` 开头的 URL
4. 保存到 secrets.txt，标注为 `REDIS_URL`

---

## 第七步：部署后端到 Zeabur

**7.1 注册 Zeabur**

1. 打开 [zeabur.com](https://zeabur.com) → Sign Up（用 GitHub 登录）
2. 绑定信用卡（Visa/万事达均可，0 元验证）

**7.2 新建项目**

1. Dashboard → `Create Project`
2. 选择区域：**Hong Kong**（香港，国内延迟最低）
3. 项目名：`gtfs-miner`

**7.3 部署后端服务**

1. 在项目页面 → `Add Service` → `Git`
2. 连接 GitHub → 选择 `gtfs-miner` 仓库
3. **Root Directory**：填 `backend`（告诉 Zeabur 在 backend/ 目录里找 Dockerfile）
4. Zeabur 自动检测到 Dockerfile，点 `Deploy`

**7.4 配置环境变量**

部署开始后（不需要等成功），点击服务 → `Variables` 标签 → 逐个添加：

| 变量名 | 值（从 secrets.txt 复制） |
|---|---|
| `DATABASE_URL` | Supabase 连接串（第三步获取） |
| `R2_ACCOUNT_ID` | R2 账号 ID |
| `R2_ACCESS_KEY_ID` | R2 访问密钥 ID |
| `R2_SECRET_ACCESS_KEY` | R2 秘密访问密钥 |
| `R2_BUCKET_NAME` | `gtfs-miner` |
| `R2_ENDPOINT_URL` | `https://你的AccountID.r2.cloudflarestorage.com` |
| `REDIS_URL` | Upstash Redis URL |
| `CORS_ORIGINS` | `https://app.yourdomain.com`（先填 `*`，前端上线后再改） |

添加完毕后 Zeabur 自动重新部署。

**7.5 查看部署日志**

点击服务 → `Deployments` → 最新一次部署 → 点进去看日志。

正常日志最后几行应该类似：
```
INFO  [alembic.runtime.migration] Running upgrade -> abc123, initial_schema
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

如果有红色错误，截图并检查环境变量是否填写正确。

**7.6 绑定自定义域名**

1. 服务页面 → `Networking` 标签
2. 点 `Generate Domain` 先获取一个 Zeabur 临时域名（如 `gtfs-miner-api.zeabur.app`），用于测试
3. 点 `Custom Domain` → 填 `api.yourdomain.com`
4. Zeabur 显示一条 CNAME 记录，例如：
   ```
   CNAME  api  →  xxx.zeabur.app
   ```
5. 去 Cloudflare Dashboard → 你的域名 → `DNS` → `Add record`：
   - **Type**：`CNAME`
   - **Name**：`api`
   - **Target**：Zeabur 给的地址（`xxx.zeabur.app`）
   - **Proxy**：打开（橙色云朵）← 推荐，国内稳定性更好
6. 回 Zeabur 点 `Verify`，等待 DNS 生效（几分钟内）

**7.7 验证后端是否正常**

浏览器打开：`https://api.yourdomain.com/docs`

如果能看到 FastAPI 的 Swagger UI 页面（蓝色标题、接口列表），说明后端部署成功。

---

## 第八步：部署前端到 Cloudflare Pages

**8.1 进入 Cloudflare Pages**

Cloudflare Dashboard → `Workers & Pages` → `Pages` → `Create a project`

**8.2 连接 GitHub 仓库**

1. 点 `Connect to Git`
2. 选择 `gtfs-miner` 仓库 → 点 `Begin setup`

**8.3 构建配置**

| 设置项 | 填写值 |
|---|---|
| Project name | `gtfs-miner-app` |
| Production branch | `main` |
| **Build command** | `npm run build` |
| **Build output directory** | `dist` |
| **Root directory** | `frontend` |

**8.4 环境变量**

在同一页面的 `Environment variables` 下方，点 `Add variable`：

| 变量名 | 值 |
|---|---|
| `VITE_API_URL` | `https://api.yourdomain.com` |

**8.5 部署**

点 `Save and Deploy`，等待约 1–3 分钟。

构建成功后 Cloudflare 给你一个临时地址如 `gtfs-miner-app.pages.dev`。

**8.6 绑定自定义域名**

1. Pages 项目 → `Custom domains` → `Set up a custom domain`
2. 输入 `app.yourdomain.com` → 点 `Continue`
3. Cloudflare 自动添加 DNS 记录（因为域名已在 CF 管理，无需手动操作）
4. 等待几分钟，访问 `https://app.yourdomain.com` 即可

---

## 第九步：端到端验证

**9.1 功能测试**

1. 浏览器打开 `https://app.yourdomain.com`
2. 点击上传，选择一个 GTFS ZIP 文件（用 `backend/tests/Resources/raw/` 里的测试数据）
3. 点击提交，观察进度条是否出现并逐步更新（7 个步骤）
4. 步骤完成后，下载按钮变为可用，点击下载
5. 解压下载的 ZIP，确认里面有 15 个 CSV 文件

**9.2 查看后端日志**

如果出现问题，在 Zeabur → 服务 → `Deployments` → 当前部署 → `Logs` 查看实时日志。

**9.3 常见问题**

| 现象 | 可能原因 | 解决方法 |
|---|---|---|
| 前端页面空白 | 构建失败或 VITE_API_URL 未设置 | 检查 Cloudflare Pages 构建日志 |
| 上传报 CORS 错误 | `CORS_ORIGINS` 未包含前端域名 | 在 Zeabur 更新 `CORS_ORIGINS` 变量 |
| 进度条不动 | WebSocket 连接失败 | 确认 Cloudflare DNS 橙色云朵已开启 |
| 下载 404 | 处理失败或文件路径问题 | 查看 Zeabur 日志里的错误堆栈 |
| Zeabur 构建失败 | Dockerfile 路径错误 | 确认 `Root directory` 设置为 `backend` |

---

## 部署完成后的日常操作

**更新代码（重新部署）**

```bash
git push
```

Zeabur 和 Cloudflare Pages 都会自动检测到 push 并重新部署，无需任何手动操作。

**查看费用**

Zeabur Dashboard → 你的账号 → `Billing`，可以看到当月用量。Phase 0 通常低于 $8/月。

**Phase 1 迁移提示**

当需要从 SQLite 切换到 Supabase 时，只需要：
1. 在 Zeabur 把 `DATABASE_URL` 改为 Supabase 连接串
2. Zeabur 重新部署后，Alembic 会自动在 Supabase 上建表（`alembic upgrade head` 在启动命令里）
3. Worker 代码无需修改

---

## 所有凭据汇总（部署前填写）

> 把这张表复制到你的 `secrets.txt`，填好后保存。

```
DATABASE_URL         = （Supabase 第三步获取）
R2_ACCOUNT_ID        = （R2 第五步获取）
R2_ACCESS_KEY_ID     = （R2 第五步获取）
R2_SECRET_ACCESS_KEY = （R2 第五步获取）
R2_BUCKET_NAME       = gtfs-miner
R2_ENDPOINT_URL      = https://[R2_ACCOUNT_ID].r2.cloudflarestorage.com
REDIS_URL            = （Upstash 第六步获取）
CORS_ORIGINS         = https://app.yourdomain.com
SUPABASE_URL         = （Supabase 第三步获取，Phase 1 备用）
SUPABASE_ANON_KEY    = （Supabase 第三步获取，Phase 1 备用）
```
