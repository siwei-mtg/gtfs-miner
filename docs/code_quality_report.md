# 代码质量报告 — gtfs_core

> 范围：`backend/app/services/gtfs_core/`
> 日期：2026-04-06
> 评审：Claude Code（人工静态分析）

---

## 1. 总体评分

**综合评分：6.5 / 10**

顶层架构设计思路正确（Protocol + 依赖注入 + 分层管道），但执行层积累了明显的技术债，主要集中在可观测性、可测试性和命名安全三个方向。

| 维度 | 分数 | 说明 |
|------|------|------|
| 类型注解 | 7.5 | 基础良好；多个函数缺少返回值类型 |
| 错误处理 | 5.5 | 静默 fallback、无 logging、无业务异常类 |
| 耦合度 | 7.0 | Protocol 设计好；pandas 列名硬编码散落各处 |
| 内聚性 | 7.0 | 模块分工清晰；`gtfs_generator.py` 混杂三种职责 |
| 可测试性 | 5.0 | 15 个生成函数零单元测试 |
| 命名 | 8.0 | 领域术语一致；缩写无常量定义 |
| 文档注释 | 6.5 | 模块级 docstring 尚可；函数级严重缺失 |
| SOLID | 7.0 | OCP/DIP/LSP 优秀；generator 层违反 SRP |
| 圈复杂度 | 6.0 | 两个函数圈复杂度过高 |
| 反模式 | 5.5 | `inplace=True` 滥用、魔法数字、无入参校验 |

---

## 2. 完整问题清单

### 2.1 错误处理与可观测性

#### [EH-01] — P0 — 异常被吞没，无任何日志
- **文件**：`gtfs_norm.py`（`calendar` merge 的 try/except 块）
- **现象**：日历合并失败时，代码静默地将 `calendar = None`，生产环境无法诊断。
- **问题代码**：
  ```python
  try:
      ...  # calendar merge
  except Exception:
      calendar = None   # 无日志，无任何痕迹
  ```
- **修复方案**：
  ```python
  except Exception as exc:
      logger.warning("Calendar merge failed, continuing without calendar: %s", exc)
      calendar = None
  ```

#### [EH-02] — P0 — 关键路径上的静默 fallback
- **文件**：`gtfs_spatial.py`、`gtfs_utils.py`、`pipeline.py`
- **现象**：默认返回值（`0`、`np.nan`、`None`）无任何日志记录，数据损坏无法被发现。
- **修复方案**：在每个模块引入 `logging.getLogger(__name__)`，对所有非平凡 fallback 记录 `WARNING` 级别日志。

#### [EH-03] — P1 — 无入参列校验
- **文件**：`gtfs_export.py`、`gtfs_generator.py`
- **现象**：`MEF_ligne`、`MEF_course`、`course_generate` 等函数假定特定列存在，列缺失时抛出不含业务上下文的 `KeyError`。
- **修复方案**：
  ```python
  def _require_columns(df: pd.DataFrame, cols: list[str], context: str) -> None:
      missing = set(cols) - set(df.columns)
      if missing:
          raise ValueError(f"[{context}] 缺少列：{missing}")
  ```

---

### 2.2 命名与常量

#### [CN-01] — P0 — 业务逻辑中硬编码魔法数字
- **文件**：`gtfs_spatial.py`、`gtfs_norm.py`（另见 CLAUDE.md §硬编码常量）
- **问题代码**：
  ```python
  k = max(1, round(len(coor) / 500))   # 500：K-Means 分块大小
  eps = 100 / 6371000                   # 100 m：DBSCAN epsilon
  if len(stops) > 5000:                 # 5000：大数据集切换阈值
  ```
- **修复方案**：新建 `gtfs_core/constants.py`，将 CLAUDE.md 中所有常量集中管理：
  ```python
  CLUSTERING_CHUNK_SIZE: int = 500       # 每个 K-Means 分组的站点数
  DBSCAN_EPSILON_METERS: float = 100.0   # 站点合并距离阈值（米）
  BIG_VOLUME_THRESHOLD: int = 5000       # 超过此值切换至 K-Means
  KMEANS_CHUNK_DIVISOR: int = 500        # k = len(stops) / this
  MISSING_DIRECTION_ID: int = 999
  MISSING_ROUTE_TYPE: int = 3            # 回退值 = 公共汽车
  ENCODING_SAMPLE_BYTES: int = 10_000
  ```

#### [CN-02] — P0 — 时段字符串硬编码，无常量定义
- **文件**：`gtfs_generator.py`（约第 278–307 行）
- **现象**：`'FM'`、`'HPM'`、`'HC'`、`'HPS'`、`'FS'` 散落在频率计算逻辑中，无集中定义。
- **修复方案**：
  ```python
  class Period:
      EARLY_MORNING = 'FM'   # 早班低谷
      PEAK_MORNING  = 'HPM'  # 早高峰
      OFF_PEAK      = 'HC'   # 平峰
      PEAK_EVENING  = 'HPS'  # 晚高峰
      LATE_EVENING  = 'FS'   # 晚班低谷

  ALL_PERIODS = [Period.EARLY_MORNING, Period.PEAK_MORNING, Period.OFF_PEAK,
                 Period.PEAK_EVENING, Period.LATE_EVENING]
  ```

#### [CN-03] — P2 — 缩写无文档说明
- **文件**：全局（`TH`、`crs_tj`、`AP`、`AG`、`nb_crs`、`iti_arc`、`EPM/HPS/HC`……）
- **现象**：新贡献者可读性差，需要大量阅读才能理解含义。
- **修复方案**：在模块头部或新建 `docs/glossaire.md` 中添加术语表；新开发中优先使用 `courses_by_day_type` 而非 `crs_tj`。

---

### 2.3 单一职责原则（SRP）

#### [SR-01] — P1 — `gtfs_generator.py` 承担三种职责
- **文件**：`gtfs_generator.py`（约 500 行，15 个函数）
- **问题**：该文件混杂了：
  1. GTFS 实体生成（`course_generate`、`sl_generate`、`itineraire_generate`、`itiarc_generate`）
  2. 运营指标计算（`caract_par_sl`、`nb_passage_ag`、`nb_course_ligne`、`passage_arc`）
  3. 公里数计算（`kcc_course_sl`、`kcc_course_ligne`）
- **建议拆分**：
  ```
  gtfs_generator_core.py    # 纯 GTFS 实体生成
  gtfs_metrics.py           # 运营指标（频率、通过次数）
  gtfs_distances.py         # 公里数计算
  ```

#### [SR-02] — P2 — `caract_par_sl` 混合时段分配与频率计算
- **文件**：`gtfs_generator.py`（约第 250–332 行，80 行，10+ 分支）
- **修复方案**：将 `_assign_period(h_dep: pd.Series) -> pd.Series` 提取为独立纯函数，单独测试。

#### [SR-03] — P2 — `service_date_generate` 日历逻辑过于密集
- **文件**：`gtfs_generator.py`（约第 64–151 行，88 行）
- **修复方案**：提取 `_is_calendar_all_zero(calendar: pd.DataFrame) -> bool` 和 `_apply_exceptions(dates, exceptions) -> pd.Series`。

---

### 2.4 可测试性

#### [TS-01] — P1 — `gtfs_generator.py` 零单元测试
- **文件**：`backend/tests/`（缺失：`test_gtfs_generator.py`）
- **15 个未覆盖函数**：`course_generate`、`sl_generate`、`itineraire_generate`、`itiarc_generate`、`service_date_generate`、`ag_ap_generate`、`caract_par_sl`、`nb_passage_ag`、`nb_course_ligne`、`kcc_course_sl`、`kcc_course_ligne`、`passage_arc`、`corr_sl_shape`、`ag_cours_generate`、`itineraire_arc_generate`
- **修复方案**：新建 `test_gtfs_generator.py`，每个函数至少一个测试，使用内存构造的最小 DataFrame。

#### [TS-02] — P1 — `gtfs_export.py` 零单元测试
- **文件**：`backend/tests/`（缺失：`test_gtfs_export.py`）
- **7 个未覆盖函数**：`MEF_ligne`、`MEF_course`、`MEF_iti`、`MEF_iti_arc`、`MEF_ag`、`MEF_ap`、`export_all`
- **修复方案**：用最小 fixture 测试输出结构与列名。

#### [TS-03] — P1 — 聚类策略未做单元测试
- **文件**：`gtfs_spatial.py`（策略类：`HierarchicalClustering`、`KMeansHierarchical`、`DBSCANClustering`）
- **修复方案**：用合成坐标数据（< 20 个站点）对每种策略独立测试。

#### [TS-04] — P1 — 手工测试脚本不符合 pytest 规范
- **文件**：`backend/tests/test_gtfs_norm.py`、`backend/tests/test_gtfs_pipeline.py`
- **现象**：这些脚本生成 Markdown 报告而非 pytest 断言。`pytest` 执行它们但不验证任何内容。
- **修复方案**：将报告生成替换为针对关键列和行数的 `assert` 断言。

#### [TS-05] — P2 — 缺少参数化测试
- **文件**：整个 `tests/` 目录
- **现象**：每个边界场景（空 DataFrame、单行、编码异常）需要单独一个测试，而非使用 `@pytest.mark.parametrize`。
- **修复方案**：在新测试模块中用 `@pytest.mark.parametrize` 合并边界用例。

---

### 2.5 pandas 反模式

#### [AP-01] — P1 — `inplace=True` 滥用
- **文件**：`gtfs_norm.py`、`gtfs_generator.py`（15+ 处）
- **现象**：阻止链式调用，无中间值可检查，潜在触发 `SettingWithCopyWarning`。
- **问题代码**：
  ```python
  stops.drop(columns=['geometry'], inplace=True)
  trips.rename(columns={...}, inplace=True)
  ```
- **修复方案**：
  ```python
  stops = stops.drop(columns=['geometry'])
  trips = trips.rename(columns={...})
  ```

#### [AP-02] — P1 — 手动循环补列，应使用 `reindex`
- **文件**：`gtfs_generator.py`（约第 300–307 行）
- **问题代码**：
  ```python
  for p in ['FM', 'HPM', 'HC', 'HPS', 'FS']:
      if p not in headway_pv.columns:
          headway_pv[p] = 0
  ```
- **修复方案**：
  ```python
  headway_pv = headway_pv.reindex(columns=ALL_PERIODS, fill_value=0)
  ```

#### [AP-03] — P2 — 在大 DataFrame 上使用 `iterrows()`
- **文件**：`gtfs_spatial.py`（QGIS 适配器，坐标遍历）
- **现象**：`iterrows()` 比 numpy/pandas 向量化操作慢 10–100 倍。
- **修复方案**：替换为 `df[['lon', 'lat']].to_numpy()` + 矩阵运算。

---

### 2.6 类型注解

#### [TA-01] — P2 — `MEF_*` 函数缺少返回值类型
- **文件**：`gtfs_export.py`
- **函数**：`MEF_ligne`、`MEF_course`、`MEF_iti`、`MEF_iti_arc`、`MEF_ag`、`MEF_ap`——均缺少 `-> pd.DataFrame`
- **修复方案**：在每个函数签名上补充返回值类型注解。

#### [TA-02] — P2 — `gtfs_utils.py` 中缺少返回值类型
- **文件**：`gtfs_utils.py`
- **函数**：`distmatrice`、`heure_from_xsltime_vec`、`str_time_hms`
- **修复方案**：分别标注 `-> np.ndarray`、`-> pd.Series`、`-> str`。

---

### 2.7 文档注释

#### [DC-01] — P2 — 生成函数缺少 Args/Returns 说明
- **文件**：`gtfs_generator.py`、`gtfs_export.py`
- **现象**：docstring 有时描述 Input/Output Schema（已较好），但不说明参数含义和约束条件。
- **修复方案**：统一采用 Google Docstring 格式：
  ```python
  def course_generate(trips: pd.DataFrame, stops: pd.DataFrame) -> pd.DataFrame:
      """生成标准化班次表。

      Args:
          trips: 已丰富的 GTFS trips DataFrame（必需列：trip_id, route_id, …）
          stops: 已标准化的 stops DataFrame（必需列：stop_id, id_ag, …）

      Returns:
          班次 DataFrame，含列 [id_course_num, id_ligne_num, …]

      Raises:
          ValueError: 当必需列缺失时。
      """
  ```

#### [DC-02] — P2 — 缺少缩写术语表
- 参见 [CN-03]。

---

### 2.8 接口隔离原则（ISP）

#### [IS-01] — P2 — `MEF_*` 函数族缺少 `Formatter` Protocol
- **文件**：`gtfs_export.py`
- **现象**：6 个 `MEF_*` 函数均为 `(df1, df2, …) -> pd.DataFrame` 签名，但没有共同的形式契约，难以扩展和测试。
- **修复方案**：
  ```python
  from typing import Protocol

  class GTFSFormatter(Protocol):
      def format(self, *dfs: pd.DataFrame) -> pd.DataFrame: ...
  ```

---

## 3. 优先级汇总

### P0 — 严重（上线前必须修复）

| 编号 | 问题 | 文件 | 预估工时 |
|------|------|------|----------|
| EH-01 | 异常被吞没，无日志 | `gtfs_norm.py` | 30 分钟 |
| EH-02 | 关键路径静默 fallback | `gtfs_spatial.py`、`gtfs_utils.py`、`pipeline.py` | 2 小时 |
| CN-01 | 魔法数字硬编码 | `gtfs_spatial.py`、`gtfs_norm.py` | 1 小时 |
| CN-02 | 时段字符串无常量 | `gtfs_generator.py` | 1 小时 |

**P0 合计估算：约 4.5 小时**

---

### P1 — 重要（下一个 sprint）

| 编号 | 问题 | 文件 | 预估工时 |
|------|------|------|----------|
| EH-03 | 无入参列校验 | `gtfs_export.py`、`gtfs_generator.py` | 2 小时 |
| SR-01 | `gtfs_generator.py` 违反 SRP | `gtfs_generator.py` | 3 小时 |
| TS-01 | `gtfs_generator.py` 零单元测试 | `tests/` | 4 小时 |
| TS-02 | `gtfs_export.py` 零单元测试 | `tests/` | 2 小时 |
| TS-03 | 聚类策略未测试 | `tests/` | 1 小时 |
| TS-04 | 手工测试脚本不符合 pytest | `test_gtfs_norm.py`、`test_gtfs_pipeline.py` | 2 小时 |
| AP-01 | `inplace=True` 滥用 | `gtfs_norm.py`、`gtfs_generator.py` | 1.5 小时 |
| AP-02 | 手动循环补列应改用 `reindex` | `gtfs_generator.py` | 30 分钟 |

**P1 合计估算：约 16 小时**

---

### P2 — 改进（待办积压）

| 编号 | 问题 | 文件 | 预估工时 |
|------|------|------|----------|
| SR-02 | `caract_par_sl` 复杂度过高 | `gtfs_generator.py` | 1 小时 |
| SR-03 | `service_date_generate` 逻辑过密 | `gtfs_generator.py` | 1 小时 |
| TS-05 | 缺少参数化测试 | `tests/` | 1 小时 |
| AP-03 | `iterrows()` 性能问题 | `gtfs_spatial.py` | 1 小时 |
| TA-01 | `MEF_*` 缺返回值类型 | `gtfs_export.py` | 30 分钟 |
| TA-02 | utils 缺返回值类型 | `gtfs_utils.py` | 20 分钟 |
| DC-01 | 函数 docstring 不完整 | `gtfs_generator.py`、`gtfs_export.py` | 2 小时 |
| DC-02 | 缺少缩写术语表 | 新建文件 | 1 小时 |
| IS-01 | 缺少 `Formatter` Protocol | `gtfs_export.py` | 1 小时 |
| CN-03 | 缩写无文档说明 | 全局 | 1 小时 |

**P2 合计估算：约 9.5 小时**

---

## 4. 受影响文件索引

```
P0
├── backend/app/services/gtfs_core/gtfs_norm.py       [EH-01, CN-01]
├── backend/app/services/gtfs_core/gtfs_spatial.py    [EH-02, CN-01]
├── backend/app/services/gtfs_core/gtfs_utils.py      [EH-02]
├── backend/app/services/gtfs_core/pipeline.py        [EH-02]
└── backend/app/services/gtfs_core/gtfs_generator.py  [CN-02]
   + 新增：backend/app/services/gtfs_core/constants.py

P1
├── backend/app/services/gtfs_core/gtfs_generator.py  [SR-01, AP-01, AP-02, EH-03]
├── backend/app/services/gtfs_core/gtfs_export.py     [EH-03]
├── backend/tests/test_gtfs_norm.py                   [TS-04]
├── backend/tests/test_gtfs_pipeline.py               [TS-04]
│   + 新增：test_gtfs_generator.py、test_gtfs_export.py、test_gtfs_spatial.py

P2
├── backend/app/services/gtfs_core/gtfs_export.py     [TA-01, IS-01, DC-01]
├── backend/app/services/gtfs_core/gtfs_utils.py      [TA-02]
└── backend/app/services/gtfs_core/gtfs_generator.py  [SR-02, SR-03, DC-01, CN-03]
```

---

*本报告为 SOLID 分析的配套文件——另见 `docs/SOLID_analysis.md`。*
