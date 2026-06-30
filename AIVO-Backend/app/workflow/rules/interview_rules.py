"""面试规则引擎"""

from typing import Callable
from app.workflow.state import InterviewState, InterviewStatus


class FollowUpRule:
    """追问规则"""

    def __init__(
        self,
        name: str,
        condition: Callable[[InterviewState], bool],
        action: Callable[[InterviewState], InterviewState],
        priority: int = 0,
    ):
        self.name = name
        self.condition = condition
        self.action = action
        self.priority = priority


class InterviewRuleEngine:
    """面试规则引擎"""

    def __init__(self):
        self.follow_up_rules: list[FollowUpRule] = []
        self._register_default_rules()

    def _register_default_rules(self):
        """注册默认规则"""

        # 规则1: 得分较高，继续追问
        self.add_follow_up_rule(
            name="high_score_continue",
            condition=lambda state: (
                state.metadata.get("last_score", 0) >= 15 and
                state.follow_up_count < state.max_follow_up
            ),
            action=lambda state: state.model_copy(
                update={"status": InterviewStatus.FOLLOW_UP}
            ),
            priority=10,
        )

        # 规则2: 得分中等，评估后决定
        self.add_follow_up_rule(
            name="medium_score_assess",
            condition=lambda state: (
                8 <= state.metadata.get("last_score", 0) < 15 and
                state.follow_up_count < 1
            ),
            action=lambda state: state.model_copy(
                update={"status": InterviewStatus.FOLLOW_UP}
            ),
            priority=5,
        )

        # 规则3: 回答不完整，追问
        self.add_follow_up_rule(
            name="incomplete_answer",
            condition=lambda state: (
                state.metadata.get("is_answer_incomplete", False) and
                state.follow_up_count < state.max_follow_up
            ),
            action=lambda state: state.model_copy(
                update={"status": InterviewStatus.FOLLOW_UP}
            ),
            priority=8,
        )

        # 规则4: 技术深度不足，追问
        self.add_follow_up_rule(
            name="shallow_depth",
            condition=lambda state: (
                state.metadata.get("depth_insufficient", False) and
                state.follow_up_count < state.max_follow_up
            ),
            action=lambda state: state.model_copy(
                update={"status": InterviewStatus.FOLLOW_UP}
            ),
            priority=7,
        )

        # 规则5: 追问次数已达上限，进入下一题
        self.add_follow_up_rule(
            name="max_follow_up_reached",
            condition=lambda state: (
                state.follow_up_count >= state.max_follow_up
            ),
            action=lambda state: state.model_copy(
                update={"status": InterviewStatus.ASKING}
            ),
            priority=100,  # 最高优先级
        )

        # 规则6: 所有问题完成
        self.add_follow_up_rule(
            name="all_questions_done",
            condition=lambda state: (
                state.current_question_index >= state.total_questions - 1 and
                state.follow_up_count >= state.max_follow_up
            ),
            action=lambda state: state.model_copy(
                update={
                    "status": InterviewStatus.COMPLETED,
                    "should_continue": False,
                }
            ),
            priority=100,
        )

    def add_follow_up_rule(
        self,
        name: str,
        condition: Callable[[InterviewState], bool],
        action: Callable[[InterviewState], InterviewState],
        priority: int = 0,
    ):
        """添加追问规则"""
        rule = FollowUpRule(name, condition, action, priority)
        self.follow_up_rules.append(rule)
        # 按优先级排序
        self.follow_up_rules.sort(key=lambda r: r.priority, reverse=True)

    def evaluate_follow_up(self, state: InterviewState) -> InterviewState:
        """评估是否需要追问"""
        for rule in self.follow_up_rules:
            if rule.condition(state):
                return rule.action(state)

        # 默认进入下一题
        return state.model_copy(
            update={"status": InterviewStatus.ASKING}
        )

    def evaluate_answer_quality(
        self,
        score: int,
        completeness: int,
        depth: int,
        clarity: int,
    ) -> dict:
        """评估回答质量"""
        quality_flags = {
            "is_high_quality": score >= 15,
            "is_answer_incomplete": completeness < 10,
            "depth_insufficient": depth < 8,
            "clarity_issue": clarity < 8,
        }

        return {
            "flags": quality_flags,
            "should_follow_up": (
                quality_flags["is_high_quality"] or
                quality_flags["depth_insufficient"]
            ),
            "priority": self._calculate_priority(quality_flags),
        }

    def _calculate_priority(self, flags: dict) -> int:
        """计算追问优先级"""
        if flags.get("depth_insufficient"):
            return 8
        if flags.get("is_answer_incomplete"):
            return 7
        if flags.get("is_high_quality"):
            return 5
        return 0


# 全局规则引擎
rule_engine = InterviewRuleEngine()
