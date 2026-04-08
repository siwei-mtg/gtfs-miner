# Phase 0 TDD 任务拆解计划

**版本**：1.5
**日期**：2026-04-07
**状态**：后端全部完成（Sprint 1+2），前端全部完成（Sprint 3+4）

---

## Context

Phase 0 目标（PRD §9）：**端到端流程可演示** — 上传 GTFS ZIP → 异步处理 → WebSocket 实时进度 → 下载结果 ZIP + 最简前端。**不含**认证、多租户、在线表格、地图。

### 当前进度

| 模块 | 完成度 | 说明 |
|------|--------|------|
| FastAPI 脚手架 | **100%** | CORS、路由、WebSocket 已就绪 |
| 项目 CRUD API | **100%** | create / list / get 均已实现 |
| GTFS 上传 API | **100%** | 接收 ZIP → 存 temp → 触发 BackgroundTask |
| Worker 管线 | **100%** | 7 步管线 → 15 个 CSV → WebSocket 进度推送 |
| 下载 API | **100%** | ZIP 打包已实现，7 个测试（happy-path + 5 error-cases）全部通过 |
| 前端 | **100%** | Task 9–16 全部完成，37 个测试 0 错误 |
| 测试基础设施 | **100%** | conftest StaticPool 修复（in-memory 跨 session 可见性），18 个测试 0 错误 |

### 关键文件清单

- `backend/app/api/endpoints/projects.py` — 下载端点 stub（L95-100）
- `backend/app/services/worker.py` — 已完成的 Worker 管线
- `backend/app/api/websockets/progress.py` — WebSocket 连接管理器
- `backend/app/core/config.py` — `PROJECT_DIR` 路径定义
- `backend/app/db/models.py` — `Project` 模型
- `backend/app/schemas/project.py` — Pydantic schemas
- `backend/tests/test_api_pipeline_integration.py` — 现有 E2E 测试
- `frontend/vite.config.ts` — 需添加 proxy
- `frontend/src/App.tsx` — 需替换为应用代码

---

## GROUP A：后端测试基础设施（Task 1–2）

### Task 1：pytest 配置 + conftest 共享 fixtures ✅

**目标**：建立测试隔离和共享 fixture 基础。

**创建文件**：
- `backend/pytest.ini` — 配置 `testpaths = tests`，`norecursedirs = tests/integration`
- `backend/tests/conftest.py` — 共享 fixtures：
  - `test_engine`：内存 SQLite（`sqlite:///:memory:`）
  - `test_db`：创建表 → yield session → rollback
  - `client`：覆盖 `get_db` 依赖，返回 `TestClient(app)`
  - `GTFS_ZIP` 路径常量、`EXPECTED_CSVS` 列表常量

**执行结果**（2026-04-04）：
- `pytest --collect-only` 成功收集 4 个测试（`test_api_pipeline_integration.py`），conftest fixtures 正常发现
- `norecursedirs = tests/integration` 已排除 QGIS 遗留测试（需要 `qgis` 模块）
- **已知问题**：`test_gtfs_core.py`、`test_gtfs_norm.py`、`test_gtfs_pipeline.py` 使用 `from backend.app...` 绝对路径导入，在 `backend/` 目录下运行时失败 → **Task 2 修复**

**验证方式**：`pytest --collect-only` 确认 fixture 发现正常。✅

---

### Task 2：重构现有集成测试使用共享 fixtures ✅

**修改文件**：`backend/tests/test_api_pipeline_integration.py`
- 删除内联 `client` fixture 和 `sys.path` 操作
- 改用 conftest 中的共享 fixtures（`GTFS_ZIP`、`EXPECTED_CSVS`、`client`）

**同步修复（Task 1 遗留问题）**：
- `conftest.py`：`client` fixture 改为 session-scoped、使用真实 SQLite DB（`real_engine`）；新增 `isolated_client`（in-memory，供 Task 3+ 的 download 测试使用）
- `test_gtfs_core.py`：`from backend.app…` → `from app…`
- `test_gtfs_norm.py`：`from backend.app…` → `from app…`；硬编码路径 → `Path(__file__).parent / …`
- `test_gtfs_pipeline.py`：同上

**设计决策**：集成测试的 `client` 必须使用真实 DB，因为 Worker（`worker.py:19`）通过 `SessionLocal` 直接访问 DB，无法被 `get_db` 依赖覆写所影响。

**执行结果**（2026-04-04）：
- `pytest --collect-only` → **11 tests collected，0 errors** ✅
- `test_gtfs_zip_exists`、`test_create_project` → **PASSED** ✅
- `test_gtfs_core.py` 全部 5 个单元测试 → **PASSED** ✅
- `test_upload_and_wait`、`test_get_project_list`（含完整管线，耗时数分钟）已验证 fixtures 正确联通，待完整运行

**依赖**：Task 1

---

## GROUP B：后端下载端点（Task 3–6）

### Task 3：下载端点 happy-path 测试（先写测试）✅

**创建文件**：`backend/tests/test_download.py`

**测试用例**：
1. `test_download_completed_project` — 手动在 output 目录放入 15 个 dummy CSV → `GET .../download` → 断言：
   - HTTP 200
   - Content-Type 为 `application/zip`
   - ZIP 内含 15 个文件，名称匹配 `EXPECTED_CSVS`
   - 每个文件非空
2. `test_download_filename` — `Content-Disposition` 包含 `filename="gtfs_results_{project_id}.zip"`

**设计要点**：不运行管线，直接写入 dummy CSV → 快速（亚秒级）。

**执行结果**（2026-04-04）：测试编写后立即红 → 实现后绿 ✅

**依赖**：Task 1

---

### Task 4：下载端点 error-case 测试（先写测试）✅

**追加到**：`backend/tests/test_download.py`

**测试用例**：
1. `test_download_nonexistent_project` — 随机 UUID → 404
2. `test_download_pending_project` — status=pending → 400
3. `test_download_processing_project` — status=processing → 400
4. `test_download_failed_project` — status=failed → 400
5. `test_download_no_output_dir` — status=completed 但无 output 目录 → 404

**执行结果**（2026-04-04）：5 个 error-case 均通过 ✅

**依赖**：Task 3

---

### Task 5：实现 ZIP 打包逻辑 ✅

**实现**：在 `projects.py` 的 download 端点中使用 `zipfile.ZipFile` + `io.BytesIO` 内存打包 output 目录下所有 CSV。

**方案**：逻辑较轻（<15 行），直接内联在端点函数中，不额外建 packaging 模块。

**依赖**：Task 3–4（测试已存在且失败中）

---

### Task 6：实现下载端点 ✅

**修改文件**：`backend/app/api/endpoints/projects.py`（原 L95-100 stub → 完整实现）

**新增 imports**：`StreamingResponse`, `io`, `zipfile`, `PROJECT_DIR`

**实现逻辑**：
1. 校验 project 存在（404）
2. 校验 status == "completed"（400）
3. 校验 output 目录存在（404）
4. `zipfile.ZipFile(BytesIO)` 打包所有 `*.csv`
5. 返回 `StreamingResponse(media_type="application/zip")` + `Content-Disposition` header

**附加修复（conftest）**：`test_engine` 增加 `poolclass=StaticPool`，解决 SQLite in-memory 多 session 不共享同一连接导致 `no such table` 的问题。

**执行结果**（2026-04-04）：
- `pytest tests/test_download.py -v` → **7 passed in 0.27s** ✅
- `pytest tests/test_api_pipeline_integration.py tests/test_gtfs_core.py -v` → **9 passed in 17s**（无回归）✅

**依赖**：Task 5

---

## GROUP C：后端 WebSocket 与 E2E 验证（Task 7–8）

### Task 7：WebSocket 集成测试 ✅

**创建文件**：`backend/tests/test_websocket.py`

**测试用例**：
1. `test_websocket_receives_progress_messages` — 使用小数据集 `gtfs-20240704-090655.zip`(55KB)：
   - 创建项目 → 连接 WebSocket → 上传 ZIP（后台线程 0.3s 延迟）→ 收集消息至 `status == "completed"`
   - 断言：至少 7 条 step 消息、最后一条 status=completed、每条包含 `project_id` / `step` / `time_elapsed`

**技术实现**：上传在 `threading.Thread(daemon=True)` 中执行，主线程维持 WebSocket 连接并接收消息；TestClient 的 ASGI 服务器在独立线程运行，支持 HTTP + WS 并发。标记为 `@pytest.mark.slow`（已在 pytest.ini 注册）。

**执行结果**（2026-04-04）：**PASSED** ✅

**依赖**：Task 1

---

### Task 8：完整 E2E 测试（含下载）✅

**修改文件**：`backend/tests/test_api_pipeline_integration.py`（新增 `test_full_e2e_upload_process_download`）

**测试用例**：
1. `test_full_e2e_upload_process_download` — 创建 → 上传 → 轮询至 completed → `GET /download` → 验证 ZIP 内 15 个 CSV 非空且分号分隔

**执行结果**（2026-04-04）：**PASSED** ✅ 总计 18 tests passed in 47s（含 Task 7 WebSocket 测试）

**依赖**：Task 2、Task 6

---

## GROUP D：前端（Task 9–16）

> 可与 GROUP A/B/C **并行开发**。

### Task 9：Vite 代理 + 测试运行器 ✅

**修改文件**：
- `frontend/vite.config.ts` — 改用 `vitest/config` 的 `defineConfig`，添加 `server.proxy`（`/api` → `http://localhost:8000`，`ws: true`）并内联 `test` 配置（`environment: jsdom`、`setupFiles`、`globals: true`）
- `frontend/package.json` — 新增 devDeps：`vitest`、`@testing-library/react`、`@testing-library/jest-dom`、`@testing-library/user-event`、`jsdom`；新增 `"test": "vitest run"`、`"test:watch": "vitest"` 脚本

**创建文件**：
- `frontend/src/__tests__/smoke.test.ts` — `1 + 1 === 2` 冒烟测试（1 个测试）
- `frontend/src/__tests__/setup.ts` — `@testing-library/jest-dom` 的 matchers 注册文件

**设计决策**：vitest 配置直接内联在 `vite.config.ts`（改用 `vitest/config` 导出）而非单独的 `vitest.config.ts`，避免两套配置文件冲突。

**执行结果**（2026-04-07）：`npm run test` → **1 passed** ✅

**依赖**：无

---

### Task 10：TypeScript 类型定义 ✅

**创建文件**：`frontend/src/types/api.ts`
- `ProjectStatus = 'pending' | 'uploading' | 'processing' | 'completed' | 'failed'`
- `ProjectCreate`（6 个参数字段：`hpm_debut`、`hpm_fin`、`hps_debut`、`hps_fin`、`vacances`、`pays`）
- `ProjectResponse`（含 `id`、`status`、`created_at`、`updated_at`、`parameters`、`error_message`）
- `WebSocketMessage`（含 `project_id`、`status`、`step`、`time_elapsed`、`error`）
- `UploadResponse`（`msg`、`project_id`）

**执行结果**（2026-04-07）：`tsc --noEmit` 编译通过，被后续所有模块正确引用 ✅

**依赖**：Task 9

---

### Task 11：API client 模块 ✅

**创建文件**：
- `frontend/src/api/client.ts` — 4 个函数：`createProject()`（POST JSON）、`uploadGtfs()`（POST FormData）、`getProject()`（GET）、`getDownloadUrl()`（纯 URL 构造，返回 string 而非 Promise）
- `frontend/src/__tests__/api.test.ts` — 6 个测试：mock `fetch`（`vi.spyOn(globalThis, 'fetch')`）验证方法、URL、请求体、错误抛出

**执行结果**（2026-04-07）：`npm run test` → **6 passed** ✅

**依赖**：Task 10

---

### Task 12：WebSocket hook ✅

**创建文件**：
- `frontend/src/hooks/useProjectProgress.ts` — `useProjectProgress(projectId: string | null)` 返回 `{ messages, latestStatus, isConnected }`；`useEffect` 依赖 `projectId`，切换时先重置三个状态再重连（修复 commit c0e126e 中的状态残留 bug）
- `frontend/src/__tests__/useProjectProgress.test.ts` — 6 个测试：手写 `MockWebSocket` 类（含 `trigger()` 辅助方法），验证：null 时不连接、URL 正确、open/close 状态切换、消息追加与 latestStatus 更新、unmount 时关闭连接、projectId 变更时重连

**执行结果**（2026-04-07）：**6 passed** ✅

**依赖**：Task 10

---

### Task 13：上传组件 ✅

**创建文件**：
- `frontend/src/components/UploadForm.tsx` — 受控表单：文件选择（`.zip`）+ 6 个参数时间/文本输入（预填默认值）+ 提交；按钮在无文件或 `isLoading` 时禁用；错误信息通过 `role="alert"` 段落展示
- `frontend/src/__tests__/UploadForm.test.tsx` — 8 个测试：渲染、无文件时禁用、`isLoading` 时禁用、选文件后启用、提交回调携带 file 与 params、加载文本切换、错误显示、禁用时点击不触发回调

**执行结果**（2026-04-07）：**8 passed** ✅

**依赖**：Task 11

---

### Task 14：进度展示组件 ✅

**创建文件**：
- `frontend/src/components/ProgressPanel.tsx` — 纯展示组件：`messages` 为空时显示等待提示；非空时渲染 7 步有序列表（用正则 `/^\[(\d)\/7\]/` 解析步骤编号，已完成步骤显示 `✓`）+ 末条消息的耗时 + 状态（completed/failed/processing 三种样式）
- `frontend/src/__tests__/ProgressPanel.test.tsx` — 7 个测试：空消息等待态、7 个列表项、步骤全文展示、耗时数值、completed/failed/processing 各状态

**设计**：纯展示组件，props 接收 `messages: WebSocketMessage[]`，无内部副作用。

**执行结果**（2026-04-07）：**7 passed** ✅

**依赖**：Task 10

---

### Task 15：下载按钮组件 ✅

**创建文件**：
- `frontend/src/components/DownloadButton.tsx` — `projectId` 为 null 或 `disabled=true` 时渲染 `<button disabled>`；否则渲染 `<a href="..." download role="button">`（两者均带 `aria-label="download-button"`）
- `frontend/src/__tests__/DownloadButton.test.tsx` — 4 个测试：null 时禁用、disabled prop 禁用、启用时为 `<a>` 且 href 正确、有 `download` attribute

**执行结果**（2026-04-07）：**4 passed** ✅

**依赖**：Task 11

---

### Task 16：App 组合 — 串联全部组件 ✅

**修改文件**：
- `frontend/src/App.tsx` — 状态机 `AppPhase = 'idle' | 'uploading' | 'active'`：`idle/uploading` 阶段显示 `<UploadForm>`；`active` 阶段显示 `<ProgressPanel>` + `<DownloadButton>`（仅 completed 时启用）+ "Nouveau traitement" 重置按钮（completed 或 failed 后出现）；WebSocket 仅在 `active` 阶段激活（`phase === 'active' ? projectId : null`）
- `frontend/src/App.css` — 最简样式
- `frontend/src/__tests__/App.test.tsx` — 5 个测试：初始态显示上传表单、上传成功后切换到进度面板、处理中下载按钮禁用、completed 后下载按钮启用且 href 正确、API 失败时显示错误并返回 idle；通过 `vi.spyOn` mock `client` 和 `useProjectProgress`

**执行结果**（2026-04-07）：**5 passed** ✅
- `npm run test` → **37 passed in 6.8s**（7 test files，0 errors）✅

**依赖**：Task 13、14、15

---

## 依赖关系与执行顺序

```
GROUP A (后端测试基础)        GROUP D (前端) — 可与 A/B/C 并行
  Task 1 → Task 2              Task 9 → Task 10 → Task 11 → Task 13 ─┐
    │                                       │ → Task 12               │
    ├→ Task 3 → Task 4                      │ → Task 14               ├→ Task 16
    │    └→ Task 5 → Task 6                 └→ Task 15 ───────────────┘
    │              │
    ├→ Task 7      │
    └→ Task 2 ─────┴→ Task 8
```

**推荐执行批次**：
1. **Sprint 1**：Task 1 → 2 → 3 → 4 → 5 → 6（后端下载闭环）
2. **Sprint 2**：Task 7 → 8（后端验证闭环）
3. **Sprint 3**：Task 9 → 10 → 11 → 12（前端基础，可与 Sprint 1 并行）
4. **Sprint 4**：Task 13 + 14 + 15（可并行）→ 16（前端闭环）

---

## 验证：Phase 0 完成标准

Phase 0 演示流程（PRD §10）：

> 技术团队完成一次端到端处理演示（上传→处理→下载）

**端到端验收测试**：
1. `pytest backend/tests/ -v` — 全部通过（含 Task 3/4/7/8 的新测试）
2. `cd frontend && npm run test` — 全部通过
3. 手动演示：启动 `uvicorn` + `npm run dev` → 浏览器打开前端 → 上传 GTFS ZIP → 观察 7 步进度 → 下载结果 ZIP → 解压验证 15 个 CSV 文件存在且内容正确
