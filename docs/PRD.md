# PRD — GTFS Miner Web（产品需求文档）

**版本**：0.7  
**作者**：Wei SI / Transamo  
**日期**：2026-04-12  
**状态**：Phase 0 ✅ 已完成，Phase 1 ✅ 技术完成（待 Transamo 内部试用），Phase 2 🔄 进行中（Task 41-44 ✅）

---

## 1. 背景与目标

### 1.1 背景

GTFS Miner 目前是一款 QGIS 桌面插件，面向熟悉 GIS 工具的技术用户。其核心价值在于将 GTFS 原始公共交通数据转化为标准化的业务分析输出（指标表格、空间图层）。

将其迁移为 Web 应用的动机在于：
- **降低使用门槛**：消除对 QGIS 的依赖，让业务分析人员无需安装任何软件即可使用；
- **商业化路径**：以 SaaS 形式对外销售，Transamo 自身作为首个客户；
- **协作与多项目管理**：支持多用户、多数据集的在线管理与历史查阅；
- **LLM 驱动的自然语言洞察**：让 GTFS 数据真正可对话——用户通过提问派生自定义指标，超越静态表格输出，无需编写代码。

### 1.2 产品目标

> **核心定位**：一键将原始 GTFS 数据转化为公共交通分析洞察——覆盖三层价值：标准化处理 → 可视化看板 → LLM 自然语言查询与指标派生。

| 目标 | 衡量指标 |
|------|---------|
| 一键将原始 GTFS 数据转化为公共交通分析洞察 | 用户从上传到获得首个洞察结果的成功率 ≥ 90% |
| 支持 Transamo 作为首个租户上线 | MVP（上传 + 处理 + 下载）在 1 周内可演示 |
| 为后续 SaaS 对外销售奠定基础 | 多租户隔离机制验证通过 |
| 用户可通过自然语言查询派生自定义指标，无需编写代码 | Phase 3 上线后，用户自主派生指标准确率 ≥ 80% |

---

## 2. 目标用户

### 2.1 主要用户画像

**业务分析人员（核心用户）**
- 所在机构：交通管理局（AOT）、公共交通运营商、咨询公司（如 Transamo）
- 技术水平：熟悉 Excel、报表工具；不具备 GIS / Python 技能
- 核心诉求：上传或在线选择 GTFS 数据集 → 获得可读的分析结果 → 获得清洗过的、以便于深入分析的数据集 → 通过自然语言提问获得洞察、自定义派生指标 → 快速导出/分享
- 痛点：使用要求用户已有 QGIS 软件；作为 QGIS 插件开发者难以变现；处理结果为静态 CSV，无法直接提问，指标扩展需技术人员介入

**技术管理员（次要用户）**
- 所在机构：Transamo 或客户 IT 部门
- 核心诉求：管理租户、用户权限；监控任务状态；维护参数配置（日历等）

### 2.2 不在目标范围内的用户

- 需要深度分析的数据专家

---

## 3. 功能范围

### 3.1 MVP（第一周可演示）

MVP 的核心主线：**上传 GTFS → 配置参数 → 异步处理 → 查看洞察 → 下载结果**

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
| 日历数据源 | 系统内置日历微服务（DB 驱动，每周自动同步 api.gouv.fr）⚠️ 定期同步尚未接入调度器，手动录入数据仅至 2027-12（TD-004） | 官方 API (api.gouv.fr) |
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

#### F-08：数据看板（Dashboard）

处理完成后，在结果页提供交互式数据看板，包含图表、表格与地图三类视图，支持联动筛选。

**图表视图**
- 饼状图：线路交通模式（route_type）构成、高峰/平峰班次占比
- 柱状图：各线路班次数对比、KCC 排行、各时段通过次数

**动态表格视图**
- 基于 F-06 的结果表（A–F 组），新增字段筛选器（多选下拉 + 数值范围）
- 勾选/过滤行时，图表与地图同步高亮对应数据

**GIS 地图视图（空间饼状图）**
- 底图：MapLibre GL JS（OSM）
- 站点层：每个通用站点（AG）以**空间饼状图**标注，扇区 = 途经线路的 route_type 构成（按通过次数加权）
- 点击 AG → 侧面板展示该站点的详细指标（途经线路列表、各时段通过次数）

**联动筛选**
- 图表区、表格区、地图三者双向联动：
  - 在表格中筛选字段（如 route_type = tramway）→ 图表重算、地图高亮对应 AG
  - 在地图点击/框选区域 → 表格过滤为区域内 AG 的数据、图表同步
  - 图表扇区/柱体点击 → 表格 + 地图同步过滤

**套餐限制**
- Free：图表 + 表格（基础筛选）；地图空间饼状图仅 Pro/Enterprise 开放

---

### 3.2 后续版本路线图

#### F-10：UI/UX 设计系统（Phase 2 前置）

**目标**：内部工具级视觉质量（对标 Retool / Linear：干净、高信息密度、无多余动效），确保 Phase 2 地图与看板组件具备统一的设计基础。

**技术方案**：Tailwind CSS v4 + shadcn/ui（组件按需复制到项目，无版本锁定）

**设计令牌**：
- 主色（primary）：紫色系（与现有 `--accent: #aa3bff` 对齐）
- 中性色（neutral）、危险色（destructive）：shadcn 默认
- 间距、圆角、阴影：Tailwind 默认体系

**交付范围**：
- 核心 shadcn 组件：Button、Card、Badge、Input、Select、Tabs、Table、Dialog、Sonner（Toast）、Progress
- 页面重构：LoginPage、RegisterPage、ProjectListPage、ProjectDetailPage（含 ProgressPanel）、UploadForm、ResultTable
- AppShell：统一顶栏（Logo + 用户信息 + 退出）、最大宽度 1280px 响应式容器

**组件架构**：遵循 Atomic Design 原则（`docs/atomic-design.md`），目录分层 atoms / molecules / organisms / templates / pages；规则强制写入 `CLAUDE.md §前端组件架构`。

**不包含**：品牌视觉设计（logo、插画）、移动端深度优化、i18n

---

#### F-09：LLM 智能查询与自定义指标派生（Phase 3）

处理结果不再是只能下载的静态 CSV——用户可通过自然语言与数据对话，Agent 自主推导并持久化自定义指标。

**架构**：ReAct Agent（Claude API tool_use）+ DWD SQLite（pipeline 完成后自动加载）

**工具箱**：

| 工具 | 作用 |
|------|------|
| `query_dwd(sql)` | 在 DWD SQLite 上执行 SQL，核心计算工具 |
| `describe_table(name)` | 返回实时表结构 + 示例行，供 Agent 自主探索 schema |
| `list_indicators()` | 列出已有 E_*/F_* 及用户自定义指标 |
| `spatial_filter(stops, center, radius_m)` | 地理围栏筛选（SQL 无法表达的空间查询） |
| `save_indicator(name, sql, description)` | 将派生指标持久化至 `custom_indicators` 表 |
| `explain_result(df)` | 将数字结果翻译为交通业务语言 |

**核心功能**：
- 自然语言查询处理结果（"周一早高峰通过次数最多的前 10 个站点"）
- 多步推导复杂指标（Agent 自动拆解问题、链式调用工具、SQL 报错时自动修正重试）
- **派生指标持久化**：`save_indicator` 将一次性分析沉淀为可复用的自定义指标，跨会话保留，相当于用户与 Agent 协作持续扩展指标层
- 前端：对话框 UI，支持查看生成的 SQL 与结果表格

**套餐限制**：Free 限每项目 3 个自定义指标；Pro/Enterprise 不限

**数据层关系**：

```
DWD 层（A_*/B_*/C_*/D_*）  ←  Agent 的计算原料
    ↓ pipeline 固化
指标层（E_*/F_*）           ←  可直接查询
    ↓ save_indicator
自定义指标层（custom_indicators 表）  ←  随使用持续增长
```

#### V2：交互式地图 + 数据看板

**地图图层**

| 图层 | 说明 |
|------|------|
| E_1 站点通过 | 点图层，每个 AG 以**空间饼状图**标注，扇区 = 途经线路 route_type 构成（按通过次数加权） |
| E_4 弧段通过 | 线图层，**线宽 = 通过量大小**；具有方向性：A→B 通过量绘制在 A→B 弧段的**右侧**，B→A 通过量绘制在 B→A 弧段的**右侧**（两个方向的弧段在地图上重叠为一条线，通过左右偏移区分方向） |

功能：底图切换（OSM / 空白）、图层开关、要素点击弹窗、**GeoPackage 导出**（含所有矢量图层）

**GeoPackage 导出内存策略**：导出时真正的内存瓶颈在构建 GeoDataFrame（geopandas join + geometry 构造），而非写文件格式本身。对 IDFM 规模（~5 万站点、数千弧段）的数据集，全量一次性构建 GeoDataFrame 峰值内存约 800 MB–1.2 GB。为控制内存：
- `export_geopackage()` 按图层逐个处理（passage_ag → passage_arc），写完即释放
- 同一图层数据量过大时按 AG 分批构建（每批 ≤ 500 个 AG），用 `fiona` append 模式追加写入
- 格式保持 GeoPackage（单文件多图层，MapLibre / QGIS 均原生支持）；不改用 GeoJSON（整体序列化，内存更高）

**数据看板**（F-08）
- 饼状图 / 柱状图：线路模式分布、班次数、KCC 对比
- 动态表格：字段多选筛选 + 数值范围过滤
- 空间饼状图：AG 层按途经线路 route_type 构成显示
- 三视图双向联动筛选

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
    ├── 结果查询 API
    └── /query → LLM Agent（ReAct，Claude API tool_use）
              ├── query_dwd    → DWD SQLite（{project_id}_query.sqlite）
              │                  E_*/F_* 已 melt 规范化；pipeline 完成后自动加载
              ├── spatial_filter → Python / Shapely
              └── save_indicator → custom_indicators 表（PostgreSQL）
            ↓
任务队列（Celery + Redis）
    └── Worker：现有 Python 处理逻辑（零修改复用）
            ↓
数据库（Supabase / PostgreSQL）
    ├── 用户 / 租户 / 项目元数据
    ├── 日历数据（calendar_dates 表，取代本地 Excel）
    ├── 处理结果表（分表存储，按 project_id 索引）
    └── custom_indicators（用户派生指标：name, sql, description, project_id）
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
| 对象存储 | **Cloudflare R2**（S3 兼容，boto3 原生） | 10 GB 免费；通过自定义域名 CF 代理，国内可达；与 DB 无耦合 |
| 地图（V2） | **MapLibre GL JS** | 开源；矢量渲染性能好；适合大数据集 |
| 容器化 | **Docker（开发/生产）/ Zeabur（云部署，香港节点）** | push-to-deploy，国内直连，无需代理 |
| 实时通信 | **WebSocket**（FastAPI 原生支持） | 任务进度实时推送 |
| LLM Agent | **Claude API（claude-sonnet-4-6）+ tool_use** | ReAct 循环；tool_use 原生支持工具调用；无需 LangChain 等框架 |

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
| 7. 存储替换（Phase 1）| `backend/app/services/storage.py`（新建）、`worker.py` | 将本地 `storage/projects/` 输出通过 `storage.upload_file()` 写入 **Cloudflare R2**；`use_r2` 标志控制开发/生产切换 |

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

### Phase 0 — 技术验证（第 1 周）✅ 已完成
**目标**：端到端流程可演示，不考虑多租户

- [x] FastAPI + BackgroundTasks 项目脚手架（Phase 0 不含 Celery，Phase 1 引入）
- [x] GTFS ZIP 上传接口
- [x] 现有 Python 处理逻辑接入 Worker（7 步管线，15 个 CSV 输出）
- [x] WebSocket 实时进度推送（7 步 + 耗时）
- [x] 处理完成后结果 ZIP 可下载
- [x] 最简前端：上传 → 进度条 → 下载（React + TypeScript，37 个前端测试全部通过）
- [x] 后端测试：18 个测试全部通过（含 E2E、下载、WebSocket）
- [x] gtfs_core SOLID 重构（P0–P6 全部处理，20 个单元测试通过）

**不包含**：认证、多租户、在线表格、地图

---

### Phase 1 — MVP（第 2–4 周）✅ 技术完成

> **完成日期**：2026-04-11。Sprint 1–5 全任务通过（Task 1–28 + Task 20b + TD-004），73 个自动化测试 0 错误。

- [x] 用户认证（注册/登录）— Tasks 6–10
- [x] 多租户隔离（应用层 + 存储层）— Tasks 11–12
- [x] 项目管理（创建/列表/历史）— Tasks 17–20、25
- [x] 参数配置表单（F-04 基础参数）— Tasks 16、26
- [x] 在线结果表格查看（F-06，结果存入 PostgreSQL）— Tasks 17–19、27
- [x] 单表 / 全量 CSV 下载（F-07）— Task 20
- [x] **pipeline 完成后自动加载 CSV 至 DWD SQLite**（E_*/F_* melt 规范化；F-09 前置依赖）— Task 20b
- [x] **Calendar Service**（DB 驱动替代本地 XLS；修复 D2/E1/E4/F1/F3/F4 假期区空表 BUG-003）— 2026-04-11
- [x] **Calendar Service 定期同步**（Celery Beat 每周一 03:00 拉取 api.gouv.fr）— 2026-04-11（TD-004）
- [x] 前端完整路由（react-router-dom + AuthGuard + ProjectDetailPage）— Tasks 22–28
- [ ] Transamo 内部试用

---

### Phase 2 — 地图 + 数据看板（第 4–8 周）
- [ ] **UI 设计系统基础**（F-10）：
  - [x] Task 41：Tailwind v4 + shadcn/ui 安装、Atomic Design 目录骨架、cn() 工具函数（2026-04-12）
  - [x] Task 42：AppShell + 全局布局 (2026-04-12)
  - [x] Task 43：LoginPage + RegisterPage + ProjectListPage 重构 (2026-04-12)
  - [x] Task 44：ProjectDetailPage + ProgressPanel + UploadForm 重构 (2026-04-12)
  - [ ] Task 45：ResultTable 重构（shadcn Table + Pagination）
- [ ] E_1 站点通过图层（AG 空间饼状图：扇区 = route_type 构成，按通过次数加权）
- [ ] E_4 弧段通过图层（有向线宽图：线宽 = 通过量；A→B 与 B→A 各绘于对应弧段右侧，视觉上合为一条线）
- [ ] GeoPackage 导出（含所有矢量图层）
- [ ] 数据看板（F-08）：
  - [ ] 饼状图 / 柱状图（线路模式、班次数、KCC）
  - [ ] 动态表格字段筛选器（多选下拉 + 数值范围）
  - [ ] 图表 × 表格 × 地图三视图联动筛选

---

### Phase 3 — LLM Agent + API 开放（第 8–12 周）
- [ ] **F-09 LLM Agent（ReAct，Claude API tool_use）**
  - [ ] `/api/v1/projects/{id}/query` 端点（POST，接收自然语言问题）
  - [ ] 工具实现：`query_dwd` / `describe_table` / `list_indicators` / `spatial_filter` / `save_indicator` / `explain_result`
  - [ ] `custom_indicators` 表（PostgreSQL）+ Alembic 迁移
  - [ ] `semantic_schema.yaml`（表/列业务定义，Agent 初始上下文）
  - [ ] 前端对话框 UI（含生成的 SQL 可展开查看）
  - [ ] Free 套餐限 3 个自定义指标，Pro/Enterprise 不限
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
| Phase 0 | ✅ 技术团队完成一次端到端处理演示（上传→处理→下载）— 55 个自动化测试覆盖 |
| Phase 1 | 🔄 技术完成（69 个测试通过）；待 Transamo 业务分析人员独立完成 3 次不同 GTFS 数据集的处理与结果查看 |
| Phase 2 | 用户可在看板上通过字段筛选定位目标站点/线路，图表、表格、地图三视图同步响应；可在地图上查看 AG 的路线构成饼图并导出地图 |
| Phase 3 | 用户通过自然语言成功派生 3 个管线未覆盖的自定义指标，结果经人工验证准确率 ≥ 80%；派生指标跨会话可复用 |
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
