# 面试域不变量

面试域内必须遵守的业务约束，一旦违反会导致数据不一致或功能异常。

## 会话不变量

### Python 版本

- `InterviewRecord.session_id` 全局唯一。
- `InterviewRecord.user_id` 是归属判断唯一依据。
- `READY` 和 `ASKING` 才能恢复继续答题。
- `FINISHED` 和 `ABANDONED` 不应再进入答题编排。

### Java 版本（参考）

- `InterviewSession.sessionId` 全局唯一。
- `InterviewSession.userId` 是归属判断唯一依据。
- `READY` 和 `IN_PROGRESS` 才能恢复继续答题。
- `FINISHED` 和 `ABANDONED` 不应再进入答题编排。

## 流转不变量

- 题目流转状态和会话状态不是一个东西。
- `ASKING` / `EVALUATING` / `FOLLOW_UP` / `COMPLETED` 仅描述 flow。
- `current_question_number` 必须和请求题号一致，否则直接拒绝。
- 同题并发必须串行化（Redis 锁）。

## 评分不变量

- 评分结果必须包含 `score`。
- `follow_up_needed` 只能作为建议，最终是否追问要看 `should_generate_follow_up()` 和追问上限。
- **追问不直接累计总分**。
- 主问题分数只在成功返回前提交。

## 恢复不变量

- 恢复页必须优先读取主记录，再回补快照。
- 只读恢复不能冒充可写恢复。
- 快照和记录不一致时，应优先遵循更新更近、语义更强的运行态数据。
- 软回放和补偿必须保持题号连续性。

## 契约不变量

### Python 版本

- AI 输出字段必须和 Python 解析代码一致（`ai_client.py`）。
- `request_id` 是幂等边界，不是业务主键。
- `question_number`、`next_question_number`、`follow_up_count`、`finished` 一起构成答题响应语义。
- MongoDB ObjectId 必须转字符串才能序列化。

### Java 版本（参考）

- workflow 输出字段必须和 Java 解析字段一致。
- `requestId` 是幂等边界，不是业务主键。
- `questionNumber`、`nextQuestionNumber`、`followUpCount`、`finished` 一起构成答题响应语义。

## Python 特有不变量

### 异步不变量

- 所有服务层方法必须是 `async def`。
- 调用服务方法必须使用 `await`。
- 数据库操作使用 `await self.db.flush()`。

### 存储不变量

- MySQL `interview_record` 表存储会话主记录。
- MongoDB `interview_snapshots` 集合存储运行态快照。
- Redis 存储幂等缓存（30s）和成功响应（1h）。

### 序列化不变量

- MongoDB 返回的 `ObjectId` 必须用 `_serialize_snapshot()` 转字符串。
- API 响应注意 `snake_case` 和 `camelCase` 的转换。
