"""面试答案处理管道

完整复刻 Java 版本的 InterviewAnswerPipeline
"""

import hashlib
import re
import time
from typing import Optional

from app.core.schemas.interview_answer import InterviewAnswerRespDTO


# 追问判断阈值
SCORE_THRESHOLD = 60  # 低于此分数需要追问
MAX_FOLLOW_UP = 2  # 最大追问次数


def normalize_question_number(question_number: str) -> Optional[str]:
    """归一化题号"""
    if not question_number:
        return None
    normalized = question_number.strip().upper()
    # 纯数字
    if re.match(r"^\d+$", normalized):
        try:
            return str(int(normalized))
        except ValueError:
            return normalized
    # 追问题号 (如 "1-F1", "2-F2")
    if re.match(r"^\d+-F\d+$", normalized):
        parts = normalized.split("-F")
        try:
            return f"{int(parts[0])}-F{int(parts[1])}"
        except ValueError:
            return normalized
    return normalized


def is_follow_up_question(question_number: str) -> bool:
    """判断是否是追问"""
    if not question_number:
        return False
    return bool(re.match(r"^\d+-F\d+$", question_number.strip()))


def extract_main_question_number(question_number: str) -> Optional[str]:
    """提取主问题题号"""
    if not question_number:
        return None
    normalized = question_number.strip()
    separator_index = normalized.find("-F")
    if separator_index > 0:
        return normalized[:separator_index]
    return normalized


def extract_follow_up_count(question_number: str) -> int:
    """提取追问次数"""
    if not is_follow_up_question(question_number):
        return 0
    try:
        separator_index = question_number.find("-F")
        if separator_index >= 0 and separator_index + 2 < len(question_number):
            return max(0, int(question_number[separator_index + 2:].strip()))
    except (ValueError, IndexError):
        pass
    return 0


def build_follow_up_question_number(main_question_number: str, follow_up_count: int) -> Optional[str]:
    """构建追问题号"""
    if not main_question_number or follow_up_count <= 0:
        return None
    return f"{main_question_number}-F{follow_up_count}"


def sanitize_follow_up_question(question: Optional[str]) -> Optional[str]:
    """清理追问问题"""
    if not question:
        return None
    normalized = question.strip()
    # 过滤无效值
    if normalized.lower() in ("none", "null", "n/a", "-", "__finish__"):
        return None
    # 确保以问号结尾
    if not normalized.endswith("?"):
        normalized += "?"
    # 限制长度
    return normalized[:100] if len(normalized) > 100 else normalized


def generate_request_id(session_id: str, question_number: str, answer_content: str) -> str:
    """生成请求ID（用于幂等）"""
    seed = f"{session_id}|{question_number.strip()}|{answer_content}"
    return f"auto-{hashlib.sha256(seed.encode()).hexdigest()[:32]}"


def should_generate_follow_up(
    score: int,
    follow_up_count: int,
    max_follow_up: int = MAX_FOLLOW_UP,
    follow_up_needed_from_ai: bool = False,
) -> tuple[bool, int]:
    """判断是否需要生成追问

    Returns:
        (是否需要追问, 解决后的最大追问次数)
    """
    resolved_max = max_follow_up if max_follow_up > 0 else MAX_FOLLOW_UP

    # 追问次数已达上限
    if follow_up_count >= resolved_max:
        return False, resolved_max

    # AI 建议需要追问
    if follow_up_needed_from_ai:
        return True, resolved_max

    # 分数低于阈值，需要追问
    if score < SCORE_THRESHOLD:
        return True, resolved_max

    return False, resolved_max


def resolve_max_follow_up(flow_state: Optional[dict]) -> int:
    """从流程状态中解析最大追问次数"""
    if flow_state and flow_state.get("max_follow_up"):
        max_val = flow_state.get("max_follow_up")
        if isinstance(max_val, int) and max_val > 0:
            return max_val
    return MAX_FOLLOW_UP


def resolve_follow_up_count(flow_state: Optional[dict], question_number: str) -> int:
    """解析当前追问次数"""
    # 优先从流程状态获取（这是最可靠的来源）
    if flow_state and flow_state.get("follow_up_count") is not None:
        return max(0, flow_state.get("follow_up_count", 0))

    # 其次从题号解析
    if is_follow_up_question(question_number):
        parsed = extract_follow_up_count(question_number)
        if parsed > 0:
            return parsed

    return 0


class InterviewAnswerPipeline:
    """面试答案处理管道"""

    def __init__(self, interview_service):
        self.interview_service = interview_service

    async def execute(
        self,
        session_id: str,
        request_id: Optional[str],
        question_number: str,
        answer_content: str,
    ) -> InterviewAnswerRespDTO:
        """执行答案处理管道"""
        ctx = AnswerPipelineContext()
        ctx.session_id = session_id
        ctx.request_id = request_id or generate_request_id(session_id, question_number, answer_content)
        ctx.question_number = question_number.strip()
        ctx.answer_content = answer_content
        ctx.response = InterviewAnswerRespDTO.init()

        try:
            # 1) 基础参数校验
            if not self._validate_request(ctx):
                return ctx.response

            # 2) 归一化 requestId
            ctx.request_id = ctx.request_id.strip() or generate_request_id(
                session_id, ctx.question_number, ctx.answer_content
            )

            # 3) 幂等检查
            if not await self._step_idempotency(ctx):
                return ctx.response

            # 4) 加载当前问题
            if not await self._step_load_current_question(ctx):
                return await self._finish_and_return(ctx, False)

            # 5) 评分
            if not await self._step_evaluate_and_score(ctx):
                return ctx.response

            # 6) 推进流程并组装响应
            if not await self._step_advance_flow_and_assemble(ctx):
                return ctx.response

            return await self._finish_and_return(ctx, True)

        except Exception as e:
            ctx.response.fail(f"处理答案时出错: {str(e)}")
            return ctx.response

    def _validate_request(self, ctx: "AnswerPipelineContext") -> bool:
        """验证请求参数"""
        if not ctx.session_id:
            ctx.response.fail("sessionId cannot be empty")
            return False
        if not ctx.question_number:
            ctx.response.fail("question number cannot be empty")
            return False
        if not ctx.answer_content:
            ctx.response.fail("answer content cannot be empty")
            return False
        return True

    async def _step_idempotency(self, ctx: "AnswerPipelineContext") -> bool:
        """幂等检查"""
        # 检查是否有正在处理的请求
        cache_key = f"idempotency:{ctx.session_id}:{ctx.request_id}"

        try:
            existing = await self.interview_service.get_cached_value(cache_key)
            if existing:
                # 解析已有响应
                if isinstance(existing, dict):
                    ctx.response = InterviewAnswerRespDTO(**existing)
                    return False
        except Exception:
            pass

        # 标记为处理中（设置较短过期时间）
        await self.interview_service.set_cached_value(
            cache_key,
            {"status": "processing"},
            expire_seconds=30,
        )
        ctx.idempotency_started = True
        return True

    async def _step_load_current_question(self, ctx: "AnswerPipelineContext") -> bool:
        """加载当前问题"""
        snapshot = await self.interview_service.get_snapshot(ctx.session_id)
        if not snapshot:
            ctx.response.fail("interview session not found")
            return False

        ctx.flow_state = snapshot.get("flow_state", {})
        questions = snapshot.get("questions", [])

        if not questions:
            ctx.response.fail("no questions found")
            return False

        # 获取流程状态
        flow_state = ctx.flow_state
        current_index = flow_state.get("current_index", 0) if flow_state else 0
        total_questions = flow_state.get("total_questions", len(questions)) if flow_state else len(questions)
        current_follow_up_count = flow_state.get("follow_up_count", 0) if flow_state else 0
        max_follow_up = resolve_max_follow_up(flow_state)

        # 检查是否已完成
        if current_index >= total_questions:
            total_score = snapshot.get("total_score", 0)
            ctx.response.with_next_question("", "", False, 0).finish().success()
            ctx.response.total_score = total_score
            return False

        # 获取当前问题
        # 优先使用 flow_state 中的 current_question_number（追问时会更新）
        flow_question_number = flow_state.get("current_question_number") if flow_state else None
        if current_index < len(questions):
            current_q = questions[current_index]
            ctx.current_question = current_q.get("content", "")
            # 如果 flow_state 中有 current_question_number，使用它；否则从 questions 获取
            ctx.current_question_number = flow_question_number or current_q.get("number") or str(current_index + 1)
        else:
            ctx.response.fail("current question not found")
            return False

        # 验证题号匹配
        normalized_requested = normalize_question_number(ctx.question_number)
        normalized_current = normalize_question_number(ctx.current_question_number)
        if normalized_requested != normalized_current:
            ctx.response.fail("stale question number, please refresh current question")
            return False

        # 设置上下文
        ctx.current_is_follow_up = is_follow_up_question(ctx.current_question_number)
        ctx.current_follow_up_count = resolve_follow_up_count(flow_state, ctx.current_question_number)
        ctx.max_follow_up = max_follow_up

        ctx.response.with_current_question(ctx.current_question_number, ctx.current_question)
        return True

    async def _step_evaluate_and_score(self, ctx: "AnswerPipelineContext") -> bool:
        """评分"""
        from app.agents.ai_client import ai_client

        try:
            # 调用 AI 评分
            evaluation = await ai_client.evaluate_answer(
                question=ctx.current_question,
                answer=ctx.answer_content,
                follow_up_count=ctx.current_follow_up_count,
            )

            score = evaluation.get("score", 0)
            feedback = evaluation.get("evaluation", "")
            follow_up_needed = evaluation.get("follow_up_needed", False)
            follow_up_question_hint = evaluation.get("follow_up_question")

            ctx.score = score
            ctx.total_score = evaluation.get("total_score", score)
            ctx.follow_up_needed_from_ai = follow_up_needed
            ctx.follow_up_question_hint = follow_up_question_hint

            ctx.response.with_evaluation(score, feedback, ctx.total_score)
            return True

        except Exception as e:
            ctx.response.fail(f"evaluation failed: {str(e)}")
            return False

    async def _step_advance_flow_and_assemble(self, ctx: "AnswerPipelineContext") -> bool:
        """推进流程并组装响应"""
        snapshot = await self.interview_service.get_snapshot(ctx.session_id)
        questions = snapshot.get("questions", []) if snapshot else []
        flow_state = ctx.flow_state or {}

        current_index = flow_state.get("current_index", 0)
        total_questions = flow_state.get("total_questions", len(questions))
        current_follow_up_count = ctx.current_follow_up_count

        # 判断是否需要追问
        need_follow_up, resolved_max = should_generate_follow_up(
            score=ctx.score,
            follow_up_count=current_follow_up_count,
            max_follow_up=ctx.max_follow_up,
            follow_up_needed_from_ai=ctx.follow_up_needed_from_ai,
        )

        # 追问分支
        if need_follow_up and current_follow_up_count < resolved_max:
            # 生成追问
            follow_up_question = await self._generate_follow_up(ctx)
            if follow_up_question:
                follow_up_number = build_follow_up_question_number(
                    extract_main_question_number(ctx.current_question_number) or "1",
                    current_follow_up_count + 1,
                )

                # 保存追问到缓存
                await self.interview_service.save_follow_up_question(
                    ctx.session_id, follow_up_number, follow_up_question
                )

                # 更新流程状态
                new_follow_up_count = current_follow_up_count + 1
                await self.interview_service.update_flow_state(
                    ctx.session_id,
                    {
                        "follow_up_count": new_follow_up_count,
                        "current_follow_up_question": follow_up_question,
                        "current_follow_up_number": follow_up_number,
                        "current_question_number": follow_up_number,  # 更新当前题号为追问题号
                    }
                )

                # 追问不计入总分，但返回追问内容
                ctx.response.with_next_question(
                    follow_up_number,
                    follow_up_question,
                    True,
                    new_follow_up_count,
                ).success()
                return True

        # 无追问时，推进主问题
        next_index = current_index + 1

        # 检查是否是最后一题
        if next_index >= total_questions:
            # 标记完成
            await self.interview_service.update_flow_state(
                ctx.session_id,
                {"status": "completed", "current_index": next_index}
            )
            ctx.response.finish().success()
            ctx.response.total_score = ctx.total_score
            return True

        # 获取下一题
        if next_index < len(questions):
            next_q = questions[next_index]
            next_question = next_q.get("content", "")
            next_question_number = next_q.get("number") or str(next_index + 1)

            # 更新流程状态
            await self.interview_service.update_flow_state(
                ctx.session_id,
                {
                    "current_index": next_index,
                    "current_question_number": next_question_number,
                    "follow_up_count": 0,  # 重置追问计数
                }
            )

            ctx.response.with_next_question(
                next_question_number,
                next_question,
                False,
                0,
            ).success()
            return True

        ctx.response.fail("next question not found")
        return False

    async def _generate_follow_up(self, ctx: "AnswerPipelineContext") -> Optional[str]:
        """生成追问"""
        from app.agents.ai_client import ai_client

        try:
            # 优先使用 AI 评分返回的追问提示
            if ctx.follow_up_question_hint:
                return sanitize_follow_up_question(ctx.follow_up_question_hint)

            # 调用专门的追问生成
            follow_up = await ai_client.generate_follow_up(
                question=ctx.current_question,
                answer=ctx.answer_content,
                previous_follow_ups=[],
            )

            return sanitize_follow_up_question(follow_up)

        except Exception as e:
            # 追问生成失败，使用默认提示
            return sanitize_follow_up_question(
                f"你刚才的回答还可以继续深入，能详细说说具体的实现细节吗？"
            )

    async def _finish_and_return(
        self, ctx: "AnswerPipelineContext", success: bool
    ) -> InterviewAnswerRespDTO:
        """完成并返回"""
        if success and ctx.response.is_success:
            # 记录轮次日志
            await self.interview_service.save_turn_log(
                session_id=ctx.session_id,
                request_id=ctx.request_id,
                question_number=ctx.current_question_number,
                question_content=ctx.current_question,
                answer_content=ctx.answer_content,
                score=ctx.score,
                total_score=ctx.total_score,
                feedback=ctx.response.feedback,
                is_follow_up=ctx.current_is_follow_up,
                follow_up_count=ctx.current_follow_up_count,
                next_question=ctx.response.next_question,
                next_question_number=ctx.response.next_question_number,
                finished=ctx.response.finished,
            )

            # 标记幂等成功
            cache_key = f"idempotency:{ctx.session_id}:{ctx.request_id}"
            await self.interview_service.set_cached_value(
                cache_key,
                ctx.response.model_dump() if hasattr(ctx.response, 'model_dump') else {
                    "is_success": ctx.response.is_success,
                    "score": ctx.score,
                    "total_score": ctx.total_score,
                    "feedback": ctx.response.feedback,
                    "next_question": ctx.response.next_question,
                    "next_question_number": ctx.response.next_question_number,
                    "is_follow_up": ctx.response.is_follow_up,
                    "follow_up_count": ctx.response.follow_up_count,
                    "finished": ctx.response.finished,
                },
                expire_seconds=3600,
            )

        return ctx.response


class AnswerPipelineContext:
    """答案管道上下文"""
    def __init__(self):
        self.session_id: str = ""
        self.request_id: str = ""
        self.question_number: str = ""
        self.answer_content: str = ""
        self.response: InterviewAnswerRespDTO = InterviewAnswerRespDTO.init()
        self.flow_state: Optional[dict] = None
        self.current_question: str = ""
        self.current_question_number: str = ""
        self.current_is_follow_up: bool = False
        self.current_follow_up_count: int = 0
        self.max_follow_up: int = MAX_FOLLOW_UP
        self.score: int = 0
        self.total_score: int = 0
        self.follow_up_needed_from_ai: bool = False
        self.follow_up_question_hint: Optional[str] = None
        self.idempotency_started: bool = False
