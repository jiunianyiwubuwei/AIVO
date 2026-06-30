"""AI 对话 API - 与 Java 后端保持字段命名一致"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.security import get_current_user
from app.infrastructure.database.models import User
from app.infrastructure.cache.mongodb_client import mongodb_client

router = APIRouter()


class ChatMessage(BaseModel):
    """聊天消息"""
    role: str
    content: str
    created_at: Optional[str] = None


class ChatRequest(BaseModel):
    """聊天请求"""
    sessionId: Optional[str] = None
    inputMessage: str = ""
    userName: Optional[str] = None
    aiId: Optional[int] = None
    messageSeq: Optional[int] = None
    imageUrls: Optional[list] = None
    mediaList: Optional[list] = None


async def chat_with_ai(
    messages: list[dict],
    session_id: str,
    username: str,
) -> AsyncIterator[str]:
    """与 AI 对话"""
    from app.agents.ai_client import ai_client

    try:
        # 获取对话历史 - 使用 Java 字段名
        history = await mongodb_client.find_many(
            "ai_message",
            {"sessionId": session_id, "delFlag": {"$ne": 1}},
            sort=[("createTime", 1)],
            limit=50,
        )

        # 构建消息列表
        system_prompt = {
            "role": "system",
            "content": "你是一个友好的 AI 助手，名字叫小讯。请用简洁、有帮助的方式回答用户的问题。"
        }

        all_messages = [system_prompt]
        for msg in history:
            all_messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("messageContent", msg.get("content", "")),
            })
        all_messages.extend(messages)

        # 调用 AI
        full_response = ""
        async for chunk in ai_client.chat(all_messages, stream=True):
            full_response += chunk
            yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"

        # 保存消息到 MongoDB - 使用 Java 字段名
        now = datetime.now(timezone.utc)

        await mongodb_client.insert_one("ai_message", {
            "messageId": str(uuid.uuid4()),
            "sessionId": session_id,
            "username": username,
            "role": "user",
            "messageContent": messages[-1]["content"] if messages else "",
            "messageType": 1,
            "messageSeq": 1,
            "createTime": now,
            "updateTime": now,
            "delFlag": 0,
        })

        await mongodb_client.insert_one("ai_message", {
            "messageId": str(uuid.uuid4()),
            "sessionId": session_id,
            "username": username,
            "role": "assistant",
            "messageContent": full_response,
            "messageType": 2,
            "messageSeq": 2,
            "createTime": now,
            "updateTime": now,
            "delFlag": 0,
        })

        # 更新会话信息
        await mongodb_client.update_one(
            "ai_conversation",
            {"sessionId": session_id},
            {
                "updateTime": now,
                "lastMessageTime": now,
            }
        )

    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    yield "data: {\"done\": true}\n\n"


@router.post("/sessions/{session_id}/chat")
async def chat(
    session_id: str,
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """AI 聊天接口 (SSE 流式返回)"""
    username = request.userName or current_user.username

    # 确保会话存在 - 使用 Java 字段名
    existing_session = await mongodb_client.find_one(
        "ai_conversation",
        {"sessionId": session_id, "username": current_user.username}
    )

    if not existing_session:
        now = datetime.now(timezone.utc)
        await mongodb_client.insert_one("ai_conversation", {
            "sessionId": session_id,
            "username": current_user.username,
            "aiId": request.aiId,
            "title": request.inputMessage[:30] if request.inputMessage else "新对话",
            "status": 1,
            "messageCount": 0,
            "createTime": now,
            "updateTime": now,
            "lastMessageTime": now,
            "delFlag": 0,
        })

    messages = [{"role": "user", "content": request.inputMessage}]

    async def generate():
        async for chunk in chat_with_ai(
            messages=messages,
            session_id=session_id,
            username=username,
        ):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/conversations")
async def list_ai_conversations(
    current: int = Query(default=1, ge=1, description="当前页"),
    size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_user),
):
    """获取 AI 对话列表"""
    skip = (current - 1) * size

    try:
        # 使用 Java 字段名
        conversations = await mongodb_client.find_many(
            "ai_conversation",
            {"username": current_user.username, "delFlag": {"$ne": 1}},
            sort=[("createTime", -1)],
            limit=size,
            skip=skip,
        )

        total = await mongodb_client.count_documents(
            "ai_conversation",
            {"username": current_user.username, "delFlag": {"$ne": 1}}
        )

        result = []
        for conv in conversations:
            # 获取最后一条消息
            msgs = await mongodb_client.find_many(
                "ai_message",
                {"sessionId": conv.get("sessionId"), "delFlag": {"$ne": 1}},
                sort=[("createTime", -1)],
                limit=1
            )
            last_message_doc = msgs[0] if msgs else None
            result.append({
                "sessionId": conv.get("sessionId", ""),
                "username": conv.get("username", ""),
                "aiId": conv.get("aiId"),
                "title": conv.get("title") or "新对话",
                "lastMessage": last_message_doc.get("messageContent") if last_message_doc else None,
                "messageCount": conv.get("messageCount", 0),
                "status": conv.get("status", 1),
                "lastMessageTime": conv.get("lastMessageTime"),
                "createTime": conv.get("createTime"),
                "updateTime": conv.get("updateTime"),
            })

        return {
            "code": 200,
            "message": "success",
            "success": True,
            "records": result,
            "total": total,
            "size": size,
            "current": current,
            "pages": (total + size - 1) // size if total > 0 else 0,
        }
    except Exception as e:
        return {
            "code": 200,
            "message": "success",
            "success": True,
            "records": [],
            "total": 0,
            "size": size,
            "current": current,
            "pages": 0,
        }


@router.post("/conversations")
async def create_ai_conversation(
    current_user: User = Depends(get_current_user),
):
    """创建新的 AI 对话"""
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # 使用 Java 字段名
    await mongodb_client.insert_one("ai_conversation", {
        "sessionId": session_id,
        "username": current_user.username,
        "title": "新对话",
        "status": 1,
        "messageCount": 0,
        "createTime": now,
        "updateTime": now,
        "lastMessageTime": now,
        "delFlag": 0,
    })

    return {
        "code": 200,
        "message": "success",
        "success": True,
        "data": {
            "sessionId": session_id,
            "conversationTitle": "新对话",
        }
    }


@router.get("/history/{session_id}")
async def get_conversation_history(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """获取对话历史"""
    # 使用 Java 字段名
    messages = await mongodb_client.find_many(
        "ai_message",
        {"sessionId": session_id, "delFlag": {"$ne": 1}},
        sort=[("createTime", 1)],
    )

    result = []
    for msg in messages:
        result.append({
            "id": msg.get("messageId"),
            "sessionId": msg.get("sessionId"),
            "messageType": msg.get("messageType", 1 if msg.get("role") == "user" else 2),
            "messageContent": msg.get("messageContent"),
            "reasoningContent": msg.get("reasoningContent"),
            "createTime": msg.get("createTime"),
        })

    return {
        "code": 200,
        "message": "success",
        "success": True,
        "data": result,
    }


@router.delete("/conversations/{session_id}")
async def delete_ai_conversation(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """删除 AI 对话"""
    now = datetime.now(timezone.utc)
    await mongodb_client.update_one(
        "ai_conversation",
        {"sessionId": session_id, "username": current_user.username},
        {"delFlag": 1, "updateTime": now}
    )
    return {"code": 200, "message": "success", "success": True}


@router.put("/conversations/{session_id}")
async def update_ai_conversation(
    session_id: str,
    title: str = Query(..., description="新标题"),
    current_user: User = Depends(get_current_user),
):
    """更新 AI 对话标题"""
    now = datetime.now(timezone.utc)
    await mongodb_client.update_one(
        "ai_conversation",
        {"sessionId": session_id, "username": current_user.username},
        {"title": title, "updateTime": now}
    )
    return {"code": 200, "message": "success", "success": True}


@router.get("/conversations/{session_id}")
async def get_ai_conversation(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """获取 AI 对话详情"""
    conv = await mongodb_client.find_one(
        "ai_conversation",
        {"sessionId": session_id, "username": current_user.username}
    )
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")

    return {
        "code": 200,
        "message": "success",
        "success": True,
        "data": {
            "sessionId": conv.get("sessionId"),
            "username": conv.get("username"),
            "aiId": conv.get("aiId"),
            "title": conv.get("title", "新对话"),
            "status": conv.get("status", 1),
            "messageCount": conv.get("messageCount", 0),
            "createTime": conv.get("createTime"),
            "updateTime": conv.get("updateTime"),
            "lastMessageTime": conv.get("lastMessageTime"),
        }
    }
