"""面试相关 Schema"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class CreateInterviewRequest(BaseModel):
    """创建面试请求"""
    user_id: Optional[int] = Field(default=None, description="用户ID(可选，后端从token获取)")
    interview_direction: Optional[str] = Field(default=None, description="面试方向")
    resume_content: Optional[str] = Field(default=None, description="简历内容")


class InterviewSessionResponse(BaseModel):
    """面试会话响应"""
    id: int = Field(..., description="记录ID")
    user_id: int = Field(..., description="用户ID")
    session_id: str = Field(..., description="会话ID")
    interview_score: Optional[int] = Field(default=None, description="面试得分")
    resume_score: Optional[int] = Field(default=None, description="简历得分")
    interview_status: Optional[str] = Field(default=None, description="面试状态")
    question_count: Optional[int] = Field(default=None, description="题目数量")
    interview_direction: Optional[str] = Field(default=None, description="面试方向")
    start_time: Optional[datetime] = Field(default=None, description="开始时间")
    end_time: Optional[datetime] = Field(default=None, description="结束时间")
    duration_seconds: Optional[int] = Field(default=None, description="面试时长(秒)")
    interview_suggestions: Optional[str] = Field(default=None, description="面试建议")
    create_time: Optional[datetime] = Field(default=None, description="创建时间")

    class Config:
        from_attributes = True


class MessageRequest(BaseModel):
    """发送消息请求"""
    session_id: str = Field(..., description="会话ID")
    content: str = Field(..., description="消息内容")
    message_type: str = Field(default="text", description="消息类型: text/audio")


class MessageResponse(BaseModel):
    """消息响应"""
    message_id: str = Field(..., description="消息ID")
    role: str = Field(..., description="角色: user/assistant")
    content: str = Field(..., description="消息内容")
    created_at: datetime = Field(..., description="创建时间")


class StreamResponse(BaseModel):
    """流式响应"""
    session_id: str = Field(..., description="会话ID")
    content: str = Field(..., description="内容片段")
    is_final: bool = Field(default=False, description="是否最终片段")
    thinking: Optional[str] = Field(default=None, description="思考过程")


class InterviewSnapshot(BaseModel):
    """面试快照"""
    session_id: str = Field(..., description="会话ID")
    status: str = Field(..., description="状态: INIT/ASKING/EVALUATING/FOLLOW_UP/COMPLETED")
    current_question_number: str = Field(..., description="当前题目编号")
    current_index: int = Field(..., description="当前题目索引")
    total_questions: int = Field(..., description="总题目数")
    follow_up_count: int = Field(default=0, description="追问次数")
    max_follow_up: int = Field(default=2, description="最大追问次数")
    total_score: int = Field(default=0, description="当前总分")


class InterviewResult(BaseModel):
    """面试结果"""
    session_id: str = Field(..., description="会话ID")
    interview_score: int = Field(..., description="面试得分")
    resume_score: int = Field(..., description="简历得分")
    total_score: int = Field(..., description="总分")
    interview_suggestions: str = Field(..., description="面试建议")
    question_count: int = Field(..., description="题目数量")
    duration_seconds: int = Field(..., description="面试时长")
    questions: list[dict[str, Any]] = Field(default_factory=list, description="问题列表")
    answers: list[dict[str, Any]] = Field(default_factory=list, description="回答列表")
