# Bug & 技术债追踪表

**维护规则**：每次运行 pytest 发现失败时，Claude 自动将新 bug 追加至本文件（见 CLAUDE.md §Bug 追踪）。

---

## Bug 列表

| ID | 状态 | 严重度 | 标题 | 首次发现 |
|----|------|--------|------|---------|
| [BUG-001](#bug-001) | ✅ Resolved | High | `test_websocket` — `client_authed` auth bypass 被 function-scoped fixture 清除 → 401 | 2026-04-11 |
| [BUG-002](#bug-002) | ✅ Resolved | Medium | `test_upload_and_wait` — pipeline 完成但 output 目录不存在 | 2026-04-11 |

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

## 技术债列表

| ID | 状态 | 优先级 | 标题 | 来源 |
|----|------|--------|------|------|
| [TD-001](#td-001) | 🟡 Pending | Low | `create_engine()` 缺 `pool_pre_ping=True` | Task 2 小缺口 |
| [TD-002](#td-002) | 🟡 Pending | Low | `.env.example` 模板文件未创建 | Task 2 TODO |
| [TD-003](#td-003) | 🟡 Pending | Low | `storage.py` 缺 `delete_file()` 实现 | Task 3 TODO |

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
