# AI 契约提取脚本（Python 版本）

Python 版本使用 LangGraph + AI Client，而非 Java 版本的 LiteFlow + YAML。

## Python 工作流结构

Python 版本的 AI 调用契约定义在以下文件中：

| 功能 | 文件 | 方法 |
|------|------|------|
| 问题生成 | `app/agents/ai_client.py` | `AIModelClient.generate_questions()` |
| 答案评分 | `app/agents/ai_client.py` | `AIModelClient.evaluate_answer()` |
| 追问生成 | `app/agents/ai_client.py` | `AIModelClient.generate_follow_up()` |
| 面试总结 | `app/agents/ai_client.py` | `AIModelClient.generate_summary()` |

## 契约提取方式

由于 Python 版本使用代码定义 prompt 而非 YAML 文件，契约信息需要通过代码审查获取。

### 提取评分契约

```python
# 查看 ai_client.py 中的 evaluate_answer() 方法
async def evaluate_answer(self, question: str, answer: str, follow_up_count: int = 0) -> dict:
    """评估回答"""
    # prompt 中定义了期望返回的 JSON 格式
```

### 提取问题生成契约

```python
# 查看 ai_client.py 中的 _build_question_generation_prompt() 方法
def _build_question_generation_prompt(self, direction: str, resume_content: Optional[str], count: int) -> str:
    """构建问题生成提示"""
    # prompt 中定义了期望返回的 JSON 格式
```

## 契约格式示例

### 问题生成返回格式

```json
{
    "questions": [
        {
            "id": "q_1",
            "number": "1",
            "content": "问题内容",
            "category": "分类",
            "difficulty": 3,
            "expected_duration": 120
        }
    ],
    "resumeScore": 80,
    "resumeAnalysis": "简历分析...",
    "resumeStrengths": ["优点1", "优点2"],
    "resumeWeaknesses": ["缺点1"],
    "type": "面试方向"
}
```

### 评分返回格式

```json
{
    "score": 85,
    "accuracy": 17,
    "completeness": 16,
    "depth": 17,
    "clarity": 17,
    "relevance": 18,
    "evaluation": "详细评价...",
    "suggestions": "改进建议...",
    "follow_up_needed": false,
    "follow_up_question": null
}
```

## Java 版本（参考）

Java 版本使用 `scripts/extract_workflow_contracts.py` 从 YAML 文件提取契约：

```bash
python scripts/extract_workflow_contracts.py
```

这会更新 `references/generated-workflow-contracts.md` 文件。

## 维护建议

1. **修改 prompt 时**：同步更新本文档和代码注释
2. **修改返回格式时**：同步更新 `answer_pipeline.py` 中的解析逻辑
3. **添加新 AI 接口时**：在 `ai_client.py` 中定义，并更新本文档
