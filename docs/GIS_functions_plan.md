# 代码中的 GIS 功能 — 当前状态与 Web 迁移计划

## 1. GIS 功能清单

目前代码中包含 5 类 GIS 功能，其复杂程度各不相同：

### 1.1 空间聚类 (AG/AP) — `gtfs_spatial.py`

**作用**：根据地理邻近性，将物理站点（AP，location_type=0）归类为逻辑站点（AG，逻辑站台）。

**当前实现**：

| 变体 | 函数 | 算法 | 触发条件 |
| :--- | :--- | :--- | :--- |
| **原生 GTFS 层级** | `ag_ap_generate_asit()` | 直接读取 `parent_station` | 所有 AP 均有父级站点 |
| **层级聚类** | `ag_ap_generate_hcluster()` | 基于 Haversine 距离矩阵进行 `scipy.cluster.hierarchy.linkage()` + `cut_tree(height=100m)` | 无父级站点的 AP 数量 < 5,000 |
| **两阶段聚类** | `ag_ap_generate_bigvolume()` | 先进行 K-Means (k = AP总数 / 500)，再在簇内进行层级聚类 | AP 数量 ≥ 5,000 |
| **自适应选择** | `ag_ap_generate_reshape()` | 在上述三种方法中进行裁定 | 始终运行（入口点） |

**依赖库**：`scipy.cluster.hierarchy`, `scipy.cluster.vq`, `numpy`
**输出**：两个表格型 DataFrame（AG 和 AP），无几何对象，仅在 `stop_lat`/`stop_lon` 列中存有坐标。

**关键点**：此处从未实例化几何图形，属于纯矩阵计算。唯一的 GIS 依赖是距离公式 (Haversine)。

---

### 1.2 距离计算 — `gtfs_utils.py`

**作用**：计算站点间的直线距离（单位：米）。

**具体实现**：

- **`getDistHaversine(lat1, lon1, lat2, lon2)`**
  - 基于 WGS84 椭球体的 Haversine 公式。
  - 支持 numpy 数组。
  - 返回米（float 或数组）。

- **`distmatrice(nparray [[lon, lat], ...])`**
  - 通过 `squareform()` 构建 NxN 压缩矩阵。
  - 供 `linkage()` 用于层级聚类。

**在流水线中的用途**：
- 空间聚类（用于 `linkage()` 的 NxN 完整矩阵）。
- 在 `itiarc_generate()` 中计算 `DIST_Vol_Oiseau`（直线距离）—— 针对每个弧（A→B 站点），在数百万行数据上进行向量化计算。

**依赖库**：`numpy`, `scipy.spatial.distance.squareform`
**状态**：无 QGIS 依赖。这些函数已 100% 可直接移植到 Web 环境。

---

### 1.3 轨迹生成 — `gtfs_export.py` + `gtfs_generator.py`

**作用**：生成代表每条子线路路径的有序坐标点序列。

**两种来源**：

| 情况 | 函数 | 坐标来源 | 输出 |
| :--- | :--- | :--- | :--- |
| **提供 shapes.txt** | `corr_sl_shape()` | 来自 `shapes.txt` 的点（`shape_pt_lat/lon`，带序号） | 按 `shape_pt_sequence` 排序的点 DataFrame |
| **缺失 shapes.txt** | `trace_sl_vol_oiseau()` | 按停靠顺序排列的 AG 坐标 | 按 `stop_sequence` 排序的点 DataFrame |

**输出**：点 DataFrame（`sous_ligne`, `stop_lon`, `stop_lat`, `ordre`）—— 尚未转换为几何图形，仅为有序坐标表。

**状态**：无 QGIS 依赖。这些函数可以移植。

---

### 1.4 QGIS 矢量图层创建 — `gtfs_qgis_adapter.py`

**作用**：将坐标 DataFrame 转换为 QGIS 几何对象，用于可视化和 Shapefile 导出。

**相关函数**：

| 函数 | 几何类型 | 输入 | QGIS 输出 |
| :--- | :--- | :--- | :--- |
| `create_qgsLines()` | LineString | 有序的点 DataFrame (`sous_ligne`, `stop_lon`, `stop_lat`) | 内存中的 `QgsVectorLayer` (EPSG:4326) |
| `aggregate_polylines_by_category()` | MultiLineString | 子线路图层 | 按 `id_ligne_num` 聚合的 `QgsVectorLayer` |
| `Qgs_PassageAG()` | Point | 点 DataFrame (`id_ag_num`, `stop_lon`, `stop_lat`) | `QgsVectorLayer` + 关联的通过次数 CSV |
| `Qgs_PassageArc()` | LineString | 按弧划分的 DataFrame (`LON_x`, `LAT_x`, `LON_y`, `LAT_y`) | `QgsVectorLayer` + 关联的通过次数 CSV |

**PyQGIS 依赖库**：`QgsVectorLayer`, `QgsGeometry`, `QgsPointXY`, `QgsDistanceArea`, `processing.run('qgis:joinattributestable', ...)`

这是唯一依赖 QGIS 的模块。它执行两项任务：
1. 表格到几何图形的转换（`fromPolylineXY`, `fromPointXY`）。
2. 使用 `QgsDistanceArea` (WGS84) 进行椭球体长度测量。

---

### 1.5 Shapefile 导出 — `gtfs_qgis_adapter.py`

**作用**：将 QGIS 图层以 ESRI Shapefile 格式写入磁盘。

**`shapefileWriter(layer, output_path, fileName)`**
- 调用 `QgsVectorFileWriter.writeAsVectorFormatV3(...)`
- 参数：`driver="ESRI Shapefile"`, `encoding="UTF-8"`, `CRS=EPSG:4326`

**产生文件**：每个图层生成 `.shp` + `.dbf` + `.shx` + `.prj`。
**导出图层**：共 4 个：`G_1_Trace_Sous_Ligne`, `G_2_Trace_Ligne`, `E_1_Nombre_Passage_AG`, `E_4_Nombre_Passage_Arc`。

**状态**：完全依赖 QGIS。需替换为 `geopandas.to_file()` 或导出为 GeoJSON。

---

## 2. 移植性矩阵

| 功能 | QGIS 依赖 | 可无缝移植 | Web 迁移方案 |
| :--- | :--- | :--- | :--- |
| **空间聚类 (AG/AP)** | ❌ 无 | ✅ 是 | 直接复用 |
| **Haversine / 距离矩阵** | ❌ 无 | ✅ 是 | 直接复用 |
| **直线路径生成** | ❌ 无 | ✅ 是 | 直接复用 |
| **shapes.txt 匹配** | ❌ 无 | ✅ 是 | 直接复用 |
| **矢量图层创建** | ✅ PyQGIS | ❌ 否 | 替换为 `geopandas` / GeoJSON |
| **椭球体长度测量** | ✅ QgsDistanceArea | ❌ 否 | 替换为现有的 `getDistHaversine()` |
| **Shapefile 导出** | ✅ QgsVectorFileWriter | ❌ 否 | 替换为 `geopandas.to_file()` 或 GeoJSON |
| **地理属性关联 (Join)** | ✅ processing.run(...) | ❌ 否 | 替换为已有的 `pd.merge()` |

**结论**：仅 `gtfs_qgis_adapter.py`（4 个函数）阻碍了迁移。其余所有代码已具备 Web 就绪条件。

---

## 3. Web 迁移计划 (基于 PRD)

GIS 迁移将遵循 PRD 的各阶段，并为每个阶段界定明确的范围：

### 阶段 0–1 (MVP — 无视觉 GIS)

非 QGIS 相关的 GIS 功能（聚类、Haversine、表格轨迹）将原封不动地在 Celery Worker 中使用。无需任何替换。

4 个矢量图层（G_1, G_2, E_1, E_4）在 MVP 阶段不生成 —— 基础数据（坐标 + 通过次数）存储在 PostgreSQL 中，并支持以 CSV 形式下载。

**[Celery Worker 中调用的模块]**：
- `gtfs_spatial.ag_ap_generate_reshape()` —— **保持不变**
- `gtfs_generator.itiarc_generate()` —— **保持不变** (用于直线距离计算)
- `gtfs_export.trace_sl_vol_oiseau()` —— **保持不变** (用于点序列生成)
- `gtfs_qgis_adapter.*` —— **MVP 阶段不调用**

---

### 阶段 2 (V2 — 交互式地图)

在此阶段，`gtfs_qgis_adapter.py` 将被替换。
**原则**：几何数据在服务器端构建为 GeoJSON，并在浏览器端通过 MapLibre GL JS 渲染。

**函数替换映射**：

| 旧版 (QGIS) | 新版 (Web) | 依赖库 | 输出格式 |
| :--- | :--- | :--- | :--- |
| `create_qgsLines(df_points)` | 通过 `groupby` 子线路创建带 LineString 的 `geopandas.GeoDataFrame` | `geopandas` + `shapely.geometry.LineString` | GeoJSON |
| `aggregate_polylines_by_category()` | `gdf.dissolve(by='id_ligne_num')` | `geopandas` | GeoJSON |
| `Qgs_PassageAG(df)` | 带 Point 的 `geopandas.GeoDataFrame` + 通过次数列 | `geopandas` + `shapely.geometry.Point` | GeoJSON |
| `Qgs_PassageArc(df)` | 带 A→B LineString 的 `geopandas.GeoDataFrame` + 通过次数列 | `geopandas` + `shapely.geometry.LineString` | GeoJSON |
| `shapefileWriter(layer)` | `gdf.to_file('output.geojson', driver='GeoJSON')` | `geopandas` | GeoJSON / (可选) Shapefile |
| `QgsDistanceArea.measureLength()` | 现有的 `gtfs_utils.py` 中的 `getDistHaversine()` | 内部实现 | 米 (float) |
| `processing.run('qgis:joinattributestable')` | `pd.merge(gdf, passages_df, on='id_ag_num')` | `pandas` | — |

**新模块**：`gtfs_geo_adapter.py` (取代 `gtfs_qgis_adapter.py`)
- `build_geojson_lines(df_points)`: 生成线路 GeoJSON
- `build_geojson_points(df_ag)`: 生成点 GeoJSON
- `build_geojson_arcs(df_arc)`: 生成弧 GeoJSON
- `export_geojson(gdf, path)`: 导出 `.geojson` 文件

**存储与坐标系**：
- **存储**：GeoJSON 写入存储对象（S3/MinIO），通过 REST API 提供给 MapLibre。
- **坐标系**：保持 EPSG:4326 (WGS84，GTFS 原生坐标系)。

---

### V2 图层及其数据源

| 图层 | 来源函数 | 数据内容 | MapLibre 样式 |
| :--- | :--- | :--- | :--- |
| **G_1 子线路** | `trace_sl_vol_oiseau()` 或 `corr_sl_shape()` → `build_geojson_lines()` | 排序后的点序列 | 按 `id_ligne_num` 着色的线条 |
| **G_2 聚合线路** | `gdf.dissolve('id_ligne_num')` | 合并后的子线路 | 较粗的线条 |
| **E_1 站点通过次数** | `nb_passage_ag()` → `build_geojson_points()` | (经度, 纬度, 通过次数) | 与通过次数成比例的圆圈 |
| **E_4 弧通过次数** | `passage_arc()` → `build_geojson_arcs()` | (起点, 终点, 通过次数) | 与通过次数成比例的线宽 |

---

### 阶段 3+ (API、多国支持、高级参数)

GIS 功能基本无需变动 —— 聚类和距离函数可以通过 V5 界面接收新参数（如：可配置的 100m 阈值，自定义椭球体），而无需更改架构。

---

## 4. 保持不变的部分

空间聚类 (`scipy`) 和 Haversine 距离计算 (`numpy`) 独立于任何 GIS 库。它们将坐标视为数字而非几何图形进行处理。在 Web 迁移过程中，它们将保留在 `gtfs_spatial.py` 和 `gtfs_utils.py` 中，无需修改。