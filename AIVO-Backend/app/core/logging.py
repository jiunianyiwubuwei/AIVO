"""日志配置模块"""

import logging
import sys
from typing import Optional

from app.core.config import settings


def setup_logging(
    level: Optional[str] = None,
    log_file: Optional[str] = None,
) -> None:
    """配置日志"""
    log_level = level or getattr(settings.app, "debug", False) and "DEBUG" or "INFO"

    # 日志格式
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # 配置根日志
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())

    # 清除已有的处理器
    root_logger.handlers.clear()

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level.upper())
    console_formatter = logging.Formatter(log_format, date_format)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # 文件处理器（如果指定）
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(log_level.upper())
        file_formatter = logging.Formatter(log_format, date_format)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # 第三方库日志级别 - 静默处理
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("litellm").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


class Logger:
    """日志记录器封装"""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def debug(self, msg: str, **kwargs):
        """调试日志"""
        self.logger.debug(msg, **kwargs)

    def info(self, msg: str, **kwargs):
        """信息日志"""
        self.logger.info(msg, **kwargs)

    def warning(self, msg: str, **kwargs):
        """警告日志"""
        self.logger.warning(msg, **kwargs)

    def error(self, msg: str, **kwargs):
        """错误日志"""
        self.logger.error(msg, **kwargs)

    def critical(self, msg: str, **kwargs):
        """严重错误日志"""
        self.logger.critical(msg, **kwargs)

    def exception(self, msg: str, **kwargs):
        """异常日志（包含堆栈）"""
        self.logger.exception(msg, **kwargs)


def get_logger(name: str) -> Logger:
    """获取日志记录器"""
    return Logger(name)
