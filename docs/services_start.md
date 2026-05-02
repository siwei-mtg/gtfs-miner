终端 1 — Uvicorn（FastAPI 服务）                                                                                                              
cd "C:/Users/wei.si/Projets/GTFS Miner/backend"
venv/Scripts/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
终端 2 — Celery Worker
cd "C:/Users/wei.si/Projets/GTFS Miner/backend"
venv/Scripts/python -m celery -A app.celery_app.celery worker -P solo --loglevel=info
-P solo 是 Windows 必须加的参数（Windows 不支持默认的 prefork 多进程池）。
启动前确认 Redis 正在运行，否则 Celery 会回退到内存 broker（仅测试可用）。

cd "C:/Users/wei.si/Projets/GTFS Miner/frontend"
npm run dev
# 端口 5174 已写死在 vite.config.ts 的 server.port