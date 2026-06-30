"""面试答案响应 DTO"""

from typing import Optional
from pydantic import BaseModel


class InterviewAnswerRespDTO(BaseModel):
    """面试答案响应"""
    question_number: Optional[str] = None  # 题号
    question_content: Optional[str] = None  # 题目内容
    score: Optional[int] = None  # 本次得分
    total_score: Optional[int] = None  # 累计总分
    is_success: bool = False  # 是否成功
    error_message: Optional[str] = None  # 错误信息
    feedback: Optional[str] = None  # AI评价内容
    next_question: Optional[str] = None  # 下一题内容
    next_question_number: Optional[str] = None  # 下一题题号
    is_follow_up: bool = False  # 是否是追问
    follow_up_count: int = 0  # 当前追问次数
    finished: bool = False  # 是否结束

    @classmethod
    def init(cls):
        """初始化默认响应"""
        return cls(
            is_success=False,
            finished=False,
            is_follow_up=False,
            follow_up_count=0,
        )

    def fail(self, error_message: str) -> "InterviewAnswerRespDTO":
        """标记失败"""
        self.error_message = error_message
        self.is_success = False
        return self

    def success(self) -> "InterviewAnswerRespDTO":
        """标记成功"""
        self.is_success = True
        return self

    def with_current_question(self, question_number: str, question_content: str) -> "InterviewAnswerRespDTO":
        """写入当前题目"""
        self.question_number = question_number
        self.question_content = question_content
        return self

    def with_evaluation(self, score: int, feedback: str, total_score: int) -> "InterviewAnswerRespDTO":
        """写入评分"""
        self.score = score
        self.feedback = feedback
        self.total_score = total_score
        return self

    def with_next_question(
        self,
        next_question_number: str,
        next_question: str,
        is_follow_up: bool,
        follow_up_count: int,
    ) -> "InterviewAnswerRespDTO":
        """写入下一题"""
        self.next_question_number = next_question_number
        self.next_question = next_question
        self.is_follow_up = is_follow_up
        self.follow_up_count = follow_up_count if follow_up_count else 0
        self.finished = False
        return self

    def finish(self) -> "InterviewAnswerRespDTO":
        """标记结束"""
        self.finished = True
        self.is_follow_up = False
        self.follow_up_count = 0
        self.next_question = None
        self.next_question_number = None
        return self

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "questionNumber": self.question_number,
            "questionContent": self.question_content,
            "score": self.score,
            "totalScore": self.total_score,
            "isSuccess": self.is_success,
            "errorMessage": self.error_message,
            "feedback": self.feedback,
            "nextQuestion": self.next_question,
            "nextQuestionNumber": self.next_question_number,
            "isFollowUp": self.is_follow_up,
            "followUpCount": self.follow_up_count,
            "finished": self.finished,
        }
