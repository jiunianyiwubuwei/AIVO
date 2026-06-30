"""initial migration

Revision ID: 001_initial
Revises:
Create Date: 2026-06-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建用户表
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=256), nullable=False),
        sa.Column('password', sa.String(length=512), nullable=True),
        sa.Column('real_name', sa.String(length=256), nullable=True),
        sa.Column('phone', sa.String(length=128), nullable=True),
        sa.Column('mail', sa.String(length=512), nullable=True),
        sa.Column('create_time', sa.DateTime(), nullable=True),
        sa.Column('update_time', sa.DateTime(), nullable=True),
        sa.Column('del_flag', sa.Integer(), server_default='0', nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
    )

    # 创建 AI 配置表
    op.create_table(
        'ai_properties',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ai_name', sa.String(length=256), nullable=True),
        sa.Column('ai_type', sa.String(length=128), nullable=True),
        sa.Column('api_key', sa.String(length=512), nullable=True),
        sa.Column('api_url', sa.String(length=512), nullable=True),
        sa.Column('model_name', sa.String(length=256), nullable=True),
        sa.Column('max_tokens', sa.Integer(), server_default='4096', nullable=True),
        sa.Column('temperature', sa.Float(), server_default='0.7', nullable=True),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('is_enabled', sa.Integer(), server_default='1', nullable=True),
        sa.Column('enable_thinking', sa.Integer(), server_default='0', nullable=True),
        sa.Column('thinking_budget_tokens', sa.Integer(), nullable=True),
        sa.Column('del_flag', sa.Integer(), server_default='0', nullable=False),
        sa.Column('create_time', sa.DateTime(), nullable=True),
        sa.Column('update_time', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # 创建 Agent 配置表
    op.create_table(
        'agent_properties',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('agent_name', sa.String(length=256), nullable=True),
        sa.Column('api_secret', sa.String(length=512), nullable=True),
        sa.Column('api_key', sa.String(length=512), nullable=True),
        sa.Column('api_flow_id', sa.String(length=256), nullable=True),
        sa.Column('ai_mode', sa.String(length=64), server_default='workflow', nullable=True),
        sa.Column('ai_properties_id', sa.Integer(), nullable=True),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('del_flag', sa.Integer(), server_default='0', nullable=False),
        sa.Column('create_time', sa.DateTime(), nullable=True),
        sa.Column('update_time', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['ai_properties_id'], ['ai_properties.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # 创建面试记录表
    op.create_table(
        'interview_record',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('session_id', sa.String(length=256), nullable=True),
        sa.Column('interview_score', sa.Integer(), nullable=True),
        sa.Column('resume_score', sa.Integer(), nullable=True),
        sa.Column('interview_status', sa.String(length=64), nullable=True),
        sa.Column('question_count', sa.Integer(), nullable=True),
        sa.Column('interview_direction', sa.String(length=256), nullable=True),
        sa.Column('start_time', sa.DateTime(), nullable=True),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('interview_suggestions', sa.Text(), nullable=True),
        sa.Column('create_time', sa.DateTime(), nullable=True),
        sa.Column('update_time', sa.DateTime(), nullable=True),
        sa.Column('del_flag', sa.Integer(), server_default='0', nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id'),
    )

    # 创建索引
    op.create_index('idx_user_username', 'users', ['username'])
    op.create_index('idx_session_id', 'interview_record', ['session_id'])
    op.create_index('idx_user_id', 'interview_record', ['user_id'])


def downgrade() -> None:
    op.drop_index('idx_user_id', table_name='interview_record')
    op.drop_index('idx_session_id', table_name='interview_record')
    op.drop_index('idx_user_username', table_name='users')
    op.drop_table('interview_record')
    op.drop_table('agent_properties')
    op.drop_table('ai_properties')
    op.drop_table('users')
