# PRD — GTFS Miner Web（产品需求文档）

**版本**：0.9  
**作者**：Wei SI / Transamo  
**日期**：2026-04-18  
**状态**：Phase 0 ✅ 已完成，Phase 1 ✅ 技术完成（待 Transamo 内部试用），Phase 2 🔄 进行中（Task 41-45 ✅ GROUP UI 完成）

> **v0.9 核心调整**（与《独立顾问变现规划 v2.1:空间智能 × AI × 交通三位一体战略》对齐）：
> 1. **战略定位再升级**：产品从"交通 AI Agent 框架的参考实现"升级为"**Spatial Transit AI Agent 框架**的参考实现"——空间智能与 AI 并列为核心能力支柱，不再是可视化的从属组件
> 2. **Phase 3a Agent 工具箱默认加入 `spatial_query`**（PostGIS 空间 SQL）：零新依赖，作为空间能力的最轻量入口，不影响 demo 上线节奏
> 3. **Phase 3a 公开 demo 预置样本必含至少 1 个空间问答**（如"哪些 IRIS 公交覆盖不足?"配染色地图）——这是 v2.1 定位差异化的关键展示
> 4. **新增 Phase 2.5:可达性分析模块**（F-11），作为独立于 GTFS Miner 主管线的空间分析产品线起点，对应 v2.1 L2 空间分析算法层
> 5. **新增 §12.5 空间能力战略**，明确 GTFS Miner 是"Transit Accessibility + AI"产品线的起点
> 6. **产品目标新增 L1/L2/L3 三层能力分工**，对齐 v2.1 能力矩阵

**v0.8 → v0.9 保留不变的决策**：Phase 1 已完成范围、Phase 2 地图看板、Phase 3a/3b 拆分结构、三语界面、多租户隔离、硬编码规则清单等均保持不变。本版本为**增量补丁**,非重写。

---

## 1. 背景与目标

### 1.1 背景

GTFS Miner 目前是一款 QGIS 桌面插件，面向熟悉 GIS 工具的技术用户。其核心价值在于将 GTFS 原始公共交通数据转化为标准化的业务分析输出（指标表格、空间图层）。

将其迁移为 Web 应用的动机在于：
- **降低使用门槛**：消除对 QGIS 的依赖，让业务分析人员无需安装任何软件即可使用；
- **战略性作品集资产**（v0.8 重估）：作为作者独立顾问业务的**技术可信度锚点**与**公开 demo 线索入口**——吸引交通+AI 定制化项目的潜在客户，而非追求 SaaS 规模化变现；Transamo 仍作为首个付费参考案例；
- **协作与多项目管理**：支持多用户、多数据集的在线管理与历史查阅；
- **LLM 驱动的自然语言洞察**：让 GTFS 数据真正可对话——用户通过提问派生自定义指标，超越静态表格输出，无需编写代码；三语（中/英/法）界面作为国际市场独特卖点；
- **Spatial Transit AI Agent 框架原型**（v0.9 升级）：Phase 3 Agent 架构(ReAct + 工具箱含 PostGIS 空间查询 + 自定义指标持久化)作为"**Spatial Transit AI Agent 框架**"的参考实现——空间智能与 AI 并列为核心能力,不再作为可视化的从属组件。为客户定制化部署项目(铁路运营空间决策支持、投标 CCTP 地理范围自动提取、AOT 覆盖率诊断、TOD 评估)提供可复用基础。
- **法国空间数据本地化优势**（v0.9 新增）：深度集成 IGN(BD TOPO、AdminExpress)、INSEE(Filosofi、IRIS、MOBPRO)、SIRENE、BPE 等法国政府开放数据,形成非法国竞争对手(Conveyal、Remix)难以本地化的独特壁垒。

### 1.2 产品目标

> **核心定位**（v0.9）：**将原始 GTFS 数据转化为空间智能 × AI 双栈加持的公共交通分析洞察**——覆盖四层价值：标准化处理 → 可视化看板 → **空间分析算法**(可达性/覆盖率/TOD)→ LLM 自然语言查询与指标派生。

**三层能力分工**（对齐 v2.1 战略):

| 层级 | 能力 | 主要交付 |
|------|------|---------|
| **L1 · 空间数据基础层** | GTFS / OSM / IGN / INSEE 数据处理与标准化 | Phase 0-1 已完成的处理管线 |
| **L2 · 空间分析算法层** | 可达性、覆盖率、OD 空间化、TOD 评估 | Phase 2.5 F-11(v0.9 新增) |
| **L3 · Spatial AI Agent 层** | 对话式空间分析 + 决策支持 | Phase 3a/3b F-09a/F-09b |

| 目标 | 衡量指标 |
|------|---------|
| 一键将原始 GTFS 数据转化为公共交通分析洞察 | 用户从上传到获得首个洞察结果的成功率 ≥ 90% |
| 支持 Transamo 作为首个租户上线 | MVP（上传 + 处理 + 下载）在 1 周内可演示 |
| 为后续 SaaS 对外销售奠定基础 | 多租户隔离机制验证通过 |
| 用户可通过自然语言查询派生自定义指标，无需编写代码 | Phase 3b 上线后，用户自主派生指标准确率 ≥ 80% |
| **用户可通过自然语言做空间分析**（v0.9 新增） | Phase 3a 公开 demo 空间问答样本可用;Spatial Agent 空间 SQL 首次正确率 ≥ 70% |
| **作为作者独立顾问业务的线索入口**（v0.8 新增） | Phase 3a 公开 demo 上线后，月度陌生访问 ≥ 50；demo → 商务对话转化 ≥ 1 例/月 |
| **可达性分析能力作为独立 POC 产品**（v0.9 新增） | Phase 2.5 上线后,单次可达性分析(城市级)计算时间 ≤ 5 分钟;交付物含交互式等时线地图 |

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

#### F-09a：Spatial Transit AI Agent MVP（Phase 3a，4-6 周内与 Phase 2 并行提前交付）

> **战略优先级**：作为作者独立顾问业务的**公开技术 demo**，上线时间优先于 Phase 2 的完整看板。目标是让三位目标客户(铁路公司 Directeur、咨询公司创始人、AOT 联系人)在首次商务对话中即可见到**可用的 Spatial AI 演示**——**空间问答是 v2.1 定位差异化的关键展示**,不可省略。

**架构**：ReAct Agent(Claude API tool_use) + DWD SQLite(pipeline 完成后自动加载) + **PostGIS 空间扩展**(Supabase 原生支持,零额外依赖)

**工具箱(4 个核心工具)**:

| 工具 | 作用 |
|------|------|
| `query_dwd(sql)` | 在 DWD SQLite 上执行 SQL，核心计算工具 |
| `describe_table(name)` | 返回实时表结构 + 示例行，供 Agent 自主探索 schema |
| `spatial_query(postgis_sql)` | **（v0.9 新增）**在 PostGIS 上执行空间 SQL(ST_Buffer / ST_Contains / ST_Within / ST_DWithin 等),返回表格或 GeoJSON。支持站点缓冲、行政区筛选、空间叠加等基础空间操作。 |
| `explain_result(df)` | 将数字结果翻译为交通业务语言 |

**核心功能**：
- 自然语言查询处理结果("周一早高峰通过次数最多的前 10 个站点")
- **空间维度自然语言查询**(v0.9 新增):
  - "15 区经过了哪些线路?"→ PostGIS ST_Within + 表格高亮
  - "Gare de Lyon 周边 500m 的站点?"→ ST_DWithin + 地图
  - "哪些 IRIS 距离最近公交站点超过 500m?"(需 IRIS 边界数据,样本数据集预置)
- 多步推导(Agent 自动拆解问题、链式调用工具、SQL 报错时自动修正重试)
- **三语界面(中/英/法)**:UI 文案 + Agent system prompt 的多语种配置,用户语言自动切换
- 前端:简单对话框 UI + **地图结果渲染区**(GeoJSON 响应自动渲染到 MapLibre)
- **公开 demo URL**:无需登录即可访问的演示入口(使用预置 GTFS 样本数据集)

**预置样本数据集要求**(v0.9 明确):
- 至少包含 1 个法国中等城市的 GTFS(如 Rennes、Nantes、Grenoble 等,数据规模适中)
- 预加载该城市对应的 IGN AdminExpress 行政边界(communes / IRIS)到 PostGIS
- 预置 5-8 个示范问答(跨三语),其中**至少 2 个为空间问答**

**不包含**(留给 F-09b):
- `list_indicators` / `spatial_filter`(高级地理围栏) / `save_indicator` 工具
- `custom_indicators` 表与持久化逻辑
- 套餐配额限制
- SQL 可展开查看的高级 UI
- `semantic_schema.yaml` 结构化业务定义(MVP 阶段用简化 system prompt 即可)
- 可达性 / 等时线 / 覆盖率诊断(由 Phase 2.5 F-11 独立承载)

---

#### F-09b：Spatial Transit AI Agent 完整版（Phase 3b）

处理结果不再是只能下载的静态 CSV——用户可通过自然语言与数据对话，Agent 自主推导并持久化自定义指标,**包括空间维度的指标**。

**架构**：在 F-09a 基础上扩展为完整工具箱 + 指标持久化 + 可达性能力集成

**扩展工具箱**：

| 工具 | 作用 |
|------|------|
| `list_indicators()` | 列出已有 E_*/F_* 及用户自定义指标 |
| `spatial_filter(stops, center, radius_m)` | 地理围栏筛选(应用层封装,便于 Agent 常用场景调用) |
| `save_indicator(name, sql, description)` | 将派生指标持久化至 `custom_indicators` 表 |
| `isochrone(origin, minutes, mode)` | **(v0.9 新增)** 等时线计算,复用 F-11 可达性模块 |
| `coverage_analysis(region, buffer_m)` | **(v0.9 新增)** 覆盖率诊断,站点缓冲 × 人口网格,复用 F-11 |
| `nearby_poi(point, radius, category)` | **(v0.9 新增,可选)** 周边 POI 检索(来自 BPE 或 Overture 数据) |
| `render_map(geojson, style)` | **(v0.9 新增)** 生成可嵌入的地图结果(替代纯表格输出) |

**核心功能**：
- 继承 F-09a 三语界面与 `spatial_query` 基础能力
- **派生指标持久化**:`save_indicator` 将一次性分析(含空间指标)沉淀为可复用指标,跨会话保留
- **空间决策支持对话**(v0.9 新增):
  - "帮我给 XX 站周边 500m 做一个 TOD 开发潜力评估"
  - "法兰西岛西部哪些社区的公交服务明显不足?"
  - "这个 CCTP 投标范围对应哪些行政区,现有公交网络诊断如何?"
- 前端:对话框 UI + **地图结果渲染区** + SQL 可展开查看

**套餐限制**:Free 限每项目 3 个自定义指标;Pro/Enterprise 不限

**数据层关系**(v0.9 更新):

```
L1 空间数据基础层                 ←  Phase 0-1 已完成
├── DWD 层(A_*/B_*/C_*/D_*)       ←  Agent 的计算原料
│   └── pipeline 固化
├── 指标层(E_*/F_*)                ←  可直接查询
└── 法国空间数据(IRIS/communes)    ←  预加载至 PostGIS
                ↓
L2 空间分析算法层                  ←  Phase 2.5 F-11
├── 可达性模块(isochrone)
├── 覆盖率诊断模块
└── TOD 评估模块
                ↓
L3 Spatial AI Agent 层             ←  Phase 3a/3b
├── F-09a 基础工具箱(含 spatial_query)
├── F-09b 扩展工具箱(含 isochrone / coverage / POI / render_map)
└── 自定义指标持久化(custom_indicators 表,含空间指标)
```

---

#### F-11:可达性分析模块(Phase 2.5,v0.9 新增) 🔥

> **战略定位**:对应 v2.1 战略中 L2 空间分析算法层的首个产品化交付,作为独立于 GTFS Miner 主管线的**空间分析产品线起点**。既可作为 GTFS Miner 的增强模块,也可作为独立 POC 产品对外销售(€8-15k)。

> **排期说明**:Phase 2.5 位于 Phase 2(地图看板)与 Phase 3(Agent)之间,但**技术上可与 Phase 2/3a 并行推进**。由独立模块组成,不阻塞主线上线节奏。

**核心能力**:

| 能力 | 说明 | 技术栈 |
|------|------|-------|
| **Isochrone(等时线)** | 从指定起点计算 15/30/45 分钟可达范围(公交 + 步行多模态) | **R5**(Conveyal,Java)或 **OpenTripPlanner 2**,Docker 部署 |
| **加权可达性指数** | 基于等时线 × 人口/就业数据计算可达机会数 | R5 + PostGIS + INSEE Filosofi / SIRENE |
| **覆盖率诊断** | 站点多环缓冲(300m/500m/800m)× 人口密度 = 覆盖人口;Gap 识别 | PostGIS ST_Buffer + INSEE IRIS |
| **服务公平性(Equity)分析** | 覆盖 × 社会经济变量(收入/年龄/无车家庭)叠加 | PostGIS + INSEE Filosofi 200m × 200m 网格 |

**交付形态**:

1. **独立 Web 页面**(不依赖 GTFS Miner 主项目流):
   - 输入:GTFS 文件 + 城市名 / 行政区选择
   - 输出:交互式等时线地图 + 可达就业/人口数据 + 覆盖率热力图 + 服务空白报告(PDF 可导出)
2. **集成到 GTFS Miner 主产品**(作为项目详情页的附加分析 tab)
3. **Agent 工具化**(被 F-09b 的 `isochrone` / `coverage_analysis` 工具调用)

**法国空间数据预加载**:

| 数据源 | 用途 | 缓存策略 |
|-------|------|---------|
| IGN AdminExpress | 行政边界(communes / arrondissements / IRIS) | 季度全量下载 |
| INSEE Filosofi | 200m × 200m 人口 / 收入网格 | 年度更新 |
| INSEE IRIS | 2000 居民人口社会单元 | 年度更新 |
| SIRENE | 企业数据库(就业岗位) | 季度增量 |
| BPE(Base Permanente des Équipements) | POI(学校/医院/商店) | 年度更新 |

**性能要求**:
- 单次城市级可达性分析(以 Rennes / Nantes 规模为例):计算时间 ≤ 5 分钟
- IDFM 规模仅限 Enterprise 套餐,预计算 ≤ 30 分钟

**套餐限制**:
- Free:不可用(引导升级)
- Pro:每月 10 次可达性计算
- Enterprise:不限

**不包含**(留给 Phase 4+):
- 多模态细粒度路径规划(仅支持公交 + 步行;不支持骑行 + 共享单车)
- 需求侧建模(OD 矩阵预测)
- 方案模拟("如果新增 X 号线会怎样")

---

#### V2：交互式地图 + 数据看板

**地图图层**

| 图层 | 说明 |
|------|------|
| E_1 站点通过 | 点图层，每个 AG 以**空间饼状图**标注，扇区 = 途经线路 route_type 构成（按通过次数加权） |
| E_4 弧段通过 | **带宽图**（对齐 AequilibraE Bandwidth on network links）：每条有向弧段渲染为可变宽度线段，线宽（px）= `weight × max_width_px`；AB 向右偏移 `线宽/2 + 0.1px`，BA 向左对称，两侧视觉不重叠。`max_width_px` 通过前端控件调节。GeoPackage 导出为 **LineString** 图层，携带 `nb_passage`、`max_nb_passage`、`direction` 字段，由 QGIS 数据定义覆盖（`scale_linear` 线宽 + 偏移 + 线型）渲染，无需 Polygon 预计算 |

功能：底图切换（OSM / 空白）、图层开关、要素点击弹窗、**GeoPackage 导出**（含所有矢量图层）

**GeoPackage 导出内存策略**：导出时真正的内存瓶颈在构建 GeoDataFrame（geopandas join + geometry 构造），而非写文件格式本身。对 IDFM 规模（~5 万站点、数千弧段）的数据集，全量一次性构建 GeoDataFrame 峰值内存约 800 MB–1.2 GB。为控制内存：
- `export_geopackage()` 按图层逐个处理（passage_ag → passage_arc → arrets），写完即释放
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

- GTFS-RT(实时数据)处理
- Access 数据库导出(legacy)
- SNCF 专用逻辑(GTFS_algorithm.py legacy)
- **GIS 专家级几何编辑功能**(v0.9 澄清:不做 QGIS 级别的要素编辑、拓扑校正等专家工具;空间分析算法如可达性、覆盖率则**在范围内**,由 Phase 2.5 F-11 承载)
- **需求侧建模**(OD 矩阵预测、方案模拟等;仅提供现状分析,不做预测)
- 移动端适配(桌面浏览器优先)

---

## 5. 技术架构建议

> 选型原则：**易维护、易部署、高性能**。

### 5.1 总体架构

```
浏览器(React + TypeScript + MapLibre GL JS + deck.gl)
    ↓ HTTPS / WebSocket
API 网关(FastAPI)
    ├── 认证服务(JWT + OAuth2)
    ├── 项目管理 API
    ├── 日历服务 (Calendar Service: API Sync + DB)
    ├── 文件上传 API
    ├── 任务状态 WebSocket
    ├── 结果查询 API
    ├── /accessibility → F-11 可达性分析服务(v0.9 新增)
    │       ├── isochrone      → R5 / OTP(Docker)
    │       ├── coverage       → PostGIS + INSEE IRIS
    │       └── equity         → PostGIS + INSEE Filosofi
    └── /query → Spatial Transit AI Agent(ReAct,Claude API tool_use)
              ├── 数据工具箱
              │   ├── query_dwd       → DWD SQLite({project_id}_query.sqlite)
              │   │                     E_*/F_* 已 melt 规范化;pipeline 完成后自动加载
              │   ├── describe_table  → schema 内省
              │   ├── list_indicators → 指标清单
              │   └── save_indicator  → custom_indicators 表(PostgreSQL)
              ├── 空间工具箱(v0.9 新增)
              │   ├── spatial_query    → PostGIS(Supabase 原生)
              │   ├── spatial_filter   → Python / Shapely 封装
              │   ├── isochrone        → 复用 F-11 服务
              │   ├── coverage_analysis → 复用 F-11 服务
              │   ├── nearby_poi       → PostGIS + BPE 数据
              │   └── render_map       → GeoJSON → MapLibre 渲染指令
              └── explain_result       → 业务语言翻译
            ↓
任务队列(Celery + Redis)
    └── Worker:现有 Python 处理逻辑(零修改复用)+ 可达性计算 Worker(v0.9 新增)
            ↓
数据库(Supabase / PostgreSQL + PostGIS 扩展)
    ├── 用户 / 租户 / 项目元数据
    ├── 日历数据(calendar_dates 表,取代本地 Excel)
    ├── 处理结果表(分表存储,按 project_id 索引)
    ├── custom_indicators(用户派生指标:name, sql, description, project_id,含空间指标)
    └── 法国空间数据预加载(v0.9 新增)
         ├── IGN AdminExpress(communes / arrondissements / IRIS)
         ├── INSEE Filosofi(200m × 200m 人口/收入网格)
         ├── INSEE IRIS / MOBPRO
         ├── SIRENE(企业就业数据)
         └── BPE(POI)
            ↓
对象存储(Supabase Storage / S3)
    └── 原始 GTFS 上传文件、结果 ZIP 归档、可达性分析 PDF 报告
```

### 5.2 技术栈

| 层级 | 技术 | 理由 |
|------|------|------|
| 后端 API | **FastAPI (Python)** | 与现有处理逻辑同语言；原生 WebSocket；自动生成 OpenAPI 文档 |
| 任务队列 | **Celery + Redis** | 成熟异步方案；支持进度回调；Worker 可横向扩展 |
| 前端 | **React + TypeScript** | 生态成熟；Ant Design 表格组件开箱即用 |
| 数据库 | **Supabase（PostgreSQL）** | 托管 PG；内置 Row Level Security；Storage + Auth 一体；免运维 |
| **空间数据库扩展**(v0.9 新增) | **PostGIS**(Supabase 原生支持) | 空间 SQL(ST_Buffer / ST_Contains / ST_DWithin 等);`spatial_query` 工具依赖;零新部署成本 |
| 对象存储 | **Cloudflare R2**（S3 兼容，boto3 原生） | 10 GB 免费；通过自定义域名 CF 代理，国内可达；与 DB 无耦合 |
| 地图(V2/Phase 2.5) | **MapLibre GL JS + deck.gl**(v0.9 扩展) | 开源；矢量渲染性能好；deck.gl 适合大规模点/线/等时线渲染 |
| **路径规划 / 可达性**(v0.9 新增,Phase 2.5) | **Conveyal R5** 或 **OpenTripPlanner 2** | 开源公交可达性引擎;R5 性能更优,OTP 生态更成熟;Docker 部署 |
| **空间索引**(v0.9 新增,Phase 2.5+) | **H3**(Uber) | 六边形网格,便于 AI 跨图层聚合;Python/JS 双语言 SDK |
| **法国空间数据缓存**(v0.9 新增) | 本地 PostGIS 预加载 | IGN AdminExpress / INSEE Filosofi / IRIS / SIRENE / BPE 周期性全量下载,避免运行时 API 依赖 |
| 容器化 | **Docker（开发/生产）/ Zeabur（云部署，香港节点）** | push-to-deploy，国内直连，无需代理 |
| 实时通信 | **WebSocket**（FastAPI 原生支持） | 任务进度实时推送 |
| LLM Agent | **Claude API(claude-sonnet-4-6)+ tool_use** | ReAct 循环;tool_use 原生支持工具调用;无需 LangChain 等框架 |

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

> **v0.8 战略定位说明**：GTFS Miner Web 不作为作者独立顾问业务的主要现金流来源。产品的核心商业价值在于作为**技术可信度锚点**和**客户线索入口**——面向"通用交通 AI Agent 框架"的定制化部署项目（铁路运营数据分析、投标知识库 RAG、规划数据分析等）。下方分级订阅体系保留，用于 Transamo 首个付费参考案例、服务已表达付费意愿的外部用户，以及未来视市场反馈决定是否扩大投入。

### 6.1 定价策略：分级订阅（按项目数 + 用户数）

| 套餐 | 活跃项目数 | 用户数 | 数据保留期 | 大数据集支持 | 定价参考 |
|------|-----------|--------|-----------|------------|---------|
| **Free** | 2 | 1 | 30 天 | 否（≤5K 站点）| 免费 |
| **Pro** | 10 | 5 | 12 个月 | 否 | 待定 €/月 |
| **Enterprise** | 无限 | 无限 | 自定义 | 是（IDFM 级） | 定制报价 |

> **大数据集**（>5 万停靠站，如 IDFM）仅在 Enterprise 套餐开放，原因：单次处理消耗算力显著高于普通数据集（30 分钟 vs 5 分钟）。

### 6.2 V6 数据集对比功能定位

版本对比作为 Pro / Enterprise 套餐的**差异化卖点**，对 Transamo 等咨询公司具有高商业价值（用于交通网络调整前后效果评估）。

### 6.3 Demo 作为线索入口（v0.8 新增）

Phase 3a Agent MVP 的公开 demo URL 是产品商业价值的核心体现路径：

- 对独立顾问业务的价值路径：**陌生访问 → 商务对话 → Agent 框架定制化项目（€25-60k/次）或 Retainer（€7-9k/月）**
- 对比 Free/Pro 订阅的单客户终身价值（LTV），一次定制化项目相当于数十个 Pro 订阅的净现值
- 因此产品开发优先级：**Phase 3a Agent MVP（demo 上线）> Phase 2 看板完整度 > SaaS 订阅付费漏斗优化**

### 6.4 独立顾问业务收入结构(v0.9 新增,与 v2.1 战略对齐)🔥

与 v0.8 相比,v0.9 进一步明确了产品在独立顾问业务版图中的收入主力路径:

| 收入路径 | 定价 | 转化依赖 |
|---------|------|---------|
| **Retainer 月费**(v2.1 主力) | €8-10k/mois HT | demo 触达 → 商务对话 → 首次 POC → 签约 |
| **Spatial Agent 定制化项目**(v2.1 主力) | €35-75k 一次性 + €3-6k/月维护 | 框架复用 30-50% + 客户定制化 |
| **可达性分析 POC**(v0.9 新产品线) | €8-15k / 3-4 周 | F-11 模块作为交付基础 |
| **空间决策支持咨询项目** | €40-120k | 高端客户定制 |
| SaaS 订阅(Free/Pro/Enterprise) | 见 §6.1 | 机会驱动,非主线 |

**收入路径的产品依赖**:
- Retainer 签约依赖:Phase 3a demo 上线 + 首次 POC 完成
- Spatial Agent 定制化依赖:Phase 3a/3b 完整工具箱 + Phase 2.5 F-11 可复用模块
- 可达性 POC 依赖:Phase 2.5 F-11 可独立交付(不依赖 GTFS Miner 全栈)

因此 v0.9 的**开发优先级顺序**:
```
Phase 3a 含 spatial_query 的 demo(第 4-8 周)🔥
    ↓ 并行
Phase 2.5 F-11 可达性模块(第 4-10 周,可独立交付)🔥
    ↓
Phase 3b Spatial Agent 完整版(第 8-12 周)
    ↓
Phase 2 地图看板完整度(与上述并行,节奏可适度放缓)
```

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
| **可达性分析性能(城市级)**(v0.9 新增) | Rennes / Nantes 规模 Isochrone + 覆盖率计算 ≤ 5 分钟 |
| **可达性分析性能(IDFM 级)**(v0.9 新增) | 全网络 Isochrone 预计算 ≤ 30 分钟;仅限 Enterprise 套餐 |
| **Agent 响应时间**(v0.9 新增) | 单轮对话(含 1-3 次工具调用)p50 ≤ 15 秒,p95 ≤ 30 秒 |
| **Agent 空间 SQL 首次正确率**(v0.9 新增) | 预置 20 个空间问答测试集,首次正确率 ≥ 70%;自动纠错后 ≥ 90% |
| 并发处理 | 初期 5 个并发 Worker；可横向扩展 |
| 文件上传限制 | 初期 500 MB / ZIP；大文件考虑分片上传 |
| 数据保留 | 按套餐定义（30 天 / 12 个月 / 自定义） |
| 安全性 | HTTPS 全程；JWT 有效期 24h；租户数据隔离 |
| 浏览器兼容 | Chrome / Edge / Firefox 最新两个大版本 |
| **空间数据预加载存储**(v0.9 新增) | 法国空间数据预加载总容量 ≤ 20 GB(Supabase Pro 计划充裕) |

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
  - [x] Task 45：ResultTable 重构（shadcn Table + Pagination）(2026-04-14)
- [x] MapLibre 底图组件（Task 33：OSM 底图 + E_1/E_4 图层开关 + AG 点击回调）（2026-04-15）
- [ ] E_1 站点通过图层（AG 空间饼状图：扇区 = route_type 构成，按通过次数加权）
- [ ] E_4 弧段通过图层（AequilibraE 带宽图：weight × max_width_px px，gap_px 间距，可按 route_type 等分组堆叠；AB 右侧，BA 左侧）
- [ ] GeoPackage 导出（含所有矢量图层）
- [ ] 数据看板（F-08）：
  - [ ] 饼状图 / 柱状图（线路模式、班次数、KCC）
  - [ ] 动态表格字段筛选器（多选下拉 + 数值范围）
  - [ ] 图表 × 表格 × 地图三视图联动筛选

---

### Phase 2.5 — 可达性分析模块(与 Phase 2/3a 可并行,v0.9 新增)🔥
**目标**:F-11 空间分析算法层的首次产品化交付,既作为 GTFS Miner 增强模块,也作为独立 POC 产品

- [ ] **基础设施**
  - [ ] Supabase PostGIS 扩展启用验证
  - [ ] R5 或 OTP 容器化部署(docker-compose)
  - [ ] 法国空间数据预加载脚本(IGN AdminExpress + INSEE IRIS)
- [ ] **核心算法模块**
  - [ ] Isochrone 计算(调用 R5/OTP)
  - [ ] 加权可达性指数(叠加 SIRENE 就业数据)
  - [ ] 覆盖率诊断(站点缓冲 × INSEE IRIS)
  - [ ] 服务公平性分析(叠加 Filosofi 社会经济变量)
- [ ] **前端交付**
  - [ ] 独立 Web 页面(输入 GTFS + 城市 → 输出等时线地图)
  - [ ] 集成入口:GTFS Miner 项目详情页 "可达性分析" Tab
  - [ ] PDF 报告导出(覆盖率 + 服务空白 + 社会经济对比)
- [ ] **性能验证**
  - [ ] 城市级(Rennes/Nantes 规模)计算 ≤ 5 分钟

**成功标准**:
- 上线后单次 POC 可达性分析能在客户会议中现场演示
- 作为独立产品线,首月吸引至少 1 次外部客户咨询

---

### Phase 3a — Spatial AI Agent MVP + 开源(第 4-8 周,与 Phase 2 并行提前交付)🔥 战略优先级
**目标**:公开可访问的三语 **Spatial** Agent demo URL,作为独立顾问业务的线索入口和技术可信度证明。v0.9 强调:**空间问答是差异化的关键展示,不可省略**。

- [ ] **F-09a Spatial AI Agent MVP**
  - [ ] `/api/v1/projects/{id}/query` 端点(POST,接收自然语言问题)
  - [ ] 工具实现(4 个,v0.9 从 3 个增至 4 个):
    - [ ] `query_dwd`
    - [ ] `describe_table`
    - [ ] **`spatial_query`(PostGIS 空间 SQL,v0.9 新增)**
    - [ ] `explain_result`
  - [ ] 三语 system prompt(中/英/法),根据用户语言切换
  - [ ] 简单对话框 UI + **地图结果渲染区**(GeoJSON 响应自动渲染)
  - [ ] 公开 demo URL 部署(预置 GTFS + IGN 行政边界样本数据集)
  - [ ] **预置 5-8 个示范问答,其中至少 2 个为空间问答**(v0.9 新增)
- [ ] **开源核心代码**
  - [ ] GitHub 组织页 / 仓库整理
  - [ ] 双语 README(中/英)+ Agent 架构文档 + **空间能力章节**
  - [ ] 至少 3 个使用示例,其中 1 个为空间问答场景
  - [ ] 明确许可证条款(核心开源 + 商业部分保留)

**成功标准**:demo URL 上线;空间问答样本可用;月度陌生访问 ≥ 50;至少 1 次由 demo 触发的商务对话

---

### Phase 3b — Spatial AI Agent 完整版 + API 开放(第 8-12 周)
- [ ] **F-09b Spatial AI Agent 完整版**
  - [ ] 扩展工具箱:`list_indicators` / `spatial_filter` / `save_indicator`
  - [ ] **空间工具扩展:`isochrone` / `coverage_analysis` / `render_map`**(v0.9 新增,复用 Phase 2.5 F-11)
  - [ ] `custom_indicators` 表(PostgreSQL,含空间指标支持)+ Alembic 迁移
  - [ ] `semantic_schema.yaml`(表/列业务定义,含空间表 metadata)
  - [ ] 前端对话框 UI 升级(含生成的 SQL 可展开查看 + 地图结果渲染)
  - [ ] Free 套餐限 3 个自定义指标,Pro/Enterprise 不限
- [ ] REST API + API Key 鉴权
- [ ] 自定义假期日历上传(多国支持基础)
- [ ] 性能优化(大数据集)
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
| **Phase 2.5**(v0.9 新增)| F-11 可达性分析模块上线;单次城市级(Rennes/Nantes 规模)计算 ≤ 5 分钟;可输出交互式等时线地图 + 覆盖率热力图;作为独立 POC 产品首月吸引至少 1 次外部客户咨询 |
| Phase 3a | Spatial Agent MVP demo URL 公开上线;三语界面(中/英/法)可用;**工具箱含 `spatial_query`,预置空间问答样本至少 2 个**(v0.9 强化);代码开源(GitHub 仓库 + README + 使用示例);月度陌生访问 ≥ 50;至少 1 次由 demo 触发的独立顾问业务商务对话 |
| Phase 3b | 用户通过自然语言成功派生 3 个管线未覆盖的自定义指标(**含至少 1 个空间指标**,v0.9 强化),结果经人工验证准确率 ≥ 80%;派生指标跨会话可复用 |
| SaaS 商业化（可选） | 第一个付费外部客户成功完成 onboarding — **注**：v0.8 起此目标优先级降为"机会驱动"，不作为开发路线图的强制里程碑 |
| **独立顾问业务关联**（v0.8 新增） | Phase 3a 上线后 12 周内，至少 1 个 **Spatial Agent 框架**(v0.9 更新)定制化项目签约（€35k+,v0.9 上调）|
| **空间分析产品线关联**(v0.9 新增)| Phase 2.5 上线后 16 周内,至少 1 个独立**可达性分析 POC 项目**签约(€8-15k) |

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
| Q7（v0.8） | 产品在独立顾问业务中的角色 | ✅ 作品集资产 + 技术可信度锚点 + 线索入口，非主要现金流来源 |
| Q8（v0.8） | Phase 3 排期 | ✅ 拆分为 3a（Agent MVP，与 Phase 2 并行提前）+ 3b（完整 Agent） |
| Q9（v0.8） | Agent 界面语言 | ✅ 中/英/法三语，根据用户选择切换 |
| **Q10**(v0.9) | 空间能力在产品中的定位 | ✅ 空间智能与 AI 并列为核心支柱,不再是可视化的从属组件;产品升级为 "Spatial Transit AI Agent 框架的参考实现" |
| **Q11**(v0.9) | 可达性分析是否纳入 GTFS Miner | ✅ 纳入,作为 Phase 2.5 F-11 独立模块;既可集成于主产品,也可作为独立 POC 销售 |
| **Q12**(v0.9) | Agent Phase 3a 是否应该包含空间工具 | ✅ 是,加入 `spatial_query`(零新依赖,仅 PostGIS SQL),不延期 demo 上线 |

---

## 12. 战略定位补充（v0.8 新增）

> 本章节基于《独立顾问变现规划 v2.0》的战略决策,明确 GTFS Miner Web 在更大商业版图中的角色。

### 12.1 产品的三重战略角色

| 角色 | 含义 | 对应开发优先级 |
|------|------|--------------|
| **作品集资产** | 向潜在客户展示"从业务建模到 AI 部署全链路落地"的完整能力证明 | 功能完整度优先于规模化 |
| **技术可信度锚点** | 公开可访问、可审阅、开源的代码与架构,回应"AI 顾问是否真的懂技术"的信任疑虑 | 核心代码开源 + 架构文档化 |
| **线索入口** | 通过公开 demo 吸引陌生访问者进入独立顾问业务漏斗 | Phase 3a demo URL 优先于 SaaS 付费漏斗 |

### 12.2 与"Spatial Transit AI Agent 框架"的复用关系(v0.9 更新)

GTFS Miner Phase 3 Agent 架构是作者"**Spatial Transit AI Agent 框架**"(v0.9 升级命名)的**首个参考实现**。该框架拟向以下客户场景做 30-50% 定制化部署:

| 目标场景 | 复用 GTFS Miner 的组件 | 需定制化部分 |
|---------|---------------------|------------|
| 铁路运营数据分析(排班/客流/票务/晚点) | Agent 内核 + 工具箱 + 对话 UI 骨架 + 空间能力 | Schema 配置 + 领域专属工具 2-4 个 |
| **铁路车站周边空间决策支持**(v0.9 新增) | Agent 内核 + `spatial_query` + `isochrone` + `coverage_analysis` | 客户内部客流数据接入 + TOD 指标定制 |
| 投标知识库 RAG + NL2SQL | Agent 内核 + `query_dwd` + `describe_table` | RAG 检索工具 + 文档向量化管线 |
| **CCTP 地理范围自动提取 + 投标诊断**(v0.9 新增) | 全空间栈 + Agent + RAG | 法语 NER 模型 + IGN AdminExpress API 集成 |
| 公共交通规划数据(OD 矩阵/频率/路网) | GTFS 数据管线 + Agent 全栈 | 路网扩展工具 + 规划专用指标 |
| **AOT 覆盖率诊断仪表盘**(v0.9 新增) | F-11 可达性模块 + Agent + 地图栈 | AOT 区域专属数据接入 + 行政报告模板 |
| **TOD / 房地产开发潜力评估**(v0.9 新增,新客户赛道) | F-11 可达性 + 人口/就业数据 + Agent | 房地产行业指标层 + 开发商数据接入 |

> 因此 F-09a/F-09b/F-11 的实现质量,直接决定了定制化项目交付的复用比例——这是 GTFS Miner 作为"作品集资产"投入的真实 ROI。v0.9 相对 v0.8 新增了 3 个空间相关场景,大幅扩展了框架的变现入口。

### 12.3 开源策略

| 组件 | 许可证 | 理由 |
|------|--------|------|
| gtfs_core 数据处理模块（`gtfs_norm.py` / `gtfs_spatial.py` / `gtfs_generator.py` / `gtfs_export.py` / `gtfs_utils.py`） | 开源（MIT 或 Apache 2.0） | 建立行业可见性,吸引贡献者,形成技术权威 |
| Phase 3a Agent 架构 + 工具定义 | 开源 | 作为 AI 技术可信度的关键证明 |
| Phase 3b custom_indicators 持久化、多租户、计费、套餐 | 保留闭源 | 保护商业化边界 |
| Phase 2 地图 + 看板前端 | 视情况决定 | 暂定闭源,可随市场反馈调整 |

### 12.4 语言战略

三语支持(中/英/法)不仅是国际化功能,更是作者独立顾问业务差异化定位的核心体现:

- **法语界面**:对法国本土客户的专业信任锚点
- **英语界面**:扩展到比利时/瑞士/卢森堡/英国等法语区外欧洲市场,以及法语世界外的跨国咨询公司
- **中文界面**:个人 IP 在中文交通+AI 圈子的传播

此三语组合在欧洲交通+AI 领域**近乎唯一**,是公开 demo 转化为商务对话的关键钩子之一。

### 12.5 空间能力战略(v0.9 新增)🔥

空间智能(GIS)在 v0.9 版本中正式升格为产品核心支柱,与 AI 并列,不再作为可视化的从属组件。

**战略判断**:
- 纯 "交通 + AI" 领域的独立顾问市场已有竞争者
- **"交通 + GIS + AI" 三位一体的独立顾问,在法国市场近乎空集**
- 这个生态位的护城河比纯 AI 定位深一个层级(技术门槛 + 本地数据壁垒 + 付费意愿强度均更优)

**GTFS Miner 在空间战略中的角色演进**:

| 版本 | GTFS Miner 定位 |
|------|---------------|
| v0.7 | 旗舰 SaaS 产品 |
| v0.8 | 通用交通 AI Agent 框架的作品集资产 |
| **v0.9**(当前) | **Spatial Transit AI Agent 框架的参考实现 + "Transit Accessibility + AI" 独立产品线起点** |

**空间能力在产品中的分布**:

| 能力层次 | 载体 | 商业形态 |
|---------|------|---------|
| L1 · 空间数据基础 | Phase 0-1 已完成的处理管线 + 法国空间数据预加载 | 开源 / 免费层 |
| L2 · 空间分析算法 | Phase 2.5 F-11(可达性 / 覆盖率 / TOD / Equity) | 独立 POC 产品(€8-15k),Pro/Enterprise SaaS 增值功能 |
| L3 · Spatial AI Agent | Phase 3a F-09a(`spatial_query`)→ Phase 3b F-09b(全空间工具箱) | Spatial Agent 定制化项目(€35-75k),Retainer 核心卖点(€8-10k/月) |

**法国空间数据本地化策略**:

深度集成 IGN、INSEE、SIRENE、BPE 等法国开放数据资源,形成非法国竞争对手(Conveyal、Remix 等)难以本地化的独特壁垒。数据源采用**本地 PostGIS 预加载**策略,避免运行时 API 依赖:

| 数据源 | 缓存周期 | 预计数据量 |
|-------|---------|-----------|
| IGN AdminExpress(行政边界) | 季度全量 | ~500 MB |
| INSEE Filosofi(200m × 200m 人口/收入网格) | 年度全量 | ~2 GB |
| INSEE IRIS(2000 居民单元) | 年度全量 | ~200 MB |
| INSEE MOBPRO(通勤 OD) | 年度全量 | ~1 GB |
| SIRENE(企业数据库) | 季度增量 | ~5 GB(压缩后 ~1 GB) |
| BPE(POI 数据库) | 年度全量 | ~500 MB |

**与独立顾问业务的价值链**:

```
Phase 3a demo URL(含空间问答)
       ↓ (陌生访问 ≥ 50/月)
客户商务对话(空间 AI Agent demo 开场)
       ↓ (至少 1 例/月)
可达性分析 POC (€8-15k) 或 Spatial Agent 定制化 (€35-75k)
       ↓ (转化率 30-50%)
Retainer 签约 (€8-10k/月) + 后续滚动项目
```

v0.9 版本的所有技术决策(工具箱加 `spatial_query`、Phase 2.5 F-11、预置空间问答样本等)都服务于上述价值链的闭环。

---

*版本 0.9 — 与《独立顾问变现规划 v2.1:空间智能 × AI × 交通的三位一体战略》对齐;空间智能正式升格为产品核心支柱;Phase 3a 工具箱加入 `spatial_query`;新增 Phase 2.5 F-11 可达性分析模块;新增 §12.5 空间能力战略章节;Spatial Transit AI Agent 框架替代原"通用交通 AI Agent 框架"命名。*