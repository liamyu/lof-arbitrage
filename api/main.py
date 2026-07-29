"""
FastAPI 主入口
提供 LOF 套利数据的 REST API 服务
"""
import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.routers import funds, opportunities, meta
from core.scheduler import init_scheduler, shutdown_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化定时任务，关闭时清理"""
    init_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(
    title="LOF 套利数据 API",
    description="LOF 溢价套利评分与数据查询服务",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS 配置（允许 H5 前端调用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应改为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(meta.router, prefix="/api/v1")
app.include_router(opportunities.router, prefix="/api/v1")
app.include_router(funds.router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "message": "LOF 套利数据 API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/api/v1/health")
def health():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return {
        "status": "ok",
        "timestamp": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    }


@app.get("/api/v1/meta/scheduler")
def scheduler_status():
    """查看定时任务调度器状态"""
    from core.scheduler import get_scheduler_info
    return get_scheduler_info()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
