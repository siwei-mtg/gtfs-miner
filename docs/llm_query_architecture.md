# LLM 数据查询架构评估

> **背景**：评估在 GTFS Miner 处理输出上增加 LLM 自然语言查询与自定义指标派生功能的技术路径。  
> **日期**：2026-04-10 | **阶段**：Phase 0/1 参考

---

## 1. 问题定义

用户希望在 pipeline 处理结果上支持两类操作：

1. **自然语言查询**：如"查询周一早高峰通过次数最多的前 10 个站点"
2. **新指标派生**：以 A_*/B_*/C_*/D_* 作为 DWD 层，生成管线尚未计算的自定义指标（如"各线路每公里平均停站数"、"各区段早高峰发车间隔方差"），不依赖现有 E_*/F_* 文件

**当前状态**：

- 管线输出 14 个 CSV 文件（`;` 分隔，UTF-8 BOM），无查询 API
- SQLite 仅存储项目元数据（user/tenant/project），不含处理数据
- `/tables/{table_name}` API 端点目前是空 stub，返回 `[]`
- 管线计算全程在内存 Pandas DataFrame 中完成

---

## 2. 为什么单轮 Text-to-SQL 不够

在进入方案设计前，需理解 GTFS 数据的三个结构性问题，它们会直接导致单轮 Text-to-SQL 失效：

### 2.1 透视列问题（Pivot Problem）

E_*/F_* 指标文件使用**透视列**结构——日类型作为列名：

```
# E_1_Nombre_Passage_AG.csv 实际结构
id_ag_num | stop_name     | stop_lat | stop_lon | 1    | 2    | ... | 7
----------|---------------|----------|----------|------|------|-----|----
10001     | Gare Centrale | 48.851   | 2.341    | 1240 | 1187 | ... | 543
```

其中 `1`～`7` 为星期一至星期日的通过次数。这种结构对 SQL 非常不友好，必须先 unpivot（melt）才能规范化查询。

### 2.2 列名不透明

| 实际列名 | 含义 |
|----------|------|
| `DIST_Vol_Oiseau` | 连续站点间的大圆距离（米） |
| `h_dep_num` | 出发时间（日内小数，0.0～1.0） |
| `id_ag_num` | 聚合站（Arret Generique）数字 ID |
| `Headway_HPM` | 早高峰发车间隔（分钟） |
| `sous_ligne` | 子线路标识符（复合业务键，非自然主键） |

零样本情况下，LLM 对这些列名的推断准确率极低，估计 < 40%。

### 2.3 复杂问题需要多步推导

有意义的交通指标往往无法一条 SQL 完成：

```
用户："分析 12 号线的服务均衡性"

需要：
  Step 1 → 查 B_2 获取 12 号线所有子线路和停站序列
  Step 2 → 查 C_2 计算各区段实际发车间隔分布
  Step 3 → 计算间隔的方差或 Gini 系数
  Step 4 → 识别间隔超过阈值的异常时段
  Step 5 → 生成结论
```

单轮 Text-to-SQL 在 Step 1 就停了。同样，空间问题（"找出 500m 内未被同一子线路覆盖的站点"）需要混合 SQL + 地理计算，一条 SQL 无法表达。

**结论**：对于 GTFS 数据查询，**Agent 架构比单轮 Text-to-SQL 的价值高一个量级**，核心差异不是"多轮对话"，而是工具调用能力和指标持久化。

---

## 3. 问题一：是否需要语义层建模？

### 结论：**是，但形式是 Agent 的工具，不是静态配置文件**

语义层在 Agent 架构中以两种方式存在：

**静态层**：`semantic_schema.yaml`，声明表/列的业务定义，作为 Agent 的初始上下文注入。Phase 0/1 的 schema 基本固定，一个 YAML 文件足够。

```yaml
tables:
  arrets_generiques:
    source_file: A_1_Arrets_Generiques.csv
    description: 聚合站点（物理站点空间聚类后的逻辑站点），是所有指标的空间基准
    columns:
      id_ag_num:
        type: integer
        description: 聚合站唯一数字ID，是 C_*/E_*/B_2 的关联键
      stop_name:
        type: string
        description: 站点名称（取聚类内第一个物理站点的名称）

relations:
  - from: cours.id_ag_num_debut
    to: arrets_generiques.id_ag_num
    label: 行程起点站
```

**动态层**：`describe_table(name)` 工具。Agent 自主调用时，返回实时表结构 + 示例值行。有了这个工具，schema 变化时无需手动同步 YAML，Agent 可自主探索。

**不需要 dbt / Cube.dev 的原因**：这些工具适合多数据源、多团队、持续演进的 BI 场景。GTFS Miner 的 schema 在 Phase 0/1 固定，静态 YAML + 动态工具的组合已经足够。

---

## 4. 问题二：是否需要将管线从 Pandas 改为 SQL？

### 结论：**管线不需要改；在 pipeline 完成后加一个 SQLite 加载步骤**

这是两个独立关切：

| 层次 | 现状 | 建议 | 理由 |
|------|------|------|------|
| **管线计算层**（gtfs_norm → gtfs_spatial → gtfs_generator） | Pandas | 保持不变 | 空间聚类（DBSCAN/K-Means）、时间序列处理、复杂 pivot 等场景 Pandas 有天然优势；改写为 SQL 无准确率收益，重构成本极高 |
| **查询层**（pipeline 完成后的 Agent 交互） | 无（CSV 文件） | 加载进 SQLite | SQL 语义明确、可验证；E_*/F_* 在加载时 melt 为规范行格式 |

**加载步骤的关键点**：E_*/F_* 透视列在加载时转为规范行（unpivot）：

```python
# E_1 透视结构 → 规范化，加载进 SQLite
df_melted = df_passage.melt(
    id_vars=["id_ag_num", "stop_name", "stop_lat", "stop_lon"],
    var_name="jour_type",    # 1-7 或 Type_Jour_Vacances_A 等
    value_name="nb_passages"
)
```

加载位置：`worker.py` step [7/7] 完成后，写入 `{project_id}_query.sqlite`。

---

## 5. 方案对比

### 方案 A：单轮 Text-to-SQL（无 Agent，无语义层）

**做法**：LLM 接收 CSV 文件头 + 用户问题，生成一条 SQL 并执行。

| 维度 | 评分 |
|------|------|
| 实施成本 | ★☆☆☆☆ 极低 |
| 准确率 | ★★☆☆☆ 低（列名不透明，无法多步推导，透视列混淆） |
| 指标派生能力 | 无 |

**适用场景**：1-2 天快速验证 LLM 能否理解数据，不适合生产。

---

### 方案 B：语义层 + 单轮 Text-to-SQL on SQLite

**做法**：pipeline 完成后加载 CSV 到 SQLite（E_*/F_* 先 melt），LLM 接收 `semantic_schema.yaml` + 用户问题 → 生成 SQL → 执行返回结果。

| 维度 | 评分 |
|------|------|
| 实施成本 | ★★★☆☆ 中（CSV→SQLite 加载器 ~200 行，schema YAML ~100 行） |
| 准确率 | ★★★★☆ 高（SQL 可验证，语义层消除列名歧义） |
| 指标派生能力 | 低（单步 SQL，无法拆解复杂问题） |

**限制**：无自我修正，无多步推导，复杂指标需要用户自行拆解问题。

---

### 方案 C：ReAct Agent + 工具箱 + 指标持久化 ⭐ 推荐

**做法**：Agent 通过 Think → Act（调工具）→ Observe 循环自主完成多步推导，最终可将派生指标持久化回项目。

**核心工具箱设计**（工具设计是此方案的最关键决策）：

| 工具 | 签名 | 作用 |
|------|------|------|
| `query_dwd` | `(sql: str) → DataFrame` | 在 DWD SQLite 上执行 SQL，是主计算工具 |
| `describe_table` | `(name: str) → Schema + 示例行` | 自主探索表结构，无需依赖静态 YAML |
| `list_indicators` | `() → list` | 列出已有 E_*/F_* 及用户自定义指标 |
| `spatial_filter` | `(stops, center, radius_m) → id_list` | 地理围栏筛选（SQL 无法表达的空间查询） |
| `save_indicator` | `(name, sql, description) → void` | 持久化派生指标，写入项目自定义指标库 |
| `explain_result` | `(df) → str` | 将数字结果翻译为交通业务语言 |

**Agent 工作流示例**：

```
用户："分析 12 号线的服务均衡性"

[Plan]  拆解为：① 获取子线路 ② 计算各区段发车间隔 ③ 统计分布 ④ 识别异常

[Act 1] query_dwd("SELECT * FROM sous_lignes WHERE route_short_name='12'")
[Obs 1] 返回 4 条子线路记录

[Act 2] query_dwd("SELECT sous_ligne, jour_type, AVG(headway) ... FROM cours JOIN ...")
[Obs 2] 各区段各日类型的平均间隔

[Act 3] query_dwd("计算间隔方差...")   ← 如果 SQL 报错，Agent 自动修正重试
[Obs 3] 方差结果

[Act 4] save_indicator(
    name="headway_variance_ligne_12",
    sql="...",
    description="12 号线各区段发车间隔方差，周一至周日"
)

[Output] "12 号线在早高峰（7-9 时）服务均衡性较好，方差 X 分钟²；
          晚间（20 时后）3 号子线路间隔达 45 分钟，是全线最薄弱环节。"
```

**指标持久化的独特价值**：`save_indicator` 将一次性分析沉淀为可复用的自定义指标。用户与 Agent 协作越多，项目的指标库越丰富，相当于在 pipeline 固化的 E_*/F_* 层之上持续扩展一个**用户自定义指标层**。

| 维度 | 评分 |
|------|------|
| 实施成本 | ★★★★☆ 中高（Agent 框架 + 工具实现 + SQLite 加载，约 2-3 周） |
| 准确率 | ★★★★★ 高（自我修正 + 多步推导 + 空间工具） |
| 指标派生能力 | 高（链式推理 + 持久化） |

---

### 方案 D：向量检索 + Agent 混合（RAG 架构）

**做法**：将站点/线路描述预计算为 embedding，用向量相似度检索实体，再交给 Agent 执行 SQL 聚合。

| 维度 | 评分 |
|------|------|
| 实施成本 | ★★★★★ 高（需向量数据库、embedding pipeline、检索-生成协调层） |
| 准确率 | ★★★★★ 高（适合模糊站名匹配，如"从南站附近"） |
| 指标派生能力 | 高 |

**适用场景**：用户查询包含模糊实体名称（站名、线路名拼写不准确），或需要跨项目语义搜索时。Phase 0/1 暂不推荐，方案 C 的精确匹配已够用。

---

## 6. 发力点总结

三个关键决策，优先级从高到低：

**① 工具设计**（最关键）：`describe_table` + `save_indicator` 是两个核心差异化工具。前者让 Agent 自主探索 schema，后者让一次性分析变成可复用资产。工具边界划分正确，Agent 的能力上限才能被充分释放。

**② 指标持久化机制**：`save_indicator` 写入项目专属的 `custom_indicators` 表，每条记录存储 SQL 定义 + 描述 + 创建时间。`list_indicators` 将其与 E_*/F_* 平铺给用户，用户无需知道哪些是管线输出、哪些是自定义的。

**③ 语义层的维护策略**：`semantic_schema.yaml` 在 Phase 1 手动维护即可；Phase 2 可考虑从 SQLite 表结构 + 注释自动生成，减少人工维护负担。

---

## 7. 推荐路径

```
Phase 0  →  方案 A（1-2 天，验证 LLM 理解数据的可行性）
Phase 1  →  方案 B（生产基线，CSV→SQLite + semantic_schema.yaml + /query 端点）
Phase 1+ →  方案 C（在 B 的 SQLite 基础上加 Agent 层 + 工具箱 + 指标持久化）
Phase 2+ →  方案 C + 局部方案 D（为模糊实体匹配加向量检索）
```

方案 B 和 C 共享同一个 SQLite 基础，升级路径平滑——Phase 1 实现加载和 `/query` 端点，Phase 1+ 在同一 SQLite 上套 Agent 层即可，无需重建。

---

## 8. 方案 C 实施要点

1. **`worker.py`** step [7/7] 后增加 `load_outputs_to_sqlite(project_id, output_dir)` 调用
2. E_*/F_* 文件加载时调用 `pd.melt()` unpivot 日类型列
3. 建 `custom_indicators` 表存储用户派生指标（name, description, sql, created_at）
4. `semantic_schema.yaml` 放于 `backend/app/services/gtfs_core/`，与代码同版本管理
5. 实现 `/api/v1/projects/{project_id}/query` 端点（POST），接收自然语言问题，返回结果 + 所用 SQL
6. 当前 stub `/tables/{table_name}` 端点可在同步骤实现，复用同一 SQLite

---

## 9. 附：数据分层图

```
┌──────────────────────────────────────────────────────────────────┐
│  DWD 层（明细数据，Agent 派生新指标的原料）                         │
│                                                                  │
│  A_1 Arrets_Generiques ──┐                                       │
│      id_ag_num           ├── C_2 Itineraire (id_ag_num)          │
│  A_2 Arrets_Physiques ───┘    C_3 Itineraire_Arc (id_ag_num_a/b) │
│      id_ap_num                B_2 Sous_Lignes (id_ag_num_debut/terminus)│
│                                                                  │
│  B_1 Lignes ─────────────┐                                       │
│      id_ligne_num         ├── B_2 Sous_Lignes (id_ligne_num)     │
│                           ├── C_1 Courses (id_ligne_num)         │
│                           └── D_2 Service_Jourtype (id_ligne_num)│
│                                                                  │
│  D_1 Service_Dates ────── id_service_num → C_1, D_2              │
└──────────────────────────────────────────────────────────────────┘
          │  管线固化（pipeline 已计算，可直接查询）
          ▼
┌──────────────────────────────────────────────────────────────────┐
│  指标层（E_*/F_*，pipeline 输出的第一批聚合指标）                   │
│                                                                  │
│  E_1 Nombre_Passage_AG    — 通过次数 / 站点 / 日类型              │
│  E_4 Nombre_Passage_Arc   — 通过次数 / 路段 / 日类型              │
│  F_1 Nombre_Courses_Lignes— 班次数 / 线路 / 日类型                │
│  F_2 Caract_SousLignes    — 子线路特征（发车间隔等）               │
│  F_3 KCC_Lignes           — 公里班次 / 线路 / 日类型              │
│  F_4 KCC_Sous_Ligne       — 公里班次 / 子线路 / 日类型            │
└──────────────────────────────────────────────────────────────────┘
          │  Agent 按需派生（save_indicator 持久化）
          ▼
┌──────────────────────────────────────────────────────────────────┐
│  自定义指标层（custom_indicators 表，随使用持续增长）               │
│  每条记录 = name + description + SQL 定义 + created_at           │
│  示例：每公里停站数、首末班时间窗口、区段间隔方差...                 │
└──────────────────────────────────────────────────────────────────┘
```
