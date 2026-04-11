# Phase 2 TDD 任务拆解计划

**版本**：1.0  
**日期**：2026-04-11  
**状态**：待开始

---

## Context

Phase 2 目标（PRD §9）：**交互式地图 + 数据看板**，在 Phase 1 端到端流程基础上新增三类视图（地图、图表、增强表格）及它们之间的双向联动筛选，并支持 GeoPackage 导出。

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
| `maplibre-gl` | 矢量地图底图与图层渲染 |
| `recharts` 或 `chart.js` | 饼状图 / 柱状图 |
| `@deck.gl/layers`（可选） | E_4 有向弧段线宽渲染（如 MapLibre 原生线宽不足） |

---

## GROUP A：后端地图数据 API（Task 29–31）

> 为前端地图提供 GeoJSON / 数值端点；不修改现有 result 表结构。

### Task 29：G 层轨迹 GeoJSON API

**背景**：G_1（子线路轨迹）和 G_2（线路轨迹）需要从 `result_c3_itineraire_arc` + `result_a1_arrets_generiques` 坐标重建线段几何，以 GeoJSON FeatureCollection 形式返回。

**新增端点**：`GET /api/v1/projects/{project_id}/map/routes`

```
查询参数：
  jour_type: int | None   （筛选日类型，默认不过滤）
  ligne_ids: str | None   （逗号分隔的 id_ligne_num，默认全部）

返回：GeoJSON FeatureCollection
  Feature.geometry: LineString（按 id_ag_num_a/b 坐标连线）
  Feature.properties: { id_ligne_num, route_short_name, route_type, sous_ligne }
```

**新增文件**：`backend/app/services/map_builder.py`

```python
def build_routes_geojson(project_id: str, db: Session, ...) -> dict
```

- 从 `result_c3_itineraire_arc` 取弧段，join `result_a1_arrets_generiques` 取坐标
- 按 `sous_ligne` 聚合为 LineString Feature

**测试**（`tests/test_map_api.py`）：
1. `test_routes_geojson_structure` — 返回 200，type="FeatureCollection"，features 非空
2. `test_routes_geojson_properties` — 每个 Feature 含 `route_short_name`、`route_type`
3. `test_routes_filter_by_ligne` — ligne_ids 过滤后 features 数量减少
4. `test_routes_unauthorized` — 无 token → 401
5. `test_routes_wrong_tenant` — 跨租户 → 404

**依赖**：Task 19（结果查询 API）

---

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

### Task 31：E_4 弧段通过 API（有向线宽数据）

**背景**：E_4 弧段具有方向性，A→B 与 B→A 是两条独立弧段，各自的通过量绘制在该弧段右侧（偏移线）。

**新增端点**：`GET /api/v1/projects/{project_id}/map/passage-arc`

```
查询参数：
  jour_type: int          （必填）

返回：GeoJSON FeatureCollection
  Feature.geometry: LineString（A→B 方向，坐标已向右偏移）
  Feature.properties: {
    id_ag_num_a, id_ag_num_b,
    nb_passage: int,
    direction: "AB" | "BA",
    offset_m: float        （右侧偏移量，单位米，前端可覆盖）
  }
```

**新增函数**：`map_builder.build_passage_arc_geojson(project_id, jour_type, db)`

- 从 `result_e4_passage_arc` 取 (id_ag_num_a, id_ag_num_b, nb_passage)
- join `result_a1_arrets_generiques` × 2 取 A、B 坐标
- 对每条弧段计算垂直右偏移坐标（`_offset_linestring(lat_a, lon_a, lat_b, lon_b, offset_m=5)`）
- `direction="AB"` 保持顺序，`direction="BA"` 反转（B→A 弧段单独一行）

**测试**（追加到 `tests/test_map_api.py`）：
1. `test_passage_arc_has_direction` — properties 含 `direction` in ["AB","BA"]
2. `test_passage_arc_ab_ba_separate` — 同一对站点同时出现 AB 和 BA 两行
3. `test_passage_arc_geometry_offset` — AB 与 BA 的 LineString 坐标不完全相同（已偏移）

**依赖**：Task 19

---

### Task 32：GeoPackage 导出 API

**新增端点**：`GET /api/v1/projects/{project_id}/export/geopackage`

将以下图层写入单个 `.gpkg` 文件，使用 `fiona` 或 `geopandas`：

| 图层名 | 几何类型 | 数据来源 |
|--------|---------|---------|
| `routes_sous_ligne` | LineString | G_1（子线路轨迹） |
| `routes_ligne` | LineString | G_2（线路聚合轨迹） |
| `passage_ag` | Point | E_1（站点通过，含 nb_passage） |
| `passage_arc_AB` | LineString | E_4 方向 AB |
| `passage_arc_BA` | LineString | E_4 方向 BA |
| `arrets_generiques` | Point | A_1 |
| `arrets_physiques` | Point | A_2 |

返回：`StreamingResponse`，Content-Type `application/geopackage+sqlite3`，文件名 `{project_id}.gpkg`

**修改文件**：`backend/app/services/map_builder.py`（新增 `export_geopackage(project_id, jour_type, db) → Path`）

**新增依赖**：`geopandas`、`fiona`（已在 Dockerfile 系统库中）

**内存策略（分批计算）**：

GeoPackage 导出的内存瓶颈在 GeoDataFrame 构建（geopandas join + geometry 构造），而非写文件格式本身。IDFM 规模全量一次性构建峰值约 800 MB–1.2 GB，须采用分批策略：

```python
def export_geopackage(project_id: str, jour_type: int, db: Session) -> Path:
    out_path = ...
    # 逐图层处理，写完即释放，避免所有图层同时在内存
    for layer_name, build_fn in LAYER_BUILDERS:
        gdf = build_fn(project_id, jour_type, db)   # 单图层 GeoDataFrame
        gdf.to_file(out_path, layer=layer_name, driver="GPKG")
        del gdf                                       # 立即释放
    return out_path
```

对 `passage_ag` / `passage_arc` 等大图层，`build_fn` 内部按每批 ≤ 500 个 AG 分批构建，使用 `fiona` append 模式追加写入：

```python
for chunk_ids in chunked(ag_ids, 500):
    gdf_chunk = _build_chunk(chunk_ids, ...)
    gdf_chunk.to_file(out_path, layer=layer_name, driver="GPKG", mode="a")
    del gdf_chunk
```

**测试**（`tests/test_geopackage_export.py`）：
1. `test_gpkg_file_created` — 返回 200，Content-Type 正确
2. `test_gpkg_contains_expected_layers` — 用 fiona 打开，layer 列表含上表所有图层名
3. `test_gpkg_passage_ag_has_nb_passage` — `passage_ag` 层含 `nb_passage` 字段且值 > 0
4. `test_gpkg_arc_direction_separated` — `passage_arc_AB` 与 `passage_arc_BA` 均存在且行数 > 0
5. `test_gpkg_batch_no_duplicate_features` — 分批写入时不产生重复要素（行数 = 预期总行数）

**依赖**：Tasks 29–31

---

## GROUP B：前端地图组件（Task 33–36）

### Task 33：MapLibre 底图组件

**创建文件**：`frontend/src/components/MapView.tsx`

```typescript
// Props：{ projectId: string, jourType: number }
// 渲染 MapLibre GL JS 地图，OSM 底图
// 暴露图层开关（G_1/G_2/E_1/E_4）
// 点击 AG → 触发 onStopClick(id_ag_num) 回调
```

**新增依赖**：`maplibre-gl`、`react-map-gl`（或直接封装 maplibre-gl）

**测试**（`frontend/src/__tests__/MapView.test.tsx`）：
1. `test_mapview_renders` — 容器 div 存在
2. `test_layer_toggles_visible` — 切换图层开关后 checkbox 状态变化
3. `test_stop_click_callback` — 模拟点击事件，onStopClick 被调用

**依赖**：Task 29（API 契约）

---

### Task 34：E_1 空间饼状图图层

**创建文件**：`frontend/src/components/PassageAGLayer.tsx`

- 调用 `GET /map/passage-ag?jour_type=X`
- 在每个 AG 坐标处渲染 SVG 饼状图 Marker，扇区颜色 = route_type 配色
- 饼状图半径与 `nb_passage_total` 对数比例缩放
- 点击 Marker → 侧面板显示详情

**测试**（`frontend/src/__tests__/PassageAGLayer.test.tsx`）：
1. `test_renders_markers_for_each_ag` — mock API，markers 数量 = response features 数量
2. `test_pie_sectors_count` — 每个 marker 的扇区数 = `by_route_type` key 数量
3. `test_click_opens_side_panel` — 点击 marker → 侧面板出现

**依赖**：Task 30、Task 33

---

### Task 35：E_4 有向弧段图层

**创建文件**：`frontend/src/components/PassageArcLayer.tsx`

- 调用 `GET /map/passage-arc?jour_type=X`
- 用 MapLibre `line-width` 表达式按 `nb_passage` 线性/对数缩放线宽
- AB 与 BA 弧段各自渲染（坐标已由后端偏移，视觉上右侧分离）
- 鼠标悬停 → tooltip 显示 `nb_passage` 数值

**测试**（`frontend/src/__tests__/PassageArcLayer.test.tsx`）：
1. `test_renders_ab_and_ba` — mock API，AB 和 BA 方向均有对应要素
2. `test_hover_shows_tooltip` — 模拟 mouseover，tooltip 出现含 nb_passage

**依赖**：Task 31、Task 33

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
| `frontend/src/components/ResultTable.tsx` | 修改（增强筛选器） |
| `frontend/src/pages/ProjectDetailPage.tsx` | 修改（看板入口 + GeoPackage 按钮） |
| `frontend/src/App.tsx` | 修改（新增 /dashboard 路由） |

---

## 执行顺序

```
Task 29 → Task 30 → Task 31 ──┐
                               ├──→ Task 32（GeoPackage 导出）
                               │
Task 33（底图）──→ Task 34 ────┤
                Task 35 ───────┤
                Task 36 ───────┘

Task 37（图表）──┐
Task 38（筛选）──┼──→ Task 39（联动）──→ Task 40（路由 + 门控）
Task 33 ─────────┘
```

后端（Tasks 29–32）可与前端底图（Task 33）并行开发；看板联动（Task 39）依赖所有子组件就绪。
