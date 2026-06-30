"""Redis 连接和服务"""

import json
import logging
from typing import Any, Optional

import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis 客户端"""

    _instance: Optional["RedisClient"] = None
    _client: Optional[redis.Redis] = None
    _connected: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self) -> None:
        """连接 Redis"""
        if self._client is None:
            try:
                # 强制使用 RESP2 协议，兼容旧版 Redis 服务器
                self._client = redis.Redis(
                    host=settings.redis.host,
                    port=settings.redis.port,
                    db=settings.redis.db,
                    password=settings.redis.password or None,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=5,
                    protocol=2,  # 强制使用 RESP2 协议
                )
                # 测试连接
                await self._client.ping()
                self._connected = True
                logger.info(f"Redis connected: {settings.redis.host}:{settings.redis.port}")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}. Continuing without Redis.")
                self._client = None
                self._connected = False

    async def close(self) -> None:
        """关闭连接"""
        if self._client:
            try:
                await self._client.close()
            except Exception:
                pass
            self._client = None
            self._connected = False

    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connected and self._client is not None

    @property
    def client(self) -> Optional[redis.Redis]:
        """获取 Redis 客户端（可能为 None）"""
        return self._client

    # ============ 基础操作 ============

    async def get(self, key: str) -> Optional[str]:
        """获取值"""
        if not self.is_connected:
            return None
        try:
            return await self._client.get(key)
        except Exception:
            return None

    async def set(
        self,
        key: str,
        value: str,
        ex: Optional[int] = None,
        px: Optional[int] = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        """设置值"""
        if not self.is_connected:
            return False
        try:
            return await self._client.set(key, value, ex=ex, px=px, nx=nx, xx=xx)
        except Exception:
            return False

    async def delete(self, *keys: str) -> int:
        """删除键"""
        if not self.is_connected or not keys:
            return 0
        try:
            return await self._client.delete(*keys)
        except Exception:
            return 0

    async def exists(self, *keys: str) -> int:
        """检查键是否存在"""
        if not self.is_connected:
            return 0
        try:
            return await self._client.exists(*keys)
        except Exception:
            return 0

    async def expire(self, key: str, seconds: int) -> bool:
        """设置过期时间"""
        if not self.is_connected:
            return False
        try:
            return await self._client.expire(key, seconds)
        except Exception:
            return False

    # ============ JSON 操作 ============

    async def get_json(self, key: str) -> Optional[Any]:
        """获取 JSON 值"""
        data = await self.get(key)
        if data:
            try:
                return json.loads(data)
            except Exception:
                return None
        return None

    async def set_json(
        self,
        key: str,
        value: Any,
        ex: Optional[int] = None,
    ) -> bool:
        """设置 JSON 值"""
        return await self.set(key, json.dumps(value, ensure_ascii=False), ex=ex)

    # ============ 哈希操作 ============

    async def hget(self, key: str, field: str) -> Optional[str]:
        """获取哈希字段值"""
        if not self.is_connected:
            return None
        try:
            return await self._client.hget(key, field)
        except Exception:
            return None

    async def hset(self, key: str, field: str, value: str) -> int:
        """设置哈希字段值"""
        if not self.is_connected:
            return 0
        try:
            return await self._client.hset(key, field, value)
        except Exception:
            return 0

    async def hgetall(self, key: str) -> dict:
        """获取所有哈希字段"""
        if not self.is_connected:
            return {}
        try:
            return await self._client.hgetall(key)
        except Exception:
            return {}

    async def hdel(self, key: str, *fields: str) -> int:
        """删除哈希字段"""
        if not self.is_connected:
            return 0
        try:
            return await self._client.hdel(key, *fields)
        except Exception:
            return 0

    # ============ 分布式锁 ============

    async def acquire_lock(
        self,
        key: str,
        timeout: int = 30,
        token: Optional[str] = None,
    ) -> bool:
        """获取分布式锁"""
        if not self.is_connected:
            # 如果 Redis 未连接，返回 True 允许继续（无锁模式）
            return True

        if token is None:
            import uuid
            token = str(uuid.uuid4())

        lock_key = f"lock:{key}"
        try:
            acquired = await self._client.set(lock_key, token, ex=timeout, nx=True)
            return bool(acquired)
        except Exception:
            return True  # 出错时允许继续

    async def release_lock(self, key: str, token: str) -> bool:
        """释放分布式锁"""
        if not self.is_connected:
            return True

        lock_key = f"lock:{key}"
        try:
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            result = await self._client.eval(lua_script, 1, lock_key, token)
            return result == 1
        except Exception:
            return True

    # ============ 自增/自减 ============

    async def incr(self, key: str, amount: int = 1) -> int:
        """自增"""
        if not self.is_connected:
            return 0
        try:
            return await self._client.incrby(key, amount)
        except Exception:
            return 0

    async def decr(self, key: str, amount: int = 1) -> int:
        """自减"""
        if not self.is_connected:
            return 0
        try:
            return await self._client.decrby(key, amount)
        except Exception:
            return 0


# 全局 Redis 客户端
redis_client = RedisClient()


async def get_redis() -> RedisClient:
    """获取 Redis 客户端的依赖"""
    return redis_client
