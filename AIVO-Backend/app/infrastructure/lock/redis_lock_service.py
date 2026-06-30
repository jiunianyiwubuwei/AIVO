"""Redis 分布式锁服务"""

import asyncio
import logging
import secrets
import time
from typing import Optional

from app.infrastructure.cache.redis_client import get_redis

logger = logging.getLogger(__name__)

_DEFAULT_LOCK_PREFIX = "interview:ai:lock:"


class RedisLockService:
    """Redis 分布式锁服务"""

    def __init__(
        self,
        prefix: str = _DEFAULT_LOCK_PREFIX,
        default_ttl_seconds: int = 30,
        retry_count: int = 3,
        retry_delay_seconds: float = 0.05,
    ):
        self.prefix = prefix
        self.default_ttl_seconds = default_ttl_seconds
        self.retry_count = max(retry_count, 0)
        self.retry_delay_seconds = retry_delay_seconds

    def _make_key(self, lock_key: str) -> str:
        return f"{self.prefix}{lock_key}"

    def _token(self) -> str:
        return secrets.token_hex(8)

    async def acquire(
        self,
        lock_key: str,
        ttl_seconds: Optional[int] = None,
        retry_count: Optional[int] = None,
    ) -> Optional[str]:
        lock_name = self._make_key(lock_key)
        token = self._token()
        effective_ttl = ttl_seconds if ttl_seconds and ttl_seconds > 0 else self.default_ttl_seconds
        attempts = retry_count if retry_count is not None else self.retry_count

        redis_client = get_redis()
        if not redis_client.is_connected:
            logger.debug("Redis not connected, lock acquired in no-op mode for %s", lock_name)
            return token

        for index in range(attempts + 1):
            acquired = await redis_client.client.set(
                lock_name,
                token,
                ex=effective_ttl,
                nx=True,
            )
            if acquired:
                logger.debug("Acquired lock %s", lock_name)
                return token
            if index < attempts:
                await asyncio.sleep(self.retry_delay_seconds)

        logger.warning("Failed to acquire lock %s after %s attempts", lock_name, attempts)
        return None

    async def release(self, lock_key: str, token: str) -> bool:
        lock_name = self._make_key(lock_key)
        redis_client = get_redis()
        if not redis_client.is_connected:
            return False

        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
          return redis.call("del", KEYS[1])
        else
          return 0
        end
        """
        try:
            result = await redis_client.client.eval(script, 1, lock_name, token)
            released = result == 1
            logger.debug("Released lock %s success=%s", lock_name, released)
            return released
        except Exception as exc:
            logger.exception("Release lock failed %s", lock_name)
            return False

    async def extend(self, lock_key: str, token: str, ttl_seconds: Optional[int] = None) -> bool:
        lock_name = self._make_key(lock_key)
        effective_ttl = ttl_seconds if ttl_seconds and ttl_seconds > 0 else self.default_ttl_seconds
        redis_client = get_redis()
        if not redis_client.is_connected:
            return False

        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
          return redis.call("expire", KEYS[1], ARGV[2])
        else
          return 0
        end
        """
        try:
            result = await redis_client.client.eval(script, 1, lock_name, token, effective_ttl)
            return result == 1
        except Exception as exc:
            logger.exception("Extend lock failed %s", lock_name)
            return False

    async def is_locked(self, lock_key: str) -> bool:
        lock_name = self._make_key(lock_key)
        redis_client = get_redis()
        if not redis_client.is_connected:
            return False

        try:
            exists = await redis_client.client.exists(lock_name)
            return exists == 1
        except Exception:
            return False

    async def with_lock(
        self,
        lock_key: str,
        coro,
        *,
        ttl_seconds: Optional[int] = None,
        retry_count: Optional[int] = None,
    ):
        token = await self.acquire(lock_key, ttl_seconds=ttl_seconds, retry_count=retry_count)
        if token is None:
            raise RuntimeError(f"acquire lock failed: {self._make_key(lock_key)}")

        try:
            return await coro()
        finally:
            await self.release(lock_key, token)


redis_lock_service = RedisLockService()
