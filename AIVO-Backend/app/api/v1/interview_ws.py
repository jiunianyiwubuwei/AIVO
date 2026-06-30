"""面试 WebSocket API"""

import json
from typing import Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.infrastructure.database.connection import get_db
from app.infrastructure.database.models import User
from app.application.interview.workflow_service import InterviewWorkflowService

router = APIRouter()


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        """建立连接"""
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str):
        """断开连接"""
        if session_id in self.active_connections:
            del self.active_connections[session_id]

    async def send_json(self, session_id: str, data: dict):
        """发送 JSON 数据"""
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(data)

    async def send_text(self, session_id: str, text: str):
        """发送文本"""
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_text(text)


manager = ConnectionManager()


@router.websocket("/interview/ws/{session_id}")
async def interview_websocket(
    websocket: WebSocket,
    session_id: str,
    token: Optional[str] = Query(None),
):
    """面试 WebSocket 端点"""
    from app.infrastructure.database.connection import get_db_context

    # 验证 token
    if token:
        payload = decode_token(token)
        if payload is None:
            await websocket.close(code=4001, reason="Invalid token")
            return
    else:
        await websocket.close(code=4001, reason="Token required")
        return

    await manager.connect(websocket, session_id)

    try:
        # 使用正确的数据库会话管理
        async with get_db_context() as db:
            service = InterviewWorkflowService(db)

            # 加载当前状态
            state = await service.get_current_state(session_id)

            if state is None:
                await manager.send_json(session_id, {
                    "type": "error",
                    "message": "Session not found"
                })
                return

            # 发送初始状态
            await manager.send_json(session_id, {
                "type": "state",
                "data": {
                    "status": state.status.value,
                    "current_question_index": state.current_question_index,
                    "total_questions": state.total_questions,
                    "total_score": state.total_score,
                    "follow_up_count": state.follow_up_count,
                }
            })

            # 如果在等待状态，发送当前问题
            if state.ai_message:
                await manager.send_json(session_id, {
                    "type": "message",
                    "content": state.ai_message,
                    "role": "assistant",
                })

            # 循环处理消息
            while True:
                try:
                    # 接收用户消息
                    data = await websocket.receive_text()
                    message_data = json.loads(data)

                    msg_type = message_data.get("type")

                    if msg_type == "message":
                        # 用户发送消息
                        user_input = message_data.get("content", "")

                        # 处理消息
                        new_state = await service.send_message(session_id, user_input)

                        # 发送 AI 响应
                        if new_state.ai_message:
                            await manager.send_json(session_id, {
                                "type": "message",
                                "content": new_state.ai_message,
                                "role": "assistant",
                            })

                        # 发送状态更新
                        await manager.send_json(session_id, {
                            "type": "state",
                            "data": {
                                "status": new_state.status.value,
                                "current_question_index": new_state.current_question_index,
                                "total_questions": new_state.total_questions,
                                "total_score": new_state.total_score,
                                "follow_up_count": new_state.follow_up_count,
                            }
                        })

                        # 如果面试完成
                        if new_state.status.value == "COMPLETED":
                            await manager.send_json(session_id, {
                                "type": "completed",
                                "data": {
                                    "interview_score": new_state.interview_score,
                                    "suggestions": new_state.interview_suggestions,
                                }
                            })

                    elif msg_type == "ping":
                        # 心跳
                        await manager.send_json(session_id, {"type": "pong"})

                except json.JSONDecodeError:
                    await manager.send_json(session_id, {
                        "type": "error",
                        "message": "Invalid JSON"
                    })

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        await manager.send_json(session_id, {
            "type": "error",
            "message": str(e)
        })
        manager.disconnect(session_id)
