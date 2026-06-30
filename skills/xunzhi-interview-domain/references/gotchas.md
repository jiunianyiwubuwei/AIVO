# 面试域易错点

## 最容易混淆的几件事

- 不要把会话状态和 flow 状态混为一谈。
- 不要只改 workflow prompt，不改 Python 解析字段（`ai_client.py` 中的 JSON 解析逻辑）。
- 不要在答题链路绕过幂等检查和同题加锁（`answer_pipeline.py` 中的 Redis 操作）。
- 不要让追问直接累计到总分，当前实现只累计主问题分数。
- 不要假设恢复接口只读数据库，它会主动触发运行态回填。
- 不要在可写场景使用只读恢复结果，否则会遇到 `read-only` 失败。

## Python/Java 易错点对比

### Python 特有

- **async/await 缺失**：所有服务层方法都必须是 `async def`，漏掉会导致 `coroutine was never awaited` 错误。
- **SQLAlchemy 会话管理**：必须使用 `await self.db.flush()` 而不是直接 commit，漏掉会导致数据未保存。
- **MongoDB ObjectId**：从 MongoDB 读取的数据包含 `ObjectId`，需要用 `_serialize_snapshot()` 转换才能返回给前端。
- **Pydantic 模型验证**：请求体使用 `BaseModel`，但 API 返回需要确保字段名匹配前端期望（驼峰命名）。
- **Redis 连接池**：使用 `redis_client` 时注意异步操作需要 `await`。

### Java/Python 共性

| 易错点 | Java 侧 | Python 侧 |
|--------|---------|-----------|
| 状态混用 | `InterviewSession.status` vs `InterviewFlowState` | `interview_status` vs `InterviewStatus` 枚举 |
| 题号语义 | `questionNumber` 可能是追问 | 同样，可能是 `1`、`1-F1`、`1-F2` |
| 幂等边界 | `requestId` | 同上，生成逻辑在 `generate_request_id()` |
| 快照刷新时机 | 答题成功后刷新 | `save_turn_log()` 时同步更新 |

## 现象到检查点

### Python 版本

| 现象 | 第一检查点 | 常见原因 |
|------|------------|----------|
| 一直无法答题推进 | `answer_pipeline.py` 前半段（`_step_idempotency` 到 `_step_load_current_question`） | requestId 不稳定、Redis 锁冲突、旧题号 |
| 评分结果字段缺失 | `ai_client.py` 的 `evaluate_answer()` 输出 | prompt 解析失败、JSON 格式问题 |
| 追问次数不对 | `answer_pipeline.py` 的 `should_generate_follow_up()` + `rule_engine` | 规则引擎、 `MAX_FOLLOW_UP` 配置或题号状态 |
| 恢复页内容不完整 | `get_snapshot()` + `/restore` 接口 | 会话主记录、题目快照、缓存三层回填 |
| 总分回退或不一致 | `interview_service.py` 的快照刷新 | 缓存刷新时机、补偿逻辑问题 |
| 前端字段取不到 | API 返回的字典 key vs Pydantic 字段名 | 注意 `snake_case` vs `camelCase` 转换 |
| MongoDB 查询返回空 | `_serialize_snapshot()` 未调用 | `ObjectId` 未转字符串导致 JSON 序列化失败 |

### Java 版本（参考）

| 现象 | 第一检查点 | 常见原因 |
|------|------------|----------|
| 一直无法答题推进 | `InterviewAnswerPipeline` 前半段 | requestId 不稳定、同题锁冲突、旧题号 |
| 评分结果字段缺失 | `InterviewEvaluationService` 输出 | workflow 字段和 Java 解析不一致 |
| 追问次数不对 | `InterviewFollowUpRuleService` + flow 中追问计数 | 规则引擎、默认上限或当前题号状态错了 |
| 恢复页内容不完整 | `restoreInterviewSession` | 会话主记录、题目表、缓存三层回填不一致 |
| 总分回退或不一致 | `InterviewSessionRuntimeSnapshotService` | 缓存刷新时机、回滚补偿、记录同步问题 |

## 一个实用判断

- 如果问题描述里有"题号""追问""评分""恢复"，优先看面试域，不要先去怀疑通用 Agent。
- 如果问题描述里有"只读""回放""回滚"，优先看运行态恢复和快照，不要只盯 controller。
- 如果问题描述里有"结果缺字段"，优先看 `ai_client.py` 的 JSON 解析逻辑，不要只看业务代码。
- 如果问题描述里有"异步报错""coroutine"，优先检查是否漏了 `await` 或 `async def`。
