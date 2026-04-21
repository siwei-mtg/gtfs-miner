# 看板重构计划 — GTFS Miner Tableau de bord

> **作者**：Wei SI / Claude
> **日期**：2026-04-20
> **状态**：📋 待执行
> **关联**：PRD v0.9 §9 Phase 2.5、F-08 数据看板
> **原始计划文件**：`C:\Users\wei.si\.claude\plans\tableau-de-bord-tableau-de-hazy-forest.md`

---

## 背景

当前 `DashboardPage`（`/projects/:id/dashboard`）采用三栏网格（地图 | 2×2 图表 | 表格 tab 切换），但未能真正承担"项目分析主界面"的角色。用户需求：

- **把看板变成项目的分析主入口**：从项目清单页点击已完成的项目时，默认跳转到看板页；`ProjectDetailPage` 保留为**管理页**（状态、重跑 pipeline、重命名、GeoPackage 生成）
- **重新组织为一屏自适应三栏**：左侧边栏（15 张结果表的清单，点击弹窗访问）/ 中间地图 / 右侧 KPI + 可交互图表
- **用"点击图表筛选"替代"下拉菜单选筛选"**：移除 Header 里的 `jour_type` 下拉，改为点击柱状图的某根柱直接触发联动筛选 —— 与现有地图/表格的点击筛选范式统一
- **当前阶段移除 `PlanGate`**：所有注册用户统一按 Pro 对待。`PlanGate` 组件保留，供未来差异化使用

目标产出：一个高密度、探索型的分析页面。**所有筛选维度都用可视元素暴露**，15 张结果表始终一键可达但不污染主视图。

---

## 已锁定的产品决策

| # | 决策 |
|---|------|
| 1 | 项目列表点击 `status='completed'` 的项目 → 重定向 `/projects/:id/dashboard`；否则 → `/projects/:id` |
| 2 | `ProjectDetailPage` = 管理页（状态、重命名、重跑、GeoPackage）。"Tableau de bord" 按钮在 pipeline 未完成时置灰 |
| 3 | 看板 Header：`[← Projets] [项目名] · [🔄 重置筛选 (N)] · [⚙️ 管理] · [📥 导出 ▾] · [用户]`。**不再有 jour_type 下拉** |
| 4 | 左侧边栏：**15 张表**按字母分组（A/B/C/D/E/F），双行排版 `编码加粗 + 全称灰字`。有筛选的表名后面显示漏斗图标 |
| 5 | 中间：复用现有 `MapView`，**移除** `<PlanGate>` 包裹 |
| 6 | 右侧面板：4 张 KPI 卡片（2×2）+ 2 张可点击图表 |
| 7 | 表格弹窗：**同时只能打开一个**，宽度约 75%，筛选参与 `useDashboardSync`，关闭后状态保留 |
| 8 | Header "重置筛选" 按钮 + 徽标（显示当前激活筛选维度数） |
| 9 | 全量导出：Header 下拉（GeoPackage / CSV zip）。单表导出：对应表格弹窗内的按钮 |

---

## 目标布局

```
┌────────────────────────────────────────────────────────────────────────┐
│ ← Projets │ 项目 X │ 🔄 重置 (3) │ ⚙️ │ 📥 导出 ▾ │ user            │
├─────────────┬──────────────────────────────────────┬───────────────────┤
│ 左侧边栏    │                                      │ KPI  │ KPI       │
│ A · Agrégats│                                      ├──────┼───────────┤
│   A_0 …     │                                      │ KPI  │ KPI       │
│   A_1 …     │             MapView                  ├──────┴───────────┤
│ B · Lignes  │       (E_1 AG + E_4 弧段)            │ Courses par      │
│   B_1 … 🔽  │                                      │ jour_type（柱图）│
│   B_2 …     │                                      ├──────────────────┤
│ … (15 张)   │                                      │ Courses par      │
│             │                                      │ heure (24 根柱)  │
└─────────────┴──────────────────────────────────────┴───────────────────┘
```

**尺寸目标（≥ 1280px）**：左栏 260px · 地图自适应 · 右栏 380px。视口高度 100vh，除左栏和弹窗外，任何区域都不单独滚动。

**响应式**（移动端延后，stretch goal）：
- ≥ 1280px：完整三栏
- 768–1279px：左栏折叠为抽屉（汉堡图标），地图 + 右栏水平堆叠
- < 768px：垂直堆叠，tab 切换 [地图 / 表格 / 图表]，左栏为抽屉

---

## 组件架构（Atomic Design）

### 新增组件

| 文件 | 层级 | 作用 |
|------|------|------|
| `frontend/src/components/templates/DashboardLayout.tsx` | template | 三栏骨架，响应式，零业务逻辑 |
| `frontend/src/components/organisms/TableListSidebar.tsx` | organism | 左栏渲染：15 张表分组 + 漏斗图标 + 点击 → 打开弹窗 |
| `frontend/src/components/organisms/DashboardRightPanel.tsx` | organism | 右栏组装（KPI + 2 图表） |
| `frontend/src/components/organisms/CoursesByJourTypeChart.tsx` | organism | 可点击柱图；点击 → dispatch `SET_JOUR_TYPE` |
| `frontend/src/components/organisms/CoursesByHourChart.tsx` | organism | 24 根柱；点击 → dispatch `TOGGLE_HOUR` |
| `frontend/src/components/organisms/TablePopup.tsx` | organism | Sheet / Drawer（宽度 75vw），内含 `ResultTable` |
| `frontend/src/components/molecules/KpiCard.tsx` | molecule | KPI 卡片：label + 数值 + 图标；支持 skeleton 加载态 |
| `frontend/src/components/molecules/TableSidebarItem.tsx` | molecule | 左栏条目：粗体编码 + 灰字全称 + 条件漏斗 |
| `frontend/src/components/molecules/TableGroupHeader.tsx` | molecule | 分组标题：`A · Agrégats` 等 |

### 修改组件

| 文件 | 改动 |
|------|------|
| `frontend/src/pages/DashboardPage.tsx` | 移除 `DashboardShell`，改用 `DashboardLayout` 组装；去掉 `<PlanGate>`；去掉 jour_type 下拉；弹窗通过本地 state + 上下文驱动 |
| `frontend/src/pages/ProjectListPage.tsx` | 点击 `status='completed'` 的项目 → navigate 到 `/projects/:id/dashboard`（而不是 `/projects/:id`） |
| `frontend/src/pages/ProjectDetailPage.tsx` | 检查 "Tableau de bord" 按钮在 pipeline 未完成时是否正确置灰（commit `8947f2d` 已部分实现） |
| `frontend/src/components/organisms/AppHeader.tsx` | 看板场景下的 Header 变体：返回按钮 + 项目名 + 重置 + 齿轮 + 导出 + 用户。可抽成新的 `DashboardHeader` organism |
| `frontend/src/hooks/useDashboardSync.tsx` | `FilterState` 新增 `hoursSelected: number[]`；新增 action `TOGGLE_HOUR`（复用 `sameArray()` 防死循环）；新增辅助 `activeFilterCount()` 和 `isTableFiltered()` |

### 删除组件

| 文件 | 原因 |
|------|------|
| `frontend/src/components/organisms/DashboardCharts.tsx` | 由 `DashboardRightPanel` + 两张专用图表替代；Top 20 Courses 和 Top 20 KCC 与 F_1 / F_3（弹窗内可达）信息重复 |
| `DashboardPage.tsx` 内的 `DashboardShell` 内嵌组件 | 布局完全重构 |

---

## 后端接口

### 新增

```
GET /api/v1/projects/{id}/charts/courses-by-jour-type
  → [{jour_type: int, jour_type_name: str, nb_courses: int}, ...]
  按 F_1 GROUP BY jour_type 聚合。不接收筛选参数（始终展示全局视角）。

GET /api/v1/projects/{id}/charts/courses-by-hour?jour_type={int}&route_types[]={str}
  → [{heure: int, nb_courses: int}, ...]  # 0..23
  按 F_1（或 E_1，视 schema）的发车小时聚合。受 jour_type + route_types 过滤。

GET /api/v1/projects/{id}/kpis?jour_type={int}&route_types[]={str}
  → {nb_lignes: int, nb_arrets: int, nb_courses: int, kcc_total: float}
  一次性返回 4 个 KPI 指标（避免 4 次独立请求）。
```

### 废弃

- `GET /charts/peak-offpeak`（被 `/courses-by-hour` 替代）。保留一个 release 后删除。

### 保留

- `GET /projects/{id}/tables/{table_id}`（ResultTable 使用）
- `GET /projects/{id}/map/bounds`
- `GET /projects/{id}/jour-types`（图表 label 仍需要）

---

## `useDashboardSync` 扩展

```typescript
type FilterState = {
  jourType: number;              // 单选，默认 = JOB
  routeTypes: string[];
  ligneIds: number[];
  agIds: number[];
  hoursSelected: number[];       // 新增 —— 多选 0..23
};

type Action =
  | { type: 'SET_JOUR_TYPE'; payload: number }
  | { type: 'TOGGLE_ROUTE_TYPE'; payload: string }
  | { type: 'SET_ROUTE_TYPES'; payload: string[] }
  | { type: 'TOGGLE_LIGNE_ID'; payload: number }
  | { type: 'TOGGLE_AG_ID'; payload: number }
  | { type: 'TOGGLE_HOUR'; payload: number }         // 新增
  | { type: 'CLEAR_FILTERS' };

// 新增辅助函数：
activeFilterCount(state: FilterState): number   // 给 Header 的重置徽标
isTableFiltered(state: FilterState, tableId: string): boolean  // 给左栏漏斗图标
```

**防死循环规则**（保留 commit `98decec` 的修复）：所有数组型 action 在 dispatch 前执行 `sameArray()` shallow equality 检查，包括新增的 `TOGGLE_HOUR`。

**初始状态**：`jourType` 用 `/jour-types` 接口返回的第一个值初始化（通常是 JOB）；`hoursSelected = []`（没选就是没筛）。

---

## 筛选维度 → 表格 映射（漏斗图标规则）

| 激活维度 | 显示漏斗的表格 |
|----------|---------------|
| `routeTypes` 非空 | B_1, B_2, F_1, F_3, E_1, E_4 |
| `ligneIds` 非空 | B_1, B_2, F_1, F_3 |
| `agIds` 非空 | A_1, E_1, E_4 |
| `hoursSelected` 非空 | F_1, E_1, E_4 |
| `jourType` ≠ 默认值 | F_1, F_3, E_1, E_4 |

规则集中在 `useDashboardSync` 里的 `isTableFiltered(state, tableId)` helper。`TableListSidebar` 调用它决定是否渲染漏斗图标。

---

## 实施前必读的关键文件

- `frontend/src/pages/DashboardPage.tsx` —— 现有 `DashboardShell`（第 88–231 行）是同步逻辑的参考实现
- `frontend/src/hooks/useDashboardSync.tsx` —— reducer 基础，需遵循现有防死循环保护
- `frontend/src/components/organisms/ResultTable.tsx` —— 原样复用到 `TablePopup`，检查 `externalEnumValues` + `onFilterChange` props
- `frontend/src/components/organisms/MapView.tsx` —— 原样复用，只去掉外部 `<PlanGate>` 包裹
- `frontend/src/components/ui/dialog.tsx` —— `TablePopup` 的基座（Radix Dialog 已安装）
- `docs/atomic-design.md` —— 设计规范、层级决策、CSS 变量
- `frontend/src/hooks/useProjectProgress.ts` —— pipeline 状态的唯一真相来源，用于控制 Dashboard 按钮置灰
- `backend/app/api/v1/charts.py`（或等价路径）—— 现有 `/charts/peak-offpeak` 端点是两个新端点的模板

---

## 实施步骤

### Phase 1 —— 后端
1. 新增端点 `GET /projects/{id}/charts/courses-by-jour-type`
2. 新增端点 `GET /projects/{id}/charts/courses-by-hour`（支持 `jour_type` + `route_types[]`）
3. 新增端点 `GET /projects/{id}/kpis`（4 个指标一次返回）
4. pytest 三个端点（复用 SEM/SOLEA fixtures）

### Phase 2 —— Hook 和 State
5. 扩展 `useDashboardSync`：`hoursSelected`、`TOGGLE_HOUR`、`activeFilterCount`、`isTableFiltered`
6. reducer 单元测试（Vitest）

### Phase 3 —— 基础组件
7. 创建 `KpiCard`、`TableSidebarItem`、`TableGroupHeader`（molecules）
8. 创建 `DashboardLayout` template（三栏骨架）

### Phase 4 —— Organisms
9. 创建 `TableListSidebar`（消费 `useDashboardSync` 决定漏斗，暴露 `onTableClick`）
10. 创建 `CoursesByJourTypeChart`（点击 → `SET_JOUR_TYPE`）
11. 创建 `CoursesByHourChart`（点击 → `TOGGLE_HOUR`）
12. 创建 `DashboardRightPanel`（组合 KPI + 2 图表）
13. 创建 `TablePopup`（Sheet/Dialog + `ResultTable`）

### Phase 5 —— 页面装配 + 路由
14. 重写 `DashboardPage`：删除 `DashboardShell`、去掉 `<PlanGate>`、用 `DashboardLayout` 组装、用本地 state 控制弹窗
15. 适配 `AppHeader`（或新建 `DashboardHeader`）：返回、项目名、重置按钮 + 徽标、齿轮、导出下拉
16. 修改 `ProjectListPage`：点击 `status='completed'` 的项目跳 `/dashboard`
17. 检查 `ProjectDetailPage` 里 Dashboard 按钮的 gating

### Phase 6 —— 清理
18. 删除 `DashboardCharts.tsx`（旧 2×2 网格）
19. 废弃 `/charts/peak-offpeak`（代码注释标注，下个 release 删除）

---

## 端到端验证

### 后端
```bash
cd backend && pytest tests/api/test_charts.py -v
cd backend && pytest tests/api/test_kpis.py -v
```

### 前端
```bash
cd frontend && npm run typecheck
cd frontend && npm run test
cd frontend && npm run dev  # 手动测试
```

### 手动测试黄金路径
1. 登录 → 项目列表 → 点击 SEM 项目（status=completed）→ **应直接进入 `/dashboard`**
2. 看板加载：4 张 KPI 显示数值，2 张图渲染，地图可见，左栏列出 15 张表按 A/B/C/D/E/F 分组
3. 点击 `jour_type` 图表的 "DIM" 柱 → 地图 + KPI + 小时图刷新；F_1, F_3, E_1, E_4 出现漏斗
4. 点击小时图的 "8" 柱 → F_1 新增漏斗；重置按钮徽标变为 2
5. 点击左栏 "B_1" → 右侧 Sheet 弹出，`ResultTable` 显示按 DIM 过滤后的数据
6. 弹窗内激活 `route_type = [3,7]` 的 enum 筛选 → 后台地图刷新；关闭弹窗 → B_1 的漏斗保留
7. 点击 "重置筛选" → 徽标归 0，所有漏斗消失，图表取消选中，地图回到初始状态
8. 点击 ⚙️ 管理 → 跳转 `/projects/:id`（ProjectDetailPage）
9. 创建新项目 → pipeline 运行期间 "Tableau de bord" 按钮应置灰；完成后从列表点击会触发重定向
10. 导出下拉：GeoPackage 和 CSV zip 都能正确下载

### 回归测试
- Bug 40B（DashboardShell / ResultTable 同步死循环）不复发：在弹窗里反复开关 10 次并每次改筛选 —— 不应卡死，不应有 "Maximum update depth exceeded" 日志
- 地图饼图点击：仍应 toggle `agIds`，并触发 KPI / 图表 / 受影响表格的刷新

---

## 已识别的风险

1. **KPI 端点性能**：`/kpis` 如果串行执行 4 次 SQL 聚合，延迟会叠加。缓解：如果后端是 async 栈就用 `asyncio.gather` 并行；否则在后端做缓存（key = project_id + 筛选参数 hash）
2. **点击图表的选中反馈**：激活状态的柱必须有清晰的视觉区分（蓝色 vs 灰色）。缺失视觉反馈的话，用户看不出已经有筛选
3. **弹窗选型 Sheet vs Dialog**：对于宽表（E_4 有 20+ 列），75vw 的 Sheet 可能还是紧。用真实数据测试；必要时回退到 `max-w-[95vw]` 的 Dialog
4. **响应式移动端**：v2 再做，但 `DashboardLayout` 现在就要用 flexbox / grid + 预留断点，避免后续大重构
5. **jour_type 迁移**：习惯用下拉的老用户会失去熟悉元素。用柱图高亮 + tooltip "点击筛选该 jour_type" 做心智补偿

---

## 相关 Commit 和前置工作

- `fc6b48a` feat(frontend): DashboardPage three-view sync via useDashboardSync (Task 39B)
- `8947f2d` feat(frontend): plan-based gating for dashboard map + /dashboard route (Task 40B)
- `c8c74c0` feat(api): expose tenant plan in UserResponse.plan (Task 40A)
- `3cb9d2e` fix(frontend): wrap DashboardPage in ErrorBoundary + rename useDashboardSync to .tsx
- `98decec` fix(frontend): break DashboardShell/ResultTable sync loop (Bug 40B)

本计划建立在这些 commit 已经完成的基础上。
