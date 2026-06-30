# 面试状态机

面试域里至少有两套状态，需要严格区分。

## Python 实现

文件位置：`app/workflow/state.py`

## 会话状态 vs 流程状态

### 会话状态 (Session Status)

存储在 `interview_record.interview_status` 字段：

| 状态 | Python 值 | 说明 |
|------|-----------|------|
| 草稿 | `"DRAFT"` | 刚创建，尚未上传或提取简历 |
| 上传中 | `"RESUME_UPLOADING"` | 正在上传并提取简历 |
| 就绪 | `"READY"` | 题目、方向、简历地址已准备好 |
| 进行中 | `"IN_PROGRESS"` 或 `"ASKING"` | 已经开始取题或答题 |
| 完成 | `"FINISHED"` | 已完成面试并收尾 |
| 废弃 | `"ABANDONED"` | 已废弃或不可继续 |

### 流程状态 (Flow Status)

使用 `InterviewStatus` 枚举（`app/workflow/state.py`）：

```python
class InterviewStatus(str, Enum):
    DRAFT = "DRAFT"          # 草稿/未启动
    READY = "READY"          # 就绪
    INIT = "INIT"            # 初始化
    ASKING = "ASKING"        # 提问中
    WAITING = "WAITING"      # 等待用户回答
    EVALUATING = "EVALUATING"  # 评估回答
    FOLLOW_UP = "FOLLOW_UP"  # 追问
    COMPLETED = "COMPLETED"  # 面试完成
    FINISHED = "FINISHED"    # 面试结束（最终状态）
    ERROR = "ERROR"          # 错误状态
```

## Flow 合法流转

```
INIT → ASKING → WAITING → EVALUATING → FOLLOW_UP
                ↓                      ↓
              ASKING ←──────────────┘
                ↓
            COMPLETED
                ↓
             FINISHED
```

**详细流转规则**：

| 当前状态 | 合法下一状态 |
|----------|--------------|
| `INIT` | `ASKING`, `COMPLETED` |
| `ASKING` | `WAITING`, `ERROR`, `COMPLETED` |
| `WAITING` | `EVALUATING`, `ERROR`, `COMPLETED` |
| `EVALUATING` | `FOLLOW_UP`, `ASKING`（下一题）, `COMPLETED` |
| `FOLLOW_UP` | `EVALUATING`, `ASKING`（下一题）, `COMPLETED` |
| `COMPLETED` | `FINISHED` |

## 关键方法

### Python 关键函数

| 方法 | 位置 | 作用 |
|------|------|------|
| `_step_load_current_question()` | `answer_pipeline.py` | 加载当前题目，校验题号 |
| `_step_evaluate_and_score()` | `answer_pipeline.py` | 调用 AI 评分 |
| `_step_advance_flow_and_assemble()` | `answer_pipeline.py` | 推进流程，处理追问/下一题 |
| `should_generate_follow_up()` | `answer_pipeline.py` | 判断是否需要追问 |
| `rule_engine.evaluate_follow_up()` | `interview_rules.py` | 规则引擎决策 |

### 状态推进逻辑

```python
# 追问分支
if need_follow_up and current_follow_up_count < resolved_max:
    follow_up_question = await self._generate_follow_up(ctx)
    # 更新 flow_state
    await self.interview_service.update_flow_state(
        session_id,
        {
            "follow_up_count": new_follow_up_count,
            "current_follow_up_question": follow_up_question,
            "current_question_number": follow_up_number,
        }
    )

# 无追问时，推进主问题
next_index = current_index + 1
if next_index >= total_questions:
    await self.interview_service.update_flow_state(
        session_id,
        {"status": "completed", "current_index": next_index}
    )
```

## 题号规则

### 题号格式

- **主问题题号**：纯数字字符串，如 `"1"`, `"2"`, `"3"`
- **追问题号**：`{主问题号}-F{追问次数}`，如 `"1-F1"`, `"1-F2"`, `"2-F1"`

### 题号解析

```python
def normalize_question_number(question_number: str) -> Optional[str]:
    """归一化题号"""
    # "1" → "1", " 1 " → "1", "01" → "1"

def is_follow_up_question(question_number: str) -> bool:
    """判断是否追问"""
    # "1-F1" → True, "1" → False

def extract_main_question_number(question_number: str) -> Optional[str]:
    """提取主问题号"""
    # "1-F2" → "1"

def extract_follow_up_count(question_number: str) -> int:
    """提取追问次数"""
    # "1-F2" → 2, "1" → 0
```

## Java 版本（参考）

### Java 会话状态

```java
public enum InterviewSessionStatus {
    DRAFT,           // 草稿
    RESUME_UPLOADING, // 简历上传中
    READY,           // 就绪
    IN_PROGRESS,     // 进行中
    FINISHED,        // 完成
    ABANDONED        // 废弃
}
```

### Java 流程状态

```java
public enum InterviewFlowStatus {
    INIT,        // 初始化
    ASKING,      // 提问中
    EVALUATING,  // 评估中
    FOLLOW_UP,   // 追问
    COMPLETED    // 完成
}
```

### Java 状态机关键方法

| 方法 | 作用 |
|------|------|
| `moveToEvaluating()` | 进入评分阶段 |
| `moveToFollowUp()` | 进入追问阶段 |
| `startFollowUpQuestion()` | 在 flow 合法的前提下创建追问题号 |
| `advanceMainQuestion()` | 推进到下一主问题；如果越界则改为完成 |
| `markCompleted()` | 显式收口 |

## 实战提醒

- **改题号推进时**，必须同时考虑主问题和追问题号的更新。
- **会话状态变成 `FINISHED`** 并不自动等于 flow 已完成，`finish_interview` 接口需要统一打通。
- **题号不匹配时**，直接拒绝答题，避免客户端重试时状态错乱。
