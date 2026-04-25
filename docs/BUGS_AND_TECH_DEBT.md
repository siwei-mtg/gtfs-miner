# Bug & 技术债追踪表

**维护规则**：每次运行 pytest 发现失败时，Claude 自动将新 bug 追加至本文件（见 CLAUDE.md §Bug 追踪）。

---

## Bug 列表

| ID | 状态 | 严重度 | 标题 | 首次发现 |
|----|------|--------|------|---------|
| [BUG-001](#bug-001) | ✅ Resolved | High | `test_websocket` — `client_authed` auth bypass 被 function-scoped fixture 清除 → 401 | 2026-04-11 |
| [BUG-002](#bug-002) | ✅ Resolved | Medium | `test_upload_and_wait` — pipeline 完成但 output 目录不存在 | 2026-04-11 |
| [BUG-003](#bug-003) | ✅ Resolved | High | 假期区分析时 D2/E1/E4/F1/F3/F4 结果表全部为空 | 2026-04-11 |
| [BUG-004](#bug-004) | 🔴 Open | Medium | `DownloadButton.test.tsx` — 测试期望 `<a>` 元素但组件渲染 `<button>` | 2026-04-14 |
| [BUG-005](#bug-005) | 🔴 Open | Medium | `useAuth.test.ts` — 6 个测试因 `useAuthContext must be used within AuthProvider` 全部失败 | 2026-04-14 |
| [BUG-006](#bug-006) | 🔴 Open | Medium | `App.test.tsx` — 4 个路由测试在 Task 42 AppShell 重构后失败 | 2026-04-14 |
| [BUG-007](#bug-007) | ✅ Resolved | High | `e7be33f` 双路径 melt 在数字列名下误触发 label map → E1/E4/F1/F3/F4 再次为空 | 2026-04-22 |

---

### BUG-001

**标题**：`test_websocket_receives_progress_messages` 因 `dependency_overrides.clear()` 失效 → 401

**状态**：✅ Resolved（修复 commit：Task 20b session，2026-04-11）  
**严重度**：High（导致 WebSocket 集成测试持续失败）  
**影响测试**：`tests/test_websocket.py::test_websocket_receives_progress_messages`  
**错误信息**：
```
AssertionError: {"detail":"Not authenticated"}
assert 401 == 201
```

**根因**：  
`isolated_client_authed`（function-scoped）在 teardown 时调用 `app.dependency_overrides.clear()`，将 `client_authed`（session-scoped）注册的 `get_current_active_user` override 一并抹除。后续使用 `client_authed` 的测试因无 auth bypass 而返回 401。

**复现路径**：  
任意使用 `isolated_client_authed` 的测试（`test_download.py`、`test_tenancy.py`、`test_result_api.py`）→ teardown → `test_websocket` 使用 `client_authed` → 401。

**修复方案**：  
在所有 function-scoped fixtures 中将 `.clear()` 改为精确清除，避免影响其他 fixture 注册的 override：

```python
# backend/tests/conftest.py
# isolated_client、isolated_client_authed、fresh_client 的 teardown 均需修改

# 替换：
app.dependency_overrides.clear()

# 改为（按各 fixture 实际注册的 key）：
app.dependency_overrides.pop(get_db, None)
app.dependency_overrides.pop(get_current_active_user, None)  # 仅 authed 变体
```

**涉及文件**：`backend/tests/conftest.py`

---

### BUG-002

**标题**：`test_upload_and_wait` — pipeline 完成但 `output/` 目录未写入本地

**状态**：✅ Resolved（修复 commit：Task 20b session，2026-04-11）  
**严重度**：Medium（E2E 文件持久化断言失败；pipeline 本身运行正常）  
**影响测试**：`tests/test_api_pipeline_integration.py::test_upload_and_wait`  
**错误信息**：
```
AssertionError: Output directory not found:
  C:\...\storage\projects\{id}\output
assert False
```

**根因**（已确认）：  
`worker.py` 写出路径为 `PROJECT_DIR / project.tenant_id / project_id / "output"`（含 `tenant_id` 层级），而测试（`test_api_pipeline_integration.py:92`）断言路径为 `PROJECT_DIR / project_id / "output"`（缺少 `tenant_id`）。路径不匹配导致 `assert out_dir.exists()` 失败。

**修复方案**：  
更新测试中路径构造，先从 DB 查询 `project.tenant_id`，再拼接完整路径：

```python
# test_api_pipeline_integration.py
db = SessionLocal()
project = db.query(Project).filter(Project.id == project_id).first()
db.close()
out_dir = PROJECT_DIR / project.tenant_id / project_id / "output"
```

**涉及文件**：`backend/tests/test_api_pipeline_integration.py:92`

---

---

### BUG-003

**标题**：假期区分析时 D2/E1/E4/F1/F3/F4 结果表全部为空

**状态**：✅ Resolved（2026-04-11）  
**严重度**：High（前端所有 pivot 表无数据，用户无法使用假期区功能）  
**影响范围**：`vacances` 参数为 A/B/C 时；`全部`（Type_Jour）模式不受影响  

**根因**（双重）：  
1. `Calendrier.xls` 的 `Type_Jour_Vacances_*` 列存储**字符串标签**（`"Lundi_Scolaire"`, `"Ferie"` 等），pipeline pivot 后 CSV 列名亦为字符串。`worker.py` 的 melt 逻辑 `str(c).isdigit()` 只识别数字列名 `"1"`–`"7"`，字符串列名无法触发 melt → E1/E4/F1/F3/F4 不入库。  
2. D2 的 CSV 列名为 `"Type_Jour_Vacances_A"`，DB model 期望列名 `"Type_Jour"` → Type_Jour 字段 NULL。

**修复方案**：  
- `LocalXlsCalendarProvider.enrich()`：merge 后将字符串标签 `.map(TYPE_JOUR_VAC_LABELS)` 为整数（1–11 编码）。  
- `MEF_servjour()`：末尾添加 `.rename(columns={type_vac: "Type_Jour"})`，统一列名。  
- 同时实现 Calendar Service（`DBCalendarProvider` + `calendar_seeder.py`），以 DB 驱动替代本地 XLS。

**Day-type 整数编码**（`TYPE_JOUR_VAC_LABELS`）：  
1–7 = 学期内周一至周日；8 = 假期工作日；9 = 假期周六；10 = 假期周日；11 = 法定节假日。

**涉及文件**：  
- `backend/app/services/gtfs_core/calendar_provider.py`  
- `backend/app/services/gtfs_core/gtfs_export.py`  
- `backend/app/services/worker.py`  
- `backend/app/db/models.py`（新增 `CalendarDate`）  
- `backend/app/services/calendar_seeder.py`（新增）

**后续回归**：该问题在 commit `e7be33f`（2026-04-15）被无意回归，详见 [BUG-007](#bug-007)。

---

### BUG-007

**标题**：`e7be33f` 双路径 melt 在数字列名下误触发 label map → E1/E4/F1/F3/F4 再次为空

**状态**：✅ Resolved（2026-04-22）  
**严重度**：High（BUG-003 回归；新上传 GTFS 的 E/F 表 DB 写入 0 行，前端显示全空，F2 不受影响）  
**影响范围**：在 `e7be33f` 之后上传的所有项目（数字列 `"1"`–`"11"` 格式，当前/正常路径）

**根因**：  
commit `e7be33f` 为了兼容旧 CSV 的法语标签列（`Jeudi_Scolaire` 等）在 `_persist_results_to_db()` 的 melt 步骤加入 `.map(TYPE_JOUR_VAC_LABELS)`，但**没有区分两条路径**：

```python
pivot_cols = [c for c in df.columns if str(c).isdigit()]       # 路径 A：数字列
if not pivot_cols:
    pivot_cols = [c for c in df.columns if c in TYPE_JOUR_VAC_LABELS]  # 路径 B：法语标签
...
df = df[keep + pivot_cols].melt(...)
if df["type_jour"].dtype == object:       # ← 两条路径 melt 后都是 object 类型
    df["type_jour"] = df["type_jour"].map(TYPE_JOUR_VAC_LABELS)  # 路径 A 下 "1"/"2"/"11" 不在字典 → 全 NaN
    df = df.dropna(subset=["type_jour"])   # ← 抹掉所有行
```

路径 A（新 CSV，数字列）melt 后 `type_jour` 是 `"1"/"2"/…/"11"` 字符串，这些 key 不在 `TYPE_JOUR_VAC_LABELS` 字典（只含 `Lundi_Scolaire` 等法语标签），`.map()` 全部返回 NaN，`dropna()` 抹除所有行 → 空表写入 DB。

**为什么 F2 幸免**：`_CSV_TO_TABLE` 中 F_2 的 `id_cols=None`，跳过整个 melt 分支，CSV 原样入库。

**复现**：上传任一 GTFS ZIP 触发 pipeline，查 `result_e1_passage_ag WHERE project_id=?` 为 0 行，但磁盘 CSV 大小正常。

**修复方案**：用 `is_legacy_labels` 布尔标记区分两条路径，只在法语标签路径下执行 `.map()`：

```python
pivot_cols = [c for c in df.columns if str(c).isdigit()]
is_legacy_labels = False
if not pivot_cols:
    pivot_cols = [c for c in df.columns if c in TYPE_JOUR_VAC_LABELS]
    is_legacy_labels = True
...
if is_legacy_labels:
    df["type_jour"] = df["type_jour"].map(TYPE_JOUR_VAC_LABELS)
    df = df.dropna(subset=["type_jour"])
df["type_jour"] = df["type_jour"].astype(int)
```

**恢复历史数据**：对受影响项目跑 `python backend/repersist_project.py <project_id>`（idempotent）。

**涉及文件**：  
- `backend/app/services/worker.py`（`_persist_results_to_db`）  
- `backend/tests/test_result_persistence.py`（新增 `test_persist_melts_numeric_columns` 和 `test_persist_melts_legacy_label_columns` 回归测试，覆盖两条路径）

---

## 技术债列表

| ID | 状态 | 优先级 | 标题 | 来源 |
|----|------|--------|------|------|
| [TD-001](#td-001) | 🟡 Pending | Low | `create_engine()` 缺 `pool_pre_ping=True` | Task 2 小缺口 |
| [TD-002](#td-002) | 🟡 Pending | Low | `.env.example` 模板文件未创建 | Task 2 TODO |
| [TD-003](#td-003) | 🟡 Pending | Low | `storage.py` 缺 `delete_file()` 实现 | Task 3 TODO |
| [TD-004](#td-004) | ✅ Resolved | High | Calendar Service 缺定期自动同步（Celery Beat）；XLS 有效数据仅至 2027-12 | Calendar Service 遗留缺口 |
| [TD-005](#td-005) | 🟡 Pending | Medium | 前端 `npm run build` 因 TS strict 违规失败（5处） | Task 41 发现（Phase 1 遗留） |

---

### TD-001

**标题**：`create_engine()` 缺 `pool_pre_ping=True`

**说明**：生产稳定性参数，Supabase 切换前应补充，避免长连接超时导致查询失败。  
**位置**：`backend/app/db/database.py`  
**优先级**：Low（SQLite 开发阶段影响不大，切 Supabase 前必须修）

---

### TD-002

**标题**：`.env.example` 模板文件未创建

**说明**：只有真实 `.env` 文件（已 gitignore），缺少供新成员参考的不含真实值的模板。  
**位置**：`backend/.env.example`（待创建）  
**优先级**：Low

---

### TD-003

**标题**：`storage.py` 缺 `delete_file()` 实现

**说明**：Task 3 中标注 TODO，Task 12（存储路径租户前缀化）或项目删除清理时需要。  
**位置**：`backend/app/services/storage.py`  
**优先级**：Low（Task 12 时补充）

---

### TD-005

**标题**：前端 `npm run build` 因 TypeScript strict 违规失败（3 处，Task 45 后）

**说明**：`tsc -b tsconfig.app.json` 发现以下违规，阻止 Vite 生产构建。`npm test` 不受影响（vitest 不通过 tsc）。Task 45 已修复其中 2 项（`ResultTable.tsx` catch 绑定 + `ResultTable.test.tsx` 非法引用）。

| 文件 | 行 | 错误 | 状态 |
|------|-----|------|------|
| ~~`src/components/organisms/ResultTable.tsx`~~ | ~~36~~ | ~~`'err' is declared but its value is never read`~~ | ✅ Task 45 修复 |
| `src/pages/ProjectDetailPage.tsx` | 34 | `'isFailed' is declared but its value is never read` (`noUnusedLocals`) | 🔴 Open |
| `src/pages/ProjectListPage.tsx` | 28 | `'err' is declared but its value is never read` (`noUnusedLocals`) | 🔴 Open |
| `src/__tests__/api.test.ts` | 2 | `Module '"../api/client"' has no exported member 'getDownloadUrl'` | 🔴 Open |
| ~~`src/__tests__/ResultTable.test.tsx`~~ | ~~24~~ | ~~`Property 'getTableDownloadUrl' does not exist`~~ | ✅ Task 45 修复 |

**根因**：
- `noUnusedLocals: true` 在 `tsconfig.app.json` 中启用；Phase 1 代码存在 catch 块中未使用的 `err` 变量和未使用的状态变量。
- `getDownloadUrl` 是测试中引用但 `api/client.ts` 中从未导出的函数（Phase 1 API 重构遗留）。

**修复方案**：
- 删除未使用的 `isFailed` 变量（`ProjectDetailPage.tsx:34`）。
- 将 `catch (err)` 改为 `catch` 或 `catch (_err)`（`ProjectListPage.tsx:28`）。
- 删除 `api.test.ts` 中 `getDownloadUrl` 相关测试或在 `api/client.ts` 中补充该导出。

**涉及文件**：
- `frontend/src/pages/ProjectDetailPage.tsx`
- `frontend/src/pages/ProjectListPage.tsx`
- `frontend/src/__tests__/api.test.ts`

---

### TD-004

**标题**：Calendar Service 缺定期自动同步（Celery Beat）

**状态**：✅ Resolved（2026-04-11）

**说明**：`calendar_seeder.sync_from_api()` 已实现，但目前仅在 `calendar_dates` 表为空时触发一次（被动播种）。

**⚠️ 数据有效期截止**（经验证）：
- `Vacances_A/B/C`（学区假期）有效数据最后日期：**2026-05-17**
- `Ferie`（法定节假日）有效数据最后日期：**2027-12-25**
- XLS 文件行数覆盖至 2050-12-31，但 2026-05 / 2027-12 之后的行均为全零（无假期标记）

**影响**：处理含 2026-05 以后日期的 GTFS 文件时，假期区分析将**静默出错**——所有日期被错误归类为普通学期日（`Lundi_Scolaire` 等），Type_Jour_Vacances_A/B/C 计算结果失真，且不会有任何报错提示。

**修复**：新增 `backend/app/services/calendar_task.py`，注册 `@celery.task(name="gtfs_miner.sync_calendar")`；在 `celery_app.py` 配置 Beat 调度（每周一 03:00）。4 个测试通过（`tests/test_calendar_task.py`）。

**涉及文件**：`backend/app/celery_app.py`、`backend/app/services/calendar_task.py`（新增）、`backend/tests/test_calendar_task.py`（新增）

---

### BUG-004

**标题**：`DownloadButton.test.tsx` — 2 个测试因组件渲染 `<button>` 而非 `<a>` 元素失败

**状态**：🔴 Open  
**严重度**：Medium（前端 CI 噪音；功能本身可用，仅测试断言与实现不一致）  
**影响测试**：`frontend/src/__tests__/DownloadButton.test.tsx`  
- `renders an anchor with correct href when enabled` — `expect('BUTTON').toBe('A')` 失败  
- `anchor has download attribute` — `expect(element).toHaveAttribute("download")` 失败  
**错误信息**：
```
expected 'BUTTON' to be 'A'
```

**根因**：Task 41 重构将 `DownloadButton` 迁移至 `organisms/` 后，组件已改为渲染 shadcn `<Button>`（即 `<button>` 元素）并通过 `downloadProjectResults()` API 调用触发下载，但测试仍期望一个带 `href` 和 `download` 属性的原生 `<a>` 元素（Phase 1 旧实现）。

**修复方案**：
- 方案 A：将测试更新为匹配当前 `<button>` 渲染与 `onClick` 行为（推荐）。
- 方案 B：将 `DownloadButton` 改回 `<a asChild>` 模式（shadcn Button + `asChild` + `<a href>`），使原生下载属性可用。

**涉及文件**：`frontend/src/__tests__/DownloadButton.test.tsx`

---

### BUG-005

**标题**：`useAuth.test.ts` — 6 个测试因 `useAuthContext must be used within AuthProvider` 失败

**状态**：🔴 Open  
**严重度**：Medium（auth hook 单元测试完全失效）  
**影响测试**：`frontend/src/__tests__/useAuth.test.ts`（全部 6 个测试）  
**错误信息**：
```
Error: useAuthContext must be used within AuthProvider
```

**根因**：Task 42/43 重构将 auth 逻辑从独立 hook 迁移至 `AuthProvider` context。`useAuth.test.ts` 直接调用 `useAuth()` 或 `useAuthContext()` hook，但测试中没有将组件包裹在 `<AuthProvider>` 中，导致 context 读取失败。

**修复方案**：在测试的 `render` 调用中添加 `<AuthProvider>` 包裹，或使用 Testing Library 的 `wrapper` 选项注入 provider。

**涉及文件**：`frontend/src/__tests__/useAuth.test.ts`

---

### BUG-006

**标题**：`App.test.tsx` — 4 个路由测试在 Task 42 AppShell 重构后失败

**状态**：🔴 Open  
**严重度**：Medium（App 级集成测试回归）  
**影响测试**：`frontend/src/__tests__/App.test.tsx`  
- `test_redirects_to_login_if_unauthenticated`  
- `test_shows_project_list_when_authenticated`  
- `test_navigates_to_project_detail`  
- `test_new_project_flow`  
**根因**：Task 42 将 App.tsx 中的内联 header 替换为 `<AppShell>`，并引入 `<AuthProvider>` 包裹结构变化。测试使用旧的 mock/render 方式未适配新组件树（例如 AppShell 期望 auth context，或路由匹配因 layout wrapper 层级改变而失效）。

**修复方案**：更新 `App.test.tsx` 的 render helper，在测试包裹器中注入 `<AuthProvider>` + `<MemoryRouter>`，并按新路由结构调整 mock。

**涉及文件**：`frontend/src/__tests__/App.test.tsx`
