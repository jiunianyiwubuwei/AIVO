# 答题流水线详解

`InterviewAnswerPipeline` 是面试域最核心的业务编排器。

## Python 实现

文件位置：`app/application/interview/answer_pipeline.py`

## 执行顺序

1. **参数校验**：验证 `session_id`、`question_number`、`answer_content` 是否为空。
2. **归一化 requestId**：保证幂等键稳定，调用 `generate_request_id()` 生成。
3. **幂等检查**：调 `_step_idempotency()` 做幂等门禁。
4. **加载当前题**：调 `_step_load_current_question()` 获取当前题目，拒绝过期题号。
5. **评分**：调 `_step_evaluate_and_score()` 获取 AI 评分。
6. **推进流程**：调 `_step_advance_flow_and_assemble()` 决定追问或下一题。
7. **收尾**：调用 `_finish_and_return()` 保存轮次日志和幂等缓存。

## 幂等门禁

```python
# 检查是否有正在处理的请求
cache_key = f"idempotency:{session_id}:{request_id}"
existing = await self.interview_service.get_cached_value(cache_key)
if existing:
    # 命中成功回放时，不再重新评分，直接返回历史响应
    ctx.response = InterviewAnswerRespDTO(**existing)
    return False

# 标记为处理中（设置较短过期时间）
await self.interview_service.set_cached_value(
    cache_key,
    {"status": "processing"},
    expire_seconds=30,
)
```

**返回语义**：
- 处理中返回：`current request is processing, please retry later`
- 命中成功回放时：直接返回历史响应，不再重新评分

## 题号保护

```python
# 归一化题号
normalized_requested = normalize_question_number(ctx.question_number)
normalized_current = normalize_question_number(ctx.current_question_number)
if normalized_requested != normalized_current:
    ctx.response.fail("stale question number, please refresh current question")
    return False
```

**返回语义**：
- 过期题号返回：`stale question number, please refresh current question`
- Redis 锁冲突返回：`current question is processing, please retry later`
- 题目不存在返回：`no questions found` 或 `current question not found`

## 题号工具函数

| 函数 | 作用 | 示例 |
|------|------|------|
| `normalize_question_number()` | 归一化题号格式 | `"1"` → `"1"`, `" 1 "` → `"1"` |
| `is_follow_up_question()` | 判断是否追问 | `"1-F1"` → `True`, `"1"` → `False` |
| `extract_main_question_number()` | 提取主问题号 | `"1-F2"` → `"1"` |
| `extract_follow_up_count()` | 提取追问次数 | `"1-F2"` → `2` |
| `build_follow_up_question_number()` | 构建追问题号 | `"1", 1` → `"1-F1"` |

## 评分结构化结果

当前代码约定的主字段（`ai_client.py` 的 `evaluate_answer()`）：

```python
{
    "score": int,              # 0~100 的整数
    "accuracy": int,           # 准确性得分
    "completeness": int,       # 完整性得分
    "depth": int,              # 技术深度得分
    "clarity": int,            # 表达清晰度得分
    "relevance": int,          # 项目经验相关性得分
    "evaluation": str,          # 详细评价文字
    "suggestions": str,        # 改进建议
    "follow_up_needed": bool,   # 是否需要追问
    "follow_up_question": str   # 追问问题
}
```

## 追问分支

```python
def should_generate_follow_up(
    score: int,
    follow_up_count: int,
    max_follow_up: int = MAX_FOLLOW_UP,  # 默认 2
    follow_up_needed_from_ai: bool = False,
) -> tuple[bool, int]:
```

**追问条件**（满足任一即可）：
1. AI 建议追问且未达上限
2. 分数低于阈值（60分）

**追问题号格式**：`{主问题号}-F{追问次数}`，如 `"1-F1"`, `"1-F2"`

## 分数提交与补偿

- **只有主问题计入总分**，追问本身不累计总分
- 分数是在"返回成功前"提交到快照
- 如果 `flow_state` 更新失败，会回滚客户端重试时仍命中当前题

## 与恢复链路的关系

- 载入当前题时会调用 `get_snapshot()` 获取运行时状态
- 如果快照为空，返回"interview session not found"
- 成功提交后会调用 `save_turn_log()` 保存轮次日志

## Java 版本（参考）

Java 版本使用 `InterviewAnswerPipeline.java`，核心流程类似但实现细节不同：

1. 使用 LiteFlow 做流程编排
2. 使用 Redis 做分布式锁
3. 使用 LiteFlow 规则引擎做追问决策

### Java 关键类

- `InterviewAnswerIdempotencyService.tryStart()` - 幂等门禁
- `InterviewFlowStateMachine` - 状态机
- `InterviewFollowUpRuleService.decide()` - 追问规则引擎
