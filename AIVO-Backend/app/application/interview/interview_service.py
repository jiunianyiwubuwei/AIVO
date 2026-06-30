"""面试服务层"""

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import InterviewRecord
from app.infrastructure.cache.mongodb_client import mongodb_client


class InterviewService:
    """面试服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(
        self,
        user_id: int,
        interview_direction: Optional[str] = None,
        resume_content: Optional[str] = None,
    ) -> InterviewRecord:
        """创建面试会话"""
        session_id = str(uuid.uuid4())

        interview = InterviewRecord(
            user_id=user_id,
            session_id=session_id,
            interview_status="INIT",
            interview_direction=interview_direction,
            create_time=datetime.now(timezone.utc),
            update_time=datetime.now(timezone.utc),
            del_flag=0,
        )
        self.db.add(interview)
        await self.db.flush()

        # 初始化 MongoDB 快照
        await self._init_snapshot(session_id, user_id)

        return interview

    async def _init_snapshot(self, session_id: str, user_id: int) -> None:
        """初始化面试快照"""
        snapshot = {
            "session_id": session_id,
            "user_id": user_id,
            "status": "INIT",
            "current_question_number": "0",
            "current_index": 0,
            "total_questions": 5,
            "follow_up_count": 0,
            "max_follow_up": 2,
            "total_score": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await mongodb_client.interview_snapshots.insert_one(snapshot)

    async def get_by_session_id(self, session_id: str) -> Optional[InterviewRecord]:
        """根据会话ID获取面试记录"""
        result = await self.db.execute(
            select(InterviewRecord).where(
                InterviewRecord.session_id == session_id,
                InterviewRecord.del_flag == 0
            )
        )
        return result.scalar_one_or_none()

    async def get_by_user_id(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[InterviewRecord], int]:
        """获取用户的面试记录列表"""
        query = select(InterviewRecord).where(
            InterviewRecord.user_id == user_id,
            InterviewRecord.del_flag == 0
        ).order_by(InterviewRecord.create_time.desc())

        from sqlalchemy import func
        count_result = await self.db.execute(
            select(func.count()).where(
                InterviewRecord.user_id == user_id,
                InterviewRecord.del_flag == 0
            )
        )
        total = count_result.scalar() or 0

        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = result.scalars().all()

        return list(items), total

    async def update_status(
        self,
        session_id: str,
        status: str,
        **kwargs,
    ) -> Optional[InterviewRecord]:
        """更新面试状态"""
        interview = await self.get_by_session_id(session_id)
        if interview is None:
            return None

        interview.interview_status = status
        interview.update_time = datetime.now(timezone.utc)

        for key, value in kwargs.items():
            if hasattr(interview, key) and value is not None:
                setattr(interview, key, value)

        await self.db.flush()
        return interview

    async def soft_delete(self, session_id: str, user_id: int) -> bool:
        """软删除面试记录"""
        interview = await self.get_by_session_id(session_id)
        if interview is None:
            return False
        if interview.user_id != user_id:
            return False

        interview.del_flag = 1
        interview.update_time = datetime.now(timezone.utc)
        await self.db.flush()
        return True

    async def finish_interview(
        self,
        session_id: str,
        interview_score: int,
        interview_suggestions: str,
        total_questions: int,
        duration_seconds: int,
    ) -> Optional[InterviewRecord]:
        """完成面试"""
        interview = await self.get_by_session_id(session_id)
        if interview is None:
            return None

        interview.interview_status = "FINISHED"
        interview.interview_score = interview_score
        interview.interview_suggestions = interview_suggestions
        interview.question_count = total_questions
        interview.end_time = datetime.now(timezone.utc)
        interview.duration_seconds = duration_seconds
        interview.update_time = datetime.now(timezone.utc)

        await self.db.flush()
        return interview

    async def get_snapshot(self, session_id: str) -> Optional[dict]:
        """获取面试快照"""
        return await mongodb_client.find_one(
            "interview_snapshots",
            {"session_id": session_id}
        )

    async def update_snapshot(self, session_id: str, updates: dict) -> None:
        """更新面试快照"""
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await mongodb_client.update_one(
            "interview_snapshots",
            {"session_id": session_id},
            updates
        )

    async def save_snapshot(self, session_id: str, data: dict) -> None:
        """保存面试快照（使用 upsert）"""
        document = {
            "session_id": session_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **data,
        }
        await mongodb_client.update_one(
            "interview_snapshots",
            {"session_id": session_id},
            document,
            upsert=True,
        )

    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> str:
        """保存消息到 MongoDB"""
        message = {
            "session_id": session_id,
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc),
        }
        return await mongodb_client.insert_one("conversations", message)

    async def get_messages(
        self,
        session_id: str,
        limit: int = 50,
    ) -> list[dict]:
        """获取会话消息"""
        return await mongodb_client.find_many(
            "conversations",
            {"session_id": session_id},
            sort=[("created_at", 1)],
            limit=limit,
        )

    async def submit_answer(
        self,
        session_id: str,
        question_number: str,
        answer_content: str,
    ) -> dict:
        """提交面试答案并获取评分"""
        from app.agents.ai_client import ai_client

        # 获取快照
        snapshot = await self.get_snapshot(session_id)
        if not snapshot:
            raise ValueError("面试会话不存在")

        # 获取问题内容
        questions = snapshot.get("questions", [])
        current_question = None
        for q in questions:
            if q.get("number") == question_number or q.get("id") == question_number:
                current_question = q
                break

        if not current_question:
            raise ValueError(f"问题 {question_number} 不存在")

        # 获取当前追问次数
        current_follow_up = snapshot.get("current_follow_up_count", 0)

        # 调用 AI 评估
        evaluation = await ai_client.evaluate_answer(
            question=current_question.get("content", ""),
            answer=answer_content,
            follow_up_count=current_follow_up,
        )

        # 保存答案
        answer_record = {
            "question_number": question_number,
            "question_content": current_question.get("content", ""),
            "answer_content": answer_content,
            "score": evaluation.get("score", 0),
            "evaluation": evaluation.get("evaluation", ""),
            "suggestions": evaluation.get("suggestions", ""),
            "details": evaluation,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }

        # 更新快照
        answers = snapshot.get("answers", [])
        answers.append(answer_record)

        # 更新总分数
        total_score = sum(a.get("score", 0) for a in answers)
        answered_count = len(answers)

        # 检查是否是最后一题
        total_questions = snapshot.get("total_questions", len(questions))
        is_last_question = answered_count >= total_questions

        # 准备下一题（如果还有题目）
        next_question = None
        next_question_number = None
        if not is_last_question:
            # 获取下一个问题
            next_index = answered_count
            if next_index < len(questions):
                next_question = questions[next_index]
                next_question_number = next_question.get("number") or f"q_{next_index + 1}"

        updates = {
            "answers": answers,
            "total_score": total_score,
            "answered_count": answered_count,
            "current_question": next_question,  # 保存下一题作为当前题
            "current_question_number": next_question_number,
            "current_index": next_index if not is_last_question else snapshot.get("current_index", 0),
        }

        await self.save_snapshot(session_id, {**snapshot, **updates})

        return {
            "question_number": question_number,
            "question_content": current_question.get("content", ""),
            "score": evaluation.get("score", 0),
            "total_score": total_score,
            "is_success": True,
            "feedback": evaluation.get("evaluation", ""),
            "next_question": next_question.get("content") if next_question else None,
            "next_question_number": next_question_number,
            "is_follow_up": current_follow_up > 0,
            "finished": is_last_question,
        }

    async def generate_next_question(
        self,
        session_id: str,
    ) -> Optional[dict]:
        """生成下一道问题"""
        from app.agents.ai_client import ai_client

        # 获取快照
        snapshot = await self.get_snapshot(session_id)
        if not snapshot:
            raise ValueError("面试会话不存在")

        questions = snapshot.get("questions", [])
        answered_count = snapshot.get("answered_count", 0)
        total_questions = snapshot.get("total_questions", len(questions))

        if answered_count >= total_questions:
            return None  # 所有问题都已回答

        # 获取下一个问题
        next_index = answered_count
        if next_index < len(questions):
            next_question = questions[next_index]
            await self.update_snapshot(session_id, {
                "current_question": next_question,
                "current_question_number": next_question.get("number", str(next_index + 1)),
                "current_index": next_index,
                "current_follow_up_count": 0,
            })
            return next_question

        # 如果问题不够，动态生成新问题
        direction = snapshot.get("interview_direction", "技术面试")
        resume_content = snapshot.get("resume_content")

        generated_questions = await ai_client.generate_questions(
            direction=direction,
            resume_content=resume_content,
            count=1,
        )

        if generated_questions:
            new_question = generated_questions[0]
            # 添加到问题列表
            questions.append(new_question)
            await self.update_snapshot(session_id, {
                "questions": questions,
                "current_question": new_question,
                "current_question_number": new_question.get("number", str(len(questions))),
                "current_index": len(questions) - 1,
                "total_questions": len(questions),
                "current_follow_up_count": 0,
            })
            return new_question

        return None

    async def generate_follow_up(
        self,
        session_id: str,
        question_number: str,
        answer_content: str,
    ) -> Optional[str]:
        """生成追问"""
        from app.agents.ai_client import ai_client

        snapshot = await self.get_snapshot(session_id)
        if not snapshot:
            raise ValueError("面试会话不存在")

        # 获取问题
        questions = snapshot.get("questions", [])
        current_question = None
        for q in questions:
            if q.get("number") == question_number or q.get("id") == question_number:
                current_question = q
                break

        if not current_question:
            raise ValueError(f"问题 {question_number} 不存在")

        # 获取之前的追问
        answers = snapshot.get("answers", [])
        previous_follow_ups = []
        for a in answers:
            if a.get("question_number") == question_number and a.get("is_follow_up"):
                previous_follow_ups.append(a.get("answer_content", ""))

        # 获取当前追问次数
        current_follow_up = snapshot.get("current_follow_up_count", 0)
        max_follow_up = snapshot.get("max_follow_up", 2)

        if current_follow_up >= max_follow_up:
            return None  # 达到追问上限

        # 生成追问
        follow_up = await ai_client.generate_follow_up(
            question=current_question.get("content", ""),
            answer=answer_content,
            previous_follow_ups=previous_follow_ups,
        )

        # 更新追问计数
        await self.update_snapshot(session_id, {
            "current_follow_up_count": current_follow_up + 1,
            "current_follow_up": {
                "content": follow_up,
                "question_number": f"{question_number}_f{current_follow_up + 1}",
            },
        })

        return follow_up

    async def get_cached_value(self, key: str) -> Optional[dict]:
        """获取缓存值"""
        try:
            from app.infrastructure.cache.redis_client import redis_client
            value = await redis_client.get(key)
            if value:
                import json
                return json.loads(value)
        except Exception:
            pass
        return None

    async def set_cached_value(self, key: str, value: dict, expire_seconds: int = 3600) -> bool:
        """设置缓存值"""
        try:
            from app.infrastructure.cache.redis_client import redis_client
            import json
            await redis_client.set(key, json.dumps(value), ex=expire_seconds)
            return True
        except Exception:
            return False

    async def save_follow_up_question(
        self,
        session_id: str,
        question_number: str,
        content: str,
    ) -> None:
        """保存追问"""
        snapshot = await self.get_snapshot(session_id)
        if not snapshot:
            return

        follow_ups = snapshot.get("follow_up_questions", {})
        follow_ups[question_number] = content

        await self.update_snapshot(session_id, {
            "follow_up_questions": follow_ups,
        })

    async def get_follow_up_question(
        self,
        session_id: str,
        question_number: str,
    ) -> Optional[str]:
        """获取追问"""
        snapshot = await self.get_snapshot(session_id)
        if not snapshot:
            return None
        follow_ups = snapshot.get("follow_up_questions", {})
        return follow_ups.get(question_number)

    async def update_flow_state(
        self,
        session_id: str,
        updates: dict,
    ) -> None:
        """更新流程状态"""
        snapshot = await self.get_snapshot(session_id)
        if not snapshot:
            return

        flow_state = snapshot.get("flow_state", {})
        flow_state.update(updates)

        await self.update_snapshot(session_id, {
            "flow_state": flow_state,
        })

    async def save_turn_log(
        self,
        session_id: str,
        request_id: str,
        question_number: str,
        question_content: str,
        answer_content: str,
        score: int,
        total_score: int,
        feedback: str,
        is_follow_up: bool,
        follow_up_count: int,
        next_question: Optional[str],
        next_question_number: Optional[str],
        finished: bool,
    ) -> None:
        """保存轮次日志（同时保存到 turn_logs 和 answers）"""
        from app.infrastructure.cache.mongodb_client import mongodb_client

        # 构建 turn_log
        turn_log = {
            "session_id": session_id,
            "request_id": request_id,
            "question_number": question_number,
            "question_content": question_content,
            "answer_content": answer_content,
            "score": score,
            "total_score": total_score,
            "feedback": feedback,
            "is_follow_up": is_follow_up,
            "follow_up_count": follow_up_count,
            "next_question": next_question,
            "next_question_number": next_question_number,
            "finished": finished,
            "timestamp": int(time.time() * 1000),
        }

        # 构建 answer_record（用于报告展示）
        answer_record = {
            "question_number": question_number,
            "question_content": question_content,
            "answer_content": answer_content,
            "score": score,
            "evaluation": feedback,
            "suggestions": "",
            "is_follow_up": is_follow_up,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }

        # 同时保存到 turn_logs 和 answers
        await mongodb_client.update_one(
            "interview_snapshots",
            {"session_id": session_id},
            {
                "$push": {
                    "turn_logs": turn_log,
                    "answers": answer_record,
                }
            },
        )

    async def get_question_by_number(
        self,
        session_id: str,
        question_number: str,
    ) -> Optional[dict]:
        """根据题号获取问题"""
        snapshot = await self.get_snapshot(session_id)
        if not snapshot:
            return None

        questions = snapshot.get("questions", [])
        for q in questions:
            q_num = q.get("number", "")
            if q_num == question_number or q_num == str(question_number):
                return q

        return None

    async def add_session_score(self, session_id: str, score: int) -> int:
        """添加分数到会话"""
        snapshot = await self.get_snapshot(session_id)
        if not snapshot:
            return score

        current_score = snapshot.get("total_score", 0)
        new_score = current_score + score

        await self.update_snapshot(session_id, {
            "total_score": new_score,
        })

        return new_score
