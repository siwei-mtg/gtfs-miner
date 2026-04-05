# SOLID 原则分析报告 — gtfs_core

**分析范围**：`backend/app/services/gtfs_core/`  
**分析日期**：2026-04-04  **最后更新**：2026-04-06（P5 已处理）

---

## 总结

| 原则 | 违反程度 | 主要位置 |
|------|---------|---------|
| **S — 单一职责** | 高 | `pipeline.main()`、`gtfs_norm` 模块边界模糊 |
| **O — 开闭** | 中 | `ag_ap_generate_reshape()`、`ligne_generate()` |
| **D — 依赖倒置** | 中 | `read_date()`/`read_validite()` 硬编码路径 |
| **L — 里氏替换** | 无 | 过程式代码，无继承体系 |
| **I — 接口隔离** | 轻微 | `gtfs_normalize()` 返回胖字典 |

---

## 问题清单

| 优先级 | 原则 | 问题 | 状态 |
|--------|------|------|------|
| P0 | D | `read_date()`/`read_validite()` 硬编码文件路径，阻碍 Supabase 迁移 | ✅ 已处理 |
| P1 | S | `pipeline.main()` 混合 argparse / 编排 / I/O / 日志 | ✅ 已处理 |
| P2 | S | `gtfs_norm.py` 混合规范化、文件 I/O、资源加载、Legacy 入口 | ✅ 已处理 |
| P3 | S | `rawgtfs_from_zip()` 编码检测内嵌，`encoding_guess()` 已存在却未复用 | ✅ 已处理 |
| P4 | O | `ag_ap_generate_reshape()` if/elif 硬编码三种聚类算法分支 | ✅ 已处理 |
| P5 | I | `gtfs_normalize()` 返回 13 键胖字典，下游只需其中少数键 | ✅ 已处理 |
| P6 | O | `ligne_generate()` 交通类型映射表内嵌为字面量 | 待处理 |

---

## 已处理问题 — 执行记录

### P1 + P2 + P3：SRP 重构（2026-04-05）

**问题根源**：`pipeline.main()` 和 `gtfs_norm.py` 各自承担多项不相关职责；编码检测逻辑在 `rawgtfs_from_zip()` / `rawgtfs()` 中各自重复实现，`gtfs_utils.encoding_guess()` 形同虚设。

**执行结果**：

| 文件 | 操作 |
|------|------|
| `gtfs_core/pipeline.py` | 提取 `PipelineConfig` dataclass + `run_pipeline()` 纯编排函数；`main()` 缩减为 ~25 行 CLI 适配层 |
| `gtfs_core/gtfs_reader.py` | **新建**：`read_gtfs_zip()` / `read_gtfs_dir()`，编码检测统一委托 `encoding_guess()` |
| `gtfs_core/gtfs_norm.py` | 删除 `rawgtfs_from_zip`、`rawgtfs`、`read_date`、`read_validite`、`read_input` 及相关 import；文件从 ~360 行缩减至 ~200 行，仅保留规范化职责 |
| `gtfs_core/gtfs_utils.py` | `encoding_guess()` 扩展支持 `bytes`（ZIP 内存场景） |
| `worker.py`、`pipeline.py`、两个测试文件 | 更新导入路径，无 re-export 别名 |

**验证**：7 个单元测试全部通过。

### P0 — D：日历资源读取硬编码路径（2026-04-05）

**问题根源**：`Type_Jour_Vacances_A/B/C`（法国学区假期分类）来自 `Calendrier.xls`，原代码将文件路径硬编码在业务模块内，无法测试注入、无法替换为 DB 查询。

**执行结果**：

| 文件 | 操作 |
|------|------|
| `gtfs_core/calendar_provider.py` | **新建**：`CalendarProvider` Protocol + `LocalXlsCalendarProvider`（读 XLS，延迟加载，XLS 缺失时静默降级）+ `NullCalendarProvider`（测试用） |
| `gtfs_core/pipeline.py` | `run_pipeline()` 新增 `calendar_provider` 参数；内部调用 `_calendar.enrich(Dates)` 替代直接路径读取；CLI `main()` 传入 `LocalXlsCalendarProvider()` |
| `worker.py` | 显式传入 `LocalXlsCalendarProvider().enrich(Dates)` |

**Phase 1 迁移路径**（无需改动 pipeline/worker 逻辑）：

```python
# 实现 DBCalendarProvider，注入 run_pipeline()
class DBCalendarProvider:
    def __init__(self, session): self._session = session
    def enrich(self, dates: pd.DataFrame) -> pd.DataFrame:
        # 从 SQLite/Supabase calendar_dates 表查询，merge 到 dates
        ...

# worker.py 只需替换这一行
provider = DBCalendarProvider(db_session)
results  = run_pipeline(raw_dict, config, calendar_provider=provider)
```

**验证**：7 个单元测试全部通过。

### P4 — O：`ag_ap_generate_reshape()` 硬编码算法分支（2026-04-06）

**问题根源**：`ag_ap_generate_reshape()` 内部 if/elif 链直接判断数据特征并调用具体算法，每新增聚类方式都需修改分发函数。

**执行结果**：

| 文件 | 操作 |
|------|------|
| `gtfs_core/gtfs_spatial.py` | 新增 `ClusteringStrategy` Protocol（含 `marker` 属性 + `cluster()` 方法）；提取 `BigVolumeStrategy`、`HClusterStrategy`、`AsitStrategy` 三个具体策略类；新增 `select_strategy()` 工厂函数集中持有选择条件；`ag_ap_generate_reshape()` 缩减为 3 行纯调度，不含任何条件分支 |

**扩展路径**（新增算法无需修改现有代码）：
```python
class MyNewStrategy:
    marker = 'my_method'
    def cluster(self, stops: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        ...  # 实现算法

# 只需在 select_strategy() 中添加一个分支
```

### P5 — I：`gtfs_normalize()` 返回胖字典（2026-04-06）

**问题根源**：函数返回 13 键 `Dict[str, Any]`，IDE 无法静态检查键名，调用方只能靠字符串字面量定位字段。

**执行结果**：

| 文件 | 操作 |
|------|------|
| `gtfs_core/gtfs_norm.py` | 新增 `NormedGTFS(TypedDict)` 定义 13 个键的显式类型契约；`gtfs_normalize()` 返回类型由 `Dict[str, Any]` 改为 `NormedGTFS`；docstring 中手写 Output Schema 描述改为指向 TypedDict |

**零破坏性**：TypedDict 运行时仍是普通 dict，`pipeline.py` / `worker.py` / 测试文件中的 `normed['stops']` 等 dict 访问语法无需任何修改。

**Phase 1 注意**：若引入 `dataclass` 改为属性访问，届时需同步更新三个调用方。

**验证**：20 个测试全部通过。

---

## 待处理问题

### P6 — O：`ligne_generate()` 内嵌交通类型映射表

新增 GTFS 交通类型（如 `route_type=800`）需修改函数内部字面量，而非外部配置。

```python
types_map = pd.DataFrame({
    'route_type': [0, 1, 2, 3, 4, 5, 6, 7, 11, 12],
    'mode': ["tramway", "metro", "train", "bus", ...]
})
```

**目标方向**：将映射表提取为模块级常量或可注入的外部配置（JSON/DB），函数只做 merge 操作。低频变化，优先级最低。
