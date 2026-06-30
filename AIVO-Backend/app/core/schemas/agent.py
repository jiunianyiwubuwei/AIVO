"""Agent 相关 Schema"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AgentPropertiesResponse(BaseModel):
    """Agent 配置响应"""
    id: int = Field(..., description="ID")
    agent_name: Optional[str] = Field(default=None, description="智能体名称")
    api_secret: Optional[str] = Field(default=None, description="鉴权密钥")
    api_key: Optional[str] = Field(default=None, description="鉴权key")
    api_flow_id: Optional[str] = Field(default=None, description="工作流ID")
    ai_mode: Optional[str] = Field(default="workflow", description="模式")
    ai_properties_id: Optional[int] = Field(default=None, description="绑定的AI配置ID")
    system_prompt: Optional[str] = Field(default=None, description="系统提示词")
    create_time: Optional[datetime] = Field(default=None, description="创建时间")
    update_time: Optional[datetime] = Field(default=None, description="修改时间")

    class Config:
        from_attributes = True


class AgentPropertiesCreate(BaseModel):
    """Agent 配置创建"""
    agent_name: Optional[str] = Field(default=None, description="智能体名称")
    api_flow_id: Optional[str] = Field(default=None, description="工作流ID")
    ai_mode: Optional[str] = Field(default="workflow", description="模式")
    ai_properties_id: Optional[int] = Field(default=None, description="绑定的AI配置ID")
    system_prompt: Optional[str] = Field(default=None, description="系统提示词")
    api_key: Optional[str] = Field(default=None, description="鉴权key")
    api_secret: Optional[str] = Field(default=None, description="鉴权密钥")


class AiPropertiesResponse(BaseModel):
    """AI 模型配置响应"""
    id: int = Field(..., description="ID")
    ai_name: Optional[str] = Field(default=None, description="AI名称")
    ai_type: Optional[str] = Field(default=None, description="AI类型")
    api_key: Optional[str] = Field(default=None, description="API密钥")
    api_url: Optional[str] = Field(default=None, description="API地址")
    model_name: Optional[str] = Field(default=None, description="模型名称")
    max_tokens: Optional[int] = Field(default=4096, description="最大token数")
    temperature: Optional[float] = Field(default=0.70, description="温度参数")
    system_prompt: Optional[str] = Field(default=None, description="系统提示词")
    is_enabled: Optional[int] = Field(default=1, description="是否启用")
    enable_thinking: Optional[int] = Field(default=0, description="是否开启思考模式")
    thinking_budget_tokens: Optional[int] = Field(default=None, description="思考预算")
    create_time: Optional[datetime] = Field(default=None, description="创建时间")

    class Config:
        from_attributes = True


class AiPropertiesCreate(BaseModel):
    """AI 模型配置创建"""
    ai_name: Optional[str] = Field(default=None, description="AI名称")
    ai_type: Optional[str] = Field(default=None, description="AI类型")
    api_key: Optional[str] = Field(default=None, description="API密钥")
    api_secret: Optional[str] = Field(default=None, description="API密钥")
    api_url: Optional[str] = Field(default=None, description="API地址")
    model_name: Optional[str] = Field(default=None, description="模型名称")
    max_tokens: Optional[int] = Field(default=4096, description="最大token数")
    temperature: Optional[float] = Field(default=0.70, description="温度参数")
    system_prompt: Optional[str] = Field(default=None, description="系统提示词")
    is_enabled: Optional[int] = Field(default=1, description="是否启用")
    enable_thinking: Optional[int] = Field(default=0, description="是否开启思考模式")
    thinking_budget_tokens: Optional[int] = Field(default=None, description="思考预算")
    project_id: Optional[str] = Field(default=None, description="项目ID")
    organization_id: Optional[str] = Field(default=None, description="组织ID")


class AiConversationResponse(BaseModel):
    """AI 对话会话响应"""
    session_id: str = Field(..., description="会话ID")
    user_id: int = Field(..., description="用户ID")
    username: Optional[str] = Field(default=None, description="用户名")
    ai_id: Optional[int] = Field(default=None, description="AI配置ID")
    ai_name: Optional[str] = Field(default=None, description="AI名称")
    title: Optional[str] = Field(default=None, description="对话标题")
    last_message: Optional[str] = Field(default=None, description="最后一条消息")
    message_count: int = Field(default=0, description="消息数量")
    status: str = Field(default="active", description="状态")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="最后更新时间")


class AgentPropertiesUpdate(BaseModel):
    """Agent 配置更新"""
    agent_name: Optional[str] = Field(default=None, description="智能体名称")
    api_secret: Optional[str] = Field(default=None, description="鉴权密钥")
    api_key: Optional[str] = Field(default=None, description="鉴权key")
    api_flow_id: Optional[str] = Field(default=None, description="工作流ID")
    ai_mode: Optional[str] = Field(default=None, description="模式")
    ai_properties_id: Optional[int] = Field(default=None, description="绑定的AI配置ID")
    system_prompt: Optional[str] = Field(default=None, description="系统提示词")
