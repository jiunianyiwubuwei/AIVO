"""面试工作流节点"""

from typing import AsyncIterator

from app.agents.ai_client import ai_client
from app.workflow.state import InterviewState, InterviewStatus, Question


async def init_interview(state: InterviewState) -> InterviewState:
    """初始化面试节点"""
    # 生成面试问题
    questions_data = await ai_client.generate_questions(
        direction=state.interview_direction,
        resume_content=state.metadata.get("resume_content"),
        count=state.total_questions,
    )

    # 构建问题列表
    questions = []
    for i, q_data in enumerate(questions_data):
        question = Question(
            id=q_data.get("id", f"q_{i+1}"),
            number=q_data.get("number", str(i + 1)),
            content=q_data.get("content", ""),
            category=q_data.get("category", "技术问题"),
            difficulty=q_data.get("difficulty", 3),
            expected_duration=q_data.get("expected_duration", 120),
        )
        questions.append(question)

    return state.model_copy(
        update={
            "questions": questions,
            "current_question_index": 0,
            "current_question": questions[0] if questions else None,
            "status": InterviewStatus.ASKING,
        }
    )


async def ask_question(state: InterviewState) -> InterviewState:
    """提问节点 - 生成并输出问题"""
    if not state.current_question:
        return state.model_copy(
            update={
                "status": InterviewStatus.COMPLETED,
                "error_message": "没有可用的面试问题",
            }
        )

    current_q = state.current_question

    # 构建面试提示
    prompt = f"""你是一个专业的技术面试官。请向候选人提出以下面试问题。

当前问题 ({current_q.number}/{state.total_questions}):
{current_q.content}

问题分类: {current_q.category}
难度等级: {current_q.difficulty}/5

请以面试官的身份，友好地提出这个问题，引导候选人回答。
如果有简历信息参考，请在提问时适当结合候选人的背景。"""

    if state.metadata.get("resume_content"):
        prompt += f"\n\n候选人简历信息:\n{state.metadata.get('resume_content')}"

    response = await ai_client.chat(
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )

    # 收集完整响应
    full_response = ""
    async for chunk in response:
        full_response += chunk

    return state.model_copy(
        update={
            "status": InterviewStatus.WAITING,
            "ai_message": full_response,
            "is_answer_complete": False,
        }
    )


async def receive_answer(state: InterviewState) -> InterviewState:
    """接收回答节点 - 处理用户输入"""
    user_answer = state.user_input.strip()

    if not user_answer:
        return state.model_copy(
            update={
                "error_message": "用户输入为空",
            }
        )

    # 保存回答到元数据
    answers = state.metadata.get("answers", [])
    answers.append({
        "question": state.current_question.content if state.current_question else "",
        "answer": user_answer,
        "question_index": state.current_question_index,
    })

    return state.model_copy(
        update={
            "metadata": {
                **state.metadata,
                "answers": answers,
            },
            "status": InterviewStatus.EVALUATING,
            "is_answer_complete": True,
        }
    )


async def evaluate_answer(state: InterviewState) -> InterviewState:
    """评估节点 - 评估用户回答"""
    if not state.current_question:
        return state.model_copy(
            update={
                "status": InterviewStatus.ERROR,
                "error_message": "当前没有问题可评估",
            }
        )

    # 获取当前回答
    answers = state.metadata.get("answers", [])
    current_answer = ""
    current_answer_index = -1
    for ans in reversed(answers):
        if ans.get("question_index") == state.current_question_index:
            current_answer = ans.get("answer", "")
            current_answer_index = answers.index(ans)
            break

    # 评估回答
    evaluation = await ai_client.evaluate_answer(
        question=state.current_question.content,
        answer=current_answer,
        follow_up_count=state.follow_up_count,
    )

    # 更新问题得分
    question_score = evaluation.get("score", 0)

    # 更新答案记录中的分数
    updated_answers = state.metadata.get("answers", [])
    if current_answer_index >= 0:
        updated_answers[current_answer_index] = {
            **updated_answers[current_answer_index],
            "score": question_score,
            "evaluation": evaluation.get("evaluation", ""),
        }

    # 更新状态
    new_total_score = state.total_score + question_score
    new_follow_up_count = state.follow_up_count

    # 根据评估结果决定是否追问
    should_follow_up = (
        question_score >= 30 and  # 得分较高，可以深入
        state.follow_up_count < state.max_follow_up and  # 未超过最大追问次数
        new_total_score < state.total_questions * 20  # 总分未满
    )

    return state.model_copy(
        update={
            "total_score": new_total_score,
            "follow_up_count": new_follow_up_count,
            "metadata": {
                **state.metadata,
                "answers": updated_answers,
            },
            "status": InterviewStatus.FOLLOW_UP if should_follow_up else InterviewStatus.ASKING,
            "ai_message": evaluation.get("evaluation", ""),
            "thinking": evaluation.get("suggestions", ""),
            "should_continue": True,
        }
    )


async def generate_follow_up(state: InterviewState) -> InterviewState:
    """追问节点 - 生成追问"""
    if not state.current_question:
        return state.model_copy(
            update={
                "status": InterviewStatus.ERROR,
                "error_message": "没有当前问题",
            }
        )

    # 获取之前的追问
    previous_follow_ups = state.current_question.follow_ups

    # 获取当前回答
    answers = state.metadata.get("answers", [])
    current_answer = ""
    for ans in reversed(answers):
        if ans.get("question_index") == state.current_question_index:
            current_answer = ans.get("answer", "")
            break

    # 生成追问
    follow_up_question = await ai_client.generate_follow_up(
        question=state.current_question.content,
        answer=current_answer,
        previous_follow_ups=previous_follow_ups,
    )

    # 更新追问计数
    new_follow_up_count = state.follow_up_count + 1

    # 更新问题的追问列表
    updated_questions = []
    for q in state.questions:
        if q.id == state.current_question.id:
            q.follow_ups.append(follow_up_question)
        updated_questions.append(q)

    return state.model_copy(
        update={
            "questions": updated_questions,
            "follow_up_count": new_follow_up_count,
            "status": InterviewStatus.WAITING,
            "ai_message": follow_up_question,
            "user_input": "",  # 清空用户输入，准备接收追问回答
        }
    )


async def next_question(state: InterviewState) -> InterviewState:
    """下一题节点"""
    next_index = state.current_question_index + 1

    # 检查是否完成所有问题
    if next_index >= state.total_questions:
        return state.model_copy(
            update={
                "status": InterviewStatus.COMPLETED,
                "should_continue": False,
            }
        )

    # 检查追问是否完成
    if state.follow_up_count >= state.max_follow_up:
        next_index = state.current_question_index + 1
        if next_index >= state.total_questions:
            return state.model_copy(
                update={
                    "status": InterviewStatus.COMPLETED,
                    "should_continue": False,
                }
            )

    return state.model_copy(
        update={
            "current_question_index": next_index,
            "current_question": state.questions[next_index] if next_index < len(state.questions) else None,
            "follow_up_count": 0,  # 重置追问计数
            "status": InterviewStatus.ASKING,
        }
    )


async def finish_interview(state: InterviewState) -> InterviewState:
    """完成面试节点 - 生成总结"""
    # 计算最终得分
    total_possible = state.total_questions * 20  # 每题最高20分
    interview_score = int((state.total_score / total_possible) * 100) if total_possible > 0 else 0

    # 生成总结
    answers = state.metadata.get("answers", [])
    summary = await ai_client.generate_summary(
        questions=state.questions,
        answers=answers,
    )

    return state.model_copy(
        update={
            "status": InterviewStatus.COMPLETED,
            "interview_score": interview_score,
            "interview_suggestions": summary,
            "should_continue": False,
            "ai_message": f"面试完成！\n\n面试得分: {interview_score}分\n\n{summary}",
        }
    )


def should_continue_interview(state: InterviewState) -> str:
    """条件路由 - 决定下一步"""
    if state.status == InterviewStatus.ERROR:
        return "error"

    if state.status == InterviewStatus.COMPLETED:
        return "finish"

    if state.status == InterviewStatus.WAITING:
        return "receive_answer"

    if state.status == InterviewStatus.ASKING:
        return "ask_question"

    if state.status == InterviewStatus.EVALUATING:
        return "evaluate_answer"

    if state.status == InterviewStatus.FOLLOW_UP:
        return "generate_follow_up"

    return "finish"
