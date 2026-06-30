# 面试工作流契约

面试域的工作流不是"补充资料"，而是正式契约的一部分。

## Python 工作流实现

Python 版本使用 **LangGraph** 实现工作流，而非 Java 版本的 **LiteFlow + YAML**。

### 工作流文件

| 功能 | Java (YAML) | Python |
|------|-------------|--------|
| 出题 | `面试题出题官.yml` | `ai_client.generate_questions()` |
| 评分 | `用户答案评分官.yml` | `ai_client.evaluate_answer()` |
| 追问 | `面试提问官.yml` | `ai_client.generate_follow_up()` |
| 简历评分 | `简历评分面试官.yml` | `ai_client.generate_questions()` 中 |
| 神态分析 | `表情分析面试官.yml` | `mediapipe/` 模块 |

### 工作流图结构

文件：`app/workflow/interview_graph.py`

```
┌─────────┐
│   init  │  初始化面试
└────┬────┘
     │
     ▼
┌─────────┐
│ask_question│ 提问
└────┬────┘
     │
     ▼
┌─────────┐
│receive_answer│ 接收回答
└────┬────┘
     │
     ▼
┌─────────┐
│evaluate_answer│ 评分
└────┬────┘
     │
     ▼
┌───────────────┐    ┌─────────────┐
│generate_follow_up│→│next_question│
└───────┬───────┘    └──────┬──────┘
        │                   │
        └───────┬───────────┘
                ▼
            ┌──────┐
            │finish│
            └──┬───┘
               ▼
              END
```

### 节点说明

| 节点 | 函数 | 作用 |
|------|------|------|
| `init` | `init_interview()` | 初始化面试状态，生成问题 |
| `ask_question` | `ask_question()` | 生成当前问题 |
| `receive_answer` | `receive_answer()` | 接收用户回答 |
| `evaluate_answer` | `evaluate_answer()` | 评分 |
| `generate_follow_up` | `generate_follow_up()` | 生成追问 |
| `next_question` | `next_question()` | 推进到下一题 |
| `finish` | `finish_interview()` | 结束面试 |

## 契约维护方式

### Python 版本

1. **AI 调用契约** 在 `app/agents/ai_client.py` 中定义
2. **结构化字段变更**时，必须同步修改：
   - `ai_client.py` 中的 prompt
   - `answer_pipeline.py` 中的解析逻辑
   - `InterviewAnswerRespDTO` 的字段
3. **JSON 解析** 使用 `json.loads()` + `result.get()` 访问

### Java 版本（参考）

1. **YAML 工作流** 变更需要同步修改 Java 解析代码
2. **运行脚本** `scripts/extract_workflow_contracts.py` 提取契约
3. **自动文档** `references/generated-workflow-contracts.md`

## 输出字段契约

### 评分输出 (`evaluate_answer`)

```python
# ai_client.py 返回格式
{
    "score": int,              # 0~100
    "accuracy": int,           # 0-20
    "completeness": int,       # 0-20
    "depth": int,              # 0-20
    "clarity": int,            # 0-20
    "relevance": int,          # 0-20
    "evaluation": str,          # 评价文本
    "suggestions": str,        # 建议文本
    "follow_up_needed": bool,  # 是否追问
    "follow_up_question": str, # 追问问题
}
```

### 问答响应 (`InterviewAnswerRespDTO`)

```python
class InterviewAnswerRespDTO:
    question_number: str        # 题号
    question_content: str       # 题目内容
    score: int                 # 本次得分
    total_score: int           # 累计总分
    is_success: bool           # 是否成功
    error_message: str         # 错误信息
    feedback: str              # AI评价
    next_question: str        # 下一题
    next_question_number: str  # 下一题号
    is_follow_up: bool         # 是否追问
    follow_up_count: int       # 当前追问次数
    finished: bool             # 是否结束
```

## Java 工作流契约（参考）

### YAML 工作流列表

- `面试题出题官.yml` - 生成面试问题
- `用户答案评分官.yml` - 评分回答
- `面试提问官.yml` - 追问问题
- `简历评分面试官.yml` - 简历评分
- `表情分析面试官.yml` - 神态分析

### 契约维护（Java）

- 结构化字段变更时，必须同步修改工作流 YAML、Java 解析代码和下游 DTO
- 改动后重新运行 `scripts/extract_workflow_contracts.py`，刷新自动生成文档
