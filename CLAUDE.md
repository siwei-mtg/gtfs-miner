# CLAUDE.md — GTFS Miner

当前阶段：**从 QGIS 桌面插件迁移至 Web SaaS 应用**（Phase 0 MVP）。
产品路线：QGIS 插件（Legacy）→ Web MVP（Phase 0–1）→ SaaS（Phase 2+）。

> 架构总览见 `docs/architecture.md`，产品需求见 `docs/PRD.md`。

---

## 边界约束

- `legacy_qgis/` **仅供参考，禁止在 Web 端构建中引用或修改**。
- 严禁导入 `qgis.core`。
- 路径处理强制使用 `pathlib.Path`，禁止字符串拼接路径。
- 核心算法模块使用**显式相对导入**（如 `from .gtfs_utils import ...`）。

---

## 开发规范

- 所有公开函数必须使用类型注解。
- 处理 DataFrame 的函数需在 docstring 标注 Input/Output Schema。
- **Git Commit**：使用 Angular 规范（`feat:`, `fix:`, `refactor:` 等）。
- CSV 输出格式：**分号分隔（`;`）、UTF-8 with BOM**（兼容 Excel）。

---

## 硬编码常量（V5 前禁止修改）

| 常量 | 当前值 | 位置 | 说明 |
|------|-------|------|------|
| 站点聚类距离阈值 | `100` m | `gtfs_spatial.py` | 层次聚类截断高度 |
| 大数据集切换阈值 | `5000` 站点 | `gtfs_spatial.py` | 超过此值切换至 K-Means |
| K-Means 分组基数 | `500` 站点/组 | `gtfs_norm.py` | `k = len(stops) / 500` |
| 缺失 direction_id | `999` | `gtfs_generator.py` | 占位符 |
| 缺失 route_type | `3`（bus） | `gtfs_norm.py` | 回退值 |
| 编码采样大小 | `10000` 字节 | `gtfs_utils.py` | chardet 采样量 |

---

## 数据库

当前 Phase 0 使用 SQLite（`backend/storage/miner_app.db`）。

**迁移至 Supabase（Phase 1）时注意**：
- 连接串存放于 `backend/.env`（已加入 `.gitignore`，**勿提交**）
- `database.py` 需删除 `check_same_thread: False`（SQLite 专用参数）
- 驱动使用 `psycopg2-binary`（同步，与 `worker.py` 同步模式匹配）
- `worker.py` 业务逻辑无需改动，ORM 对两种数据库透明

---

## SOLID 约束

> 完整分析与重构方案见 `docs/SOLID_analysis.md`。

- **P0 — 禁止硬编码资源路径**：不得新增 `Path(__file__).parent / "resources" / ...` 依赖；日历数据须通过参数注入（DIP）。
- **P1 — pipeline 编排与 I/O 分离**：纯编排逻辑放入 `run_pipeline()`，文件读写只在 `main()` 和 `worker.py` 边界处发生（SRP）。
- **P2 — 禁止在 `gtfs_norm.py` 新增文件 I/O**：读取逻辑属于 `gtfs_reader.py`（SRP）。
- **P3 — 新函数返回值优先用 `TypedDict` / `dataclass`**，避免扩大胖字典（ISP）。

---

## 测试

```bash
cd backend && pytest
```

- 测试数据集位于 `backend/tests/Resources/raw/`（SEM、SOLEA、ginko 三个最小样本）。
- 禁止在测试中引入新的 GTFS 样本数据（保持最小化）。
- 大数据集（IDFM 规模 >5 万站点）处理时间约 30 分钟，集成测试中避免使用。

---

## Bug 追踪

**每次运行 pytest 后**，若出现新的失败测试，Claude 必须执行以下操作：

1. 判断该 bug 是否已记录在 `docs/BUGS_AND_TECH_DEBT.md` 中。
2. **若未记录**：在文件的 Bug 列表表格末尾追加一行，并在文件末尾新增对应的详情小节，格式与已有条目一致，包含：ID、状态（🔴 Open）、严重度、标题、影响测试、错误信息、根因、修复方案（可为"待查"）、涉及文件。
3. **若已记录**：无需重复追加，但如有新信息（如根因确认、修复方案明确）则更新对应条目。
4. 若某个 bug 已被修复且测试通过，将状态改为 ✅ Resolved 并注明修复 commit。

技术债（非测试失败的代码质量问题）同理维护在同一文件的"技术债列表"中。
