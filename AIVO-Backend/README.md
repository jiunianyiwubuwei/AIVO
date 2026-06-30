# AIVO Backend - Python FastAPI

基于 Python FastAPI 构建的 AI 智能面试后端服务，支持简历分析、模拟面试、实时语音转写等功能。

## 技术栈

| 技术 | 说明 |
|------|------|
| Python | 3.11+ |
| FastAPI | Web 框架 |
| SQLAlchemy | ORM 持久层 |
| MySQL | 关系型数据库 |
| MongoDB | 文档数据库，存储会话消息 |
| Redis | 分布式锁、缓存 |
| OpenAI API | AI 模型接入 |
| MediaPipe | 仪态分析 |
| Whisper | 语音转文字 |

## 项目结构

```
AIVO-Backend/
├── app/
│   ├── agents/              # AI Agent 核心模块
│   │   ├── ai_client.py        # AI 客户端（兼容旧接口）
│   │   ├── enhanced_client.py   # 增强版 AI 客户端
│   │   ├── prompts.py          # Prompt 配置
│   │   └── streaming.py        # 流式响应处理
│   ├── api/
│   │   └── v1/             # API 路由
│   │       ├── interview.py     # 面试 API
│   │       ├── agent.py         # Agent API
│   │       ├── user.py          # 用户 API
│   │       └── health.py        # 健康检查
│   ├── application/
│   │   ├── interview/       # 面试业务逻辑
│   │   │   ├── interview_service.py
│   │   │   ├── answer_pipeline.py
│   │   │   └── workflow_service.py
│   │   └── agent/
│   │       └── agent_service.py
│   ├── core/
│   │   ├── config.py           # 配置管理
│   │   ├── security.py         # 安全认证
│   │   └── schemas/            # 数据模型
│   ├── infrastructure/
│   │   ├── cache/              # 缓存（Redis、MongoDB）
│   │   └── database/           # 数据库连接
│   └── workflow/               # 工作流引擎
├── alembic/                    # 数据库迁移
├── uploads/                    # 文件上传目录
└── tests/                      # 测试文件
```

## 快速开始

### 1. 环境要求

- Python 3.11+
- MySQL 8.0+
- MongoDB 6.x+
- Redis 7.x+

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

复制 `.env.example` 为 `.env` 并配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
DB_PASSWORD=your_db_password
JWT_SECRET=your_jwt_secret_key_min_32_chars_here
SILICONFLOW_API_KEY=your_siliconflow_api_key
```

### 4. 启动服务

```bash
# 开发模式（自动重载）
python -m uvicorn app.main:app --host 0.0.0.0 --port 8766 --reload

# 生产模式
python -m uvicorn app.main:app --host 0.0.0.0 --port 8766 --workers 4
```

服务启动后访问：
- API 文档：http://localhost:8766/docs
- 健康检查：http://localhost:8766/health

## API 文档

### 面试 API (`/xunzhi/v1/interview`)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /sessions | 创建面试会话 |
| GET | /sessions | 获取会话列表 |
| GET | /sessions/{id} | 获取会话详情 |
| POST | /sessions/{id}/interview-questions | 生成面试问题 |
| POST | /sessions/{id}/interview/answer | 提交回答 |
| GET | /sessions/{id}/current-question | 获取当前问题 |
| PUT | /sessions/{id}/finish | 结束面试 |
| GET | /records | 获取面试记录列表 |

### Agent API (`/xunzhi/v1/agents`)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /sessions | 创建 Agent 会话 |
| POST | /sessions/{id}/chat | Agent 对话（SSE 流式） |
| GET | /sessions/{id}/messages | 获取会话消息 |
| POST | /files/upload | 文件上传 |

### 用户 API (`/xunzhi/v1/users`)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /register | 用户注册 |
| POST | /login | 用户登录 |
| POST | /logout | 用户登出 |

## Docker 部署

```bash
# 构建镜像
docker build -t aivo-backend .

# 运行容器
docker-compose up -d
```

## 测试

```bash
# 运行所有测试
pytest

# 运行指定测试
pytest tests/test_interview.py -v
```

## 环境变量说明

| 变量 | 说明 | 必填 |
|------|------|------|
| DB_PASSWORD | MySQL 密码 | 是 |
| REDIS_PASSWORD | Redis 密码 | 否 |
| JWT_SECRET | JWT 密钥（至少 32 字符） | 是 |
| SILICONFLOW_API_KEY | SiliconFlow API Key | 是 |
| DEEPSEEK_API_KEY | DeepSeek API Key | 否 |
| XUNFEI_APP_ID | 讯飞应用 ID | 否 |
| XUNFEI_API_KEY | 讯飞 API Key | 否 |
| HTTPS_PROXY | HTTPS 代理 | 否 |

## License

MIT License
