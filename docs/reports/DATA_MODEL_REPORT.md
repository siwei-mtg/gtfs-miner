# GTFS Miner — 数据模型必要性分析报告

> 日期：2026-04-03
> 分支：`feat/web-app-scaffold`

---

## 1. 现状分析

### 1.1 数据流转方式

当前所有核心模块间的数据传递均使用原始 `pd.DataFrame`，列名通过字符串隐式约定：

```
gtfs_norm.*_norm()          → Dict[str, pd.DataFrame]
gtfs_spatial.ag_ap_generate → (AP: DataFrame, AG: DataFrame)
gtfs_generator.*            → DataFrame
gtfs_export.MEF_*           → DataFrame
```

### 1.2 已识别的风险点

| 风险 | 说明 | 示例 |
|------|------|------|
| **Schema 仅存在于 docstring** | 列名、类型、值域无运行时保障 | `id_ap_num` 拼成 `id_ap_no` 不会报错，只会在后续 merge 时产生空列 |
| **模块间隐式契约** | `itineraire_generate` 的输出列名必须与 `course_generate` 的输入完全一致，但无代码层面约束 | `stop_sequence` vs `ordre` 命名不一致需手动 rename |
| **类型漂移** | `id_ag_num` 在某些路径下可能为 float（因 NaN 污染），下游 merge 静默失败 | `AG.merge(AP, on='id_ag_num')` 类型不匹配时产生空结果 |
| **Web 迁移需 API 序列化** | FastAPI 天然要求 Pydantic model 定义请求/响应体 | 无模型则 API 层需大量临时 dict 构造 |

### 1.3 核心 DataFrame 契约清单

通过代码审查，提取出模块间流转的关键 DataFrame 结构：

| DataFrame | 来源模块 | 核心列 | 下游消费者 |
|-----------|---------|--------|-----------|
| **AP** | `gtfs_spatial` | `id_ap, id_ag, id_ap_num, id_ag_num, stop_name, stop_lat, stop_lon` | `gtfs_generator`, `gtfs_export` |
| **AG** | `gtfs_spatial` | `id_ag, id_ag_num, stop_name, stop_lat, stop_lon` | `gtfs_generator`, `gtfs_export` |
| **Itineraire** | `gtfs_generator` | `id_course_num, id_ligne_num, id_service_num, direction_id, stop_sequence, id_ap_num, id_ag_num, arrival_time, departure_time, TH, trip_headsign` | `course_generate`, `itiarc_generate`, `MEF_iti` |
| **Course** | `gtfs_generator` | `id_course_num, id_ligne_num, sous_ligne, id_service_num, direction_id, heure_depart, heure_arrive, id_ap_num_debut, id_ap_num_terminus, id_ag_num_debut, id_ag_num_terminus, nb_arrets` | `MEF_course`, `MEF_ligne`, `nb_course_ligne` |
| **Itineraire Arc** | `gtfs_generator` | `id_course_num, ordre_a, ordre_b, id_ag_num_a, id_ag_num_b, stop_lat_src, stop_lon_src, stop_lat_dst, stop_lon_dst, DIST_Vol_Oiseau` | `MEF_iti_arc`, `passage_arc` |
| **Service Dates** | `gtfs_generator` | `id_service_num, Date_GTFS, Type_Jour, Semaine, Mois, Annee` | `MEF_serdate`, `nb_passage_ag` |

---

## 2. 结论：需要数据模型，分两层实施

### 2.1 整体策略

```
┌─────────────────────────────────────────────────┐
│                   Web API 层                     │
│          Pydantic Model (请求/响应)              │
│       StopOut, CourseOut, ProcessingResult        │
├─────────────────────────────────────────────────┤
│                  核心计算层                       │
│         Pandera Schema (DataFrame 校验)          │
│     APSchema, AGSchema, ItineraireSchema, ...    │
├─────────────────────────────────────────────────┤
│              pandas DataFrame                    │
│          （现有计算逻辑保持不变）                  │
└─────────────────────────────────────────────────┘
```

**设计原则**：不侵入现有 pandas 计算链，在边界处加校验。

### 2.2 为什么不用 dataclass / TypedDict 包装 DataFrame？

核心计算全部是 pandas 的 `groupby` / `merge` / `pivot` 链式操作。将 DataFrame 包装进 dataclass 会导致：

- `df.merge()` 变成 `obj.data.merge()`，增加调用摩擦
- 每次 merge/groupby 后需手动重新包装
- pandas 原生 API 的灵活性被人为限制

**Pandera** 是正确的工具选型——它在 DataFrame 之上贴校验，而非替代 DataFrame。

---

## 3. 第 1 层：Pandera Schema（核心计算层）

### 3.1 技术选型

- **库**：[pandera](https://pandera.readthedocs.io/) >= 0.18
- **作用**：在模块入口/出口对 DataFrame 做列名、类型、值域校验
- **侵入度**：每个函数仅增加 1 行 `.validate()` 调用

### 3.2 Schema 定义示例

```python
# gtfs_schemas.py
"""
GTFS Miner DataFrame Schema 定义模块

功能：
定义核心 DataFrame 的列名、类型和值域约束，
用于模块边界的运行时校验。
"""

import pandera as pa
from pandera import Column, DataFrameSchema, Check

# ---- 空间模块输出 (gtfs_spatial) ----

APSchema = DataFrameSchema({
    "id_ap":      Column(str,   nullable=False),
    "id_ag":      Column(str,   nullable=False),
    "id_ap_num":  Column(int,   Check.ge(100000), nullable=False),
    "id_ag_num":  Column(int,   Check.ge(10000),  nullable=False),
    "stop_name":  Column(str),
    "stop_lat":   Column(float, Check.in_range(-90, 90)),
    "stop_lon":   Column(float, Check.in_range(-180, 180)),
}, coerce=True)

AGSchema = DataFrameSchema({
    "id_ag":      Column(str,   nullable=False),
    "id_ag_num":  Column(int,   Check.ge(10000), nullable=False),
    "stop_name":  Column(str),
    "stop_lat":   Column(float, Check.in_range(-90, 90)),
    "stop_lon":   Column(float, Check.in_range(-180, 180)),
}, coerce=True)

# ---- 业务生成模块输出 (gtfs_generator) ----

ItineraireSchema = DataFrameSchema({
    "id_course_num":  Column(int,   nullable=False),
    "id_ligne_num":   Column(int,   nullable=False),
    "id_service_num": Column(int,   nullable=False),
    "direction_id":   Column(int),
    "stop_sequence":  Column(int,   Check.ge(1)),
    "id_ap_num":      Column(int,   nullable=False),
    "id_ag_num":      Column(int,   nullable=False),
    "arrival_time":   Column(float),
    "departure_time": Column(float),
    "TH":             Column(int),
    "trip_headsign":  Column(str),
}, coerce=True)

CourseSchema = DataFrameSchema({
    "id_course_num":      Column(int, nullable=False),
    "id_ligne_num":       Column(int, nullable=False),
    "sous_ligne":         Column(str, nullable=False),
    "id_service_num":     Column(int),
    "direction_id":       Column(int),
    "heure_depart":       Column(float),
    "heure_arrive":       Column(float),
    "id_ap_num_debut":    Column(int),
    "id_ap_num_terminus": Column(int),
    "id_ag_num_debut":    Column(int),
    "id_ag_num_terminus": Column(int),
    "nb_arrets":          Column(int, Check.ge(1)),
}, coerce=True)

ItiArcSchema = DataFrameSchema({
    "id_course_num":   Column(int, nullable=False),
    "ordre_a":         Column(int),
    "ordre_b":         Column(int),
    "id_ag_num_a":     Column(int, nullable=False),
    "id_ag_num_b":     Column(int, nullable=False),
    "DIST_Vol_Oiseau": Column(float, Check.ge(0)),
}, coerce=True)

ServiceDateSchema = DataFrameSchema({
    "id_service_num": Column(int, nullable=False),
    "Date_GTFS":      Column(str, nullable=False),
    "Type_Jour":      Column(str),
    "Semaine":        Column(int),
    "Mois":           Column(int, Check.in_range(1, 12)),
    "Annee":          Column(int),
}, coerce=True)
```

### 3.3 在现有模块中的使用方式

```python
# gtfs_spatial.py — 仅在函数出口增加 1 行
from gtfs_schemas import APSchema, AGSchema

def ag_ap_generate_hcluster(raw_stops: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    # ... 现有逻辑完全不变 ...
    AP = APSchema.validate(AP)   # ← 新增
    AG = AGSchema.validate(AG)   # ← 新增
    return AP, AG
```

```python
# gtfs_generator.py — 同理
from gtfs_schemas import ItineraireSchema, CourseSchema

def itineraire_generate(...) -> pd.DataFrame:
    # ... 现有逻辑 ...
    return ItineraireSchema.validate(itineraire)  # ← 新增

def course_generate(itineraire: pd.DataFrame) -> pd.DataFrame:
    # ... 现有逻辑 ...
    return CourseSchema.validate(course)           # ← 新增
```

### 3.4 单元测试中的应用

```python
# test_gtfs_core.py — 用 schema 替代手写列断言
from gtfs_schemas import APSchema

def test_ag_ap_generate_hcluster():
    AP, AG = ag_ap_generate_hcluster(sample_stops)
    APSchema.validate(AP)  # 替代: assert 'id_ap' in AP.columns, ...
```

---

## 4. 第 2 层：Pydantic Model（Web API 层）

### 4.1 技术选型

- **库**：pydantic >= 2.0（FastAPI 内置）
- **作用**：定义 API 请求体和响应体的序列化格式
- **时机**：Phase 0-1 Web 迁移时实施

### 4.2 Model 定义示例

```python
# api/models.py
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date

# ---- 响应模型 ----

class StopOut(BaseModel):
    """站点输出"""
    id_ap: str
    id_ag_num: int
    stop_name: str
    stop_lat: float = Field(ge=-90, le=90)
    stop_lon: float = Field(ge=-180, le=180)

class CourseOut(BaseModel):
    """班次输出"""
    id_course_num: int
    id_ligne_num: int
    sous_ligne: str
    heure_depart: str
    heure_arrive: str
    nb_arrets: int = Field(ge=1)

class LigneOut(BaseModel):
    """线路输出"""
    id_ligne_num: int
    route_short_name: Optional[str]
    route_long_name: Optional[str]
    origin: Optional[str]
    destination: Optional[str]

class ProcessingResult(BaseModel):
    """处理结果概览"""
    ag_count: int
    ap_count: int
    ligne_count: int
    course_count: int
    date_range: str
    cluster_method: str

# ---- 请求模型 ----

class ProcessingRequest(BaseModel):
    """处理任务请求"""
    project_name: str
    description: Optional[str] = None

# ---- DataFrame ↔ Pydantic 转换 ----

def df_to_model_list(df, model_class):
    """将 DataFrame 转为 Pydantic model 列表（用于 API 响应）"""
    return [model_class(**row) for row in df.to_dict(orient='records')]
```

### 4.3 在 FastAPI 端点中的使用

```python
# api/routes.py
from fastapi import APIRouter
from api.models import StopOut, ProcessingResult, df_to_model_list

router = APIRouter()

@router.get("/projects/{project_id}/stops", response_model=List[StopOut])
async def get_stops(project_id: int):
    ap_df = ...  # 从数据库/缓存获取
    return df_to_model_list(ap_df, StopOut)
```

---

## 5. 实施计划

| 阶段 | 任务 | 改动量 | 前置条件 |
|------|------|--------|---------|
| **Step 1** | 新建 `gtfs_schemas.py`，定义 6 个核心 Schema | 1 个新文件（~80 行） | `pip install pandera` |
| **Step 2** | 在 `gtfs_spatial` + `gtfs_generator` 输出端加 `.validate()` | 约 8 行改动 | Step 1 |
| **Step 3** | 单元测试中引入 Schema 断言 | 替换现有断言 | Step 1 |
| **Step 4** | Web 层开发时编写 `api/models.py` | 按需推进 | Phase 0-1 启动 |

### 优先级

```
Step 1 + 2（立即）→ Step 3（本迭代）→ Step 4（Web 迁移时）
```

---

## 6. 不纳入范围

| 方案 | 原因 |
|------|------|
| dataclass 包装 DataFrame | 与 pandas 链式操作冲突，增加调用摩擦 |
| TypedDict 标注 DataFrame 列 | 仅 IDE 提示，无运行时校验 |
| SQLAlchemy ORM model | 当前阶段无数据库交互，Phase 1 数据库设计时再引入 |
| 全量输入校验 | 优先校验输出（生产者保证契约），输入校验按需添加 |

---

## 7. 实施记录

| 实施日期 | 状态 | 备注 |
|----------|------|------|
| 2026-04-03 | 已完成 | Step 1 + 2 核心计算层 Pandera Schema 实施完毕 |

### 7.1 变更详情

1.  **依赖更新**：在 `backend/requirements.txt` 中添加 `pandera>=0.18`。
2.  **Schema 定义**：创建 `gtfs_schemas.py`，定义了 6 个核心 DataFrame Schema：
    -   `APSchema`: 包含 7 列，支持 `coerce=True`。
    -   `AGSchema`: 包含 5 列。
    -   `ItineraireSchema`: 包含 11 列。
    -   `CourseSchema`: 包含 14 列（新增 `trip_headsign` 和 `DIST_Vol_Oiseau` 的校验）。
    -   `ItiArcSchema`: 扩展至 15 列。
    -   `ServiceDateSchema`: 包含 6 列。
3.  **校验注入**：
    -   `gtfs_spatial.py`: 在 `ag_ap_generate_bigvolume`, `ag_ap_generate_hcluster`, `ag_ap_generate_asit` 的返回处添加校验。
    -   `gtfs_generator.py`: 在 `itineraire_generate`, `service_date_generate`, `course_generate`, `itiarc_generate` 的返回处添加校验。

### 7.2 技术考量点

-   **Nullable Integer (可空整型)**：所有 ID 和整型列改为使用 `pa.Int64`。这解决了部分脏数据（如 `stop_times` 引用了不存在的站点）导致的 `NaN` 匹配问题。使用 `pa.Int64` 既能允许 `NaN` 存在，又能防止列退化为 `float64`，维持了数据模型的整洁。
-   **Coerce (自动转换)**：所有 Schema 开启了 `coerce=True`，能自动处理类型转换。
-   **边界校验**：坚持仅在“生产者”端（函数出口）进行校验，下游“消费者”模块默认接收已满足 Schema 的数据，减少重复校验开销。


### 7.3 后续建议

-   **Step 3 (单元测试)**：建议在后续迭代中，将 `test_gtfs_core.py` 中的手写断言替换为 Schema 校验。
-   **Step 4 (API Models)**：在 Web API 路由开发时，参考此处的 Schema 定义编写对应的 Pydantic 模型。
