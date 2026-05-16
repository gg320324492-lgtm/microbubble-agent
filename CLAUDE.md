# MicroBubble Agent - 项目上下文

## 项目简介

"小气" - 微纳米气泡课题组智能Agent系统，约20人研究实验室的AI助手。

- 后端: Python 3.11 + FastAPI + SQLAlchemy + PostgreSQL + Redis + Celery
- 前端: Vue 3 + Vite + Element Plus
- AI: Claude API (Sonnet) + faster-whisper + pgvector
- 部署: Docker Compose (8 services)

## 当前开发阶段

项目处于**Phase 1 完成阶段**，核心 Agent 工具调用链路已打通。详见 `ROADMAP.md`。

## 关键架构决策

- Agent 工具调用通过 `app/agent/core.py` 的 `_execute_tool` 方法路由到 service 层（10 个工具已全部接入）
- `chat()` 和 `chat_stream()` 接收 `db: AsyncSession` 参数，由 API 路由通过 `Depends(get_db)` 传入
- 使用 `AsyncAnthropic` 客户端，不阻塞事件循环
- 认证使用 JWT，`app/core/security.py` 已实现但大部分路由未接入
- 会话存储当前为内存 dict（需迁移到 Redis）
- 知识库使用 pgvector 做向量搜索（扩展已在 main.py 启动时自动安装，语义搜索暂用 SQL LIKE）
- 语音识别使用 faster-whisper，TTS 使用 Edge-TTS

## 服务层结构

| 文件 | 职责 |
|------|------|
| `app/services/task_service.py` | 任务 CRUD + 统计 + 自动提醒 |
| `app/services/member_service.py` | 成员 CRUD + 按姓名查询 |
| `app/services/meeting_service.py` | 会议 CRUD + 参与者管理 |
| `app/services/project_service.py` | 项目+里程碑 CRUD |
| `app/services/knowledge_service.py` | 知识库 CRUD + 语义搜索 |
| `app/services/reminder_service.py` | 提醒服务 + Celery task |

## 开发注意事项

- 数据库模型使用 PostgreSQL 特有类型（ARRAY, Vector），不可直接切换到 SQLite
- 前端 ProjectView 调用了 DELETE /projects/{id}（已实现），MeetingView 的 PUT 端点未实现
- `requirements.txt` 中有多个未使用的依赖（langchain, chromadb, sentence-transformers, minio, pyannote）
- 登录页显示了默认账号密码，需在生产环境移除
- Agent 的 `generate_project_plan` 工具会调用 Claude API 两次（生成计划 + 对话），注意 token 消耗
