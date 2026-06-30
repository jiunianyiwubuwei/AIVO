# Workflow 契约索引

## 重要说明

### Python 版本

Python 版本使用 **LangGraph + AI Client** 而非 Java 版本的 **LiteFlow + YAML**。

AI 调用契约定义在 `app/agents/ai_client.py` 中，通过 prompt 定义而非 YAML 文件。

### Java 版本（参考）

Java 版本使用 `scripts/extract_workflow_contracts.py` 从 `admin/src/main/resources/workflow/*.yml` 自动提取契约。

---

## Python AI 契约

### 问题生成 (`generate_questions`)

**返回格式**:

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
    "resumeStrengths": ["优点1"],
    "resumeWeaknesses": ["缺点1"],
    "type": "面试方向"
}
```

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `questions` | array | 是 | 问题列表 |
| `resumeScore` | int | 是 | 简历评分 0-100 |
| `resumeAnalysis` | string | 是 | 简历分析文本 |
| `resumeStrengths` | array | 否 | 简历优点 |
| `resumeWeaknesses` | array | 否 | 简历缺点 |
| `type` | string | 是 | 面试方向 |

### 答案评分 (`evaluate_answer`)

**返回格式**:

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

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `score` | int | 是 | 总分 0-100 |
| `accuracy` | int | 是 | 准确性 0-20 |
| `completeness` | int | 是 | 完整性 0-20 |
| `depth` | int | 是 | 技术深度 0-20 |
| `clarity` | int | 是 | 表达清晰度 0-20 |
| `relevance` | int | 是 | 项目经验相关性 0-20 |
| `evaluation` | string | 是 | AI 评价文本 |
| `suggestions` | string | 是 | 改进建议 |
| `follow_up_needed` | bool | 是 | 是否需要追问 |
| `follow_up_question` | string | 否 | 追问问题 |

### 追问生成 (`generate_follow_up`)

**返回格式**: 直接返回追问问题文本字符串

### 面试总结 (`generate_summary`)

**返回格式**: 直接返回总结文本，包含以下章节：

```
## 整体评价
## 亮点总结
## 待改进点
## 下一步建议
```

---

## Java Workflow 契约（参考）

Java 版本从 YAML 文件提取，详见原始文档。
