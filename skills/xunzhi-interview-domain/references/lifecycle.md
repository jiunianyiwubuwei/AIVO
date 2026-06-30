# 面试生命周期

## 会话状态

### Python 版本

| 状态 | 说明 | 可恢复 | 可写 |
|------|------|--------|------|
| `DRAFT` | 刚创建，尚未上传或提取简历 | 否 | 否 |
| `READY` | 题目、方向、简历地址已准备好 | 是 | 是 |
| `ASKING` | 已经开始取题或答题 | 是 | 是 |
| `FINISHED` | 已完成面试并收尾 | 是 | 否 |
| `ABANDONED` | 已废弃或不可继续 | 否 | 否 |

### Java 版本（参考）

| 状态 | 说明 | 可恢复 | 可写 |
|------|------|--------|------|
| `DRAFT` | 刚创建，尚未上传或提取简历 | 否 | 否 |
| `RESUME_UPLOADING` | 正在上传并提取题目 | 否 | 否 |
| `READY` | 题目、方向、简历地址已准备好 | 是 | 是 |
| `IN_PROGRESS` | 已经开始取题或答题 | 是 | 是 |
| `FINISHED` | 已完成面试并收尾 | 是 | 否 |
| `ABANDONED` | 已废弃或不可继续 | 否 | 否 |

## 核心推进链路

### Python 版本

```
┌──────────────────────────────────────────────────────────────────────┐
│ 1. create_session() → 创建 InterviewRecord，状态 = DRAFT              │
│ 2. 上传简历 + generate_interview_questions() → 状态 = ASKING         │
│ 3. 答题 → answer_json() → InterviewAnswerPipeline.execute()          │
│ 4. finish_interview() → 状态 = FINISHED                             │
└──────────────────────────────────────────────────────────────────────┘
```

| 方法 | 作用 | 状态变化 |
|------|------|----------|
| `create_session()` | 创建会话 | `DRAFT` |
| `generate_interview_questions()` | 上传简历，生成问题 | `DRAFT` → `ASKING` |
| `submit_answer()` / `answer_json()` | 提交答案 | 保持在 `ASKING` |
| `finish_interview()` | 结束面试 | `ASKING` → `FINISHED` |

### Java 版本（参考）

| 方法 | 作用 | 状态变化 |
|------|------|----------|
| `createSession()` | 创建会话 | `DRAFT` |
| `extractInterviewQuestions()` | 先标 `RESUME_UPLOADING`，成功后标 `READY` | `DRAFT` → `RESUME_UPLOADING` → `READY` |
| `getCurrentQuestion()` / `getNextQuestion()` / `answerInterviewQuestion()` | 都会先校验会话归属和是否可继续；首次进入会把 `READY` 升到 `IN_PROGRESS` | `READY` → `IN_PROGRESS` |
| `finishSession()` / `endConversation()` | 统一走 finalize 收口 | `IN_PROGRESS` → `FINISHED` |

## canResume 语义

### Python 版本

```python
def can_resume(interview_status: str) -> bool:
    return interview_status in ["READY", "ASKING"]
```

| 状态 | canResume | 说明 |
|------|-----------|------|
| `DRAFT` | `False` | 题目材料还不完整 |
| `READY` | `True` | 可以开始答题 |
| `ASKING` | `True` | 面试进行中 |
| `FINISHED` | `False` | 面试已结束 |
| `ABANDONED` | `False` | 已废弃 |

### Java 版本（参考）

| 状态 | canResume | 说明 |
|------|-----------|------|
| `DRAFT` | `False` | 题目材料还不完整 |
| `READY` | `True` | 可以开始答题 |
| `IN_PROGRESS` | `True` | 面试进行中 |
| `FINISHED` | `False` | 面试已结束 |
| `ABANDONED` | `False` | 已废弃 |

## 生命周期与材料回填

### Python 版本

1. **提题成功后**：
   - `InterviewService.update_status()` 会把 `resume_score` 和 `question_count` 回填到 MySQL
   - `save_snapshot()` 会把题目列表和 `flow_state` 保存到 MongoDB

2. **恢复接口**：
   - 优先读取 MySQL 主记录获取 `interview_status`、`resume_score`
   - 再用 MongoDB 快照补齐 `questions`、`flow_state`、`answers`

3. **恢复页渲染**：
   - 建议前端把恢复接口看成"恢复页渲染的总装接口"
   - 不仅查状态，还会触发运行态回填

### Java 版本（参考）

1. **提题成功后**：
   - `InterviewSessionFacade` 会把 `resumeFileUrl` 和 `interviewType` 回填到会话主记录

2. **恢复接口**：
   - 优先读会话主字段，再用 `InterviewQuestion` 补齐方向、简历、简历分

## 状态流转图

### Python 版本

```
                    ┌─────────┐
                    │  DRAFT  │
                    └────┬────┘
                         │ 上传简历
                         ▼
                    ┌─────────┐
                    │  ASKING │
                    └────┬────┘
                         │ 答题完成
                         ▼
                    ┌──────────┐
              ┌─────│ FINISHED  │←──┐
              │     └──────────┘   │
              │                    │ finish
              │     ┌─────────┐   │
              └────►│ ABANDONED│───┘
                    └─────────┘
```

### Java 版本（参考）

```
                    ┌─────────┐
                    │  DRAFT  │
                    └────┬────┘
                         │ 上传简历
                         ▼
            ┌────────────┴────────────┐
            │   RESUME_UPLOADING      │
            └────────────┬────────────┘
                         │ 提题成功
                         ▼
                    ┌─────────┐
                    │  READY  │
                    └────┬────┘
                         │ 开始答题
                         ▼
                    ┌────────────┐
                    │IN_PROGRESS │
                    └─────┬──────┘
                          │
           ┌──────────────┴──────────────┐
           ▼                             ▼
     ┌──────────┐                  ┌──────────┐
     │ FINISHED │                  │ ABANDONED │
     └──────────┘                  └──────────┘
```
