"""缓存模块初始化"""

from app.infrastructure.cache.redis_client import redis_client, RedisClient, get_redis
from app.infrastructure.cache.mongodb_client import mongodb_client, MongoDBClient, get_mongodb

__all__ = [
    "redis_client",
    "RedisClient",
    "get_redis",
    "mongodb_client",
    "MongoDBClient",
    "get_mongodb",
]
