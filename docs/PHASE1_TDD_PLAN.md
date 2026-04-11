# Phase 1 TDD 任务拆解计划

**版本**：1.2  
**日期**：2026-04-11  
**状态**：Sprint 1–4 完成 / Sprint 5 进行中（Task 22 完成）

---

## Context

Phase 1 目标（PRD §9）：**Transamo 内部 MVP** — 在 Phase 0 端到端流程（上传→处理→**查看洞察**→下载）基础上，叠加用户认证、多租户隔离、在线结果表格查看、参数配置表单，并完成基础设施从 SQLite/BackgroundTasks 迁移至 Supabase + Celery + R2。

> **产品目标更新（PRD v0.5）**：核心定位调整为「一键将原始 GTFS 数据转化为公共交通分析洞察」。Phase 1 新增一项前置依赖：pipeline 完成后自动将 CSV 加载至 **DWD SQLite**（E_*/F_* melt 规范化），为 Phase 3 LLM Agent（F-09）铺路。

### Phase 0 基线（已完成，100%）

| 模块 | 状态 | 关键文件 |
|------|------|---------|
| FastAPI 脚手架 | ✅ | `backend/app/main.py` |
| Project CRUD API（6 个端点） | ✅ | `backend/app/api/endpoints/projects.py` |
| GTFS 上传 + BackgroundTask Worker | ✅ | `backend/app/services/worker.py` |
| WebSocket 实时进度（7 步 × 15 CSV） | ✅ | `backend/app/api/websockets/progress.py` |
| ZIP 下载 API | ✅ | `projects.py:download_results()` |
| React 前端（上传→进度→下载） | ✅ | `frontend/src/` |
| 测试（55 个，0 错误） | ✅ | `backend/tests/` + `frontend/src/__tests__/` |

### 当前限制（Phase 1 需解决）

- 无认证：所有端点完全开放
- 无租户隔离：所有项目共享同一 `projects` 表，无 `owner_id`
- 存储：SQLite（开发可用，不适合生产多用户）
- 任务队列：`BackgroundTasks`（单进程，不可横向扩展）
- 结果：仅生成 CSV 文件；`GET /tables/{name}` 端点为 stub
- 前端：无登录页、无项目列表页、无在线表格视图
- **无 DWD SQLite 查询层**：E_*/F_* 透视列未规范化，F-09 LLM Agent 前置依赖缺失（新增，PRD v0.5）

### 关键文件清单

- `backend/app/core/config.py` — Settings（需扩展 R2/Redis/CORS/JWT）
- `backend/app/db/models.py` — Project 模型（需加 User/Tenant + 外键）
- `backend/app/db/database.py` — SQLite 专用参数（需条件化）
- `backend/app/api/endpoints/projects.py` — 现有 6 个端点（需加认证依赖）
- `backend/app/services/worker.py` — BackgroundTask Worker（迁移至 Celery）
- `backend/app/api/websockets/progress.py` — ConnectionManager（需适配 Redis pub/sub）
- `backend/requirements.txt` — 已含 celery、redis、alembic、boto3、asyncpg

---

## GROUP A：基础设施迁移（Task 1–5）

> 先于所有功能组完成。其他 GROUP 均依赖此组的环境就绪。

### Task 1：config.py 升级 ✅

> **当前状态**：已完成。`backend/app/core/config.py` 所有字段和属性均已实现。

**修改文件**：`backend/app/core/config.py`

按 `docs/deployment.md §1` 替换为完整 Settings：

- 新增字段：`CORS_ORIGINS`、`SECRET_KEY`、`JWT_ALGORITHM`、`JWT_EXPIRE_MINUTES`
- 新增字段：`R2_ACCOUNT_ID`、`R2_ACCESS_KEY_ID`、`R2_SECRET_ACCESS_KEY`、`R2_BUCKET_NAME`、`R2_ENDPOINT_URL`
- 新增字段：`REDIS_URL`、`SUPABASE_URL`、`SUPABASE_ANON_KEY`
- 新增属性：`cors_origins_list`、`storage_dir`、`temp_dir`、`project_dir`、`use_r2`
- 保持向后兼容导出：`STORAGE_DIR`、`TEMP_DIR`、`PROJECT_DIR`

**测试**（`tests/test_config.py`）：
1. `test_defaults_sqlite` — 默认值：DATABASE_URL 含 sqlite、use_r2=False
2. `test_cors_list_wildcard` — `CORS_ORIGINS="*"` → `cors_origins_list == ["*"]`
3. `test_cors_list_multiple` — `CORS_ORIGINS="a.com,b.com"` → 列表含两项
4. `test_use_r2_true` — 设 R2_ENDPOINT_URL + R2_BUCKET_NAME → `use_r2 == True`

**依赖**：无

---

### Task 2：database.py 条件化 + Alembic 初始化 ✅

> **当前状态**：已完成。小缺口：`create_engine()` 缺 `pool_pre_ping=True`（生产稳定性用，Supabase 切换前补充即可）。
>
> **TODO**：`backend/.env.example` 模板文件尚未创建（目前只有 `.env` 真实文件），推送前补充一份不含真实值的模板。

**修改文件**：`backend/app/db/database.py`

```python
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
```

**创建文件**：
- `backend/alembic.ini`（`script_location = alembic`）
- `backend/alembic/env.py`（从 Settings 读取 DATABASE_URL；`target_metadata = Base.metadata`）
- `backend/.env.example`（按 `deployment.md §9` 模板）

**执行**：
```bash
cd backend
alembic revision --autogenerate -m "initial_project_table"
alembic upgrade head   # 本地 SQLite 验证
```

**验证**：`alembic current` 输出 head revision；SQLite DB 中 `projects` 表存在。

**依赖**：Task 1

---

### Task 3：storage.py — 本地 / R2 存储抽象 ✅

> **当前状态**：已完成。`upload_file` 和 `generate_presigned_url` 已实现。`delete_file()` 尚未添加——Task 12（存储路径租户前缀化）用到时补充。

**创建文件**：`backend/app/services/storage.py`

按 `deployment.md §5` 实现三个函数：
- `upload_file(local_path, key) → str`
- `generate_presigned_url(key, expires=3600) → str`
- `delete_file(key) → None`（Phase 1 新增：项目删除时清理）

本地模式（`use_r2=False`）：文件复制至 `project_dir / key`，presigned URL 返回本地端点路径。

**测试**（`tests/test_storage.py`）：
1. `test_upload_local` — 上传文件，验证目标路径存在
2. `test_presigned_url_local` — 返回字符串含 project_id
3. `test_upload_r2_called`（mock boto3）— `use_r2=True` 时调用 `s3.upload_file`
4. `test_delete_local` — 删除后文件不存在

**依赖**：Task 1

---

### Task 4：Dockerfile + zeabur.json ✅

> **当前状态**：已完成。`backend/Dockerfile` 多阶段构建，含 geopandas/scipy 系统库，Alembic 启动命令正确。

**创建文件**：
- `backend/Dockerfile`（按 `deployment.md §6`，多阶段构建含 geopandas/scipy 系统库）
- `backend/zeabur.json`（可选，Zeabur 自动检测时省略）

**验证（本地 Docker）**：
```bash
docker build -t gtfs-miner-backend backend/
docker run -p 8000:8000 --env-file backend/.env gtfs-miner-backend
curl http://localhost:8000/docs   # Swagger UI 正常
```

**依赖**：Task 2

---

### Task 5：main.py 更新 ✅

> **当前状态**：已完成。CORS 使用 `settings.cors_origins_list`，`Base.metadata.create_all` 已删除。

**修改文件**：`backend/app/main.py`

- `allow_origins=["*"]` → `allow_origins=settings.cors_origins_list`
- 删除 `Base.metadata.create_all(bind=engine)`（改由 Alembic 管理）
- 添加 Celery worker 启动检查（可选 health check 端点）

**测试**（追加到 `tests/test_config.py`）：
1. `test_cors_from_env` — 设环境变量 `CORS_ORIGINS=https://x.com`，启动 app，验证 CORS header

**依赖**：Task 1、2

---

## GROUP B：用户认证（Task 6–10）

### Task 6：User + Tenant 模型 + Alembic 迁移 ✅

> **当前状态**：已完成。`backend/app/db/models.py` 中 `Tenant` 和 `User` 模型均已实现，`Project` 已添加 `tenant_id` / `owner_id` 外键。

**修改文件**：`backend/app/db/models.py`

新增模型：

```python
class Tenant(Base):
    __tablename__ = "tenants"
    id: str (UUID, PK)
    name: str
    plan: str (default="free")   # free / pro / enterprise
    created_at: datetime

class User(Base):
    __tablename__ = "users"
    id: str (UUID, PK)
    email: str (unique, indexed)
    hashed_password: str
    tenant_id: str (FK → tenants.id)
    role: str (default="member")   # admin / member
    is_active: bool (default=True)
    created_at: datetime
```

修改 `Project`：
- 添加 `tenant_id: str (FK → tenants.id, indexed)`
- 添加 `owner_id: str (FK → users.id)`

**执行**：
```bash
alembic revision --autogenerate -m "add_user_tenant_to_project"
alembic upgrade head
```

**验证**：`alembic current` = head；SQLite 三张表均存在。

**依赖**：Task 2

---

### Task 7：Auth schemas ✅

> **当前状态**：已完成。`backend/app/schemas/auth.py` 所有 schema（`TenantCreate`、`UserCreate`、`UserResponse`、`Token`、`TokenData`）均已实现，测试已通过。

**创建文件**：`backend/app/schemas/auth.py`

```python
class TenantCreate(BaseModel): name: str
class TenantResponse(BaseModel): id, name, plan, created_at

class UserCreate(BaseModel): email: EmailStr, password: str (≥8 chars), tenant_name: str
class UserResponse(BaseModel): id, email, role, tenant_id, created_at
class Token(BaseModel): access_token: str, token_type: str = "bearer"
class TokenData(BaseModel): user_id: str | None
```

**测试**（`tests/test_auth_schemas.py`）：
1. `test_user_create_valid`
2. `test_user_create_short_password` — 校验失败
3. `test_token_default_type` — token_type == "bearer"

**依赖**：Task 6

---

### Task 8：密码哈希 + JWT 工具 ✅

> **当前状态**：已完成。`backend/app/core/security.py` 实现了 `hash_password`、`verify_password`、`create_access_token`、`decode_token`，`passlib[bcrypt]` 和 `python-jose[cryptography]` 已加入 `requirements.txt`，测试已通过。

**创建文件**：`backend/app/core/security.py`

- `hash_password(plain: str) → str`（passlib bcrypt）
- `verify_password(plain, hashed) → bool`
- `create_access_token(data: dict, expires_delta: timedelta | None) → str`（python-jose）
- `decode_token(token: str) → TokenData`

**测试**（`tests/test_security.py`）：
1. `test_hash_and_verify` — 正向验证
2. `test_wrong_password` — verify=False
3. `test_token_roundtrip` — create → decode，user_id 一致
4. `test_token_expired` — 过期 token 抛出异常

**新增依赖**（`requirements.txt`）：`passlib[bcrypt]`、`python-jose[cryptography]`

**依赖**：Task 7

---

### Task 9：Auth 端点 + 测试（先写测试）✅

> **当前状态**：已完成。`backend/app/api/endpoints/auth.py` 实现了 `POST /register`、`POST /login`、`GET /me` 三个端点，`tests/test_auth.py` 8 个测试已通过。

**创建文件**：`backend/app/api/endpoints/auth.py`

端点：

| Method | Path | 功能 |
|--------|------|------|
| POST | `/api/v1/auth/register` | 创建 Tenant + User；返回 Token |
| POST | `/api/v1/auth/login` | 验证邮箱+密码；返回 Token |
| GET  | `/api/v1/auth/me` | 返回当前 User（需认证） |

**创建文件**：`backend/tests/test_auth.py`

测试用例：
1. `test_register_success` — 201，返回 access_token
2. `test_register_duplicate_email` — 409
3. `test_login_success` — 200，返回 Token
4. `test_login_wrong_password` — 401
5. `test_login_unknown_email` — 401
6. `test_me_authenticated` — 200，返回 email
7. `test_me_no_token` — 401
8. `test_me_invalid_token` — 401

**依赖**：Task 8

---

### Task 10：get_current_user 依赖 + 保护现有端点 ✅

> **当前状态**：已完成。`projects.py` 全部 6 个端点添加了 `get_current_active_user` 依赖；`create_project` 写入 `tenant_id`/`owner_id`；`list_projects` 加租户过滤。`conftest.py` 新增 `auth_client`、`auth_client_b`、`client_authed`、`isolated_client_authed` 四个 fixture；`test_auth.py` 追加 3 个测试（含租户隔离）；`test_download.py`/`test_api_pipeline_integration.py`/`test_websocket.py` 更新为使用 authed fixtures。全量 32 个测试通过（不含慢速 E2E）。

**创建文件**：`backend/app/api/deps.py`

```python
async def get_current_user(token: str = Depends(oauth2_scheme), db = Depends(get_db)) → User
async def get_current_active_user(current_user = Depends(get_current_user)) → User
```

**修改文件**：`backend/app/api/endpoints/projects.py`

所有端点添加 `current_user: User = Depends(get_current_active_user)`。

**测试**（追加到 `tests/test_auth.py`）：
1. `test_create_project_unauthenticated` — 401
2. `test_create_project_authenticated` — 201
3. `test_list_projects_only_own_tenant` — User A 看不到 User B 的项目

**修改文件**：`backend/tests/conftest.py`

新增 fixtures：
- `auth_client` — 已注册并登录的 TestClient（含 Authorization header）
- `auth_client_b` — 第二租户的 TestClient（隔离测试用）
- 将现有 `client` fixture 改为匿名客户端

**依赖**：Task 9

---

## GROUP C：多租户隔离（Task 11–12）

### Task 11：项目查询租户过滤 ✅

> **当前状态**：已完成。`get_project`、`upload_gtfs`、`get_table_data`、`download_results` 均加入双条件过滤（`Project.id` + `Project.tenant_id`），跨租户访问返回 404。`tests/test_tenancy.py` 新增 3 个测试全部通过。

**修改文件**：`backend/app/api/endpoints/projects.py`

所有查询（list / get / upload / download）添加 `.filter(Project.tenant_id == current_user.tenant_id)`。

其他租户的项目返回 404（不泄露存在信息）。

**测试**（`tests/test_tenancy.py`）：
1. `test_project_invisible_to_other_tenant` — A 创建的项目，B 的 GET 返回 404
2. `test_list_isolated` — A 的列表不含 B 的项目
3. `test_download_isolated` — B 无法下载 A 的结果

**依赖**：Task 10

---

### Task 12：存储路径租户前缀化 ✅

> **当前状态**：已完成。`worker.py` output dir 改为 `PROJECT_DIR / tenant_id / project_id / output/`；`projects.py` download 路径同步；`storage.py` 新增 `delete_file()`。`test_tenancy.py` 第 4 个测试（路径结构验证）通过；`test_download.py` helpers 已更新 tenant_id 前缀。

**修改文件**：`backend/app/services/worker.py`

输出目录改为 `PROJECT_DIR / {tenant_id} / {project_id} / output/`。

**修改文件**：`backend/app/api/endpoints/projects.py`（download 端点同步更新路径）

**修改文件**：`backend/app/services/storage.py`

`upload_file` key 格式：`{tenant_id}/projects/{project_id}/output/{filename}`

**测试**（追加到 `tests/test_tenancy.py`）：
1. `test_output_path_contains_tenant_id` — 处理完成后验证目录结构

**依赖**：Task 11、Task 3

---

## GROUP D：Celery 异步队列（Task 13–15）✅

### Task 13：Celery app 配置 ✅

**创建文件**：`backend/app/celery_app.py`

```python
from celery import Celery
from app.core.config import settings

celery = Celery("gtfs_miner", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
celery.conf.task_serializer = "json"
```

**测试**（`tests/test_celery.py`）：
1. `test_celery_ping`（需 Redis）— `celery.control.ping()` 返回响应；标记 `@pytest.mark.integration`

**依赖**：Task 1

---

### Task 14：BackgroundTasks → Celery task 迁移 ✅

**修改文件**：`backend/app/services/worker.py`

将 `run_project_task_sync` 包装为 `@celery.task`：

```python
@celery.task(bind=True, name="gtfs_miner.process_project")
def process_project_task(self, project_id: str, zip_path: str, parameters: dict): ...
```

**修改文件**：`backend/app/api/endpoints/projects.py`（upload 端点）

```python
# 替换：
background_tasks.add_task(run_project_task_sync, ...)
# 为：
process_project_task.delay(project_id, zip_path, parameters)
```

**测试**（`tests/test_worker_celery.py`）：
1. `test_task_registered` — task name 在 celery 注册列表中
2. `test_task_eager`（`CELERY_TASK_ALWAYS_EAGER=True`）— 直接执行，输出目录含 15 个 CSV

**注意**：WebSocket 进度推送在单 Worker 时仍可工作（loop 传参保持不变）；多 Worker 时需 Task 15。

**依赖**：Task 13

---

### Task 15：WebSocket 进度通过 Redis pub/sub（多 Worker 支持）✅

**修改文件**：`backend/app/api/websockets/progress.py`

将 `ConnectionManager` 的广播从内存字典改为：
- Worker 端：`redis.publish(f"progress:{project_id}", json.dumps(msg))`
- WebSocket 端点：`redis.subscribe(f"progress:{project_id}")` → 转发给客户端

开发环境（无 Redis）退化：保持原内存模式（通过 `settings.REDIS_URL` 是否有效判断）。

**测试**（追加到 `tests/test_websocket.py`，标记 `@pytest.mark.integration`）：
1. `test_ws_progress_via_redis` — 两个进程模拟：Worker publish → WS 客户端收到消息

**依赖**：Task 14

---

## GROUP E：参数配置验证 F-04（Task 16）✅

### Task 16：参数 Schema 严格验证 ✅

**修改文件**：`backend/app/schemas/project.py`

增强 `ProjectCreate`：

```python
class ProjectCreate(BaseModel):
    hpm_debut: str = "07:00"    # 正则校验 HH:MM
    hpm_fin:   str = "09:00"
    hps_debut: str = "17:00"
    hps_fin:   str = "19:30"
    vacances:  Literal["A","B","C","全部"] = "A"
    pays:      str = "france"   # Phase 4 多国预留

    @validator("hpm_debut", "hpm_fin", "hps_debut", "hps_fin")
    def validate_time_format(cls, v): ...  # 必须匹配 ^([01]\d|2[0-3]):[0-5]\d$

    @validator("hpm_fin")
    def hpm_fin_after_debut(cls, v, values): ...  # hpm_fin > hpm_debut
```

**测试**（`tests/test_project_schema.py`）：
1. `test_valid_defaults`
2. `test_invalid_time_format` — "25:00" → ValidationError
3. `test_invalid_vacances` — "D" → ValidationError
4. `test_hpm_fin_before_debut` — "06:00" < "07:00" → ValidationError
5. `test_valid_all_vacances`

**依赖**：Task 6（Project 模型）

---

## GROUP F：在线结果表格 F-06（Task 17–20）

### Task 17：15 个结果表 DB 模型 ✅

**创建文件**：`backend/app/db/result_models.py`

按 PRD F-06 定义 15 个 SQLAlchemy 模型，命名规则 `Result{Code}_{Name}`：

| 模型类 | 表名 | 关键字段（示例）|
|--------|------|----------------|
| `ResultA1ArretGenerique` | `result_a1_arrets_generiques` | `project_id`, `ag_id`, `nom`, `lat`, `lon` |
| `ResultA2ArretPhysique` | `result_a2_arrets_physiques` | `project_id`, `ap_id`, `ag_id`, `nom`, `lat`, `lon` |
| `ResultB1Ligne` | `result_b1_lignes` | `project_id`, `ligne_id`, `nom`, `route_type` |
| `ResultB2SousLigne` | `result_b2_sous_lignes` | `project_id`, `sl_id`, `ligne_id` |
| `ResultC1Course` | `result_c1_courses` | `project_id`, `course_id`, `sl_id`, `direction_id` |
| `ResultC2Itineraire` | `result_c2_itineraire` | `project_id`, `course_id`, `seq`, `ag_id`, `heure` |
| `ResultC3ItineraireArc` | `result_c3_itineraire_arc` | `project_id`, `arc_id`, `ag_dep`, `ag_arr` |
| `ResultD1ServiceDate` | `result_d1_service_dates` | `project_id`, `service_id`, `date` |
| `ResultD2ServiceJourtype` | `result_d2_service_jourtype` | `project_id`, `service_id`, `jourtype` |
| `ResultE1PassageAG` | `result_e1_passage_ag` | `project_id`, `ag_id`, `jourtype`, `nb_passage` |
| `ResultE4PassageArc` | `result_e4_passage_arc` | `project_id`, `arc_id`, `jourtype`, `nb_passage` |
| `ResultF1CourseLigne` | `result_f1_nb_courses_lignes` | `project_id`, `ligne_id`, `jourtype`, `nb_course` |
| `ResultF2CaractSL` | `result_f2_caract_sous_lignes` | `project_id`, `sl_id`, `intervalle_hpm` |
| `ResultF3KCCLigne` | `result_f3_kcc_lignes` | `project_id`, `ligne_id`, `kcc` |
| `ResultF4KCCSL` | `result_f4_kcc_sous_lignes` | `project_id`, `sl_id`, `kcc` |

所有表共同字段：`id`（整数自增 PK）、`project_id`（FK，indexed）。

**执行**：
```bash
alembic revision --autogenerate -m "add_15_result_tables"
alembic upgrade head
```

**依赖**：Task 6

---

### Task 18：Worker 写入 PostgreSQL ✅

**修改文件**：`backend/app/services/worker.py`

在步骤 7 完成后（CSV 写入完毕），新增步骤：读取每个 CSV → bulk insert 到对应 result 表。

设计：
- 使用 `pandas.read_csv(..., sep=";", encoding="utf-8-sig")` 读取
- 通过 `df.to_sql(table_name, engine, if_exists="append", index=False)` 批量写入
- 先清除该 project_id 的旧数据（幂等性）

**测试**（`tests/test_result_persistence.py`）：
1. `test_results_written_to_db`（CELERY_TASK_ALWAYS_EAGER）— 处理完成后查询 `result_a1_arrets_generiques` 行数 > 0
2. `test_result_project_id_filter` — 两个项目的结果不混淆
3. `test_idempotent_reprocess` — 同一项目重跑后，行数不翻倍

**依赖**：Task 17、Task 14

---

### Task 19：结果查询 API（stub → 完整）✅

**修改文件**：`backend/app/api/endpoints/projects.py`

实现 `GET /{project_id}/tables/{table_name}`：

```
查询参数：
  skip: int = 0
  limit: int = 50  (最大 200)
  sort_by: str | None
  sort_order: "asc" | "desc" = "asc"
  q: str | None  (简单文本搜索，对所有 str 字段 OR 过滤)
```

返回：`{ "total": int, "rows": list[dict], "columns": list[str] }`

**新增文件**：`backend/app/services/result_query.py`

封装查询逻辑，支持动态表名路由（`TABLE_REGISTRY: dict[str, type]`）。

**测试**（`tests/test_result_api.py`）：
1. `test_get_table_a1_paginated` — 返回 200，rows 非空，total 正确
2. `test_get_table_unknown` — 404
3. `test_get_table_wrong_project` — 其他租户 404
4. `test_sort_by_column` — 指定 sort_by，结果有序
5. `test_text_search` — q 过滤后 rows 均含搜索词
6. `test_limit_max_200` — limit=500 → 实际返回 ≤ 200
7. `test_total_count_correct` — total 与 count(*) 一致

**依赖**：Task 18、Task 11

> **当前状态**：已完成。7 个测试全部通过（commit `7c888f3`，2026-04-11）。

---

### Task 20：单表 CSV 下载（F-07 扩展）✅

**修改文件**：`backend/app/api/endpoints/projects.py`

新增端点：`GET /{project_id}/tables/{table_name}/download`

从 result 表查询全量数据 → 生成分号分隔 UTF-8 BOM CSV → `StreamingResponse`。

**测试**（追加到 `tests/test_result_api.py`）：
1. `test_single_table_csv_download` — Content-Type `text/csv`，分号分隔，含 BOM
2. `test_single_table_csv_columns` — 列名与 table schema 一致

**依赖**：Task 19

> **当前状态**：已完成。2 个测试全部通过（2026-04-11）。

---

### Task 20b：DWD SQLite 加载（F-09 前置依赖）✅

> **来源**：PRD v0.5 Phase 1 新增项。pipeline 完成后将 14 个 CSV 加载至项目专属 SQLite，供 Phase 3 LLM Agent 查询；E_*/F_* 透视列在加载时规范化（melt）。

**创建文件**：`backend/app/services/dwd_loader.py`

```python
def load_outputs_to_dwd(project_id: str, output_dir: Path) -> Path:
    """
    将 output_dir 下 14 个 CSV 加载至 {output_dir}/{project_id}_query.sqlite。
    E_*/F_* 文件在加载前调用 pd.melt() 将日类型透视列转为规范行格式：
      - id_vars: 非日类型列（id_ag_num, stop_name 等）
      - var_name: "jour_type"
      - value_name: 依文件而定（nb_passages / nb_courses / kcc_km 等）
    返回 SQLite 文件路径。
    """
```

**melt 规则对照表**：

| 文件 | id_vars | value_name |
|------|---------|------------|
| E_1_Nombre_Passage_AG | `id_ag_num, stop_name, stop_lat, stop_lon` | `nb_passages` |
| E_4_Nombre_Passage_Arc | `id_ag_num_a, id_ag_num_b` + 坐标列 | `nb_passages` |
| F_1_Nombre_Courses_Lignes | `id_ligne_num, route_short_name, route_long_name` | `nb_courses` |
| F_3_KCC_Lignes | `id_ligne_num, route_short_name, route_long_name` | `kcc_km` |
| F_4_KCC_Sous_Ligne | `sous_ligne, id_ligne_num, route_short_name, route_long_name` | `kcc_km` |
| F_2_Caract_SousLignes | 所有非数值列 | 按 `Type_Jour` 保留原结构（已含 jour_type 列，无需 melt） |
| A_*/B_*/C_*/D_* | — | 直接加载，不 melt |

**修改文件**：`backend/app/services/worker.py`

在 step [7/7] 完成（CSV 写入）、数据库写入（Task 18）之后，追加调用：

```python
from app.services.dwd_loader import load_outputs_to_dwd
dwd_path = load_outputs_to_dwd(project_id, output_dir)
# 更新 Project.output_path 或记录 dwd_path（可选）
```

**测试**（`tests/test_dwd_loader.py`）：
1. `test_load_creates_sqlite` — 处理完成后 `{project_id}_query.sqlite` 文件存在
2. `test_all_14_tables_loaded` — SQLite 中恰好存在 14 张表（含 E_*/F_* melt 后的名称）
3. `test_e1_melted_schema` — `passage_ag` 表含 `jour_type`、`nb_passages` 列，不含数字列名（`"1"`, `"2"` 等）
4. `test_f3_melted_schema` — `kcc_lignes` 表含 `jour_type`、`kcc_km` 列
5. `test_a1_row_count_matches_csv` — `arrets_generiques` 行数与源 CSV 行数一致
6. `test_idempotent_reload` — 重跑后 SQLite 行数不翻倍（先清空再写入）

**依赖**：Task 18（CSV 已写入 output_dir）、Task 14（Celery task 框架）

> **当前状态**：已完成。6 个测试全部通过（2026-04-11）。注：实际 CSV 文件为 15 个（TDD 计划中"14"为笔误，E_4 是第 15 个文件），测试断言已相应修正为 15 张表。

---


## GROUP H：前端更新（Task 22–28）

> 可与 GROUP B–G **并行开发**（依赖 Task 9 auth endpoints 就绪的契约即可）。

### Task 22：Auth API client + types ✅

**修改文件**：`frontend/src/types/api.ts`

新增类型：`UserCreate`、`UserResponse`、`Token`、`TenantCreate`

**修改文件**：`frontend/src/api/client.ts`

新增函数：`register(data: UserCreate) → Token`、`login(email, password) → Token`、`getMe() → UserResponse`

**测试**（`frontend/src/__tests__/api.test.ts`，追加）：
1. `test_register_call` — POST `/api/v1/auth/register`
2. `test_login_call` — POST `/api/v1/auth/login`，FormData（OAuth2 格式）
3. `test_getMe_with_auth_header`

**依赖**：Task 9（接口契约）

> **当前状态**：已完成。新增类型及 register/login/getMe 函数，配套测试全部通过。

---

### Task 23：useAuth hook + token 管理 ✅

**创建文件**：`frontend/src/hooks/useAuth.ts`

```typescript
// 返回 { user, token, login, register, logout, isLoading }
// token 存于 localStorage；请求时附加 Authorization: Bearer {token}
```

**创建文件**：`frontend/src/__tests__/useAuth.test.ts`（6 个测试）：
1. `test_initial_state_no_token`
2. `test_login_stores_token`
3. `test_logout_clears_token`
4. `test_restores_token_from_storage`
5. `test_login_failure_no_token`
6. `test_user_loaded_after_login`

**依赖**：Task 22

> **当前状态**：已完成。成功实现由 localStorage 管理 token 的 useAuth hooks，处理了组件和 React 异步更新，配套的 6 个测试全部通过。

---

### Task 24：登录 / 注册页 ✅

**创建文件**：`frontend/src/pages/LoginPage.tsx`、`RegisterPage.tsx`

- 表单：邮箱 + 密码（注册时含组织名称）
- 提交调用 `useAuth.login/register`
- 成功后跳转至项目列表
- 错误提示（role="alert"）

**创建文件**：`frontend/src/__tests__/LoginPage.test.tsx`（5 个测试）：
1. `test_renders_form`
2. `test_submit_calls_login`
3. `test_error_displayed_on_failure`
4. `test_redirects_on_success`
5. `test_link_to_register`

**依赖**：Task 23

> **当前状态**：已完成。成功创建了包含受控表单的 LoginPage 和 RegisterPage 组件，以及针对 LoginPage 组件完整的 DOM 交互测试，测试 100% 通过。

---

### Task 25：项目列表页 ✅

**创建文件**：`frontend/src/pages/ProjectListPage.tsx`

- 列出当前租户所有项目（调用 `GET /api/v1/projects`）
- 状态徽章：pending / processing / completed / failed
- 点击项目 → 进入项目详情页
- "新建项目"按钮 → 打开参数配置表单（Task 26）

**创建文件**：`frontend/src/__tests__/ProjectListPage.test.tsx`（5 个测试）：
1. `test_renders_project_list`
2. `test_shows_status_badges`
3. `test_new_project_button`
4. `test_empty_state`
5. `test_click_project_navigates`

**依赖**：Task 22

> **当前状态**：已完成。新增了项目列表页组件和相关测试。同时修改了 api/client.ts 的内部逻辑使其支持附加 Authorization Headers，顺利修复并验证了之前所有的相关测试。共有 56 个单元测试全部通过。

---

### Task 26：参数配置表单组件 F-04 ✅

**修改文件**：`frontend/src/components/UploadForm.tsx`（或提取为 `ParametersForm.tsx`）

新增 6 个基础参数输入（时间选择器 + vacances 下拉），默认值与 PRD F-04 一致：

| 字段 | 类型 | 默认值 |
|------|------|--------|
| hpm_debut | time input | 07:00 |
| hpm_fin | time input | 09:00 |
| hps_debut | time input | 17:00 |
| hps_fin | time input | 19:30 |
| vacances | select | A |
| pays | hidden | france |

**创建文件**：`frontend/src/__tests__/ParametersForm.test.tsx`（6 个测试）：
1. `test_renders_all_fields`
2. `test_default_values`
3. `test_vacances_options` — A/B/C/全部四个选项
4. `test_submit_with_params`
5. `test_disabled_while_loading`
6. `test_time_field_validation`

**依赖**：Task 22

> **当前状态**：已完成。成功修改了 UploadForm 以支持额外的 5 个基础参数录入，以及客户端时间范围简单验证，同时补全了所有 DOM 交互测试，单元测试全部通过。

---

### Task 27：在线结果表格组件 F-06

**创建文件**：`frontend/src/components/ResultTable.tsx`

- Props：`projectId: string`, `tableName: string`
- 调用 `GET /tables/{tableName}?skip=&limit=&sort_by=&q=`
- 分页（50/100/200 行可选）、列标题点击排序、顶部文本搜索框
- 显示总行数；加载中显示 skeleton
- 每个表格标签页对应 PRD F-06 中的 A–F 分组

**创建文件**：`frontend/src/__tests__/ResultTable.test.tsx`（8 个测试）：
1. `test_renders_table_headers`
2. `test_renders_rows`
3. `test_pagination_controls`
4. `test_sort_on_header_click`
5. `test_search_input`
6. `test_shows_total_count`
7. `test_loading_state`
8. `test_download_button_per_table`

**依赖**：Task 19（API 契约）、Task 22

---

### Task 28：App 路由 + 状态机更新

**修改文件**：`frontend/src/App.tsx`

引入 React Router（`react-router-dom`）：

```
/login        → LoginPage（公开）
/register     → RegisterPage（公开）
/             → ProjectListPage（需认证）
/projects/:id → ProjectDetailPage（进度 + 结果表格 + 下载）
```

- `AuthGuard` 组件：未登录重定向 `/login`
- `ProjectDetailPage` 组合 `ProgressPanel` + `ResultTable` + `DownloadButton`

**创建文件**：`frontend/src/__tests__/App.test.tsx`（更新原有 5 个测试 + 新增 4 个）：
1. `test_redirects_to_login_if_unauthenticated`
2. `test_shows_project_list_when_authenticated`
3. `test_navigates_to_project_detail`
4. `test_logout_clears_session`

**依赖**：Task 24、25、26、27

---

## 依赖关系与执行顺序

```
GROUP A (基础设施)
  Task 1 → Task 2 → Task 3 (Alembic)
        └→ Task 3 (storage)
        └→ Task 4 (Docker)
        └→ Task 5 (main.py)

GROUP B (认证)         [依赖 A]
  Task 6 (模型) → Task 7 (schemas) → Task 8 (security) → Task 9 (endpoints) → Task 10 (deps)

GROUP C (多租户)       [依赖 B]
  Task 11 → Task 12

GROUP D (Celery)       [依赖 A]
  Task 13 → Task 14 → Task 15

GROUP E (参数校验)     [依赖 B]
  Task 16

GROUP F (结果表格)     [依赖 B + D]
  Task 17 → Task 18 → Task 19 → Task 20
              └→ Task 20b (DWD SQLite 加载，F-09 前置依赖)

GROUP H (前端)         [依赖 B 契约 + F 契约]
  Task 22 → Task 23 → Task 24 ─┐
                  └→ Task 25   │
                  └→ Task 26   ├→ Task 28
  Task 27 ───────────────────────┘
```

**推荐执行批次**：

| Sprint | 任务 | 目标 |
|--------|------|------|
| Sprint 1（基础设施）| Task 1–5 | ✅ 完成（Supabase + Alembic + Docker 就绪） |
| Sprint 2（认证）| Task 6–10 | ✅ 完成（端点受保护，租户隔离，32 测试通过） |
| Sprint 3（租户 + Celery）| Task 11–15 + Task 16 | ✅ 完成（Task 11–15: 26 测试通过；Task 16: 5 测试通过） |
| Sprint 4（结果）| Task 17–20 + **Task 20b** | ✅ 全部完成（Task 17: 3 + Task 18: 7 + Task 20: 2 + Task 20b: 6 测试通过） |
| Sprint 5（前端）| Task 22–28 | 完整前端：登录→项目管理→结果查看 |

---

## 验证：Phase 1 完成标准

### 后端验收

```bash
cd backend
pytest tests/ -v --ignore=tests/integration   # 全部通过（含 56 个 Phase 0 测试）
pytest tests/ -v -m integration               # 需本地 Redis 运行
alembic current                               # 输出 head
```

### 前端验收

```bash
cd frontend
npm run test   # 全部通过（含 Phase 0 的 37 个测试）
```

### 手动验收流程（Transamo 内部试用）

1. 启动服务：`docker compose up`（backend + Redis；或 uvicorn + celery worker）
2. 打开 `http://localhost:5173/register` → 创建账号 + 组织
3. 上传 GTFS ZIP → 配置参数（调整高峰时段）→ 提交
4. 观察 7 步实时进度条
5. 在线查看各结果表（A1–F4）：分页、排序、文本搜索
6. 下载单表 CSV（分号分隔，Excel 可直接打开）
7. 下载全量 ZIP
8. **验证 DWD SQLite**：确认 `output/{project_id}_query.sqlite` 存在，E_1 表含 `jour_type` / `nb_passages` 列（非透视列 `"1"`, `"2"` 等）

**Phase 1 成功标准（PRD v0.5 §10）**：
> Transamo 业务分析人员无需技术指导，独立完成 3 次不同 GTFS 数据集的处理与结果查看；处理结果 DWD SQLite 文件规范化加载，为 Phase 3 LLM Agent 就绪。
