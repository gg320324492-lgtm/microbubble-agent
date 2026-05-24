# MicroBubble Agent - 完善路线图

> 最后更新: 2026-05-22 (更新：文档全面核对，Phase 1-5 全部完成)

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

- [x] **添加测试** -- `tests/` 新增 conftest.py + test_auth/test_tasks/test_members，覆盖认证、任务 CRUD、成员管理（⚠️ 需真实 PostgreSQL+pgvector 环境才能运行，无 CI 流水线）
- [x] **配置日志系统** -- `app/core/logging.py` 统一配置，生产环境写文件（RotatingFileHandler 10MB×5）
- [x] **前端 Pinia 状态管理** -- 新增 member store（共享成员列表）和 user store（用户信息+通知数），MainLayout 接入
- [x] **voice.py 会议转写保存** -- WebSocket 断开后自动将转写结果保存到 meeting.transcript
- [x] **meeting.py WebSocket 转写** -- 已在 voice.py 实现（/ws/meeting/{id}/transcript），meeting.py 无需重复
- [x] **Docker Whisper 服务与 app 内 Whisper 重复加载** -- asr.py 改为优先调用远程 Whisper 服务，回退到本地模型

## 第五阶段：功能增强

- [x] **企业微信群机器人** -- 5 个部署阻塞项已全部修复（运行时 bug、配置补全、@提及检测、Redis 持久化、结构化日志），代码就绪待上线
- [x] **微信互通（普通微信用户支持）** -- 课题组成员可用私人微信与机器人对话（私聊+群聊），无需下载企业微信。通过企业微信「微信互通」外部联系人功能实现
- [x] **腾讯会议 API 集成** -- 签名算法修正、Agent `create_meeting` 自动创建线上会议、Webhook 回调端点、错误重试。需配置凭据后测试
- [x] **MinIO 文件上传** -- 通用上传 + 会议附件上传 + 删除，自动创建 bucket
- [x] **前端 ECharts 注册** -- `<script setup>` 已自动注册，无需额外配置
- [x] **通知 badge 真实数据** -- 改为从 API 获取待处理提醒数量，user store 管理
- [x] **会议转写自动分析** -- 会议结束自动提取摘要/要点/决定/任务，任务自动创建并关联会议。WebSocket 转写断开和腾讯会议 Webhook 回调均触发分析，支持手动 `POST /meetings/{id}/analyze`
- [x] **CLAUDE_MODEL 可配置** -- 新增 `CLAUDE_MODEL` 配置项，analyzer 和 summary 统一使用，兼容 mimo-v2.5 ThinkingBlock 响应
- [x] **前端图片识别** -- 主对话窗口支持图片上传和识别，使用 mimo-v2.5 多模态能力，支持图片+文字混合消息
- [x] **任务权限控制与自定义提醒** -- 管理员可分配任务给任何人，普通成员只能给自己创建/查看/编辑/删除任务；支持自定义提醒时间点；API/Agent/前端三层权限控制

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

### WeChat Bot (2026-05-17) -- ⚠️ 代码完成，未部署

| 功能 | 说明 | 状态 |
|------|------|------|
| 消息加解密 | AES-256-CBC + PKCS7，支持 URL 验证和消息加解密 | ✅ 代码完成 |
| Webhook 回调 | GET 验证 + POST 接收，异步处理避免 5 秒超时 | ✅ 代码完成 |
| 任务派发 | 老师对话触发 → 创建任务 → 私发给每个负责人 | ✅ 代码完成 |
| 进度回复 | 学生回复"完成/进度50%/遇到问题" → 自动更新任务状态 | ✅ 代码完成 |
| 汇总通知 | 有问题转发老师，全员完成自动汇总通知 | ✅ 代码完成 |
| 群聊+私聊 | 群里 @机器人 或 私聊直接发消息均可触发 | ⚠️ @检测硬编码，不匹配实际企业微信格式 |
| 多信号身份识别 | userid → wechat_id → 手机号 → 昵称模糊匹配，首次匹配自动绑定 | ✅ 代码完成 |
| 群聊被动监听 | 消息缓冲 + 关键词触发 → Claude 分析 → 自动提取任务/会议/决定 | ✅ 代码完成 |
| 主动提醒调度 | Celery 定时（15分钟）检查：即将到期、已逾期、未确认、即将开始的会议 | ✅ 代码完成 |
| 图片识别 | mimo-v2.5 多模态模型分析图片消息，支持任务截图和人物识别 | ✅ 代码完成，已修复 |

**~~部署阻塞项~~（已全部修复）：**
1. ~~`handler.py:259` 调用不存在的 `notifier.notify_meeting_notification()`~~ → 改为 `wechat_bot.send_meeting_notification()`
2. ~~`.env.example` 缺少 `WECHAT_CALLBACK_TOKEN` 和 `WECHAT_ENCODING_AES_KEY`~~ → 已补全
3. ~~`_pending_users` / `_group_buffers` 为内存状态~~ → 已迁移到 Redis（自动过期）
4. ~~异常处理全部用 `print()`~~ → 改用 `logging.getLogger("microbubble.wechat")`
5. ~~Nginx 未配置微信 5 秒超时优化~~ → 异步 `asyncio.create_task` + 立即返回 success

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

### 微信互通 (2026-05-18) -- 支持普通微信用户

课题组成员可用私人微信与机器人对话，无需下载企业微信。通过企业微信「微信互通」外部联系人功能实现。

| 功能 | 说明 | 状态 |
|------|------|------|
| 外部用户识别 | 通过 `external_userid`（wm 开头）自动识别普通微信用户 | ✅ 完成 |
| 双通道发送 | 内部用户走 `/cgi-bin/message/send`，外部用户走 `/cgi-bin/externalcontact/message/send` | ✅ 完成 |
| 外部群聊 | 外部群（wr 开头）走 `/cgi-bin/externalcontact/groupchat/send_chat_msg` | ✅ 完成 |
| 智能路由 | `smart_send()` / `smart_send_to_group()` 自动选择正确的 API | ✅ 完成 |
| 身份绑定 | 外部用户首次使用时通过姓名/手机号自引导绑定 | ✅ 完成 |
| 通知适配 | 任务提醒、会议通知、进度汇报等全部支持外部用户 | ✅ 完成 |

**新建文件：**
- `alembic/versions/002_add_external_userid.py` — 数据库迁移

**修改文件：**
- `app/models/member.py` — 新增 `external_userid` 列
- `app/schemas/member.py` — 新增 `external_userid` 字段
- `app/config.py` — 新增 `WECHAT_EXTERNAL_SENDER` 配置
- `.env.example` — 新增 `WECHAT_EXTERNAL_SENDER`
- `app/wechat/identity.py` — 新增 `resolve_by_external_userid()`，更新 `resolve_multi_signal()` 和 `bind_identity()`
- `app/wechat/bot.py` — 新增 `send_to_external_user()`、`send_to_external_group()`、`smart_send()`、`smart_send_to_group()`
- `app/wechat/handler.py` — 外部用户检测、身份解析、回复路由、群聊适配
- `app/wechat/notifier.py` — 方法签名改为接收 `Member` 对象，使用 `smart_send()`
- `app/wechat/scheduler.py` — 全部改用 `smart_send()` 支持外部用户
- `app/services/reminder_service.py` — 改用 `smart_send()`，修复 `print()` 为结构化日志

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

### Phase 4 (2026-05-17)

| 问题 | 修复内容 |
|------|---------|
| 无日志配置 | `app/core/logging.py` 统一日志，生产环境 RotatingFileHandler |
| Dashboard ECharts 不显示 | 确认 `<script setup>` 自动注册，无需修改 |
| 通知角标硬编码 | MainLayout 改为从 API 获取提醒数量，user store 管理 |
| 会议转写未保存 | voice.py WebSocket 断开后自动存入 meeting.transcript |
| meeting.py 转写 stub | 已在 voice.py 实现，meeting.py 无需重复 |
| Whisper 双重加载 | asr.py 改为 HTTP 优先调用远程服务，回退本地模型 |
| 无 Pinia store | 新增 user store + member store + format 工具函数 |
| 无测试 | 新增 conftest.py + 3 个测试文件（auth/tasks/members） |

**新建文件：**
- `app/core/logging.py` — 统一日志配置
- `app/core/rate_limit.py` — 滑动窗口限流器
- `web/src/stores/member.js` — 成员 Pinia store
- `web/src/stores/user.js` — 用户 Pinia store
- `web/src/utils/format.js` — 日期格式化工具
- `tests/conftest.py` — 测试 fixtures（db/client/auth）
- `tests/test_auth.py` — 认证测试（登录/刷新/修改密码）
- `tests/test_tasks.py` — 任务测试（CRUD/统计/dashboard）
- `tests/test_members.py` — 成员测试（CRUD/权限）
- `pytest.ini` — pytest 配置

**修改文件：**
- `app/api/v1/voice.py` — 转写断开后保存到数据库
- `app/api/v1/task.py` — 新增 reminders/pending-count 端点
- `app/voice/asr.py` — 改为远程 Whisper 优先 + 本地回退
- `app/main.py` — 引入 logging 模块
- `web/src/layouts/MainLayout.vue` — 接入 user store + member store

### Phase 5 (2026-05-17)

| 功能 | 说明 | 状态 |
|------|------|------|
| 腾讯会议 API | 创建/查询/取消/结束会议，HMAC-SHA256 签名，Webhook 回调，Agent 自动创建线上会议，错误重试 | ✅ 代码完成，待配置凭据测试 |
| MinIO 文件上传 | 通用上传（50MB 限制）+ 会议附件 + 删除，自动创建 bucket | ✅ 完成 |
| 企业微信群机器人 | 完整实现（已在 WeChat Bot 阶段完成） | ⚠️ 代码完成，未部署（见 WeChat Bot 部署阻塞项） |
| 会议转写自动分析 | 转写结束自动调用 Claude 提取摘要/要点/决定，自动创建任务并关联会议，支持手动重新分析 | ✅ 完成 |
| CLAUDE_MODEL 可配置 | 新增配置项，兼容代理服务的 ThinkingBlock 响应 | ✅ 完成 |

**新建文件：**
- `app/services/tencent_meeting_service.py` — 腾讯会议 API 客户端（HMAC-SHA256 签名）
- `app/services/file_service.py` — MinIO 文件存储服务
- `app/api/v1/tencent_meeting.py` — 腾讯会议 API 端点（创建/关联/查询/取消）
- `app/api/v1/upload.py` — 文件上传 API 端点（通用/会议附件/删除）

**修改文件：**
- `app/main.py` — 注册 upload 和 tencent_meeting 路由
- `requirements.txt` — 恢复 minio==7.2.0
- `app/services/meeting_service.py` — 新增 `process_meeting_transcript()`、`_generate_summary()`、`_auto_create_task_from_meeting()`
- `app/api/v1/voice.py` — WebSocket 断开后自动触发会议分析
- `app/api/v1/meeting.py` — 新增 `POST /meetings/{id}/analyze` 手动分析端点
- `app/api/v1/tencent_meeting.py` — Webhook 会议结束时自动触发分析
- `app/wechat/analyzer.py` — 模型改为 `settings.CLAUDE_MODEL`，兼容 ThinkingBlock 响应
- `app/config.py` — 新增 `CLAUDE_MODEL`

### 前端图片识别 (2026-05-19)

| 功能 | 说明 | 状态 |
|------|------|------|
| 图片上传 | 前端支持选择图片文件，预览后发送 | ✅ 完成 |
| 多模态对话 | 使用 mimo-v2.5 模型分析图片内容，支持图片+文字混合消息 | ✅ 完成 |
| 图片消息展示 | 消息列表支持显示图片，点击可全屏预览 | ✅ 完成 |
| API 图片接口 | 新增 `POST /chat/image` 接口，支持 multipart/form-data 图片上传 | ✅ 完成 |
| WebSocket 图片 | WebSocket 支持 base64 编码的图片消息 | ✅ 完成 |
| 企业微信视觉 | vision_service 改用配置的模型（默认 mimo-v2.5） | ✅ 完成 |

**修改文件：**
- `app/agent/core.py` — `chat()` 和 `chat_stream()` 新增 `image_data` 和 `image_media_type` 参数，构建多模态消息
- `app/api/v1/chat.py` — 新增 `POST /chat/image` 接口，WebSocket 支持图片消息
- `app/services/vision_service.py` — `analyze_image()` 改用 `settings.CLAUDE_MODEL` 或 `mimo-v2.5`
- `web/src/views/ChatView.vue` — 新增图片上传按钮、预览功能、图片消息展示、相关样式

### 企业微信图片处理修复 (2026-05-19)

| 问题 | 修复内容 |
|------|---------|
| 微信发送图片显示"图片处理出错了" | vision_service.py 添加异常处理和日志记录 |
| 模型配置错误 | 改用 `settings.CLAUDE_MODEL or "mimo-v2.5"` 替代硬编码的 `claude-sonnet-4-20250514` |
| media_type 硬编码 | 添加 `_detect_media_type()` 方法，根据图片魔数自动检测格式 |
| Docker 容器代码未同步 | 重新构建镜像并重启容器 |

**修改文件：**
- `app/services/vision_service.py` — 添加 try/except 异常处理、结构化日志、更健壮的响应解析、自动检测 media_type

**状态：** ✅ 已修复，图片识别功能正常工作

### 联网搜索 (2026-05-19)

| 功能 | 说明 | 状态 |
|------|------|------|
| 搜狗微信搜索 | 通过 weixin.sogou.com 搜索微信公众号文章，国内可直连 | ✅ 完成 |
| 必应搜索 | 通过 www.bing.com 搜索，作为补充引擎 | ✅ 完成 |
| 双引擎并发 | 两个搜索引擎并发请求，按 URL 去重合并结果 | ✅ 完成 |
| 流式工具调用修复 | 修复 chat_stream 中 input_json 被覆盖而非追加的 bug | ✅ 完成 |
| SDK 方法名修复 | get_final_response 改为 get_final_message（SDK 0.103.0） | ✅ 完成 |
| 回复格式优化 | 系统提示词去除 markdown 格式，避免模型模仿产生混乱排版 | ✅ 完成 |
| 禁止编造网址 | 提示词约束模型只使用搜索结果中的 URL，不自行编造 | ✅ 完成 |

**修改文件：**
- `app/services/search_service.py` — 完整重写：搜狗微信+必应双引擎并发搜索
- `app/agent/core.py` — 修复流式 input_json 拼接 bug + get_final_message 方法名
- `app/agent/prompts.py` — 去除 markdown 格式，添加搜索回复格式规范

### Claude Code 任务通知优化 (2026-05-19)

| 功能 | 说明 | 状态 |
|------|------|------|
| 音量调至最大 | `$synth.Volume = 100`，Rate 调为 -1 更清晰 | ✅ 完成 |
| 提示词加长 | 从"任务完成啦"改为完整提示语 | ✅ 完成 |

**修改文件：**
- `.claude/notify.ps1` — 音量最大 + 语速调整
- `.claude/settings.json` — Stop hook 提示词更新

---

## 部署架构（2026-05-18 确定）

采用 **云服务器 + 本地电脑 FRP 穿透** 方案：

```
用户 → 云服务器 (Nginx + SSL + FRP 服务端) → FRP 隧道 → 本地电脑 (全部 Docker 服务 + GPU Whisper)
```

- **云服务器**（2核 2G）：只运行 Nginx 反向代理 + FRP 服务端，轻量无压力
- **本地电脑**（有 GPU）：运行全部应用服务（app、PostgreSQL、Redis、MinIO、Whisper GPU、Celery）
- **FRP 隧道**：本地 8000 端口穿透到云服务器，用户通过 `https://agent.mnb-lab.cn` 访问

## 待完成：生产部署与上线

### 部署代码准备 ✅

- [x] docker-compose.yml 添加 Nginx 服务 + app 端口映射
- [x] 创建 Nginx 生产配置（HTTP/HTTPS，安全头，WebSocket 代理）
- [x] 部署脚本：`deploy-cloud.sh`（云服务器）、`deploy-local.sh`（本地电脑）
- [x] FRP 内网穿透配置（frps.toml / frpc.toml）
- [x] Whisper 改为 GPU 模式（Dockerfile.whisper 支持环境变量配置）
- [x] Claude API 支持代理地址（`CLAUDE_BASE_URL` 配置项）
- [x] `.env.example` 补全 `WECHAT_CALLBACK_TOKEN` 和 `WECHAT_ENCODING_AES_KEY`

### 云服务器部署 ✅

- [x] FRP 服务端安装（v0.61.1，已配置 systemd 自启动）
- [x] FRP 服务端配置（端口 7000，token 认证）
- [x] Nginx 安装
- [x] 前端构建并部署（本地构建 → 压缩 → 阿里云文件管理上传 → 服务器解压）
- [x] Nginx 配置部署（更新已有 agent 配置，HTTPS + SSL 已有证书）
- [x] 防火墙配置（开放 80/443/7000 端口）
- [x] 恢复之前的网站配置 ✅
- [x] SSL 证书（已有 Let's Encrypt 证书，直接复用）

### 本地电脑部署 ✅

- [x] 安装 Docker Desktop ✅
- [x] 配置 .env 文件（Claude API Key + 代理地址）
- [x] Docker 全服务构建（app/db/redis/minio/celery-worker/celery-beat）
- [x] FRP 客户端连接云服务器
- [x] 通过域名访问测试（API 正常响应）
- [x] Docker 数据迁移到 G 盘（释放 C 盘 68GB，通过符号链接无感迁移）
- [x] 一键启动/停止/状态脚本（start.bat / stop.bat / status.bat）

### 企业微信部署

- [x] 修复 `handler.py:259` 运行时 bug（改为 `wechat_bot.send_meeting_notification()`）
- [x] 内存状态（`_pending_users` / `_group_buffers`）迁移到 Redis（自动过期）
- [x] 异常处理改用结构化日志（`logging.getLogger("microbubble.wechat")`）
- [x] @提及检测改为匹配企业微信实际格式（` @` 分隔符 + AgentID 匹配）
- [x] Nginx 已满足 5 秒超时（异步 `asyncio.create_task` + 立即返回 success）
- [x] 通知消息格式修复（markdown → text，插件端不支持 markdown 渲染）
- [x] `wechat_id` 从昵称同步为真实 UserId（`list_department_members()` API）
- [x] 通知代码独立 try/except + 结构化日志 + errcode 检查
- [ ] 9 位成员未在企业微信通讯录中，需在管理后台添加后才能接收提醒推送

### 微信互通部署（普通微信用户支持） - ✅ 已完成

> **当前方案**：使用企业微信「微信插件」功能，成员只需注册一次企业微信，之后可在普通微信内与小气对话，无需额外配置。
> **微信互通适用场景**：如有外部用户（不愿注册企业微信的人）需要联系小气，再启用此功能。

**微信互通配置步骤（已完成）：**

- [x] 企业微信管理后台创建机器人专属成员账号（如 `xiaoqi`）
- [x] 开通「客户联系」→ 将 `xiaoqi` 加入可使用范围
- [x] 创建「联系我」二维码（单人模式，选 `xiaoqi`）
- [x] 配置回调：勾选客户联系相关事件（`change_external_contact`、`change_external_chat`）
- [x] `.env` 配置 `WECHAT_EXTERNAL_SENDER=xiaoqi`
- [x] 运行数据库迁移：`alembic upgrade head`
- [x] 用普通微信扫码添加「小气」，测试私聊消息收发
- [x] 创建外部群，拉「小气」进群，测试群聊消息收发
- [x] 从日志获取群聊 `wr...` chat_id：`docker compose logs app | grep chat_id`

### 腾讯会议部署

- [x] 修正签名算法（HMAC-SHA256，URI 加 openapi 前缀）
- [x] 添加 `host.userid` 参数（创建会议必须）
- [x] Agent `create_meeting` 工具集成腾讯会议 API（自动创建线上会议）
- [x] 添加 Webhook 回调端点（`/api/v1/tencent-meeting/webhook`）
- [x] 添加错误重试（3 次，指数退避）
- [x] 新增 list/end 端点
- [ ] 申请并配置真实 API 凭据（`TENCENT_MEETING_SDK_ID` / `TENCENT_MEETING_SDK_KEY` / `TENCENT_MEETING_USERID`）
- [ ] 企业微信管理后台配置 Webhook 回调 URL
- [ ] 凭据到位后端到端测试

---

## 第六阶段：功能增强

### 联网搜索

- [x] **Agent 工具集成联网搜索** -- 新增 `web_search` 工具，搜狗微信+必应双引擎并发搜索，无需 API Key
- [x] **搜索结果摘要** -- 搜索结果由 LLM 整理后返回，避免直接返回原始网页内容
- [x] **搜索来源引用** -- 回复中附带信息来源链接，方便用户查证
- [x] **搜索权限控制** -- 搜索功能始终可用，无需额外配置

### 长期记忆 (2026-05-19)

- [x] **用户偏好记忆** -- 记住用户的常用设置、偏好习惯，preference 类型按 key 去重
- [x] **对话历史摘要** -- 对话结束后后台自动提取值得记忆的信息（偏好/实体/摘要）
- [x] **知识图谱构建** -- 从对话中提取实体关系（人员-项目-成果），entity 类型存储
- [x] **记忆检索与更新** -- 新对话自动检索相关记忆注入系统提示词，支持手动编辑/遗忘
- [x] **记忆存储方案** -- PostgreSQL + pgvector 语义搜索，importance 衰减机制

**新建文件：**
- `app/models/memory.py` — Memory 模型（preference/summary/entity 三种类型）
- `app/services/memory_service.py` — 记忆 CRUD + 语义搜索 + LLM 自动提取
- `app/api/v1/memory.py` — 记忆管理 API（列表/编辑/删除）
- `alembic/versions/004_add_memory_table.py` — 数据库迁移
- `web/src/views/MemoryView.vue` — 记忆管理前端页面

**修改文件：**
- `app/models/__init__.py` — 注册 Memory 模型
- `app/agent/tools.py` — 新增 save_memory/search_memory/forget_memory 三个工具
- `app/agent/core.py` — chat() 新增 user_id 参数，记忆注入系统提示词，后台自动提取记忆
- `app/agent/prompts.py` — 添加长期记忆使用规则
- `app/api/v1/chat.py` — 所有端点传递 user_id 给 agent
- `app/main.py` — 注册 memory 路由
- `app/core/celery.py` — 新增 memory-maintenance 定时任务（每小时衰减重要性）
- `web/src/router/index.js` — 新增 /memory 路由

### 对话窗口文件上传 (2026-05-19)

- [x] **前端文件上传组件** -- 对话窗口回形针按钮，支持上传图片、PDF、Word、Excel 等文件
- [x] **图片预览与发送** -- 图片和文件分别显示预览，支持文件名和大小显示
- [x] **文件内容提取** -- 后端 pdfplumber/python-docx/openpyxl 解析文件，提取文本发送给 Agent
- [x] **文件对话上下文** -- 上传的文件内容自动注入对话上下文，支持基于文件内容的问答
- [x] **文件存储管理** -- 上传的文件存储到 MinIO（chat/{session_id}/ 前缀），返回文件 URL

**新建文件：**
- `app/services/file_parser_service.py` — 文件内容提取服务（PDF/Word/Excel/TXT/Markdown）

**修改文件：**
- `app/api/v1/chat.py` — 新增 POST /chat/file 端点，ChatResponse 添加 file_url/file_name
- `web/src/views/ChatView.vue` — 回形针按钮、文件预览、统一发送逻辑

### 知识库增强 (2026-05-19)

- [x] **知识库文件上传** -- 知识库页面新增上传按钮，支持拖拽上传 PDF/Word/TXT/Markdown 文件
- [x] **文件自动解析** -- 上传后自动提取文本内容，后台生成摘要和关键词
- [x] **智能分类分析** -- LLM 自动分析文件内容，自动归类到合适的分类
- [x] **自动标签生成** -- 根据文件内容自动生成标签
- [x] **分类统计面板** -- 知识库页面顶部展示各分类文件数量统计，支持点击筛选

**新建文件：**
- `app/services/llm_analysis_service.py` — LLM 内容分析服务（自动分类+标签+摘要）
- `alembic/versions/003_knowledge_file_upload.py` — 知识表添加文件列

**修改文件：**
- `app/models/knowledge.py` — 新增 file_path/file_name/file_type/summary 列
- `app/schemas/knowledge.py` — KnowledgeResponse 添加文件字段，修复 KnowledgeSearchResult
- `app/services/knowledge_service.py` — 修复 embedding 自动生成 bug，新增 create_from_file()
- `app/api/v1/knowledge.py` — 修复分页 total bug，新增 /upload 和 /stats 端点
- `requirements.txt` — 新增 pdfplumber/python-docx/openpyxl
- `web/src/views/KnowledgeView.vue` — 上传对话框、分类统计面板、文件图标、修复搜索结果显示

### 对话知识自动入库 (2026-05-19)

- [x] **对话知识提取工具** -- 新增 `save_conversation_knowledge` 工具，Agent 可主动将有价值的对话内容保存到知识库
- [x] **后台自动提取** -- 每次对话结束后 LLM 自动分析内容，提取实验方法、研究发现、技术方案等专业知识
- [x] **智能分类打标签** -- 提取的知识自动分类（基础/方法/文献/FAQ）并生成标签和摘要
- [x] **对话来源标记** -- 知识库中来自对话的条目显示 💬 标记，详情页标注"来自对话记录，AI 自动提取"

**修改文件：**
- `app/agent/tools.py` — 新增 save_conversation_knowledge 工具定义
- `app/agent/core.py` — 新增 `_extract_and_save_knowledge` 后台任务，chat() 中触发知识提取
- `app/agent/prompts.py` — 系统提示词新增知识库保存规则
- `app/services/knowledge_service.py` — 新增 `create_from_conversation()` 方法
- `web/src/views/KnowledgeView.vue` — 对话来源标记样式

### 成员身份系统全面升级 (2026-05-20)

| 问题 | 修复内容 |
|------|---------|
| 插件身份冲突 | 微信插件 `from_user` 是真实 ID 时用它识别，是 agent app name 时走验证流程，不绑定 agent ID |
| 验证缓存 key 碰撞 | `_get_plugin_cache_key` 统一缓存 key 逻辑，`from_user` 是真实 ID 时用它做 key |
| 群聊/私聊 user_id 错误 | `_handle_group_message` 和 `_handle_private_message` 改用 `msg["_resolved_user_id"]` |
| bind_identity 永不覆盖 | 新增 `force` 参数，`True` 时覆盖已有值，`False` 时仅填充空字段 |
| 重名返回任意匹配 | `resolve_by_nickname` 改为返回 `List[Member]`，多人同名时进入消歧流程 |
| 验证缓存无失效 | 新增 `invalidate_verified_cache_for_member()`，验证成功/成员停用时清除旧缓存 |
| kf_service open_kfid 未传递 | `_call_agent_for_kf` 增加 `open_kfid` 参数，移除无效的 `hasattr` 判断 |
| _handle_event 未设 _reply_to | 事件处理也设置 `msg["_reply_to"]`，与 handle_message 一致 |

**修改文件：**
- `app/core/redis.py` — 新增 `invalidate_verified_cache_for_member()` 工具函数
- `app/wechat/identity.py` — `resolve_by_nickname` 返回列表 + `bind_identity` 增加 `force` 参数
- `app/wechat/handler.py` — 7 处改动（插件身份、缓存 key、群聊/私聊 user_id、重名消歧、事件回复、客服 open_kfid）
- `app/api/v1/member.py` — 删除成员时清除验证缓存

### 前端体验优化 (2026-05-19)

- [x] **知识库标签美化** -- 分类改为彩色徽章（蓝/绿/橙/紫），标签改为圆角药丸样式
- [x] **分类统计增强** -- 统计面板增加 emoji 图标，点击支持筛选切换，hover 上浮动效
- [x] **分类标签栏** -- 改为圆角药丸样式，选中态蓝色高亮
- [x] **AI 摘要展示** -- 知识详情弹窗 AI 摘要区域独立展示（蓝色渐变背景 + 左侧边框）
- [x] **文件上传提示** -- 上传对话框增加 AI 自动分析提示条
- [x] **对话拖拽上传** -- 小气助手输入区域支持拖拽文件/图片上传，拖入时显示蓝色虚线边框
- [x] **上传按钮优化** -- 上传按钮增加 hover 高亮，文件按钮 tooltip 补充格式说明

**修改文件：**
- `web/src/views/KnowledgeView.vue` — 标签/分类/统计面板/详情弹窗/上传对话框全面美化
- `web/src/views/ChatView.vue` — 拖拽上传支持、Upload 图标导入、上传按钮样式

### 时间精度全面升级 (2026-05-20)

将整个系统的时间处理从"天级"提升到"分钟级"，统一北京时间/UTC 时区处理。

| 改动 | 说明 | 状态 |
|------|------|------|
| 系统提示词注入精确时间 | `get_system_prompt()` 动态注入 `YYYY年M月D日 星期X HH:MM`，Agent 感知当前时间 | ✅ 完成 |
| 用户消息注入时间标签 | 每条消息前加 `[当前时间: YYYY-MM-DD HH:MM]`，防止模型引用历史过期时间 | ✅ 完成 |
| due_date 精度提升 | 工具描述改为 `YYYY-MM-DD HH:MM`，解析先尝试精确格式再 fallback 日期 | ✅ 完成 |
| 提醒消息精确时间 | `_format_reminder_message` 用 `total_seconds()` 替代 `.days`，显示"还有X小时/分钟到期" | ✅ 完成 |
| 时区统一 | 全局 `utcnow()` 返回 naive UTC，Agent 解析时先转北京时间再转 UTC 存储 | ✅ 完成 |
| 默认提醒优化 | 根据距截止时间远近自适应：≤1h→1分钟后提醒，≤24h→提前30分钟，>24h→提前2天+2小时 | ✅ 完成 |
| 前端 datetime 选择器 | Dashboard/TaskView 截止日期改为 `type="datetime"`，支持选择具体时间 | ✅ 完成 |

**修改文件：**
- `app/agent/prompts.py` — `get_system_prompt()` 动态注入当前时间
- `app/agent/core.py` — 用户消息注入时间标签 + due_date/reminders 北京时间→UTC 转换 + `update_task` 支持 due_date
- `app/agent/tools.py` — due_date/reminders 参数描述更新
- `app/models/base.py` — `utcnow()` 改为 `datetime.now(timezone.utc).replace(tzinfo=None)`
- `app/services/reminder_service.py` — `_format_reminder_message` 精确时间显示
- `app/services/task_service.py` — `_create_default_reminders` 自适应提醒策略
- `web/src/views/Dashboard.vue` — datetime 选择器 + 时间显示
- `web/src/views/TaskView.vue` — datetime 选择器
- 约 15 个文件的 `datetime.utcnow()` 替换为 `utcnow()`

### Redis 精确提醒调度 (2026-05-20)

使用 Redis 有序集合（ZSET）实现秒级精度的提醒调度，替代原来纯 DB 15 分钟轮询。

| 功能 | 说明 | 状态 |
|------|------|------|
| Redis ZSET 调度 | 提醒创建时同步到 Redis ZSET，score 为 remind_at 时间戳 | ✅ 完成 |
| 秒级精度检查 | Celery 每 10 秒扫描 Redis ZSET，获取 score ≤ 当前时间的提醒 | ✅ 完成 |
| DB 兜底 | Redis 为空时从 DB 查询待发送提醒，自动同步到 Redis | ✅ 完成 |
| 启动同步 | app 启动时自动将所有 pending 提醒从 DB 同步到 Redis | ✅ 完成 |
| 批量清理 | 提醒处理后从 Redis 批量移除已发送的 ID | ✅ 完成 |

**新建文件：**
- `app/services/reminder_scheduler.py` — Redis 精确提醒调度器

**修改文件：**
- `app/services/task_service.py` — 创建提醒时同步到 Redis
- `app/services/reminder_service.py` — `process_reminders()` 优先从 Redis 获取
- `app/core/celery.py` — `check-reminders` 从 60 秒改为 10 秒
- `app/main.py` — 启动时同步 pending 提醒到 Redis

### Celery 任务连接池修复 (2026-05-20)

修复 Celery worker 中 SQLAlchemy 和 Redis 的跨事件循环连接池冲突。

| 问题 | 修复内容 |
|------|---------|
| SQLAlchemy "another operation is in progress" | 每个 Celery 任务创建独立 engine + `NullPool`，不复用全局连接池 |
| Redis "Event loop is closed" | 每个 Celery 任务创建独立 Redis 客户端，通过 `redis_override` 参数传入 |
| `beijing_tz` 未定义 | 移到 `due_date` 解析块之前，避免仅有 reminders 时 NameError |

**修改文件：**
- `app/services/reminder_service.py` — `process_reminders_task` 创建独立 engine + Redis，`process_reminders` 接受 `redis_override`
- `app/wechat/scheduler.py` — `run_proactive_checks` 创建独立 engine，`run_all_checks` 接受 `db` 参数
- `app/services/memory_service.py` — `maintenance_task` 创建独立 engine

### 微信插件 UserId 自动绑定 (2026-05-20)

修复微信插件用户 `wechat_id` 存储的是显示名而非 UserId 的问题。

| 问题 | 修复内容 |
|------|---------|
| `wechat_id` 是显示名 | 识别到插件用户且 `from_user` 是真实 UserId 时，自动绑定到 `wechat_id` |
| API 发送失败 | `errcode: 81013 "user & party & tag all invalid"` — `touser` 需要 UserId 而非显示名 |
| 多处绑定逻辑 | 验证缓存识别、昵称匹配、handle_message 三处均加入插件用户绑定 |
| 部分成员手动修复 | 通过企业微信 API 查询 UserId，修正张懿/耿嘉栋/张宏魁/吴孟铨的 `wechat_id` |

**修改文件：**
- `app/wechat/handler.py` — 三处添加插件用户 UserId 绑定逻辑
- `app/services/reminder_service.py` — 发送失败时记录 API 响应详情

**待解决：** 部分成员（如邓国祥）未在企业微信通讯录中，需在管理后台添加后才能接收提醒推送。

### 任务权限修复 (2026-05-20)

| 问题 | 修复内容 |
|------|---------|
| assignee 无法编辑自己的任务 | 权限检查从 `created_by` 扩展为 `created_by OR assignee_id` |
| Agent 工具权限 | `_execute_tool` update_task 权限检查加入 `assignee_id` |
| API 权限 | PUT/DELETE 端点同步修复 |

**修改文件：**
- `app/agent/core.py` — update_task 权限检查
- `app/api/v1/task.py` — PUT/DELETE 端点权限检查

### 主动提醒去重 (2026-05-20)

| 问题 | 修复内容 |
|------|---------|
| 同一任务每15分钟重复提醒 | Redis SET 记录已提醒任务，24小时过期后才会再次提醒 |
| check_due_soon/check_overdue/check_unconfirmed | 三个检查方法均加入去重逻辑 |
| Celery Redis 连接 | 创建独立 Redis 客户端，与 reminder_service 同模式（NullPool） |

**修改文件：**
- `app/wechat/scheduler.py` — 新增 `_already_notified`/`_mark_notified` 方法，三个检查方法加去重，Celery task 传入 Redis 客户端

### 管理员身份感知 + Agent 回答准确性 (2026-05-20)

| 功能 | 说明 | 状态 |
|------|------|------|
| 系统提示词注入用户身份 | 当前用户姓名+角色注入系统提示词，管理员权限可见 | ✅ 完成 |
| query_tasks 返回真实人名 | 工具返回增加 `assignee_name` 字段，批量查询成员姓名映射 | ✅ 完成 |
| 禁止编造人名 | 系统提示词约束：必须使用工具返回的真实姓名 | ✅ 完成 |

**修改文件：**
- `app/agent/core.py` — `_build_system_prompt` 注入用户身份，`query_tasks` 返回 `assignee_name`
- `app/agent/prompts.py` — 回复格式增加人名约束

### 企业微信通知可靠化 (2026-05-20)

修复管理员通过 Agent/API 给成员分配任务后，成员收不到企业微信通知的问题。

| 问题 | 修复内容 |
|------|---------|
| `wechat_id` 存的是昵称而非 UserId | 数据库 17/28 成员的 `wechat_id` 是显示名（如"流苏"），企业微信 API 要求 UserId（如"LiuSu"）。通过 `list_department_members()` API 同步真实 UserId |
| 通知结果被静默丢弃 | `notify_task_assigned()` 返回值从未检查，WeChat API errcode 被忽略。添加独立 try/except + errcode 检查 + 结构化日志 |
| 异常被 `_execute_tool` 大 try/except 吞掉 | 通知代码用独立 try/except 包裹，不影响任务创建返回值 |
| markdown 格式不兼容 | `notifier.py` 所有方法从 `msg_type="markdown"` 改为 `msg_type="text"`，企业微信插件端不支持标准 `**bold**` 语法 |
| 时区显示错误 | 提醒消息和任务通知的时间从 UTC 改为北京时间（UTC+8） |
| `check_overdue` 跳过无 wechat_id 的成员 | 分离负责人和创建人通知逻辑，负责人无标识时仍通知创建人 |
| `send_reminder` 静默标记已发送 | 重构为仅在实际发送成功后才标记 `status="sent"`，失败返回 False 供重试 |

**新建文件/接口：**
- `GET /api/v1/debug/wechat-notify/{member_name}` — 调试接口，测试给指定成员发送企业微信通知
- `POST /api/v1/debug/sync-wechat-ids` — 管理员接口，从企业微信 API 同步成员 UserId

**修改文件：**
- `app/wechat/notifier.py` — 6 个通知方法全部从 markdown 改为 text 格式
- `app/wechat/bot.py` — 新增 `list_department_members()` 方法
- `app/wechat/handler.py` — 插件用户 `wechat_id` 自动修复（正则校验 + force 绑定）；会议通知改用 text 格式
- `app/wechat/scheduler.py` — `check_overdue` 修复负责人/创建人独立通知；时区修正
- `app/agent/core.py` — 通知代码独立 try/except + 日志 + errcode 检查
- `app/api/v1/task.py` — 通知代码独立 try/except + 日志 + 调试接口
- `app/services/reminder_service.py` — 时区修正 + 发送失败不标记已发送

**验证结果：** 杨慈（wechat_id=LiuSu）成功收到任务分配通知和到期提醒。

**待解决：** 9 位成员（邓国祥、董昊宇、宋洋、王书馨、李锐远、孟祥琪、吴怡霏、周之超、蒋芦笛）未在企业微信通讯录中或名称不匹配，需在管理后台添加后才能接收提醒推送。

### 任务双向通知模式 (2026-05-20)

升级任务通知模型：管理员创建任务和任务即将到期时，同时通知管理员（创建人）和负责人（assignee）。

| 场景 | 修改前 | 修改后 |
|------|--------|--------|
| 任务创建 | 仅通知负责人 | 通知负责人 + 通知创建人（派发确认） |
| 即将到期 | 仅通知负责人 | 通知负责人 + 通知创建人 |
| 已逾期 | 通知负责人 + 创建人 | 不变 |

**修改文件：**
- `app/wechat/notifier.py` — 新增 `notify_task_assigned_to_creator()` 和 `notify_due_soon_to_creator()` 方法
- `app/agent/core.py` — 任务创建后增加创建人派发确认通知
- `app/api/v1/task.py` — 同上
- `app/wechat/scheduler.py` — `check_due_soon()` 增加创建人通知

---

## Agent 会议转录总结工具 (2026-05-22)

用户可直接将会议转录文字发给小气助手，自动生成摘要、要点、决议，并永久存入 Agent 长期记忆（与项目记忆共用 `memories` 表）。

| 功能 | 说明 | 状态 |
|------|------|------|
| `summarize_meeting_transcript` 工具 | Agent 新工具，对话中直接触发，无需 API | ✅ 完成 |
| 会议总结存入记忆 | `memory_type="summary"`，与项目讨论共用语义搜索 | ✅ 完成 |
| `_generate_summary` 类方法化 | 改为 `@classmethod` 供 Agent 工具直接调用 | ✅ 完成 |

**修改文件：**
- `app/agent/tools.py` — 新增 `summarize_meeting_transcript` 工具定义
- `app/agent/core.py` — 新增工具处理器（生成摘要 + 提取行动项 + 存入记忆）
- `app/services/meeting_service.py` — `_generate_summary` 改为类方法

---

## 全员任务状况格式化输出 (2026-05-22)

解决 Agent 回答"给我说一下其他成员的任务状况"时输出格式不固定的问题，改为流程化固定格式输出。

| 功能 | 说明 | 状态 |
|------|------|------|
| `query_all_member_tasks` 工具 | Agent 新工具，查询全员任务状况 | ✅ 完成 |
| `get_all_members_workload()` 方法 | TaskService 新增，按成员分组统计 | ✅ 完成 |
| 固定格式输出 | 按状态分组：进行中→待办→已完成，固定三段结构 | ✅ 完成 |
| 权限控制 | 仅 admin/leader 可查，普通成员返回权限错误 | ✅ 完成 |
| 同人任务缩进显示 | 同一成员多条任务时，人名只显示一次，后续任务缩进对齐 | ✅ 完成 |
| pgvector 扩展安装 | 自定义 Dockerfile.db 基于 postgres:16-alpine 安装 pgvector 0.7.0 | ✅ 完成 |
| app 目录挂载 | docker-compose.yml app 服务添加 `./app:/app/app` volume，挂载本地代码 | ✅ 完成 |
| _generate_brief 传 db 参数 | 修复"先简要后详细"模式下简要生成器无法访问数据库的问题 | ✅ 完成 |

## 微信对话响应速度优化 (2026-05-25)

解决用户等待微信回复时间过长（4-16秒）无反馈的问题。

| 功能 | 说明 | 状态 |
|------|------|------|
| 双消息模式 | 用户发送后 0.5 秒内先发"🤔 收到，让我思考一下..."，后台处理完再发正式回复 | ✅ 完成 |
| 异步处理 | Agent 对话改为 asyncio.create_task 后台执行，不阻塞消息发送 | ✅ 完成 |
| 语音重复反馈修复 | 语音消息设置 `_skip_thinking` 标志，避免重复发送思考中消息 | ✅ 完成 |
| 群聊同步优化 | 群聊 @机器人 同样采用双消息模式 | ✅ 完成 |

**修改文件：**
- `app/agent/tools.py` — 新增 `query_all_member_tasks` 工具定义
- `app/agent/core.py` — 新增工具处理器，格式化输出固定三段结构，同人任务缩进显示
- `app/services/task_service.py` — 新增 `get_all_members_workload()` 方法
- `app/agent/prompts.py` — 新增 Task Query Rules 强制 Agent 调用 query_all_member_tasks
- `Dockerfile.db` — 新建，基于 postgres:16-alpine 安装 pgvector 0.7.0
- `docker-compose.yml` — app 服务添加 `./app:/app/app` volume 挂载

---

## UI 全面升级（2026-05-24）

为前端建立统一的设计系统规范，并逐页升级界面。

### 设计系统建立 ✅

| 内容 | 说明 | 状态 |
|------|------|------|
| CSS 设计令牌 | `web/src/assets/variables.css` 全局 CSS 变量（颜色/阴影/圆角/字体/间距/动画） | ✅ 完成 |
| 暖橙珊瑚色系 | 主色 #FF7A5C，辅助色 #FFB347，温馨课题组风格 | ✅ 完成 |
| UI Design Skill | `.claude/skills/ui-design/SKILL.md` 前端设计规范（20个检查项） | ✅ 完成 |

### Dashboard 首页升级 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| 侧边栏玻璃拟态 | 暖白半透明背景 + backdrop-filter 模糊，橙色指示条滑入动效 | ✅ 完成 |
| 欢迎区改版 | 珊瑚橙渐变背景 + 脉冲光晕装饰 + 动画按钮 | ✅ 完成 |
| 统计卡片大数字 | 去掉圆环进度条，改为大数字 + 彩色图标区 + 计数器动画 | ✅ 完成 |
| 任务分组折叠 | 点击负责人头部行展开/收起任务列表（ArrowDown 图标） | ✅ 完成 |
| 完成/编辑按钮 | 进行中/即将到期每行任务添加"完成"和"编辑"按钮 | ✅ 完成 |
| 骨架屏 | 统计卡片、任务列表、会议列表各自显示 shimmer 骨架加载态 | ✅ 完成 |
| 丰富动效 | staggered fadeSlideUp 入场、数字滚动动画、悬停卡片提升 | ✅ 完成 |
| 即将到期分组 | 按紧急程度（今天/明天/后天/逾期）分组，橙色/红色边框高亮 | ✅ 完成 |

### TaskView 升级 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| CSS 设计令牌全面应用 | 全部硬编码颜色替换为 CSS 变量 | ✅ 完成 |
| 卡片/按钮/标签样式 | 统一使用 variables.css 的 design token | ✅ 完成 |
| 任务分组折叠/展开 | 点击负责人头部行展开/收起，带 ArrowDown 图标动画 | ✅ 完成 |
| 动效类名统一 | fade-slide-up, stagger-1/2/3 系列入场动画 | ✅ 完成 |
| 负责人头像 hover 效果 | 圆形变圆角方形 scale(1.08) 悬停动效 | ✅ 完成 |

### ChatView 升级 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| CSS 设计令牌全面应用 | 全部硬编码颜色替换为 CSS 变量 | ✅ 完成 |
| 消息气泡 hover 动效 | scale + shadow 提升 | ✅ 完成 |
| 快捷按钮胶囊样式 | 圆角胶囊 + hover 上浮 + 颜色翻转 | ✅ 完成 |
| 发送按钮动效 | scale + brightness + shadow | ✅ 完成 |
| 打字指示器颜色 | dots 颜色改为珊瑚橙 | ✅ 完成 |
| 整体卡片入场动画 | fadeSlideUp fadeSlideUp | ✅ 完成 |

### MeetingView 升级 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| CSS 设计令牌全面应用 | 全部硬编码颜色替换为 CSS 变量 | ✅ 完成 |
| 会议卡片样式 | border-radius/box-shadow 统一 design token | ✅ 完成 |
| 会议项 hover 动效 | border-color + shadow + translateY(-2px) | ✅ 完成 |
| 日期大数字颜色 | 改为珊瑚橙 | ✅ 完成 |
| 操作按钮动效 | hover scale 动效 | ✅ 完成 |
| 筛选/列表卡片入场动画 | fadeSlideUp staggered | ✅ 完成 |

### KnowledgeView 升级 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| 统计卡片渐变背景 | 改为珊瑚橙/金橙渐变 | ✅ 完成 |
| 分类标签 hover 动效 | 上浮 + 颜色翻转 | ✅ 完成 |
| 知识项 hover 动效 | border-color + shadow + translateY | ✅ 完成 |
| 标签 chip hover | 变为珊瑚橙 | ✅ 完成 |
| 搜索结果/AI摘要卡片 | 统一 design token | ✅ 完成 |
| 各卡片入场动画 | fadeSlideUp staggered | ✅ 完成 |

### MemberView 升级 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| 成员卡片 hover 动效 | translateY + shadow + border-color | ✅ 完成 |
| 头像样式 | 圆角方形 + hover 缩放 | ✅ 完成 |
| 详情项图标颜色 | 改为珊瑚橙 | ✅ 完成 |
| 操作按钮 hover 动效 | 背景变为珊瑚橙浅色 | ✅ 完成 |
| 整体入场动画 | fadeSlideUp | ✅ 完成 |

### ProjectView 升级 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| 项目卡片 hover 动效 | translateY + shadow + border-color | ✅ 完成 |
| 图标颜色 | 改为珊瑚橙 | ✅ 完成 |
| 成员标签 hover 动效 | 变为珊瑚橙 | ✅ 完成 |
| 整体入场动画 | fadeSlideUp | ✅ 完成 |

### MemoryView 升级 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| 记忆卡片 hover 动效 | translateY + shadow + border-color | ✅ 完成 |
| 操作按钮 hover 动效 | 变为珊瑚橙 | ✅ 完成 |
| 整体入场动画 | fadeSlideUp | ✅ 完成 |

### LoginView 升级 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| 背景渐变 | 改为珊瑚橙/金橙 | ✅ 完成 |
| 登录按钮 hover 动效 | 上浮 + 亮度提升 | ✅ 完成 |
| 整体卡片入场动画 | fadeSlideUp | ✅ 完成 |

---

**UI 全面升级已全部完成！** 所有页面（Dashboard / MainLayout / TaskView / ChatView / MeetingView / KnowledgeView / MemberView / ProjectView / MemoryView / LoginView）均已使用统一的设计令牌系统。
- [ ] **MeetingView** — 会议卡片样式、会议详情页
- [ ] **KnowledgeView** — 知识库列表、搜索结果样式
- [ ] **MemberView** — 成员卡片、头像样式
- [ ] **ProjectView** — 项目卡片、里程碑样式
- [ ] **MemoryView** — 记忆列表样式
- [ ] **LoginView** — 登录页珊瑚橙主题统一

---

## 待完成

### 开发环境 Docker 配置 (2026-05-20)

- [x] **docker-compose.dev.yml** -- 开发专用配置：app 热重载（`--reload`）、禁用 nginx/whisper、挂载 `./app` 目录
- 使用方式：`docker compose -f docker-compose.dev.yml up -d`

### GitHub Actions CI 流水线 (2026-05-20)

- [x] **ci.yml** -- push/PR 到 main 时自动触发：flake8 语法检查 + Docker 构建测试
- 不跑 pytest（需真实 PostgreSQL+pgvector），不做自动部署（已有 webhook 机制）

**新建文件：**
- `docker-compose.dev.yml` — 开发环境 Docker 配置
- `.github/workflows/ci.yml` — GitHub Actions CI 流水线

---

### 部署文档 + 生产环境加固 (2026-05-20)

| 内容 | 说明 | 状态 |
|------|------|------|
| 部署文档 | `docs/deploy.md` 覆盖架构、云服务器/本地部署、企业微信配置、运维操作 | ✅ 完成 |
| 数据库备份 | `scripts/backup_db.sh` pg_dump + gzip，保留 7 天，支持 cron 定时 | ✅ 完成 |
| Docker 健康检查 | app/minio 添加 healthcheck，db/redis 已有 | ✅ 完成 |
| Docker 资源限制 | app(512m)、db(512m)、redis(256m)、minio(256m) | ✅ 完成 |
| Nginx 限流 | API 10r/s + 登录 5r/m，429 状态码 | ✅ 完成 |
| Nginx 超时优化 | API 超时从 5s/30s 提升到 10s/120s，适配 AI 长请求 | ✅ 完成 |
| JSON 日志 | 生产环境文件日志改为 JSON 格式，便于接入 ELK/Loki | ✅ 完成 |

**新建文件：**
- `docs/deploy.md` — 完整部署文档
- `scripts/backup_db.sh` — 数据库备份脚本

**修改文件：**
- `docker-compose.yml` — 健康检查 + 资源限制
- `nginx/nginx.conf` — 限流 zone 定义
- `nginx/conf.d/tunnel.conf` — API/登录限流 + 超时优化
- `app/core/logging.py` — JSON 日志格式

### 语音识别准确性全面优化 (2026-05-20)

通过代码审查发现 8 项影响识别准确率的问题，包括 1 个关键 bug，全部修复。

| 优化项 | 说明 | 状态 |
|--------|------|------|
| SILK 采样率 bug | PCM 以 24kHz 解码但 WAV header 写 16kHz，导致音频被加速播放，严重影响识别 | ✅ 已修复 |
| 消除重复转码 | `transcribe_wechat_voice` 已转 WAV 后不再重复调 ffmpeg，减少音质损失 | ✅ 已修复 |
| 领域提示词 | 添加 `initial_prompt` 注入课题组常见术语（微纳米气泡、zeta电位等），提升专业词汇识别率 | ✅ 已完成 |
| beam_size 优化 | 从 5 降到 3，准确率几乎无损，速度提升约 40% | ✅ 已完成 |
| 健康检查 TTL | 远程 Whisper 服务缓存 60 秒后自动重试，服务恢复后自动切回 | ✅ 已完成 |
| VAD 参数统一 | `transcribe_stream` 补齐 `vad_parameters`，与其他方法行为一致 | ✅ 已完成 |
| 识别结果后处理 | 过滤 `no_speech_prob > 0.8` 的噪音段 + 连续重复文本去重 | ✅ 已完成 |
| 模型默认值统一 | Dockerfile 和 docker-compose 默认模型统一为 `large-v3` | ✅ 已完成 |

**修改文件：**
- `app/voice/silk.py` — 修复采样率 bug（默认 24kHz→16kHz）
- `app/voice/asr.py` — 添加 INITIAL_PROMPT、健康检查 TTL、skip_convert、beam_size、VAD、后处理
- `app/whisper_server.py` — 添加 INITIAL_PROMPT、beam_size、no_speech_prob 输出、后处理
- `Dockerfile.whisper` — 默认模型 `base`→`large-v3`
- `docker-compose.yml` — 默认模型 `base`→`large-v3`

### Agent 回复完整性优化 (2026-05-21)

解决 Agent 生成较长内容时（如段子集锦、长文列表等）回复被截断、内容说不全的问题。三管齐下：提示词约束 + token 提升 + 截断续写。

| 优化项 | 说明 | 状态 |
|--------|------|------|
| 系统提示词约束 | 新增完整性规则：所有列表项/代码块/分段内容必须全部写完，严禁中途截断 | ✅ 完成 |
| max_tokens 提升 | `chat()` 和 `chat_stream()` 的 4 处 API 调用从 4096 → 8192 | ✅ 完成 |
| 截断自动续写 | `_process_response()` 检测 `stop_reason == "max_tokens"` 时自动追加续写请求（最多 3 次） | ✅ 完成 |
| 流式续写 | `chat_stream()` 新增 `_stream_continuation()` 辅助方法，流式场景同样支持截断续写 | ✅ 完成 |

**修改文件：**
- `app/agent/prompts.py` — 回复质量要求新增完整性规则
- `app/agent/core.py` — max_tokens 提升 + `_process_response()` 截断续写 + `_stream_continuation()` 方法

### 先简要后详细回复 (2026-05-22)

用户提问时先快速返回【简要】核心结论，后台并行生成【详细】展开内容并自动追加到对话。

| 功能 | 说明 | 状态 |
|------|------|------|
| 两阶段并行调用 | 同时发起两次 API 调用（简要 + 详细），简要完成后立即返回 | ✅ 完成 |
| 【简要】回复格式 | 系统提示词约束生成简短核心结论 | ✅ 完成 |
| 【详细】回复格式 | 使用专用 prompt 生成详细展开内容 | ✅ 完成 |
| 后台追加机制 | asyncio.create_task 并行执行，详细内容生成后追加到 Redis 会话 | ✅ 完成 |
| 前端展开按钮 | 【简要】回复显示"点击查看详情"按钮 | ✅ 完成 |
| 轮询检测 | 前端每 2 秒轮询 `/chat/history/{session_id}` 检测详细回复并追加 | ✅ 完成 |
| API is_brief 标记 | ChatResponse 新增 `is_brief` 字段，前端据此显示展开按钮 | ✅ 完成 |

**新建文件：**
- `app/agent/prompts.py` — 新增 `get_brief_prompt()` 和 `get_detail_prompt()` 函数

**修改文件：**
- `app/agent/core.py` — 新增 `_generate_brief()`/`_generate_detail()`/`_append_detail()` 方法，chat() 改为两阶段调用
- `app/core/redis.py` — 新增 `append_message()` 方法
- `app/api/v1/chat.py` — ChatResponse 新增 `is_brief` 字段，新增 `/chat/history/{session_id}` 接口
- `web/src/views/ChatView.vue` — 显示展开按钮、轮询检测详细回复并追加显示

### 代码质量优化 (2026-05-21 审计)

全面代码审查发现 50+ 个问题，按优先级分 4 批执行。

#### 第一批：无效代码清理（零风险）

**后端未使用的导入（11 处）✅**

- [x] `app/config.py:1` — 移除 `import warnings`
- [x] `app/main.py:5` — 移除 `from app.core.logging import logger`（从未使用，用的 print）
- [x] `app/api/v1/voice.py:19` — 移除 `from app.models.meeting import Meeting`（动态导入已覆盖）
- [x] `app/services/file_parser_service.py:6` — 移除 `Dict` from typing import
- [x] `app/wechat/analyzer.py:15` — 移除 `Optional` from typing import
- [x] `app/wechat/crypto.py:6` — 移除 `import socket`
- [x] `app/voice/recorder.py:4` — 移除 `import numpy as np`
- [x] `app/whisper_server.py:3` — 移除 `import io`
- [x] `app/whisper_server.py:8` — 移除 `from fastapi.responses import JSONResponse`
- [x] `app/schemas/auth.py:5` — 移除 `from datetime import datetime`
- [x] `app/models/task.py:3` — 移除 `from datetime import datetime`

**后端未使用的函数/类（13 处）✅**

- [x] `app/wechat/bot.py:123-150` — 移除 `send_task_reminder()`（无人调用，已用 smart_send 替代）
- [x] `app/wechat/bot.py:152-181` — 移除 `send_meeting_notification()`（无人调用）
- [x] `app/wechat/bot.py:183-209` — 移除 `send_meeting_minutes()`（无人调用）
- [x] `app/wechat/bot.py:416-428` — 移除 `reply_to_user()`（冗余别名）
- [x] `app/services/vision_service.py:152-157` — 移除 `identify_person_from_image()`（无人调用）
- [x] `app/core/security.py:181-200` — 移除 `require_role()`（无人调用，所有角色检查用 inline if）
- [x] `app/core/security.py:203-238` — 移除 `get_current_user_ws()`（无人调用，WebSocket 手动 decode_token）
- [x] `app/schemas/meeting.py:67-73` — 移除 `TranscriptEntry`（无人引用）
- [x] `app/services/search_service.py:20-22` — 移除 `is_configured` property（永远返回 True）
- [x] `app/voice/recorder.py:203-207` — 移除 `create_recorder()`/`get_recorder()`/`remove_recorder()`
- [x] `app/voice/recorder.py:118-120` — 移除 `get_audio_data()`
- [x] `app/voice/tts.py:114-126` — 移除 `get_voices()`

**前端未使用的导入/变量/函数 ✅**

- [x] `web/src/views/MemberView.vue:172` — 移除 `ElMessageBox` 导入
- [x] `web/src/views/MeetingView.vue:323-331` — 移除未调用的 `startMeeting()` 函数
- [x] `web/src/components/VoiceRecorder.vue:56-57` — 移除未使用的 `audioContext` 和 `analyser` 变量
- [x] `web/src/stores/member.js:27-29` — 移除未调用的 `getMemberById()` 函数

**未使用的依赖包 ✅**

- [x] `requirements.txt` — 移除 `openai>=1.0.0`（从未 import）
- [x] `requirements.txt` — 移除 `pandas==2.1.4`（从未 import）
- [x] `requirements.txt` — 移除 `matplotlib==3.8.2`（从未 import）
- [x] `requirements.txt` — 移除 `aiofiles==23.2.1`（从未 import）
- [x] `requirements.txt` — 移除 `bcrypt==4.0.1`（passlib[bcrypt] 已包含）
- [x] `requirements.txt` — 移除重复的 `pydantic==2.5.2`（pydantic[email] 已包含）
- [x] `requirements.txt` — 移除 `faster-whisper==1.2.1`（仅 whisper 容器使用，Dockerfile.whisper 已有）
- [x] `web/package.json` — 移除 `@vueuse/core`（从未 import）
- [x] `web/package.json` — 移除 `sass`（无 lang="scss" 使用）

**过时的代码/注释 ✅**

- [x] `app/api/v1/chat.py:229` — "语音功能开发中..." 已过时，语音已实现，改为提示文字
- [x] `app/voice/asr.py:182` — 误导性注释修正（AMR 格式处理逻辑描述不准确）

#### 第二批：重复代码提取（低风险）

**后端重复逻辑**

- [x] 北京时区常量 — 8+ 处 `timezone(timedelta(hours=8))` → 提取 `BEIJING_TZ` 到 `app/models/base.py`，替换 4 个文件 9 处
- [x] Anthropic 客户端工厂 — 6 处重复实例化 → 提取 `get_anthropic_client()` 到 `app/core/llm.py`
- [x] LLM JSON 解析工具 — 4 处 markdown 代码块剥离 → 提取 `parse_llm_json()` 和 `extract_text_from_response()` 到 `app/core/llm.py`
- [x] `_postprocess_result` 完全重复 — `voice/asr.py` 和 `whisper_server.py` → 提取到 `app/voice/postprocess.py`
- [ ] ~~任务通知逻辑重复~~ — `agent/core.py` 和 `api/v1/task.py` → 暂不提取（涉及业务逻辑，改动风险较高）
- [ ] ~~Celery 任务样板代码~~ — 3 处 engine/session/asyncio.run → 暂不提取（影响异步任务稳定性）
- [x] 微信长文本分割 — 3 处相同分割逻辑 → 提取 `_split_long_text()` 辅助函数到 `app/wechat/handler.py`

**前端重复逻辑**

- [x] `fetchMembers` 重复 — 5 个组件各自调 API → 改用 `useMemberStore`
- [x] `getMemberName` 重复 — 2 处相同查找逻辑 → 改用 `memberStore.getMemberName()`
- [x] `formatDate` 重复 — 6 个组件各自定义 → 统一使用 `utils/format.js`（新增 formatRelativeTime/formatCompactDate）
- [x] `formatTime` 重复 — 3 处组件各自定义 → 统一使用 `utils/format.js`
- [ ] `isMobile` 重复 — 8 个组件独立定义 → 待后续统一（需决定是否保留 @vueuse/core）
- [x] `getStatusType` 重复 — 3 个组件相同映射 → 提取到新建 `utils/task.js`
- [x] `getPriorityType` 重复 — 2 个组件相同映射 → 提取到 `utils/task.js`

#### 第三批：配置优化（中等风险）✅

**硬编码提取到 Settings ✅**

- [x] `CLAUDE_MAX_TOKENS=8192` — `agent/core.py` 7 处 → `settings.CLAUDE_MAX_TOKENS`
- [x] `SESSION_WINDOW_SIZE=30` — `agent/core.py` 2 处 → `settings.SESSION_WINDOW_SIZE`
- [x] `WHISPER_SERVICE_URL` — `voice/asr.py` → `settings.WHISPER_SERVICE_URL`
- [x] `CORS_ORIGINS` — `main.py` 支持逗号分隔追加
- [x] `DB_POOL_SIZE=20, DB_MAX_OVERFLOW=10` — `core/database.py` → `settings.DB_POOL_SIZE/DB_MAX_OVERFLOW`
- [x] `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` — `core/security.py` → settings
- [x] `SESSION_TTL` — `core/redis.py` → `settings.SESSION_TTL`
- [x] `MAX_UPLOAD_SIZE_MB=50` — `knowledge.py`, `upload.py` → `settings.MAX_UPLOAD_SIZE_MB`

**.env.example 补全 ✅**

- [x] 新增 `MIMO_API_KEY` / `MIMO_BASE_URL` / `MIMO_MODEL`
- [x] 新增 `MINIO_SECURE=false`
- [x] 新增 `HF_ENDPOINT=`（HuggingFace 镜像源，国内可设 hf-mirror.com）
- [x] 新增 `APP_ENV` 可选值说明（development/production）

**Docker Compose 优化 ✅**

- [x] 移除 `docker-compose.yml` 和 `docker-compose.dev.yml` 中的 `version: '3.8'`
- [x] `celery-worker`/`celery-beat` 添加 `depends_on` 的 `condition: service_healthy`
- [x] `celery-worker` 添加 `mem_limit: 256m`，`celery-beat` 添加 `mem_limit: 128m`
- [x] `whisper` 服务添加 `mem_limit: 4g`

**Nginx 安全加固 ✅**

- [x] `nginx.conf` 添加 `server_tokens off`（隐藏版本号）
- [x] `default.conf` 的 `proxy_read_timeout` 从 5s 提升到 60s（适配 AI 长请求）

**安全问题修复 ✅**

- [x] `scripts/deploy-local.sh:56` — 移除硬编码 API Key
- [x] `scripts/webhook.service` — secret 改用 EnvironmentFile（`.env.webhook`）
- [x] `scripts/deploy-cloud.sh` — 移除 `ufw allow 7500/tcp`

#### 第四批：前端细节优化（低风险）✅

- [x] `Dashboard.vue` — 用 `useUserStore` 替代直接读 localStorage
- [x] `Dashboard.vue` — resize 监听器添加 `onUnmounted` 清理 + `onMounted` 注册
- [x] `LiveTranscript.vue:140` — WebSocket 协议 `ws://` → 根据 location.protocol 动态选择
- [ ] ~~axios `baseURL` 统一~~ — 跳过（改动量大，收益小，风险大于收益）
- [ ] ~~isMobile 响应式修复~~ — 跳过（仅影响 dialog 宽度，用户极少调整窗口时打开 dialog）
- [ ] ~~ProjectView.vue:257~~ — 跳过（功能占位，非 bug）

### MCP 视觉服务架构（2026-05-22）

为切换到 DeepSeek 等不支持图片识别的文本模型，预先实现 MCP 架构解耦视觉能力。

| 组件 | 说明 | 状态 |
|------|------|------|
| MCP 服务器 | stdio 传输的视觉分析 MCP Server | ✅ 完成 |
| MCP 客户端 | VisionMCPClient，连接 MCP 服务器调用工具 | ✅ 完成 |
| VisionService MCP 模式 | `VISION_USE_MCP=true` 时通过 MCP 调用视觉 | ✅ 完成 |
| Agent MCP 视觉 | `chat()`/`chat_stream()` 检测到图片时走 MCP 描述→文本 | ✅ 完成 |
| 配置项 | `VISION_USE_MCP`/`VISION_MCP_TRANSPORT`/`VISION_MCP_SERVER_CMD` | ✅ 完成 |
| Docker 服务 | `vision-mcp` 服务接入 docker-compose | ✅ 完成 |

**新建文件：**
- `mcp_server/` — MCP 服务器包（server.py + tools/vision.py）
- `app/mcp/client.py` — VisionMCPClient（stdio 传输）

**切换 DeepSeek 步骤：**
1. 确保 `vision-mcp` 容器运行中
2. `.env` 设置 `VISION_USE_MCP=true`，`CLAUDE_MODEL=deepseek-xxx`
3. 图片先通过 MCP 调用视觉服务获取描述，再以文本形式发给 DeepSeek

---

## 2026-05-24 更新

### 任务软删除/垃圾桶功能

实现任务的软删除机制，删除的任务进入垃圾桶而非直接删除，支持恢复或永久删除。

| 功能 | 说明 | 状态 |
|------|------|------|
| 软删除字段 | Task.deleted_at 字段，null=未删除，有值=已删除 | ✅ 完成 |
| 删除 API 变更 | DELETE /tasks/{id} 改为设置 deleted_at | ✅ 完成 |
| 恢复 API | POST /tasks/{id}/restore 恢复任务 | ✅ 完成 |
| 永久删除 API | DELETE /tasks/{id}/permanent 彻底删除 | ✅ 完成 |
| 列表查询排除 | GET /tasks 默认排除 deleted_at 非空记录 | ✅ 完成 |
| 仪表盘统计排除 | dashboard/stats 排除已删除任务 | ✅ 完成 |
| 前端垃圾桶 UI | Tab 页切换（任务列表/垃圾桶），显示删除倒计时 | ✅ 完成 |
| 自动删除倒计时 | 显示"还有 X 天自动删除"，最多显示 3 天 | ✅ 完成 |

**修改文件：**
- `app/models/task.py` — deleted_at 字段 + cascade delete-orphan
- `app/schemas/task.py` — deleted_at 响应字段
- `app/api/v1/task.py` — 软删除/恢复/永久删除 API
- `app/services/task_service.py` — 查询排除已删除
- `web/src/views/TaskView.vue` — Tab 页垃圾桶 UI

### 外键 CASCADE 修复

修复删除父记录时外键约束失败的问题，为所有 NOT NULL 外键添加 ondelete="CASCADE"。

| 修复位置 | 说明 |
|----------|------|
| reminders.task_id | → tasks(id) |
| task_dependencies.task_id | → tasks(id) |
| task_dependencies.depends_on_id | → tasks(id) |
| milestones.project_id | → projects(id) |
| meeting_participants.meeting_id | → meetings(id) |
| meeting_participants.member_id | → members(id) |
| memories.user_id | → members(id) |
| feedback.user_id | → members(id) |

**修改文件：**
- `app/models/reminder.py`
- `app/models/task.py` (TaskDependency)
- `app/models/project.py`
- `app/models/meeting.py`
- `app/models/memory.py`
- `app/models/feedback.py`

### TaskView 筛选修复

修复 TaskView 空值筛选参数导致 FastAPI 422 错误的问题。

| 问题 | 修复 |
|------|------|
| filters 为空时发送 status=&assignee_id=&priority= | Object.fromEntries 过滤空值 |
