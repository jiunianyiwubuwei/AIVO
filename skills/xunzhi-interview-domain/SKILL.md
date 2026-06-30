---
name: xunzhi-interview-domain
description: AI-Meeting 面试业务知识 Skill。用于处理面试会话创建、简历提题、答题评分、追问、恢复、简历预览、神态分析、收尾归档、工作流契约和面试状态机相关需求；当需求命中 `/api/xunzhi/v1/interview/**`、`workflow/*.py` 或面试运行态恢复逻辑时使用。
---

# xunzhi-interview-domain

只要需求落到面试主链路，就使用这个 Skill。

## 使用顺序

- 再看 `references/object-dictionary.md` 和 `references/invariants.md`，确认对象模型和不可破坏的业务约束。
- 先看 `references/lifecycle.md`，确认会话处于哪个业务阶段。
- 再看 `references/answer-pipeline.md`，确认答题是如何做幂等、加锁、评分和推进的。
- 改状态推进时看 `references/state-machine.md`。
- 改评分、追问、规则引擎时看 `references/scoring-followup-rules.md`。
- 改工作流字段、结构化输出时看 `references/workflow-contracts.md` 和 `references/generated-workflow-contracts.md`。
- 改恢复、收尾、快照、会话重建时看 `references/restore-and-finalize.md`。

## 关键入口

### Python 版本入口

- **API 控制器**: `app/api/v1/interview.py`
- **面试服务**: `app/application/interview/interview_service.py`
- **答案处理管道**: `app/application/interview/answer_pipeline.py`
- **状态定义**: `app/workflow/state.py`
- **规则引擎**: `app/workflow/rules/interview_rules.py`
- **工作流图**: `app/workflow/interview_graph.py`
- **AI 客户端**: `app/agents/ai_client.py`
- **数据库模型**: `app/infrastructure/database/models.py`
- **MongoDB 客户端**: `app/infrastructure/cache/mongodb_client.py`
- **Redis 客户端**: `app/infrastructure/cache/redis_client.py`

### Java 版本入口（参考）

- `admin/src/main/java/com/hewei/hzyjy/xunzhi/interview/api/InterviewSessionController.java`
- `admin/src/main/java/com/hewei/hzyjy/xunzhi/interview/api/InterviewResumeController.java`
- `admin/src/main/java/com/hewei/hzyjy/xunzhi/interview/flow/session/InterviewSessionFacade.java`
- `admin/src/main/java/com/hewei/hzyjy/xunzhi/interview/flow/answer/InterviewAnswerPipeline.java`
- `admin/src/main/java/com/hewei/hzyjy/xunzhi/interview/application/flow/InterviewFlowStateMachine.java`

## Python/Java 对照表

| 功能 | Java 类/包 | Python 模块/文件 |
|------|------------|------------------|
| 会话门面 | `InterviewSessionFacade` | `InterviewService` (`interview_service.py`) |
| 答案管道 | `InterviewAnswerPipeline` | `InterviewAnswerPipeline` (`answer_pipeline.py`) |
| 状态机 | `InterviewFlowStateMachine` | `InterviewStatus` 枚举 (`state.py`) |
| 规则引擎 | `InterviewFollowUpRuleService` | `rule_engine` (`interview_rules.py`) |
| 工作流 | LiteFlow + `*.yml` | LangGraph + `ai_client` (`interview_graph.py`) |
| API 控制器 | `InterviewSessionController` | `interview.py` (`api/v1/`) |
| 数据库模型 | MyBatis Entity | SQLAlchemy Model (`models.py`) |
| 运行态存储 | Redis + MongoDB | Redis + MongoDB (同上) |

## 必守约束

- 面试会话状态和题目流转状态是两套状态，不要混写。
- `questionNumber` 既可能是主问题，也可能是追问题，不能把它当数据库主键看。
- `requestId` 是答题幂等边界，必须稳定，不能让前端每次重试都换值。
- 工作流输出字段必须和 Python 侧解析字段对齐。
- 答题链路不能跳过幂等、题号校验、同题加锁和分数提交补偿。
- 追问是否发生，不只看 AI 输出，还要看规则引擎和最大追问次数。
- 恢复与收尾不是附属能力，而是正式业务契约。

## 状态枚举对照

### 会话状态 (Session Status)

| Java | Python | 说明 |
|------|--------|------|
| `DRAFT` | `"DRAFT"` | 刚创建，尚未上传或提取简历 |
| `READY` | `"READY"` | 题目、方向、简历地址已准备好 |
| `IN_PROGRESS` | `"IN_PROGRESS"` 或 `"ASKING"` | 已经开始取题或答题 |
| `FINISHED` | `"FINISHED"` | 已完成面试并收尾 |
| `ABANDONED` | `"ABANDONED"` | 已废弃或不可继续 |

### 流程状态 (Flow Status)

| Java | Python | 说明 |
|------|--------|------|
| `INIT` | `InterviewStatus.INIT` | 初始化 |
| `ASKING` | `InterviewStatus.ASKING` | 提问中 |
| `EVALUATING` | `InterviewStatus.EVALUATING` | 评估回答 |
| `FOLLOW_UP` | `InterviewStatus.FOLLOW_UP` | 追问中 |
| `COMPLETED` | `InterviewStatus.COMPLETED` | 流程完成 |

## 数据存储对照

| 数据 | Java 存储 | Python 存储 |
|------|-----------|------------|
| 会话主记录 | MongoDB `interview_session` | MySQL `interview_record` 表 |
| 题目数据 | MongoDB `interview_question` | MongoDB `interview_snapshots` |
| 运行态快照 | Redis/MongoDB | MongoDB `interview_snapshots` |
| 幂等缓存 | Redis | Redis (via `redis_client`) |
| 轮次日志 | Redis/MongoDB | MongoDB `interview_snapshots.turn_logs` |
| 问答记录 | MongoDB | MongoDB `interview_snapshots.answers` |

## 评分结构对照

| 字段 | Java | Python | 说明 |
|------|------|--------|------|
| 分数 | `score` (int) | `score` (int) | 0~100 |
| 反馈 | `feedback` (String) | `feedback` (str) | 简洁、可执行的反馈 |
| 缺失点 | `missing_points` (List) | - | Python 版本暂未实现 |
| 需要追问 | `follow_up_needed` (boolean) | `follow_up_needed` (bool) | 规则引擎决策依据 |
| 追问问题 | `follow_up_question` (String) | `follow_up_question` (str) | 当需要追问时应非空 |

## 追问规则对照

| 参数 | Java | Python |
|------|------|--------|
| 最大追问次数 | `default-max-follow-up: 2` | `MAX_FOLLOW_UP = 2` (`answer_pipeline.py`) |
| 低分阈值 | `default-low-score-threshold: 60` | `SCORE_THRESHOLD = 60` (`answer_pipeline.py`) |
| fail-open | `fail-open: true` | `should_generate_follow_up()` 函数逻辑 |
| 规则版本 | `rule-version: v1.0.0` | 嵌入代码逻辑 |

## 参考资料

- `references/object-dictionary.md`
- `references/invariants.md`
- `references/lifecycle.md`
- `references/answer-pipeline.md`
- `references/state-machine.md`
- `references/scoring-followup-rules.md`
- `references/workflow-contracts.md`
- `references/generated-workflow-contracts.md`
- `references/restore-and-finalize.md`
- `references/gotchas.md`
- `references/api-map.md`

## 常见问题排查

| 现象 | Python 第一检查点 | 常见原因 |
|------|-------------------|----------|
| 一直无法答题推进 | `answer_pipeline.py` 前半段 | requestId 不稳定、Redis 锁冲突、旧题号 |
| 评分结果字段缺失 | `ai_client.py` 输出 | prompt 解析失败、JSON 格式问题 |
| 追问次数不对 | `answer_pipeline.py` + `rule_engine` | 规则引擎、最大追问次数或题号状态 |
| 恢复页内容不完整 | `get_snapshot()` + `restore` 接口 | 会话主记录、题目快照、缓存三层回填 |
| 总分回退或不一致 | `interview_service.py` 快照刷新 | 缓存刷新时机、补偿逻辑问题 |
