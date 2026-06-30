# 恢复与收尾

## Python 实现

Python 版本使用 MongoDB 存储运行态快照，而非 Java 版本的 Redis + MongoDB 混合存储。

### 存储结构

文件：`app/infrastructure/cache/mongodb_client.py`

| 数据类型 | 存储位置 | 说明 |
|----------|----------|------|
| 运行态快照 | MongoDB `interview_snapshots` | 主要存储 |
| 幂等缓存 | Redis | 30s 过期 |
| 成功响应缓存 | Redis | 1h 过期 |
| 会话主记录 | MySQL `interview_record` | 持久化 |

## 恢复服务

### 恢复入口

`app/api/v1/interview.py` 中的 `/restore` 接口：

```python
@router.get("/sessions/{session_id}/restore")
async def restore_interview_session(
    session_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
```

### 恢复流程

```
请求 /restore
    ↓
1. 校验会话归属 (user_id)
    ↓
2. 获取 MySQL 主记录 (interview_record)
    ↓
3. 获取 MongoDB 快照 (interview_snapshots)
    ↓
4. 序列化 ObjectId (_serialize_snapshot)
    ↓
5. 组装恢复数据
    ↓
返回前端
```

### 恢复数据来源

| 字段 | 来源 | 说明 |
|------|------|------|
| `sessionId` | MySQL | 会话ID |
| `status` | MySQL `interview_status` | 会话状态 |
| `questions` | MongoDB 快照 | 题目列表 |
| `flow_state` | MongoDB 快照 | 流程状态 |
| `answers` | MongoDB 快照 | 问答记录 |
| `total_score` | MongoDB 快照 | 总分 |
| `resume_score` | MySQL `resume_score` | 简历分 |
| `resumeFileUrl` | 构造 | 简历预览URL |

## 快照服务

### 快照数据结构

文件：`app/application/interview/interview_service.py`

```python
# 初始化快照
snapshot = {
    "session_id": session_id,
    "user_id": user_id,
    "status": "INIT",
    "current_question_number": "0",
    "current_index": 0,
    "total_questions": 5,
    "follow_up_count": 0,
    "max_follow_up": 2,
    "total_score": 0,
    "created_at": "...",
    "updated_at": "...",
}
```

### 快照更新时机

| 时机 | 更新内容 | 方法 |
|------|----------|------|
| 创建会话 | 初始化快照 | `_init_snapshot()` |
| 提题成功后 | 保存题目、flow_state | `save_snapshot()` |
| 答题成功后 | 保存轮次日志、刷新分数 | `save_turn_log()` |
| 追问生成 | 保存追问、跟新 follow_up_count | `save_follow_up_question()` |
| 面试结束 | 标记完成、保存最终结果 | `finish_interview()` |

## 收尾语义

### 结束面试 (`finish_interview`)

```python
@router.put("/sessions/{session_id}/finish")
async def finish_interview(...):
    # 1. 计算最终统计数据
    total_score = sum(a.get("score", 0) for a in answers)
    interview_score = total_score

    # 2. 生成面试总结
    ai_summary = await ai_client.generate_summary(questions, answers)

    # 3. 更新快照
    await service.update_snapshot(session_id, {
        "status": "FINISHED",
        "total_score": total_score,
        "interview_score": interview_score,
        "interview_suggestions": suggestions,
        "ai_summary": ai_summary,
    })

    # 4. 更新会话状态
    await service.update_status(session_id, "FINISHED")

    # 5. 集成仪态评估（如果启用）
    # 调用 comprehensive_scorer.evaluate_comprehensive()
```

### 收尾与恢复的关系

- `finish_interview` 最终会更新快照中的 `status` 为 `FINISHED`
- 查询总分、建议、雷达图时，代码优先读快照，再回退 MySQL 记录
- 恢复接口返回的快照数据包含完整的问答历史

## 读写模式

Python 版本简化了读写模式的区分，主要通过快照中的 `status` 字段判断：

| 状态 | 可恢复 | 可写 | 说明 |
|------|--------|------|------|
| `DRAFT` | 否 | 否 | 题目材料不完整 |
| `READY` | 是 | 是 | 可以开始答题 |
| `ASKING` | 是 | 是 | 面试进行中 |
| `FINISHED` | 是 | 否 | 面试已结束 |

## Java 版本（参考）

Java 版本使用更复杂的分层恢复：

### 恢复范围

- `FLOW_ONLY` - 只恢复题目材料和 flow
- `SCORE_ONLY` - 只恢复总分
- `PLAYBACK_ONLY` - 只恢复轮次回放
- `MATERIAL_ONLY` - 恢复题目、建议、简历材料
- `HOT_RUNTIME` - 恢复答题时所需的热态
- `FULL_RUNTIME` - 恢复完整运行态

### 读写模式

- `READ_ONLY` - 用于只读查询
- `READ_WRITE_REQUIRED` - 用于答题推进

### Java 关键类

- `InterviewSessionRuntimeRehydrateService` - 恢复服务
- `InterviewSessionRuntimeSnapshotService` - 快照服务
