# MicroBubble Agent - 完善路线图

> 最后更新: **2026-06-04** — 声纹测试修复 + DB 列迁移 + Skills 升级 + 代码质量升级计划

## 📋 目录（按时间倒序）

### 最新完成（2026-06-04）
- [声纹测试修复+DB迁移+Skills升级+升级计划](#声纹测试修复db迁移skills升级升级计划2026-06-04)（VoiceTestDialog AudioContext + meetings 列迁移 + 16 新 Skills + 4轮24任务计划）
- [听会功能路由修复+ProcessingDialog阶段同步](#听会功能路由修复processingdialog阶段同步2026-06-04)（路由冲突 + 阶段不匹配）
- [前端优化+对话持久化+PPT支持](#前端优化对话持久化ppt支持2026-06-047-commit)（7 commit — ECharts 升级 + passive 补丁 + Element Plus 修复 + 对话持久化 + PPT + 重复回复修复）

### 2026-06-03
- [声纹会议系统全面修复](#声纹会议系统全面修复2026-06-038-commit)（8 commit — enrolled API + 参会人 + hangup 后处理 + 反幻觉 + Celery 事件循环）
- [会议模板重构](#会议模板重构2026-06-03-commit-d619f33)（commit `d619f33` — 删独立页 + 内嵌 CRUD）
- [Webhook 性能修复](#webhook-性能修复2026-06-03-commit-7ec6ce0)（commit `7ec6ce0`，0.001s 响应）
- [垃圾桶系统全面修复](#垃圾桶系统全面修复2026-06-034-commit-链)（4 commit 链）
- [项目当前状态速查](#项目当前状态速查2026-06-03)

---

## 声纹测试修复+DB迁移+Skills升级+升级计划（2026-06-04）

### 1. 声纹测试麦克风误报修复

**问题**：王书馨可以正常录入声纹，但测试时显示"麦克风权限被拒绝"，杜同贺手机测试正常。

**根因**：`VoiceTestDialog` 的 `startRecord()` 中，`getUserMedia` 成功后紧接着创建 `AudioContext({ sampleRate: 16000 })` 用于音量可视化。部分手机浏览器（Safari/微信浏览器）的 `AudioContext` 可能处于 `suspended` 状态或不支持指定 `sampleRate`，被外层 catch 兜底捕获后**误报**为"麦克风权限被拒绝"。而 `VoiceprintEnrollDialog` 不需要 `AudioContext`，所以录入正常。

**修复**：
- 分离 `getUserMedia` 和 `AudioContext` 的 try/catch，错误信息精确区分（`NotAllowedError`/`NotFoundError`/其他）
- AudioContext 失败时跳过音量可视化，录音不受影响
- 添加 `webkitAudioContext` 前缀 + `resume()` 处理 suspended 状态
- 录音格式兜底：webm → mp4 → 默认（兼容 Safari）

### 2. meetings 表列迁移

**问题**：创建会议 500 错误，日志报 `column "audio_url" of relation "meetings" does not exist`

**根因**：`Meeting` 模型定义了 `audio_url`/`audio_duration`/`recording_started_at`/`recording_ended_at` 4 列，但数据库 `meetings` 表没有这些列。`Base.metadata.create_all()` 不会给已有表添加新列。

**修复**：手动 ALTER TABLE 添加 4 列。

### 3. Skills 框架升级

从 [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) 下载 16 个新 Skills：

| 技能 | 用途 |
|------|------|
| senior-backend | REST API 设计、数据库优化、认证流程 |
| senior-devops | CI/CD、基础设施自动化、容器化 |
| senior-qa | 单元测试、集成测试、E2E 测试 |
| rag-architect | RAG 流水线设计、向量搜索优化 |
| database-designer | 数据库 schema 设计、迁移规划 |
| performance-profiler | CPU/内存/IO 瓶颈分析 |
| api-design-reviewer | REST API 设计审查 |
| tdd-guide | TDD 红-绿-重构 |
| docker-development | Dockerfile 优化、多阶段构建 |
| llm-cost-optimizer | LLM token 用量优化 |
| migration-architect | 零停机迁移规划 |
| spec-driven-workflow | 先写规格再写代码 |
| codebase-onboarding | 代码库分析、新人上手文档 |
| security-guidance | 安全反模式检测 |
| a11y-audit | WCAG 2.2 无障碍审计 |
| api-test-suite-builder | API 测试生成 |

总计 **37 个 Skills**。

### 4. 代码质量全面升级计划

已完成设计文档和实现计划，待执行：

- **设计文档**：`docs/superpowers/specs/2026-06-04-code-quality-upgrade-design.md`
- **实现计划**：`docs/superpowers/plans/2026-06-04-code-quality-upgrade.md`
- **4 轮 24 任务**：API 规范化（任务 1-8）→ 后端测试（9-15）→ 前端拆分（16-19）→ 前端测试（20-24）
- **执行方式**：子代理驱动

---

## 听会功能路由修复+ProcessingDialog阶段同步（2026-06-04）

**问题**：点击"开始听会"后录音正常，但点击"结束听会"后不会触发自动分析。后端返回 405 Method Not Allowed。

**根因分析**：
1. **路由冲突**：`meeting.py` 的 `/meetings/{meeting_id}` 路由先注册，把 `/meetings/start-recording` 当作 `meeting_id = "start-recording"` 匹配，但该路由只接受 GET，所以 POST 返回 405
2. **ProcessingDialog 阶段不匹配**：前端用的是旧版阶段名（`extracting_transcript`、`polishing_transcript` 等），与后端 `ProgressStage`（`downloading_audio`、`transcribing` 等）完全对不上，导致进度条卡住

**修复清单**：

| 文件 | 修复内容 |
|------|----------|
| `app/main.py` | `meeting_recording.router` 注册顺序移到 `meeting.router` 之前 |
| `web/src/components/ProcessingDialog.vue` | 阶段列表改为与后端一致的 6 阶段 |

**关键教训**：
- FastAPI 按注册顺序匹配路由，固定路径必须在参数路径之前注册
- ProcessingDialog 阶段必须与后端 ProgressStage 枚举保持同步

---

## 声纹会议系统全面修复（2026-06-03，8 commit）

**问题**：声纹会议存在多个阻塞性 bug — enrolled API 解析错误导致声纹状态始终为 0、参会人未传递导致"等待发言"、hangup 后 ProcessingDialog 永远卡住、Celery 后处理事件循环冲突、Whisper 幻觉过滤不足。

**修复清单**：

| commit | 修复内容 |
|--------|----------|
| `8460016` | 声纹全链路测试：`POST /api/v1/voiceprint/test` + `VoiceTestDialog` 组件 |
| `cbc503f` | enrolled API 解析（`vpData.members`）+ 参会人自拉取 + avatar schema + startVoiceCreate 自动添加当前用户 |
| `086db70` | hangup 时触发 `post_meeting_process` Celery 任务 |
| `5a3b864` | hangup 后等待服务器关闭 WS 再关对话框 |
| `fddff52` | hangup 后 `watch(connected)` 等 WS 断开再 emit call-ended |
| `63a3e82` | `batch_polisher` 传入 `_live_loop_inner`（修复 NameError） |
| `00b399b` + `1ed628a` + `095938a` | Celery 后处理独立引擎（NullPool）+ 独立 Redis + `new_event_loop` |
| `1659f55` | 反幻觉强化：重复句阈值 3→2 + 低置信度短文本过滤 + 新增黑名单 |
| `87a33b5` | ProcessingDialog 改为 500px 弹窗 |

**关键教训**：
- `sendHangup()` 不能立即 disconnect，要等服务器处理完
- Celery worker 不能复用主 app 的 async_session / Redis 连接池（事件循环冲突）
- `batch_polisher` 等局部变量必须显式传入内部函数

### 2026-06-02 全面热修
- 声纹会议全方位热修（9 commit 链）
- 声纹系统线上修复（9 个 commit）
- KnowledgeView 白屏修复
- 声纹会议 WS 崩溃循环 + L3 优化（6 commit）
- Webhook SSH 拉取改造（5 commit 链）
- 反幻觉七重过滤（36/36 测试）
- A11y 警告彻底清零
- 本地运维三件套
- 文档与 Memory 同步

### 2026-06-01 声纹会议
- wave 3a/3b（声纹库 + 会议模板）
- wave 2a/2b（实时识别 + AI 互动）

### 早期阶段（2026-05-18 ~ 2026-05-31）
- [第六阶段：会议系统智能升级](#第六阶段会议系统智能升级--实时声纹识别-2026-05-29)
- [Knowledge Brain 二次升级](#knowledge-brain-二次升级--实体图谱--假设生成--量化推理-2026-05-27)
- [知识库自主进化](#知识库深层逻辑系统--自主进化知识大脑-2026-05-26)
- [2026-05-27 Bug 修复记录](#2026-05-27-bug-修复记录)
- [2026-05-25 更新](#2026-05-25-更新)
- [2026-05-24 更新](#2026-05-24-更新)
- [UI 全面升级](#ui-全面升级2026-05-24)
- 早期阶段一~五 + 第六阶段（[第一阶段](#第一阶段让系统真正能用关键) 起）

---

## 🟢 项目当前状态速查（2026-06-04）

| 维度 | 状态 | 最近更新 |
|------|------|----------|
| 后端 | Phase 1-6 + 声纹系统 5 修复 + 反幻觉七重过滤 + 垃圾桶系统 4 bug 全修 + PPT 文件解析 + 听会路由修复 + meetings 列迁移 | 2026-06-04 |
| 知识库 | 自主进化知识大脑（实体图谱+假设+量化推理）+ PPT 上传支持 | 2026-06-04 |
| 会议系统 | 录音机+离线后处理模式 + 路由冲突修复 + ProcessingDialog 阶段同步 + 声纹测试修复 | 2026-06-04 |
| 任务管理 | 软删除/垃圾桶 + 3 天后自动清理（1h 调度）+ 精准倒计时双行显示 + 5 级颜色 | 2026-06-03 |
| 前端 | ECharts 5.6.0 + passive 补丁 + Element Plus 废弃修复 + 对话持久化 + 重复回复修复 + VoiceTestDialog 修复 | 2026-06-04 |
| 部署 | 阿里云 Nginx+FRP + 本地 Docker 8 services + SSH 拉取（130s→5s）+ webhook 多线程（0.001s 响应） | 2026-06-03 |
| Webhook 自动部署 | SSH 拉取已端到端验证（commit `cd92ad6`）+ ThreadingHTTPServer 性能修复（commit `7ec6ce0`，0.001s 响应）| 2026-06-03 |
| Skills | 37 个 Skills（21 原有 + 16 新增），覆盖后端/前端/DevOps/测试/安全/RAG/数据库 | 2026-06-04 |
| 升级计划 | 代码质量全面升级 4轮24任务（设计+计划已完成，待执行） | 2026-06-04 |
| 文档 | README/ROADMAP/CLAUDE.md/MEMORY 已同步 | 2026-06-04 |

---

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

---

## 2026-05-25 更新

### 文件对话存入知识库功能

用户上传文件给小气助手后，Agent 回复后追加"存入知识库？"按钮，可一键将文件提取的文本存入公共知识库。

| 功能 | 说明 | 状态 |
|------|------|------|
| 后端 API | `POST /api/v1/knowledge/from-chat`，接收 title 和 content | ✅ 完成 |
| 前端按钮 | AI 回复后显示"📚 存入知识库"按钮 | ✅ 完成 |
| 知识内容传递 | `ChatResponse` 新增 `knowledge_content` 字段返回提取文本 | ✅ 完成 |
| 权限设计 | 知识库公共（所有人可见），长期记忆私有（按 user_id 过滤） | ✅ 确认 |

**修改文件：**
- `app/api/v1/chat.py` — ChatResponse 新增 knowledge_content 字段，chat_with_file 返回提取文本
- `app/api/v1/knowledge.py` — 新增 `/knowledge/from-chat` 端点
- `web/src/views/ChatView.vue` — 消息展示添加存入知识库按钮，saveToKnowledge 函数

### 知识库前端修复

| 问题 | 修复 | 状态 |
|------|------|------|
| 文件上传失败 | 移除手动设置的 `Content-Type: multipart/form-data`，axios 会自动处理 boundary | ✅ 完成 |
| KnowledgeView 弹窗遮挡 | 添加 `height: 100%; overflow-y: auto` | ✅ 完成 |
| ProjectView 弹窗遮挡 | 添加 `height: 100%; overflow-y: auto` | ✅ 完成 |

**修改文件：**
- `web/src/views/KnowledgeView.vue` — 移除错误 header，设置正确 height/overflow
- `web/src/views/ProjectView.vue` — 设置正确 height/overflow
- `web/src/views/ChatView.vue` — 移除 3 处错误 Content-Type 设置

### MinIO 异步上传修复

| 问题 | 修复 | 状态 |
|------|------|------|
| MinIO 同步调用阻塞事件循环 | 使用 `asyncio.to_thread()` 包装同步的 `put_object` 调用 | ✅ 完成 |

**修改文件：**
- `app/services/file_service.py` — upload_file 改为 async，使用 asyncio.to_thread

### 微信思考消息重复修复

| 问题 | 修复 | 状态 |
|------|------|------|
| 语音消息重复发送思考中消息 | 添加 `_skip_thinking` 标志，语音消息识别和非识别路径均设置 | ✅ 完成 |
| 图片消息重复发送思考中消息 | 同上 | ✅ 完成 |

**修改文件：**
- `app/wechat/handler.py` — `_handle_general_chat`/`_handle_group_chat` 检测 `_skip_thinking`，语音/图片处理设置标志

### 移动端侧边栏修复与动画优化 (2026-05-25)

解决移动端侧边栏菜单只显示图标不显示文字的问题（根因为云服务器部署流水线未生效），以及为侧边栏添加动态过渡特效。

| 功能 | 说明 | 状态 |
|------|------|------|
| 独立 div 抽屉方案 | 移动端抽屉改为 el-container 外部独立 div，彻底绕过 Element Plus aside 全局 CSS | ✅ 完成 |
| 桌面端隔离 | `v-if="!isMobile"` 确保桌面端 el-aside 不被移动端代码影响 | ✅ 完成 |
| 遮罩淡入淡出 | opacity 过渡 + backdrop-filter blur 渐变层次 | ✅ 完成 |
| 抽屉弹性滑入 | translateX + cubic-bezier(0.34,1.56,0.64,1) overshoot 回弹 | ✅ 完成 |
| 菜单项弹簧 stagger | scale(0.9→1) + translateX，每个延迟 60ms，关闭时反向退出 | ✅ 完成 |
| 汉堡图标旋转过渡 | Fold↔Expand 带 rotation + scale 过渡动画 | ✅ 完成 |
| 品牌 logo 独立入场 | logo 缩放弹出 + 文字淡入，各自独立延迟 | ✅ 完成 |

**修改文件：**
- `web/src/layouts/MainLayout.vue` — 模板（独立抽屉 + Transition）+ CSS（6 组 @keyframes + transition classes）

### 移动端顶部栏全面优化 (2026-05-25)

优化移动端顶部栏三个问题：汉堡按钮太小、铃铛点击无反馈、头像显示灰色默认图标。

| 功能 | 说明 | 状态 |
|------|------|------|
| 汉堡按钮增大 | 移动端 24px 图标 + 10px padding = 44px 触控区（iOS/Material 标准）| ✅ 完成 |
| 铃铛改为提醒面板 | el-popover 弹窗：显示提醒数 + "全部标为已读"按钮 + "查看我的任务"链接 | ✅ 完成 |
| 头像读取真实 URL | 从 `userStore.userInfo.avatar` 读取真实头像，无则 fallback 默认图标 | ✅ 完成 |
| 移动端 header 紧凑 | padding 12px，gap 8px，铃铛+头像触控区增大 | ✅ 完成 |

**修改文件：**
- `web/src/layouts/MainLayout.vue` — 模板（el-popover + 动态头像 + 移动端 class）+ 脚本（userAvatar + handleMarkAllRead）+ 样式（通知面板 + 移动端适配）

### 任务权限简化 (2026-05-25)

将所有成员的"我的任务"改为"全部任务"，统一可见范围，降低认知负担。

| 改动 | 说明 | 状态 |
|------|------|------|
| 查询条件移除 member_id 过滤 | 所有成员可查看全部任务，不再限制为"自己的任务" | ✅ 完成 |
| 编辑/删除权限保留 | 仅创建人/负责人/管理员可编辑、删除、恢复、永久删除 | ✅ 完成 |
| 错误提示友好化 | REST + Agent 两种路径均返回清晰的中文权限错误信息 | ✅ 完成 |
| 垃圾桶权限同步放开 | 进入垃圾桶的任务对创建人/负责人/管理员可见 | ✅ 完成 |

**修改文件：**
- `app/api/v1/task.py` — tasks GET 移除 member_id 过滤，PUT/DELETE 保留权限检查
- `app/agent/core.py` — `query_tasks` 和 `query_all_member_tasks` 返回全部任务

### 待办与进行中状态统一 (2026-05-25)

todo（待办）和 in_progress（进行中）语义高度重合，统一为"进行中"。

| 改动 | 说明 | 状态 |
|------|------|------|
| 后端模型默认状态 | `TaskStatus.TODO` → `TaskStatus.IN_PROGRESS` | ✅ 完成 |
| Service/API/Agent 默认状态 | 所有新建任务的 status 默认值从 `todo` 改为 `in_progress` | ✅ 完成 |
| AI 工具枚举 | 从允许的状态列表中移除 `todo` | ✅ 完成 |
| Agent 任务汇总 | 将 todo 任务归入 in_progress_list 输出 | ✅ 完成 |
| 统计合并 | todo 和 in_progress 合并计数 | ✅ 完成 |
| WeChat 调度器 | 查询条件增加 todo 兼容（现有 todo 任务仍被检查） | ✅ 完成 |
| 前端状态标签 | `todo: '待办'` → `todo: '进行中'`，UI 显示统一 | ✅ 完成 |
| 前端选项 | Dashboard/TaskView 状态筛选和编辑对话框移除"待办"选项 | ✅ 完成 |
| 取消完成任务 | 反向状态从 `todo` 改为 `in_progress` | ✅ 完成 |

**修改文件（14 个）：**
- `app/models/task.py` — 模型默认值
- `app/services/task_service.py` — 服务层默认值 + 统计
- `app/wechat/handler.py` — 微信创建任务默认值
- `app/services/meeting_service.py` — 会议创建任务默认值
- `app/agent/core.py` — Agent 创建任务默认值 + 统计 + 汇总
- `app/agent/tools.py` — 工具枚举
- `app/wechat/scheduler.py` — 查询条件
- `app/api/v1/task.py` — 统计接口
- `web/src/utils/task.js` — 状态标签
- `web/src/views/Dashboard.vue` — 状态选项 + 反向状态
- `web/src/views/TaskView.vue` — 状态选项 + 反向状态

### Dashboard/TaskView 一致性修复 (2026-05-25)

修复 Dashboard 首页"进行中任务"数量与 TaskView 显示不一致的问题。

| 问题 | 修复 | 状态 |
|------|------|------|
| TaskView 默认 pageSize=20，Dashboard 统计却包含所有任务 | 默认 pageSize 提升至 100，与 Dashboard 统计范围一致 | ✅ 完成 |
| Dashboard 首页"进行中任务"定义不明确 | 统一定义为 `todo + in_progress + blocked`（所有非 done 状态） | ✅ 完成 |

**修改文件：**
- `web/src/views/TaskView.vue` — pageSize 20→100
- `web/src/views/Dashboard.vue` — 进行中任务定义统一

### 个人设置页面 (2026-05-25)

新增个人设置页面，成员可编辑个人信息和上传头像。

| 功能 | 说明 | 状态 |
|------|------|------|
| 个人信息编辑 | 姓名、邮箱、手机号、角色等字段编辑 | ✅ 完成 |
| 头像上传 | MinIO 存储，公网可读 | ✅ 完成 |
| 头像 URL 修复 | 运行时生成新鲜签名，bucket 名称自动补全，nginx 代理访问 | ✅ 完成 |

**新建文件：**
- `web/src/views/SettingsView.vue` — 个人设置页面

**修改文件：**
- `web/src/router/index.js` — 新增 /settings 路由
- `app/services/file_service.py` — 头像上传逻辑
- `app/core/security.py` — 头像 URL 签名生成
- `app/api/v1/member.py` — 成员更新端点

### 云自动部署修复 (2026-05-25)

诊断并修复 Webhook 自动部署流水线的多个问题，端到端验证通过。

| 问题 | 修复 | 状态 |
|------|------|------|
| Webhook 端点不可达 | 云 Nginx 添加 `/webhook` 代理到 `127.0.0.1:9001` | ✅ 完成 |
| deploy-auto.sh 无错误处理 | 添加 `set -e`、磁盘空间检查（500MB）、构建产物验证、nginx -t 预检 | ✅ 完成 |
| 端口冲突（9000 vs MinIO FRP） | webhook 端口从 9000 改为 9001 | ✅ 完成 |
| SSL 证书路径错误 | tunnel.conf 证书路径修正为 `/etc/letsencrypt/live/` | ✅ 完成 |
| Git remote 使用 SSH 无密钥 | 云服务器改用 HTTPS remote | ✅ 完成 |
| 静态资源无缓存头 | JS/CSS 添加 `expires 7d; Cache-Control: public, immutable` | ✅ 完成 |
| .env.webhook 缺失 | 服务器手动创建 + systemd EnvironmentFile 引入 | ✅ 完成 |
| 缺少 tunnel.conf 模板 | 创建 `nginx/conf.d/tunnel.conf`（HTTPS + WebSocket + 缓存 + 安全头） | ✅ 完成 |
| deploy-cloud.sh 缺少 webhook | HTTP 临时配置添加 /webhook 代理 | ✅ 完成 |
| webhook.py 硬编码默认密钥 | 移除默认值，强制从环境变量读取 | ✅ 完成 |

**修改文件：**
- `scripts/deploy-auto.sh` — 全面加固（set -e + 磁盘检查 + 构建验证 + 本地修改丢弃）
- `scripts/webhook.py` — 端口改为 9001 + 移除硬编码默认密钥
- `nginx/conf.d/tunnel.conf` — 新建（HTTPS + /webhook + /api + /ws + /minio + 缓存头 + 安全头）
- `scripts/deploy-cloud.sh` — HTTP 临时配置添加 /webhook 代理 + 缓存头

### 任务排序优化 (2026-05-25)

Dashboard 首页和 TaskView 任务管理中，同一人的任务排序规则优化。

| 改动 | 说明 | 状态 |
|------|------|------|
| Dashboard 排序 | 从 `in_progress` 状态优先 + `created_at` 降序 → 优先级高→中→低 + 截止时间早→晚 | ✅ 完成 |
| TaskView 排序 | 从 `created_at` 降序 → 优先级高→中→低 + 截止时间早→晚 | ✅ 完成 |
| 无截止日期 | 同优先级中无截止日期的排最后 | ✅ 完成 |

**修改文件：**
- `web/src/views/Dashboard.vue` — `fetchInProgressTasks` 排序逻辑
- `web/src/views/TaskView.vue` — `groupTasksByAssignee` 组内排序逻辑

### Webhook 异步部署 (2026-05-25)

修复 GitHub webhook 持续超时（"时间耗尽"）的问题。

| 改动 | 说明 | 状态 |
|------|------|------|
| 同步→异步 | `subprocess.run` 改为 `threading.Thread` 后台执行 | ✅ 完成 |
| 先返回 200 | HTTP 响应立即返回，部署脚本在后台运行 | ✅ 完成 |
| 错误处理 | 后台线程独立 try/except，日志记录超时和异常 | ✅ 完成 |

**修改文件：**
- `scripts/webhook.py` — `do_POST` 先返回 200，部署移入 `_run_deploy` 线程方法

### Dashboard 完成任务 UI 优化 (2026-05-25)

去除任务行前的复选框，统一为一个绿色"✓ 完成"按钮。

| 改动 | 说明 | 状态 |
|------|------|------|
| 去掉复选框 | 进行中和即将到期任务行前的 `el-checkbox` 全部删除 | ✅ 完成 |
| 按钮样式 | 从 `text` 文字按钮改为 `type="success" round` 绿色实心圆角按钮 | ✅ 完成 |
| 清理代码 | 删除不再使用的 `toggleTaskStatus` 函数 | ✅ 完成 |

**修改文件：**
- `web/src/views/Dashboard.vue` — 模板（进行中/即将到期任务）和脚本（删除 toggleTaskStatus）

### 创建任务不填截止日期修复 (2026-05-25)

前端 `due_date` 初始值为空字符串，Pydantic 无法转为 `datetime` 导致 422 错误。

| 改动 | 说明 | 状态 |
|------|------|------|
| Dashboard.vue | `due_date: ''` → `due_date: null`（3 处） | ✅ 完成 |
| TaskView.vue | `due_date: ''` → `due_date: null`（2 处） | ✅ 完成 |

### Dashboard 列表顺序修复 (2026-05-25)

后端 `list_tasks` 添加 `ORDER BY created_at DESC`，Dashboard `page_size` 从 60 提升至 100，确保新创建任务不会排在分页之外。

| 改动 | 说明 | 状态 |
|------|------|------|
| 后端排序 | `app/api/v1/task.py` `list_tasks` 添加 `.order_by(Task.created_at.desc())` | ✅ 完成 |
| 前端 page_size | Dashboard `fetchInProgressTasks` 从 60→100 | ✅ 完成 |

**修改文件：**
- `app/api/v1/task.py` — list_tasks 添加 ORDER BY
- `web/src/views/Dashboard.vue` — page_size 60→100

### 通知面板显示具体提醒内容 (2026-05-25)

铃铛弹窗只显示"您有 N 条待处理提醒"+ "全部标为已读"按钮，看不到具体是什么提醒。新增后端列表接口，改造前端弹窗为提醒列表。

**关键变更：**

| 变更 | 说明 | 状态 |
|------|------|------|
| 后端 GET /reminders | 新增端点返回待处理提醒列表（含 task_title、remind_at），按时间升序，最多 50 条 | ✅ 完成 |
| 前端 userStore | 新增 `notifications` 数组 + `fetchNotifications()` 方法 | ✅ 完成 |
| 前端弹窗面板 | 显示每条提醒的具体内容（任务标题+提醒时间），点击跳转任务管理 | ✅ 完成 |

**修改文件：**
- `app/api/v1/task.py` — 新增 `GET /reminders` 端点
- `web/src/stores/user.js` — 新增 `notifications` ref 和 `fetchNotifications()`
- `web/src/layouts/MainLayout.vue` — 弹窗模板改为通知列表 + 新增 `handlePopoverShow`/`goToTask`/`formatTime`

### 企业微信回复失败 + Dashboard 500 修复 (2026-05-25)

**问题 1：** 企业微信用户（刘莫菲、杜同贺）给机器人发消息后无回复。根因是 `.env` 中 `WECHAT_API_BASE_URL=https://agent.mnb-lab.cn/wechat-api`，该路径在 Nginx 上无代理规则，所有微信 API 请求（gettoken/message/send）打到前端 HTML，JSON 解析失败导致全部微信功能瘫痪。

**问题 2：** `GET /dashboard/stats` 返回 500 错误。根因是 `get_dashboard_stats` 调用了不存在的 `_get_visible_member_ids` 函数。

**关键变更：**

| 变更 | 说明 | 状态 |
|------|------|------|
| WECHAT_API_BASE_URL | 从 `agent.mnb-lab.cn/wechat-api` 改为 `qyapi.weixin.qq.com` 直接调用企业微信官方 API | ✅ 完成 |
| Dashboard 权限过滤 | 移除 `_get_visible_member_ids` 调用，所有用户统一使用软删除过滤 | ✅ 完成 |

**修改文件：**
- `.env` — WECHAT_API_BASE_URL 修正
- `app/api/v1/task.py` — `get_dashboard_stats` 简化权限过滤

### 成员登录修复 (2026-05-25)

刘莫菲无法登录网页端。排查发现 4 位成员（刘莫菲、孟祥琪、吴怡霏、蒋芦笛）的 `password_hash` 为 `None`，均为批量导入时未设置密码导致。

**关键变更：**

| 变更 | 说明 | 状态 |
|------|------|------|
| 密码补全 | 为 4 位无密码成员设置 bcrypt 哈希后的默认密码 `123456` | ✅ 完成 |

**根因：** 成员批量创建时未调用 `get_password_hash()` 设置密码。

### 头像上传 prefix 参数修复 (2026-05-26)

头像上传后无法正常显示。排查发现前端通过 FormData 发送 `prefix=avatars`，但后端 `app/api/v1/upload.py` 使用 `Query("uploads")` 读取该参数——`Query()` 无法从 multipart/form-data 读取值，导致 prefix 静默回退到默认值 `"uploads"`，所有头像文件存到 `uploads/` 而非 `avatars/`。

**关键变更：**

| 变更 | 说明 | 状态 |
|------|------|------|
| Query → Form | `app/api/v1/upload.py` 中 `prefix` 参数从 `Query("uploads")` 改为 `Form("uploads")` | ✅ 完成 |

**修改文件：**
- `app/api/v1/upload.py` — `Query` 改为 `Form`

**验证：** 端到端测试确认：上传 → `avatars/uuid.png` 前缀正确 → 云代理 HTTP 200 → 保存资料写入 DB → `_resolve_avatar_url` 返回公网 URL。

### mnb-lab.cn SSL 证书修复 (2026-05-26)

`https://mnb-lab.cn` 不可访问，报 `SEC_E_WRONG_PRINCIPAL`。云服务器 Let's Encrypt 证书仅覆盖 `agent.mnb-lab.cn`，`mnb-lab.cn` HTTPS 请求落入 `agent.mnb-lab.cn` 的 server block，证书域名不匹配被浏览器拦截。

**修复：**
1. `certbot --expand` 将 `mnb-lab.cn` / `www.mnb-lab.cn` 加入证书
2. nginx 新增 `mnb-lab.cn` 的 HTTP（301→HTTPS）和 HTTPS server block，指向 `/var/www/mnb-lab`

**教训：** 同服务器新增域名 → 必须扩展 SSL 证书 + 添加 nginx server block。

### mnb-lab.cn 内容更新 + 云服务器 OOM (2026-05-26)

`mnb-lab.cn` 网站内容过期，尝试云服务器构建 Next.js 时 2核2G 内存耗尽导致服务器卡死。改为本地 Windows 构建（`npm run build`）→ MinIO 中转 → 云服务器下载部署。

**教训：** 云服务器严禁运行 `npm run build`，所有构建在本地完成后上传静态产物。

### 铃铛通知去重 (2026-05-26)

用户创建 3 个任务，铃铛显示 6 条通知，每个任务出现两次（内容相同但时间不同）。

**根因：** `_create_default_reminders()` 为截止时间 >24h 的任务创建 2 个提醒（提前 2 天 + 提前 2 小时），`GET /reminders` 返回所有 reminder 行，3 任务 × 2 提醒 = 6 条。后端多提醒是合理的调度策略，但通知面板应按任务去重。

**关键变更：**

| 变更 | 说明 | 状态 |
|------|------|------|
| pending-count 去重 | `func.count(Reminder.id)` → `func.count(func.distinct(Reminder.task_id))` | ✅ 完成 |
| reminders 去重 | 新增 `.distinct(Reminder.task_id)` + `ORDER BY task_id, remind_at` | ✅ 完成 |

**修改文件：**
- `app/api/v1/task.py` — 两个查询（第 546、592 行）

**验证：** 耿嘉栋 3 个任务各有 2 个 pending reminder → count=3（非 6），列表每条 task_id 唯一，mark-read 正常归零。

### Nginx ^~ MinIO 修复 (2026-05-26)

**问题：** Nginx 正则 location `~* \.(png|jpg|jpeg|gif)$` 优先级高于 `/minio/` 前缀 location，导致所有通过 `/minio/` 代理访问的头像图片被正则拦截 → 从文档根目录查找静态文件 → 404。

**根因：** Nginx prefix location 默认优先级低于 regex location。请求 `/minio/microbubble/avatars/xxx.jpg` 同时匹配 `/minio/` 前缀和 `\.jpg$` 正则 → 正则胜出 → nginx 尝试从 `root` 提供静态文件。

**修复：** 给 `/minio/` location 添加 `^~` 修饰符（优先前缀匹配，优先级高于 regex）。

**修改文件：**
- `nginx/conf.d/tunnel.conf` — `location /minio/` → `location ^~ /minio/`
- `nginx/conf.d/default-http.conf` — 同上

### MemberView 管理员编辑污染 DB 头像 (2026-05-26)

**问题：** 管理员编辑成员时，`{ ...member }` 展开运算符将 `_resolve_avatar_url()` 解析后的完整 URL 拷贝到表单，保存时将完整 URL（如 `https://agent.mnb-lab.cn/minio/microbubble/avatars/xxx.jpg`）写回 DB，而不是 raw object_name。

**修改文件：**
- `web/src/views/MemberView.vue` — 编辑成员时排除 `avatar` 字段

### SettingsView 头像自动保存 + 手机端上传修复 (2026-05-26)

**问题 1：** 上传头像后需手动点"保存资料"才能持久化，容易遗漏导致刷新后头像丢失。

**修复：** 上传成功后立即调 `PUT /api/v1/auth/profile` 只传 `avatar` 字段，自动持久化。

**问题 2：** 手机端上传头像间歇性失败。根因之一：手动设置 `Content-Type: multipart/form-data` 缺少 `boundary` 参数，手机浏览器更严格导致请求失败。根因之二：HEIC 格式（iPhone 默认拍照格式）Canvas 不支持，`compressImage` 直接报错。

**修复：**
- 删除手动 Content-Type header，让浏览器自动填写正确的 boundary
- Canvas 压缩失败时静默回退，直接用原文件上传
- 优化上传+保存+获取完整 URL 三步骤：拆分为独立 try/catch，任意步骤失败不影响 localStorage 写入，防止网络波动导致刷新后头像回退

**修改文件：**
- `web/src/views/SettingsView.vue` — 4 处改动（自动保存 + HEIC 回退 + 错误拆分 + Content-Type 删除）

---

## 知识库深层逻辑系统 — 自主进化知识大脑 (2026-05-26)

将知识库从"手动喂入的静态文档库"升级为**自主进化的课题组知识大脑**。

### Phase 1: 动态内容分析 + 知识关联 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| 动态 LLM 分析 Prompt | 不再硬编码 `基础/方法/文献/FAQ`，改为 LLM 根据内容自由生成具体方向（如"臭氧气泡消毒动力学"） | ✅ 完成 |
| 模型扩展 | Knowledge 新增 key_concepts、related_topics、knowledge_type、analysis_status、auto_researched、quality_score 6 个字段，category 扩宽至 100 字 | ✅ 完成 |
| 知识关系模型 | KnowledgeRelation 表（source_id/target_id/relation_type/score/reason/created_by），支持 similar/supplements/contradicts/cites/extends/prerequisite | ✅ 完成 |
| 自动关联引擎 | 新入库条目自动与已有条目建关联：pgvector 余弦相似度（>0.65 similar）+ key_concepts 重叠（≥2 supplements）+ related_topics 重叠（≥1 extends），双向写入 | ✅ 完成 |
| 动态分类 API | `GET /knowledge/categories` — 从实际数据 GROUP BY 聚合 | ✅ 完成 |
| 标签云 API | `GET /knowledge/tags` — `unnest(tags)` 频率排序 | ✅ 完成 |
| 知识图谱 API | `GET /knowledge/graph` — BFS 遍历节点+边，支持中心展开和全局视图 | ✅ 完成 |
| 关联知识 API | `GET /knowledge/{id}/related` — 按 relation_type 过滤，score 降序 | ✅ 完成 |
| 增强统计 API | `GET /knowledge/stats/rich` — 类型分布/分析状态/关联数/自动研究数 | ✅ 完成 |

**新建文件：**
- `app/services/knowledge_graph_service.py` — 知识图谱服务（关联发现 + BFS 图谱 + 动态分类 + 标签云 + 统计）
- `alembic/versions/007_knowledge_brain_models.py` — 数据库迁移（6 新列 + 关系表 + 3 个索引）

**修改文件：**
- `app/services/llm_analysis_service.py` — 分析 Prompt 重写（动态分类 + key_concepts + related_topics + knowledge_type）
- `app/models/knowledge.py` — 6 新字段 + KnowledgeRelation 模型
- `app/services/knowledge_service.py` — `_analyze_and_embed` 保存全部新字段 + 分析完成后自动关联
- `app/schemas/knowledge.py` — 新字段 + 5 个新 schema（RelatedKnowledge/GraphNode/GraphEdge/KnowledgeGraph/DynamicCategory/TagCloudItem/KnowledgeStats）
- `app/api/v1/knowledge.py` — 5 个新端点（categories/tags/graph/related/rich-stats）

### Phase 2: RAG 优先问答引擎 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| RAG 合成答案 | 语义搜索 → 阈值分类（高/中/低相关）→ LLM 合成 → 来源引用 | ✅ 完成 |
| 置信度评分 | 基于高相关条目数量判断 high/medium/low | ✅ 完成 |
| 自动研究触发 | 高相关条目 < 2 时自动生成联网搜索查询 | ✅ 完成 |
| 推荐阅读 | 返回相关知识条目 ID 列表 | ✅ 完成 |

**新建文件：**
- `app/services/knowledge_qa_service.py` — RAG 问答引擎（检索 + 阈值 + LLM 合成 + 研究查询生成）

**修改文件：**
- `app/schemas/knowledge.py` — 新增 QASource/QAResponse 结构
- `app/api/v1/knowledge.py` — 新增 `POST /knowledge/qa` 端点

### Phase 3: 自主研究引擎（自我进化核心）✅

| 功能 | 说明 | 状态 |
|------|------|------|
| 联网自动研究 | 对研究查询执行搜索（搜狗+必应）→ 抓取页面 → LLM 提取知识 → 去重 → 入库 → 建立关联 | ✅ 完成 |
| 知识空白检测 | LLM 分析知识库统计 → 识别薄弱领域 → 生成研究查询 → 定向补充 | ✅ 完成 |
| 矛盾检测 | 高分相似条目对 → LLM 判断是否矛盾 → 返回矛盾列表 | ✅ 完成 |
| 重复检测 | 两两计算 pgvector 余弦相似度 > 0.92 → 返回重复对 | ✅ 完成 |
| 过期检测 | 超过 365 天未更新的条目（排除 auto_research） | ✅ 完成 |

**新建文件：**
- `app/services/auto_research_service.py` — 自主研究引擎（研究/空白填充/矛盾检测/重复检测/过期检测）
- `app/services/knowledge_evolution_tasks.py` — Celery 定时任务（每日进化/6h 空白检测/12h 健康检查）

**修改文件：**
- `app/core/celery.py` — 3 个新定时任务 + 自动发现
- `app/schemas/knowledge.py` — 新增 ResearchResultItem/ResearchResponse 结构
- `app/api/v1/knowledge.py` — 6 个新端点（QA/research/gaps/contradictions/duplicates/staleness）

### Phase 4: 动态分类体系 + 知识健康监控 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| 涌现分类 | 从已有 category 聚合 + key_concepts 频率统计 → 分类树+热门概念 | ✅ 完成 |
| 分类建议 | 基于最相似条目的 embedding 余弦相似度建议分类 | ✅ 完成 |
| 主题关联网络 | 分类间概念重叠（Jaccard 相似度）→ 关联网络 | ✅ 完成 |
| 分类报告 | Markdown 格式的动态分类报告生成 | ✅ 完成 |

**新建文件：**
- `app/services/dynamic_taxonomy_service.py` — 动态分类体系（涌现分类/建议/网络/报告）

**修改文件：**
- `app/api/v1/knowledge.py` — 2 个新端点（taxonomy/emerging + taxonomy/network）

### Phase 5: 前端改造 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| 动态标签云 | 从实际数据聚合的可点击研究主题标签云，字号按频率自适应 | ✅ 完成 |
| RAG QA 问答面板 | 替换旧语义搜索，合成答案 + 来源引用 + 置信度 + 研究触发提示 + 快捷问题 | ✅ 完成 |
| 知识详情增强 | 显示 key_concepts/related_topics 分析结果、analysis_status 标签、auto_researched 标记 | ✅ 完成 |
| 关联知识面板 | 知识详情页显示关联条目（relation_type + score + reason），点击跳转 | ✅ 完成 |
| 知识图谱可视化 | ECharts force-directed graph，节点大小=关联数，颜色=分类，悬停显示详情 | ✅ 完成 |
| 动态分类选择器 | 添加/编辑对话框的分类/标签下拉从 API 动态获取 | ✅ 完成 |

**修改文件：**
- `web/src/views/KnowledgeView.vue` — 完整重写（动态标签云 + RAG QA + 关联面板 + 图谱 + 分析结果展示）

### 新增 API 端点汇总

| 端点 | 说明 | 阶段 |
|------|------|------|
| `GET /knowledge/categories` | 动态分类列表（从实际数据聚合） | P1 |
| `GET /knowledge/tags` | 标签云（频率排序） | P1 |
| `GET /knowledge/graph` | 知识图谱（节点+边） | P1 |
| `GET /knowledge/{id}/related` | 关联知识列表 | P1 |
| `GET /knowledge/stats/rich` | 增强统计 | P1 |
| `POST /knowledge/qa` | RAG 知识问答 | P2 |
| `POST /knowledge/research` | 触发自主研究 | P3 |
| `POST /knowledge/research/gaps` | 分析并填充知识空白 | P3 |
| `GET /knowledge/health/contradictions` | 矛盾检测 | P3 |
| `GET /knowledge/health/duplicates` | 重复检测 | P3 |
| `GET /knowledge/health/staleness` | 过期检测 | P3 |
| `GET /knowledge/taxonomy/emerging` | 涌现分类体系 | P4 |
| `GET /knowledge/taxonomy/network` | 主题关联网络 | P4 |

---

## Knowledge Brain 二次升级 — 实体图谱 + 假设生成 + 量化推理 (2026-05-27)

将知识从"文档附属品"升级为**跨文档可查询、可推理、可计算**的课题组知识大脑。

### P0: 实体级知识图谱 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| 跨文档实体融合 | 从文档 entities JSONB 提取 → 精确匹配 → embedding 余弦 ≥0.78 合并 → 新建实体 | ✅ 完成 |
| 共现网络 | 同一文档内的实体对写入 entity_co_occurrence 表，作为图谱边 | ✅ 完成 |
| 实体搜索 | 按 subject/predicate/object/keyword 分页搜索 | ✅ 完成 |
| 实体图谱 API | centered 模式（单实体+邻居）和 global 模式（全部节点+边） | ✅ 完成 |
| 实体详情 | 含来源文档列表（source_knowledge_ids → 文档标题） | ✅ 完成 |
| 每日实体融合 | Celery 定时任务，LLM 批量判定同 predicate 相似实体合并 | ✅ 完成 |
| 前端实体图谱 tab | ECharts 力导向图（节点颜色=predicate 分类，大小=occurrence_count）| ✅ 完成 |
| 前端实体卡片 | subject→predicate→object + condition + 置信度进度条 + 来源数 | ✅ 完成 |

**数据：** 56 个跨文档实体，173 条共现边，从 9 篇文档 54 个文档内三元组融合而来。

**新建文件：**
- `app/models/knowledge_entity.py` — KnowledgeEntity + EntityCoOccurrence 模型
- `app/services/entity_service.py` — 实体融合/搜索/图谱/详情/LLM 合并

**修改文件：**
- `app/models/__init__.py` — 注册新模型
- `app/services/knowledge_service.py` — _analyze_and_embed Step 5 触发实体融合
- `app/api/v1/knowledge.py` — 3 个新端点（entities/list, entities/graph, entities/{id}）
- `app/schemas/knowledge.py` — 4 个新 schema（EntityItem/EntityList/EntityGraph/EntityDetail）
- `app/core/celery.py` — entity-fusion-daily 定时任务
- `app/services/knowledge_evolution_tasks.py` — fuse_entities_task
- `web/src/views/KnowledgeView.vue` — 实体图谱 tab + 搜索 + 卡片 + 弹窗（~300 行）

### P1: 科研假设生成引擎 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| LLM 假设生成 | 收集实体三元组 + 知识空白 + 关系模式 → LLM 生成可验证假设 | ✅ 完成 |
| 假设持久化 | statement + rationale + suggested_experiment + supporting_entity_ids | ✅ 完成 |
| 验证生命周期 | proposed → validated / rejected，记录验证时间 | ✅ 完成 |
| 优先级+标签 | high/medium/low 优先级 + 自由标签 | ✅ 完成 |
| 前端假设 tab | 筛选栏（状态/优先级）+ 生成按钮 + 卡片网格 + 验证/否决操作 | ✅ 完成 |

**新建文件：**
- `app/models/knowledge_hypothesis.py` — KnowledgeHypothesis 模型
- `app/services/hypothesis_service.py` — 假设生成/列表/验证/详情

**修改文件：**
- `app/models/__init__.py` — 注册新模型
- `app/api/v1/knowledge.py` — 4 个新端点（hypotheses POST/GET, hypotheses/{id} GET, hypotheses/{id}/validate）
- `app/schemas/knowledge.py` — 2 个新 schema（HypothesisItem/HypothesisList）
- `web/src/views/KnowledgeView.vue` — 假设 tab（~200 行）

### P3: 公式库增强 ✅

| 功能 | 说明 | 状态 |
|------|------|------|
| FormulaCategory 模型 | 二级分类树（6 大类 24 子分类），支持图标+排序+描述 | ✅ 完成 |
| 知识公式关联分类 | knowledge_formulas 新增 category_id FK + source_type（builtin/extracted）+ is_active | ✅ 完成 |
| 内置公式库 | 32 个微纳米气泡领域公式，覆盖气泡动力学/传质/水质/化学动力学/流体力学/统计分析 | ✅ 完成 |
| 幂等种子数据 | 启动时自动初始化 formula_categories + 内置公式，仅首次执行 | ✅ 完成 |
| 分类树 API | GET /knowledge/formulas/categories — 返回树形结构 + 公式计数 | ✅ 完成 |
| 公式筛选增强 | list_formulas 新增 category_id / source_type 参数，支持按分类+来源组合筛选 | ✅ 完成 |
| domain→category 映射 | 40+ 条模糊匹配规则，LLM 提取公式自动归入正确分类 | ✅ 完成 |
| LaTeX 转换增强 | 希腊字母（σ/μ/θ/δ/λ）+ 上标（²/³）+ sum 符号扩展 | ✅ 完成 |
| LLM 提示词优化 | domain 字段引导使用标准化分类名 | ✅ 完成 |
| 前端分类树 | el-tree-select 替换 domain 下拉，支持搜索+层级展开+公式计数 | ✅ 完成 |
| 来源标签 | 公式列表+计算器显示"内置"（绿色）/ "提取"（灰色）标签 | ✅ 完成 |
| 内置公式去知识链接 | 内置公式无父文档时隐藏"来源: 知识条目 #N"链接 | ✅ 完成 |

**新建文件：**
- `app/models/formula_category.py` — FormulaCategory 模型
- `app/seed/formula_library.py` — 内置公式库种子数据（32 条公式）
- `app/seed/seeder.py` — 幂等种子服务
- `alembic/versions/009_formula_categories.py` — 数据库迁移

**修改文件：**
- `app/models/knowledge_formula.py` — 新增 source_type/category_id/is_active，knowledge_id 改为 nullable
- `app/services/formula_service.py` — 新增 get_categories / _resolve_category_name / 增强 list_formulas
- `app/schemas/knowledge.py` — 新增 FormulaCategoryItem + FormulaItem 增强
- `app/api/v1/knowledge.py` — 新增 formulas/categories 端点 + 增强 list_formulas 参数
- `app/services/llm_analysis_service.py` — 提示词 domain 字段优化
- `web/src/views/KnowledgeView.vue` — 分类树 + 来源标签 + 筛选器
- `app/main.py` — 启动时调用 seed_formula_library

**验证：** API 分类树返回 6 个顶级分类 + 24 子分类 + 32 内置公式 ✅ Young-Laplace 计算 2×0.072/0.00005=2880 Pa ✅

### 新增 API 端点汇总（公式增强）

| 端点 | 说明 | 维度 |
|------|------|------|
| `GET /knowledge/formulas/categories` | 获取公式分类树（含公式计数） | P3 |

### 前端改造

KnowledgeView.vue 从 ~2400 行扩展为 ~2450 行，公式计算 tab 改造：
- **分类树浏览**：el-tree-select 替代 domain 下拉，支持层级展开 + 关键字搜索 + 公式计数显示
- **来源筛选**：el-select 切换 全部/内置公式/文档提取
- **公式卡片增强**：显示来源标签（绿色"内置"/灰色"提取"）+ 分类路径
- **计算器面板增强**：显示分类路径 + 来源标签，内置公式无"来源: 知识条目"链接

**后端总新增：** ~300 行（1 模型 + 1 种子数据 + 1 种子服务 + 1 迁移 + 1 API + schema/service 增强）
**前端总新增：** ~50 行（模板 + 样式 + 方法）
**数据库新增：** 1 张表（formula_categories）+ 3 列（knowledge_formulas.source_type/category_id/is_active）

### Dashboard 布局简化 + Webhook 部署修复 (2026-05-27)

| 功能 | 说明 | 状态 |
|------|------|------|
| Dashboard 移除"即将到期" | 删除统计卡片中的"即将到期"数字、"即将到期任务"列表、"最近会议"列表，简化首页 | ✅ 完成 |
| 前端 dist 未构建修复 | Dashboard.vue 源码已修改但 web/dist/ 未重建，线上仍是旧版。本地 npm run build 后提交 dist | ✅ 完成 |
| Webhook 手动触发 | GitHub 报告"未能连接到主机"，确认 webhook.py 服务正常但网络瞬时不畅，手动模拟签名 POST 触发部署 | ✅ 完成 |

**教训：** 前端源码修改后必须 `npm run build` 并提交 dist。dist 在 `.gitignore` 中，需 `git add -f web/dist/` 强制添加。deploy-auto.sh 依赖 git 已提交的 dist 文件，不在服务器构建。

### 新增 API 端点汇总（二次升级）

| 端点 | 说明 | 维度 |
|------|------|------|
| `GET /knowledge/entities` | 搜索实体（subject/predicate/keyword 过滤） | P0 |
| `GET /knowledge/entities/graph` | 实体图谱（nodes + co-occurrence edges） | P0 |
| `GET /knowledge/entities/{entity_id}` | 实体详情（含来源文档列表） | P0 |
| `POST /knowledge/hypotheses` | 生成科研假设 | P1 |
| `GET /knowledge/hypotheses` | 列出假设（status/priority 过滤） | P1 |
| `GET /knowledge/hypotheses/{id}` | 假设详情（含关联实体） | P1 |
| `POST /knowledge/hypotheses/{id}/validate` | 标记验证结果（validated/rejected） | P1 |
| `GET /knowledge/formulas` | 列出公式（domain/keyword 过滤） | P2 |
| `GET /knowledge/formulas/domains` | 公式领域分布 | P2 |
| `POST /knowledge/formulas/calculate` | 计算公式 | P2 |

### 前端改造

KnowledgeView.vue 从 1890 行单文件扩展为 ~2400 行，使用 `el-tabs` 分为四个 tab 页：
- **知识库** — 原有功能（列表+搜索+RAG QA+图谱+关联+分析结果）
- **实体图谱** — 实体搜索+ECharts 力导向图+实体卡片网格+详情弹窗
- **科研假设** — 筛选栏+生成按钮+假设卡片（状态 badge+验证操作）
- **公式计算** — 双栏布局（公式列表+计算器），变量输入+结果显示+步骤展开

**后端总新增：** ~750 行（3 模型 + 3 服务 + 10 API + 6 schema）
**前端总新增：** ~500 行（3 tab + 方法 + 样式）
**数据库新增：** 4 张表（knowledge_entities, entity_co_occurrence, knowledge_hypotheses, knowledge_formulas）

---

## 2026-05-27 Bug 修复记录

### Nginx 多站点配置被覆盖（mnb-lab.cn 下线）

- **现象**：`mnb-lab.cn` 网站无法访问，Nginx 配置中 `mnb-lab.cn` server block 丢失
- **根因**：`deploy-auto.sh` 每次部署时将 `nginx/conf.d/tunnel.conf` 直接覆盖到 `/etc/nginx/conf.d/default.conf`，但 `tunnel.conf` 只包含 `agent.mnb-lab.cn` 配置，每次部署都清掉同服其他站点
- **修复**：`tunnel.conf` 补回 `mnb-lab.cn` + `www.mnb-lab.cn` 完整 HTTPS server block（SSL 独立证书 `/etc/letsencrypt/live/mnb-lab.cn/`，root `/opt/Micro-Nano-Bubble-Technology-Lab/out`）
- **预防**：CLAUDE.md 新增"修改 tunnel.conf 必须验证两个站点"的注意事项

### 侧边栏导航相对路径导致 422 错误

- **现象**：点击左侧任何导航菜单项都提示"获取知识详情失败"，API 返回 422
- **根因**：`MainLayout.vue` 侧边栏 `el-menu-item :index="route.path"` 使用相对路径（如 `dashboard`），当用户在 `/knowledge` 页面点击其他菜单时，Vue Router 解析为 `/knowledge/dashboard`，误匹配 `/knowledge/:id` 路由，KnowledgeDetailView 被错误挂载，调用 `GET /api/v1/knowledge/dashboard` → 422
- **修复**：
  1. 桌面端 `:index` 改为 `'/' + route.path`（绝对路径）
  2. 移动端 `router.push(path)` 改为 `router.push('/' + path)`
  3. `menuRoutes` 过滤 `r.meta?.icon`，排除 `knowledge/:id` 等详情页路由

### KnowledgeView 缺失 Vue 导入导致白屏

- **现象**：知识库页面完全白屏，Console 报 `ReferenceError: watch is not defined`
- **根因**：`KnowledgeView.vue` 中使用了 `watch()`、`nextTick()`、`onUnmounted()` 但 `import { ref, computed, onMounted } from 'vue'` 未包含这三个 API
- **修复**：补全 import 为 `import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'`

---

## 第六阶段：会议系统智能升级 + 实时声纹识别 (2026-05-29)

- [x] **粘贴文本 AI 分析** — `MeetingAnalysisService` 三阶段流程：检测发言者 → 确认映射 → 全量分析（摘要+要点+决策+发言人统计+自动创建任务）
- [x] **发言者自动检测** — 支持 3 种格式：对话转录（`【张三】`/`张三说`）、结构化摘要（`发言人：张三、李四`）、纯文本 → Claude AI 回退。文档结构标签黑名单过滤
- [x] **标题 AI 自动生成** — 不填标题时 Claude 根据内容自动生成 15 字以内标题
- [x] **3 个新 API 端点** — `POST /meetings/detect-speakers`、`POST /meetings/analyze-text`、`POST /meetings/{id}/speaker-map`、`GET /meetings/{id}/analytics`
- [x] **声纹识别基础设施** — 3D-Speaker ERes2Net (ModelScope) 256 维嵌入 + pgvector 余弦相似度匹配 + silero-vad 语音活动检测
- [x] **实时声纹会议 WebSocket** — `/ws/meeting/{id}/live`：音频流 → VAD → 声纹识别 → ASR → 实时回传发言人标签 + 置信度
- [x] **AI 实时对话** — 通话中呼叫"小气"，Claude 实时回复
- [x] **声纹录入** — `POST /voiceprint/enroll/{member_id}` 上传语音 → 提取嵌入 → 存储到 Member.voice_embedding。Agent `enroll_voice` 工具支持对话触发
- [x] **全屏炫酷通话界面** — 暗蓝黑渐变背景 + 粒子浮动 + 中央大头像 + 涟漪波纹 + 频谱跳动 + 毛玻璃转写面板 + 半透明操作栏
- [x] **AudioWorklet 低延迟采集** — 替代 ScriptProcessor，16kHz 重采样在独立线程完成
- [x] **前端粘贴分析对话框** — 三阶段：输入 → 发言者映射 → 结果展示 + 内联编辑
- [x] **Agent 工具升级** — 新增 `analyze_meeting_transcript`、`enroll_voice` 工具，升级会议分析提示词
- [x] **数据库扩展** — Member: +voice_embedding(Vector 256), +voice_enrolled_at, +voice_sample_count; Meeting: +speaker_mapping(JSON), +speaker_stats(JSON)
- [x] **Docker GPU 支持** — app 容器添加 nvidia GPU device reservation，celery-worker 内存升至 2g
- [x] **Nginx WebSocket 升级** — /api location 添加 Upgrade/Connection 头支持 WebSocket

**新建文件：**
- `app/services/meeting_analysis_service.py` — AI 分析服务（发言者检测 + 结构化分析 + 统计数据 + 标题生成）
- `app/services/voiceprint_service.py` — 声纹录入/识别/匹配服务
- `app/voice/vad.py` — silero-vad 语音活动检测封装
- `app/voice/pipeline.py` — VAD → 声纹 → ASR 实时流水线
- `app/api/v1/voiceprint.py` — 声纹录入 API
- `web/src/components/PasteAnalyzeDialog.vue` — 三阶段粘贴分析对话框
- `web/src/components/SpeakerMappingPanel.vue` — 发言者映射表
- `web/src/components/AnalysisResultPanel.vue` — 分析结果展示+内联编辑
- `web/src/components/MeetingRoom.vue` — 全屏炫酷声纹通话界面
- `web/src/composables/useAudioCapture.js` — AudioWorklet 音频采集

**修改文件（12个）：**
- `app/models/member.py` — +voice_embedding, +voice_enrolled_at, +voice_sample_count
- `app/models/meeting.py` — +speaker_mapping(JSON), +speaker_stats(JSON)
- `app/schemas/meeting.py` — 新请求/响应模型（SpeakerDetectRequest/Response, TranscriptAnalyzeRequest/Response 等）
- `app/api/v1/meeting.py` — 4 个新端点 + 路由重排序 + minutes 404 修复
- `app/api/v1/voice.py` — 新 WebSocket `/ws/meeting/{id}/live` + 动态发言者切换
- `app/services/meeting_service.py` — process_pasted_transcript(), reanalyze_with_speakers(), _link_speakers_to_participants()
- `app/agent/tools.py` — +analyze_meeting_transcript, +enroll_voice
- `app/agent/core.py` — 新工具分发 + 声纹感知会议提示词
- `app/main.py` — 注册 voiceprint 路由
- `web/src/views/MeetingView.vue` — 集成 PasteAnalyzeDialog + MeetingRoom 对话框
- `web/src/components/LiveTranscript.vue` — 发言者选择下拉菜单
- `requirements.txt` — +modelscope, +torch, +torchaudio, +addict, +datasets, +faster-whisper
- `docker-compose.yml` — app 容器 GPU support + celery-worker mem_limit 2g
- `nginx/conf.d/tunnel.conf` — /api location WebSocket 支持

### 垃圾桶系统修复 (2026-05-31)

- [x] **垃圾桶 API 过滤修复** — `include_deleted=true` 时加 `deleted_at IS NOT NULL`，不再混入活跃任务
- [x] **提醒查询过滤已删除任务** — pending-count / mark-read / GET reminders 三个端点加 `Task.deleted_at.is_(None)`
- [x] **自动清理 Celery 任务** — 每 6 小时永久删除垃圾桶中超过 3 天的任务
- [x] **前端倒计时精确化** — 按小时/分钟显示剩余时间，< 12h 红色高亮提醒

### Dashboard 体验优化 (2026-05-31)

- [x] **文案优化** — "您有X项逾期任务" → "团队共有X项逾期任务"，避免对个人的责备感
- [x] **逾期卡片可点击** — 点击「已逾期」统计卡片直接跳转任务列表并自动过滤逾期任务

### 会议系统深度审计 + 全面修复 (2026-05-31)

- [x] **12 个 Bug 一次性修复** — 崩溃级4个（音频管道/db=None/process_meeting_transcript缺失/3D-Speaker任务类型）+ 功能级5个 + 功能缺失3个
- [x] **会议编辑/删除按钮** — 圆形图标按钮+色彩编码+Tooltip，创建/编辑复用同一对话框
- [x] **跳过映射修复** — 空dict不再被误判为"未提供映射"
- [x] **发言者映射增强** — 映射列改为成员下拉选择器，支持手动输入
- [x] **任务负责人选择** — 分析结果中任务负责人列改为成员下拉选择器
- [x] **手动添加发言人** — 阶段2新增按钮，可添加AI未检测到的发言人
- [x] **删除会议修复** — 先清理关联参与者+解除任务外键约束

### ChatView UI 深度升级 (2026-05-31)

- [x] **沉浸式布局** — 去掉外框卡片，渐变背景+毛玻璃顶栏/底栏
- [x] **欢迎页重设计** — 大图标浮动动画+圆环脉冲+胶囊按钮
- [x] **Markdown增强** — marked.js 支持代码块/列表/表格/引用/链接
- [x] **消息气泡** — 用户珊瑚橙渐变+AI白卡阴影

---

## 声纹会议系统 — 第二波（2a）实时识别全流程 (2026-06-01)

把"声纹识别"从"已有"变成"真正在跑"：从 VAD 检测到声纹匹配到未识别弹窗到声波条可视化，全链路贯通。

- [x] **声纹识别真正启用** — `/live` 端点接入 `MeetingPipeline`，声纹嵌入 → pgvector 匹配 → 实时返回 speaker_name
- [x] **声纹录入整合** — `SpeakerUnidentifiedDialog` 弹窗，未识别说话人时弹出候选成员列表，选人后写入 `speaker_mapping`
- [x] **audio_level 推送** — `/live` 端点 0.1s 间隔推送当前 active speaker 的音量级别，前端声波条跳动
- [x] **SpeakerStrip 声波条** — 5 根 CSS 高度条根据 `audioLevels[memberId]` 实时跳动
- [x] **speaker_claim 消息处理** — 前端 `useMeetingRoomWS` 处理 `speaker_claim_ack`，确认后端已写入映射
- [x] **DB 迁移 010** — 补 `members.voice_embedding` 字段（vector(192)）+ `voice_sample_count` 默认 0
- [x] **VAD per-instance** — 移除 VAD 单例，改为 per-pipeline 实例，避免事件循环绑定冲突
- [x] **MeetingPipeline 注入改造** — Pipeline 通过依赖注入接收 VAD/声纹/ASR 实例，支持单测 mock
- [x] **SpeakerUnidentifiedService** — 新增服务：查询未录入声纹的活跃成员 + 提交 speaker_claim 写入映射
- [x] **前端 MeetingRoom 集成** — `audioLevels` ref + `unidentified` ref 接入弹窗与声波条
- [x] **Float32→Int16 转换** — `useAudioCapture` 输出 Float32，WS 协议用 Int16 PCM，转换放在 MeetingRoom 层
- [x] **MeetingRoom onMounted 修复** — 删除重复的 `})`，让 WS 连接 + 音频采集正确包含在 onMounted 内

## 声纹会议系统 — 第二波（2b）实时 AI 互动 + 声音质量 (2026-06-01)

在声纹实时识别全流程基础上，加上"AI 主动介入"能力与"声音质量"工程化。

- [x] **实时 AI 互动（总结 30s / 翻译 / 纪要 / 提问 + TTS）** — 4 个 AI 触发按钮：📝 总结最近 30 秒、🌐 中英翻译、📋 现在总结、🤔 AI 提问，结果通过 Edge-TTS 实时播报
- [x] **声音质量（MinIO opus 音频存档 + 多设备同步）** — 会议关闭时 audio.opus 上传 MinIO，新加入设备自动从 MinIO 同步缺失片段
- [x] **Admin DELETE audio 端点** — `DELETE /admin/meetings/{id}/audio` 清理音频存档（GDPR/隐私合规）
- [x] **Redis 滑窗 + 多设备广播** — `transcript_buffer` 200 条上限 + LTRIM + 24h TTL，Redis pub/sub 跨设备广播 transcript/ai_response/audio_archive 事件
- [x] **db=None 修复 + AI 工具调用工作** — 修复 chat_stream/db 链路，Agent 工具调用 17 个全部走 service 层

## 声纹会议系统 — 第三波（3a）声纹库 + 跨会议关联 (2026-06-01)

在 wave 2b 实时识别基础上，建设"声纹库中心"和"会议间智能关联"两大基础能力。

- [x] **声纹库中心（256 竖条指纹图 + 置信度历史 + 跨会议搜索）** — 新增 `/voiceprint/fingerprints` 返回所有成员 256 维 embedding + 元数据，`/voiceprint/{member_id}/history` 返回该成员置信度历史，`/voiceprint/search` 跨会议搜索发言片段
- [x] **跨会议相似度推荐（pgvector cosine）** — 会议详情页末尾展示 top-3 相关会议卡片（`Meeting.embedding` + pgvector 余弦相似度匹配）
- [x] **5 分钟前会议提醒（企业微信）** — 创建会议时勾选"提前 5 分钟提醒"，自动创建 `Reminder(target_type='meeting')` 记录，Celery 调度器（10 秒精度）触发企业微信通知
- [x] **voice_embedding / meeting.embedding HNSW 索引** — `members.voice_embedding` HNSW 索引（vector_cosine_ops）支持快速匹配，`meetings.embedding` 同上支持跨会议检索
- [x] **DB 迁移 012/013/014/015** — voice_embedding 256 维、meeting.embedding 768 维、reminder.target_type 支持 meeting、reminder.meeting_id 外键
- [x] **3 个新模型** — `Meeting.embedding`/`related_meeting_ids`/`agenda`、`Reminder.target_type`/`meeting_id`、`VoiceprintHistory`（每次识别一行历史）
- [x] **VoiceprintCard 256 竖条冷暖色指纹图** — 冷色（蓝/青）→ 暖色（橙/红）渐变，0.1~1.0 confidence 映射
- [x] **/live 集成历史记录** — 每次声纹识别 → 写一行 `VoiceprintHistory`，支持声纹库中心的置信度历史曲线
- [x] **5 个 REST 端点** — `/voiceprint/fingerprints`、`/voiceprint/{member_id}/history`、`/voiceprint/search`、`/meetings/{id}/related`、`/meetings` 支持 `remind_5min` 参数
- [x] **5 个前端任务** — VoiceprintView 中心 + ConfidenceChart + SpeakerSearch、MeetingDetailView 相关会议推荐、MeetingView 创建会议提醒复选框、router 加 /voiceprint 路由
- [x] **修复 Meeting.VoiceprintHistory mapper 错误** — `app/models/__init__.py` 缺少 `VoiceprintHistory` 导入，导致 SQLAlchemy mapper 初始化失败（500 错误）

- [x] 第三波（3b）：会议模板 + 通话主屏升级 + UX 收尾
  - 会议模板（4 内置：组会/一对一/立项会/自由 + 用户自建 + CRUD）
  - 议程链路：模板 → MeetingCreate → DB → PATCH /agenda → 通话中勾选完成 → MeetingDetailView 展示
  - 通话主屏升级：大头像 + 16 声波条（LiveSpeakerPanel）+ 议程勾选进度（AgendaPanel）+ 5s 轮询发言统计（SpeakerStatsLive）+ 时间轴跳转（TimelineScrubber）
  - 静音全屏遮罩（MuteOverlay）+ 网络状态条（NetworkStatusBar 显式弱网/离线 + pending 块数）
  - 移动端横屏适配（grid 布局 + media query）
  - 修复 activeSpeaker bug（`onTranscript` 加 `speaker_confidence > 0.45` 阈值判断）
  - 修复 agent/core.py agenda 字段错位（错写到 description → 正确字段）
  - MeetingService.create_meeting + schemas 加 agenda 形参，POST /meetings 端点补 agenda 字段
  - 6 个新组件 + useNetworkStatus composable + MeetingTemplatesView 模板管理页面
  - DB 迁移 016：meeting_templates 表 + 4 内置种子（组会/一对一/立项会/自由）

---

## 文档与 Memory 同步（2026-06-02）

集中更新 README / ROADMAP / CLAUDE.md / MEMORY 文件，统一反映当前项目状态（Phase 1-6 + 知识库两次升级 + 声纹会议系统三波 2a/2b/3a/3b），并将 AI 无法自动完成的部分登记到「待做」区。

---

## 本地运维三件套（方案 A 落地，2026-06-02）

按用户「不要过多占用云服务器资源」原则，把所有能在本地做的运维工作搬到本地 Windows，云服务器职责不变但资源占用更低。

### 实施内容

| 脚本 | 作用 | 触发方式 | 资源消耗（本地）|
|------|------|----------|-----------------|
| `scripts/local-watchdog.ps1` | Docker 服务健康监控（app/db/redis/minio/whisper/celery-worker/celery-beat）| 任务计划每 5 分钟 | < 50MB 瞬时 |
| `scripts/local-backup.ps1` | PostgreSQL 每日备份（gzip → `backups/microbubble_YYYYMMDD_HHMMSS.sql.gz`）| 任务计划每日 02:00 | < 100MB 瞬时 |
| `scripts/local-build-verify.ps1` | 前端 dist 校验（`index.html` / `assets/*.js` / `assets/*.css` / 总体积 ≥ 500KB）| 手动（`npm run build` 后）| 0（纯文件检查）|
| `scripts/install-local-ops.bat` | 一键注册 3 个 schtasks（普通用户即可，管理员权限可选）| 用户双击运行 | 0 |

### 技术要点

- **PowerShell 5.1 兼容**（用 `[ordered]@{}`、`2>$null`、`$inputStream` 替代 7+ 专属语法）
- **结构化 JSON 日志**（`logs/watchdog/*.log` / `logs/backup/*.log`）便于 ELK/Loki 接入
- **Edge-TTS 告警**（参考 `.claude/notify.ps1`）— 用 `Microsoft Huihui Desktop` 中文语音
- **告警去重**（watchdog）— 只在"正常 → 异常"状态切换时 TTS 播报，避免每 5 分钟重复吼叫
- **幂等性**（backup）— 重复跑不报错，备份文件按时间戳命名
- **本地优先**（verify）— 校验失败立即 exit 1，绝不推送坏 dist 到 GitHub

### 踩坑教训

- **`$ErrorActionPreference = "Stop"` 会把 docker compose 的 warning（如 `POSTGRES_PASSWORD not set`）当成 Error 抛异常**。PowerShell 脚本必须用 `$ErrorActionPreference = "Continue"`，需要严格检查时用 `if/throw` 显式控制
- **`2>&1` 会让 `$LASTEXITCODE` 被管道最后一节覆盖**。改用 `2>$null` 抑制 stderr 而不污染退出码
- **`$input` 是 PowerShell 自动变量**，手动赋值会冲突。改名 `$inputStream`
- **未批准的 PowerShell 动词**（如 `Speak-Alert`/`Print-Line`）触发 PSScriptAnalyzer 警告。改用 `Send-Alert`/`Write-Line` 等批准动词
- **TTS 在中文系统上可能没有 `Microsoft Huihui Desktop` 语音**。`try { SelectVoice } catch {}` 优雅降级到默认英语

### 验证结果（2026-06-02 03:32 ✅ 全部通过）

| 项 | 验证时间 | 验证方式 | 结果 |
|----|----------|----------|------|
| watchdog 手动跑 | 03:23 / 03:29 | `& local-watchdog.ps1` | ✅ `All services healthy, 7 services` |
| backup 手动跑 | 03:23 / 03:29 | `& local-backup.ps1` | ✅ 生成 `microbubble_20260602_032334.sql.gz` (950K) |
| build-verify 手动跑 | 03:20 | `& local-build-verify.ps1` | ✅ 24 JS / 17 CSS / 2.82MB / 主入口 1165KB |
| **schtasks 注册** | 03:31 | `cmd /c install-local-ops.bat` | ✅ 3 个任务全部 `Ready`（修复了 `^` 续行符 + 单行 if/else 括号嵌套 bug）|
| **schtasks 自动触发** | 03:32 | `schtasks /Run /TN MicrobubbleWatchdog` | ✅ 任务自动跑，日志显示 03:32:25 写入 `All services healthy` |

### 已注册的 Windows 任务计划

| 任务名 | 触发方式 | 下次运行 | 状态 |
|--------|----------|----------|------|
| `MicrobubbleWatchdog` | 每 5 分钟 | 每 5 分钟滚动 | ✅ Ready |
| `MicrobubbleDBBackup` | 每日 02:00 | 2026/6/3 02:00 | ✅ Ready |
| `MicrobubbleBuildVerify` | 手动（`schtasks /Run`）| on-demand | ✅ Ready |

### 当前部署架构（方案 A 后）

- **本地 Windows (32核+GPU)**：8 个 Docker 服务 + 3 个 schtasks 自动化运维 + Edge-TTS 告警
- **阿里云 ECS 2核2G**：仅 Nginx + FRPS + Webhook（保持不变，**0 负载增加**）
- **数据流**：浏览器 → 云 Nginx → FRP 隧道 → 本地 Docker（不变）
- **运维流**：本地 schtasks → 本地 PowerShell 脚本 → 本地 TTS/日志/备份（**全本地**）

---

## 待做：AI 无法自动完成的部分

> 这些操作需要人类介入（密码、凭据、特殊硬件环境），AI 无法在本地沙箱中端到端执行。请在合适时由人工完成。

### 1. SSH 密钥不匹配

- **现象**：本地 `~/.ssh/id_ed25519` 与云服务器（`60.205.93.8`）不匹配
- **AI 限制**：本地无 `sshpass` / `expect` 工具，无法交互式输入密码完成 SSH
- **人工解决路径**：
  1. 将本地 `id_ed25519.pub` 加入服务器的 `~/.ssh/authorized_keys`
  2. 或将服务器密钥导入本地（更安全，避免服务器密钥扩散）
  3. 或安装 `sshpass` / `expect` 让 AI 后续能自动处理
- **影响范围**：所有需要远程命令执行的自动化流程（手动触发 webhook、查看服务器日志等）

### 2. Webhook HMAC 签名无凭据

- **现象**：测试 webhook 收到 `Invalid signature` 错误
- **AI 限制**：本地无 `WEBHOOK_SECRET` 环境变量，无法生成正确的 `X-Hub-Signature-256` HMAC-SHA256 签名
- **人工解决路径**：
  1. 从服务器 `cat /opt/microbubble/.env.webhook` 或 systemd EnvironmentFile 获取 `WEBHOOK_SECRET`
  2. 安全地同步到本地（建议放入 `.env.webhook` 但加入 `.gitignore`，或本地 `.env` 中）
  3. 测试时用：`echo -n '<payload>' | openssl dgst -sha256 -hmac "<SECRET>" | awk '{print "sha256="$2}'` 生成签名
- **影响范围**：本地模拟 GitHub webhook 触发自动部署时无法通过签名校验

### 3. 云服务器资源限制（npm 构建 OOM）

- **现象**：阿里云 2核2G 服务器无法运行 `npm run build`
- **AI 限制**：CLAUDE.md 已明确禁止在云服务器上执行 `npm run build`（Next.js 构建会 OOM 导致 SSH 断开）
- **现状**（已完成部分）：
  - ✅ 所有前端构建在本地 Windows（32核+GPU）完成
  - ✅ `npm run build` 在 `web/` 目录下生成 `dist/`
  - ✅ `git add -f web/dist/` 强制提交 dist（dist 在 `.gitignore` 中）
  - ✅ 服务器 `deploy-auto.sh` 通过 git pull 拉取已提交的 dist 文件
  - ✅ 已在 README「快速开始」明确说明此约束
- **人工解决路径**（若需要云服务器也能构建）：
  1. 升级云服务器配置到至少 4核4G（构建内存峰值约 2-3GB）
  2. 或迁移到 `docs/deploy.md` 第八节所述的高性能单机部署（9950X3D + RTX 5090 32GB + 128GB RAM + 8TB SSD）
- **影响范围**：未来若引入 SSR / 服务端组件或大体积前端框架，仍受此约束

---

## 声纹系统线上修复（2026-06-02 9 个 commit）

继 wave 3b 后线上发现 5 类问题，按 commit 顺序修复：

| Commit | 修复 |
|--------|------|
| `317ab12` | 声纹会议三问题：WS 重连策略健壮化 + 微信 enroll_voice 状态机 + MemberView 加声纹录入入口 |
| `f61432c` | **WS 闪烁真正根因**：`voice.py:_run_live_loop` 函数内冗余 `import asyncio` 触发 UnboundLocalError |
| `3e6b432` | 声纹模型 404（换 ID `_16k-common`）+ 维度 256→192 + 移动端弹窗 + 迁移 017 + 修复 alembic 链断点 |
| `2d1f9ce` | 3D-Speaker pipeline 临时文件传路径 + 固化声纹依赖到 requirements.txt |
| `85ed5ef` | extract_embedding 加 3 层回退（pipeline(路径)→pipeline(numpy)→底层 model） |
| `b76b181` / `ff09baa` / `8dea5d0` | fingerprints API no-cache 头（最终版：`Response` 参数注入，不用 jsonable_encoder）+ get_fingerprints 用 `.tolist()` 转 python float 避免 numpy 序列化崩 |
| `515e203` | 前端 member store `normalizeAvatarUrl` 兜底裸路径 avatar（旧数据 upload.py Query→Form 修复前的脏数据）|
| `7e2ce55` | .gitignore 加 `backups/`（local-backup.ps1 生成的数据库备份不进 git）|
| `8a49b01` | **声纹提取逻辑精修**：`_extract_via_model` 改用 1D tensor（符合 ERes2Net_Pipeline.preprocess 规范）；ConfidenceChart markLine 0.45→0.55 统一前后端阈值；**清空 2 个旧 embedding 让用户重新录入** |

### 关键经验沉淀（已写入 CLAUDE.md）

- 任何函数内的 `import xxx` 都会让 Python 把整个函数的 `xxx` 当局部变量，外部访问会 UnboundLocalError
- FastAPI 默认序列化器**也是**用 `jsonable_encoder`，遇到 numpy 类型会崩
- pgvector SQLAlchemy 读出的是 numpy array，转 list 后元素仍是 numpy.float32
- ModelScope iic 仓库的模型 ID 不稳定，旧 ID 会被新 ID 替换（带 `-common` 后缀）
- 3D-Speaker pipeline 只接受文件路径或 numpy 数组，不接受 bytes
- **3D-Speaker 模型 forward 接收 1D tensor**（不要 `.unsqueeze(0)` 加 batch 维，模型内部自己加）
- 前端 hover 用 `transform` 会创建 containing block，破坏 fixed 定位子元素的渲染
- **ConfidenceChart 里的水平线是 markLine 阈值参考线**（红色虚线 `yAxis`），不是真实数据 — 数据看 `voiceprint_history` 表
- 声纹提取逻辑变更后必须清空旧 DB embedding，让用户重新录入（旧 embedding 是用旧逻辑算的）

---

## 声纹会议全方位热修（2026-06-02，9 commit 链）

一次会话连续修了 9 个生产 bug，按时间倒序：

| Commit | 修复 |
|--------|------|
| `3e1c475` | **A11y daterange 警告**：`el-date-picker type="daterange"` 内部 `<input class="el-range-input">` 没 name（Element Plus 内部渲染，prop 不会传到内部 input）。拆成两个独立 `type="date"` 选择器（`name="...-from"` / `name="...-to"`） |
| `d6ec60b` | 文档同步 |
| `66428c4` | **反幻觉七重过滤**扩展（见下文） |
| `190015f` | **A11y 表单 name**修复：全项目 50+ 个 `el-input/select/textarea/date-picker/checkbox` 加 `name` 属性（5 个 A11y 警告 → 0） |
| `3260bc2` | **Celery worker [tasks] 缺 `post_meeting_process`**（autodiscover `related_name='tasks'` 静默失败 → 显式 `conf.imports` + celery-worker 加 `./app` volume 挂载） |
| `58a4bf2` | 反幻觉**四重过滤** + TimelineScrubber 跳转修复 |
| `9e827a7` | Progress WS snapshot `data=null` 前端崩 |
| `c5ca909` | 声纹会议 live WS 静默断开 + audioLevels 解耦 activeSpeaker |
| `4098d91` | 声纹会议 ASR 幻觉（whisper_server 漏加反幻觉参数） |

### 关键经验沉淀

1. **WS live 静默断开**（`c5ca909`）：`meeting_live_ws` + `_run_live_loop` 必须有**顶层 try/except 兜底**。VAD 加载 / `transcript_history` 发送 / `pubsub.subscribe` / `send_json` 任何异常如果只捕获 `WebSocketDisconnect` 会逃逸到 Uvicorn 静默关闭 WS，**没有错误日志**。验证：改前 1 秒断开，改后 11+ 秒维持
2. **Celery autodiscover `related_name='tasks'` 静默失败**（`3260bc2`）：Celery 5+ 默认 `related_name='tasks'` 会找 `{package}.tasks` 子模块，找不到**静默失败**，`[tasks]` 列表**缺任务**但 worker 启动**不报错**。修复：显式 `celery_app.conf.imports = [...]` + `autodiscover_tasks(related_name=None)`。诊断：`docker logs celery-worker | grep -A 12 "^\[tasks\]$"` 看实际注册列表
3. **Celery 任务失败必须推 progress_update**（`3260bc2`）：`_run_live_loop` 失败时 return error dict 不推 WS，前端永远卡在初始 5 步。修复：失败时在 fail_loop 里 `update_progress(..., status="error")` 推 WS
4. **`audioLevels` 必须解耦 `activeSpeaker`**（`c5ca909`）：之前只在 `activeSpeaker !== null` 时更新 audioLevels，但 activeSpeaker 只在收到 transcript 时才设置。修复：activeSpeaker null 时用 `self` 槽位兜底
5. **Progress WS snapshot 不能发 null**（`9e827a7`）：`get_progress()` 返回 None 时**不发**该消息；前端 `if (msg.data && typeof msg.data === 'object')` 防御性检查
6. **反幻觉必须七重过滤**（`66428c4`）：仅靠 `condition_on_previous_text=False` + `NOISE_PATTERNS` 远远不够。详见上方「Whisper 反幻觉必须三层防护」+「后端七重过滤」条目
7. **TimelineScrubber duration 不能等于 elapsed**（`58a4bf2`）：`meetingDuration = elapsed` 导致 el-slider `max=currentTs` 无法拖动。修复：`meetingDuration = Math.max(MAX_MEETING_DURATION_SEC, elapsed + 60)`
8. **A11y 警告修复双路径**（`190015f` + `3e1c475`）：
   - 普通表单：直接加 `name` 属性（用 Python 脚本跨行扫描 + 按 `v-model` 路径推断 name）
   - **daterange/datetimerange 内部 input 没 name**（Element Plus 已知限制）：拆成两个独立 `type="date"`/`type="datetime"` 选择器

### 完整反幻觉策略（多层防护）

| 层 | 位置 | 修复内容 |
|----|------|----------|
| 1 | `app/whisper_server.py` | `condition_on_previous_text=False` + `no_speech_threshold=0.6` + 过滤 `no_speech_prob > 0.6` 的 segment |
| 2 | `app/voice/asr.py`（本地 fallback） | 同上三件套 |
| 3 | `NOISE_PATTERNS` 黑名单 | 40+ 关键词（明镜与点点/请勿模仿/感谢观看/鲜奶油/锅里/盐巴...） |
| 4 | `_run_live_loop` 7 重过滤 | 短 segment / 短文本 / 字符重复（先去标点）/ 字母数字串 / 乱码启发式 / 句子重复 |

---

## KnowledgeView 白屏修复（2026-06-02 commit `fbffb88`）

线上报 `ReferenceError: chartInstance is not defined`（生产 chunk `KnowledgeView-D0ZcLBJh.js`），路由到 `/knowledge` 切到实体图谱 tab 再离开时 `onUnmounted` 触发崩溃，组件白屏。

- **根因**：`web/src/views/KnowledgeView.vue` 的 `onUnmounted`（原 1083 行）写的是 `chartInstance`，但文件内实际声明的实例变量是 `entityChartInstance`（632 行 `let entityChartInstance = null`，946-970 行 `renderEntityGraph` 中初始化和 `setOption`）。属于闭包内变量名笔误，Vite/Rollup 不会报 undefined 引用错误，运行到 onUnmounted 才崩
- **修复**：onUnmounted 块内 `chartInstance` → `entityChartInstance`（3 处），重新 `npm run build` 提交新 dist
- **经验沉淀**：
  - **变量名笔误也是生产 bug** — `<script setup>` 内任何对未声明标识符的引用，运行到那一行才抛 `ReferenceError`。HMR/esbuild 不会拦下，**只有生产构建 + 触发到对应生命周期才能发现**。任何 `onMounted` / `onUnmounted` / `watch` / `nextTick` 内引用的变量名都要二次核对
  - **同文件多实例变量的命名纪律** — 一旦文件内有 `entityChartInstance` / `meetingChartInstance` / `chartInstance` 多个 echarts 实例，引用前必须打开顶部 `<script setup>` 块确认声明名
  - **CI 防御** — 可在 `web/src/views/**/onUnmounted` 加 lint 规则（eslint-plugin-vue 自定义规则或 `no-undef`），强制 onUnmounted 内引用的变量必须在同文件内声明

## 声纹会议 WS 崩溃循环 + L3 优化（2026-06-02，6 commit）

继三级润色流水线（5 commit）之后的"上线后"修复，按时间倒序：

| Commit | 主题 |
|--------|------|
| `6bc9687` | **WS 崩溃循环根因修复** — BatchPolisher 初始化时访问 `meeting.participants`（lazy relationship）→ async session 触发 sync IO → `sqlalchemy.exc.MissingGreenlet` → WS 关闭 (1011) → 客户端重连 → 服务端又崩 → 循环（用户看到"重连中"永远不停）。修复：传空数组 |
| `e01ffdb` | **L3 3 项优化** — `meeting.key_points` 从 L3 [{text,ts,kind}] 提取纯 text 回写 + `voice.py _broadcast_loop` 订阅 `transcript_polished:{id}` Redis pub/sub 频道（L3 推送给其他设备）+ L3 `_polish_one_chunk` 加 sha1 缓存（24h TTL，重入会话命中）|
| `793d61e` | docs 同步三级润色经验到 CLAUDE.md + memory |
| `3dacea0` | Phase 4+5 前端协议 + UI（useTranscript 状态机 + Tab 切换 + 状态徽章 raw/batch_polished/full_polished + 详情页"AI 精润版转录"section）|
| `8ef1b3b` | Phase 3 L3 全文精润色（alembic 018 加 `transcript_polished` JSON 列 + `meeting_full_polisher.py run_full_polish_pipeline` 分块 + 跨块 context + `prompts/meeting_full_polish.py` L3 专用 prompt 含 `removed` 字段）|

### 关键经验沉淀

7. **async session 中不要访问 lazy relationship**（2026-06-02 教训）— `meeting.participants` / `meeting.related` / `meeting.speaker_stats` 等关系属性在 async session 中**没有**预加载（`selectinload()`）时，访问触发 lazy load → 走同步 IO → `sqlalchemy.exc.MissingGreenlet`。**要么 `await db.refresh(meeting, attribute_names=[...])` 预加载，要么避免访问关系属性**。润色/metadata 上下文**不依赖**关系属性，传空数组/字典即可。**重要 bug 模式**：JS 端"重连中"循环 + 服务端 1011 close code + 完整 traceback 含 `_emit_lazyload` 关键字
8. **SQLAlchemy 异步 lazy load 错误指纹**：`greenlet_spawn has not been called; can't call await_only() here. Was IO attempted in an unexpected place?` + 堆栈含 `strategies.py:1130 _emit_lazyload` → 100% 是这个错
9. **会议上下文 metadata 字段选型**：`meeting_context` / `meeting_metadata` 等**不依赖** lazy 关系。L2/L3 润色需要的 `title` / `participants` / `topic_line` / `context_segments` 应该从已加载字段（`meeting.title` 是 column，**不**触发 lazy load）或显式空值构造

---

---

## 垃圾桶系统全面修复（2026-06-03，4 commit 链）

### 问题
用户报告 5/25 删除的任务到 6/3 仍在垃圾桶中（应 5/28 自动清理），且前端倒计时显示"即将自动删除 / 06-03 03:46 删除"但任务没真正删除。

### 根因（3 个独立 bug + 1 个运维缺陷叠加）

1. **`auto_purge_trash_task` 缺 `@celery_app.task` 装饰器**（commit `dc93bff`）
   - 函数定义是 `async def auto_purge_trash_task():` 但没用 `@celery_app.task` 装饰
   - 验证：`type=function` + `NO NAME` 属性
   - worker 收到任务消息后**找不到**该函数 → 静默丢弃

2. **`celery.py` imports 列表缺 `app.services.task_service`**（commit `dc93bff`）
   - 即便补装饰器，模块不会被 worker 加载
   - 与 2026-06-02 修的 `post_meeting_process` 同类问题（那次修复时漏了本任务）

3. **`celery-beat` 容器缺 `./app:/app/app` volume 挂载**（commit `dc93bff`）
   - 2026-06-02 修复时只给了 `celery-worker`，没给 `celery-beat`
   - beat 容器跑的是构建时烧进镜像的旧代码，新增 schedule 必须 rebuild 25GB 镜像
   - 修复：补 4 个挂载（`./app` + `./data` + `./logs` + `./models/hf_cache`）与 worker 一致

4. **Celery prefork + async session 跨事件循环**（commit `dc93bff`，运行时发现）
   - 一开始用全局 `async_session` 触发 "Future attached to different loop" 错误
   - 改为独立 `create_async_engine(NullPool) + async_sessionmaker`（与 `process_reminders_task` 模式一致）
   - 用 FK `ondelete=CASCADE` 让 DB 自动级联清理 `task_dependencies`（避免访问 lazy relationship 触发 `MissingGreenlet`）

### 调度粒度优化（commit `47fb2c9`）

| 版本 | 调度 | 最大延迟 | retention 3 天时误差 | 用户体验 |
|------|------|----------|----------------------|----------|
| 最初（commit `72d88be`） | 6h | 6h | 8.3% | 用户看到过期但要等 6h 才清理 |
| v1 优化（commit `dc93bff`） | 4h | 4h | 5.5% | 仍会让用户困惑（看到 3.5h 前的"过期"）|
| **v2 优化（commit `47fb2c9`）** | **1h** | **1h** | **1.4%** | **"准点清理"** |

### 前端精准倒计时（commits `b91e429` + `46f04ab` + `47fb2c9`）

- **后端**：`TaskResponse` 新增 `auto_delete_at: Optional[datetime] = None` 字段
  - `list_tasks` / `get_task` 路由用 `setattr` 附加 `deleted_at + settings.TRASH_RETENTION_DAYS`
  - **单一数据源**与 Celery 清理任务共享 `settings.TRASH_RETENTION_DAYS`，不漂移

- **前端** 4 项优化：
  1. 倒计时精度：`< 60min` 精确到分 / `< 24h` X 小时 Y 分 / `>= 24h` X 天 Y 小时
  2. 实时刷新：`setInterval(30s)` 驱动响应式 `now` ref，停留页面不卡住
  3. 5 级颜色分级：imminent/urgent/warning/normal/safe（按剩余小时数）
  4. 双行直接显示：上方相对时间（紧急度颜色）+ 下方绝对时间（具体时刻）
  5. 过期文案：旧"即将自动删除 / 06-03 03:46 删除"误导 → 新"等待下次清理 / 06-03 03:46 到期"明确

- **onUnmounted 缺 import 修复**（与 2026-06-02 KnowledgeView 白屏同源问题）

### 修改文件

- `app/services/task_service.py` — `@celery_app.task` 装饰器 + 独立 NullPool 引擎 + 始终输出日志
- `app/core/celery.py` — `imports` 加 `app.services.task_service` + schedule 4h → 1h
- `app/config.py` — 新增 `TRASH_RETENTION_DAYS: int = 3` 配置
- `app/api/v1/task.py` — 路由附加 `auto_delete_at = deleted_at + retention`
- `app/schemas/task.py` — `TaskResponse` 加 `auto_delete_at` 字段
- `docker-compose.yml` — `celery-beat` 加 `./app` + `./logs` volume 挂载
- `web/src/views/TaskView.vue` — 双行显示 + 5 级颜色 + 实时刷新 + 过期文案

### 验证

- 手动 trigger 第 1 次：🗑️ 永久删除 35 个超过 3 天的过期任务（包含 5/25 那批）
- 手动 trigger 第 2 次：✅ 垃圾桶健康（0 删除，幂等性正确）
- 重启 beat 后 DB 验证：垃圾桶剩余任务数 = 0
- beat 加载新 schedule：`schedule=3600.0`（1h）

### 教训总结

| 类别 | 教训 | 适用 |
|------|------|------|
| Celery 任务添加 | **3 个地方必须同步**：`@task` 装饰器 + `celery.py` imports + **celery-beat 也需 volume 挂载** | 任何新 Celery 任务 |
| Beat 调度粒度 | **要与用户期望对齐**：4h 对 3 天 retention 太粗，1h 才是"准点清理" | 任何时间敏感型清理 |
| Python 模块缓存 | volume 挂载不重载已 import 的模块，**代码改完必须 `docker compose restart worker`** | 任何已 import 模块的修改 |
| async Celery 任务 | 必须独立 `create_async_engine(NullPool)`，**不能用全局 `async_session`** | 任何 async Celery 任务 |
| FK CASCADE 利用 | DB 级 `ondelete="CASCADE"` 已能级联清理，**不要在 async session 中显式遍历 lazy relationship** | 任何关联删除场景 |

---

## Webhook 性能修复（2026-06-03 commit `7ec6ce0`）

### 问题
用户 push `a28d50e` 文档 commit 后，GitHub 报告「**delivery failed: We can't deliver this payload: time out**」。本地 5 次连续 curl `http://agent.mnb-lab.cn:9001/` 验证：

| 次数 | 响应时间 |
|------|----------|
| #1 | 15s |
| #2-5 | 21-22s（线性恶化）|

全部超过 GitHub 10s 超时红线。

### 根因
[scripts/webhook.py:139](scripts/webhook.py#L139) 用 Python `http.server.HTTPServer`（**单线程顺序处理请求**）。即使 `do_POST` 内用 `daemon=True` 启动 deploy 线程（避免单次响应阻塞），**HTTP 请求的接收/响应仍是串行的**。

部署时 git pull 触发 5 次重试 + 75s 指数退避（最坏 200s+），期间所有后续 webhook 健康检查（do_GET）都被 HTTPServer 串行排队 → 全部 10s+ 超时 → GitHub 标记 delivery failed。

### 修复
```python
# 之前
from http.server import HTTPServer, BaseHTTPRequestHandler
server = HTTPServer(("0.0.0.0", PORT), WebhookHandler)

# 之后（2026-06-03）
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
server = ThreadingHTTPServer(("0.0.0.0", PORT), WebhookHandler)
```

每个请求独立线程，do_GET 健康检查与 do_POST deploy 完全不阻塞。

### 验证（用户 SSH 阿里云实测）
```
Webhook #1: 200 0.001232s
Webhook #2: 200 0.000968s
Webhook #3: 200 0.000971s
Webhook #4: 200 0.000973s
Webhook #5: 200 0.001036s
```

对比之前 15-22s 改善 **10000 倍**。

### 重要约束（"鸡生蛋"问题）
修改 `scripts/webhook.py` / `deploy-auto.sh` / `webhook.service` 后，**webhook 服务不会自动重启**（deploy-auto.sh 不在重启列表里 — 否则 deploy 流程会被中断）。需要**手动 SSH 阿里云** `systemctl restart webhook` 才生效。这是 webhook 元部署的本质限制。

### 教训
| 类别 | 教训 | 适用 |
|------|------|------|
| Python `http.server` | **`HTTPServer` 是单线程**，daemon 线程只解决"do_POST 内的耗时"，**不解决"多个 HTTP 请求并发"** | 任何对外服务（webhook / health check / 长任务触发）|
| 部署服务的元部署 | webhook 触发 deploy，但 deploy 不能重启 webhook（会自中断）| 任何"部署触发器"型服务（webhook / CI runner）|
| 响应延迟监控 | 持续 10s+ 响应是 webhook 性能问题的早期信号，应在 `local-watchdog.ps1` 加 `WebhookLatency` 监控项 | 部署健康监控 |

---

## 会议模板重构（2026-06-03 commit `d619f33`）

### 问题
用户反馈：会议模板独立页面（`MeetingTemplatesView.vue`）与会议管理（`MeetingView.vue`）功能重叠，且模板功能不完整：
- 自定义模板的**编辑功能是 stub**（`ElMessageBox.alert('编辑功能见后续 PR')`）
- 字段 `default_participant_ids` 和 `default_location` 写但**前端未使用**
- 用户要管理模板必须**切换页面**，使用流程断裂

### 方案
**合并**：删除独立 `MeetingTemplatesView.vue`（91 行）+ `/meeting-templates` 路由，把模板选择/管理**内嵌到 MeetingView 创建会议对话框顶部**。

### 实施

#### 删除
- `web/src/views/MeetingTemplatesView.vue`（91 行孤立页）
- `web/src/router/index.js` 中 `/meeting-templates` 路由

#### MeetingView 视觉重构
| 之前 | 之后 |
|------|------|
| 隐藏式下拉选择器 | **卡片网格**：4 builtin 卡片 + 自定义模板横向排列 |
| 选中态无视觉反馈 | 选中卡片高亮（珊瑚橙边框 + 微渐变背景）|
| 自定义模板需切页面管理 | **行内 CRUD**（hover 显示编辑/删除图标）|
| 创建模板需切页面 | 右上角"存为新模板"按钮，弹窗填字段 |

#### 字段应用修复
`onTemplateChange` 实际已实现完整字段应用（包括 `default_participant_ids` 和 `default_location`），重命名为 `applyTemplate` 并补充 `ElMessage` 提示。

#### 新增模板编辑对话框
字段：`name` / `title_template` / `description` / `default_duration_minutes` / `default_location` / `default_participant_ids` / `agenda`
- 复用会议表单的 `item-list` 样式（议题增删）
- 复用成员的 `el-select multiple`（默认参与人多选）
- 保存：PUT（编辑）/ POST（创建），自动 reload 列表

#### 细节优化
- 关闭对话框时清理 `templateId` 高亮（避免下次打开误显示选中）
- 自定义模板 hover 显示操作按钮（`.template-card.custom:hover` 触发）
- builtin 模板**没有删除按钮**（数据库 `is_builtin` 标记保护）

### 后端
API 完整，无需改动（CRUD 端点 5 个 + `apply_template_to_meeting_data` 服务函数均已实现）。

### 收益
- 减 **91 行**孤立代码
- 减 1 个路由 + 1 个导航菜单项
- 模板管理贴近使用场景（创建会议时管理，**减少 1 次页面跳转**）
- 编辑功能**真正可用**（之前是 stub）

### 教训
- **功能完整性是产品质量的硬指标**：stub 功能（"见后续 PR"）应该被移除或补全，**不应该留在生产**
- **页面拆分要考虑使用流程**：管理 + 使用的强耦合场景应该靠近（如模板管理贴近模板使用），而不是各自为政
- **视觉化优于隐藏**：下拉菜单隐藏信息，卡片网格让用户**看到**所有可用模板（包括 builtin），更易发现价值

---

## 项目当前状态速查（2026-06-03）

| 维度 | 状态 | 最近更新 |
|------|------|----------|
| 后端 | Phase 1-6 + 声纹系统 5 修复 + 反幻觉七重过滤 + 垃圾桶系统 4 bug 全修 | 2026-06-03 |
| 知识库 | 自主进化知识大脑（实体图谱+假设+量化推理）| 2026-05-27 |
| 会议系统 | 声纹会议 wave 3b + 微信 enroll_voice + 192 维修正 + Celery tasks 修复 | 2026-06-02 |
| 任务管理 | 软删除/垃圾桶 + 3 天后自动清理（1h 调度）+ 精准倒计时双行显示 + 5 级颜色 | 2026-06-03 |
| 部署 | 阿里云 Nginx+FRP + 本地 Docker 8 services + SSH 拉取（130s→5s）+ webhook 多线程（0.001s 响应） | 2026-06-03 |
| Webhook 自动部署 | SSH 拉取已端到端验证（commit `cd92ad6`）+ ThreadingHTTPServer 性能修复（commit `7ec6ce0`，0.001s 响应）| 2026-06-03 |
| 文档 | README/ROADMAP/CLAUDE.md/MEMORY 已同步 | 2026-06-03 |

