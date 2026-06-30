"""通用响应模式"""

from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class BaseResponse(BaseModel, Generic[T]):
    """通用响应"""
    code: int = Field(default=200, description="状态码")
    message: str = Field(default="success", description="消息")
    data: Optional[T] = Field(default=None, description="数据")
    success: bool = Field(default=True, description="是否成功")


class BaseListResponse(BaseModel, Generic[T]):
    """通用列表响应"""
    code: int = Field(default=200, description="状态码")
    message: str = Field(default="success", description="消息")
    data: list[T] = Field(default_factory=list, description="数据列表")
    success: bool = Field(default=True, description="是否成功")


class PageInfo(BaseModel):
    """分页信息"""
    page: int = Field(default=1, description="当前页")
    page_size: int = Field(default=20, description="每页数量")
    total: int = Field(default=0, description="总数")


class PageResponse(BaseResponse[T]):
    """分页响应"""
    page_info: Optional[PageInfo] = Field(default=None, description="分页信息")


class ErrorResponse(BaseModel):
    """错误响应"""
    code: int = Field(default=500, description="错误码")
    message: str = Field(..., description="错误消息")
    detail: Optional[str] = Field(default=None, description="详细错误")
