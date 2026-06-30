"""数据库迁移脚本"""

import asyncio
from sqlalchemy import text
from app.infrastructure.database.connection import engine, get_db
from app.infrastructure.database.models import Base


async def create_tables():
    """创建所有表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("All tables created successfully!")


async def drop_tables():
    """删除所有表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("All tables dropped!")


async def init_database():
    """初始化数据库"""
    print("Initializing database...")

    # 创建表
    await create_tables()

    # 插入初始数据
    async for db in get_db():
        try:
            # 检查是否已有数据
            result = await db.execute(text("SELECT COUNT(*) FROM t_user"))
            count = result.scalar()

            if count == 0:
                # 插入默认管理员
                from app.core.security import hash_password
                await db.execute(
                    text("""
                        INSERT INTO t_user (username, password, real_name, create_time, update_time, del_flag)
                        VALUES (:username, :password, :real_name, NOW(), NOW(), 0)
                    """),
                    {
                        "username": "admin",
                        "password": hash_password("admin123"),
                        "real_name": "管理员",
                    }
                )

                # 插入默认 AI 配置
                await db.execute(
                    text("""
                        INSERT INTO ai_properties (ai_name, ai_type, api_key, api_url, model_name, max_tokens, temperature, is_enabled, del_flag, create_time)
                        VALUES (:ai_name, :ai_type, :api_key, :api_url, :model_name, :max_tokens, :temperature, :is_enabled, 0, NOW())
                    """),
                    {
                        "ai_name": "OpenAI GPT-4",
                        "ai_type": "openai",
                        "api_key": "",
                        "api_url": "https://api.openai.com/v1",
                        "model_name": "gpt-4",
                        "max_tokens": 4096,
                        "temperature": 0.7,
                        "is_enabled": 1,
                    }
                )

                # 插入默认 Agent 配置
                await db.execute(
                    text("""
                        INSERT INTO agent_properties (agent_name, ai_mode, ai_properties_id, del_flag, create_time)
                        VALUES (:agent_name, :ai_mode, :ai_properties_id, 0, NOW())
                    """),
                    {
                        "agent_name": "默认面试官",
                        "ai_mode": "workflow",
                        "ai_properties_id": 1,
                    }
                )

                await db.commit()
                print("Initial data inserted!")
            else:
                print("Database already has data, skipping initialization.")

        except Exception as e:
            print(f"Error initializing database: {e}")
            await db.rollback()
            raise

    print("Database initialization completed!")


if __name__ == "__main__":
    asyncio.run(init_database())
