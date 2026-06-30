"""用户 WebSocket API"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket
from fastapi import status as http_status

from app.core.security import decode_token, get_current_user
from app.infrastructure.database.connection import get_db
from app.infrastructure.database.models import User
from app.infrastructure.websocket.websocket_manager import user_ws_manager
from app.infrastructure.websocket.websocket_auth import authorize_websocket

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/user/{user_id}/status")
async def get_user_online_status(
    user_id: str,
):
    """查询用户在线状态"""
    return {
        "code": 200,
        "message": "success",
        "success": True,
        "data": {
            "userId": user_id,
            "online": user_ws_manager.is_online(user_id),
        }
    }


@router.post("/send-message")
async def send_message(
    user_id: str,
    message_type: str = Query(..., alias="type", description="消息类型"),
    message: Optional[str] = Query(None, description="消息内容"),
    data: Optional[str] = Query(None, description="扩展数据"),
    current_user: User = Depends(get_current_user),
):
    """发送自定义消息到用户"""
    if not user_ws_manager.is_online(user_id):
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="用户当前离线")

    payload = {
        "type": message_type,
        "message": message,
        "data": data,
        "timestamp": None,
    }

    success = await user_ws_manager.send_json(user_id, payload)
    if not success:
        raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail="消息发送失败")

    return {"code": 200, "message": "success", "success": True}


@router.post("/notification/{user_id}")
async def send_system_notification(
    user_id: str,
    message: str = Query(..., description="通知内容"),
    current_user: User = Depends(get_current_user),
):
    """发送系统通知"""
    if not user_ws_manager.is_online(user_id):
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="用户当前离线")

    payload = {
        "type": "system_notification",
        "message": message,
        "timestamp": None,
    }

    success = await user_ws_manager.send_json(user_id, payload)
    if not success:
        raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail="通知发送失败")

    return {"code": 200, "message": "success", "success": True}


@router.post("/transcription/{user_id}")
async def send_transcription_result(
    user_id: str,
    result: str = Query(..., description="转写文本"),
    is_final: bool = Query(default=False, description="是否最终结果"),
    current_user: User = Depends(get_current_user),
):
    """推送语音转写结果"""
    if not user_ws_manager.is_online(user_id):
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="用户当前离线")

    payload = {
        "type": "transcription" if not is_final else "final",
        "message": result,
        "data": {
            "result": result,
            "isFinal": is_final,
        },
        "timestamp": None,
    }

    success = await user_ws_manager.send_json(user_id, payload)
    if not success:
        raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail="推送失败")

    return {"code": 200, "message": "success", "success": True}


@router.post("/error/{user_id}")
async def send_error_message(
    user_id: str,
    error_message: str = Query(..., description="错误信息"),
    current_user: User = Depends(get_current_user),
):
    """推送错误消息"""
    if not user_ws_manager.is_online(user_id):
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="用户当前离线")

    payload = {
        "type": "error",
        "message": error_message,
        "timestamp": None,
    }

    success = await user_ws_manager.send_json(user_id, payload)
    if not success:
        raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail="推送失败")

    return {"code": 200, "message": "success", "success": True}


@router.websocket("/user/{user_id}")
async def user_websocket(
    websocket: WebSocket,
    user_id: str,
    token: Optional[str] = Query(None, description="认证令牌"),
):
    """用户 WebSocket 端点"""
    # 鉴权
    auth_result = await authorize_websocket(websocket, user_id, token)
    if not auth_result.ok:
        await websocket.close(code=auth_result.close_code or 1008, reason=auth_result.reason)
        return

    # 注册连接
    await user_ws_manager.connect(user_id, websocket)

    try:
        while True:
            message_text = await websocket.receive_text()

            try:
                message = __import__("json").loads(message_text)
            except __import__("json").JSONDecodeError:
                await user_ws_manager.send_json(user_id, {
                    "type": "error",
                    "message": "Invalid JSON",
                })
                continue

            msg_type = message.get("type")

            if msg_type == "pong":
                # 心跳回包由 ConnectionManager 内部处理，此处仅跳过
                continue

            await user_ws_manager.send_json(user_id, {
                "type": "error",
                "message": f"unsupported message type: {msg_type}",
            })
    except Exception as exc:
        logger.info("user websocket closed", extra={"user_id": user_id, "error": str(exc)})
    finally:
        user_ws_manager.disconnect(user_id)
