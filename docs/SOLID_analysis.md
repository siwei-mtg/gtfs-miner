# SOLID 原则分析报告 — gtfs_core

**分析范围**：`backend/app/services/gtfs_core/`  
**分析日期**：2026-04-04  
**涉及文件**：`pipeline.py`、`gtfs_norm.py`、`gtfs_spatial.py`、`gtfs_generator.py`

---

## 总结

| 原则 | 违反程度 | 主要位置 |
|------|---------|---------|
| **S — 单一职责** | 高 | `pipeline.main()`, `gtfs_norm` 模块边界模糊 |
| **O — 开闭** | 中 | `ag_ap_generate_reshape()`, `ligne_generate()` |
| **D — 依赖倒置** | 中 | `read_date()`/`read_validite()` 硬编码路径 |
| **L — 里氏替换** | 无 | 过程式代码，无继承体系 |
| **I — 接口隔离** | 轻微 | `gtfs_normalize()` 返回胖字典 |

---

## S — 单一职责原则 (Single Responsibility Principle)

> 一个模块应该只有一个引起它变化的原因。

### 违反 1：`pipeline.py::main()` — God Function

`main()` 函数同时承担以下职责：

1. CLI 参数解析（`argparse`）
2. 流程编排（调用各模块）
3. 文件 I/O（CSV 写入到磁盘）
4. 日志打印（`print` 进度）

任何一个职责的变化（比如改成 Web API 入口、换成数据库写出、静默运行）都必须触动同一个函数。这也是为什么这个函数在 Web 化改造后基本无法复用——它的 I/O 和编排耦合在一起。

**问题代码（`pipeline.py:132–151`）**：
```python
# 编排 + 文件写入混在同一函数体
AG.to_csv(output_dir / "A_1_Arrets_Generiques.csv", **CSV_OPTS)
AP.to_csv(output_dir / "A_2_Arrets_Physiques.csv",  **CSV_OPTS)
```

### 违反 2：`gtfs_norm.py` 模块边界模糊

模块名叫"规范化"，但实际上还包含：

- `rawgtfs_from_zip()` / `rawgtfs()` — **文件读取**职责
- `read_date()` / `read_validite()` — **资源文件加载**职责
- `read_input()` — **一键加载**入口（混合了读取与规范化）

文件读取是 I/O 层的职责，和数据规范化（清洗、类型转换、列校验）是两件不同的事，理应分属不同模块。`build_dates_table()` 放在 `pipeline.py` 而非日历模块同理。

### 违反 3：`rawgtfs_from_zip()` 读取与编码处理混合

```python
# gtfs_norm.py:208-213
try:
    df = pd.read_csv(f, encoding='utf-8', low_memory=False)
except (UnicodeDecodeError, pd.errors.ParserError):
    df = pd.read_csv(f, encoding='latin-1', low_memory=False)
```

编码检测逻辑与文件读取耦合在一起，而 `gtfs_utils.py` 里已经存在 `encoding_guess()` 函数。职责应统一收归 `gtfs_utils`，`rawgtfs_from_zip` 只做读取。

---

## O — 开闭原则 (Open/Closed Principle)

> 软件实体应对扩展开放，对修改封闭。

### 违反 1：`gtfs_spatial.py::ag_ap_generate_reshape()`

每增加一种聚类算法，必须修改这个分发函数的 `if/elif/else` 链：

```python
# gtfs_spatial.py:147-163
if nb_types == 1:
    if ap_potentiel >= 5000:
        AP, AG = ag_ap_generate_bigvolume(raw_stops)   # ← 硬编码分支
    else:
        AP, AG = ag_ap_generate_hcluster(raw_stops)    # ← 硬编码分支
elif ap_no_parent == 0:
    AP, AG = ag_ap_generate_asit(raw_stops)            # ← 硬编码分支
```

**符合 OCP 的思路**：策略模式（Strategy Pattern）。定义一个 `ClusteringStrategy` 协议，由调用方注入算法，`reshape` 函数只负责调用，不负责选择。

```python
# 改造方向示意
class ClusteringStrategy(Protocol):
    def cluster(self, stops: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]: ...

def ag_ap_generate_reshape(raw_stops, strategy: ClusteringStrategy) -> ...:
    return *strategy.cluster(raw_stops), strategy.marker
```

### 违反 2：`gtfs_norm.py::ligne_generate()` 内嵌映射表

```python
# gtfs_norm.py:101-104
types_map = pd.DataFrame({
    'route_type': [0, 1, 2, 3, 4, 5, 6, 7, 11, 12],
    'mode': ["tramway", "metro", "train", "bus", ...]
})
```

新增交通类型（如 GTFS 未来扩展的 `route_type=800`）必须修改函数内部。这张映射表应该是可注入的外部配置（常量文件或数据库），而非内嵌字面量。

---

## D — 依赖倒置原则 (Dependency Inversion Principle)

> 高层模块不应依赖低层模块；两者都应依赖抽象。

### 违反 1：日历资源读取硬编码文件路径

```python
# gtfs_norm.py:238
p = Path(__file__).parent / "resources" / "Calendrier.txt"
```

高层业务逻辑直接依赖了文件系统的具体路径。这带来两个直接问题：

1. **测试困难**：测试中无法注入测试日历数据，必须依赖真实文件存在。
2. **阻碍迁移**：PRD Phase 1 要求日历数据从 SQLite/Supabase 获取（`calendar.service.get_dates()`），而当前代码完全无法适配——必须修改 `gtfs_norm` 内部。

**符合 DIP 的思路**：`gtfs_normalize()` 接收一个日历数据提供者参数，而非自己去读文件：

```python
# 改造方向示意
def gtfs_normalize(raw_dict, calendar_provider: CalendarProvider) -> dict:
    dates = calendar_provider.get_dates(...)  # 文件/DB/API 均可
```

### 违反 2：`pipeline.py::main()` 直接绑定具体实现

`main()` 通过顶层 `import` 直接耦合所有底层模块的具体函数。高层编排逻辑和低层算法之间没有任何抽象层，导致单独测试 pipeline 逻辑时无法替换任何一个步骤。

---

## L — 里氏替换原则 (Liskov Substitution Principle)

**无违反。**

该代码库采用纯过程式风格，几乎不使用继承。所有模块均为独立函数集合，不存在父子类替换的场景，因此 LSP 不适用。

---

## I — 接口隔离原则 (Interface Segregation Principle)

> 不应强迫客户端依赖它不使用的接口。

### 轻微违反：`gtfs_normalize()` 返回胖字典

`gtfs_normalize()` 返回一个包含 15 个键的大字典：

```python
return {
    'agency': ..., 'routes': ..., 'stops': ..., 'trips': ...,
    'stop_times': ..., 'calendar': ..., 'calendar_dates': ...,
    'shapes': ..., 'route_id_coor': ..., 'trip_id_coor': ...,
    'ser_id_coor': ..., 'initial_na': ..., 'final_na_time_col': ...
}
```

下游调用者（如 `gtfs_spatial` 只需要 `stops`，`gtfs_generator` 只需要 `stop_times`/`trips`）被迫接收整个字典。这不是严格的 ISP 违反（Python 没有强制接口），但它是一个信号：

- 字典无类型约束，IDE 无法静态检查键名
- 调用方需要阅读文档才知道自己应该用哪些键
- 建议改为具名 `TypedDict` 或 `dataclass`，使契约显式化

---

## 优先级建议

从实际影响出发，建议按以下顺序处理：

| 优先级 | 问题 | 原因 |
|-------|------|------|
| **P0** | `read_date()`/`read_validite()` 硬编码路径（D） | 直接阻碍 Phase 1 的 Supabase 迁移 |
| **P1** | `pipeline.main()` 混合 I/O 与编排（S） | Web 化后此函数无法复用 |
| **P2** | `ag_ap_generate_reshape()` 硬编码分支（O） | 新增算法成本高，当前有3种算法已现端倪 |
| **P3** | `gtfs_normalize()` 胖字典（I） | 影响可读性与静态分析，改动范围大 |
| **P4** | `ligne_generate()` 内嵌映射表（O） | 低频变化，风险较低 |

---

## 重构方案：`pipeline.py::main()`

### 目标

将 `main()` 的四项职责拆解为职责单一的三个层次：

```
argparse (CLI 适配)  →  run_pipeline() (纯编排)  →  gtfs_* 函数 (算法)
```

### 背景发现

探索 `worker.py` 后发现：Web 层**已经绕过 `main()`**，手动逐步调用所有 pipeline 函数（约 70 行重复逻辑），且两处代码都使用相同的 `hpm`/`hps`/`type_vac` 参数，但没有共享的配置对象。这意味着现在有两份并行维护的编排逻辑。

---

### Step 1 — 新增 `PipelineConfig` dataclass

将分散在 `main()` 和 `worker.py` 中的参数收归一处，放在 `pipeline.py` 顶部：

```python
from dataclasses import dataclass, field
from typing import Tuple

@dataclass
class PipelineConfig:
    hpm:      Tuple[float, float] = field(default_factory=lambda: (7/24, 9/24))
    hps:      Tuple[float, float] = field(default_factory=lambda: (17/24, 19/24))
    type_vac: str  = 'Type_Jour'
    has_shp:  bool = False          # shapes 可用时启用真实距离计算
```

原有 `DEFAULT_HPM`、`DEFAULT_HPS`、`DEFAULT_TYPE_VAC` 常量保留为别名，避免 `worker.py` 的现有 import 被破坏。

---

### Step 2 — 提取 `run_pipeline()` 纯编排函数

**函数签名：**

```python
from typing import Callable, Optional

def run_pipeline(
    raw_dict:    dict[str, pd.DataFrame],
    config:      Optional[PipelineConfig] = None,
    on_progress: Optional[Callable[[str], None]] = None,
) -> dict[str, pd.DataFrame]:
    """
    GTFS 处理流水线总编排。无文件 I/O，无 print。
    Input:  原始 GTFS 表字典 + 配置
    Output: 命名 DataFrame 字典（键名即 CSV 文件名前缀）
    """
```

**迁移内容（从 `main()` 移入）：**

- `gtfs_normalize()` 调用及所有下游步骤（当前 `main()` 第 119–218 行）
- `build_dates_table()` 调用（第 168 行）
- `pnode` 重命名块（第 192–195 行）——内部中间逻辑，不属于 I/O
- `type_vac` 列回退保护（目前仅在 `worker.py` 存在，应统一到此）
- 所有 `print("[N/7] ...")` 替换为 `on_progress` 回调

**返回字典（15 个键）：**

```python
return {
    "A_1_Arrets_Generiques":     AG,
    "A_2_Arrets_Physiques":      AP,
    "B_1_Lignes":                lignes_export,
    "B_2_Sous_Lignes":           sous_ligne,
    "C_1_Courses":               courses_export,
    "C_2_Itineraire":            itineraire_export,
    "C_3_Itineraire_Arc":        iti_arc_export,
    "D_1_Service_Dates":         ser_dates_export,
    "D_2_Service_Jourtype":      serv_jour_export,
    "E_1_Nombre_Passage_AG":     nb_psg_ag,
    "E_4_Nombre_Passage_Arc":    nb_psg_arc,
    "F_1_Nombre_Courses_Lignes": nb_crs_ligne,
    "F_2_Caract_SousLignes":     caract_sl,
    "F_3_KCC_Lignes":            kcc_ligne,
    "F_4_KCC_Sous_Ligne":        kcc_sl,
}
```

---

### Step 3 — Slim `main()`（目标 ~22 行）

`main()` 缩减为纯 CLI 适配层，只保留以下内容：

```python
def main() -> None:
    # 1. argparse
    parser = argparse.ArgumentParser(...)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="output")
    parser.add_argument("--type-vac", default='Type_Jour', choices=[...])
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)
    if not input_path.exists():
        print(f"Error: '{input_path}' does not exist.")
        return
    output_dir.mkdir(parents=True, exist_ok=True)

    start_time = time.time()

    # 2. CLI-only I/O: 加载原始表
    if input_path.is_dir():
        raw_dict = {f.stem: pd.read_csv(f, low_memory=False)
                    for f in input_path.glob('*.txt')}
    else:
        raw_dict = rawgtfs_from_zip(input_path)
    if not raw_dict:
        print("Error: No GTFS .txt tables found.")
        return

    # 3. 调用纯编排函数
    config  = PipelineConfig(type_vac=args.type_vac)
    results = run_pipeline(raw_dict, config, on_progress=print)

    # 4. CLI-only I/O: 写出 CSV
    for name, df in results.items():
        df.to_csv(output_dir / f"{name}.csv", **CSV_OPTS)

    print(f"\nDone. {time.time() - start_time:.2f}s — {output_dir.resolve()}")
```

---

### 次要受益：`worker.py` 简化

重构完成后，`worker.py` 约 70 行的手动步骤序列可替换为：

```python
from .gtfs_core.pipeline import run_pipeline, PipelineConfig, CSV_OPTS

config  = PipelineConfig(hpm=hpm, hps=hps, type_vac=type_vac)
results = run_pipeline(raw_dict, config, on_progress=send_progress)

for name, df in results.items():
    df.to_csv(out_dir / f"{name}.csv", **CSV_OPTS)
```

消除效果：
- 删除 ~70 行重复的步骤调用
- 删除重复的 `pnode` 重命名块
- 删除 `worker.py` 中单独维护的 `type_vac` 回退保护
- 将 15 处分散的 `to_csv` 调用收归为一个循环

> **注意**：重构后 CSV 写入发生在 `run_pipeline()` 返回之后，而非穿插在各步骤之间。若 WebSocket 客户端依赖文件写入完成后的进度信号，需调整 `on_progress` 的调用时机或在写出循环内补发一次进度通知。

---

### 涉及文件

| 文件 | 操作 |
|------|------|
| `backend/app/services/gtfs_core/pipeline.py` | 新增 `PipelineConfig`、`run_pipeline()`，精简 `main()` |
| `backend/app/services/worker.py` | （次要）替换逐步调用为 `run_pipeline()` |
| `gtfs_*` 所有模块 | **不修改** |

---

## 重构方案：`gtfs_norm.py` 模块边界模糊

### 问题诊断

`gtfs_norm.py` 当前承担四项不同职责，任意一项变化都需要修改这个文件：

| 职责 | 函数 | 是否属于"规范化"？ |
|------|------|---------------|
| 数据规范化（类型转换、列校验） | `*_norm()`、`gtfs_normalize()` | ✅ 是 |
| GTFS 文件 I/O（ZIP / 目录读取） | `rawgtfs_from_zip()`、`rawgtfs()` | ❌ 否 |
| 静态资源文件加载 | `read_date()`、`read_validite()` | ❌ 否（兼有 DIP 违反） |
| Legacy 一键入口 | `read_input()` | ❌ 否（QGIS 时代遗留，Web 栈中已无调用） |

**额外发现（编码逻辑重复）**：`gtfs_utils.py` 已有 `encoding_guess()` 工具函数，但 `rawgtfs_from_zip()` 和 `rawgtfs()` 各自实现了独立的 `try/except` 编码回退逻辑，违反了 DRY 原则。

---

### Step 1 — 新建 `gtfs_reader.py`，剥离文件 I/O

将 `rawgtfs_from_zip()` 和 `rawgtfs()` 迁移到独立的 `gtfs_reader.py`，同时修复编码逻辑，使用已有的 `encoding_guess()`：

```python
# backend/app/services/gtfs_core/gtfs_reader.py (新建)
"""GTFS 文件读取层：ZIP 和目录两种输入源，不做任何数据清洗。"""
from pathlib import Path
from typing import Dict, Union
from zipfile import ZipFile
import io

import pandas as pd

from .gtfs_utils import encoding_guess


def read_gtfs_zip(zippath: Union[str, Path]) -> Dict[str, pd.DataFrame]:
    """
    从 ZIP 文件读取 GTFS 原始 CSV 数据。
    编码检测委托给 gtfs_utils.encoding_guess()，不在此硬编码。
    """
    result = {}
    with ZipFile(zippath, "r") as zf:
        for name in zf.namelist():
            if not name.endswith('.txt'):
                continue
            stem = Path(name).stem
            raw_bytes = zf.read(name)
            # encoding_guess 基于 chardet 采样，返回 {'encoding': ..., 'confidence': ...}
            detected = encoding_guess(io.BytesIO(raw_bytes))
            enc = detected.get('encoding') or 'utf-8'
            try:
                result[stem] = pd.read_csv(io.BytesIO(raw_bytes), encoding=enc, low_memory=False)
            except (UnicodeDecodeError, pd.errors.ParserError):
                result[stem] = pd.read_csv(io.BytesIO(raw_bytes), encoding='latin-1', low_memory=False)
    return result


def read_gtfs_dir(dirpath: Union[str, Path]) -> Dict[str, pd.DataFrame]:
    """
    从本地目录读取 GTFS 原始 .txt 文件，编码检测同上。
    """
    result = {}
    for f in Path(dirpath).glob('*.txt'):
        detected = encoding_guess(f)
        enc = detected.get('encoding') or 'utf-8'
        try:
            result[f.stem] = pd.read_csv(f, encoding=enc, low_memory=False)
        except (UnicodeDecodeError, pd.errors.ParserError):
            result[f.stem] = pd.read_csv(f, encoding='latin-1', low_memory=False)
    return result
```

---

### Step 2 — `gtfs_norm.py` 保留重导出，保持向后兼容

当前 `rawgtfs_from_zip` 被以下文件直接导入：

- `backend/app/services/gtfs_core/pipeline.py`
- `backend/app/services/worker.py`
- `backend/tests/test_gtfs_norm.py`
- `backend/tests/test_gtfs_pipeline.py`

**不破坏现有导入的做法**：在 `gtfs_norm.py` 顶部添加重导出别名，调用方无需任何改动：

```python
# gtfs_norm.py 顶部新增（替代原有函数定义）
from .gtfs_reader import read_gtfs_zip as rawgtfs_from_zip   # 向后兼容别名
from .gtfs_reader import read_gtfs_dir as rawgtfs             # 向后兼容别名
```

原有函数定义（第 197–229 行）直接删除。

---

### Step 3 — 删除 `read_input()`

`read_input()` 是 QGIS 插件时代的一键入口，在整个 Web 栈中**无任何调用方**（已通过 `grep` 确认：仅在 `gtfs_norm.py` 内部被 `read_date()` / `read_validite()` 调用）。

直接删除第 254–265 行，无需迁移。

---

### Step 4 — `read_date()` 和 `read_validite()` 的归属（与 DIP P0 联动）

这两个函数同时违反 SRP 和 DIP：

- **SRP**：资源文件加载不是"规范化"职责
- **DIP**：`Path(__file__).parent / "resources" / "Calendrier.txt"` 硬编码了实现路径，与 Phase 1 的 Supabase 迁移目标直接冲突

**推荐处置方案**（与优先级 P0 对齐，待日历服务完成后统一迁移）：

```
当前：gtfs_norm.read_date()  →  读取本地 resources/Calendrier.txt
目标：calendar.service.get_dates(start, end)  →  从 SQLite/Supabase 查询
```

过渡期内可保留这两个函数在 `gtfs_norm.py` 中不动，但打上 `# TODO(P0): migrate to calendar.service` 注释，不再对其增加新逻辑。

---

### 重构前后对比

| 维度 | 重构前 | 重构后 |
|------|-------|-------|
| `gtfs_norm.py` 行数 | ~360 行，4 项职责 | ~280 行，纯规范化职责 |
| 文件 I/O | 内嵌在 norm 模块 | 独立 `gtfs_reader.py` |
| 编码检测 | 每处各自 try/except | 统一由 `encoding_guess()` 处理 |
| `read_input()` | 存在（无调用方） | 删除 |
| 向后兼容 | — | 重导出别名，调用方零改动 |

---

### 涉及文件

| 文件 | 操作 |
|------|------|
| `backend/app/services/gtfs_core/gtfs_reader.py` | **新建**：迁入 `rawgtfs_from_zip`、`rawgtfs`，修复编码逻辑 |
| `backend/app/services/gtfs_core/gtfs_norm.py` | 删除 I/O 函数体（保留重导出别名）、删除 `read_input()` |
| `backend/app/services/gtfs_core/__init__.py` | 若有公开导出，更新 `gtfs_reader` 路径 |
| `read_date()` / `read_validite()` | 暂保留，打 TODO 注释，待 P0（DIP 修复）时迁移 |
