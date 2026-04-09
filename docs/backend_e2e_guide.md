# 后端全流程梳理：端到端运行 + Human-in-the-Loop 节点

> 最后更新：2026-04-06 | 适用阶段：Phase 0 MVP

## 背景

`backend/app/services/gtfs_core/` 中的核心算法为手写代码；API 层、Worker、DB、WebSocket 等脚手架由 AI 根据 PRD 生成。本文档梳理后端从启动到产出结果的完整流程，以及需要人类介入的决策节点。

---

## 一、后端"全部跑通"的完整流程

### 第 0 步：启动服务

```bash
cd backend
# venv 位于 backend/.venv/（Windows）
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

> **Windows 注意**：`--reload` 模式在 Windows 上存在 socket 继承问题，启动时去掉该参数。

启动后自动完成：
- SQLite 数据库创建（`storage/miner_app.db`）
- 存储目录创建（`storage/temp/`、`storage/projects/`）
- Swagger 文档就绪：`http://localhost:8000/docs`

### 第 1 步：创建项目（人类操作）

```
POST /api/v1/projects/
Body: {
  "hpm_debut": "07:00",       ← 早高峰起始
  "hpm_fin":   "09:00",       ← 早高峰结束
  "hps_debut": "17:00",       ← 晚高峰起始
  "hps_fin":   "19:30",       ← 晚高峰结束
  "vacances":  "A",           ← 假期区域（A / B / C / 全部）
  "pays":      "FR"
}
返回: { "id": "uuid-xxx", "status": "pending", ... }
```

### 第 2 步：上传 GTFS ZIP（人类操作）

```
POST /api/v1/projects/{project_id}/upload
Form: file = gtfs.zip
```

上传后：
- ZIP 保存到 `storage/temp/{project_id}_{filename}.zip`
- 状态变更：`pending → uploading → pending → processing`
- **后台任务自动启动**（`worker.py` → `run_project_task_sync`）

### 第 3 步：自动处理（7 步流水线，无需人工干预）

| 步骤 | 做什么 | 输出文件 |
|------|--------|---------|
| [1/7] | 解压读取 GTFS `.txt` 文件 | — |
| [2/7] | 标准化所有表（编码检测、字段补全、ID 映射） | — |
| [3/7] | 空间聚类：物理站点 → 通用站点 | `A_1_Arrets_Generiques.csv`, `A_2_Arrets_Physiques.csv` |
| [4/7] | 生成行程、弧段、班次 | `C_1_Courses.csv`, `C_2_Itineraire.csv`, `C_3_Itineraire_Arc.csv` |
| [5/7] | 生成线路、子线路 | `B_1_Lignes.csv`, `B_2_Sous_Lignes.csv` |
| [6/7] | 展开日历、生成服务日期 | `D_1_Service_Dates.csv`, `D_2_Service_Jourtype.csv` |
| [7/7] | 计算通过次数与 KCC 指标 | `E_1`, `E_4`, `F_1` ~ `F_4` |

处理期间，WebSocket（`/api/v1/projects/{id}/ws`）实时推送进度消息：

```json
{
  "project_id": "uuid",
  "status": "processing",
  "step": "[3/7] 空间聚类生成站点映射（1234 停靠站，56 线路，789 班次）",
  "time_elapsed": 12.34,
  "error": null
}
```

### 第 4 步：获取结果（人类操作）

```
GET /api/v1/projects/{project_id}           ← 查看状态（completed / failed）
GET /api/v1/projects/{project_id}/download   ← 下载全部 CSV 的 ZIP 包
```

**全部跑通的标志：** 状态从 `pending` 走到 `completed`，下载得到包含 16 个 CSV 文件的 ZIP 包。

---

## 二、Human-in-the-Loop 节点分析

### 当前 Phase 0 的流程图

```
 ┌─────────────┐     ┌──────────────┐     ┌───────────────────┐     ┌──────────────┐
 │  创建项目    │ ──→ │  上传 GTFS   │ ──→ │  自动处理 7 步     │ ──→ │  下载结果    │
 │  (设参数)    │     │  (.zip)      │     │  (无人工干预)      │     │  (检查 CSV)  │
 └─────────────┘     └──────────────┘     └───────────────────┘     └──────────────┘
       ↑                                         │
       │                                         ↓ 失败时
       │                                  ┌──────────────┐
       └──────────────────────────────────│  查看错误     │
                                          │  调整后重试   │
                                          └──────────────┘
```

**结论：当前只有 3 个人类节点：**

| # | 节点 | 人类做什么 | 对应 API |
|---|------|-----------|---------|
| 1 | **创建项目** | 设定高峰时段、假期区域 | `POST /api/v1/projects/` |
| 2 | **上传数据** | 选择并上传 GTFS ZIP | `POST /api/v1/projects/{id}/upload` |
| 3 | **获取结果** | 下载 ZIP / 处理失败时排查错误 | `GET /api/v1/projects/{id}/download` |

### PRD 规划但尚未实现的 HITL 节点

| 缺失节点 | PRD 阶段 | 说明 |
|----------|---------|------|
| **用户认证 / 登录** | Phase 1 | 目前无 auth，任何人可操作 |
| **数据源选择（地图点选）** | Phase 1 Pro | 从 transport.data.gouv.fr 自动下载，替代手动上传 |
| **在线浏览结果表格** | Phase 1 | `get_table_data` 目前是空 stub（返回空数据） |
| **地图可视化查看** | Phase 2 | 线路轨迹、热力图 |
| **参数高级配置** | Phase 3+ | 聚类距离阈值、route_type 映射等目前是硬编码常量 |

---

## 三、关键源文件索引

| 组件 | 文件路径 | 职责 |
|------|---------|------|
| 入口 | `backend/app/main.py` | FastAPI 应用启动、挂载路由 |
| 配置 | `backend/app/core/config.py` | 路径、数据库连接串 |
| 数据库 | `backend/app/db/database.py` | SQLAlchemy engine & session |
| 模型 | `backend/app/db/models.py` | `Project` ORM（单表） |
| API | `backend/app/api/endpoints/projects.py` | REST 端点（6 个） |
| WebSocket | `backend/app/api/websockets/progress.py` | 实时进度推送 |
| 请求模型 | `backend/app/schemas/project.py` | Pydantic 输入/输出 schema |
| **Worker** | `backend/app/services/worker.py` | 后台任务编排（调用 gtfs_core） |
| **Pipeline** | `backend/app/services/gtfs_core/pipeline.py` | 流水线配置与日期表构建 |
| 读取 | `backend/app/services/gtfs_core/gtfs_reader.py` | ZIP/目录读取 |
| 标准化 | `backend/app/services/gtfs_core/gtfs_norm.py` | GTFS 表标准化 |
| 空间 | `backend/app/services/gtfs_core/gtfs_spatial.py` | 站点聚类 |
| 生成 | `backend/app/services/gtfs_core/gtfs_generator.py` | 行程/日历/指标生成 |
| 导出 | `backend/app/services/gtfs_core/gtfs_export.py` | CSV 格式化输出 |

---

## 四、验证方法

### 方式 A：跑自动化测试

```bash
cd backend

# 快速单元测试
gtfs\Scripts\python.exe -m pytest -v -m "not slow"

# 端到端集成测试（创建项目 → 上传 → 轮询 → 验证输出 → 下载）
gtfs\Scripts\python.exe -m pytest tests/test_api_pipeline_integration.py -v -s
```

测试数据位于 `backend/tests/Resources/raw/`（SEM、SOLEA、ginko 三个最小样本）。

### 方式 B：Swagger UI 手动操作

1. 启动服务：`uvicorn app.main:app --reload`
2. 打开 `http://localhost:8000/docs`
3. 按顺序调用：
   - `POST /api/v1/projects/` — 创建项目
   - `POST /api/v1/projects/{id}/upload` — 上传 `tests/Resources/raw/` 中的 ZIP
   - `GET /api/v1/projects/{id}` — 轮询直到 `status = "completed"`
   - `GET /api/v1/projects/{id}/download` — 下载结果 ZIP

---

## 五、已知问题与风险

| # | 问题 | 影响 | 严重度 |
|---|------|------|--------|
| 1 | `LocalXlsCalendarProvider` 依赖 `resources/Calendrier.xls` | 文件缺失时回退到 `Type_Jour`（功能降级但不崩溃） | 低 |
| 2 | `get_table_data` 是空 stub | 前端表格浏览功能不可用 | 中 |
| 3 | 无错误重试机制 | 处理失败后只能重新上传 | 低 |
| 4 | 无文件大小限制 | 大 GTFS 数据集可能导致 OOM | 中 |
| 5 | CORS 全开（`allow_origins=["*"]`） | 仅限开发环境使用 | 低（开发阶段） |
| 6 | 无用户认证 | 任何人可创建项目和上传文件 | 高（生产前必须解决） |
