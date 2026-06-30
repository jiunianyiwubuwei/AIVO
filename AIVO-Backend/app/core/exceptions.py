"""全局异常处理器"""

from typing import Union

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppException(Exception):
    """应用异常基类"""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail: str = None,
    ):
        self.message = message
        self.status_code = status_code
        self.detail = detail or message
        super().__init__(self.message)


class NotFoundException(AppException):
    """资源不存在异常"""

    def __init__(self, message: str = "资源不存在"):
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class UnauthorizedException(AppException):
    """未授权异常"""

    def __init__(self, message: str = "未授权"):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenException(AppException):
    """禁止访问异常"""

    def __init__(self, message: str = "禁止访问"):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class BadRequestException(AppException):
    """请求错误异常"""

    def __init__(self, message: str = "请求错误"):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器"""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        """应用异常处理"""
        logger.error(
            f"AppException: {exc.message}",
            extra={"path": request.url.path, "status": exc.status_code}
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.status_code,
                "message": exc.message,
                "detail": exc.detail,
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """请求验证异常处理"""
        logger.warning(
            f"Validation error: {exc.errors()}",
            extra={"path": request.url.path}
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "code": 422,
                "message": "请求参数验证失败",
                "detail": exc.errors(),
            }
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        """数据库异常处理"""
        logger.exception(f"Database error: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "code": 500,
                "message": "数据库错误",
                "detail": "数据库操作失败，请稍后重试",
            }
        )

    @app.exception_handler(ValidationError)
    async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
        """Pydantic 验证异常处理"""
        logger.warning(f"Pydantic validation error: {exc.errors()}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "code": 500,
                "message": "数据验证错误",
                "detail": exc.errors(),
            }
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """通用异常处理"""
        logger.exception(f"Unhandled exception: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "code": 500,
                "message": "服务器内部错误",
                "detail": "发生未知错误，请联系管理员",
            }
        )
