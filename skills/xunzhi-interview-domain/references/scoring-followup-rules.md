# 评分与追问规则

## Python 实现

文件位置：`app/application/interview/answer_pipeline.py` 和 `app/workflow/rules/interview_rules.py`

## 评分结果先于规则决策

1. **`ai_client.evaluate_answer()`** 返回结构化评分结果。
2. 代码统一归一化这些字段：`score`、`evaluation`、`follow_up_needed`、`follow_up_question`。
3. 如果 AI 返回格式异常，会回落到统一 schema 的兜底输出。

### 评分数据结构

```python
{
    "score": int,              # 0~100
    "accuracy": int,           # 准确性 (0-20)
    "completeness": int,       # 完整性 (0-20)
    "depth": int,              # 技术深度 (0-20)
    "clarity": int,            # 表达清晰度 (0-20)
    "relevance": int,          # 项目经验相关性 (0-20)
    "evaluation": str,         # AI 评价
    "suggestions": str,        # 改进建议
    "follow_up_needed": bool,  # 是否需要追问
    "follow_up_question": str, # 追问问题
}
```

## 规则引擎入口

### Python 追问决策

```python
def should_generate_follow_up(
    score: int,
    follow_up_count: int,
    max_follow_up: int = MAX_FOLLOW_UP,  # 默认 2
    follow_up_needed_from_ai: bool = False,
) -> tuple[bool, int]:
    """
    Returns: (是否需要追问, 解决后的最大追问次数)
    """
    resolved_max = max_follow_up if max_follow_up > 0 else MAX_FOLLOW_UP

    # 追问次数已达上限
    if follow_up_count >= resolved_max:
        return False, resolved_max

    # AI 建议需要追问
    if follow_up_needed_from_ai:
        return True, resolved_max

    # 分数低于阈值，需要追问
    if score < SCORE_THRESHOLD:  # 60分
        return True, resolved_max

    return False, resolved_max
```

### 追问配置参数

| 参数 | Python 默认值 | 说明 |
|------|---------------|------|
| `SCORE_THRESHOLD` | `60` | 低分阈值，低于此分触发追问 |
| `MAX_FOLLOW_UP` | `2` | 最大追问次数 |
| 追问问题长度限制 | 100 字符 | 超长截断 |

### `InterviewRuleEngine` 规则

文件：`app/workflow/rules/interview_rules.py`

```python
class InterviewRuleEngine:
    """面试规则引擎"""

    def evaluate_follow_up(self, state: InterviewState) -> InterviewState:
        """评估是否需要追问"""
        for rule in self.follow_up_rules:
            if rule.condition(state):
                return rule.action(state)
        return state

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
        return {...}
```

### 内置规则

| 规则名称 | 条件 | 动作 |
|----------|------|------|
| `high_score_continue` | 得分 >= 15 且追问次数 < 上限 | 进入追问 |
| `medium_score_assess` | 8 <= 得分 < 15 且追问次数 < 1 | 进入追问 |
| `incomplete_answer` | 回答不完整且追问次数 < 上限 | 进入追问 |
| `shallow_depth` | 技术深度不足且追问次数 < 上限 | 进入追问 |
| `max_follow_up_reached` | 追问次数 >= 上限 | 进入下一题 |
| `all_questions_done` | 所有问题完成 | 标记完成 |

## 决策原则

1. **AI 建议追问且未达上限** → 允许追问
2. **分数低于阈值 (60)** → 允许追问
3. **追问次数已达上限** → 拒绝追问，进入下一题
4. **规则引擎异常** → 回退到旧策略（AI 建议且未超限）

## 追问分支流程

```
评分结果返回
    ↓
should_generate_follow_up() 决策
    ↓
┌─────────────────────────────────────┐
│ need_follow_up = True               │
│ AND follow_up_count < resolved_max   │
└─────────────────────────────────────┘
    ↓ (满足条件)
_generate_follow_up() 生成追问问题
    ↓
save_follow_up_question() 保存追问
    ↓
update_flow_state() 更新状态
    ↓
返回追问内容 + follow_up_count
```

## Java 版本（参考）

### Java 规则配置

```yaml
# interview-followup-rule.yaml
default_followup_chain:
  chainId: "default"
  ruleVersion: "v1.0.0"
  fail-open: true
  default-max-follow-up: 2
  default-low-score-threshold: 60
```

### Java 关键类

- `InterviewFollowUpRuleContext` - 规则上下文
- `InterviewFollowUpRuleDecision` - 规则决策结果
- `InterviewAnswerPipeline.stepAdvanceFlowAndAssemble()` - 推进流程

## 你改规则时要同步看什么

### Python 版本

1. `app/application/interview/answer_pipeline.py` 中的：
   - `should_generate_follow_up()` 函数
   - `SCORE_THRESHOLD` 常量
   - `MAX_FOLLOW_UP` 常量
   - `_step_advance_flow_and_assemble()` 方法

2. `app/workflow/rules/interview_rules.py` 中的：
   - `InterviewRuleEngine` 类
   - `FollowUpRule` 定义

3. `app/agents/ai_client.py` 中的：
   - `evaluate_answer()` 方法
   - 评分 prompt

### Java 版本（参考）

1. `interview-followup-rule.yaml`
2. `liteflow/interview-followup-chain.xml`
3. `InterviewFollowUpRuleContext` / `InterviewFollowUpRuleDecision`
4. `InterviewAnswerPipeline.stepAdvanceFlowAndAssemble()`
5. `workflow/面试提问官.yml`
