"""布隆过滤器服务"""

import logging
import math
from typing import Optional

from app.infrastructure.cache.redis_client import get_redis

logger = logging.getLogger(__name__)

_DEFAULT_BLOOM_PREFIX = "bloom:"


class BloomFilterService:
    """Redis 布隆过滤器服务"""

    def __init__(
        self,
        prefix: str = _DEFAULT_BLOOM_PREFIX,
        expected_items: int = 100_000,
        false_positive_rate: float = 0.01,
    ):
        self.prefix = prefix
        self.expected_items = max(expected_items, 1)
        self.false_positive_rate = max(false_positive_rate, 1e-12)
        self._bits = self._calc_bits()
        self._hashes = self._calc_hashes()

    def _make_key(self, filter_name: str) -> str:
        return f"{self.prefix}{filter_name}"

    def _calc_bits(self) -> int:
        return min(
            max(
                int(-self.expected_items * math.log(self.false_positive_rate) / (math.log(2) ** 2)),
                64,
            ),
            1 << 29,
        )

    def _calc_hashes(self) -> int:
        return max(1, int(round(self._bits / self.expected_items * math.log(2))))

    def _hash_positions(self, filter_name: str, value: str):
        key = self._make_key(filter_name)
        positions = []
        for index in range(self._hashes):
            digest = hash((key, index, value))
            positions.append(digest % self._bits)
        return positions

    async def add(self, filter_name: str, value: str) -> bool:
        redis_client = get_redis()
        if not redis_client.is_connected:
            return False

        key = self._make_key(filter_name)
        positions = self._hash_positions(filter_name, value)
        try:
            async with redis_client.client.pipeline() as pipe:
                for position in positions:
                    await pipe.setbit(key, position, 1)
                await pipe.execute()
            return True
        except Exception as exc:
            logger.exception("Bloom filter add failed %s", key)
            return False

    async def contains(self, filter_name: str, value: str) -> bool:
        redis_client = get_redis()
        if not redis_client.is_connected:
            return False

        key = self._make_key(filter_name)
        positions = self._hash_positions(filter_name, value)
        try:
            async with redis_client.client.pipeline() as pipe:
                for position in positions:
                    await pipe.getbit(key, position)
                results = await pipe.execute()
            return all(bool(bit) for bit in results)
        except Exception as exc:
            logger.exception("Bloom filter contains failed %s", key)
            return False

    async def delete(self, filter_name: str) -> bool:
        redis_client = get_redis()
        if not redis_client.is_connected:
            return False
        try:
            return bool(await redis_client.client.delete(self._make_key(filter_name)))
        except Exception as exc:
            logger.exception("Bloom filter delete failed %s", filter_name)
            return False

    async def ensure_index(self, filter_name: str) -> bool:
        redis_client = get_redis()
        if not redis_client.is_connected:
            return False

        key = self._make_key(filter_name)
        try:
            exists = await redis_client.client.exists(key)
            if exists:
                return True

            normalized = "xunzhi-bloom-index"
            positions = self._hash_positions(filter_name, normalized)
            async with redis_client.client.pipeline() as pipe:
                for position in positions:
                    await pipe.setbit(key, position, 1)
                await pipe.execute()
            return True
        except Exception as exc:
            logger.exception("Bloom filter init index failed %s", filter_name)
            return False


bloom_filter_service = BloomFilterService()
