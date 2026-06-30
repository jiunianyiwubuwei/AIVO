"""用户相关 Schema"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., min_length=1, max_length=256, description="用户名")
    password: str = Field(..., min_length=1, description="密码")


class LoginResponse(BaseModel):
    """登录响应"""
    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    user_id: int = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    real_name: Optional[str] = Field(default=None, description="真实姓名")


class RegisterRequest(BaseModel):
    """注册请求"""
    username: str = Field(..., min_length=3, max_length=256, description="用户名")
    password: str = Field(..., min_length=6, max_length=256, description="密码")
    real_name: Optional[str] = Field(default=None, max_length=256, description="真实姓名")
    phone: Optional[str] = Field(default=None, max_length=128, description="手机号")
    mail: Optional[str] = Field(default=None, max_length=512, description="邮箱")


class UserInfo(BaseModel):
    """用户信息"""
    id: int = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    real_name: Optional[str] = Field(default=None, description="真实姓名")
    phone: Optional[str] = Field(default=None, description="手机号")
    mail: Optional[str] = Field(default=None, description="邮箱")
    create_time: Optional[datetime] = Field(default=None, description="创建时间")

    class Config:
        from_attributes = True


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, description="新密码")


class UserPageRequest(BaseModel):
    """用户分页请求"""
    skip: int = Field(default=0, ge=0, description="跳过数量")
    limit: int = Field(default=20, ge=1, le=100, description="返回数量")
    username: Optional[str] = Field(default=None, description="用户名(模糊)")
    real_name: Optional[str] = Field(default=None, description="真实姓名(模糊)")


class UserListResponse(BaseModel):
    """用户分页响应"""
    items: list[UserInfo] = Field(..., description="用户列表")
    total: int = Field(..., description="总数")
    skip: int = Field(..., description="跳过数量")
    limit: int = Field(..., description="返回数量")


class UpdateUserRequest(BaseModel):
    """更新用户信息请求"""
    real_name: Optional[str] = Field(default=None, description="真实姓名")
    phone: Optional[str] = Field(default=None, description="手机号")
    mail: Optional[str] = Field(default=None, description="邮箱")
    del_flag: Optional[int] = Field(default=None, description="删除标识")
