"""Agent API - 优化版本"""

import uuid
import json
import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.schemas.agent import (
    AgentPropertiesResponse,
    AiPropertiesResponse,
    AgentPropertiesUpdate,
    AiConversationResponse,
)
from app.core.schemas.response import BaseResponse, PageResponse
from app.core.security import get_current_user, get_current_user_optional
from app.core.config import settings
from app.infrastructure.database.connection import get_db
from app.infrastructure.database.models import User, AgentProperties, AgentFileAsset
from app.infrastructure.cache.mongodb_client import mongodb_client
from app.application.agent.agent_service import AgentService, AiPropertiesService
from app.agents.enhanced_client import enhanced_ai_client, AIResponseError
from app.agents.streaming import (
    StreamEvent,
    StreamingHandler,
    create_error_response,
)

router = APIRouter()


def get_agent_service(db: AsyncSession = Depends(get_db)) -> AgentService:
    return AgentService(db)


def get_ai_properties_service(db: AsyncSession = Depends(get_db)) -> AiPropertiesService:
    return AiPropertiesService(db)


# ========== Agent 配置 API ==========

@router.post("/properties", response_model=BaseResponse[AgentPropertiesResponse])
async def create_agent_property(
    create_data: dict,
    service: AgentService = Depends(get_agent_service),
    current_user: User = Depends(get_current_user),
):
    """创建 Agent 配置"""
    new_agent = await service.create_agent_property(
        agent_name=create_data.get("agent_name"),
        api_flow_id=create_data.get("api_flow_id"),
        ai_mode=create_data.get("ai_mode"),
        ai_properties_id=create_data.get("ai_properties_id"),
        system_prompt=create_data.get("system_prompt"),
        api_key=create_data.get("api_key"),
        api_secret=create_data.get("api_secret"),
    )
    return BaseResponse(data=AgentPropertiesResponse.model_validate(new_agent))


@router.get("/properties", response_model=PageResponse[AgentPropertiesResponse])
async def list_agent_properties(
    skip: int = Query(default=0, ge=0, description="跳过数量"),
    limit: int = Query(default=20, ge=1, le=100, description="返回数量"),
    ai_mode: Optional[str] = Query(default=None, description="AI 模式"),
    agentName: Optional[str] = Query(default=None, alias="agentName"),
    service: AgentService = Depends(get_agent_service),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """获取 Agent 配置列表"""
    items, total = await service.list_agent_properties(skip, limit, ai_mode, agentName)

    return PageResponse(
        data=[AgentPropertiesResponse.model_validate(item) for item in items],
        page_info={
            "page": skip // limit + 1,
            "page_size": limit,
            "total": total,
        }
    )


@router.get("/properties/{agent_id}", response_model=BaseResponse[AgentPropertiesResponse])
async def get_agent_property(
    agent_id: int,
    service: AgentService = Depends(get_agent_service),
):
    """获取单个 Agent 配置"""
    agent = await service.get_agent_property(agent_id)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent 不存在",
        )
    return BaseResponse(data=AgentPropertiesResponse.model_validate(agent))


@router.put("/properties/{agent_id}", response_model=BaseResponse[AgentPropertiesResponse])
async def update_agent_property(
    agent_id: int,
    update_data: AgentPropertiesUpdate,
    service: AgentService = Depends(get_agent_service),
    current_user: User = Depends(get_current_user),
):
    """更新 Agent 配置"""
    agent = await service.update_agent_property(
        agent_id,
        **update_data.model_dump(exclude_none=True)
    )
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent 不存在",
        )
    return BaseResponse(data=AgentPropertiesResponse.model_validate(agent))


# ========== AI 配置 API ==========

@router.get("/ai-configs", response_model=PageResponse[AiPropertiesResponse])
async def list_ai_configs(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    ai_type: Optional[str] = Query(default=None),
    service: AiPropertiesService = Depends(get_ai_properties_service),
):
    """获取 AI 模型配置列表"""
    items, total = await service.list_ai_properties(skip, limit, ai_type)

    return PageResponse(
        data=[AiPropertiesResponse.model_validate(item) for item in items],
        page_info={
            "page": skip // limit + 1,
            "page_size": limit,
            "total": total,
        }
    )


@router.get("/ai-configs/{ai_id}", response_model=BaseResponse[AiPropertiesResponse])
async def get_ai_config(
    ai_id: int,
    service: AiPropertiesService = Depends(get_ai_properties_service),
):
    """获取单个 AI 模型配置"""
    ai_config = await service.get_ai_property(ai_id)
    if ai_config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI 配置不存在",
        )
    return BaseResponse(data=AiPropertiesResponse.model_validate(ai_config))


# ========== AI Properties API (前端期望的路径) ==========

@router.get("/ai-properties", response_model=PageResponse[AiPropertiesResponse])
async def list_ai_properties(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    isEnabled: Optional[int] = Query(default=None, alias="isEnabled"),
    aiType: Optional[str] = Query(default=None, alias="aiType"),
    service: AiPropertiesService = Depends(get_ai_properties_service),
):
    """获取 AI 模型配置列表 (前端路径)"""
    items, total = await service.list_ai_properties(
        skip=skip,
        limit=limit,
        ai_type=aiType,
        is_enabled=isEnabled,
    )

    return PageResponse(
        data=[AiPropertiesResponse.model_validate(item) for item in items],
        page_info={
            "page": skip // limit + 1,
            "page_size": limit,
            "total": total,
        }
    )


@router.post("/ai-properties", response_model=BaseResponse[AiPropertiesResponse])
async def create_ai_property(
    create_data: dict,
    service: AiPropertiesService = Depends(get_ai_properties_service),
    current_user: User = Depends(get_current_user),
):
    """创建 AI 模型配置"""
    new_ai = AgentProperties(**create_data)
    service.db.add(new_ai)
    await service.db.flush()
    await service.db.refresh(new_ai)
    return BaseResponse(data=AiPropertiesResponse.model_validate(new_ai))


@router.put("/ai-properties", response_model=BaseResponse[AiPropertiesResponse])
async def update_ai_property(
    update_data: dict,
    service: AiPropertiesService = Depends(get_ai_properties_service),
    current_user: User = Depends(get_current_user),
):
    """更新 AI 模型配置"""
    ai_id = update_data.get("id")
    if not ai_id:
        raise HTTPException(status_code=400, detail="缺少 id 参数")

    ai_prop = await service.get_ai_property(ai_id)
    if ai_prop is None:
        raise HTTPException(status_code=404, detail="AI 配置不存在")

    for key, value in update_data.items():
        if key != "id" and hasattr(ai_prop, key) and value is not None:
            setattr(ai_prop, key, value)

    await service.db.flush()
    return BaseResponse(data=AiPropertiesResponse.model_validate(ai_prop))


@router.delete("/ai-properties/{ai_id}", response_model=BaseResponse[dict])
async def delete_ai_property(
    ai_id: int,
    service: AiPropertiesService = Depends(get_ai_properties_service),
    current_user: User = Depends(get_current_user),
):
    """删除 AI 模型配置"""
    ai_prop = await service.get_ai_property(ai_id)
    if ai_prop is None:
        raise HTTPException(status_code=404, detail="AI 配置不存在")

    ai_prop.del_flag = 1
    await service.db.flush()
    return BaseResponse(data={"id": ai_id})


@router.put("/ai-properties/{ai_id}/status", response_model=BaseResponse[AiPropertiesResponse])
async def update_ai_property_status(
    ai_id: int,
    isEnabled: int = Query(..., alias="isEnabled"),
    service: AiPropertiesService = Depends(get_ai_properties_service),
    current_user: User = Depends(get_current_user),
):
    """更新 AI 模型启用状态"""
    ai_prop = await service.get_ai_property(ai_id)
    if ai_prop is None:
        raise HTTPException(status_code=404, detail="AI 配置不存在")

    ai_prop.is_enabled = isEnabled
    await service.db.flush()
    return BaseResponse(data=AiPropertiesResponse.model_validate(ai_prop))


# ========== Agent 对话 API ==========

@router.get("/conversations", response_model=PageResponse[AiConversationResponse])
async def list_ai_conversations(
    current: int = Query(default=1, ge=1, description="当前页"),
    size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_user),
):
    """获取 AI 对话列表"""
    skip = (current - 1) * size

    conversations = await mongodb_client.find_many(
        "agent_conversation",
        {"user_id": current_user.id, "del_flag": {"$ne": 1}},
        sort=[("created_at", -1)],
        limit=size,
        skip=skip,
    )

    total = await mongodb_client.count_documents(
        "agent_conversation",
        {"user_id": current_user.id, "del_flag": {"$ne": 1}}
    )

    result = []
    for conv in conversations:
        last_message_doc = await mongodb_client.find_one(
            "agent_conversation",
            {"session_id": conv.get("session_id")},
            sort=[("created_at", -1)]
        )
        result.append(AiConversationResponse(
            session_id=conv.get("session_id", ""),
            user_id=conv.get("user_id", 0),
            username=current_user.username,
            ai_id=conv.get("ai_id"),
            ai_name=conv.get("ai_name"),
            title=conv.get("title") or conv.get("session_id", "")[:20],
            last_message=last_message_doc.get("content") if last_message_doc else None,
            message_count=conv.get("message_count", 0),
            status=conv.get("status", "active"),
            created_at=conv.get("created_at"),
            updated_at=conv.get("updated_at"),
        ))

    return PageResponse(
        data=result,
        page_info={
            "page": current,
            "page_size": size,
            "total": total,
        }
    )


@router.post("/sessions", response_model=BaseResponse)
async def create_agent_session(
    agent_id: int = Form(..., description="Agent ID"),
    title: Optional[str] = Form(None, description="会话标题"),
    current_user: User = Depends(get_current_user),
    service: AgentService = Depends(get_agent_service),
):
    """创建 Agent 会话"""
    agent = await service.get_agent_property(agent_id)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent 不存在",
        )

    session_id = str(uuid.uuid4())

    session_data = {
        "session_id": session_id,
        "user_id": current_user.id,
        "agent_id": agent_id,
        "ai_name": agent.agent_name,
        "title": title or f"会话_{session_id[:8]}",
        "status": "active",
        "message_count": 0,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "del_flag": 0,
    }
    await mongodb_client.insert_one("agent_conversation", session_data)

    return BaseResponse(
        success=True,
        message="会话创建成功",
        data={
            "sessionId": session_id,
            "agentId": agent_id,
            "agentName": agent.agent_name,
            "title": session_data["title"],
        }
    )


# ========== 文件上传 API ==========

@router.post("/files/upload")
async def upload_file(
    agent_id: int = Form(..., description="Agent ID"),
    file: UploadFile = File(..., description="上传的文件"),
    session_id: Optional[str] = Form(None, description="会话ID"),
    biz_type: str = Form(default="general", description="业务类型"),
    user_name: Optional[str] = Form(None, description="用户名"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """文件上传接口"""
    allowed_types = [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "image/jpeg",
        "image/png",
    ]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型: {file.content_type}",
        )

    file_content = await file.read()
    file_size = len(file_content)

    file_ext = file.filename.split(".")[-1] if "." in (file.filename or "") else ""
    unique_filename = f"{uuid.uuid4().hex}.{file_ext}"

    import os
    upload_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        "uploads"
    )
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, unique_filename)

    with open(file_path, "wb") as f:
        f.write(file_content)

    file_url = f"/uploads/{unique_filename}"

    file_record = AgentFileAsset(
        agent_id=agent_id,
        session_id=session_id,
        user_name=user_name or current_user.username,
        biz_type=biz_type,
        source_platform="ai-meeting",
        file_name=file.filename or unique_filename,
        file_ext=file_ext,
        content_type=file.content_type,
        file_size=file_size,
        file_url=file_url,
        upload_status=1,
        create_time=datetime.now(timezone.utc),
        update_time=datetime.now(timezone.utc),
        del_flag=0,
    )

    db.add(file_record)
    await db.flush()
    await db.commit()
    await db.refresh(file_record)

    return BaseResponse(
        success=True,
        message="文件上传成功",
        data={
            "id": file_record.id,
            "agentId": file_record.agent_id,
            "sessionId": file_record.session_id,
            "bizType": file_record.biz_type,
            "fileName": file_record.file_name,
            "fileSize": file_record.file_size,
            "contentType": file_record.content_type,
            "fileUrl": file_url,
            "createTime": file_record.create_time.isoformat() if file_record.create_time else None,
        }
    )


# ========== 聊天 API (优化版) ==========

from pydantic import BaseModel


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str
    session_id: Optional[str] = None
    system_prompt: Optional[str] = None


@router.post("/sessions/{session_id}/chat")
async def chat_with_agent(
    session_id: str,
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    """与 Agent 对话（SSE 流式响应）- 优化版"""
    handler = StreamingHandler(session_id=session_id)

    async def event_generator():
        try:
            # 获取消息历史
            messages = await mongodb_client.find_many(
                "agent_conversation",
                {"session_id": session_id, "del_flag": {"$ne": 1}},
                sort=[("created_at", 1)],
                limit=50,
            )

            history = [
                {"role": msg.get("role", "user"), "content": msg.get("content", "")}
                for msg in messages
            ]

            # 添加当前消息
            user_message = request.message
            history.append({"role": "user", "content": user_message})

            # 保存用户消息
            await mongodb_client.insert_one({
                "session_id": session_id,
                "user_id": current_user.id,
                "role": "user",
                "content": user_message,
                "created_at": datetime.now(timezone.utc),
                "del_flag": 0,
            })

            # 发送开始事件
            yield StreamEvent(
                type="start",
                data={"type": "start", "session_id": session_id}
            ).to_sse()

            # 流式获取 AI 响应
            try:
                content_stream = enhanced_ai_client.chat_with_history(
                    messages=history,
                    session_id=session_id,
                    system_prompt=request.system_prompt,
                )

                async for chunk in handler.event_generator(content_stream):
                    yield chunk

            except AIResponseError as e:
                yield create_error_response(e)

        except Exception as e:
            yield create_error_response(e)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/sessions/{session_id}/messages")
async def get_agent_session_messages(
    session_id: str,
    current: int = Query(default=1, ge=1, description="当前页"),
    size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_user),
):
    """获取 Agent 会话消息"""
    skip = (current - 1) * size

    messages = await mongodb_client.find_many(
        "agent_conversation",
        {"session_id": session_id, "del_flag": {"$ne": 1}},
        sort=[("created_at", 1)],
        limit=size,
        skip=skip,
    )

    total = await mongodb_client.count_documents(
        "agent_conversation",
        {"session_id": session_id, "del_flag": {"$ne": 1}}
    )

    return {
        "code": 200,
        "message": "success",
        "data": messages,
        "page_info": {
            "page": current,
            "page_size": size,
            "total": total,
        }
    }


@router.put("/conversations/{session_id}/end")
async def end_agent_conversation(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """结束 Agent 会话"""
    await mongodb_client.update_one(
        "agent_conversation",
        {"session_id": session_id},
        {"status": "ended", "updated_at": datetime.now(timezone.utc)},
    )
    return BaseResponse(success=True, message="会话已结束")
