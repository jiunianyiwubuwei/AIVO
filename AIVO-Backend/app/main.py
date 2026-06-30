"""FastAPI 入口文件"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.exceptions import register_exception_handlers
from app.infrastructure.database import init_db, close_db
from app.infrastructure.cache.redis_client import redis_client
from app.infrastructure.cache.mongodb_client import mongodb_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    setup_logging()
    await init_db()
    await redis_client.connect()
    await mongodb_client.connect()

    # 创建 uploads 目录
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    yield
    # 关闭时
    await redis_client.close()
    await mongodb_client.close()
    await close_db()


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title=settings.app.name,
        version="0.1.0",
        lifespan=lifespan,
    )

    # 注册异常处理器
    register_exception_handlers(app)

    # CORS 配置
    cors_origins = settings.app.cors_origins or [
        "http://localhost:7531",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:7531",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由 - 添加 /xunzhi/v1 前缀以兼容前端
    from app.api.router import api_router
    app.include_router(api_router, prefix="/xunzhi/v1")

    # 用户 WebSocket 路由（兼容前端 /xunzhi/v1/websocket/...）
    from app.api.v1 import websocket as websocket_router
    app.include_router(websocket_router.router, prefix="/xunzhi/v1/websocket", tags=["websocket"])

    # 挂载静态文件目录，提供上传文件访问
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=upload_dir), name="uploads")

    return app


app = create_app()
