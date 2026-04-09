# 生产 / 开发环境操作指南 — GTFS Miner

---

## 1. 环境总览

| 维度 | 本地开发（dev） | 生产（prod） |
|---|---|---|
| Git 分支 | `dev` | `main` |
| 后端运行方式 | `uvicorn --reload`（本地） | Zeabur 容器自动部署 |
| 前端运行方式 | `npm run dev`（Vite 热更新） | Cloudflare Pages 自动构建 |
| 数据库 | SQLite（`backend/storage/miner_app.db`） | Zeabur 环境变量中的 `DATABASE_URL` |
| 文件存储 | 本地 `backend/storage/` | Cloudflare R2（`gtfs-miner` bucket） |
| 环境变量来源 | `backend/.env`（本地文件，不提交 Git） | Zeabur → Variables 面板 |
| 访问地址 | `http://localhost:5173` | `https://app.siwei-ai.dev`（示例） |

---

## 2. 日常开发流程

### 2.1 切换到开发分支

```bash
# 首次创建
git checkout -b dev

# 之后每次开发前
git checkout dev
git pull origin main   # 保持与生产同步
```

### 2.2 启动本地后端

```bash
cd backend
# 首次：创建并激活虚拟环境
python -m venv .venv
source .gtfs/Scripts/activate.ps1   # Windows Git Bash
pip install -r requirements.txt

# 之后每次
source .gtfs/Scripts/activate.ps1 
uvicorn app.main:app --reload
```

后端运行在 `http://localhost:8000`，Swagger 文档在 `http://localhost:8000/docs`。

### 2.3 启动本地前端

```bash
cd frontend
npm install   # 首次
npm run dev
```

前端运行在 `http://localhost:5173`，`/api` 请求自动代理到 `localhost:8000`。

### 2.4 本地 `.env` 配置

`backend/.env`（**不要提交 Git**，已在 `.gitignore`）：

```env
# 本地开发 — SQLite + 本地存储（默认值，可不填）
DATABASE_URL=sqlite:///./storage/miner_app.db
R2_ENDPOINT_URL=
CORS_ORIGINS=http://localhost:5173
```

留空 `R2_ENDPOINT_URL` 时，文件自动保存在本地 `storage/` 目录，无需 R2。

---

## 3. 推送到生产

### 3.1 标准流程

```bash
# 在 dev 分支完成开发并测试
git add <修改的文件>
git commit -m "feat: 描述改动"

# 合并到 main 并推送
git checkout main
git merge dev
git push   # 触发 Zeabur 和 Cloudflare Pages 自动部署
```

### 3.2 部署时间

| 端 | 平台 | 预计时间 |
|---|---|---|
| 后端 | Zeabur（Docker 构建） | 2–4 分钟 |
| 前端 | Cloudflare Pages（npm build） | 1–2 分钟 |

### 3.3 查看部署状态

- **后端**：Zeabur → 项目 → 服务 → `Deployments` → 最新一条 → `Logs`
- **前端**：Cloudflare Dashboard → Workers & Pages → `gtfs-miner-app` → `Deployments`

正常后端日志末尾应出现：
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## 4. 环境变量管理

### 4.1 本地（开发）

编辑 `backend/.env`，修改后重启 `uvicorn` 即可生效。

### 4.2 生产（Zeabur）

Zeabur → 服务 → `Variables` → 编辑对应变量 → 保存后自动重新部署。

**当前生产变量清单：**

| 变量名 | 说明 |
|---|---|
| `DATABASE_URL` | Supabase 或 SQLite 连接串 |
| `R2_ACCOUNT_ID` | Cloudflare R2 账号 ID |
| `R2_ACCESS_KEY_ID` | R2 访问密钥 |
| `R2_SECRET_ACCESS_KEY` | R2 秘密密钥 |
| `R2_BUCKET_NAME` | `gtfs-miner` |
| `R2_ENDPOINT_URL` | `https://<account_id>.r2.cloudflarestorage.com` |
| `REDIS_URL` | Upstash Redis URL |
| `CORS_ORIGINS` | `https://app.yourdomain.com`（必须含 `https://`） |

> **注意**：`CORS_ORIGINS` 必须包含完整协议（`https://`），否则 CORS 预检请求返回 400。

---

## 5. 何时需要云端开发环境

本地 SQLite + 本地存储覆盖 90% 的开发场景。以下情况才需要额外配置：

| 需求 | 解决方案 |
|---|---|
| 测试 R2 上传/下载行为 | R2 新建 `gtfs-miner-dev` bucket，本地 `.env` 指向它 |
| 测试 PostgreSQL 特有行为 | Supabase 新建第二个项目，本地 `.env` 填入 dev 连接串 |
| 测试完整 Docker 镜像 | `docker build -t gtfs-miner-dev . && docker run -p 8000:8000 gtfs-miner-dev` |
| 测试生产 CORS 行为 | 本地 `.env` 设 `CORS_ORIGINS=http://localhost:5173` 即可复现 |

---

## 6. 常见操作速查

### 回滚生产到上一个版本

```bash
# 查看最近提交
git log --oneline -5

# 回退到某个提交（本地先测试）
git revert HEAD   # 创建一个反向提交（推荐，可追溯）
git push          # 推送触发重新部署
```

> 避免使用 `git reset --hard` + `git push --force`，会丢失提交历史。

### 强制 Zeabur 重新部署（不改代码）

Zeabur → 服务 → `Deployments` → `Redeploy`（右上角按钮）。

### 强制 Cloudflare Pages 重新构建

Cloudflare → Pages 项目 → `Deployments` → 最新部署右侧 `···` → `Retry deployment`。

### 查看生产实时日志

Zeabur → 服务 → `Logs` 标签（实时流式输出）。

### 本地运行测试

```bash
cd backend
pytest
```

测试数据位于 `backend/tests/Resources/raw/`（SEM、SOLEA、ginko 三个最小样本）。
