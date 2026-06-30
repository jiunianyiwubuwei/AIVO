"""添加 agent_file_asset 表的迁移脚本 - MySQL版本"""

import asyncio
from sqlalchemy import text
from app.infrastructure.database.connection import engine


async def run_migration():
    """运行所有迁移"""
    async with engine.begin() as conn:
        print("开始数据库迁移...")

        # 检查并添加 interview_record 表的字段
        columns_to_add = [
            ("interview_record", "interviewer_agent_id", "BIGINT NULL"),
            ("interview_record", "session_snapshot_json", "TEXT NULL"),
            ("interview_record", "resume_content", "TEXT NULL"),
        ]

        for table_name, column_name, column_type in columns_to_add:
            try:
                result = await conn.execute(text(f"""
                    SELECT COUNT(*) FROM information_schema.columns
                    WHERE table_schema = DATABASE()
                    AND table_name = '{table_name}'
                    AND column_name = '{column_name}'
                """))
                count = result.scalar()

                if count == 0:
                    await conn.execute(text(f"""
                        ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}
                    """))
                    print(f"✓ {table_name}.{column_name} 字段已添加")
                else:
                    print(f"- {table_name}.{column_name} 字段已存在")
            except Exception as e:
                print(f"✗ 添加 {table_name}.{column_name} 字段时出错: {e}")

        # 检查并创建 agent_file_asset 表
        result = await conn.execute(text("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name = 'agent_file_asset'
        """))
        count = result.scalar()

        if count > 0:
            print("- agent_file_asset 表已存在，跳过创建")
        else:
            await conn.execute(text("""
                CREATE TABLE agent_file_asset (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    agent_id BIGINT NOT NULL,
                    session_id VARCHAR(64) NULL,
                    user_name VARCHAR(64) NULL,
                    biz_type VARCHAR(32) DEFAULT 'general' NULL,
                    source_platform VARCHAR(32) DEFAULT 'ai-meeting' NULL,
                    file_name VARCHAR(255) NULL,
                    file_ext VARCHAR(32) NULL,
                    content_type VARCHAR(128) NULL,
                    file_size BIGINT DEFAULT 0 NULL,
                    file_url VARCHAR(1024) NULL,
                    upload_status SMALLINT DEFAULT 1 NULL,
                    remark VARCHAR(255) NULL,
                    create_time DATETIME NULL,
                    update_time DATETIME NULL,
                    del_flag SMALLINT DEFAULT 0 NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """))
            print("✓ agent_file_asset 表创建成功!")

            # 创建索引
            await conn.execute(text("""
                CREATE INDEX idx_agent_file_asset_agent_id ON agent_file_asset (agent_id)
            """))
            await conn.execute(text("""
                CREATE INDEX idx_agent_file_asset_session_id ON agent_file_asset (session_id)
            """))
            print("✓ 索引创建成功!")

        print("迁移完成!")


if __name__ == "__main__":
    asyncio.run(run_migration())
