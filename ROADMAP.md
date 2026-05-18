# MicroBubble Agent - 完善路线图

> 最后更新: 2026-05-18 (更新：部署架构调整为云服务器+本地电脑 FRP 穿透方案)

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
- [x] **会议创建群聊通知** -- Agent 创建会议后自动推送通知到配置的群聊（`WECHAT_NOTIFY_CHAT_ID`），包含主题/时间/地点/参会人/会议链接
- [x] **CLAUDE_MODEL 可配置** -- 新增 `CLAUDE_MODEL` 配置项，analyzer 和 summary 统一使用，兼容 mimo-v2.5 ThinkingBlock 响应

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
| 图片识别 | Claude Vision 分析图片消息，支持任务截图和人物识别 | ✅ 代码完成 |

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
| 会议创建群聊通知 | Agent 创建会议后自动推送通知到配置的群聊，含主题/时间/地点/参会人/链接 | ✅ 完成 |
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
- `app/agent/core.py` — 会议创建后异步推送群聊通知，新增 logging
- `app/wechat/analyzer.py` — 模型改为 `settings.CLAUDE_MODEL`，兼容 ThinkingBlock 响应
- `app/config.py` — 新增 `CLAUDE_MODEL`、`WECHAT_NOTIFY_CHAT_ID`

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

### 后续优化（低优先级）

- [ ] 创建 `docker-compose.dev.yml`（README 中已引用但不存在）
- [ ] 创建 CI/CD 流水线（GitHub Actions）
- [ ] 编写部署文档（`docs/deploy.md`）
- [ ] 生产环境加固：日志轮转、监控、备份脚本

### 企业微信部署

- [x] 修复 `handler.py:259` 运行时 bug（改为 `wechat_bot.send_meeting_notification()`）
- [x] 内存状态（`_pending_users` / `_group_buffers`）迁移到 Redis（自动过期）
- [x] 异常处理改用结构化日志（`logging.getLogger("microbubble.wechat")`）
- [x] @提及检测改为匹配企业微信实际格式（` @` 分隔符 + AgentID 匹配）
- [x] Nginx 已满足 5 秒超时（异步 `asyncio.create_task` + 立即返回 success）

### 微信互通部署（普通微信用户支持）

- [ ] 企业微信管理后台创建机器人专属成员账号（如 `xiaoqi`）
- [ ] 开通「客户联系」→ 将 `xiaoqi` 加入可使用范围
- [ ] 创建「联系我」二维码（单人模式，选 `xiaoqi`）
- [ ] 配置回调：勾选客户联系相关事件（`change_external_contact`、`change_external_chat`）
- [ ] `.env` 配置 `WECHAT_EXTERNAL_SENDER=xiaoqi`
- [ ] 运行数据库迁移：`alembic upgrade head`
- [ ] 用普通微信扫码添加「小气」，测试私聊消息收发
- [ ] 创建外部群，拉「小气」进群，测试群聊消息收发
- [ ] 从日志获取群聊 `wr...` chat_id：`docker compose logs app | grep chat_id`
- [ ] `.env` 配置 `WECHAT_NOTIFY_CHAT_ID=<wr...群聊ID>`（会议通知自动推送到该群）

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
