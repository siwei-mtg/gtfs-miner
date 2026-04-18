# Phase 2 TDD 任务拆解计划

**版本**：1.6  
**日期**：2026-04-18  
**状态**：进行中（Task 41–45 ✅ 已完成；Task 30–32 ✅ 已完成；Task 33 ✅ 已完成；Task 34 ✅ 已完成；Task 35 ✅ 已完成 2026-04-18）

---

## Context

Phase 2 目标（PRD §9）：**交互式地图 + 数据看板**，在 Phase 1 端到端流程基础上新增三类视图（地图、图表、增强表格）及它们之间的双向联动筛选，并支持 GeoPackage 导出。地图图层聚焦于 E_1 站点通过（空间饼状图）和 E_4 弧段通过（有向线宽），不包含路线轨迹图层（G_1/G_2）。

> **技术依赖**：所有图层数据来自 Phase 1 已入库的 15 张结果表（`result_*`）和 DWD SQLite（`{project_id}_query.sqlite`）。后端 API 无需大幅改动；主要工作在前端与地图渲染层。

### Phase 1 基线（已完成）

| 模块 | 关键文件 |
|------|---------|
| 15 张结果表（API + DB） | `backend/app/db/result_models.py`、`projects.py` |
| DWD SQLite（含 melt 规范化） | `backend/app/services/dwd_loader.py` |
| ProjectDetailPage（含 ResultTable + 下载） | `frontend/src/pages/ProjectDetailPage.tsx` |
| 前端路由（react-router-dom + AuthGuard） | `frontend/src/App.tsx` |

### 新增依赖（Phase 2 引入）

| 包 | 用途 |
|----|------|
| `tailwindcss` v4 | 全局样式工具类体系 |
| `shadcn/ui`（组件集） | Button / Card / Table / Tabs / Badge / Dialog / Sonner / Progress 等 |
| `maplibre-gl` | 矢量地图底图与图层渲染 |
| `recharts` 或 `chart.js` | 饼状图 / 柱状图 |
| `@deck.gl/layers`（可选） | E_4 有向弧段线宽渲染（如 MapLibre 原生线宽不足） |

---

## GROUP UI：前端设计系统基础（Tasks 41–45）

> Phase 2 所有前端任务（GROUP B、C）的前置依赖；可与后端 GROUP A（Tasks 30–32）**并行**开发。

**所有组件必须遵守 Atomic Design 原则（`docs/atomic-design.md` + `CLAUDE.md §前端组件架构`）**。Task 41 建立目录结构后，后续每个组件按下表归层：

| 组件 | Atomic 层 | 路径 |
|------|-----------|------|
| Button, Input, Badge, Progress, Skeleton | Atom | `components/atoms/` |
| SearchBar（Input + Button）, FormField, StatusBadge | Molecule | `components/molecules/` |
| AppHeader, ResultTable, UploadForm, ProgressPanel | Organism | `components/organisms/` |
| AppShell（AppHeader + main children）, AuthLayout（居中卡片）| Template | `components/templates/` |
| LoginPage, RegisterPage, ProjectListPage, ProjectDetailPage | Page | `pages/` |

### Task 41：Tailwind v4 + shadcn/ui 安装与设计令牌 ✅ 已完成（2026-04-12，commit `9ab3205`）

- `npm install tailwindcss @tailwindcss/vite`，在 `vite.config.ts` 注册插件
- shadcn/ui v4.2.0，zinc base color，`--primary: oklch(0.606 0.25 292.717)`（violet）
- 安装核心组件：Button、Card、Badge、Input、Select、Tabs、Table、Dialog、Sonner、Progress
- 删除 `frontend/src/App.css`，重写 `index.css`（`@import tailwindcss` + `@theme inline` + 保留 CSS 变量 + transition styles 兼容块）
- **建立 Atomic Design 目录骨架**：
  - 创建 `components/atoms/`、`components/molecules/`、`components/organisms/`、`components/templates/`
  - 创建 `src/lib/utils.ts`（`cn()` = clsx + tailwind-merge）
  - Button/Input/Badge → `atoms/`；复合组件（Table/Tabs/Dialog 等）暂留 `components/ui/`
  - DownloadButton、ProgressPanel、ResultTable、UploadForm → `organisms/`（所有内部 import 更新为 `@/`）
- **已修复回归**：Tailwind preflight 重置按钮/标题样式，通过 transition styles 块补回；LoginPage isSubmitting 状态补齐

**涉及文件**：`frontend/vite.config.ts`、`frontend/tsconfig.app.json`、`frontend/tsconfig.json`、`frontend/vitest.config.ts`、`frontend/package.json`、`frontend/components.json`（新建）、`frontend/src/index.css`、`frontend/src/App.css`（删除）、`frontend/src/lib/utils.ts`（新建）

**测试**（`frontend/src/__tests__/setup.test.tsx`）：
1. `test_tailwind_classes_applied` ✅
2. `test_shadcn_button_renders` ✅

---

### Task 42：AppHeader + AppShell + 全局布局 ✅ 已完成（2026-04-12）

**分层设计**（Atomic Design）：

| 组件 | 层级 | 路径 | 职责 |
|------|------|------|------|
| `AppHeader` | Organism | `components/organisms/AppHeader.tsx` | 顶栏 UI：logo + 用户邮箱 + Logout 按钮 |
| `AppShell` | Template | `components/templates/AppShell.tsx` | 布局骨架：`<AppHeader>` + `<main>{children}</main>` |

---

**创建文件 1**：`frontend/src/components/organisms/AppHeader.tsx`

```typescript
// Props: { email: string, onLogout: () => void }
// 左侧：文字 logo "GTFS Miner"（font-semibold text-lg）
// 右侧：email 文字（text-sm text-muted-foreground）+ Button variant="ghost" size="sm"（"Logout"）
// 使用 @/components/atoms/button（规则 A3）
```

**创建文件 2**：`frontend/src/components/templates/AppShell.tsx`

```typescript
// Props: { user: { email: string } | null, onLogout: () => void, children: ReactNode }
// 纯骨架：<div className="min-h-svh flex flex-col">
//   <AppHeader email={user.email} onLogout={onLogout} />（仅 user 非 null 时渲染）
//   <main className="flex-1 max-w-[1280px] mx-auto w-full px-6 py-8">{children}</main>
// </div>
```

替换 `App.tsx` 中的内联 header 逻辑，将认证页面（Login/Register）排除在 AppShell 外（直接渲染 `children`，不包裹 AppHeader）。

**测试**（`frontend/src/__tests__/AppHeader.test.tsx`）：
1. `test_appheader_shows_email` — 传入 email，邮箱文本出现在顶栏
2. `test_logout_button_calls_handler` — 点击 Logout，onLogout 回调被调用

**测试**（`frontend/src/__tests__/AppShell.test.tsx`）：
1. `test_appshell_renders_header_when_user` — user 非 null 时 AppHeader 存在
2. `test_appshell_hides_header_when_no_user` — user 为 null 时 AppHeader 不渲染
3. `test_appshell_hidden_on_auth_pages` — Login 路由下不渲染 AppShell 顶栏

---

### Task 43：LoginPage + RegisterPage + ProjectListPage 重构 ✅ 已完成（2026-04-12）

**LoginPage / RegisterPage**：
- shadcn Card 居中（`max-w-sm mx-auto mt-24`）+ CardHeader（标题）+ CardContent（Form）
- Input（email、password）+ Button（提交）+ 错误提示用 shadcn `Alert variant="destructive"`

**ProjectListPage**：
- shadcn Table（列：项目 ID、状态 Badge、创建时间、操作）
- Badge variant 映射：`completed→"default"`（绿）、`failed→"destructive"`（红）、`processing→"secondary"`（蓝）、`pending→"outline"`（灰）
- 顶部工具栏：搜索 Input（`placeholder="搜索项目 ID..."`）+ 状态筛选 Select + "新建项目" Button

**涉及文件**：`frontend/src/pages/LoginPage.tsx`、`RegisterPage.tsx`、`ProjectListPage.tsx`

**测试**（追加到现有测试文件）：
1. `test_login_form_renders_inputs` — email、password Input 存在
2. `test_project_list_badge_completed_green` — completed 行 Badge 含 `default` variant class
3. `test_project_list_search_filters_rows` — 搜索框输入不存在的 ID 后，列表为空

---

### Task 44：ProjectDetailPage + ProgressPanel + UploadForm 重构 ✅ 已完成（2026-04-12）

**UploadForm**：
- 拖拽上传区：`border-2 border-dashed rounded-lg p-8` + 图标 + 提示文本；点击触发 file input
- 其余字段（时段、假期类型）改用 shadcn Input / Select
- 提交按钮：shadcn Button variant="default"，加载中显示 spinner

**ProgressPanel**：
- shadcn Progress 条显示总完成百分比
- 步骤列表：完成 → `✓`（green）、进行中 → spinner icon、未开始 → `○`（gray）；耗时用 Badge variant="secondary"

**ProjectDetailPage**：
- shadcn Card 包裹各功能区块
- 顶部 Breadcrumb：`← 返回项目列表` + 项目 ID chip

**涉及文件**：`frontend/src/components/UploadForm.tsx`、`ProgressPanel.tsx`、`frontend/src/pages/ProjectDetailPage.tsx`

**测试**：
1. `test_upload_form_drag_zone_exists` — 含 `border-dashed` class 的拖拽区 div 存在
2. `test_progress_panel_completed_step_checkmark` — 完成步骤含 `✓` 文本
3. `test_project_detail_back_button` — 返回按钮存在且可点击

---

### Task 45：ResultTable 重构 ✅ 已完成（2026-04-14，commit `cdfc3c9`）

- 用 shadcn `Table / TableHeader / TableRow / TableHead / TableCell` 替换原生 `<table>`
- 分页区：shadcn `Pagination`（含 PaginationPrevious / PaginationNext / PaginationItem）
- 列头排序：`Button variant="ghost"` + Lucide `ChevronUp` / `ChevronDown` 图标（按状态切换）
- 单表下载：`Button variant="outline" size="sm"`
- **现有功能（分页逻辑、排序状态、API 调用）保持不变，仅替换 DOM 结构**

**涉及文件**：`frontend/src/components/ResultTable.tsx`

**测试**（现有测试不应回归）：
1. `test_result_table_renders_shadcn_header` — DOM 含 shadcn TableHead 元素
2. `test_result_table_sort_toggle_icon` — 点击列头，排序图标 class 切换
3. `test_result_table_pagination_prev_next` — 上一页 / 下一页按钮存在

---

## GROUP A：后端地图数据 API（Task 30–31）

> 为前端地图提供 GeoJSON / 数值端点；不修改现有 result 表结构。

### Task 30：E_1 站点通过 API（饼状图数据）

**背景**：前端需要每个 AG 的「各 route_type 通过次数」用于渲染空间饼状图扇区。

**新增端点**：`GET /api/v1/projects/{project_id}/map/passage-ag`

```
查询参数：
  jour_type: int          （必填，指定日类型）

返回：GeoJSON FeatureCollection
  Feature.geometry: Point（AG 坐标）
  Feature.properties: {
    id_ag_num, stop_name,
    nb_passage_total: int,
    by_route_type: { "bus": int, "tram": int, ... }   （按途经线路 route_type 聚合）
  }
```

**新增函数**：`map_builder.build_passage_ag_geojson(project_id, jour_type, db)`

- `result_e1_passage_ag` JOIN `result_c2_itineraire` JOIN `result_b1_lignes` → 聚合 route_type
- 按 `id_ag_num` 聚合，与 `result_a1_arrets_generiques` join 取坐标

**测试**（追加到 `tests/test_map_api.py`）：
1. `test_passage_ag_structure` — Point geometry，properties 含 `by_route_type`
2. `test_passage_ag_jour_type_required` — 缺 jour_type → 422
3. `test_passage_ag_total_equals_sum` — `nb_passage_total == sum(by_route_type.values())`

**依赖**：Task 19

---

### Task 31：E_4 弧段通过 API（AequilibraE 带宽数据）✅ 已完成（2026-04-14）

**背景**：E_4 弧段具有方向性。参照 AequilibraE Bandwidth on network links，后端返回弧段中心线 + 归一化权重 + 可选类别分组信息，前端据此渲染可变宽度带宽矩形。

**新增端点**：`GET /api/v1/projects/{project_id}/map/passage-arc`

```
查询参数：
  jour_type: int                        （必填）
  split_by: "none" | "route_type"       （可选，默认 "none"）

返回：GeoJSON FeatureCollection

当 split_by="none"（每条弧段 1 个 Feature）：
  Feature.geometry: LineString [[lon_a, lat_a], [lon_b, lat_b]]
  Feature.properties:
    id_ag_num_a, id_ag_num_b
    nb_passage: float
    direction: "AB" | "BA"              （AB: a ≤ b；BA: a > b）
    weight: float                       （= nb_passage / max_nb_passage，全局归一化）
    split_by: "none"

当 split_by="route_type"（每条弧段 × N route_type = N 个 Feature）：
  Feature.geometry: LineString（同上，共享中心线）
  Feature.properties:
    id_ag_num_a, id_ag_num_b
    direction: "AB" | "BA"
    weight: float                       （该方向总量归一化，全局 max_total 基准）
    split_by: "route_type"
    category_value: str                 （route_type 值，如 "3" "0"）
    nb_passage_category: float
    fraction_of_direction: float        （本类别占该方向总量的比例）
    cumulative_fraction_start: float    （堆叠起始位置，0 = 紧贴中心线侧）
```

**前端渲染公式**（Task 35 补充）：
```
// split_by="none"：
line_width  = weight × max_width_px
line_offset = sign(direction) × (gap_px/2 + line_width/2)

// split_by="route_type"：每个 Feature 独立一条 MapLibre line
sub_width   = fraction_of_direction × weight × max_width_px
line_width  = sub_width
line_offset = sign(direction) × (gap_px/2 + cumulative_fraction_start × weight × max_width_px + sub_width/2)

// sign(direction): AB → +1, BA → -1
// max_width_px, gap_px 均由用户通过前端滑块调节（默认 40px / 4px）
```

**新增函数**：`map_builder.build_passage_arc_geojson(project_id, jour_type, db, split_by)`

```
基础逻辑（split_by="none"）：
  - 查询 result_e4_passage_arc（project_id + type_jour）
  - JOIN result_a1_arrets_generiques 取 A/B 坐标
  - weight = nb_passage / max(nb_passage)
  - direction = "AB" if a ≤ b else "BA"

分组逻辑（split_by="route_type"）：
  - 额外查询 C3 JOIN D1 JOIN B1：
      COUNT DISTINCT C3.id_course_num
      GROUP BY (C3.id_ag_num_a, C3.id_ag_num_b, B1.route_type)
      WHERE D1.Type_Jour == jour_type
  - 按 route_type 分解 nb_passage（按比例分配总量）
  - 计算 fraction_of_direction 和 cumulative_fraction_start（按 route_type 排序后累加）
  - 每个类别生成一个 Feature（共享 LineString 几何）
```

**测试**（追加到 `tests/test_map_api.py`）：

*基础测试（PROJECT_ID_ARC = "proj-t31"，split_by 默认）*：
1. `test_passage_arc_has_direction` — direction ∈ {"AB","BA"}
2. `test_passage_arc_ab_ba_separate` — AB 和 BA Feature 同时存在
3. `test_passage_arc_geometry_is_linestring` — geometry.type=="LineString"，坐标数==2
4. `test_passage_arc_weight_normalized` — max(weight)==1.0，所有 weight ∈ [0,1]
5. `test_passage_arc_jour_type_required` — 缺 jour_type → 422

*分组测试（PROJECT_ID_ARC_SPLIT = "proj-t31s"，split_by=route_type）*：
6. `test_passage_arc_split_returns_multiple_features_per_arc` — 有 2 种 route_type 时同一弧段返回 2 个 Feature
7. `test_passage_arc_split_fractions_sum_to_one` — 同弧同方向 fraction_of_direction 之和 == 1.0
8. `test_passage_arc_split_cumulative_start_ordered` — cumulative_fraction_start 严格递增

**依赖**：Task 19

---

### Task 32：GeoPackage 导出 API ✅ 已完成（2026-04-15）

**新增端点**：`GET /api/v1/projects/{project_id}/export/geopackage`

```
查询参数：
  jour_type: int   （必填）
```

将以下图层写入单个 `.gpkg` 文件，使用 `fiona` 或 `geopandas`：

| 图层名 | 几何类型 | 数据来源 | 说明 |
|--------|---------|---------|------|
| `passage_ag` | Point | E_1 | 站点通过，含 `nb_passage` |
| `passage_arc` | LineString | E_4 | **单图层含全部有向弧段**；`direction` 字段区分 AB/BA；含 `nb_passage`、`max_nb_passage` 字段，供 QGIS 数据定义渲染 |
| `arrets_generiques` | Point | A_1 | 通用站点 |
| `arrets_physiques` | Point | A_2 | 物理站点 |

> **设计原则**：AB 与 BA 同属 `passage_arc` 图层，`direction` 字段区分，无需拆分图层。

返回：`StreamingResponse`，Content-Type `application/geopackage+sqlite3`，文件名 `{project_id}.gpkg`

**修改文件**：`backend/app/services/map_builder.py`（`export_geopackage(project_id, jour_type, db) → Path`）

**新增依赖**：`geopandas`、`fiona`（已在 Dockerfile 系统库中）

**`passage_arc` LineString 字段说明**：

`passage_arc` 以 LineString 导出，携带以下属性字段，在 QGIS 中通过「数据定义覆盖」渲染带宽效果：

| 字段 | 说明 |
|------|------|
| `nb_passage` | 该弧段方向的通过次数 |
| `max_nb_passage` | 图层全局最大值（所有弧段同值），用于 `scale_linear` 归一化 |
| `direction` | `"AB"` 或 `"BA"` |

QGIS 数据定义覆盖（线段渲染）：
- **线宽（px）**：`scale_linear("nb_passage", 0, "max_nb_passage", 0, max_width_pixel)`
- **偏移量（px）**：`if("direction"='AB', 1, -1) * (scale_linear(...)/2 + 0.1)`
- **线型**：`if(coalesce("nb_passage", 0) = 0, 'no', 'solid')`

**内存策略（分批计算）**：

GeoPackage 导出的内存瓶颈在 GeoDataFrame 构建（geopandas join + geometry 构造），而非写文件格式本身。IDFM 规模全量一次性构建峰值约 800 MB–1.2 GB，须采用分批策略：逐图层处理，写完即释放；大图层按每批 ≤ 500 个 AG 分批构建，用 `fiona` append 模式追加写入。

**测试**（`tests/test_geopackage_export.py`）：
1. `test_gpkg_file_created` — 返回 200，Content-Type 正确
2. `test_gpkg_contains_expected_layers` — 用 fiona 打开，layer 列表含上表所有图层名
3. `test_gpkg_passage_ag_has_nb_passage` — `passage_ag` 层含 `nb_passage` 字段且值 > 0
4. `test_gpkg_arc_single_layer_with_direction` — `passage_arc` 图层含 `direction` 字段，AB 和 BA 行均存在
5. `test_gpkg_batch_no_duplicate_features` — 分批写入时不产生重复要素（行数 = 预期总行数）
6. `test_gpkg_arc_geometry_is_linestring` — `passage_arc` 几何类型为 LineString（非 Polygon）
7. `test_gpkg_arc_has_max_nb_passage` — `max_nb_passage` 字段存在且全行等于图层最大值

**依赖**：Tasks 30–31

---

## GROUP B：前端地图组件（Task 33–36）

### Task 33：MapLibre 底图组件 ✅ 已完成（2026-04-15）

**创建文件**：`frontend/src/components/organisms/MapView.tsx`
（注：实际路径按 CLAUDE.md Atomic Design 规则放入 `organisms/`，非原计划的 `components/MapView.tsx`）

```typescript
// Props：{ projectId: string, jourType: number, onStopClick?, className? }
// 渲染 MapLibre GL JS 地图，OSM 底图
// 暴露图层开关（E_1/E_4）
// 点击 AG → 触发 onStopClick(id_ag_num) 回调
```

**新增依赖**：`maplibre-gl@^4`（直接封装；未引入 react-map-gl）
**CSS**：`maplibre-gl/dist/maplibre-gl.css` 挂载于 `main.tsx`（避免 vitest/jsdom 解析失败）

**测试**（`frontend/src/__tests__/MapView.test.tsx`）：
1. `test_mapview_renders` ✅ — 容器 div 存在
2. `test_layer_toggles_visible` ✅ — 切换图层开关后 checkbox 状态变化
3. `test_stop_click_callback` ✅ — 模拟点击事件，onStopClick 被调用

**依赖**：Task 30（API 契约）

---

### Task 34：E_1 空间饼状图图层 ✅ 已完成（2026-04-16 核对发现已实现）

**创建文件**：`frontend/src/components/PassageAGLayer.tsx`（已存在）

- 调用 `GET /map/passage-ag?jour_type=X`
- 在每个 AG 坐标处渲染 SVG 饼状图 Marker，扇区颜色 = route_type 配色（`frontend/src/lib/map-utils.ts` → `generatePieSvg`、`ROUTE_TYPE_COLORS`）
- 饼状图半径对数比例缩放：`10 + 5 * log10(nb_passage_total)`
- 点击 Marker → 触发 `onStopClick(id_ag_num)` 回调（`ProjectDetailPage.tsx:106` 已接入：点击切换到 `viewMode='table'` + 跳转 A1 tab）

**实际实现要点**（与原计划差异）：
- 通过 `MapContext` 获取 map 实例，通过 `useAuthContext` 获取 JWT，API 请求带 `Authorization: Bearer` header
- 组件返回 `null`（不渲染 DOM，仅管理 MapLibre Markers）
- 通过 `MapView` 的 `<div className="hidden">` children wrapper 接入，`visible` prop 从 MapView 的 E_1 checkbox 状态传入

**测试**（`frontend/src/__tests__/PassageAGLayer.test.tsx`）：
1. `should fetch data with Authorization header and create markers when visible` ✅
2. `should remove markers on unmount` ✅
3. `should not fetch data if not visible` ✅

**依赖**：Task 30、Task 33

---

### Task 35：E_4 有向弧段图层 ✅ 已完成（2026-04-18）

**创建文件**：`frontend/src/components/PassageArcLayer.tsx`

- 调用 `GET /map/passage-arc?jour_type=X`（`split_by="none"`，返回 `weight`、`direction`、`nb_passage`）
- MapLibre paint 配置（`maxWidthPx` 默认 40，通过 props 传入）：

```json
{
  "line-width": ["*", ["get", "weight"], 40],
  "line-offset": [
    "*",
    ["case", ["==", ["get", "direction"], "AB"], 1, -1],
    ["+", ["*", ["*", ["get", "weight"], 40], 0.5], 0.1]
  ],
  "line-opacity": ["case", ["==", ["get", "nb_passage"], 0], 0, 1]
}
```

渲染规则：
- 线宽（px） = `weight × maxWidthPx`（`weight` 已由后端归一化为 0–1）
- 偏移量（px） = `±(线宽/2 + 0.1)`，AB 向右（+1），BA 向左（−1），视觉上不重叠
- 无通过次数时隐藏（opacity=0）
- `maxWidthPx` 通过 props 暴露，可接入前端滑块

> 与 GeoPackage QGIS 公式等价：`weight = nb_passage / max_nb_passage`，两套渲染逻辑一致。

- 鼠标悬停 → tooltip 显示 `nb_passage` 数值

**测试**（`frontend/src/__tests__/PassageArcLayer.test.tsx`）：
1. `test_renders_ab_and_ba` — mock API，AB 和 BA 方向均有对应要素
2. `test_hover_shows_tooltip` — 模拟 mouseover，tooltip 出现含 nb_passage
3. `test_max_width_px_prop` — 传入 `maxWidthPx=20`，验证 paint 配置中线宽表达式使用 20

**依赖**：Task 31、Task 33

**实际实现要点**（与原计划差异及补丁）：

1. **架构决策**：让 `PassageArcLayer` 独占 `passage-arc` 源+图层的完整生命周期（幂等创建、组件卸载不移除，随 MapView `map.remove()` 统一清理）。MapView 删除原 E_4 占位源/图层和独立可见性 `useEffect`，通过 `cloneElement` 注入 `visible=e4Visible`。
2. **后端几何规范化**（修正原渲染公式的侧效应）：`map_builder.build_passage_arc_geojson` 与 `export_geopackage` 统一把 LineString 方向规范化为 `min(a,b)→max(a,b)`，`direction` 字段独立携带语义流向。否则 AB 与 BA 的几何反向叠加 `sign(direction)` 偏移会把两者折回同侧。新增 `test_passage_arc_geometry_orientation_normalized` 作回归守护。GeoPackage QGIS `if("direction"='AB', 1, -1) * ...` 表达式同样受益。
3. **修复 Task 34 遗漏的 popup 计数 BUG**（实施 Task 35 时发现）：`build_passage_ag_geojson` step 2（C2→B1 count）原先**未 JOIN D2 过滤 `type_jour`**，导致 popup 显示的 `nb_passage_total` 跨所有运营日累计，实测 AG 10692 显示 2247 而正确值 598（与 `result_e1_passage_ag.nb_passage` 一致）。修复：追加 `D2 JOIN` on `(id_service_num, id_ligne_num, project_id) + Type_Jour == jour_type`；fixture 扩展含 `id_service_num` 和 D2 seed；新增 `test_passage_ag_counts_respect_jour_type` 作回归。

---

### Task 36：GeoPackage 下载按钮

**修改文件**：`frontend/src/pages/ProjectDetailPage.tsx`

在地图区域旁添加「导出 GeoPackage」按钮：
- 触发 `GET /export/geopackage?jour_type=X`
- 下载文件名：`{project_id}.gpkg`

**测试**（追加到 `frontend/src/__tests__/ProjectDetailPage.test.tsx`，或新建）：
1. `test_gpkg_button_exists` — 按钮存在
2. `test_gpkg_button_triggers_download` — 点击后发出正确 GET 请求

**依赖**：Task 32

---

## GROUP C：数据看板 F-08（Task 37–40）

### Task 37：图表视图组件

**创建文件**：`frontend/src/components/DashboardCharts.tsx`

**图表列表**（使用 `recharts`）：

| 图表 | 数据来源 | 类型 |
|------|---------|------|
| 线路交通模式构成 | `result_b1_lignes.route_type` | PieChart |
| 各线路班次数对比（Top 20） | `result_f1_nb_courses_lignes` | BarChart |
| KCC 排行（Top 20） | `result_f3_kcc_lignes` | BarChart |
| 各时段 AG 通过次数（高峰 vs 平峰） | `result_e1_passage_ag` × `result_f2_caract_sous_lignes` | BarChart |

Props：`{ projectId: string, jourType: number, filters: FilterState }`

**测试**（`frontend/src/__tests__/DashboardCharts.test.tsx`）：
1. `test_pie_chart_renders` — mock API，PieChart 存在
2. `test_bar_chart_top20` — BarChart 最多渲染 20 条数据
3. `test_charts_respond_to_filter` — 传入 filters 后重新请求 API

**依赖**：Task 19（API 契约）

---

### Task 38：增强表格筛选器

**修改文件**：`frontend/src/components/ResultTable.tsx`

在现有分页/搜索基础上新增：
- **多选下拉筛选**：枚举类字段（如 `route_type`）支持多选
- **数值范围过滤**：数值类字段支持 `min/max` 输入
- 筛选条件变化时触发 `onFilterChange(filters)` 回调（供联动使用）

**修改 API**：`GET /tables/{table_name}` 追加查询参数
- `filter_field`: 字段名
- `filter_values`: 逗号分隔的枚举值
- `range_field` / `range_min` / `range_max`: 数值范围

**测试**（追加到 `frontend/src/__tests__/ResultTable.test.tsx`）：
1. `test_multi_select_filter_renders` — 枚举列有多选下拉
2. `test_range_filter_renders` — 数值列有 min/max 输入框
3. `test_filter_triggers_api_call` — 选中筛选项后发出带参数的 API 请求

**依赖**：Task 19

---

### Task 39：三视图联动筛选

**创建文件**：`frontend/src/hooks/useDashboardSync.ts`

```typescript
// 全局筛选状态 context，三个视图共享
// FilterState: { jourType, routeTypes, ligneIds, agIds, bbox }
// 提供：setJourType / toggleRouteType / setLigneFilter / setMapBbox
// 订阅：每次 state 变化通知所有视图重新加载
```

**创建文件**：`frontend/src/pages/DashboardPage.tsx`

布局：左侧地图（MapView + 图层），右侧上方图表（DashboardCharts），右侧下方表格（ResultTable）

联动规则：
- 表格多选筛选 `routeTypes` → 图表重算 + 地图高亮对应 AG
- 地图框选区域（bbox）→ 表格过滤为区域内 AG + 图表同步
- 图表扇区/柱体点击 → 表格 + 地图同步过滤

**测试**（`frontend/src/__tests__/DashboardPage.test.tsx`）：
1. `test_dashboard_renders_three_panels` — 地图、图表、表格三个区域均存在
2. `test_filter_from_chart_updates_table` — 模拟图表点击，表格收到 filter props
3. `test_filter_from_table_updates_chart` — 模拟表格筛选变化，图表 filters props 更新

**依赖**：Tasks 33–38

---

### Task 40：套餐限制 + 路由接入

**修改文件**：`frontend/src/App.tsx`

新增路由：`/projects/:id/dashboard` → `DashboardPage`（需认证）

**套餐门控**：
- Free 用户：地图图层（MapView）隐藏，仅展示图表 + 增强表格
- Pro / Enterprise：完整三视图

**修改文件**：`frontend/src/pages/ProjectDetailPage.tsx`

在结果页顶部添加「查看看板」按钮，跳转至 DashboardPage。

**测试**（`frontend/src/__tests__/App.test.tsx`，追加）：
1. `test_dashboard_route_authenticated` — 已登录可访问 `/projects/:id/dashboard`
2. `test_dashboard_route_redirects_unauthenticated` — 未登录 → `/login`

**依赖**：Task 39

---

## 关键文件清单

**GROUP UI（新增）**

| 文件 | 变更类型 |
|------|---------|
| `frontend/vite.config.ts` | 修改（Tailwind plugin） |
| `frontend/package.json` | 修改（新增依赖） |
| `frontend/src/index.css` | 修改（保留 CSS 变量，清理手写规则） |
| `frontend/src/App.css` | 删除 |
| `frontend/src/components/organisms/AppHeader.tsx` | 新建（顶栏 Organism：logo + email + Logout） |
| `frontend/src/components/templates/AppShell.tsx` | 新建（布局 Template：AppHeader + main children） |
| `frontend/src/pages/LoginPage.tsx` | 修改（shadcn Card + Form） |
| `frontend/src/pages/RegisterPage.tsx` | 修改（shadcn Card + Form） |
| `frontend/src/pages/ProjectListPage.tsx` | 修改（shadcn Table + Badge + 搜索/筛选） |
| `frontend/src/pages/ProjectDetailPage.tsx` | 修改（shadcn Card + Breadcrumb） |
| `frontend/src/components/ProgressPanel.tsx` | 修改（shadcn Progress + 步骤图标） |
| `frontend/src/components/UploadForm.tsx` | 修改（拖拽区 + shadcn Input/Select） |
| `frontend/src/components/ResultTable.tsx` | 修改（shadcn Table + Pagination） |
| `frontend/src/App.tsx` | 修改（接入 AppShell） |

**GROUP A–C（原有）**

| 文件 | 变更类型 |
|------|---------|
| `backend/app/services/map_builder.py` | 新建（GeoJSON 构建 + GeoPackage 导出） |
| `backend/app/api/endpoints/projects.py` | 修改（新增 /map/* + /export/geopackage 端点） |
| `backend/tests/test_map_api.py` | 新建 |
| `backend/tests/test_geopackage_export.py` | 新建 |
| `frontend/src/components/MapView.tsx` | 新建 |
| `frontend/src/components/PassageAGLayer.tsx` | 新建 |
| `frontend/src/components/PassageArcLayer.tsx` | 新建 |
| `frontend/src/components/DashboardCharts.tsx` | 新建 |
| `frontend/src/hooks/useDashboardSync.ts` | 新建 |
| `frontend/src/pages/DashboardPage.tsx` | 新建 |
| `frontend/src/pages/ProjectDetailPage.tsx` | 修改（看板入口 + GeoPackage 按钮） |
| `frontend/src/App.tsx` | 修改（新增 /dashboard 路由） |

---

## 执行顺序

```
Task 41 → 42 → 43 → 44 → 45 ─────────────────────────────────────┐
（GROUP UI：前端设计系统基础）                                       │
                                                                    ▼
Task 30 → Task 31 ──┐                          Task 33（底图）──→ Task 34 ──┐
                    ├──→ Task 32（GeoPackage）               Task 35 ────────┤
                                                             Task 36 ────────┘

Task 37（图表）──┐
Task 38（筛选）──┼──→ Task 39（联动）──→ Task 40（路由 + 门控）
Task 33 ─────────┘
```

- GROUP UI（Tasks 41–45）与 GROUP A（Tasks 30–32）**可并行**
- Tasks 33–40（所有前端组件）**依赖 Task 45 完成**

GROUP A（Tasks 30–32）与 GROUP UI 并行；看板联动（Task 39）依赖所有子组件（Tasks 33–38）就绪。
