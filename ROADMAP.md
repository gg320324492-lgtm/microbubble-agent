# MicroBubble Agent - 完善路线图

> 最后更新: 2026-05-16

## 第一阶段：让系统真正能用（关键）

- [x] **接入 Agent 工具执行** -- `_execute_tool` 已连接真实 service 层，10 个工具全部路由到对应 Service
- [x] **修复 session_id bug** -- `_process_response` 已接收 `session_id` 参数，不再硬编码 `"default"`
- [x] **创建 Celery 模块** -- `app/core/celery.py` 已创建，celery-worker/celery-beat 可正常启动
- [x] **配置 pgvector** -- `main.py` 启动时执行 `CREATE EXTENSION IF NOT EXISTS vector`
- [x] **chat_stream 支持工具调用** -- 已传入 `tools=self.tools`，流式对话可触发工具

## 第二阶段：补全缺失的 API

- [ ] **给所有 API 路由加认证** -- `security.py` 写好了 `get_current_user`，但只有 auth 路由用了
- [ ] **补 meeting PUT/DELETE 端点** -- 前端 `MeetingView.vue:324` 调用了但后端没有
- [ ] **补 project DELETE 端点** -- 前端 `ProjectView.vue:282` 调用了但后端没有
- [ ] **实现真正的语义搜索** -- `knowledge.py:118` 当前是 SQL LIKE + 硬编码相似度0.8
- [ ] **取消注释微信通知** -- `reminder_service.py:53` 推送代码被注释
- [ ] **补全 member 创建时的 password_hash** -- `POST /members` 未设置密码，新成员无法登录

## 第三阶段：质量和安全

- [ ] **Chat session 持久化** -- 当前 `self.sessions` 存内存，重启丢失（迁移到 Redis）
- [ ] **修复 N+1 查询** -- `task.py:185` dashboard 统计逐个查成员，应用 `func.count()`
- [ ] **清理无用依赖** -- langchain, chromadb, sentence-transformers, minio, pyannote 从未使用
- [ ] **SECRET_KEY 启动校验** -- `config.py:12` 默认值不安全，应加启动检查
- [ ] **初始化 Alembic 迁移** -- 当前用 `create_all()` 无法处理表结构变更
- [ ] **收紧 CORS** -- `main.py:34` 当前 `allow_origins=["*"]`
- [ ] **登录接口加限流** -- 防止暴力破解
- [ ] **移除登录页硬编码账号** -- `LoginView.vue:49` 显示了默认密码

## 第四阶段：补全基础设施

- [ ] **添加测试** -- `tests/` 目录完全为空，需补充单元测试和 API 测试
- [ ] **配置日志系统** -- `logs/` 目录存在但无日志配置
- [ ] **前端 Pinia 状态管理** -- 当前每个组件各自调 API，无共享状态
- [ ] **voice.py 会议转写保存** -- 第271行 TODO，WebSocket 断开后数据未存库
- [ ] **meeting.py WebSocket 转写** -- 第176行返回硬编码 stub，需接入 Whisper
- [ ] **Docker Whisper 服务与 app 内 Whisper 重复加载** -- 需统一为服务调用或进程内加载

## 第五阶段：功能增强

- [ ] **企业微信 webhook 接收** -- 当前只有推送，无法接收用户消息
- [ ] **腾讯会议 API 集成** -- 配置项存在但无集成代码
- [ ] **MinIO 文件上传** -- 配置和 docker 服务存在但无上传代码
- [ ] **前端 ECharts 注册** -- `Dashboard.vue:77` VChart 组件未注册
- [ ] **通知 badge 真实数据** -- `MainLayout.vue:48` 硬编码为 3

---

## 已完成

### Phase 1 (2026-05-16)

| 问题 | 修复内容 |
|------|---------|
| `_execute_tool` 返回模拟结果 | 重写为路由分发，10 个工具全部接入 TaskService/MemberService/MeetingService/ProjectService/KnowledgeService |
| session_id 硬编码 "default" | `_process_response` 接收 `session_id` 参数，会话隔离正确 |
| celery 模块缺失 | 创建 `app/core/celery.py`，含 beat 定时任务配置 |
| pgvector 未安装 | `main.py` 启动时 `CREATE EXTENSION IF NOT EXISTS vector` |
| chat_stream 不支持工具 | 传入 `tools=self.tools`，添加工具调用处理逻辑 |
| 同步 Anthropic 客户端 | 切换为 `AsyncAnthropic`，不再阻塞事件循环 |
| follow-up 缺少 tools 参数 | 补上 `tools=self.tools`，支持工具链式调用 |
| assistant history 格式错误 | 存储 content blocks 而非字符串 |
| meeting.py 缺少 ARRAY 导入 | 补上导入，修复 NameError |
| 重复 WebSocket 路由 | 移除 meeting.py 中的 stub，保留 voice.py 实现 |

**新建文件：**
- `app/services/member_service.py` — 成员 CRUD 服务
- `app/services/meeting_service.py` — 会议 CRUD 服务
- `app/services/project_service.py` — 项目+里程碑 CRUD 服务
- `app/services/knowledge_service.py` — 知识库 CRUD + 语义搜索服务
- `app/core/celery.py` — Celery 应用配置

**修改文件：**
- `app/agent/core.py` — 完全重写，修复 7 个 bug
- `app/api/v1/chat.py` — 传入 db session
- `app/api/v1/voice.py` — 传入 db session
- `app/api/v1/meeting.py` — 移除重复路由，generate-minutes 传入 db
- `app/models/meeting.py` — 补上 ARRAY 导入
- `app/main.py` — 启动时初始化 pgvector 扩展
- `app/services/reminder_service.py` — 添加 celery task 包装函数
