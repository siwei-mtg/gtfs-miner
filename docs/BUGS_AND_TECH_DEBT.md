# Bug & 技术债追踪表

**维护规则**：每次运行 pytest 发现失败时，Claude 自动将新 bug 追加至本文件（见 CLAUDE.md §Bug 追踪）。

---

## Bug 列表

| ID | 状态 | 严重度 | 标题 | 首次发现 |
|----|------|--------|------|---------|
| [BUG-001](#bug-001) | ✅ Resolved | High | `test_websocket` — `client_authed` auth bypass 被 function-scoped fixture 清除 → 401 | 2026-04-11 |
| [BUG-002](#bug-002) | ✅ Resolved | Medium | `test_upload_and_wait` — pipeline 完成但 output 目录不存在 | 2026-04-11 |
| [BUG-003](#bug-003) | ✅ Resolved | High | 假期区分析时 D2/E1/E4/F1/F3/F4 结果表全部为空 | 2026-04-11 |

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

---

## 技术债列表

| ID | 状态 | 优先级 | 标题 | 来源 |
|----|------|--------|------|------|
| [TD-001](#td-001) | 🟡 Pending | Low | `create_engine()` 缺 `pool_pre_ping=True` | Task 2 小缺口 |
| [TD-002](#td-002) | 🟡 Pending | Low | `.env.example` 模板文件未创建 | Task 2 TODO |
| [TD-003](#td-003) | 🟡 Pending | Low | `storage.py` 缺 `delete_file()` 实现 | Task 3 TODO |
| [TD-004](#td-004) | ✅ Resolved | High | Calendar Service 缺定期自动同步（Celery Beat）；XLS 有效数据仅至 2027-12 | Calendar Service 遗留缺口 |

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
