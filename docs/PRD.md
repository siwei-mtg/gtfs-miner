# PRD — GTFS Miner Web（产品需求文档）

**版本**：0.2  
**作者**：Wei SI / Transamo  
**日期**：2026-04-02  
**状态**：待确认

---

## 1. 背景与目标

### 1.1 背景

GTFS Miner 目前是一款 QGIS 桌面插件，面向熟悉 GIS 工具的技术用户。其核心价值在于将 GTFS 原始公共交通数据转化为标准化的业务分析输出（指标表格、空间图层）。

将其迁移为 Web 应用的动机在于：
- **降低使用门槛**：消除对 QGIS 的依赖，让业务分析人员无需安装任何软件即可使用；
- **商业化路径**：以 SaaS 形式对外销售，Transamo 自身作为首个客户；
- **协作与多项目管理**：支持多用户、多数据集的在线管理与历史查阅。

### 1.2 产品目标

| 目标 | 衡量指标 |
|------|---------|
| 业务分析人员无需 QGIS 即可独立完成 GTFS 处理 | 用户完成首次处理任务的成功率 ≥ 90% |
| 支持 Transamo 作为首个租户上线 | MVP（上传 + 处理 + 下载）在 1 周内可演示 |
| 为后续 SaaS 对外销售奠定基础 | 多租户隔离机制验证通过 |

---

## 2. 目标用户

### 2.1 主要用户画像

**业务分析人员（核心用户）**
- 所在机构：交通管理局（AOT）、公共交通运营商、咨询公司（如 Transamo）
- 技术水平：熟悉 Excel、报表工具；不具备 GIS / Python 技能
- 核心诉求：上传 GTFS 数据 → 获得可读的分析结果 → 快速导出/分享
- 痛点：安装 QGIS 插件门槛高；处理过程不透明；结果不易共享

**技术管理员（次要用户）**
- 所在机构：Transamo 或客户 IT 部门
- 核心诉求：管理租户、用户权限；监控任务状态；维护参数配置（日历等）

### 2.2 不在目标范围内的用户

- 需要深度 GIS 分析的 GIS 专家（他们仍可使用 QGIS 插件）
- 需要实时 GTFS-RT 数据处理的场景

---

## 3. 功能范围

### 3.1 MVP（第一周可演示）

MVP 的核心主线：**上传 GTFS → 配置参数 → 异步处理 → 下载结果**

> MVP 可用标准：用户可完成上传、处理、下载全流程。

#### F-01：用户认证与租户管理
- 用户注册 / 登录（邮箱+密码，或 SSO 预留接口）
- 每个租户（组织）数据完全隔离
- 租户内支持多用户（管理员 / 普通成员角色）

#### F-02：项目（数据集）管理
- 用户可创建多个"项目"，每个项目对应一次 GTFS 处理任务
- 项目信息：名称、描述、创建时间、状态（待处理 / 处理中 / 完成 / 失败）
- 支持查看历史项目列表及其结果

#### F-03：GTFS 数据获取（上传 或 目录选择）

**方式 A：手动上传**（所有套餐）
- 支持上传 GTFS ZIP 压缩包
- 上传前做基础格式校验（必需文件是否存在：stops.txt, routes.txt, trips.txt, stop_times.txt）
- 显示文件大小与预计处理时间提示
- 支持文件编码自动检测（UTF-8 / Latin-1 / ASCII）

**方式 B：从目录选择**（Pro / Enterprise）
- 地图界面：OSM 底图（MapLibre GL JS），覆盖法国区域/省级行政边界（GeoJSON 来自 geo.api.gouv.fr）
- 聚合点图层：标注有 GTFS 数据的地理单元，按类别着色：
  - 🟦 **城市网络**（Urbain）：市区公交/有轨电车/地铁
  - 🟩 **城际网络**（Interurbain）：省际客运
  - 🟥 **区域网络**（Régional）：TER、区域大巴
- 用户点击聚合点 → 侧面板展示该区域内的所有可用网络（运营商名称、类别、最后更新日期）
- 选择网络 → 系统后台从 **transport.data.gouv.fr** 自动下载 GTFS ZIP → 进入正常处理流程
- 数据源缓存：目录每 6 小时同步一次；下载的 GTFS ZIP 缓存 24 小时（相同数据集不重复下载）
- 地理范围：**仅法国**（其他国家列入后续版本）

#### F-04：处理参数配置
以下参数以表单形式呈现，分为**基础参数**（所有用户可见）和**高级参数**（折叠，专家用户可展开）：

**基础参数**

| 参数 | 说明 | 默认值 |
|------|------|--------|
| 早高峰开始时间（HPM début） | HH:MM | 07:00 |
| 早高峰结束时间（HPM fin） | HH:MM | 09:00 |
| 晚高峰开始时间（HPS début） | HH:MM | 17:00 |
| 晚高峰结束时间（HPS fin） | HH:MM | 19:30 |
| 假期类型（Vacances） | 下拉：A / B / C / 全部 | A |
| 日历数据源 | 系统内置日历微服务 (支持跨年度同步) | 官方 API (api.gouv.fr) |
| 日历国家/地区 | 下拉：法国（扩展接口预留） | 法国 |

**高级参数**（MVP 中折叠隐藏，V5 开放编辑）

| 参数 | 当前硬编码值 | 说明 |
|------|------------|------|
| 站点聚类距离阈值 | 100 m | 判断两个物理站点是否属于同一通用站点 |
| 大数据集聚类切换阈值 | 5 000 个站点 | 超过此数量切换为 K-Means 预分组 |
| K-Means 分组规模 | 每组 500 个站点 | K-Means 初始 k 值的计算基数 |
| 缺失 direction_id 默认值 | 999 | 占位符值 |
| 缺失 route_type 默认值 | 3（bus） | 缺失交通模式时的回退类型 |
| 缺失 location_type 默认值 | 0（物理站点） | 站点类型缺失时的回退 |

#### F-05：异步处理与实时进度

- 提交后立即返回，任务在后台异步执行
- **WebSocket** 实时推送处理进度，前端展示步骤条：

```
待处理 → 文件读取 → 数据标准化 → 站点聚类
       → 路线/行程生成 → 日历处理 → 指标计算 → 完成
```

- 每步显示当前步骤名称 + 累计用时
- 处理完成后，**邮件通知**用户（含项目直链）
- 处理失败时：显示具体错误摘要（如：缺少必需文件、坐标格式错误），并提供常见问题排查提示

#### F-06：结果查看（在线表格）

处理结果存入数据库，支持在线分页查看。表格分组展示：

**A. 停靠站**
- A_1 通用站点（Arrêts Génériques）
- A_2 物理站点（Arrêts Physiques）

**B. 线路**
- B_1 线路（Lignes）
- B_2 子线路（Sous-Lignes）

**C. 行程**
- C_1 班次（Courses）
- C_2 行程详情（Itinéraire）
- C_3 弧段行程（Itinéraire Arc）

**D. 服务日历**
- D_1 服务日期（Service Dates）
- D_2 日类型（Service Jourtype）

**E. 通过次数**
- E_1 站点通过次数
- E_4 弧段通过次数

**F. 指标**
- F_1 线路班次数
- F_2 子线路特征（发车间隔等）
- F_3 线路 KCC（公里班次数）
- F_4 子线路 KCC

表格交互要求：
- 分页显示（每页 50 / 100 / 200 行可选）
- 列标题点击排序
- 简单文本筛选
- 显示总行数

#### F-07：结果下载
- 支持单表 CSV 下载
- 支持一键打包下载全部结果（ZIP，含所有 CSV）
- CSV 格式：分号分隔（`;`）、UTF-8 with BOM（兼容 Excel）

---

### 3.2 后续版本路线图

#### V2：交互式地图

| 图层 | 说明 |
|------|------|
| G_1 子线路轨迹 | 矢量线，按线路着色 |
| G_2 线路轨迹 | 聚合线路 |
| E_1 站点通过热力 | 点图层，气泡大小 = 通过次数 |
| E_4 弧段通过热力 | 线图层，线宽 = 通过次数 |

功能：底图切换（OSM / 空白）、图层开关、要素点击弹窗、地图导出（PNG / PDF）

#### V3：REST API

```
POST   /api/v1/projects                        创建项目
POST   /api/v1/projects/{id}/upload            上传 GTFS
GET    /api/v1/projects/{id}/status            查询处理状态（含 WebSocket 端点）
GET    /api/v1/projects/{id}/tables/{name}     获取指定表格（JSON / CSV）
GET    /api/v1/projects/{id}/download          下载全部结果 ZIP
```

#### V4：多国日历支持 + 目录扩展到其他国家
- 日历配置抽象接口
- 支持上传自定义假期日历（CSV 格式）
- 内置：法国（当前）→ 比利时、瑞士等（待定）
- F-03 目录选择扩展到法国以外（数据源：Transitland API + Mobility Database）

#### V5：高级参数配置界面
- F-04 高级参数区域开放编辑（站点聚类阈值、K-Means 参数等）
- 参数模板：可将常用配置保存为模板，跨项目复用
- 路线类型映射自定义（route_type 对照表）

#### V6：数据集版本对比（高业务价值）
- 同一线路网不同时期 GTFS 数据集横向对比
- 可比指标：班次数变化、KCC 变化、覆盖站点变化、发车间隔变化
- 差异报告导出

---

## 4. 不在范围内

- GTFS-RT（实时数据）处理
- Access 数据库导出（legacy）
- SNCF 专用逻辑（GTFS_algorithm.py legacy）
- GIS 专家级编辑功能
- 移动端适配（桌面浏览器优先）

---

## 5. 技术架构建议

> 选型原则：**易维护、易部署、高性能**。

### 5.1 总体架构

```
浏览器（React + TypeScript）
    ↓ HTTPS / WebSocket
API 网关（FastAPI）
    ├── 认证服务（JWT + OAuth2）
    ├── 项目管理 API
    ├── 日历服务 (Calendar Service: API Sync + DB)
    ├── 文件上传 API
    ├── 任务状态 WebSocket
    └── 结果查询 API
            ↓
任务队列（Celery + Redis）
    └── Worker：现有 Python 处理逻辑（零修改复用）
            ↓
数据库（Supabase / PostgreSQL）
    ├── 用户 / 租户 / 项目元数据
    ├── 日历数据（calendar_dates 表，取代本地 Excel）
    └── 处理结果表（分表存储，按 project_id 索引）
            ↓
对象存储（Supabase Storage / S3）
    └── 原始 GTFS 上传文件、结果 ZIP 归档
```

### 5.2 技术栈

| 层级 | 技术 | 理由 |
|------|------|------|
| 后端 API | **FastAPI (Python)** | 与现有处理逻辑同语言；原生 WebSocket；自动生成 OpenAPI 文档 |
| 任务队列 | **Celery + Redis** | 成熟异步方案；支持进度回调；Worker 可横向扩展 |
| 前端 | **React + TypeScript** | 生态成熟；Ant Design 表格组件开箱即用 |
| 数据库 | **Supabase（PostgreSQL）** | 托管 PG；内置 Row Level Security；Storage + Auth 一体；免运维 |
| 对象存储 | **Supabase Storage**（MVP）/ AWS S3（扩展） | S3 兼容；与 DB 同平台；大文件上传/下载与应用层解耦 |
| 地图（V2） | **MapLibre GL JS** | 开源；矢量渲染性能好；适合大数据集 |
| 容器化 | **Docker Compose（开发）/ Kubernetes（生产）** | 标准部署；多服务编排 |
| 实时通信 | **WebSocket**（FastAPI 原生支持） | 任务进度实时推送 |
| 邮件通知 | **SMTP / SendGrid** | 任务完成通知 |

### 5.2a Supabase 接入迁移步骤

> **背景**：Phase 0 使用 SQLite 快速验证流程；Phase 1 MVP 前迁移至 Supabase，无需改动 Worker 逻辑。

| 步骤 | 改动文件 | 说明 |
|------|---------|------|
| 1. 配置连接串 | `backend/.env`（新建，加入 `.gitignore`） | 写入 Supabase PostgreSQL URI（psycopg2 格式） |
| 2. 更新 Settings | `backend/app/core/config.py` | `DATABASE_URL` 改读 `.env`；预留 `SUPABASE_URL` / `SUPABASE_ANON_KEY` 字段 |
| 3. 移除 SQLite 参数 | `backend/app/db/database.py` | 删 `check_same_thread: False`；加 `pool_pre_ping=True` 及连接池配置 |
| 4. 添加驱动 | `backend/requirements.txt` | 加 `psycopg2-binary`（同步驱动，匹配 Worker 同步模式） |
| 5. 补充 Model | `backend/app/db/models.py` | 新增 `CalendarDate` 表（按 `CALENDAR_SERVICE_PLAN.md` Schema） |
| 6. Alembic 迁移 | `backend/alembic/`（初始化） | `alembic init` → `alembic revision --autogenerate` → `alembic upgrade head` 建表到 Supabase |
| 7. 存储替换（Phase 1）| `backend/app/services/worker.py` | 将本地 `storage/projects/` 输出改写入 Supabase Storage Bucket |

> `worker.py` 核心处理逻辑**无需改动**，SQLAlchemy ORM 对 SQLite/PostgreSQL 透明。

### 5.3 多租户隔离策略

- **应用层**：所有查询附加 `tenant_id` 过滤；PostgreSQL Row Level Security 作为兜底
- **存储层**：对象存储路径前缀 `/{tenant_id}/projects/{project_id}/`
- **任务层**：初期共享 Worker 池；规模化后可按租户隔离队列

### 5.4 处理逻辑迁移策略

现有 Python 模块几乎可以**零修改**复用：

```
gtfs_norm.py         → 直接复用
gtfs_spatial.py      → 直接复用
gtfs_generator.py    → 直接复用
gtfs_export.py       → 直接复用（去除 QGIS 依赖部分）
gtfs_utils.py        → 直接复用
gtfs_qgis_adapter.py → 替换为 geopandas + GeoJSON 输出（V2 地图）
GTFS_algorithm.py    → 不迁移（legacy，保留备用）
```

唯一需要替换的依赖：**QGIS** → **geopandas + shapely**

### 5.5 结果存储策略

处理结果同时存储于两处：
- **PostgreSQL**：各输出表数据，支持在线分页查询（F-06）
- **对象存储**：结果全量 ZIP 归档，供下载使用（F-07）

每张输出表对应数据库中一张表（如 `result_a1_arrets_generiques`），加 `project_id` 外键索引。

---

## 6. 商业模式

### 6.1 定价策略：分级订阅（按项目数 + 用户数）

| 套餐 | 活跃项目数 | 用户数 | 数据保留期 | 大数据集支持 | 定价参考 |
|------|-----------|--------|-----------|------------|---------|
| **Free** | 2 | 1 | 30 天 | 否（≤5K 站点）| 免费 |
| **Pro** | 10 | 5 | 12 个月 | 否 | 待定 €/月 |
| **Enterprise** | 无限 | 无限 | 自定义 | 是（IDFM 级） | 定制报价 |

> **大数据集**（>5 万停靠站，如 IDFM）仅在 Enterprise 套餐开放，原因：单次处理消耗算力显著高于普通数据集（30 分钟 vs 5 分钟）。

### 6.2 V6 数据集对比功能定位

版本对比作为 Pro / Enterprise 套餐的**差异化卖点**，对 Transamo 等咨询公司具有高商业价值（用于交通网络调整前后效果评估）。

---

## 7. 硬编码规则清单

以下规则当前硬编码在代码中，未来可分阶段开放配置（对应 V5 高级参数）：

### 高优先级（直接影响结果）

| 规则 | 当前值 | 位置 | 说明 |
|------|-------|------|------|
| 站点聚类距离阈值 | **100 m** | `gtfs_spatial.py:33` | 层次聚类截断高度；决定通用站点（AG）划分粒度 |
| 大数据集切换阈值 | **5 000 站点** | `GTFS_algorithm.py:454` | 超过此数量使用 K-Means 预聚类 |
| K-Means 分组基数 | **500 站点/组** | `gtfs_norm.py:174` | 计算初始 k 值：`k = len(stops) / 500` |

### 中优先级（影响数据解读）

| 规则 | 当前值 | 位置 | 说明 |
|------|-------|------|------|
| 缺失 direction_id 默认值 | **999** | `gtfs_generator.py:38` | 无方向信息时的占位符 |
| 缺失 route_type 默认值 | **3（bus）** | `gtfs_norm.py:64` | 缺失交通模式回退为公交 |
| 缺失 location_type 默认值 | **0（物理站点）** | `gtfs_norm.py:47` | 缺失站点类型回退为物理站点 |
| 输出方向筛选 | **direction_id == 0** | `gtfs_export.py:24` | O/D 分析时只取主方向 |
| 距离单位 | **/ 1000（米→千米）** | `gtfs_generator.py:148` | KCC 输出单位 |

### 低优先级（内部编号/技术参数）

| 规则 | 当前值 | 位置 | 说明 |
|------|-------|------|------|
| 通用站点 ID 偏移 | **+10 000** | `gtfs_spatial.py:36` | AG 编号前缀偏移 |
| 物理站点 ID 偏移 | **+100 000** | `gtfs_spatial.py:37` | AP 编号前缀偏移 |
| 编码探测采样大小 | **10 000 字节** | `gtfs_utils.py:91` | chardet 采样量 |
| 交通模式名称映射 | 见下 | `gtfs_norm.py:74` | route_type 0–12 对应的法语名称 |

```
0 → tramway, 1 → metro, 2 → train, 3 → bus,
4 → ferry,   5 → cable, 6 → telephe, 7 → funiculaire,
11 → trolley, 12 → monorail
```

---

## 8. 非功能性需求

| 需求 | 目标 |
|------|------|
| 可用性 | 99.5% 月度在线率 |
| 处理性能（普通） | 中型数据集（~5K 站点，~1M stop_times）≤ 10 分钟 |
| 处理性能（大型） | IDFM 规模（54K 站点，19M stop_times）≤ 30 分钟 |
| 并发处理 | 初期 5 个并发 Worker；可横向扩展 |
| 文件上传限制 | 初期 500 MB / ZIP；大文件考虑分片上传 |
| 数据保留 | 按套餐定义（30 天 / 12 个月 / 自定义） |
| 安全性 | HTTPS 全程；JWT 有效期 24h；租户数据隔离 |
| 浏览器兼容 | Chrome / Edge / Firefox 最新两个大版本 |

---

## 9. 里程碑规划

### Phase 0 — 技术验证（第 1 周）
**目标**：端到端流程可演示，不考虑多租户

- [ ] FastAPI + Celery 项目脚手架
- [ ] GTFS ZIP 上传接口
- [ ] 现有 Python 处理逻辑接入 Worker
- [ ] WebSocket 实时进度推送
- [ ] 处理完成后结果 ZIP 可下载
- [ ] 最简前端：上传 → 进度条 → 下载

**不包含**：认证、多租户、在线表格、地图

---

### Phase 1 — MVP（第 2–4 周）
- [ ] 用户认证（注册/登录）
- [ ] 多租户隔离（应用层 + 存储层）
- [ ] 项目管理（创建/列表/历史）
- [ ] 参数配置表单（F-04 基础参数）
- [ ] 邮件通知（任务完成）
- [ ] 在线结果表格查看（F-06，结果存入 PostgreSQL）
- [ ] 单表 / 全量 CSV 下载（F-07）
- [ ] Transamo 内部试用

---

### Phase 2 — 地图（第 4–8 周）
- [ ] 路线轨迹图层（MapLibre）
- [ ] 站点 / 弧段通过热力图
- [ ] 地图导出

---

### Phase 3 — API & 扩展（第 8–12 周）
- [ ] REST API + API Key 鉴权
- [ ] 自定义假期日历上传（多国支持基础）
- [ ] 性能优化（大数据集）
- [ ] V5 高级参数配置界面

---

### Phase 4 — 数据集对比（待排期）
- [ ] 同一网络多版本 GTFS 对比
- [ ] 差异指标报告

---

## 10. 成功标准

| 阶段 | 成功标准 |
|------|---------|
| Phase 0 | 技术团队完成一次端到端处理演示（上传→处理→下载） |
| Phase 1 | Transamo 业务分析人员无需技术指导，独立完成 3 次不同 GTFS 数据集的处理与结果查看 |
| Phase 2 | 用户可在地图上定位任意线路并查看其通过频次 |
| SaaS 商业化 | 第一个付费外部客户成功完成 onboarding |

---

## 11. 开放问题（已关闭）

| # | 问题 | 决策 |
|---|------|------|
| Q1 | 进度通知实时性 | ✅ WebSocket 实时推送 |
| Q2 | 硬编码规则开放范围 | ✅ MVP 隐藏，V5 开放高级参数配置 |
| Q3 | 定价模型 | ✅ 分级订阅（按项目数 + 用户数），大数据集仅 Enterprise |
| Q4 | 结果存储 | ✅ PostgreSQL（在线查询）+ 对象存储（ZIP 下载） |
| Q5 | Transamo 可用标准 | ✅ 上传 + 处理 + 下载即算可用 |
| Q6 | 数据集版本对比 | ✅ 高业务价值，列入 Phase 4 |

---

*版本 0.2 — 所有开放问题已关闭，文档进入实现准备阶段。*
