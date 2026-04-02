# CLAUDE.md — GTFS Miner

本文件为 Claude Code 在此仓库工作时的指导文档。

---

## 项目概述

GTFS Miner 是一款将 GTFS 公共交通原始数据转化为标准化业务分析输出（指标表格、空间图层）的工具。当前阶段为**从 QGIS 桌面插件迁移至 Web SaaS 应用**（见 `PRD.md`）。

**产品形态路线**：QGIS 插件（现有）→ Web 应用 MVP（Phase 0–1）→ SaaS（Phase 2+）

---

## 代码结构

### 核心处理模块（可直接复用于 Web）

| 文件 | 职责 |
|------|------|
| `gtfs_utils.py` | 基础工具：字符串规范化、时间转换、Haversine 距离、编码检测 |
| `gtfs_norm.py` | 数据标准化：清洗 GTFS 原始表，Schema 校验，列重命名 |
| `gtfs_spatial.py` | 空间聚类：生成通用站点（AG）与物理站点（AP）映射 |
| `gtfs_generator.py` | 业务生成：行程序列、服务日期矩阵、班次/通过次数/发车间隔 |
| `gtfs_export.py` | 结果导出：最终格式化，生成 CSV/表格展示层 |
| `gtfs_qgis_adapter.py` | QGIS 适配层（迁移时替换为 geopandas + GeoJSON） |

### Legacy / QGIS 插件层（不迁移）

| 文件 | 说明 |
|------|------|
| `GTFS_algorithm.py` | Legacy 算法，保留备用，**不参与 Web 迁移** |
| `GTFS_miner.py` | QGIS 插件入口，依赖 `qgis.core` |
| `GTFS_miner_dialog.py` | QGIS 对话框 UI |
| `resources.py` / `resources.qrc` | QGIS 资源文件 |

### 测试

- `test_gtfs_core.py` — 核心模块单元测试
- `test/` — QGIS 插件层测试（不适用于 Web）

---

## 开发规范（`dev_rules.md` 摘要）

### 1. 模块化与层级解耦

- 每个独立功能放在单独 `.py` 文件中，单文件不超过 **600 行**
- **算法核心模块严禁导入 `qgis.core`**；QGIS 相关逻辑仅限 adapter 层
- Web 迁移中，QGIS 依赖替换为 `geopandas + shapely`

### 2. 函数契约

- 所有公开函数**必须**使用 Python 类型注解（`typing`）
- 处理 DataFrame 的函数，docstring 中**必须**标注核心 Input/Output Schema：
  ```python
  def process_stops(df: pd.DataFrame) -> pd.DataFrame:
      """
      Input Schema: [stop_id, stop_lat, stop_lon]
      Output Schema: [stop_id, normalized_lat]
      """
  ```

### 3. 模块内部结构

- 模块开头必须有功能说明文档字符串
- 严禁 `from module import *`，统一明文导入
- 路径处理**强制使用 `pathlib.Path`**，严禁字符串拼接
- 每个模块必须包含 `if __name__ == '__main__':` 自测块

### 4. 复杂流程

复杂逻辑需包含 ASCII 流程图注释，示例：
```
输入 GTFS 目录 -> [gtfs_norm] -> 规范化 DF 字典
               -> [gtfs_generator] -> 计算 ITI
               -> [gtfs_export] -> 输出 CSV
```

---

## 硬编码常量（修改前需确认）

以下常量影响处理结果，**不得随意修改**，V5 版本前保持不变：

| 常量 | 当前值 | 位置 | 说明 |
|------|-------|------|------|
| 站点聚类距离阈值 | `100`（米） | `gtfs_spatial.py:33` | 层次聚类截断高度 |
| 大数据集切换阈值 | `5000` 站点 | `GTFS_algorithm.py:454` | 超过此数切换 K-Means |
| K-Means 分组基数 | `500` 站点/组 | `gtfs_norm.py:174` | `k = len(stops) / 500` |
| 通用站点 ID 偏移 | `+10000` | `gtfs_spatial.py:36` | AG 编号前缀 |
| 物理站点 ID 偏移 | `+100000` | `gtfs_spatial.py:37` | AP 编号前缀 |
| 缺失 direction_id | `999` | `gtfs_generator.py:38` | 无方向信息占位符 |
| 缺失 route_type | `3`（bus） | `gtfs_norm.py:64` | 缺失交通模式回退值 |
| 缺失 location_type | `0`（物理站点） | `gtfs_norm.py:47` | 缺失站点类型回退值 |
| 输出方向筛选 | `direction_id == 0` | `gtfs_export.py:24` | OD 分析只取主方向 |
| 编码采样大小 | `10000` 字节 | `gtfs_utils.py:91` | chardet 采样量 |

---

## Web 迁移架构（PRD Phase 0–1）

目标技术栈：**FastAPI + Celery + Redis + PostgreSQL + React/TypeScript**

处理流程（Celery Worker 中运行）：
```
GTFS ZIP 上传
    -> gtfs_utils.encoding_guess()   # 编码检测
    -> gtfs_norm.*_norm()            # 各表标准化
    -> gtfs_spatial.ag_ap_generate_*()  # 站点聚类
    -> gtfs_generator.*()            # 业务指标生成
    -> gtfs_export.MEF_*()           # 格式化输出
    -> 写入 PostgreSQL + 归档 ZIP
```

**模块迁移状态**：
- `gtfs_norm / spatial / generator / export / utils` → 直接复用，无需修改
- `gtfs_qgis_adapter.py` → 替换为 geopandas（V2 地图功能时处理）
- `GTFS_algorithm.py` → 不迁移

---

## 处理流程输出表对照

| 分组 | 表名 | 来源模块 |
|------|------|---------|
| A_1 | 通用站点（AG） | `gtfs_spatial` |
| A_2 | 物理站点（AP） | `gtfs_spatial` |
| B_1 | 线路（Lignes） | `gtfs_generator` |
| B_2 | 子线路（Sous-Lignes） | `gtfs_generator` |
| C_1 | 班次（Courses） | `gtfs_generator` |
| C_2 | 行程详情（Itinéraire） | `gtfs_generator` |
| C_3 | 弧段行程（Itinéraire Arc） | `gtfs_generator` |
| D_1 | 服务日期 | `gtfs_generator` |
| D_2 | 日类型（Jourtype） | `gtfs_generator` |
| E_1 | 站点通过次数 | `gtfs_generator` |
| E_4 | 弧段通过次数 | `gtfs_generator` |
| F_1–F_4 | 线路/子线路指标（KCC、Headway） | `gtfs_export` |

---

## 注意事项

- **不在范围内**：GTFS-RT 实时数据、Access 数据库导出、SNCF 专用逻辑、移动端适配
- CSV 输出格式：**分号分隔（`;`）、UTF-8 with BOM**（兼容 Excel）
- 多租户隔离：所有查询必须附加 `tenant_id` 过滤；存储路径前缀 `/{tenant_id}/projects/{project_id}/`
- 大数据集（>5 万站点，如 IDFM）仅 Enterprise 套餐支持，处理时间约 30 分钟
