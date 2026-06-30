"""Add agent_file_asset table and missing columns

Revision ID: 002_add_file_asset
Revises: 001_initial
Create Date: 2026-06-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '002_add_file_asset'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 重命名 users 表为 t_user（如果不存在）
    op.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='t_user' AND xtype='U')
        BEGIN
            EXEC sp_rename 'users', 't_user'
        END
    """)

    # 修改 t_user 表结构
    op.execute("""
        IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('t_user') AND name = 'deletion_time')
        BEGIN
            ALTER TABLE t_user ADD deletion_time BIGINT NULL
        END
    """)

    # 修改 ai_properties 表结构
    op.execute("""
        IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('ai_properties') AND name = 'api_secret')
        BEGIN
            ALTER TABLE ai_properties ADD api_secret VARCHAR(512) NULL
        END
    """)
    op.execute("""
        IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('ai_properties') AND name = 'project_id')
        BEGIN
            ALTER TABLE ai_properties ADD project_id VARCHAR(255) NULL
        END
    """)
    op.execute("""
        IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('ai_properties') AND name = 'organization_id')
        BEGIN
            ALTER TABLE ai_properties ADD organization_id VARCHAR(255) NULL
        END
    """)

    # 修改 interview_record 表结构
    op.execute("""
        IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('interview_record') AND name = 'interviewer_agent_id')
        BEGIN
            ALTER TABLE interview_record ADD interviewer_agent_id BIGINT NULL
        END
    """)
    op.execute("""
        IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('interview_record') AND name = 'session_snapshot_json')
        BEGIN
            ALTER TABLE interview_record ADD session_snapshot_json TEXT NULL
        END
    """)
    op.execute("""
        IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('interview_record') AND name = 'resume_content')
        BEGIN
            ALTER TABLE interview_record ADD resume_content TEXT NULL
        END
    """)
    op.execute("""
        IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('interview_record') AND name = 'user_id')
        BEGIN
            ALTER TABLE interview_record ALTER COLUMN user_id BIGINT NOT NULL
        END
    """)

    # 创建 agent_file_asset 表
    op.create_table(
        'agent_file_asset',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('agent_id', sa.BigInteger(), nullable=False, comment='智能体ID'),
        sa.Column('session_id', sa.String(length=64), nullable=True, comment='会话ID'),
        sa.Column('user_name', sa.String(length=64), nullable=True, comment='上传用户名'),
        sa.Column('biz_type', sa.String(length=32), server_default='general', nullable=True, comment='业务类型'),
        sa.Column('source_platform', sa.String(length=32), server_default='ai-meeting', nullable=True, comment='来源平台'),
        sa.Column('file_name', sa.String(length=255), nullable=True, comment='原始文件名'),
        sa.Column('file_ext', sa.String(length=32), nullable=True, comment='文件扩展名'),
        sa.Column('content_type', sa.String(length=128), nullable=True, comment='MIME类型'),
        sa.Column('file_size', sa.BigInteger(), server_default='0', nullable=True, comment='文件大小'),
        sa.Column('file_url', sa.String(length=1024), nullable=True, comment='平台返回文件URL'),
        sa.Column('upload_status', sa.SmallInteger(), server_default='1', nullable=True, comment='上传状态'),
        sa.Column('remark', sa.String(length=255), nullable=True, comment='备注'),
        sa.Column('create_time', sa.DateTime(), nullable=True, comment='创建时间'),
        sa.Column('update_time', sa.DateTime(), nullable=True, comment='更新时间'),
        sa.Column('del_flag', sa.SmallInteger(), server_default='0', nullable=True, comment='删除标识'),
        sa.PrimaryKeyConstraint('id'),
    )

    # 创建索引
    op.create_index('idx_agent_file_asset_agent_id', 'agent_file_asset', ['agent_id'])
    op.create_index('idx_agent_file_asset_session_id', 'agent_file_asset', ['session_id'])
    op.create_index('idx_agent_file_asset_user_name', 'agent_file_asset', ['user_name'])
    op.create_index('idx_agent_file_asset_biz_type', 'agent_file_asset', ['biz_type'])


def downgrade() -> None:
    op.drop_index('idx_agent_file_asset_biz_type', table_name='agent_file_asset')
    op.drop_index('idx_agent_file_asset_user_name', table_name='agent_file_asset')
    op.drop_index('idx_agent_file_asset_session_id', table_name='agent_file_asset')
    op.drop_index('idx_agent_file_asset_agent_id', table_name='agent_file_asset')
    op.drop_table('agent_file_asset')
