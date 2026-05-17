# MicroBubble Agent - 项目上下文

## 项目简介

"小气" - 微纳米气泡课题组智能Agent系统，约20人研究实验室的AI助手。

- 后端: Python 3.11 + FastAPI + SQLAlchemy + PostgreSQL + Redis + Celery
- 前端: Vue 3 + Vite + Element Plus
- AI: Claude API (Sonnet) + faster-whisper + pgvector
- 部署: 云服务器 (Nginx + FRP 服务端) + 本地电脑 (Docker 7 services + GPU Whisper)，通过 FRP 隧道连接

## 当前开发阶段

项目处于**部署进行中**阶段。Phase 1-4 代码已完成，Phase 5 部分完成。部署采用云服务器（Nginx+FRP）+ 本地电脑（Docker 全服务+GPU）的穿透架构。详见 `ROADMAP.md`。

## 关键架构决策

- Agent 工具调用通过 `app/agent/core.py` 的 `_execute_tool` 方法路由到 service 层（10 个工具已全部接入）
- `chat()` 和 `chat_stream()` 接收 `db: AsyncSession` 参数，由 API 路由通过 `Depends(get_db)` 传入
- 使用 `AsyncAnthropic` 客户端，不阻塞事件循环
- 认证使用 JWT，`app/core/security.py` 已实现，31 个端点全部接入 `get_current_user`
- 会话存储已迁移到 Redis（`RedisSessionStore`，24 小时 TTL）
- 知识库使用 pgvector 做向量搜索（扩展已在 main.py 启动时自动安装，已接入 text2vec-base-chinese 真实语义搜索）
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
- 前端 ProjectView 调用了 DELETE /projects/{id}（已实现），MeetingView 的 PUT/DELETE 端点已实现
- 无用依赖已清理（langchain, chromadb, sentence-transformers, pyannote 已移除，minio 已恢复用于文件上传）
- 登录页硬编码账号已移除，改为"请联系管理员获取账号密码"
- Agent 的 `generate_project_plan` 工具会调用 Claude API 两次（生成计划 + 对话），注意 token 消耗
- 企业微信和腾讯会议代码完成但未部署，存在已知 bug 和配置缺失（详见 ROADMAP.md）
- 部署架构：云服务器跑 Nginx+FRP，本地电脑跑全部 Docker 服务，FRP 穿透 8000 端口
- Claude API 使用代理地址（`CLAUDE_BASE_URL`），支持第三方 API 中转
- 生产部署待完成：SSL 证书申请、企业微信 bug 修复、腾讯会议凭据配置（详见 ROADMAP.md）
