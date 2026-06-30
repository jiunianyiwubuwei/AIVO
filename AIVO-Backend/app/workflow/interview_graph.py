"""面试工作流 - LangGraph 实现"""

from typing import Annotated, Literal

from langgraph.graph import StateGraph, END

from app.workflow.state import InterviewState, InterviewStatus
from app.workflow.nodes.interview_nodes import (
    init_interview,
    ask_question,
    receive_answer,
    evaluate_answer,
    generate_follow_up,
    next_question,
    finish_interview,
    should_continue_interview,
)
from app.workflow.rules.interview_rules import rule_engine
from app.agents.ai_client import ai_client


def create_interview_graph() -> StateGraph:
    """创建面试工作流图"""

    # 定义工作流
    workflow = StateGraph(InterviewState)

    # 添加节点
    workflow.add_node("init", init_interview)
    workflow.add_node("ask_question", ask_question)
    workflow.add_node("receive_answer", receive_answer)
    workflow.add_node("evaluate_answer", evaluate_answer)
    workflow.add_node("generate_follow_up", generate_follow_up)
    workflow.add_node("next_question", next_question)
    workflow.add_node("finish", finish_interview)

    # 设置入口点
    workflow.set_entry_point("init")

    # 添加条件边
    workflow.add_conditional_edges(
        "init",
        should_continue_interview,
        {
            "ask_question": "ask_question",
            "error": END,
            "finish": "finish",
        }
    )

    workflow.add_conditional_edges(
        "ask_question",
        should_continue_interview,
        {
            "receive_answer": "receive_answer",
            "error": END,
            "finish": "finish",
        }
    )

    workflow.add_conditional_edges(
        "receive_answer",
        should_continue_interview,
        {
            "evaluate_answer": "evaluate_answer",
            "error": END,
            "finish": "finish",
        }
    )

    workflow.add_conditional_edges(
        "evaluate_answer",
        should_continue_interview,
        {
            "generate_follow_up": "generate_follow_up",
            "ask_question": "next_question",
            "error": END,
            "finish": "finish",
        }
    )

    workflow.add_conditional_edges(
        "generate_follow_up",
        should_continue_interview,
        {
            "receive_answer": "receive_answer",
            "next_question": "next_question",
            "error": END,
            "finish": "finish",
        }
    )

    workflow.add_conditional_edges(
        "next_question",
        should_continue_interview,
        {
            "ask_question": "ask_question",
            "error": END,
            "finish": "finish",
        }
    )

    workflow.add_edge("finish", END)

    return workflow.compile()


class InterviewWorkflow:
    """面试工作流管理器"""

    def __init__(self):
        self.graph = create_interview_graph()

    async def run(self, initial_state: InterviewState) -> InterviewState:
        """运行工作流"""
        result = await self.graph.ainvoke(initial_state)
        return result

    async def run_with_human_input(
        self,
        initial_state: InterviewState,
        user_input: str,
    ) -> InterviewState:
        """带人工输入运行工作流"""
        # 更新状态中的用户输入
        current_state = initial_state.model_copy(
            update={"user_input": user_input}
        )

        # 根据当前状态选择下一个节点执行
        if current_state.status == InterviewStatus.INIT:
            result = await self.graph.ainvoke(current_state)
        elif current_state.status == InterviewStatus.WAITING:
            # 接收用户回答
            updated_state = await receive_answer(current_state)
            result = await self.graph.ainvoke(updated_state)
        else:
            result = await self.graph.ainvoke(current_state)

        return result


# 全局工作流实例
interview_workflow = InterviewWorkflow()


async def run_interview_init(
    session_id: str,
    user_id: int,
    interview_direction: str = None,
    resume_content: str = None,
) -> dict:
    """初始化面试并返回问题列表和简历分析"""
    from app.workflow.state import InterviewState, Question

    # 创建初始状态
    initial_state = InterviewState(
        session_id=session_id,
        user_id=user_id,
        interview_direction=interview_direction or "通用技术面试",
        metadata={
            "resume_content": resume_content,
            "answers": [],
        },
        questions=[],
        current_question=None,
        current_question_index=0,
        total_questions=5,
        follow_up_count=0,
        max_follow_up=2,
        total_score=0,
        status=InterviewStatus.INIT,
    )

    # 只运行初始化节点
    result = await init_interview(initial_state)

    # 获取简历分析和评分
    resume_analysis = ai_client.get_last_resume_analysis()
    resume_score = resume_analysis.get("score") if resume_analysis else None

    # 返回问题列表和简历分析
    return {
        "questions": [
            {
                "id": q.id,
                "number": q.number,
                "content": q.content,
                "category": q.category,
                "difficulty": q.difficulty,
                "expected_duration": q.expected_duration,
            }
            for q in result.questions
        ],
        "resume_score": resume_score,
        "resume_analysis": resume_analysis,
    }
