"""面试工作流服务"""

import json
from datetime import datetime, timezone
from typing import Optional

from app.workflow.interview_graph import interview_workflow
from app.workflow.state import InterviewState, InterviewStatus
from app.infrastructure.cache.redis_client import redis_client
from app.infrastructure.cache.mongodb_client import mongodb_client
from app.application.interview.interview_service import InterviewService
from sqlalchemy.ext.asyncio import AsyncSession


class InterviewWorkflowService:
    """面试工作流服务"""

    # Redis 状态键前缀
    STATE_KEY_PREFIX = "interview:state:"

    def __init__(self, db: AsyncSession):
        self.db = db
        self.interview_service = InterviewService(db)

    async def start_interview(
        self,
        session_id: str,
        user_id: int,
        interview_direction: str = "通用面试",
        total_questions: int = 5,
        resume_content: Optional[str] = None,
    ) -> InterviewState:
        """启动面试"""
        # 创建初始状态
        state = InterviewState(
            session_id=session_id,
            user_id=user_id,
            interview_direction=interview_direction,
            total_questions=total_questions,
            max_follow_up=2,
            metadata={
                "resume_content": resume_content,
                "start_time": datetime.now(timezone.utc).isoformat(),
            }
        )

        # 保存状态到 Redis
        await self._save_state(state)

        # 更新面试记录状态
        await self.interview_service.update_status(session_id, "IN_PROGRESS")

        # 运行工作流
        result = await interview_workflow.run(state)

        # 保存最终状态
        await self._save_state(result)

        return result

    async def send_message(
        self,
        session_id: str,
        user_input: str,
    ) -> InterviewState:
        """发送消息"""
        # 从 Redis 加载状态
        state = await self._load_state(session_id)
        if state is None:
            raise ValueError(f"Session not found: {session_id}")

        # 更新用户输入
        state.user_input = user_input

        # 根据当前状态处理
        if state.status == InterviewStatus.WAITING:
            # 接收回答
            state = await self._process_answer(state)
        elif state.status == InterviewStatus.FOLLOW_UP:
            # 处理追问回答
            state = await self._process_answer(state)
        else:
            # 其他状态，直接运行工作流
            state = await interview_workflow.run(state)

        # 保存状态
        await self._save_state(state)

        # 如果面试完成，更新数据库
        if state.status == InterviewStatus.COMPLETED:
            await self._finish_interview(state)

        return state

    async def _process_answer(self, state: InterviewState) -> InterviewState:
        """处理回答"""
        from app.workflow.nodes.interview_nodes import receive_answer, evaluate_answer, next_question, should_continue_interview

        # 接收回答
        state = await receive_answer(state)

        # 评估回答
        state = await evaluate_answer(state)

        # 根据评估结果决定下一步
        next_step = should_continue_interview(state)

        if next_step == "generate_follow_up":
            # 生成追问
            from app.workflow.nodes.interview_nodes import generate_follow_up
            state = await generate_follow_up(state)
        elif next_step == "ask_question":
            # 进入下一题
            state = await next_question(state)
            if state.status == InterviewStatus.ASKING:
                # 继续提问
                from app.workflow.nodes.interview_nodes import ask_question
                state = await ask_question(state)
        elif next_step == "finish":
            # 完成面试
            from app.workflow.nodes.interview_nodes import finish_interview
            state = await finish_interview(state)

        return state

    async def get_current_state(self, session_id: str) -> Optional[InterviewState]:
        """获取当前状态"""
        return await self._load_state(session_id)

    async def _save_state(self, state: InterviewState) -> None:
        """保存状态到 Redis"""
        key = f"{self.STATE_KEY_PREFIX}{state.session_id}"
        state_data = state.model_dump(mode="json")
        # 转换 datetime 为字符串
        state_data = self._serialize_state(state_data)
        await redis_client.set_json(key, state_data, ex=3600 * 24)  # 24小时过期

    async def _load_state(self, session_id: str) -> Optional[InterviewState]:
        """从 Redis 加载状态"""
        key = f"{self.STATE_KEY_PREFIX}{session_id}"
        state_data = await redis_client.get_json(key)

        if state_data is None:
            return None

        return self._deserialize_state(state_data)

    def _serialize_state(self, state: dict) -> dict:
        """序列化状态"""
        serialized = {}
        for key, value in state.items():
            if isinstance(value, dict):
                serialized[key] = self._serialize_state(value)
            elif hasattr(value, "model_dump"):
                serialized[key] = value.model_dump()
            else:
                serialized[key] = value
        return serialized

    def _deserialize_state(self, state_data: dict) -> InterviewState:
        """反序列化状态"""
        return InterviewState.model_validate(state_data)

    async def _finish_interview(self, state: InterviewState) -> None:
        """完成面试后更新数据库"""
        # 计算最终得分
        total_possible = state.total_questions * 20
        interview_score = int((state.total_score / total_possible) * 100) if total_possible > 0 else 0

        # 更新面试记录
        await self.interview_service.finish_interview(
            session_id=state.session_id,
            interview_score=interview_score,
            interview_suggestions=state.interview_suggestions,
            total_questions=state.total_questions,
            duration_seconds=self._calculate_duration(state),
        )

        # 保存会话快照
        snapshot = {
            "session_id": state.session_id,
            "status": InterviewStatus.COMPLETED.value,
            "interview_score": interview_score,
            "total_score": state.total_score,
            "questions": [q.model_dump() for q in state.questions],
            "answers": state.metadata.get("answers", []),
            "suggestions": state.interview_suggestions,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        await mongodb_client.interview_snapshots.insert_one(snapshot)

        # 清理 Redis 状态
        key = f"{self.STATE_KEY_PREFIX}{state.session_id}"
        await redis_client.delete(key)

    def _calculate_duration(self, state: InterviewState) -> int:
        """计算面试时长"""
        start_time_str = state.metadata.get("start_time")
        if start_time_str:
            start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
            duration = datetime.now(timezone.utc) - start_time
            return int(duration.total_seconds())
        return 0
