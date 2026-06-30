"""面试状态机状态定义"""

from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class InterviewStatus(str, Enum):
    """面试状态枚举"""
    DRAFT = "DRAFT"        # 草稿/未启动（简历未上传）
    READY = "READY"        # 就绪（简历已上传，等待开始）
    INIT = "INIT"          # 初始化
    ASKING = "ASKING"      # 提问中
    WAITING = "WAITING"    # 等待用户回答
    EVALUATING = "EVALUATING"  # 评估回答
    FOLLOW_UP = "FOLLOW_UP"  # 追问
    COMPLETED = "COMPLETED"  # 面试完成
    FINISHED = "FINISHED"   # 面试结束（最终状态）
    ERROR = "ERROR"         # 错误状态


class Question(BaseModel):
    """面试问题"""
    id: str = Field(..., description="问题ID")
    number: str = Field(..., description="问题编号")
    content: str = Field(..., description="问题内容")
    category: str = Field(..., description="问题分类")
    difficulty: int = Field(default=3, description="难度等级 1-5")
    expected_duration: int = Field(default=120, description="期望回答时长(秒)")
    score: int = Field(default=0, description="得分")
    evaluation: Optional[str] = Field(default=None, description="评价")
    follow_ups: list[str] = Field(default_factory=list, description="追问列表")


class InterviewState(BaseModel):
    """面试状态机状态"""
    # 会话信息
    session_id: str = Field(..., description="会话ID")
    user_id: int = Field(..., description="用户ID")
    user_input: str = Field(default="", description="用户输入")
    user_message: str = Field(default="", description="用户消息")

    # 面试配置
    interview_direction: str = Field(default="通用面试", description="面试方向")
    total_questions: int = Field(default=5, description="总题目数")
    max_follow_up: int = Field(default=2, description="最大追问次数")

    # 状态流转
    status: InterviewStatus = Field(default=InterviewStatus.INIT, description="当前状态")
    current_question_index: int = Field(default=0, description="当前题目索引")
    current_question: Optional[Question] = Field(default=None, description="当前问题")
    questions: list[Question] = Field(default_factory=list, description="问题列表")

    # 评分
    total_score: int = Field(default=0, description="当前总分")
    resume_score: int = Field(default=0, description="简历得分")
    interview_score: int = Field(default=0, description="面试得分")

    # 流程控制
    follow_up_count: int = Field(default=0, description="追问次数")
    is_answer_complete: bool = Field(default=False, description="回答是否完成")
    should_continue: bool = Field(default=True, description="是否继续面试")

    # 消息
    ai_message: str = Field(default="", description="AI 消息")
    thinking: str = Field(default="", description="思考过程")

    # 结果
    interview_suggestions: str = Field(default="", description="面试建议")
    error_message: Optional[str] = Field(default=None, description="错误信息")

    # 元数据
    metadata: dict = Field(default_factory=dict, description="元数据")
