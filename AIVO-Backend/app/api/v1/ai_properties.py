"""AI Properties API (无前缀路由，兼容前端)"""

from fastapi import APIRouter, Depends, Query
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.infrastructure.database.models import User
from app.infrastructure.database.connection import get_db
from app.core.schemas.agent import AiPropertiesResponse
from app.core.schemas.response import BaseListResponse, BaseResponse
from app.application.agent.agent_service import AiPropertiesService

router = APIRouter()


def get_ai_properties_service(db: AsyncSession = Depends(get_db)) -> AiPropertiesService:
    return AiPropertiesService(db)


@router.get("/ai-properties", response_model=BaseListResponse[AiPropertiesResponse])
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

    return BaseListResponse(
        data=[AiPropertiesResponse.model_validate(item) for item in items]
    )


@router.post("/ai-properties", response_model=BaseResponse[AiPropertiesResponse])
async def create_ai_property(
    create_data: dict,
    service: AiPropertiesService = Depends(get_ai_properties_service),
    current_user: User = Depends(get_current_user),
):
    """创建 AI 模型配置"""
    from app.infrastructure.database.models import AiProperties
    new_ai = AiProperties(**create_data)
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
    from fastapi import HTTPException
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
    from fastapi import HTTPException
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
    from fastapi import HTTPException
    ai_prop = await service.get_ai_property(ai_id)
    if ai_prop is None:
        raise HTTPException(status_code=404, detail="AI 配置不存在")

    ai_prop.is_enabled = isEnabled
    await service.db.flush()
    return BaseResponse(data=AiPropertiesResponse.model_validate(ai_prop))
