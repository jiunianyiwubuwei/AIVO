"""健康检查 API"""

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.core.logging import get_logger
from app.infrastructure.database.connection import engine
from app.infrastructure.cache.redis_client import redis_client

router = APIRouter()
logger = get_logger(__name__)


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    timestamp: datetime
    services: dict


class ReadinessResponse(BaseModel):
    """就绪检查响应"""
    status: str
    checks: dict


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查端点"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc),
        services={}
    )


@router.get("/ready", response_model=ReadinessResponse)
async def readiness_check():
    """就绪检查端点 - 检查所有依赖服务"""
    checks = {
        "database": False,
        "redis": False,
    }

    # 检查数据库
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")

    # 检查 Redis
    try:
        await redis_client.set("health_check", "ok", ex=10)
        result = await redis_client.get("health_check")
        checks["redis"] = result == "ok"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")

    all_healthy = all(checks.values())

    return ReadinessResponse(
        status="ready" if all_healthy else "not_ready",
        checks=checks,
    )


@router.get("/live")
async def liveness_check():
    """存活检查端点"""
    return {"status": "alive"}
