"""用户级 WebSocket 管理器"""

import asyncio
import logging
import time
from typing import Dict, Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """用户 WebSocket 连接管理器"""

    def __init__(self):
        self._user_connections: Dict[str, WebSocket] = {}
        self._heartbeat_tasks: Dict[str, asyncio.Task] = {}
        self._last_pong: Dict[str, float] = {}

    async def connect(self, user_id: str, websocket: WebSocket, heartbeat_interval: int = 30):
        """建立用户连接"""
        if user_id in self._user_connections:
            await self.disconnect(user_id)

        await websocket.accept()
        self._user_connections[user_id] = websocket
        self._last_pong[user_id] = time.time()

        # 启动心跳任务
        self._heartbeat_tasks[user_id] = asyncio.create_task(
            self._heartbeat(user_id, websocket, heartbeat_interval)
        )

        logger.info("websocket connected", extra={"user_id": user_id})

    def disconnect(self, user_id: str):
        """断开用户连接"""
        task = self._heartbeat_tasks.pop(user_id, None)
        if task and not task.done():
            task.cancel()

        self._user_connections.pop(user_id, None)
        self._last_pong.pop(user_id, None)

        logger.info("websocket disconnected", extra={"user_id": user_id})

    async def send_json(self, user_id: str, data: dict) -> bool:
        """向指定用户发送 JSON 消息"""
        websocket = self._user_connections.get(user_id)
        if websocket is None:
            return False

        try:
            await websocket.send_json(data)
            return True
        except Exception as exc:  # pragma: no cover
            logger.warning("send json failed", extra={"user_id": user_id, "error": str(exc)})
            self.disconnect(user_id)
            return False

    async def send_text(self, user_id: str, text: str) -> bool:
        """向指定用户发送文本消息"""
        websocket = self._user_connections.get(user_id)
        if websocket is None:
            return False

        try:
            await websocket.send_text(text)
            return True
        except Exception as exc:  # pragma: no cover
            logger.warning("send text failed", extra={"user_id": user_id, "error": str(exc)})
            self.disconnect(user_id)
            return False

    def is_online(self, user_id: str) -> bool:
        """检查用户是否在线"""
        return user_id in self._user_connections

    def get_online_user_ids(self) -> list[str]:
        """获取所有在线用户"""
        return list(self._user_connections.keys())

    async def _heartbeat(self, user_id: str, websocket: WebSocket, interval: int):
        """心跳检测"""
        try:
            while True:
                await asyncio.sleep(interval)
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception as exc:  # pragma: no cover
                    logger.warning("heartbeat failed", extra={"user_id": user_id, "error": str(exc)})
                    break
        except asyncio.CancelledError:
            pass
        finally:
            self.disconnect(user_id)


user_ws_manager = ConnectionManager()
