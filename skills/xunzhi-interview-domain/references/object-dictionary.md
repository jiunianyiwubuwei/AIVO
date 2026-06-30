# 面试域对象词典

把面试域里所有"会被误解的名词"统一成同一种业务语言，并明确每个对象的真相源、写入路径、读取路径和不能替代什么。

## 1. 主记录层

### Python 版本

| 对象 | 真相源 | 写入时机 | 读取时机 | 不能替代什么 |
|------|--------|----------|----------|--------------|
| `InterviewRecord` | MySQL `interview_record` | 创建会话、状态变更、结束会话 | 创建页、恢复页、答题前校验 | 题目流转状态 |
| `InterviewSnapshot` | MongoDB `interview_snapshots` | 提题成功、恢复回填 | 提题、恢复、当前题回填 | 主会话状态 |

### Java 版本（参考）

| 对象 | 真相源 | 写入时机 | 读取时机 | 不能替代什么 |
|------|--------|----------|----------|--------------|
| `InterviewSession` | MongoDB | 创建会话、状态变更、结束会话 | 创建页、恢复页、答题前校验 | 题目流转状态 |
| `InterviewQuestion` | MongoDB | 提题成功、恢复回填 | 提题、恢复、当前题回填 | 主会话状态 |
| `InterviewRecordDO` | MySQL | finalize 收尾 | 结果页、历史页、恢复兜底 | 实时运行态 |

## 2. 运行态层

### Python 版本

| 对象 | 真相源 | 作用 | 典型写入者 | 典型读取者 |
|------|--------|------|------------|------------|
| `flow_state` | MongoDB 快照 | 当前题号、追问次数、状态游标 | 答题管道、状态机 | 答题管道、恢复链路 |
| `turn_logs` | MongoDB 快照 | 单轮答题回放、补偿、软回放 | 答题管道 | 恢复、排障、回放 |
| `answers` | MongoDB 快照 | 问答记录、评分结果 | 答题成功后的收口 | 报告展示、恢复 |

### Java 版本（参考）

| 对象 | 真相源 | 作用 | 典型写入者 | 典型读取者 |
|------|--------|------|------------|------------|
| `InterviewFlowState` | Redis | 当前题号、追问次数、状态游标 | 答题链路、状态机 | 答题链路、恢复链路 |
| `InterviewTurnLog` | Redis / 快照 / 归档 | 单轮答题回放、补偿、软回放 | 答题流水线 | 恢复、排障、回放 |
| `InterviewSessionRuntimeHotSnapshot` | MongoDB | 高频恢复、幂等回放、最近轮次 | 恢复服务、答题后刷新 | 恢复页、排障页 |
| `InterviewSessionRuntimeColdSnapshot` | MongoDB | 题目、建议、简历上下文、神态结果 | 提题链路、恢复链路 | 恢复页、结果页 |

## 3. 契约层

### Python 版本

| 对象 | 角色 | 核心字段 | 说明 |
|------|------|----------|------|
| `AnswerRequest` | 输入契约 | `question_number`、`answer_content`、`request_id` | 幂等、提问、作答入口 |
| `InterviewAnswerRespDTO` | 输出契约 | `score`、`total_score`、`next_question`、`finished` | 一次答题同时承载评分和下一步 |
| `Question` | 问题对象 | `id`、`number`、`content`、`category` | 面试题目 |
| `InterviewState` | 流程状态 | `status`、`current_question_index`、`follow_up_count` | LangGraph 状态 |

### Java 版本（参考）

| 对象 | 角色 | 核心字段 | 说明 |
|------|------|----------|------|
| `InterviewAnswerReqDTO` | 输入契约 | `questionNumber`、`answerContent`、`requestId` | 幂等、提问、作答入口 |
| `InterviewAnswerRespDTO` | 输出契约 | `score`、`totalScore`、`nextQuestion`、`finished` | 一次答题同时承载评分和下一步 |
| `InterviewQuestionRespDTO` | 输出契约 | `questions`、`suggestions`、`resumeScore` | 提题结果和简历评分合并输出 |
| `InterviewSessionRestoreRespDTO` | 输出契约 | `canResume`、`resumeFileUrl`、`suggestions` | 恢复页最小可渲染对象 |
| `RadarChartDTO` | 输出契约 | 五维画像 | 恢复后的综合展示 |
| `DemeanorScoreDTO` | 输入/输出契约 | 慌乱度、严肃度、表情处理、综合分 | 神态分析细粒度结果 |

## 4. 题号语义

### 题号格式

| 名词 | 语义 | 规则 | 示例 |
|------|------|------|------|
| `question_number` | 业务题号 | 可以是主问题，也可以是追问题 | `"1"`, `"1-F1"`, `"2-F2"` |
| `next_question_number` | 下一步题号 | 由状态机和追问规则共同决定 | `"2"`, `"1-F2"` |
| `follow_up_count` | 当前追问序号 | 只属于当前主问题分支 | `0`, `1`, `2` |
| `max_follow_up` | 最大追问次数 | 约束追问是否还能继续 | `2` |

### 题号工具函数 (Python)

```python
def normalize_question_number(q: str) -> str      # 归一化
def is_follow_up_question(q: str) -> bool        # 判断追问
def extract_main_question_number(q: str) -> str  # 提取主问题号
def extract_follow_up_count(q: str) -> int       # 提取追问次数
def build_follow_up_question_number(main, n) -> str  # 构建追问
```

## 5. 真相源判定规则

- 要判断"能不能继续答题"，先看 `InterviewRecord.interview_status`，再看快照的 `flow_state.status`。
- 要判断"当前题是什么"，先看快照的 `flow_state.current_question_number`，再看 `questions` 列表。
- 要判断"总分是多少"，先看快照的 `total_score`，再看 MySQL 记录。
- 要判断"题目/建议/简历评分是什么"，先看快照，再看 MySQL 记录。
- 要判断"当前是否能写"，先看 `interview_status` 是否为 `ASKING`。

## 6. 生命周期

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 创建 InterviewRecord → 初始化 InterviewSnapshot                  │
│ 2. 提题后写入 questions，同时落下 flow_state                        │
│ 3. 答题管道不断更新 flow_state 和 answers                          │
│ 4. 恢复时先拿主记录，再回补快照                                    │
│ 5. 结束时把最终结果写入快照，并更新 interview_status = FINISHED     │
└─────────────────────────────────────────────────────────────────────┘
```

## 7. 常见误解

- `InterviewRecord.interview_status` 不是题目流转状态。
- `question_number` 不是数据库主键，它是业务题号语义。
- `total_score` 不是任何一层都能随便改的数字，只有答题完成路径能稳定写它。
- 追问是主问题的附属分支，不是独立会话。
- MongoDB 快照中的 `ObjectId` 需要用 `_serialize_snapshot()` 转字符串才能返回前端。
