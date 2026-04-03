# GTFS Miner 核心模块优化分析报告

> 分析日期：2026-04-03  
> 分析范围：`gtfs_utils.py`, `gtfs_norm.py`, `gtfs_spatial.py`, `gtfs_generator.py`, `gtfs_export.py`

---

## 1. gtfs_utils.py — 基础工具模块

### 1.1 `distmatrice()` — 距离矩阵计算 ⚠️ 高优先级

**现状**：使用 `np.meshgrid` 构建完整 N×N 矩阵后调用 `getDistHaversine`，再通过 `squareform` 转为 condensed form。

**问题**：
- 内存占用 O(N²)，5000 站点即需 ~200MB（float64），大数据集会 OOM
- 计算了完整方阵（含对角线和对称部分），实际只需上三角的 N*(N-1)/2 个值
- `getDistHaversine` 本身已支持向量化（numpy），但 meshgrid 方式产生了大量冗余计算

**优化方案**：
```python
# 方案 A：直接用 scipy.spatial.distance.pdist + 自定义 metric
from scipy.spatial.distance import pdist

def distmatrice(nparray: np.ndarray) -> np.ndarray:
    """直接返回 condensed distance vector，内存减半。"""
    def haversine_metric(u, v):
        return getDistHaversine(u[1], u[0], v[1], v[0])  # lat/lon
    return pdist(nparray, metric=haversine_metric)

# 方案 B（更快）：用 sklearn.metrics.pairwise.haversine_distances
# 直接基于 BallTree 优化，适合 >2000 站点场景
```

**预期收益**：内存降低 50%+，大数据集（>5000 站点）避免 OOM

---

### 1.2 `str_time_hms()` / `str_time_hms_hour()` — 时间转换 ⚠️ 中优先级

**现状**：逐行 Python 字符串 `split(':')`，在 `itineraire_generate` 中通过 `.apply()` 逐行调用。

**问题**：`stop_times` 通常有数十万到数百万行，`.apply()` 是纯 Python 循环，是整条流水线中最慢的环节之一。

**优化方案**：
```python
def vectorized_hms_to_dayfrac(series: pd.Series) -> pd.Series:
    """向量化 HH:MM:SS → 天数比例。"""
    parts = series.str.split(':', expand=True).astype(float)
    return parts[0] / 24 + parts[1] / 1440 + parts[2] / 86400

def vectorized_hms_hour(series: pd.Series) -> pd.Series:
    """向量化提取小时。"""
    return pd.to_numeric(series.str.split(':').str[0], errors='coerce').fillna(0).astype(int)
```

**预期收益**：10–50x 加速（视数据量），消除 `itineraire_generate` 的主要瓶颈

---

### 1.3 `encoding_guess()` — 编码检测 🔵 低优先级

**现状**：固定读取 10000 字节采样。

**建议**：对大文件（>1MB）可先读 10KB 快速判断，若 confidence < 0.8 再扩大采样到 100KB。小文件无需优化。

---

## 2. gtfs_norm.py — 标准化模块

### 2.1 Schema 填充模式 ⚠️ 中优先级

**现状**：每个 `*_norm()` 函数都先创建空 DataFrame（含全部列），再 `pd.concat` 合并原始数据。

**问题**：
- `pd.concat` 对空 DF 和实际数据做 union 操作，列数多时开销不小
- 目的仅为"补全缺失列"，但 concat 会触发不必要的内存拷贝

**优化方案**：
```python
def ensure_columns(df: pd.DataFrame, required_cols: List[str]) -> pd.DataFrame:
    """仅添加缺失列，避免 concat 拷贝。"""
    for col in required_cols:
        if col not in df.columns:
            df[col] = np.nan
    return df
```

**预期收益**：减少每次规范化的内存拷贝，大数据集（IDFM 级）节省 ~10-20% 时间

---

### 2.2 `stops_norm()` 重复调用 `norm_upper_str` 🔵 低优先级

**现状**：第 52 行和第 59 行对 `stops.stop_name` 连续调用了两次 `norm_upper_str`。

**修复**：删除第 52 行的重复调用，纯粹是代码冗余。

---

### 2.3 `rawgtfs_from_zip()` — 编码处理 🔵 低优先级

**现状**：先尝试 UTF-8，捕获异常后 fallback 到 latin-1。

**建议**：可结合 `encoding_guess()` 一次性判断编码，避免异常驱动的 try/except 模式（异常的性能开销在批量文件时累积）。

---

### 2.4 `gtfs_normalize()` — 流程编排 🟡 架构建议

**现状**：所有规范化步骤串行执行。

**建议**：`agency_norm`, `routes_norm`, `stops_norm`, `trips_norm`, `stop_times_norm` 之间无依赖关系（仅在最后 merge 阶段才需要交叉引用），可以并行执行：
```python
from concurrent.futures import ThreadPoolExecutor
# agency / routes / stops / trips / stop_times 五个规范化可并行
```

**预期收益**：在多核机器上，规范化阶段耗时约降低 40-60%

---

## 3. gtfs_spatial.py — 空间聚类模块

### 3.1 `ag_ap_generate_hcluster()` — 层次聚类 🔴 高优先级

**现状**：对全量站点计算完整距离矩阵 → `linkage(method='complete')` → `cut_tree`。

**问题**：
- 距离矩阵 O(N²) 内存 + O(N² log N) 时间（complete linkage）
- 5000 站点时距离矩阵约 100MB，10000 站点约 400MB
- 这是整条处理链中最可能 OOM 的环节

**优化方案**：

| 方案 | 适用场景 | 说明 |
|------|---------|------|
| **A. DBSCAN** | 通用替代 | `sklearn.cluster.DBSCAN(eps=100m, metric='haversine')`，O(N log N)，不需完整距离矩阵 |
| **B. BallTree 预筛** | 保留层次聚类 | 先用 BallTree 找出 100m 邻域，构建稀疏距离矩阵，再做层次聚类 |
| **C. 分块聚类** | >5000 站点 | 先 K-Means 粗分组，每组内做层次聚类（已有 `ag_ap_generate_bigvolume` 雏形） |

**推荐方案 A**（DBSCAN）：
```python
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import haversine_distances

def ag_ap_generate_hcluster(raw_stops: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    AP = raw_stops.loc[raw_stops.location_type == 0].reset_index(drop=True)
    coords_rad = np.radians(AP[['stop_lat', 'stop_lon']].to_numpy())
    # eps = 100m / Earth_radius
    labels = DBSCAN(eps=100/6371000, min_samples=1, metric='haversine').fit_predict(coords_rad)
    AP['id_ag'] = (labels + 1).astype(str)
    # ... 后续与现有逻辑相同
```

**预期收益**：时间复杂度从 O(N²logN) 降至 O(NlogN)；内存从 O(N²) 降至 O(N)

---

### 3.2 `ag_ap_generate_reshape()` — 分支选择 ⚠️ 中优先级

**现状**：判断是否需要聚类的逻辑仅基于 `location_type` 种类数和 `parent_station` 是否为空。

**问题**：
- 未集成大数据量分支（`TODO` 标注的 bigvolume K-Means 逻辑）
- 当 `parent_station` 部分缺失（如 50% 的站点有 parent，50% 没有）时，当前逻辑会全部走聚类分支，丢弃已有的 parent 信息

**建议**：增加混合模式——有 parent 的站点保留原映射，无 parent 的站点走聚类补全。

---

## 4. gtfs_generator.py — 业务生成模块

### 4.1 `itineraire_generate()` — 行程生成 🔴 高优先级

**现状**：
```python
st['TH'] = st['arrival_time'].apply(str_time_hms_hour)       # 逐行 Python
st['arrival_time'] = st['arrival_time'].apply(str_time_hms)   # 逐行 Python
st['departure_time'] = st['departure_time'].apply(str_time_hms)  # 逐行 Python
```

**问题**：三次 `.apply()` 遍历 stop_times（通常 50 万–500 万行），是全流程最慢的单步操作。

**优化方案**：使用上述 §1.2 的向量化版本，预计加速 10–50x。

---

### 4.2 `itiarc_generate()` — Arc 生成 ⚠️ 中优先级

**现状**：
```python
arc_dist['DIST_Vol_Oiseau'] = np.around(np.vectorize(getDistHaversine)(...), 0)
```

**问题**：`np.vectorize` 并非真正向量化——它只是 Python 循环的语法糖，性能与 `.apply()` 相当。

**优化方案**：`getDistHaversine` 已经支持 numpy 数组输入（使用 `np.sin/cos/arctan2`），直接传 Series 即可：
```python
arc_dist['DIST_Vol_Oiseau'] = np.around(
    getDistHaversine(
        arc_dist.stop_lat_src.values, arc_dist.stop_lon_src.values,
        arc_dist.stop_lat_dst.values, arc_dist.stop_lon_dst.values
    ), 0)
```

**预期收益**：5–20x 加速，因为 `getDistHaversine` 内部已全部使用 numpy 运算

---

### 4.3 `course_generate()` — 多级列展平 🔵 低优先级

**现状**：`groupby().agg()` 产生 MultiIndex columns，用字符串拼接展平。

**建议**：使用 `NamedAgg` 直接命名，避免事后 rename：
```python
course = itineraire.groupby([...]).agg(
    heure_depart=('arrival_time', 'min'),
    heure_arrive=('departure_time', 'max'),
    id_ap_num_debut=('id_ap_num', 'first'),
    id_ap_num_terminus=('id_ap_num', 'last'),
    ...
)
```

---

### 4.4 `service_date_generate()` — TODO 未完成 🟡 功能缺口

**现状**：当 `calendar.txt` 存在时，返回空 DataFrame（TODO 标注）。

**影响**：部分 GTFS 数据集仅提供 `calendar.txt`（无 `calendar_dates.txt`），此时服务日期为空，后续所有基于日期的统计（通过次数、KCC 等）均失效。

**建议**：优先补全此逻辑，否则会导致部分数据集无法处理。

---

### 4.5 `caract_par_sl()` — TODO 未完成 🟡 功能缺口

**现状**：Headway (HPM/HPS) 计算逻辑为空壳。

**影响**：F 系列输出表（线路/子线路指标）无法生成发车间隔数据。

---

## 5. gtfs_export.py — 导出模块

### 5.1 `heure_from_xsltime` 的重复 `.apply()` ⚠️ 中优先级

**现状**：`MEF_course`, `MEF_iti`, `MEF_iti_arc` 三个函数各自对时间列调用 `.apply(heure_from_xsltime)`。

**优化方案**：向量化版本：
```python
def vectorized_xsltime_to_hhmm(series: pd.Series) -> pd.Series:
    """向量化 Excel 时间比例 → HH:MM。"""
    total_hours = series.fillna(0) * 24
    hours = total_hours.astype(int)
    minutes = ((total_hours - hours) * 60).astype(int)
    return hours.astype(str).str.zfill(2) + ':' + minutes.astype(str).str.zfill(2)
```

**预期收益**：每个 MEF 函数加速 5–10x

---

### 5.2 MEF 函数的重复模式 🔵 低优先级

**现状**：`MEF_iti` 和 `MEF_iti_arc` 有几乎相同的 rename + apply + merge 模式。

**建议**：可提取公共的时间格式化步骤，但优先级不高，不影响性能。

---

## 优化优先级总结

| 优先级 | 模块 | 问题 | 预期收益 |
|--------|------|------|---------|
| 🔴 P0 | `gtfs_spatial` | 层次聚类 O(N²) 距离矩阵 | 避免 OOM，10x+ 加速 |
| 🔴 P0 | `gtfs_generator` | `itineraire_generate` 三次 `.apply()` | 10–50x 加速 |
| ⚠️ P1 | `gtfs_utils` | `distmatrice` meshgrid 冗余计算 | 内存降 50%+ |
| ⚠️ P1 | `gtfs_generator` | `np.vectorize` 伪向量化 | 5–20x 加速 |
| ⚠️ P1 | `gtfs_export` | `heure_from_xsltime` 逐行 apply | 5–10x 加速 |
| ⚠️ P1 | `gtfs_norm` | concat 填充模式低效 | 10–20% 时间节省 |
| 🟡 P2 | `gtfs_generator` | `service_date_generate` 未完成 | 功能完整性 |
| 🟡 P2 | `gtfs_generator` | `caract_par_sl` Headway 空壳 | 功能完整性 |
| 🟡 P2 | `gtfs_norm` | 规范化步骤可并行 | 40–60% 加速 |
| 🔵 P3 | `gtfs_norm` | `norm_upper_str` 重复调用 | 代码质量 |
| 🔵 P3 | `gtfs_generator` | NamedAgg 替代列展平 | 代码可读性 |
| 🔵 P3 | `gtfs_spatial` | reshape 混合模式缺失 | 数据质量 |

---

## 大数据集（IDFM 级，>5 万站点）处理链瓶颈排序

```
1. gtfs_spatial.ag_ap_generate_hcluster   — OOM 风险 + O(N²logN)
2. gtfs_generator.itineraire_generate     — 数百万行逐行 apply
3. gtfs_utils.distmatrice                 — O(N²) 矩阵构建
4. gtfs_export.MEF_*                      — 重复的逐行时间格式化
5. gtfs_norm.stop_times_norm              — groupby.transform 在缺失值多时较慢
```

---

## 下一步建议

1. **立即修复**：`itiarc_generate` 中的 `np.vectorize` → 直接传数组（一行改动，收益大）
2. **短期优化**：将 `str_time_hms` / `heure_from_xsltime` 向量化（影响面最广）
3. **中期重构**：用 DBSCAN 替代层次聚类（解决大数据集 OOM）
4. **功能补全**：完成 `service_date_generate` 的 calendar.txt 逻辑
