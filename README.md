<div align="center">

# AIVO - AI 智能面试平台

基于大语言模型的简历分析、模拟面试服务


[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-teal?logo=fastapi)](https://fastapi.tiangolo.com/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-blue?logo=mysql)](https://www.mysql.com/)
[![MongoDB](https://img.shields.io/badge/MongoDB-6.x-green?logo=mongodb)](https://www.mongodb.com/)
[![Redis](https://img.shields.io/badge/Redis-Redisson-red?logo=redis)](https://redis.io/)
[![React](https://img.shields.io/badge/React-19-blue?logo=react)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9-blue?logo=typescript)](https://www.typescriptlang.org/)

</div>

## 项目概览

AIVO 是一个功能完整的 AI 智能面试平台，支持简历分析、AI 出题、模拟面试、实时语音转写、神态分析等功能。项目采用前后端分离架构，本仓库同时包含前端与后端代码。

## 技术架构

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      前端 (React + TypeScript)               │
│              AIVO-Frontend  http://localhost:5173            │
└──────────────────────────┬──────────────────────────────────┘
                           │  REST + SSE + WebSocket
                           ▼
┌─────────────────────────────────────────────────────────────┐
│           后端 - Python FastAPI (Port: 8766)                │
│                  AIVO-Backend                                │
└──────────────────────────┬──────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
    ┌─────────┐      ┌─────────┐      ┌─────────┐
    │  MySQL  │      │ MongoDB │      │  Redis  │
    └─────────┘      └─────────┘      └─────────┘
```

### 技术栈详情

#### 前端 (AIVO-Frontend)

| 技术 | 版本 | 说明 |
|------|------|------|
| React | 19.2 | UI 框架 |
| TypeScript | 5.9 | 开发语言 |
| Vite | 7.3 | 构建工具 |
| Tailwind CSS | 3.4 | 样式框架 |
| Redux Toolkit | 2.11 | 状态管理 |
| React Query | 5.90 | 数据请求缓存 |
| shadcn/ui (Radix) | - | UI 组件库 |
| Framer Motion | 12.35 | 动画库 |
| React Router | 7.13 | 路由管理 |
| React Hook Form | 7.71 | 表单管理 |
| Axios | 1.13 | HTTP 客户端 |
| React PDF | 10.4 | PDF 简历预览 |
| Zod | 4.3 | 数据校验 |

#### 后端 (AIVO-Backend)

| 技术 | 版本 | 说明 |
|------|------|------|
| Python | 3.11+ | 开发语言 |
| FastAPI | 0.110+ | Web 框架 |
| Uvicorn | 0.27+ | ASGI 服务器 |
| SQLAlchemy | 2.0+ | ORM 持久层 |
| Pydantic | 2.0+ | 数据验证 |
| LangGraph / LangChain | latest | Agent 工作流 |
| OpenAI SDK | 1.0+ | AI 模型接入 |
| Redis | 5.0+ | 缓存 / 分布式锁 |
| WebSockets | 12.0+ | 实时通信 |
| OpenAI Whisper | latest | 语音识别 |
| MediaPipe | 0.10+ | 神态分析 |
| PyMuPDF | 1.23+ | PDF 解析 |
| Prometheus | 6.1+ | 监控埋点 |

## 项目结构

```
AIVO/
├── AIVO-Frontend/                # 前端 (React 19 + TypeScript + Vite)
│   ├── docker/                     # Docker 配置
│   ├── public/                     # 静态资源
│   ├── src/
│   │   ├── app/                    # 路由应用
│   │   ├── assets/                 # 图片等资源
│   │   ├── components/             # 通用 UI 组件
│   │   ├── config/                 # 应用配置
│   │   ├── hooks/                  # 自定义 Hooks
│   │   ├── layouts/                # 页面布局
│   │   ├── lib/                    # 工具函数
│   │   ├── pages/                  # 页面组件
│   │   ├── services/               # API 服务层
│   │   ├── store/                  # Redux 状态
│   │   └── types/                  # TypeScript 类型定义
│   ├── Dockerfile
│   ├── vite.config.ts
│   └── package.json
│
├── AIVO-Backend/                 # 后端 (Python 3.11 + FastAPI)
│   ├── app/
│   │   ├── agents/                 # AI Agent 客户端 (ai_client / enhanced_client / streaming)
│   │   ├── api/v1/                 # API 路由 (interview / agent / user / tts / xunfei / websocket)
│   │   ├── application/            # 业务逻辑层 (interview / agent / user)
│   │   ├── core/                   # 核心配置 (config / security / logging / schemas)
│   │   ├── domain/                 # 领域模型
│   │   ├── infrastructure/         # 数据库 / 缓存 / 锁等基础设施
│   │   ├── integrations/           # 第三方集成
│   │   ├── workflow/               # LangGraph 工作流
│   │   └── main.py                 # FastAPI 入口
│   ├── alembic/                    # 数据库迁移
│   ├── models/                     # 本地模型 (whisper 等)
│   ├── scripts/                    # 初始化脚本
│   ├── uploads/                    # 文件上传目录
│   ├── requirements.txt
│   ├── config.yaml
│   └── Dockerfile.dev
│
├── docs/                          # 项目文档与截图
│   └── assets/                    # 截图资源
│
├── skills/                        # AI Agent 技能配置 (业务知识库)
│
├── .github/                       # GitHub 配置
│
└── README.md                      # 本文件
```

## 功能特性

### 1. 模拟面试模块

- **简历驱动出题**：上传 PDF 简历后，AI 智能解析并生成结构化面试题
- **多 Agent 协同**：出题官、提问官、评分官、追问官、表情分析官协同工作
- **LangGraph 工作流**：基于状态机的可视化面试流程编排
- **分布式 Single-flight**：多实例部署下同请求只执行一次 AI 调用
- **长会话状态治理**：支持中断恢复、CAS 并发保护
- **问答回放与雷达图**：多维评分和 AI 综合建议
- **神态分析**：基于摄像头截图 + MediaPipe 表情识别

### 2. AI 对话模块

- **多模型统一接入**：DeepSeek、SiliconFlow、讯飞星火、豆包等模型
- **SSE 流式响应**：基于 `@microsoft/fetch-event-source` 的打字机式流式输出
- **会话管理**：MongoDB 消息持久化 + Redis 上下文缓存

### 3. 智能体（Agent）模块

- **智能体配置管理**：运行时创建、更新、启停配置
- **Agent SSE 对话**：基于 LangChain 的上下文多轮记忆
- **文件上传**：附件上传与管理

### 4. 语音媒体模块

- **实时语音转写（ASR）**：WebSocket + 讯飞实时识别 + Whisper 本地回退
- **长文本语音合成（TTS）**：异步合成任务
- **WebSocket 通信**：心跳保活、鉴权校验

## 快速开始

### 前置要求

- Node.js 20+
- npm 10+
- Python 3.11+
- MySQL 8.0+
- MongoDB 6.x+
- Redis 7.x+

### 1. 启动数据库服务

```bash
docker-compose up -d mysql mongodb redis
```

### 2. 启动前端

```bash
cd AIVO-Frontend
npm install
npm run dev
```

访问 http://localhost:5173

### 3. 启动后端 (Python)

```bash
cd AIVO-Backend

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入必要的 API Key

# 启动服务
python -m uvicorn app.main:app --host 0.0.0.0 --port 8766 --reload
```

## 环境变量配置

### Python 后端 (.env)

```env
DB_PASSWORD=your_db_password
REDIS_PASSWORD=your_redis_password
JWT_SECRET=your_jwt_secret_key_min_32_chars_here
SILICONFLOW_API_KEY=your_siliconflow_api_key
DEEPSEEK_API_KEY=your_deepseek_api_key
XUNFEI_APP_ID=your_xunfei_app_id
XUNFEI_API_KEY=your_xunfei_api_key
XUNFEI_API_SECRET=your_xunfei_api_secret
```

### 前端 (.env)

```env
VITE_API_BASE_URL=http://localhost:8766
```

## API 文档

启动服务后访问：

- 后端 Swagger UI：http://localhost:8766/docs
- ReDoc：http://localhost:8766/redoc

### 核心 API

| 模块 | 路径 | 说明 |
|------|------|------|
| 面试 | `/api/v1/interview/sessions` | 面试会话管理 |
| 面试 | `/api/v1/interview/sessions/{id}/questions` | 生成面试问题 |
| 面试 | `/api/v1/interview/sessions/{id}/answer` | 提交回答 |
| Agent | `/api/v1/agents/sessions/{id}/chat` | Agent 对话 |
| 用户 | `/api/v1/users/login` | 用户登录 |
| TTS | `/api/v1/tts/*` | 语音合成 |
| Xunfei | `/api/v1/xunfei/*` | 讯飞语音接口 |

## Docker 部署

```bash
# 后端构建
cd AIVO-Backend && docker build -f Dockerfile.dev -t aivo-backend .

# 前端构建
cd AIVO-Frontend && docker build -t aivo-frontend .

# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

## 简历写法（面试加分项）

1. **AI 面试答题链路设计**：基于 LangGraph 串联评分 / 追问 Agent 协同工作，状态机 + 规则链实现追问裁决；设计分布式锁 + 幂等防重 + 异步补偿机制。

2. **长会话状态治理**：基于 MongoDB Snapshot + Redis 懒加载构建可恢复运行态体系，热冷分层 + CAS 并发保护。

3. **分布式 Single-flight 框架**：Redis Lua + 状态机 + Fencing Token 实现多实例去重、结果回放、失败分类和超时接管。

4. **实时 ASR 链路优化**：WebSocket + 讯飞 AST 实现分段增量去重，NIO 异步缓冲 + TreeMap 有序重建。

5. **Skill 业务知识体系**：模块化业务知识单元，解决复杂业务中的知识断层问题。

6. **多模型统一接入**：以 OpenAI 兼容协议屏蔽 DeepSeek / SiliconFlow / 讯飞等模型差异，运行时按策略路由。

7. **前端流式体验**：`@microsoft/fetch-event-source` + React 19 实现可中断重连的 SSE 流式渲染、Markdown 实时高亮。

## 子项目 README

- [前端文档](AIVO-Frontend/README.md)
- [后端文档](AIVO-Backend/README.md)

---

**AIVO，让 AI 助力每一次面试体验**
