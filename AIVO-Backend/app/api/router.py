"""路由聚合"""

from fastapi import APIRouter

from app.api.v1 import interview, agent, ai, user, interview_ws, health, ai_properties, websocket as user_websocket

api_router = APIRouter()

api_router.include_router(interview.router, prefix="/interview", tags=["interview"])
api_router.include_router(agent.router, prefix="/agent", tags=["agent"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(user.router, prefix="/users", tags=["user"])
api_router.include_router(interview_ws.router, tags=["interview-ws"])
api_router.include_router(user_websocket.router, prefix="/websocket", tags=["websocket"])

# AI Properties 路由 (直接放在根路径，兼容前端 /xunzhi/v1/ai-properties)
api_router.include_router(ai_properties.router, tags=["ai-properties"])

# 健康检查路由
api_router.include_router(health.router, tags=["health"])
