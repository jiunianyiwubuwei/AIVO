"""数据库连接模块"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

# 创建异步引擎
engine = create_async_engine(
    settings.database.url,
    echo=settings.app.debug,
    pool_size=settings.database.pool_size,
    pool_recycle=settings.database.pool_recycle,
    pool_pre_ping=True,
)

# 创建会话工厂
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话的依赖"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# 创建会话工厂 (alias for compatibility)
async_session_maker = async_session_factory


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话的上下文管理器"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """初始化数据库连接池"""
    async with engine.begin() as conn:
        # 可以在这里执行表创建等初始化操作
        # 由于复用现有表，这里不需要创建表
        pass


async def close_db():
    """关闭数据库连接"""
    await engine.dispose()
