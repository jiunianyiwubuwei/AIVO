"""用户 API"""

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.schemas.user import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UpdateUserRequest,
    UserInfo,
    UserListResponse,
    UserPageRequest,
)
from app.core.schemas.response import BaseResponse
from app.core.security import get_current_user
from app.infrastructure.cache.redis_client import redis_client
from app.infrastructure.database.connection import get_db
from app.infrastructure.database.models import User
from app.application.user.user_service import UserService

router = APIRouter()


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    """获取用户服务"""
    return UserService(db)


@router.post("/login", response_model=BaseResponse[LoginResponse])
async def login(
    request: LoginRequest,
    service: UserService = Depends(get_user_service),
):
    """用户登录"""
    user = await service.authenticate(request.username, request.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    token = service.create_token(user)

    return BaseResponse(
        data=LoginResponse(
            access_token=token,
            user_id=user.id,
            username=user.username or "",
            real_name=user.real_name,
        )
    )


@router.post("/register", response_model=BaseResponse[UserInfo])
async def register(
    request: RegisterRequest,
    service: UserService = Depends(get_user_service),
):
    """用户注册"""
    existing_user = await service.get_by_username(request.username)
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在",
        )

    user = await service.create(
        username=request.username,
        password=request.password,
        real_name=request.real_name,
        phone=request.phone,
        mail=request.mail,
    )

    return BaseResponse(data=UserInfo.model_validate(user))


@router.get("/me", response_model=BaseResponse[UserInfo])
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """获取当前用户信息"""
    return BaseResponse(data=UserInfo.model_validate(current_user))


@router.get("/check-login", response_model=BaseResponse[UserInfo])
async def check_login(
    current_user: User = Depends(get_current_user),
):
    """检查登录状态"""
    return BaseResponse(data=UserInfo.model_validate(current_user))


@router.get("/{user_id}", response_model=BaseResponse[UserInfo])
async def get_user(
    user_id: int,
    service: UserService = Depends(get_user_service),
):
    """获取用户信息"""
    user = await service.get_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )
    return BaseResponse(data=UserInfo.model_validate(user))


@router.post("/logout", response_model=BaseResponse[bool])
async def logout(
    current_user: User = Depends(get_current_user),
):
    """用户登出"""
    token = ""
    return BaseResponse(data=True)


@router.get("/check-username", response_model=BaseResponse[bool])
async def check_username(
    username: str,
    service: UserService = Depends(get_user_service),
):
    """检查用户名是否已存在"""
    exists = await service.is_username_exists(username)
    return BaseResponse(data=exists)


@router.post("/list", response_model=BaseResponse[UserListResponse])
async def list_users(
    request: UserPageRequest = Body(...),
    service: UserService = Depends(get_user_service),
):
    """用户分页列表"""
    users, total = await service.list_users(
        username=request.username,
        real_name=request.real_name,
        skip=request.skip,
        limit=request.limit,
    )
    return BaseResponse(
        data=UserListResponse(
            items=[UserInfo.model_validate(item) for item in users],
            total=total,
            skip=request.skip,
            limit=request.limit,
        )
    )


@router.put("/{user_id}", response_model=BaseResponse[UserInfo])
async def update_user(
    user_id: int,
    request: UpdateUserRequest = Body(...),
    service: UserService = Depends(get_user_service),
):
    """更新用户信息"""
    user = await service.update_user(
        user_id,
        real_name=request.real_name,
        phone=request.phone,
        mail=request.mail,
        del_flag=request.del_flag,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )
    return BaseResponse(data=UserInfo.model_validate(user))


@router.delete("/{user_id}", response_model=BaseResponse[bool])
async def delete_user(
    user_id: int,
    service: UserService = Depends(get_user_service),
):
    """删除用户"""
    success = await service.delete_user(user_id, soft=True)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )
    return BaseResponse(data=True)


@router.post("/change-password", response_model=BaseResponse[bool])
async def change_password(
    request: ChangePasswordRequest = Body(...),
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    """修改密码"""
    user = await service.authenticate(current_user.username, request.old_password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="旧密码错误",
        )
    success = await service.update_password(user.id, request.new_password)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="修改密码失败",
        )
    return BaseResponse(data=True)
