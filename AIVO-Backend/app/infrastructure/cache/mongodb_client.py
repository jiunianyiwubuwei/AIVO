"""MongoDB 连接和服务"""

from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings


class MongoDBClient:
    """MongoDB 客户端"""

    _instance: Optional["MongoDBClient"] = None
    _client: Optional[AsyncIOMotorClient] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self) -> None:
        """连接 MongoDB"""
        if self._client is None:
            self._client = AsyncIOMotorClient(
                settings.mongodb.uri,
                maxPoolSize=50,
                minPoolSize=10,
            )

    async def close(self) -> None:
        """关闭连接"""
        if self._client:
            self._client.close()
            self._client = None

    @property
    def database(self) -> AsyncIOMotorDatabase:
        """获取数据库"""
        if self._client is None:
            raise RuntimeError("MongoDB not connected. Call connect() first.")
        return self._client[settings.mongodb.database]

    # ============ 集合访问 ============

    @property
    def conversations(self):
        """对话消息集合"""
        return self.database.conversations

    @property
    def interview_snapshots(self):
        """面试快照集合"""
        return self.database.interview_snapshots

    @property
    def turn_logs(self):
        """轮次日志集合"""
        return self.database.turn_logs

    @property
    def agent_messages(self):
        """Agent 消息集合"""
        return self.database.agent_messages

    # ============ 通用操作 ============

    async def find_one(
        self,
        collection: str,
        filter_dict: dict,
        projection: Optional[dict] = None,
    ) -> Optional[dict]:
        """查询单条"""
        coll = getattr(self.database, collection)
        return await coll.find_one(filter_dict, projection)

    async def find_many(
        self,
        collection: str,
        filter_dict: dict,
        projection: Optional[dict] = None,
        sort: Optional[list] = None,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
    ) -> list[dict]:
        """查询多条"""
        coll = getattr(self.database, collection)
        cursor = coll.find(filter_dict, projection)
        if sort:
            cursor = cursor.sort(sort)
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        return await cursor.to_list(length=limit)

    async def insert_one(
        self,
        collection: str,
        document: dict,
    ) -> str:
        """插入单条"""
        coll = getattr(self.database, collection)
        result = await coll.insert_one(document)
        return str(result.inserted_id)

    async def update_one(
        self,
        collection: str,
        filter_dict: dict,
        update: dict,
        upsert: bool = False,
    ) -> int:
        """更新单条"""
        coll = getattr(self.database, collection)
        # 检查是否包含 MongoDB 操作符（如 $push, $inc, $set 等）
        if any(key.startswith("$") for key in update.keys()):
            # 如果直接包含操作符，直接使用
            result = await coll.update_one(filter_dict, update, upsert=upsert)
        else:
            # 否则包装为 $set
            result = await coll.update_one(filter_dict, {"$set": update}, upsert=upsert)
        return result.modified_count

    async def delete_one(
        self,
        collection: str,
        filter_dict: dict,
    ) -> int:
        """删除单条"""
        coll = getattr(self.database, collection)
        result = await coll.delete_one(filter_dict)
        return result.deleted_count

    async def count_documents(
        self,
        collection: str,
        filter_dict: dict,
    ) -> int:
        """统计文档数量"""
        coll = getattr(self.database, collection)
        return await coll.count_documents(filter_dict)


# 全局 MongoDB 客户端
mongodb_client = MongoDBClient()


async def get_mongodb() -> MongoDBClient:
    """获取 MongoDB 客户端的依赖"""
    return mongodb_client
