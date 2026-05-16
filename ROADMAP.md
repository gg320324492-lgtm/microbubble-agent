# MicroBubble Agent - 完善路线图

> 最后更新: 2026-05-17 (更新：WeChat Bot 被动监听 + 主动提醒 + 多信号身份识别)

## 第一阶段：让系统真正能用（关键）

- [x] **接入 Agent 工具执行** -- `_execute_tool` 已连接真实 service 层，10 个工具全部路由到对应 Service
- [x] **修复 session_id bug** -- `_process_response` 已接收 `session_id` 参数，不再硬编码 `"default"`
- [x] **创建 Celery 模块** -- `app/core/celery.py` 已创建，celery-worker/celery-beat 可正常启动
- [x] **配置 pgvector** -- `main.py` 启动时执行 `CREATE EXTENSION IF NOT EXISTS vector`
- [x] **chat_stream 支持工具调用** -- 已传入 `tools=self.tools`，流式对话可触发工具

## 第二阶段：补全缺失的 API

- [x] **给所有 API 路由加认证** -- 31个端点全部加了 `get_current_user`，WebSocket 从 query param 取 token
- [x] **补 meeting PUT/DELETE 端点** -- `meeting.py` 新增 `PUT /meetings/{id}` 和 `DELETE /meetings/{id}`
- [x] **补 project DELETE 端点** -- `project.py` 新增 `DELETE /projects/{id}`
- [x] **实现真正的语义搜索** -- 接入 pgvector + text2vec-base-chinese，embedding_service.py 单例加载模型
- [x] **取消注释微信通知** -- `reminder_service.py` 接入 `wechat_bot.send_message()`
- [x] **补全 member 创建时的 password_hash** -- `MemberCreate` 加 username/password，创建时自动 hash

## 第三阶段：质量和安全

- [x] **Chat session 持久化** -- 迁移到 Redis，`RedisSessionStore` 替代内存 dict，24小时 TTL
- [x] **修复 N+1 查询** -- dashboard 统计改用 `func.count()` + `GROUP BY` 聚合查询
- [x] **清理无用依赖** -- 移除 langchain, langchain-anthropic, chromadb, minio, pyannote-audio
- [x] **SECRET_KEY 启动校验** -- 生产环境检测默认值，未配置则拒绝启动
- [x] **初始化 Alembic 迁移** -- 创建 `alembic/` 目录、`env.py`（async）、初始迁移脚本
- [x] **收紧 CORS** -- 替换 `allow_origins=["*"]` 为显式白名单
- [x] **登录接口加限流** -- 滑动窗口限流器，5分钟内最多5次尝试，按 IP 限制
- [x] **移除登录页硬编码账号** -- 改为"请联系管理员获取账号密码"

## 第四阶段：补全基础设施

- [ ] **添加测试** -- `tests/` 目录完全为空，需补充单元测试和 API 测试
- [ ] **配置日志系统** -- `logs/` 目录存在但无日志配置
- [ ] **前端 Pinia 状态管理** -- 当前每个组件各自调 API，无共享状态
- [ ] **voice.py 会议转写保存** -- 第271行 TODO，WebSocket 断开后数据未存库
- [ ] **meeting.py WebSocket 转写** -- 第176行返回硬编码 stub，需接入 Whisper
- [ ] **Docker Whisper 服务与 app 内 Whisper 重复加载** -- 需统一为服务调用或进程内加载

## 第五阶段：功能增强

- [x] **企业微信群机器人** -- 完整实现：webhook 回调、消息加解密、任务派发私发、进度跟踪、汇总通知
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

### Phase 2 (2026-05-16)

| 问题 | 修复内容 |
|------|---------|
| 31个API端点无认证 | 全部加 `get_current_user`，DELETE /members 改用 `get_current_admin_user` |
| WebSocket 无认证 | 新增 `get_current_user_ws`，WS 端点从 query param 校验 token |
| meeting 缺 PUT/DELETE | 新增 `PUT /meetings/{id}` 和 `DELETE /meetings/{id}` |
| project 缺 DELETE | 新增 `DELETE /projects/{id}` |
| 语义搜索是假的 | 接入 pgvector + text2vec-base-chinese，cosine_distance 真实相似度 |
| 微信通知被注释 | 接入 `wechat_bot.send_message()`，加异常守卫 |
| 创建成员无密码 | `MemberCreate` 加 username/password，`get_password_hash` 自动 hash |

**新建文件：**
- `app/services/embedding_service.py` — 向量嵌入服务（单例模型加载 + 异步生成）

**修改文件：**
- `app/core/security.py` — 新增 `get_current_user_ws()` WebSocket 认证
- `app/api/v1/member.py` — 全部端点加认证 + 创建成员支持密码
- `app/api/v1/project.py` — 全部端点加认证 + 新增 DELETE 端点
- `app/api/v1/meeting.py` — 全部端点加认证 + 新增 PUT/DELETE 端点
- `app/api/v1/task.py` — 全部端点加认证
- `app/api/v1/knowledge.py` — 全部端点加认证 + 语义搜索改用 service
- `app/api/v1/chat.py` — POST + WebSocket 加认证
- `app/api/v1/voice.py` — 全部端点加认证
- `app/services/knowledge_service.py` — create/update 生成 embedding，search_semantic 改用 pgvector
- `app/services/reminder_service.py` — 接入 wechat_bot 推送
- `app/schemas/member.py` — MemberCreate 加 username/password 字段
- `requirements.txt` — 加 pgvector==0.2.4

### WeChat Bot (2026-05-17)

| 功能 | 说明 |
|------|------|
| 消息加解密 | AES-256-CBC + PKCS7，支持 URL 验证和消息加解密 |
| Webhook 回调 | GET 验证 + POST 接收，异步处理避免 5 秒超时 |
| 任务派发 | 老师对话触发 → 创建任务 → 私发给每个负责人 |
| 进度回复 | 学生回复"完成/进度50%/遇到问题" → 自动更新任务状态 |
| 汇总通知 | 有问题转发老师，全员完成自动汇总通知 |
| 群聊+私聊 | 群里 @机器人 或 私聊直接发消息均可触发 |
| 多信号身份识别 | userid → wechat_id → 手机号 → 昵称模糊匹配，首次匹配自动绑定 |
| 群聊被动监听 | 消息缓冲 + 关键词触发 → Claude 分析 → 自动提取任务/会议/决定 |
| 主动提醒调度 | Celery 定时（15分钟）检查：即将到期、已逾期、未确认、即将开始的会议 |
| 图片识别 | Claude Vision 分析图片消息，支持任务截图和人物识别 |

**新建文件：**
- `app/wechat/crypto.py` — 消息加解密（AES-CBC + 签名验证）
- `app/wechat/handler.py` — 消息处理（任务回复识别 + Agent 对话 + 群聊被动监听）
- `app/wechat/notifier.py` — 主动通知（任务分配/完成/问题/汇总）
- `app/wechat/identity.py` — 多信号身份解析（userid/昵称/手机/微信号模糊匹配）
- `app/wechat/analyzer.py` — 对话智能分析（Claude API 提取任务/会议/决定）
- `app/wechat/scheduler.py` — 主动提醒调度器（Celery task，每15分钟执行）
- `app/services/vision_service.py` — 视觉识别服务（Claude Vision 图片分析）
- `app/api/v1/wechat.py` — Webhook 回调端点

**修改文件：**
- `app/config.py` — 新增 WECHAT_CALLBACK_TOKEN、WECHAT_ENCODING_AES_KEY
- `app/main.py` — 注册 wechat 路由
- `app/wechat/bot.py` — 新增 reply_to_user 方法
- `app/core/celery.py` — 新增 proactive-checks 定时任务（每15分钟），autodiscover wechat 模块
- `app/services/reminder_service.py` — 添加 `@shared_task` 装饰器
- `app/models/member.py` — 新增多平台身份字段（wechat_nickname/wechat_remark/personal_wechat_id/wechat_mobile）
- `app/schemas/member.py` — MemberCreate/MemberUpdate/MemberResponse 包含新身份字段
- `app/api/v1/member.py` — 创建成员支持新身份字段

### Phase 3 (2026-05-17)

| 问题 | 修复内容 |
|------|---------|
| Chat session 存内存 | 迁移到 Redis（`RedisSessionStore`），24小时 TTL，重启不丢失 |
| dashboard N+1 查询 | 项目/成员统计改用 `func.count()` + `GROUP BY` 单条 SQL 聚合 |
| 无用依赖 | 移除 langchain, langchain-anthropic, chromadb, minio, pyannote-audio，去重 httpx |
| SECRET_KEY 不安全 | 生产环境检测默认值，未配置则 `sys.exit(1)`；开发环境 `warnings.warn` |
| 无数据库迁移 | 初始化 Alembic，async env.py，初始迁移脚本含全部 9 张表 |
| CORS 全开放 | 替换为显式白名单（localhost:5173/3000 + 生产域名） |
| 登录无限流 | 滑动窗口限流器（`rate_limit.py`），5分钟/5次/IP，失败也计数 |
| 登录页泄露密码 | 移除硬编码账号密码，改为"请联系管理员" |

**新建文件：**
- `app/core/rate_limit.py` — 滑动窗口限流器
- `app/core/redis.py` — 扩展：新增 `RedisSessionStore` 类
- `alembic.ini` — Alembic 配置
- `alembic/env.py` — 异步迁移环境
- `alembic/script.py.mako` — 迁移模板
- `alembic/versions/001_initial.py` — 初始迁移（9张表 + pgvector 扩展）

**修改文件：**
- `app/config.py` — SECRET_KEY 默认值改为空字符串
- `app/main.py` — SECRET_KEY 校验 + CORS 白名单 + Redis 关闭
- `app/api/v1/auth.py` — 登录端点接入限流器
- `app/api/v1/task.py` — dashboard 和 list 改用聚合查询
- `app/agent/core.py` — session 迁移到 Redis（`_load_session`/`_save_session`）
- `web/src/views/LoginView.vue` — 移除硬编码账号密码
- `requirements.txt` — 移除 5 个无用依赖，去重 httpx
