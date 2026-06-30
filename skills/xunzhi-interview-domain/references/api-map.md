# 面试 API 映射

## 会话与历史

| 功能 | Java API | Python API |
|------|----------|------------|
| 创建会话 | `POST /api/xunzhi/v1/interview/sessions` | `POST /xunzhi/v1/interview/sessions` |
| 查询会话列表 | `GET /api/xunzhi/v1/interview/conversations` | `GET /xunzhi/v1/interview/sessions` 或 `/conversations` |
| 结束会话 | `PUT /api/xunzhi/v1/interview/sessions/{sessionId}/finish` | `PUT /xunzhi/v1/interview/sessions/{session_id}/finish` |

## 题目与答题

| 功能 | Java API | Python API |
|------|----------|------------|
| 上传简历并提题 | `POST /api/xunzhi/v1/interview/sessions/{sessionId}/interview-questions` | `POST /xunzhi/v1/interview/sessions/{session_id}/interview-questions` |
| 表单方式答题 | `POST /api/xunzhi/v1/interview/sessions/{sessionId}/interview/answer` | `POST /xunzhi/v1/interview/sessions/{session_id}/interview/answer` |
| JSON 方式答题 | `POST /api/xunzhi/v1/interview/sessions/{sessionId}/interview/answer-json` | `POST /xunzhi/v1/interview/sessions/{session_id}/interview/answer-json` |
| 取下一题 | `GET /api/xunzhi/v1/interview/sessions/{sessionId}/next-question` | `GET /xunzhi/v1/interview/sessions/{session_id}/next-question` |
| 取当前题 | `GET /api/xunzhi/v1/interview/sessions/{sessionId}/current-question` | `GET /xunzhi/v1/interview/sessions/{session_id}/current-question` |

## 恢复与结果

| 功能 | Java API | Python API |
|------|----------|------------|
| 恢复页总装 | `GET /api/xunzhi/v1/interview/sessions/{sessionId}/restore` | `GET /xunzhi/v1/interview/sessions/{session_id}/restore` |
| 查题目集合 | `GET /api/xunzhi/v1/interview/sessions/{sessionId}/interview/questions` | `GET /xunzhi/v1/interview/sessions/{session_id}/snapshot` |
| 查总分 | `GET /api/xunzhi/v1/interview/sessions/{sessionId}/interview/score` | 快照中 `total_score` 字段 |
| 查建议 | `GET /api/xunzhi/v1/interview/sessions/{sessionId}/interview/suggestions` | 快照中 `interview_suggestions` 字段 |
| 查简历分 | `GET /api/xunzhi/v1/interview/sessions/{sessionId}/resume/score` | `interview.resume_score` |
| 查雷达图 | `GET /api/xunzhi/v1/interview/sessions/{sessionId}/radar-chart` | `GET /xunzhi/v1/interview/sessions/{session_id}/radar-chart` |
| 预览简历 PDF | `GET /api/xunzhi/v1/interview/sessions/{sessionId}/resume/preview` | `GET /xunzhi/v1/interview/sessions/{session_id}/resume/preview` |
| 神态分析 | `POST /api/xunzhi/v1/interview/sessions/{sessionId}/demeanor-evaluation` | `POST /xunzhi/v1/interview/sessions/{session_id}/demeanor/evaluate` |

## Python 特有 API

| 功能 | Python API | 说明 |
|------|------------|------|
| 语音转文字 | `POST /xunzhi/v1/interview/sessions/{session_id}/voice/transcribe` | 使用 Whisper 进行语音识别 |
| 单帧仪态分析 | `POST /xunzhi/v1/interview/sessions/{session_id}/demeanor/analyze-frame` | MediaPipe 单帧分析 |
| 仪态流初始化 | `POST /xunzhi/v1/interview/sessions/{session_id}/demeanor/stream/init` | 初始化仪态跟踪器 |
| 仪态流帧上传 | `POST /xunzhi/v1/interview/sessions/{session_id}/demeanor/stream/frame` | 批量上传视频帧 |
| 仪态流音频上传 | `POST /xunzhi/v1/interview/sessions/{session_id}/demeanor/stream/audio` | 上传音频片段 |
| 仪态最终评估 | `POST /xunzhi/v1/interview/sessions/{session_id}/demeanor/evaluate-final` | 汇总仪态数据，生成综合评分 |
| 仪态评估报告 | `GET /xunzhi/v1/interview/sessions/{session_id}/demeanor/report` | 获取完整仪态报告 |
| Whisper 分析 | `POST /xunzhi/v1/interview/sessions/{session_id}/demeanor/analyze-whisper` | 分析 Whisper 语音识别结果 |
| 面试记录列表 | `GET /xunzhi/v1/interview/records` | 分页查询面试记录 |
| 获取单条记录 | `GET /xunzhi/v1/interview/record/{session_id}` | 获取面试报告详情 |

## 入口后的第一站

### Python 架构

1. **控制器入口**：`app/api/v1/interview.py` 中的路由函数。
2. **服务层**：`app/application/interview/interview_service.py` 提供核心业务逻辑。
3. **答案管道**：`app/application/interview/answer_pipeline.py` 处理答题核心流程。
4. **规则引擎**：`app/workflow/rules/interview_rules.py` 决定追问策略。
5. **工作流**：`app/workflow/interview_graph.py` 使用 LangGraph 编排。
6. **AI 调用**：`app/agents/ai_client.py` 统一封装多提供商 AI 调用。

### Java 架构（参考）

1. 控制器入口统一落到 `InterviewSessionFacade`。
2. 真正的核心编排通常在 `InterviewAnswerPipeline`、状态机、恢复服务和 workflow 服务里。

## 请求/响应 DTO 对照

### 答题请求

| 字段 | Java | Python |
|------|------|--------|
| 会话ID | path `sessionId` | path `session_id` |
| 题号 | `questionNumber` | `questionNumber` 或 `question_number` |
| 回答内容 | `answerContent` | `answerContent` 或 `answer_content` |
| 请求ID | `requestId` (可选) | `requestId` (可选) |

### 答题响应

| 字段 | Java | Python |
|------|------|--------|
| 是否成功 | `success` | `isSuccess` |
| 题号 | `questionNumber` | `questionNumber` |
| 分数 | `score` | `score` |
| 总分 | `totalScore` | `totalScore` |
| 反馈 | `feedback` | `feedback` |
| 下一题 | `nextQuestion` | `nextQuestion` |
| 是否追问 | `followUp` | `isFollowUp` |
| 是否结束 | `finished` | `finished` |
