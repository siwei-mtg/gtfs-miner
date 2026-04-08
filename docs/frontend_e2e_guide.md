# 前端全流程梳理：端到端运行 + Human-in-the-Loop 节点

> 最后更新：2026-04-07 | 适用阶段：Phase 0 MVP | 分支：`feat/web-app-scaffold`

## 背景

前端为 **React 19 + Vite + TypeScript** 的单页应用，零运行时依赖（仅 React）。本文档梳理前端独立跑通、前后端全部联调的完整流程，以及需要人类介入的决策节点。后端流程见 `docs/backend_e2e_guide.md`。

---

## 一、前端"独立跑通"的完整流程

### 第 0 步：安装依赖与启动开发服务器

```bash
cd frontend
npm install
npm run dev    # Vite dev server → http://localhost:5173
```

启动后自动完成：
- 热模块替换（HMR）就绪
- **Vite 代理激活**：所有 `/api/*` HTTP 请求转发至 `http://localhost:8000`
- WebSocket 同样被代理（`vite.config.ts` 中 `ws: true`）

> **注意**：代理仅在 `npm run dev` 模式下生效；生产构建（`dist/`）需由 Nginx/反向代理独立配置。

### 第 1 步：跑单元测试（无需后端）

```bash
npm run test          # 一次性运行，CI 使用
npm run test:watch    # 监听模式，本地开发使用
```

测试套件覆盖（全部使用 `vi.mock` 隔离网络，无真实 HTTP/WS 请求）：

| 文件 | 测试数 | 覆盖内容 |
|------|--------|---------|
| `App.test.tsx` | 5 | 状态机转换、上传成功/失败、下载按钮启用条件 |
| `UploadForm.test.tsx` | 8 | 表单渲染、禁用逻辑、提交回调、错误展示 |
| `ProgressPanel.test.tsx` | 7 | 7 步骤渲染、状态文本、耗时显示 |
| `DownloadButton.test.tsx` | 4 | 禁用/启用态、href 正确性、download 属性 |
| `useProjectProgress.test.ts` | 6 | WS 连接/断开、消息追加、unmount 清理、重连 |
| `api.test.ts` | 6 | 5 个 API 函数的 endpoint/payload/错误处理 |
| `smoke.test.ts` | 1 | 环境健康检查 |

### 第 2 步：构建生产产物

```bash
npm run build    # tsc --noEmit（类型检查）+ vite build → dist/
npm run lint     # ESLint 静态分析
```

构建产物位于 `frontend/dist/`，可部署至任意静态文件服务器。

---

## 二、前后端"全部跑通"的完整流程

### 第 0 步：启动两个服务

**终端 1（后端）：**

```bash
cd backend
gtfs\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

**终端 2（前端）：**

```bash
cd frontend
npm run dev
```

就绪标志：
- 后端：`http://localhost:8000/docs` 可访问
- 前端：`http://localhost:5173` 可访问，控制台无红色报错

### 第 1 步：配置参数 + 选择文件（人类操作）

打开 `http://localhost:5173`，页面显示 `UploadForm`，填写：

| 字段 | 默认值 | 说明 |
|------|--------|------|
| Heure de pointe matin — début | `07:00` | 早高峰起始 |
| Heure de pointe matin — fin | `09:00` | 早高峰结束 |
| Heure de pointe soir — début | `17:00` | 晚高峰起始 |
| Heure de pointe soir — fin | `19:30` | 晚高峰结束 |
| Vacances | `A` | 假期区域（A / B / C / 全部） |
| Pays | `法国` | 国家代码 |
| Fichier GTFS (.zip) | — | **必填**，选择 GTFS ZIP 文件 |

> 测试文件位于 `backend/tests/Resources/raw/`（SEM、SOLEA、ginko 三个最小样本）。

### 第 2 步：触发处理（人类操作）

点击 **"Lancer le traitement"**，按钮在以下情况禁用：未选文件 或 正在上传。

点击后前端依次执行：

```
1. phase: 'idle' → 'uploading'
   ↓
2. POST /api/v1/projects/
   Body: { hpm_debut, hpm_fin, hps_debut, hps_fin, vacances, pays }
   → 返回 { id: "uuid-xxx", status: "pending", ... }
   ↓
3. POST /api/v1/projects/{id}/upload
   Body: FormData { file: gtfs.zip }
   → 返回 { msg: "...", project_id: "uuid-xxx" }
   ↓
4. phase: 'uploading' → 'active'
   projectId 存入状态
   ↓
5. useProjectProgress hook 建立 WebSocket 连接
   ws://localhost:5173/api/v1/projects/{id}/ws
   （由 Vite 代理转发至 ws://localhost:8000）
```

**若第 2 或第 3 步失败：**
- `phase` 回退至 `'idle'`，表单重新显示
- 错误信息以红色 `<p role="alert">` 展示在表单上方

### 第 3 步：自动处理 — 实时进度观察（无需人工干预）

`ProgressPanel` 通过 WebSocket 实时接收后端推送的 7 步进度：

```json
{
  "project_id": "uuid-xxx",
  "status": "processing",
  "step": "[3/7] 空间聚类生成站点映射（1234 停靠站，56 线路，789 班次）",
  "time_elapsed": 12.34,
  "error": null
}
```

面板展示逻辑：
- 每条消息追加至 `messages[]`
- 解析 `[N/7]` 提取步骤编号，已完成步骤标 ✓，未完成标 ○
- 显示最新消息的耗时（秒）
- 状态文字：`En cours…` / `Terminé` / `Échec — {error}`

### 第 4 步：下载结果（人类操作）

`latestStatus === 'completed'` 时，**"Télécharger les résultats"** 按钮变为可点击的 `<a>` 链接：

```
GET /api/v1/projects/{id}/download
→ 返回包含 16 个 CSV 文件的 ZIP 包
```

点击后浏览器直接触发文件下载（`download` 属性）。

下载完成后，点击 **"Nouveau traitement"** 回到初始状态，开始新一次处理。

**全部跑通的标志：** 浏览器下载得到包含 16 个 CSV 文件的 ZIP 包。

---

## 三、应用状态机

```
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                                                                         │
 │   idle ──[点击提交]──→ uploading ──[createProject + uploadGtfs 成功]──→ active
 │    ↑                       │                                              │
 │    └──────[API 报错]────────┘               [completed 或 failed 后]      │
 │                                              点击"Nouveau traitement" ────┘
 │                                                                         │
 └─────────────────────────────────────────────────────────────────────────┘
```

| Phase | 渲染内容 | WebSocket |
|-------|---------|-----------|
| `idle` | UploadForm（isLoading=false） | 未连接 |
| `uploading` | UploadForm（isLoading=true，按钮禁用） | 未连接 |
| `active` | ProgressPanel + DownloadButton + 重置按钮 | 已连接 |

---

## 四、Human-in-the-Loop 节点分析

### 当前 Phase 0 的流程图

```
 ┌──────────────────┐     ┌───────────────────┐     ┌───────────────────┐     ┌──────────────┐
 │  填写参数 + 选文件 │ ──→ │  点击"Lancer"      │ ──→ │  观察实时进度      │ ──→ │  点击下载    │
 │  (UploadForm)    │     │  (handleSubmit)    │     │  (ProgressPanel)  │     │ (DownloadBtn)│
 └──────────────────┘     └───────────────────┘     └───────────────────┘     └──────────────┘
          ↑                         │                         │
          │                         ↓ API 失败时               ↓ status=failed 时
          │                  ┌──────────────┐          ┌──────────────────┐
          └──────────────────│  显示错误信息  │          │  查看错误消息     │
                             │  重新填写上传  │          │  点击重置后重试   │
                             └──────────────┘          └──────────────────┘
```

**结论：当前只有 3 个人类节点：**

| # | 节点 | 人类做什么 | 对应组件 / API |
|---|------|-----------|--------------|
| 1 | **配置参数 + 选文件** | 设定高峰时段、假期区域，选择 GTFS ZIP | `UploadForm` |
| 2 | **触发处理** | 点击提交按钮 | `App.handleSubmit` → `POST /projects/` + `POST /upload` |
| 3 | **获取结果** | 等待 completed 后点击下载，或失败时排查错误 | `DownloadButton` → `GET /download` |

### PRD 规划但尚未实现的 HITL 节点

| 缺失节点 | PRD 阶段 | 当前状态 |
|----------|---------|---------|
| **用户认证 / 登录页** | Phase 1 | 无 auth，任何人可访问 |
| **数据源地图点选**（替代手动上传） | Phase 1 Pro | 前后端均无此功能 |
| **在线浏览结果表格** | Phase 1 | 后端 `get_table_data` 是空 stub，前端无对应页面 |
| **地图可视化查看** | Phase 2 | 未规划 |
| **参数高级配置**（聚类阈值等） | Phase 3+ | 硬编码在后端常量，前端无入口 |

---

## 五、关键源文件索引

| 组件 | 文件路径 | 职责 |
|------|---------|------|
| 入口 | `frontend/src/main.tsx` | React 挂载至 `#root` |
| 主状态机 | `frontend/src/App.tsx` | phase 管理、handleSubmit、组件编排 |
| 表单 | `frontend/src/components/UploadForm.tsx` | 参数输入 + 文件选择 + 提交 |
| 进度面板 | `frontend/src/components/ProgressPanel.tsx` | 7 步骤渲染、状态文字、耗时显示 |
| 下载按钮 | `frontend/src/components/DownloadButton.tsx` | href 指向后端下载端点 |
| WS Hook | `frontend/src/hooks/useProjectProgress.ts` | WebSocket 生命周期管理（连接/消息/清理） |
| API Client | `frontend/src/api/client.ts` | 5 个 API 调用封装（createProject / uploadGtfs / getProject / getDownloadUrl） |
| 类型定义 | `frontend/src/types/api.ts` | `ProjectStatus`、`WebSocketMessage`、`ProjectCreate` 等 |
| 代理配置 | `frontend/vite.config.ts` | `/api/*` → `:8000`，`ws: true` |
| 样式 | `frontend/src/App.css` | 主容器、表单、按钮、进度列表样式 |

---

## 六、已知问题与风险

| # | 问题 | 影响 | 严重度 |
|---|------|------|--------|
| 1 | 无 WebSocket 断线重连机制 | WS 意外断开后进度停更，需手动刷新页面 | 中 |
| 2 | 无文件上传进度条 | 大 GTFS 文件上传时 UI 无反馈，仅按钮禁用 | 低 |
| 3 | `pays` 字段存中文 `"法国"` | 若后端增加枚举校验可能失败（当前后端不校验） | 低 |
| 4 | `getProject`（轮询）已实现但未使用 | 仅依赖 WS；WS 断开时无 HTTP 轮询降级 | 低 |
| 5 | 无用户认证 | 任何人可访问前端并触发处理 | 高（生产前必须解决） |
| 6 | CORS 全开（后端侧） | 仅限开发环境使用 | 低（开发阶段） |
