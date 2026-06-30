"""SQLAlchemy 模型 - 复用现有 mianshi_agent 数据库表结构"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, SmallInteger, String, Text, DECIMAL
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """模型基类"""
    pass


# ============================================================
# 用户表 t_user
# ============================================================
class User(Base):
    """用户表"""
    __tablename__ = "t_user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment="ID")
    username: Mapped[Optional[str]] = mapped_column(String(256), unique=True, comment="用户名")
    password: Mapped[Optional[str]] = mapped_column(String(512), comment="密码")
    real_name: Mapped[Optional[str]] = mapped_column(String(256), comment="真实姓名")
    phone: Mapped[Optional[str]] = mapped_column(String(128), comment="手机号")
    mail: Mapped[Optional[str]] = mapped_column(String(512), comment="邮箱")
    deletion_time: Mapped[Optional[int]] = mapped_column(BigInteger, comment="注销时间戳")
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="创建时间")
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="修改时间")
    del_flag: Mapped[Optional[int]] = mapped_column(SmallInteger, comment="删除标识 0：未删除 1：已删除")


# ============================================================
# Agent配置表 agent_properties
# ============================================================
class AgentProperties(Base):
    """AI Agent 配置表"""
    __tablename__ = "agent_properties"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment="ID")
    agent_name: Mapped[Optional[str]] = mapped_column(String(256), comment="智能体名称")
    api_secret: Mapped[Optional[str]] = mapped_column(String(256), comment="鉴权密钥")
    api_key: Mapped[Optional[str]] = mapped_column(String(512), comment="鉴权key")
    api_flow_id: Mapped[Optional[str]] = mapped_column(String(256), comment="星火工作流ID")
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="创建时间")
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="修改时间")
    del_flag: Mapped[Optional[int]] = mapped_column(SmallInteger, comment="删除标识")
    # 新增字段
    ai_mode: Mapped[Optional[str]] = mapped_column(String(20), default="workflow", comment="模式：workflow-星火工作流, direct-直连模型")
    ai_properties_id: Mapped[Optional[int]] = mapped_column(BigInteger, comment="绑定的ai_properties ID")
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, comment="系统提示词")


# ============================================================
# AI模型配置表 ai_properties
# ============================================================
class AiProperties(Base):
    """AI 模型配置表"""
    __tablename__ = "ai_properties"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment="ID")
    ai_name: Mapped[Optional[str]] = mapped_column(String(256), comment="AI名称")
    ai_type: Mapped[Optional[str]] = mapped_column(String(64), comment="AI类型：spark、openai、claude等")
    api_key: Mapped[Optional[str]] = mapped_column(String(512), comment="API密钥")
    api_secret: Mapped[Optional[str]] = mapped_column(String(512), comment="API密钥（部分AI需要）")
    api_url: Mapped[Optional[str]] = mapped_column(String(512), comment="API地址")
    model_name: Mapped[Optional[str]] = mapped_column(String(256), comment="模型名称")
    max_tokens: Mapped[Optional[int]] = mapped_column(Integer, default=4096, comment="最大token数")
    temperature: Mapped[Optional[float]] = mapped_column(DECIMAL(3, 2), default=0.70, comment="温度参数")
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, comment="系统提示词")
    is_enabled: Mapped[Optional[int]] = mapped_column(SmallInteger, default=1, comment="是否启用")
    enable_thinking: Mapped[Optional[int]] = mapped_column(SmallInteger, default=0, comment="是否开启思考模式")
    thinking_budget_tokens: Mapped[Optional[int]] = mapped_column(Integer, comment="思考模式预算Token数")
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="创建时间")
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="修改时间")
    del_flag: Mapped[Optional[int]] = mapped_column(SmallInteger, default=0, comment="删除标识")
    project_id: Mapped[Optional[str]] = mapped_column(String(255), comment="项目ID")
    organization_id: Mapped[Optional[str]] = mapped_column(String(255), comment="组织ID")


# ============================================================
# 面试记录表 interview_record
# ============================================================
class InterviewRecord(Base):
    """面试记录表"""
    __tablename__ = "interview_record"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment="主键ID")
    user_id: Mapped[int] = mapped_column(BigInteger, comment="用户ID")
    session_id: Mapped[Optional[str]] = mapped_column(String(64), comment="会话ID")
    interview_score: Mapped[Optional[int]] = mapped_column(Integer, comment="面试得分")
    resume_score: Mapped[Optional[int]] = mapped_column(Integer, comment="简历得分")
    interview_status: Mapped[Optional[str]] = mapped_column(String(32), comment="面试状态")
    question_count: Mapped[Optional[int]] = mapped_column(Integer, comment="面试题数量")
    interviewer_agent_id: Mapped[Optional[int]] = mapped_column(BigInteger, comment="面试官Agent ID")
    interview_suggestions: Mapped[Optional[str]] = mapped_column(Text, comment="面试建议")
    interview_direction: Mapped[Optional[str]] = mapped_column(String(128), comment="面试方向")
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="开始时间")
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="结束时间")
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, comment="面试时长(秒)")
    session_snapshot_json: Mapped[Optional[str]] = mapped_column(Text, comment="会话快照JSON")
    resume_content: Mapped[Optional[str]] = mapped_column(Text, comment="简历内容")
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="创建时间")
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="更新时间")
    del_flag: Mapped[Optional[int]] = mapped_column(SmallInteger, default=0, comment="删除标记")


# ============================================================
# Agent标签表 agent_tag
# ============================================================
class AgentTag(Base):
    """智能体标签表"""
    __tablename__ = "agent_tag"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment="ID")
    tag_name: Mapped[Optional[str]] = mapped_column(String(256), comment="标签名称")
    agent_id: Mapped[int] = mapped_column(BigInteger, comment="关联的智能体ID")
    description: Mapped[Optional[str]] = mapped_column(String(512), comment="标签描述")
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="创建时间")
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="修改时间")
    del_flag: Mapped[Optional[int]] = mapped_column(SmallInteger, default=0, comment="删除标识")


# ============================================================
# 文件资产表 agent_file_asset
# ============================================================
class AgentFileAsset(Base):
    """星辰上传文件持久化表"""
    __tablename__ = "agent_file_asset"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment="主键ID")
    agent_id: Mapped[int] = mapped_column(BigInteger, comment="智能体ID")
    session_id: Mapped[Optional[str]] = mapped_column(String(64), comment="会话ID")
    user_name: Mapped[Optional[str]] = mapped_column(String(64), comment="上传用户名")
    biz_type: Mapped[Optional[str]] = mapped_column(String(32), default="general", comment="业务类型")
    source_platform: Mapped[Optional[str]] = mapped_column(String(32), default="xingchen", comment="来源平台")
    file_name: Mapped[Optional[str]] = mapped_column(String(255), comment="原始文件名")
    file_ext: Mapped[Optional[str]] = mapped_column(String(32), comment="文件扩展名")
    content_type: Mapped[Optional[str]] = mapped_column(String(128), comment="MIME类型")
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, default=0, comment="文件大小")
    file_url: Mapped[Optional[str]] = mapped_column(String(1024), comment="平台返回文件URL")
    upload_status: Mapped[Optional[int]] = mapped_column(SmallInteger, default=1, comment="上传状态")
    remark: Mapped[Optional[str]] = mapped_column(String(255), comment="备注")
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="创建时间")
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="更新时间")
    del_flag: Mapped[Optional[int]] = mapped_column(SmallInteger, default=0, comment="删除标识")


# ============================================================
# 管理员权限表 admin_permission
# ============================================================
class AdminPermission(Base):
    """管理员权限表"""
    __tablename__ = "admin_permission"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment="ID")
    user_id: Mapped[int] = mapped_column(BigInteger, comment="用户ID")
    username: Mapped[Optional[str]] = mapped_column(String(256), comment="用户名")
    is_admin: Mapped[Optional[int]] = mapped_column(SmallInteger, default=0, comment="是否管理员")
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="创建时间")
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="修改时间")
    del_flag: Mapped[Optional[int]] = mapped_column(SmallInteger, default=0, comment="删除标识")
