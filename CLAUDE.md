# MicroBubble Agent - 项目上下文

## 项目简介

"小气" - 微纳米气泡课题组智能Agent系统，约20人研究实验室的AI助手。

- 后端: Python 3.11 + FastAPI + SQLAlchemy + PostgreSQL + Redis + Celery
- 前端: Vue 3 + Vite + Element Plus（原版 `web/`，极简版 `web-minimal/`）
- AI: Claude API (Sonnet) + faster-whisper + pgvector
- 部署: 云服务器 (Nginx + FRP 服务端) + 本地电脑 (Docker 8 services + GPU Whisper)，通过 FRP 隧道连接。也支持单机部署，详见 `docs/deploy.md` 服务器迁移章节

## 当前开发阶段

**Phase 1-6 全部完成 + v2/v3/v4 全栈架构重构收官 + 移动端 10 个 PR 全栈定制收官。** 知识库已升级为**自主进化的课题组知识大脑**。会议系统已重构为**录音机 + 离线后处理模式**。**小气助手后端 Agent 架构**：从 1 个 1469 行单文件（`app/agent/core.py`）拆为 7 个职责清晰模块 + 13 个按业务域拆分的 tools/ 文件，**34 个工具全部走 `@tool` 装饰器 + Pydantic 校验**。前端用 ChatViewSSE.vue 接入真实 SSE 流式 + 12 类 Rich Block 组件 + 多会话侧栏 + dark mode + ASR/TTS 完整语音链路 + 代码高亮。**移动端**采用 NutUI 4 + Element Plus **路由级双栈**架构（`useIsMobile.js` 判定 + `resolveMobile.js` 路由适配），**18 个移动端页面 + 12 个移动端组件 + 4 个 PWA 离线策略**全部交付，**iOS Safari + Android Chrome 全兼容**。**当前状态（2026-06-13 收官后，commit `9026c07`）**：
- **43 commits 累计**（v1 修复 + v2 6 + v3 5 + v4 6 + 文档 2 + 深夜收尾 4 + 多会话并行 2 + 移动端 PR #1-10 共 10 + 文档/webhint 5 + 部署加固 1）
- **160+ 测试全过**（87 后端 + 73 前端 + 21 录音断网防御 + 2 移动端组件）
- **965 次提交 / 138K 行代码 / 617 文件 / 29 开发天数**（`app/stats.json` 由本地 Python 准确计算；之前的 webhook 统计包含 .meta/.log/.wav 等非源代码已剔除）
- **140 项待做清单**已整合到 README.md（107 项老 + 33 项 v4 收官遗留），移动端 10 PR 完成后清单大幅缩短

**v2/v3/v4 关键成果**：
- **34 个 `@tool` 装饰器工具**（覆盖任务 5 / 会议 7 / 项目 3 / 成员 2 / 知识 9 / 公式 1 / 假设 1 / 记忆 3 / 搜索 1 / 个性化 2 / 反馈 1 — 含 16 个 v2+v3 新工具）
- **12 类 Rich Block 组件**（meeting / task_list / knowledge_ref / member / formula / hypothesis / project / transcript / chart + 2 兜底）
- **真实 SSE 流式**（`/chat/stream`）替代伪流式 2s 轮询
- **10 字段响应**（content + session_id + file_url + file_name + knowledge_content + is_brief + **rich_blocks + tool_trace + usage + duration_ms**）
- **多会话侧栏**（Pinia + localStorage + 兼容 v1 单会话迁移）
- **dark mode**（CSS 变量化 + 顶栏 toggle + 主题持久化）
- **agent_traces 可观测性闭环**（Celery 异步写表 + `/admin/agent-traces` 端点 + `AgentTracesView` 管理页）
- **ASR 语音完整链路**（点 🎤 → 录音 → ASR 文字 → 自动发 + 🔊 TTS 播放）
- **代码高亮**（highlight.js + 6 种语言：python / js / bash / json / sql / yaml）
- **性能基线**（`tests/perf/` 6 测试：brief<3s / SSE<1s / tool<5ms）
- **质量评估体系**（LLM-as-judge + RAG 召回率 + 20 问标注 + 5 消融）
- **`core.py` 清理**：1469 → 689 行（-53%，原 794 行 elif 链替换为 14 行薄壳调 `dispatch_tool`）

详见 [ROADMAP.md](ROADMAP.md#v2v3v4-全栈架构重构2026-06-12-收官17-commits) 和 [README.md](README.md#近期新增按时间倒序)。

## 会议纪要标准格式（2026-06-06 硬规则）

后续所有会议 AI 分析、手动优化会议内容、历史会议补写，都必须按 `2026.5.28 例行例会` 的信息密度输出，不能只生成短摘要。完整规范见 `docs/meeting-minutes-standard.md`。

- **摘要**：3-6 句，必须包含会议背景、讨论过程、关键人物观点、结论和后续方向。
- **讨论要点**：`key_points` 必须使用 `【发言人】内容` 格式；短会议也至少提取 3 条，信息充足时 5-8 条。
- **决议事项**：`decisions` 必须使用 `【发言人/双方/全组】内容` 格式，写清楚决定/共识和后续用途。
- **原始转录保护**：不改 `transcript` 原始转录，只优化 `transcript_polished`、`summary`、`key_points`、`decisions`。
- **禁止误认**：声纹无法确认时使用 `发言人A/B`，不要为了完整性强行猜姓名。

## 前端设计系统

**CSS 设计令牌**：`web/src/assets/variables.css`，暖橙珊瑚色系，可复用于所有页面。

主要变量：
- `--color-primary: #FF7A5C`（珊瑚橙）
- `--color-accent: #FFB347`（金橙）
- 阴影层级：`--shadow-sm/md/lg/primary`
- 圆角规范：`--radius-sm(4px)/md(8px)/lg(12px)/xl(16px)`
- 动画时长：`--duration-fast(150ms)/normal(200ms)/slow(300ms)/counter(500ms)`

动画规范：使用 `fadeSlideUp`/`slideDownFade` 入场动画类，stagger 延迟 `.stagger-1` ~ `.stagger-6`。

设计规范文档：`.claude/skills/ui-design/SKILL.md`（20项 UI 升级检查清单）

## 关键架构决策

- Agent 工具调用通过 `app/agent/core.py` 的 `_execute_tool` 方法路由到 service 层（17 个工具已全部接入）
- `chat()` 和 `chat_stream()` 接收 `db: AsyncSession` 参数，由 API 路由通过 `Depends(get_db)` 传入
- 使用 `AsyncAnthropic` 客户端，不阻塞事件循环
- **Agent 回复采用"先简要后详细"双层结构** — 两阶段并行调用，简要立即返回，详细后台追加
- **MCP 视觉服务架构** — 预写架构，切换 DeepSeek 等文本模型时支持图片识别
- 认证使用 JWT，`app/core/security.py` 已实现，31 个端点全部接入 `get_current_user`
- 会话存储已迁移到 Redis（`RedisSessionStore`，24 小时 TTL）
- 知识库使用 pgvector 做向量搜索（扩展已在 main.py 启动时自动安装，已接入 text2vec-base-chinese 真实语义搜索）
- **知识库深层逻辑系统（Knowledge Brain）** — 八大模块：
  - **动态 LLM 分析**：LLM 根据内容自由生成分类/标签/key_concepts/related_topics/knowledge_type，不再硬编码
  - **自动关联引擎**：新入库条目通过 pgvector 余弦相似度 + 概念重叠自动发现关联关系，双向写入 knowledge_relations 表
  - **RAG 问答引擎**：语义搜索 → 阈值分类 → LLM 合成 → 来源引用，高相关不足时自动触发研究
  - **自主研究引擎**：知识空白检测 → 联网搜索（搜狗+必应）→ 网页抓取 → LLM 提取 → 自动入库 → 建立关联
  - **健康监控**：Celery 定时任务检测矛盾/重复/过期条目
  - **实体知识图谱**：跨文档实体融合（精确匹配→embedding 余弦→新建），共现网络，ECharts 力导向图可视化
  - **假设生成引擎**：从实体三元组+知识空白 LLM 生成可验证假设，proposed/validated/rejected 生命周期
  - **量化推理引擎**：LLM 提取数学公式 → safe_eval 安全计算 → LaTeX 渲染 → 前端计算器
  - **公式分类体系**：6 大类 24 子分类（FormulaCategory 模型树）+ 32 个内置微纳米气泡领域公式，前端分类树浏览，来源标签（内置/提取）
  - **公式自动分类**：LLM 提取公式 domain 字符串 → 模糊映射到结构化分类，新老公式统一归入分类树
- 语音识别使用 faster-whisper GPU，TTS 使用 Edge-TTS
- **会议转录总结工具** — `summarize_meeting_transcript` 工具支持对话触发与长期存储
- **任务软删除/垃圾桶** — 删除任务进入垃圾桶（deleted_at 字段），支持恢复或永久删除，3天后自动清除（Celery beat 每 1h 调度 `auto_purge_trash_task`，垃圾桶 UI 双行显示倒计时 + 5 级紧急度颜色）。详细状态见 [README.md](README.md#当前状态2026-06-03)
- **微信对话双消息模式** — 收到消息后 0.5 秒内先发"🤔 收到，让我思考一下..."，后台异步处理后发正式回复，解决等待无反馈问题
- **移动端独立抽屉架构** — 移动端侧边栏使用 el-container 外部独立 div + Vue Transition，完全绕过 Element Plus aside 的全局 CSS 干扰。桌面端 `v-if="!isMobile"` 零影响
- **通知面板** — 铃铛使用 el-popover 弹窗面板，显示每条提醒的具体内容（任务标题+提醒时间）、全部标为已读、点击跳转任务；头像读取 userStore.userInfo.avatar 真实 URL
- **任务权限模型** — 所有成员可见全部任务（降低认知负担），仅创建人/负责人/管理员可编辑、删除、恢复、永久删除
- **状态统一** — "待办"(todo) 和 "进行中"(in_progress) 语义高度重合，已统一为"进行中"。新建任务默认 in_progress，现有 todo 任务兼容显示
- **移动端路由级双栈架构**（2026-06-13 收官）— 桌面端（Element Plus）和移动端（NutUI 4）**同一 URL 不同组件**，不共享 component 树。`useIsMobile.js` 监听 viewport + UA 兜底 → `router/index.js` 通过 `resolveMobile.js` 动态 import `views/mobile/*` 或 `views/*` → 桌面端 `el-*` 与移动端 `nut-*` CSS 完全隔离。**PWA 4 策略**：manifest + service worker（workbox）预缓存 app shell + useSafeArea 读 iPhone 安全区 + 离线 IndexedDB 兜底。**视觉回归测试**：Playwright 5 viewport × 13 核心页面，CI 截图对比基线

## 代码质量规范（2026-06-04 升级）

### API 层
- **统一异常响应格式**：`{"error": {"code": "RESOURCE_NOT_FOUND", "message": "...", "details": {...}}}`
- **异常类层次**：`app/core/exceptions.py` — AppException/NotFoundException/ValidationException/AuthException/ForbiddenException/ConflictException/RateLimitException
- **统一分页模型**：`app/schemas/pagination.py` — PaginationParams + PaginatedResponse + PaginationMeta
- **全站分级限流**：`app/core/rate_limit.py` — auth:5次/分, write:30次/分, read:100次/分, upload:10次/分
- **安全响应头**：X-Content-Type-Options/X-Frame-Options/X-XSS-Protection/Referrer-Policy/X-Request-ID

### 前端架构
- **Composable 模式**：`web/src/composables/` — useTask/useMeeting/useKnowledge 提取共享状态 + API 调用
- **子组件拆分**：18 个子组件（Task:3 + Knowledge:8 + Meeting:3），主 View ≤ 1920 行
- **Vitest 测试**：`web/vitest.config.js` — composable 测试（23 个）+ 组件测试（15 个）= 38 个测试通过

### 测试规范
- **后端**：pytest + httpx AsyncClient，service 层单元测试 + API 集成测试
- **前端**：Vitest + @vue/test-utils，composable 测试优先，组件测试选择性覆盖
- **Mock 策略**：Redis 用 fakeredis，Claude API 用 respx，Embedding 用固定向量

## 服务层结构

| 文件 | 职责 |
|------|------|
| `app/services/task_service.py` | 任务 CRUD + 统计 + 自动提醒 |
| `app/services/member_service.py` | 成员 CRUD + 按姓名查询 |
| `app/services/meeting_service.py` | 会议 CRUD + 参与者管理 |
| `app/services/project_service.py` | 项目+里程碑 CRUD |
| `app/services/knowledge_service.py` | 知识库 CRUD + 语义搜索 |
| `app/services/reminder_service.py` | 提醒服务 + Celery task |
| `app/services/memory_service.py` | 长期记忆 CRUD + 语义搜索 + LLM 提取 |
| `app/services/search_service.py` | 联网搜索（搜狗+必应双引擎） |
| `app/services/embedding_service.py` | 向量嵌入（text2vec-base-chinese） |
| `app/services/file_parser_service.py` | 文件内容提取（PDF/Word/Excel/PPT） |
| `app/services/llm_analysis_service.py` | LLM 内容分析（动态分类+标签+摘要+核心概念） |
| `app/services/knowledge_graph_service.py` | 知识图谱服务（自动关联+BFS 遍历+动态分类+标签云+统计） |
| `app/services/knowledge_qa_service.py` | RAG 问答引擎（检索+阈值+LLM 合成+来源引用） |
| `app/services/auto_research_service.py` | 自主研究引擎（联网搜索+知识提取+空白填充+矛盾/重复/过期检测） |
| `app/services/dynamic_taxonomy_service.py` | 动态分类体系（涌现分类+分类建议+主题网络） |
| `app/services/knowledge_evolution_tasks.py` | Celery 知识进化定时任务（每日进化/空白检测/健康检查/实体融合） |
| `app/services/reminder_scheduler.py` | Redis 精确提醒调度（秒级精度） |
| `app/services/entity_service.py` | 实体知识图谱（跨文档融合+搜索+图谱+LLM 合并） |
| `app/services/hypothesis_service.py` | 科研假设生成（LLM 驱动假设+验证生命周期） |
| `app/services/formula_service.py` | 量化推理（公式列表+安全计算+LaTeX 转换+分类树+内置公式库） |
| `app/services/meeting_analysis_service.py` | 会议 AI 分析（发言者检测+格式识别+结构化分析+发言人统计+标题生成）|
| `app/services/voiceprint_service.py` | 声纹识别（3D-Speaker 嵌入提取+pgvector 匹配+录入）|
| `app/voice/vad.py` | silero-vad 语音活动检测 |
| `app/services/audio_processor.py` | 音频格式转换（WebM→WAV）+ 离线 VAD 分段 |

## 开发注意事项

### 2026-06-13 移动端 10 PR + 部署加固 收官新增

- **移动端路由级双栈（重要，PR #1 基建 + PR #2 NutUI 引入，commits `99bbe6b` `3c58cb1`）** — 桌面端（Element Plus）和移动端（NutUI 4）**同一 URL 不同组件**，不是 `v-if` 全局切换。模式：①`useIsMobile.js` 监听 `window.matchMedia('(max-width: 768px)')` + `navigator.userAgent`（iPad/iPhone 误判时用 UA 兜底）②`router/index.js` 通过 `resolveMobile.js` 动态 import `views/mobile/*` 或 `views/*` ③每个 View 文件在 setup 顶部 import 自己的子组件，不共享 component 树。**好处**：桌面端 `el-*` 与移动端 `nut-*` 完全隔离，无 CSS 冲突；切设备时**不重载后端**，URL 不变。**坑**：`/chat` 桌面端走 ChatViewSSE.vue，移动端走 MobileChatView.vue，store/Pinia 完全独立（避免桌面端 dark mode 状态污染移动端主题）
- **移动端首屏包大小纪律（PR #3 教训，commit `0ed4294`）** — `import.meta.glob('eager: true, import: 'default')` 在移动端 View 文件**会触发 Vite 静态分析失败**（MobileChatView 引入 12 个 block 组件全部 eager import → 桌面端代码被打进移动端 chunk）。**修复**：①eager 模式必须包在 `if (!isMobile.value) { ... }` 条件内，让 Vite tree-shake ②构建后 `web/dist/assets/` 里 grep 关键桌面组件名（如 `ChatViewSSE`），不应该出现在 mobile-*.js chunk 里 ③mobile chunk size 目标 < 250KB gzip
- **v-model on prop 误用 Vue 警告（PR #3 教训）** — Element Plus `<el-input v-model="localValue">` 在 `:value` 上写 v-model，Vue 警告。**修复**：用 `computed` get/set 包装 props 后再 v-model。`<el-input :model-value="localValue" @update:model-value="localValue = $event">` 也可
- **webhint `meta-theme-color` 静态声明 vs JS 动态注入（commit `0bbc12d` + `3cf8634`）** — 静态 `<meta name="theme-color" content="...">` 只能写一个固定值，但项目有 dark mode 需要切换。**修复**：HTML 不写静态 meta，`useThemeStore` 监听 `theme` 变化后 `document.querySelector('meta[name="theme-color"]')?.remove()` + 创建新 meta 注入。`.hintrc` 加 `"webhint:recommended"` 关闭该规则（webhint `meta-viewport` hint 仍会查这个）
- **webhint cache-busting 缓存正则匹配 hex 8 字符（commit `6339c29` 续，PR 修复迁移）** — Vite `hashCharacters: 'hex'` 输出 8 字符 hex 满足 webhint 内置 `[0-9a-f]+` 正则。新建 Vite 项目**默认配置**应为 `hex`，不要用 base64url
- **webhook 偶发 499 失败根因（重要，commit `7e41577`）** — 阿里云→GitHub HTTPS 出口网络瞬时故障，TLS 握手时 GitHub 客户端 10s 超时断开，Nginx 收 499 但 webhook service 完全没机会处理（连接都没建立）。**修复 1（deploy-auto.sh 改 git reset --hard 模式）** — 服务器是 immutable infra，`git pull` 在 dirty working tree（之前有失败 deploy 留下的 untracked 文件）下会卡。`git fetch origin main && git reset --hard origin/main` 永远把工作区强制对齐。`git clean -fd` 改 `git clean -fdx`（也清 .gitignore 内文件）。**修复 2（webhook.py socket timeout）** — `import socket` + `self.connection.settimeout(15)`（GitHub 默认 10s + 5s 余量）+ try/except socket.timeout → 504。**手动 redeliver trick**（紧急补部署）：本地 `git rev-parse HEAD` 取 SHA → 构造真实 payload → openssl dgst -sha256 -hmac 计算 X-Hub-Signature-256 → SSH 到服务器 `curl -X POST http://127.0.0.1:9001/webhook`（绕过 Nginx 直接调 service，绕过 GitHub 5min/30min 重试链）。沉淀：[webhook-debug-2026-06-13.md](C:/Users/admin/.claude/projects/g--microbubble-agent/memory/webhook-debug-2026-06-13.md)
- **移动端 18 页面 + 12 组件 + 4 PWA 策略（PR #1-10 全栈定制收官，commit `9026c07`）** — 完整覆盖：Dashboard/Login/Chat（带 session drawer + message bubble + input bar + rich card）/Task/TaskTrash/Meeting/MeetingDetail/MeetingRoom（3D CSS 声波条）/Knowledge/KnowledgeDetail/Project/ProjectStats/Member/Memory/Settings/Voiceprint/AgentTraces/admin。**核心组件**：CardList（卡片列表+下拉刷新+无限滚动）/LongPressWrapper（长按事件封装，300ms 触发）/MobileActionSheet（iOS 风格底部弹出菜单）/MobileECharts（图表懒加载+resize 监听）/MobileFormSheet（表单底部弹出）/MobileSearchSheet（搜索浮层）/MobileTaskCreateForm（任务创建 5 字段）/PageHeader（顶栏统一规范）/ProcessingSheet（处理中浮层）/SafeArea（iPhone 刘海/底栏安全区适配）/TabBar（底部 4 tab + 中间凸起 +badge）/VoiceTestFlow/VoiceprintEnrollFlow。**PWA 4 策略**：①vite-plugin-pwa 自动生成 manifest.json + service worker（workbox）②Service Worker 预缓存 app shell + 路由 fallback ③`useSafeArea` 读 env(safe-area-inset-*) + dynamic viewport units ④App 离线时显示「网络已断开但可查看最近消息」+ IndexedDB 缓存
- **移动端测试矩阵（PR #10 收官，commit `9026c07`）** — `web/tests/visual/visual-regression.spec.mjs` Playwright 跨设备截图测试，覆盖 iPhone SE/14/15 Pro Max + iPad mini + Galaxy S21 5 个 viewport，**13 个核心页面视觉对比基线**。`web/src/components/mobile/__tests__/` 2 个组件测试（CardList + MobileFormSheet）+ Vitest jsdom 环境

### 2026-06-12 v4 收官后新增（多会话并行架构）

- **多会话并行架构（修复 4）核心纪律**（重要，commit `662a6ea`）— ChatViewSSE 多会话并行不丢数据不打架：①`messagesBySession: Record<sessionId, Message[]>` per-session 隔离 ②`activeAssistantMap: Record<sessionId, Message>` SSE yield 找目标引用 ③`sendMessage` 启动时**闭包捕获 `targetSessionId`**（防止 SSE yield 时 outer `sessionId.value` 已切走）④`abortControllers[sessionId]` per-session 取消（多次点击同会话）⑤`loadedSessions: Set<sessionId>` 防重复加载覆盖后台 SSE 增量 ⑥`persistTimers: Record<sessionId, Timer>` debounce 100ms 持久化（防后台丢）⑦`scrollToBottom` / `loading` 仅 `targetSessionId === sessionId.value` 时触发（避免切走还在滚 A 的消息区）。**切会话不 abort 任何 SSE**（让 A 后台继续跑），但**组件卸载时 abort 所有**。**任何"流式响应 + 多视图"场景都要 per-session 隔离 + 闭包贯穿**。沉淀：[multi-session-parallel-architecture.md](C:/Users/admin/.claude/projects/g--microbubble-agent/memory/multi-session-parallel-architecture.md)
- **Pydantic Literal 字段不接受 None**（重要，commit `3852755`）— 即使 Python 类型注解是 `Optional[str]`，None 仍会触发 Literal 验证失败。17 个 tools/*.py 的 OutputModel schema 都定义 `rich_block_type: Optional[str] = None`（默认值），`chat_engine._extract_rich_block:432-441` 旧版只要 `result` 里有 `rich_block_type` 键就强行 `RichBlock(type=rb_type, ...)` 致 SSE 流 500。**修复**：加 `_VALID_RICH_BLOCK_TYPES: frozenset = frozenset(get_args(RichBlockType))` 守卫 + 改用 `if rb_type and rb_type in _VALID_RICH_BLOCK_TYPES` 跳过显式分支（fall through 到 implicit_map）。**用 `get_args` 动态生成集合**——与 protocol.py Literal 自动同步，未来新增 block 类型无需维护。**不要信任"键存在就构造"模式**——必须先验证值的合法性。沉淀：[richblock-type-none-pitfall.md](C:/Users/admin/.claude/projects/g--microbubble-agent/memory/richblock-type-none-pitfall.md)
- **Python 模块加载级 NameError：缺 typing import**（重要，commit `3852755`，与 4ba7390 修复 2 同类）— 整个 `app/services/hybrid_retriever.py:12` 写 `from typing import List, Optional`，但 line 272 `eval_set: List[Dict]` / line 305 `_aggregate(per_query: List[Dict]) -> Dict` 用到 `Dict` → 模块加载就抛 `NameError: name 'Dict' is not defined. Did you mean: 'dict'?` → 整个 hybrid_retriever import 失败 → search_knowledge 工具一调就报。**类型注解在模块加载时也会执行**（不是只在调用时）。**扫描 one-liner**（改进版检查 import 列表是否真含所需名字）：```bash
for f in app/services/*.py app/agent/tools/*.py; do
  for type_name in Dict List Tuple Optional Union Set FrozenSet; do
    if grep -qE "\b$type_name\b" "$f" 2>/dev/null && ! grep -qE "from typing import.*\b$type_name\b|\*\)" "$f" 2>/dev/null; then
      echo "MISSING $type_name in: $f"
    fi
  done
done
```**每个 app 子包要确保 import 链完整**——加新 model/service/tool 后跑 `python -c "from app.X import Y"` 验证。**加进 CI / pre-commit 钩子**。沉淀：[typing-import-missing-bug.md](C:/Users/admin/.claude/projects/g--microbubble-agent/memory/typing-import-missing-bug.md)
- **a11y 表单元素 4 属性套件是铁律**（小坑）— webhint 报 `A form field element should have an id or name attribute`，任何 `<textarea>` / `<input>` / `<el-input>` 都要补齐 `id` + `name` + `aria-label` + `title` 4 属性。`<textarea id="chat-input-textarea" name="chat-input-textarea" aria-label="聊天输入框" title="聊天输入框">` 是一例。**仅 file input 因为 hidden 无法走可见 label 路径，必须显式 aria-label + title 兜底**。参考 [Webhint Optimization](C:/Users/admin/.claude/projects/g--microbubble-agent/memory/webhint-optimization.md) + 2026-06-12 commit `c97071c`（file input 4 属性套件先例）+ 2026-06-12 commit `662a6ea`（chat textarea 4 属性套件）

### 2026-06-12 v4 收官新增

- **`@tool` 装饰器 + Pydantic 校验是工具调用的标准模式**（v4 收官确定）— 34 工具全走装饰器后，**任何**新增工具必须遵循 4 步：①Pydantic BaseModel 严格定义 `input_model` / `output_model`（不依赖裸 `Dict[str, Any]`）②handler 委托原 service（不重写业务逻辑）③pytest happy/error/edge 三用例 ④`dispatch_tool(name, ...)` 跑通。`@tool(requires_db=True, requires_user=False)` 标记前置条件，dispatcher 自动校验缺 DB 返 `DB_UNAVAILABLE` 错误、缺 user 返 `AUTH_REQUIRED` 错误
- **`dispatch_legacy` 是装饰器注册表的兜底**（v4 清理后保留）— 当 `TOOL_REGISTRY` 没找到某工具名时（极端情况：用户自定义工具未注册），dispatch_legacy 回退到 `MicroBubbleAgent._execute_tool` 薄壳。所有 34 工具确认走装饰器后，**未来可彻底删除 dispatch_legacy**（约 18 行代码）让错误立即抛 `ToolNotFoundError`
- **`core.py` 是兼容壳，不是真实逻辑**（v4 清理后）— 原 1469 行 → 689 行（-53%）。`_execute_tool` 14 行薄壳直接调 `dispatch_tool`，**不再有 if/elif 链**。MicroBubbleAgent 类保留仅为向后兼容（chat/chat_stream/clear_session 公开 API 仍可调用）。所有业务逻辑在 `micro_bubble_agent.py`（v2 主类）
- **Pydantic BaseModel 字段顺序很重要**（教训）— 写 `MeetingListItem` 等 OutputModel 时，`rich_block_type` 字段**必须放最后**（避免 Pydantic V2 序列化冲突）。`Field(default=...)` 显式标注默认值，让 optional 字段有 fallback
- **SSE 事件类型不要在前后端硬编码**（v4 教训）— 协议层（`app/agent/protocol.py`）用 `Literal` 类型定义 9 种 `StreamEventType`，前端 `web/src/api/agent/protocol.ts` 用 union type 镜像。**新增事件类型**只改这两个文件 + 后端 `chat_engine.py` + 前端 `sse.ts` + 组件 switch case 共 4 处
- **ASR 端到端 4 层链路**（v4 完整接通）— `前端 VoiceRecorder emit record-stop blob` → `axios.post /api/v1/voice/asr (multipart)` → `后端 app/voice/asr.py:POST /voice/asr` 调 faster-whisper GPU large-v3 → 文字 → `inputText + sendMessage()`。**任一环节断就静默失败**，必须 4 步全验证（端到端真实语音 → ASR 真实文字 → sendMessage → assistant 真实回复）
- **highlight.js 按需注册**（v4 教训）— 200+ 语言全量打包 +30KB gzip+。**只注册 6 种常用语言**（python / js / bash / json / sql / yaml）就覆盖 90% 场景。dark mode 用 CSS 变量覆盖 `.hljs` 类而非切换主题文件（更轻）
- **性能基线 P95 阈值需取实测 + 30% buffer**（v4 设计）— 不能用硬编码 3s/30s（不同机器性能差 5x）。`tests/perf/` 第一次跑取 20 次实测 P95 + 30% buffer 作为基线，CI 接受 ±30% 浮动。**机器换了**（如本地开发机 vs 生产服务器）需重测
- **评估标注集是质量基线的根基**（v4 设计）— `data/eval_queries.jsonl` 20 问的 `relevant_ids` 字段是**占位预填**（基于领域知识 1-200 范围），**部署后必须**跑 `scripts/build_eval_ground_truth.py` 半自动修正为真实 ID（检索 top-10 + 人工筛）。否则 `recall@5` 计算无意义（查的 ID 数据库里不存在）
- **`agent_traces` 表 30 天清理策略**（v4 待做）— 当前表会无限增长。Celery beat 加 `purge_old_traces(days=30)` 每日清理，**与 reminder 任务同模式**（已 `app/services/reminder_service.py` 有参考实现）

### 2026-06-12 v3 深化新增

- **12 类 Rich Block 组件化**（v3 + v4 累计）— `MeetingCard` / `TaskListBlock` / `KnowledgeRefBlock` / `MemberCardBlock` / `FormulaBlock` / `HypothesisBlock` / `ProjectSummaryBlock` / `TranscriptBlock` / `ChartBlock` + 2 兜底。注册表 `web/src/components/chat/blocks/registry.ts` 用 `Record<string, Component>` 极简映射，支持 `registerBlock()` 动态扩展。**新增 block 类型**只改 3 处：①组件实现 ②registry 注册 ③`chat_engine._extract_rich_block.implicit_map` 加映射
- **多会话侧栏 + 兼容 v1**（v3 设计）— Pinia `chatSessions` store 自动 watch 持久化到 localStorage，**首次启动调 `migrateFromV1()`** 从旧 `chat_session_id` 单键导入为新会话。**新会话标题**取首条 user 消息前 30 字（LLM-as-judge 不依赖，零成本）
- **dark mode 主题切换通过 CSS 变量**（v3 设计）— `web/src/assets/variables.css` 加 `[data-theme="dark"]` 块重定义 `--color-*` 变量，所有组件用 `var(--color-primary)` 而非硬编码 `#FF7A5C`。切换主题 = `document.documentElement.setAttribute('data-theme', 'dark')` + localStorage 持久化。**不切换主题文件**避免双套 CSS 加载

### 2026-06-12 新增（深夜，4 commits 收尾）

- **Docker volume 挂载只换文件不换 Python 模块缓存**（重要，commit `4ba7390`）— `/api/v1/chat/stream` 404 排查双层根因：①app 容器 8:43 启动，`chat.py` 17:55 才加 `/chat/stream` 路由，**volume 实时同步文件但 Python 进程只在启动时 import 一次**，路由表停留在 16:43 那刻。`docker exec ... cat chat.py` 能看到新版（误导诊断），但 `curl /openapi.json | grep /chat/stream` **完全没有**这条路由（决定性证据）②重启 app 后又暴露 `search_tools.py` 缺 `from typing import Optional`，整个 FastAPI 启动失败 → 所有 `/api/v1/*` 路由 404。这个 NameError 是 v4 收官批量改 tools/ 时引入，但**模块缓存反过来掩盖了它数天**，直到为修 chat/stream 重启才一次性炸。**规则**：①怀疑路由 404 时**第一步看 OpenAPI**：`curl /openapi.json | grep "/route"`，没有 = 100% 模块缓存问题，不要去查文件 ②任何改路由 / import / 装饰器 / Pydantic 模型字段的 commit **必须** `docker compose restart app`，不只是 celery ③批量改 `tools/` 或 `schemas/` 的 commit **必须立即手动重启验证**，不要寄望"下次自然重启"暴露 bug ④扫描 typing import 漏写的 bash one-liner：`for f in app/agent/tools/*.py; do uses=$(grep -c '\bOptional\b' "$f"); has=$(grep -c 'from typing import.*Optional' "$f"); [ "$uses" -gt 0 ] && [ "$has" -eq 0 ] && echo "MISSING typing import: $f"; done`。**沉淀**：[docker-python-module-cache.md](C:/Users/admin/.claude/projects/g--microbubble-agent/memory/docker-python-module-cache.md)
- **SSE/WS 流式事件两种语义混用必爆**（重要，commit `cf70ff5`）— `chat_engine.chat_stream` 流式分支既 yield `text_delta`（每个 token 一个增量）又在结束时 yield `brief`（`delta=accumulated_text` 完整文本快照）。前端 [ChatViewSSE.vue:215](web/src/views/chat/ChatViewSSE.vue#L215) 旧版 `if (type === 'text_delta' || type === 'brief' || type === 'detail') content += delta` **盲目 append**，结果 text_delta 累一遍 brief + brief 又把完整文本 append 一次 → 用户看到内容**重复出现两次**。**两类事件长得一样但语义相反**：
  - **增量事件**（如 `text_delta`）：delta=新增的一小段，正确处理 `content += delta`
  - **快照事件**（如 `brief`）：delta=完整累积文本，正确处理 `content = delta`（替换）或**根本不 append**（仅作阶段标记）
  
  **诊断方法**：①Network → EventStream 看原始事件流，哪一帧 delta 字段**突然变长**就是快照事件；②`console.log(content.length)` 每收一帧，长度**翻倍** = 快照被误 append。**防御纪律**：①protocol 文件里**显式标注每个事件类型的 delta 语义**（增量/快照/替换）②**前端不写「多事件类型共用 append 分支」**——拆开强迫读代码时区分语义 ③快照事件命名带 `_snapshot` / `_complete` 后缀避免误读 ④添加新事件类型时先想清楚 delta 是增量还是快照，更新两端 protocol + 组件 switch case。**沉淀**：[sse-event-semantic-mismatch.md](C:/Users/admin/.claude/projects/g--microbubble-agent/memory/sse-event-semantic-mismatch.md)
- **Composable 解构字段名拼写错误**（重要，commit `13ba305`）— `const { isOnline } = useNetworkStatus()` 但 composable 实际暴露 `online` 不是 `isOnline`，`isOnline = undefined` 让模板 `v-if="!isOnline"` 永远等价于 `v-if="true"`，横幅永远显示"网络已断开"。**与 2026-06-02 变量名笔误同源**（`<script setup>` 内标识符错误编译期完全沉默），但触发模式不同：第 2 条访问**未声明**变量 → 运行到 lifecycle 抛 `ReferenceError` → 白屏（易察觉）；这条解构出**不存在字段** → 变量永远 `undefined` → 模板永远 falsy/truthy → **沉默误导**（难察觉，看起来"功能在跑"但条件永错）。**对照**：`MainLayout.vue` / `AudioRecorder.vue` 用 `const network = useNetworkStatus()` 整体接收没踩坑。**规则**：①解构 composable **前必看 return 语句**，不凭直觉猜字段名（`isOnline` / `connected` / `available` / `loading` / `isLoading` 都是常见误猜）②不确定时改用整体接收 `const x = useXxx()` + `x.field.value` ③想要重命名就显式写 `const { online: isOnline } = useXxx()`，强迫看一眼源字段名 ④TypeScript 能编译期捕获，纯 JS 项目得靠纪律。**沉淀**：[frontend-pitfalls.md](C:/Users/admin/.claude/projects/g--microbubble-agent/memory/frontend-pitfalls.md) 第 4 条
- **a11y file input 4 属性套件**（小坑，commit `c97071c`）— webhint 在 `/chat` 报隐藏 file input 无 label。所有 `<input type="file" hidden>` 必须补齐 4 属性：①`id` + `name`（webhint「form field needs id or name」+ 浏览器 autofill 友好）②`aria-label`（axe「elements must have labels」，hidden input 无法走可见 label 路径）③`title`（webhint 兜底）。每个 id 全局唯一，多文件复用同样语义时加 `-legacy` / `-v2` 后缀避免 autofill 串扰。本项目 5 个 file input 全部修齐：[ChatViewSSE.vue:506-526](web/src/views/chat/ChatViewSSE.vue#L506-L526)（chat-image-upload / chat-file-upload）+ [ChatView.vue:147-168](web/src/views/ChatView.vue#L147-L168)（legacy 后缀）+ [SettingsView.vue:16-25](web/src/views/SettingsView.vue#L16-L25)（settings-avatar-upload）

### 2026-06-12 新增（晚间）

- **`_execute_tool` 函数体内 `from X import Y` 是 UnboundLocalError 重灾区**（重要，与 2026-06-02 声纹会议 WS 闪烁根因同类）— 2026-06-12 用户问"有没有相关会议可以学习？"助手回复"会议查询系统暂时无法正常工作"。两层根因：①LLM 看到 tools schema 但没有强 prompt 约束，倾向自己编造借口 ②代码 `app/agent/core.py:911` 在 `_execute_tool` 函数内（属于 `summarize_meeting_transcript` elif 分支）有 `from app.services.meeting_service import MeetingService`，Python 编译器**不区分 elif 分支**，会扫描整个函数体，只要看到这个名字就是 local，导致 line 881 `MeetingService(db)` 抛 `UnboundLocalError: cannot access local variable 'MeetingService' where it is not associated with a value`。被外层 `except Exception as e: return {"status":"error",...}` 吞掉后 LLM 看到 tool_result 是 error，又撒谎说"系统故障"。**规则**：①模块顶部已 import 的名字，函数体内**绝不要**再 `from X import Y` 重新导入 ②如果函数体内有 `import` 同名，**必须**重命名（`from app.X import Y as _Y`）避免污染 ③新增 tool 路由时**自上而下**检查所有 elif 分支的局部 import ④LLM 撒谎模式防御：所有 tool 必须在 `prompts.py` 顶部"工具调用黄金规则"section 显式列出"必须调用"+ "严禁编造借口"，否则 LLM 倾向 hallucinate
- **LLM 撒谎模式 (LLM Hallucination as Excuse)** — 当工具执行失败（被 except 吞掉、网络错误、参数错误）时，LLM 倾向用以下借口之一搪塞用户，**而不是诚实地报告错误**：
  - "X 系统暂时无法正常工作" / "技术问题" / "数据同步中"
  - "数据库中暂无相关记录"（即使数据库明明有数据）
  - "请联系管理员" / "稍后再试"
  - 看起来"合理的"空响应："关于会议学习，我建议您从以下方面入手" + 通用建议列表
  - **真相**：LLM 撒谎的频率与"工具是否在 system prompt 有强指令"负相关。`query_all_member_tasks` 有"必须调用"指令 → LLM 调；`query_meetings` 没有 → LLM 直接拒绝调工具编借口。**修复模式**：所有用户高频调用的 tool 必须在 `prompts.py` 系统提示词中**显式**列入"必须调用"section + 工具描述中标注「【必调工具】」+ 列举触发短语。**诊断方法**：直接调 API（绕过 LLM）确认 tool 实际能返回数据 → 问题 100% 在 LLM 提示层
- **直接调 API 验证是排查 LLM 谎话的最快方法**（重要）— 遇到"AI 助手说系统坏了"类问题，**永远先**直接 `curl /api/v1/...` 验证后端真伪：
  ```bash
  curl -sk -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/meetings | head -c 500
  ```
  如果后端正常 → 100% 是 LLM 撒谎/没调工具，不必查后端代码
  如果后端 500 → 才是后端问题，进 docker logs 找 traceback
- **调 LLM tool 必加调试日志**（诊断必经步骤）— 给 `_process_response` 和 `_execute_tool` 各加一行 `logger.warning(f"[DEBUG] tool={name}, input={input_data}")` + 外层 except 加 `logger.error(..., exc_info=True)`。无日志时 LLM 撒谎的错误被 except 吞掉，**根本无法定位**是"LLM 没调工具"还是"工具执行报错"。3 行日志可节省 1 小时排查时间

### 2026-06-12 新增（下半场）

- **webhint `detect-css-reflows/paint` 真正绕开方案**（重要）— hint 源码 `packages/hint-detect-css-reflows/src/{paint.ts,assets/CSSReflow.json}`：
  - `transform`（含 `scale()`/`rotate()`/`translate()` 函数）→ paint=true，会报警告
  - 独立 `translate:` 属性 → paint=true **AND** layout=true，比 transform 更糟
  - 独立 `scale:` / `rotate:` 属性 → **不在 JSON 里**，是 webhint 公认的干净绕开
  - `will-change` 完全不被该 hint 考虑（只扫 keyframes 内属性名）
  - **批量替换模式**：`transform: scale(N)` → `scale: N`；`transform: rotate(Xdeg)` → `rotate: Xdeg`；`transform: rotate() scale()` 组合 → 拆成 `rotate: X; scale: Y` 两行
  - 浏览器支持：CSS Transform Module Level 2（2022+ 全浏览器原生），不需要 polyfill
  - **保留 `transform: translate*()` 不动**：webhint 把所有位移属性都标 paint，没有干净替代
- **字符串聚合操作必须在源头过滤空内容**（教训）— 修 `transcriptEntries undefined.length` 崩溃时把 `raw[0].text || ''` 默认为空串，引发新 bug：21 个连续空 text 条目 merge 时累加 `'' + ' ' + ''` 全是空格 → `length > 20` 通过 `_needsPolish` → 后端 polish-text strip().length < 3 → 400。**规则**：①merge/reduce 类聚合操作要在循环条件就过滤空内容 ②API 发送前要 trim 校验 ③长度判定用 `trim().length`，不要用裸 `length`（空格不算"内容"）
- **`a?.length || 0` 必须左右两侧都防**（教训）— 比较表达式 `(current.text.length + (entry.text?.length || 0)) < N` 之前只防右边，当 transcript 条目缺 text 字段时 `current.text.length` 直接爆 undefined。**规则**：computed 内涉及外部数据的属性读取一律 `?.`，比较运算左右两侧都要兜底

### 2026-06-12 新增（上半场）

- **会议录音断网防御机制（5 阶段全栈完成）** — 2026-06-12 会议 #84 录音 58 分钟因 network error 丢失 1.6 秒废片段后永久卡死。完整修复：①前端 IndexedDB 兜底 + 边录边传骨架 ②上传状态徽章 + `useNetworkStatus` 接入 ③后端 chunked 端点（PUT /audio-chunk, POST /merge-chunks, GET /upload-status）+ 4 字段迁移 ④后端 stop-recording 硬校验 + Celery 真实 `self.retry` + 孤儿会议清理 + 删会议清 MinIO ⑤端到端测试 + bug 修复。**关键教训**（重要）：
  - **`useGlobalRecorder.js` 改造必须向后兼容** — 阶段 1 新增 `onChunk` 回调钩子（注册到 `chunkCallbacks` 数组），保留原 `audioChunks.push` 逻辑，AudioRecorder.vue 等消费者零感知改动
  - **fake-indexeddb 不支持复合索引 `IDBKeyRange.only([k, v])`** — jsdom + fake-indexeddb 抛 `DataError: parameter 2 is not of type 'Blob'`。修复：取消 `by_meeting_uploaded` 复合索引，改用 `by_meeting` 单字段 + 内存 filter `records.filter(r => !r.uploaded)`
  - **fake-indexeddb 反序列化 Blob 为普通对象** — 存进去再读出来 `blob.constructor.name === 'Object'`，后续 `FormData.append('file', blob, ...)` 抛 `parameter 2 is not of type 'Blob'`。修复：在 `idbStore.putChunk` / `getPendingChunks` 重新包装 `const safeBlob = blob instanceof Blob ? blob : new Blob([blob], { type: 'audio/webm' })`
  - **Celery `self.retry()` 必须 `raise`** — 在新 event loop 中 `try/except` 接住后**阻断** Celery 重试机制。正确模式：`_run()` 内 `except (ValueError, IOError, OSError, ConnectionError, TimeoutError) as e: raise self.retry(exc=e, countdown=60)` 让 Celery 装饰器接住；外层 `try/except` 只兜底 Celery 自身崩溃
  - **`delete_chunks` 不能"顺手删 merged"** — 阶段 5 端到端发现此 bug：merge 完成后调 delete_chunks 清理源 chunks，旧版 delete_chunks 内部又删了 merged.webm → 后处理 NoSuchKey。修复拆三个方法：`delete_chunks` / `delete_merged` / `delete_all`（用于删会议时清理）
  - **minio-py `put_object` 用位置参数** — 旧 `file_service.upload_to_path` 误用 S3-style kwargs `Bucket/Key/Body/Length/ContentType` 抛 `TypeError: Minio.put_object() got an unexpected keyword argument 'Bucket'`。正确：`put_object(bucket_name, object_name, data, length=-1, content_type=None)`
- **fake-indexeddb 必须 `import 'fake-indexeddb/auto'`** — 装包后只在 `setup.js` 顶部 import 一次，jsdom 环境才有 IndexedDB。`npm install --save-dev fake-indexeddb`
- **Vitest 默认 5s 超时** — uploadOne 内部 5xx 重试 5 次 × 指数退避（1s+2s+4s+8s+16s=31s）超过默认 timeout。测试中用 `vi.mockResolvedValue` 模拟 4xx 不重试，避免 hang
- **断网录音前端** — `useNetworkStatus.js`（2026-06-09 已实现但未接入），本次首次接入到 `MainLayout.vue` 浮动胶囊 + `AudioRecorder.vue` 徽章。`online` / `offline` 事件 + `navigator.connection.effectiveType`
- **Vite/Rollup hashCharacters 默认值** — Vite 8 默认 `hashCharacters: 'base64url'`，产出形如 `index-Qec9lxup.css`、`MainLayout-B6AkdWtm.js`（含大小写字母+数字+下划线+连字符）。webhint 内置 cache-busting 正则只认 `[0-9a-f]+` 小写 16 进制，会对所有 chunk/asset 文件报 "URL does not match configured patterns"。**修复**：`web/vite.config.js` 加 `build.rollupOptions.output.hashCharacters: 'hex'`，文件名变为 `index-9ab8129c.js` 等全小写 hex，webhint 通过。Rollup 4.x 原生支持此选项。新建 Vite 项目时应直接配为 hex
- **Vite dist 重命名提交** — 改 hashCharacters 后 `npm run build` 会重命名 100+ 个 dist 文件。**必须** `git add -f web/dist` 强制提交，否则 `.gitignore` 拦截新文件名（删了旧的不加新的），线上 404 白屏。验证 `git diff --cached --stat` 看到所有文件都是 `rename:` 不是 `deleted:`
- **webhint cache-busting 误报的真实修复路径** — 之前 MEMORY 误记为"Edge DevTools 内置 webhint 不读项目配置 → 浏览器端无法消除"，实际**工具链配置可以彻底消除**。不要被"工具限制"标签固化思路，遇到工具误报时优先考虑是否能从工具链上游（构建工具/CDN/响应头）解决

### 2026-06-11 新增

- **bash `set -e` 陷阱** — 全局 `set -e` 让所有命令的失败都退出脚本。`find` 无结果 + `xargs wc -l` 返回非零、统计命令在空目录运行等非关键步骤都会导致脚本提前退出。**修复**：移除全局 `set -e`，只在关键步骤（`git pull`/`npm run build`/`nginx reload`）手动 `exit 1`。非关键步骤用 `|| echo 0` 兜底。
- **bash 子 shell 隔离统计段** — 统计/计数函数用子 shell `( ... )` 包裹，退出码不影响主流程。函数内 `find`/`xargs`/`wc` 等命令都加 `|| echo 0` 兜底，确保不会因为无匹配文件而返回非零。
- **脚本末尾 `exit 0` 保底** — bash 在子 shell 或管道中运行时 `$?` 可能被中间命令覆盖，末尾显式 `exit 0` 确保 webhook 收到成功响应（不依赖 `$?` 的传递链）。
- **stats.json 写入路径与 Docker volume 对齐** — `deploy-auto.sh` 写 `$PROJECT_DIR/stats.json`，API 读 `app/stats.json`。Docker 只挂载 `./app`，根目录文件容器内不可见。**路径必须与 volume 挂载点一致**。
- **静态天数改为动态计算** — stats.json 中 `dev_days` 只有部署时更新，跨天不刷新。改为存 `first_commit_date`，API 每次请求 `math.ceil((now - first) / 86400)` 实时计算。
- **Vue `watch` 响应式数据** — 组件消息/内容依赖 props 数据时，只在 `onMounted` 构建一次会导致数据过时。必须用 `watch` 监听 props 变化后触发 `rebuildMessages()` 重建。
- **CSS 动画 GPU 化规范** — `@keyframes` 中只用 `transform` 和 `opacity`（GPU Composite），禁用 `left`/`margin-top`（Layout）和 `background-position`/`box-shadow`（Paint）。需要隔离定位 transform 时用 wrapper div。
- **同名 `@keyframes` 加载顺序陷阱** — `unplugin-vue-components` 按需加载 EP CSS 晚于自定义 CSS，同名 keyframes 被覆盖。**修复**：用独特前缀（`mb-*`）+ `!important` 覆盖 animation-name，或用 PostCSS 插件在构建时剥离第三方 keyframes。
- **PostCSS 剥离第三方 CSS** — `vite.config.js` 的 `css.postcss.plugins` 可注册自定义 PostCSS 插件，通过 `AtRule` 钩子按名称移除 `@keyframes`、通过 `Declaration` 钩子移除特定属性。

### 2026-06-08 新增

- **Webhint 优化纪律** — webhint 审计工具检查无障碍（ARIA）、性能（Cache-Control/CSS 动画）、安全头（X-XSS-Protection/CSP/Pragma）。修复规则：el-popover 用 `v-model:visible` + `v-if` 控制弹出内容；el-tab-pane 用 `lazy` 避免隐藏标签页包含 focusable 元素；图标按钮必须加 `aria-label`；API 用 `Cache-Control: max-age=0`（webhint 只接受 max-age，不接受 no-store/must-revalidate/Pragma/Expires）；Nginx 用 `proxy_hide_header X-XSS-Protection` 剥离 MinIO 废弃头；CSS 动画用 `transform` 替代 `background-position` 消除 Paint 性能警告
- **el-select aria-label** — Element Plus 内部 input 不继承 placeholder，必须显式加 `aria-label` prop
- **el-progress aria-label** — 进度条组件通过 `$attrs` 传递 `aria-label` 到根元素
- **对象 key 类型陷阱** — JavaScript 对象 key 始终是字符串，`{123: ...}` 变成 `{"123": ...}`。用 `===` 比较数字会失败（`"123" === 123` → false）。`getMemberName`/`getMemberAvatar` 必须用 `==` 宽松比较
- **批量删除限流** — write 限流 30次/分钟 = 1次/2秒。批量操作必须用后端单次 API 请求（`POST /tasks/batch-permanent-delete`），不要前端逐个调用
- **任务列表配对布局** — `pairedGroups` computed 合并 active/done 按 assignee_id 配对，左右对齐。分组函数用 `task.assignee_id != null` 判断（不要用 `||`，会把 0 当 falsy）
- **精确跳转** — 从其他页面跳转到任务列表时，通过 URL query `?assignee_id=xxx` 传递筛选条件，TaskView 在 `onMounted` 中读取 `route.query.assignee_id` 设置 `filters.assignee_id`
- **Nginx charset_types** — `text/html` 是 Nginx 默认值，不需要在 `charset_types` 中重复声明，否则会有 `duplicate MIME type` 警告
- **Nginx CSP 头** — 只有 `frame-ancestors 'self'` 的 CSP 太弱，webhint 认为 unneeded。如果不需要完整 CSP 策略，不要添加
- **Webhook 自动部署正常** — 每次 git push 自动触发 webhook → deploy-auto.sh → git pull → nginx reload。如果部署失败，检查 `/var/log/webhook-deploy.log`
- **IE 兼容性不修** — Vue 3 + Element Plus 本身不支持 IE，所有 IE 兼容性警告（-ms-grid、flex、sticky、8 位颜色值等）直接忽略，不需要加 `-ms-` 前缀
- **webhint http-cache 误报** — Vite content-hash 文件名（`index-f2KQs4XE.js`）是业界标准缓存方案，但 webhint 内置正则只认 `[0-9a-f]` 小写十六进制，不认 Vite 的 base64 格式。已添加 `.hintrc` 自定义 revving 正则，但 Edge DevTools 内置 webhint 不读项目配置，浏览器端无法消除此警告
- **webhint 判断规则** — Error 必须修，Warning 看情况修，Info/Tip 大部分忽略。看源码路径：自己写的代码可以改，第三方库（Element Plus/Vite 打包产物）不能改

### 2026-06-10 新增（宠物系统）

- **CSS keyframe 不能覆盖行内 transform** — walking 动画用 `transform: translateY(-6px)` 覆盖了 bunny 行内 `translate(-50%,-50%) scaleX(...)` 定位 → 兔子闪现。**修复**：动画改用 `margin-top` 或 wrapper div 隔离
- **overflow:hidden 裁切绝对定位气泡** — 欢迎区 `overflow:hidden` 用于裁剪装饰元素，但宠物气泡 `position:absolute` 超出容器被裁切。**修复**：改为 `overflow:visible`，单独给草地 `overflow:hidden`
- **互斥锁所有权限随** — `window.__petSpeaking` 从 boolean 改为记录 `props.type`（谁在说话）。`onLeave` 只清理自己不是说话者的情况，不误清轮播锁
- **bash 数组兼容性** — `EXCLUDE_DIRS=(-not -path "*/node_modules/*")` 在老 bash 上不支持。在函数内用 `set -f` + 字符串变量替代
- **`set -e` + 统计函数** — `find` 无结果 → `xargs wc -l` 返回非零 → `set -e` 退出脚本。统计段用 `set +e` 包裹，结束后恢复
- **props 默认值用 `Number()` 包裹** — `props.totalTasks || 'N'` 在值为 0 时走 `'N'` 分支。用 `Number(props.totalTasks) || 0` 先转数字再判断

### 2026-06-10 新增

- **unplugin-vue-components 不检测 JS 服务调用** — `ElMessageBox.confirm()` / `ElMessage.success()` 等服务 API 不在模板中使用 `<el-message-box>` 标签，`ElementPlusResolver` 无法为其自动导入 CSS。`el-message-box.css` 和 `el-message.css` 完全不会被打包进 dist。**修复**：在 `main.js` 中手动 `import 'element-plus/theme-chalk/el-message.css'` 和 `el-message-box.css`。**验证方法**：`npm run build` 后搜索 dist CSS 是否包含 `.el-message-box`。**教训**：新增使用 Element Plus 服务 API 时，必须手动导入对应 CSS
- **dist 提交必须 `git add -f`** — `web/dist/` 在 `.gitignore` 中，`git add web/dist/` 静默被拦截不报错，只删除旧文件不加新文件 → 线上 404。**每次 `npm run build` 后必须 `git add -f web/dist/` 提交产物**
- **bash 数组防 glob 展开** — 字符串变量 `EXCLUDE_DIRS="-not -path */node_modules/*"` 在函数中 `$EXCLUDE_DIRS` 展开时，`*/node_modules/*` 会被 shell glob 展开为实际文件路径，破坏 `find` 的 `-path` pattern。**修复**：改用 bash 数组 `EXCLUDE_DIRS=(-not -path "*/node_modules/*")` + `"${EXCLUDE_DIRS[@]}"` 展开
- **git log --reverse --max-count=1 陷阱** — `--max-count=1` 先于 `--reverse` 执行，结果永远是 HEAD 而非最早提交。正确做法：`git rev-list --max-parents=0 HEAD` 找根提交后再取日期
- **deploy-auto.sh 自更新局限** — `git pull` 后脚本文件已更新到磁盘，但当前 bash 进程仍在执行旧版内存内容。新版统计逻辑需下次部署（新进程）才能生效。紧急时可 `bash scripts/deploy-auto.sh` 手动重跑
- **PowerShell UTF-8 BOM** — `Set-Content -Encoding UTF8` 写入 UTF-8 BOM（3 字节 `EF BB BF`），Python `json.loads` 默认不处理 → `JSONDecodeError`。修复：PowerShell 用 `[System.Text.UTF8Encoding]::new($false)` 写无 BOM 文件；Python 用 `encoding="utf-8-sig"` 读取
- **stats.json Docker 路径** — Docker volume 只挂载 `./app:/app/app`，项目根 `/app/stats.json` 来自镜像构建（只读、过期）。`stats.json` 必须放在 `app/` 内才可通过 volume 实时更新

### 2026-06-09 新增

- **Nginx 扫描器正则误杀 /webhook** — `^/(...|web|...)` 中的 `web` 匹配到了 `/webhook`，GitHub webhook 被 444 静默关闭。修复：`web` → `web$` 精确匹配。**教训**：扫描器屏蔽正则中所有可能与合法路径前缀重叠的关键词必须加 `$` 锚定
- **sessionStorage 残留脏数据** — 录音结束后 sessionStorage 未清除，刷新页面后幽灵胶囊仍显示。修复：`checkActiveRecording` 始终先查后端 API，后端无 recording 会议时调 `stopRecording()` 清除 sessionStorage。不再信任 sessionStorage 作为首选数据源
- **全局录音器单例** — `useGlobalRecorder.js` 模块级变量管理 MediaRecorder 生命周期，组件销毁不影响录音。AudioRecorder 重构为纯 UI 壳。录音在后台持续进行，导航到其他页面不中断
- **useRecordingState + 浮动胶囊** — MainLayout 右下角浮动脉冲胶囊，显示录音状态 + 会议标题，点击跳转 `/meetings?resume={id}`。sessionStorage 持久化 + 后端 API 验证双重保障
- **meeting.py status 过滤** — 会议列表 API 新增 `status` 查询参数，支持按状态筛选。用于全局录音状态检查（`status=recording`）
- **Nginx 安全防护** — `nginx/conf.d/tunnel.conf` 添加恶意扫描器屏蔽规则，覆盖两个站点（agent.mnb-lab.cn + mnb-lab.cn）。屏蔽类别：敏感文件（.env/.git/.ssh/.aws/.azure）、WordPress 漏洞路径、云凭证探测、开发文件（_next/node_modules）、常见攻击路径（boaform/formLogin/servlet）。使用 `return 444` 静默关闭连接不返回任何响应。正常访问（/、/api、/minio）不受影响
- **Docker Desktop 汉化** — 使用 asxez/DockerDesktop-CN 项目，需替换 3 个文件（Docker Desktop.exe + app.asar + app.asar.unpacked）。4.74.0+ 版本有 asar 完整性校验，必须同时替换 exe。每次 Docker 更新后汉化失效需重装
- **服务器访问日志分析** — 2452 条请求中 88% 是恶意扫描器（WordPress 漏洞、.env 探测、云凭证探测），真实用户只有杜同贺（3 个 IP 同一人不同设备）和少量 mnb-lab.cn 主站访客。202.113.x.x 网段是校园/办公网络

### 2026-06-06 新增

- **语义断句** — VAD + 声纹之外，ASR 后增加基于规则的语义断句（问答切分、转折词、回应词），检测同一段内的对话切换。不使用 AI API，纯本地规则，零延迟。
- **KMeans 强制分裂** — 贪心聚类数=1 但声纹分布标准差>0.15 时，用 sklearn KMeans 硬分 2 簇，解决声纹模型区分度不够的问题。
- **同名聚类检测** — 多个聚类被 identify_speaker_by_embedding 识别为同一人时，自动保留差异为独立发言人。
- **名字校对** — 谐音映射（杜同和→杜同贺）+ 编辑距离≤1 模糊匹配 + 精确匹配三位一体，与成员管理数据库比对。
- **标题自动生成** — "听会"和"未命名会议"标题自动触发 AI 生成，重试 3 次 + 2000 字上下文 + regex 兜底提取。
- **转录合并自动润色** — 同一发言人连续段合并后，自动调 AI 加标点。超长文本（>20字）显示润色后文本。
- **转录发言人手动修改** — `PATCH /meetings/{id}/transcript-speaker` 端点，前端 el-select 下拉选人，合并条用原始索引。
- **会议纪要独立改发言人** — 每条要点/决议点击展开 el-select，改一条不影响其他。
- **AI 润色简化 + JSON 修复** — prompt 缩减到 5 句规则，max_tokens 4096→8192，JSON 截断自动补全。
- **规则标点兜底** — AI 润色失败时，本地规则加标点（问句加？，长句连接词加逗号，句末加。）。
- **VAD 精细化** — 合并阈值 0.3→0.15→0.1s，min_speech 500→300→200ms，min_silence 300→200→100ms。
- **MATCH_THRESHOLD** — 0.55→0.7（余弦距离阈值，更宽松匹配）。
- **Celery solo pool** — 改为 `--pool=solo` 避免 prefork 子进程保留旧代码。
- **modelscope 缓存挂载** — `./models/modelscope:/root/.cache/modelscope`，避免每次重建容器重下载 3D-Speaker。
- **声纹持续学习** — 每次会议识别出的发言人，自动加权平均更新 voice_embedding + voice_sample_count，越用越准。
- **pipeline 日志精简** — 跳过 3D-Speaker pipeline（必然失败），直调底层 model，消除 30+ 行 WARNING/ERROR。
- **认证限流** — 5→20次/分钟，读操作 100→200次/分钟。
- **UI** — 全项目 date-picker 替换、日期北京时区、参与者头像间距、发言人选择器缩小、纪要合并显示。
- **前端性能大幅优化（2026-06-09）** — Nginx gzip + Element Plus 按需导入 + 图标按需注册，主 JS bundle 1.2MB→199KB(-83%)，首屏 gzip ~500KB→~80KB(-84%)。具体变更：
  - **Nginx gzip** — `tunnel.conf` 两个 server block 均开启 gzip（comp_level 5），JS/CSS 传输减 70%
  - **Element Plus 按需导入** — 使用 `unplugin-vue-components` + `ElementPlusResolver({ importStyle: 'css' })`，自动按需导入组件和 CSS。vite.config.js 中配置 Components 插件
  - **main.js 精简** — 移除 `import ElementPlus from 'element-plus'`、`import 'element-plus/dist/index.css'`、`app.use(ElementPlus)`、全量图标注册（`import *` + `app.component` 循环）
  - **ElMessage/ElMessageBox** — 这些是 service 不是组件，在各文件中手动 `import { ElMessage } from 'element-plus'` 的写法保持不变，resolver 会自动优化导入路径
  - **动态 import 不能保留** — `import('element-plus').then(...)` 无法被 resolver 转换，必须改为静态 import（如 `AudioRecorder.vue` 的 `ElMessageBox`）
  - **CSS 拆分** — Element Plus 组件 CSS 自动拆分为 50+ 个独立文件，仅在对应组件渲染时加载，不再单一 355KB CSS 文件
  - **dist 构建后检查** — 修改 vite.config.js 或 main.js 后必须 `npm run build` 并 `git add -f web/dist/` 提交 dist。验证：主 bundle 应 < 300KB（而非 1.2MB）
  - **禁止回退** — 任何时候都不要把 `import ElementPlus from 'element-plus'` 或全量 CSS import 加回 main.js，也不要移除 vite.config.js 的 Components 插件，否则 bundle 会膨胀回 1.2MB
- **知识库列表 API 不能返回完整 content**（2026-06-09）— `GET /knowledge` 每页 20 条，若每条含完整文档内容会导致响应体数 MB，穿过 FRP 隧道时触发 HTTP/2 帧错误（`ERR_HTTP2_PROTOCOL_ERROR`）。**修复**：列表 API 使用 `KnowledgeListItem` schema（不含 `content`/`formatted_content`），改为 `snippet` 字段（content 前 200 字符），卡片预览用 `item.summary || item.snippet`。详情 API `GET /knowledge/{id}` 不受影响
- **Nginx /api 不能加 `Connection: upgrade`**（2026-06-09）— 该 header 仅用于 WebSocket 升级（`/ws` location），放在 `/api` 中每个请求都要求后端升级连接，会干扰 HTTP/2 帧封装。同时添加 `proxy_buffer_size 16k` + `proxy_buffers 8 64k` + `proxy_max_temp_file_size 128m` 防止大响应撑爆缓冲区
- **Element Plus 图标按需导入注意事项**（2026-06-09）— `unplugin-vue-components` 可以解析模板中的 `<IconName />` 静态标签，但**无法解析**以下两种用法，必须显式 `import { X } from '@element-plus/icons-vue'`：
  1. **动态组件**：`<component :is="item.meta.icon" />` — 编译时看不到字符串值
  2. **某些图标**：`Aim`、`Bell` 等 — resolver 可能漏解析，必须在 script 中显式 import
  - MainLayout.vue 现已导入全部 14 个图标（Aim/Bell/ArrowRight/DataBoard + 10 个路由 meta 图标）

## 开发注意事项（历史）

- **重构子组件不能丢样式**（2026-06-05 教训）— 把 Element Plus 组件（el-table、el-card）换成裸 div 时必须手写等效 CSS，否则 UI 变成无样式纯文本。抽完后对比原始 UI 确保视觉一致
- 数据库模型使用 PostgreSQL 特有类型（ARRAY, Vector），不可直接切换到 SQLite
- 前端 ProjectView 调用了 DELETE /projects/{id}（已实现），MeetingView 的 PUT/DELETE 端点已实现
- 无用依赖已清理（langchain, chromadb, sentence-transformers, pyannote 已移除，minio 已恢复用于文件上传）
- 登录页硬编码账号已移除，改为"请联系管理员获取账号密码"
- Agent 的 `generate_project_plan` 工具会调用 Claude API 两次（生成计划 + 对话），注意 token 消耗
- 企业微信已上线，腾讯会议凭据待配置（详见 ROADMAP.md）
- 部署架构：云服务器跑 Nginx+FRP+Webhook(9001)，本地电脑跑全部 Docker 服务，FRP 穿透 8000/9000/2222 端口
- Webhook 自动部署：GitHub push → Nginx /webhook 代理 → webhook.py (9001) → deploy-auto.sh → npm build → nginx reload，已端到端验证
- Claude API 使用代理地址（`CLAUDE_BASE_URL`），支持第三方 API 中转
- **文件上传 prefix 参数** — `app/api/v1/upload.py` 中 `prefix` 使用 `Form("uploads")` 而非 `Query`，因为前端通过 FormData 发送该字段。若误用 `Query`，prefix 会静默回退到默认值 `"uploads"`，导致头像等文件存到错误前缀
- **铃铛提醒去重** — `_create_default_reminders()` 为每个任务创建 1-2 个 reminder（分级预警），但通知 API 必须按 task 去重。`GET /reminders` 使用 PostgreSQL `DISTINCT ON (task_id)` + `ORDER BY task_id, remind_at` 保留最早提醒，`pending-count` 使用 `COUNT(DISTINCT task_id)`。任何时候修改提醒相关查询，都要确保前端铃铛不会因一个任务多个 reminder 而重复显示
- **云服务器资源限制** — 阿里云 2核2G，严禁在云服务器上运行 `npm run build`（Next.js 构建会 OOM 导致 SSH 断开）。所有前端构建在本地 Windows（32核+GPU）完成，静态产物上传到服务器
- **前端 dist 构建提交** — 修改 `web/src/` 下的 Vue 源码后必须执行 `npm run build`（`web/` 目录下）并 `git add -f web/dist/` 提交 dist（dist 在 `.gitignore` 中，需 `-f` 强制添加），否则线上部署的仍是旧版静态文件。服务器通过 git 已提交的 dist 文件提供服务，不在服务器上构建
- **同服多站点** — 云服务器同时托管 `agent.mnb-lab.cn` 和 `mnb-lab.cn`，通过 nginx `server_name` 区分，各自独立 SSL 证书（Let's Encrypt certbot --expand 扩展）。新增站点时必须：1) SSL 证书覆盖新域名 2) 添加 HTTPS server block 3) 确保 `^~` 修饰符避免 regex location 拦截
- **多站点部署隔离** — `agent.mnb-lab.cn` 是 Vite SPA（构建轻量），`mnb-lab.cn` 是 Next.js 静态导出（201MB 图片，构建吃资源）。两者 Nginx 配置在同一文件 `/etc/nginx/conf.d/default.conf`，修改时必须确保不影响另一个站点。`deploy-auto.sh` 仅处理 agent 项目，mnb-lab 需手动构建部署。两个站点共享 FRP 隧道的 MinIO 端口（9000），minio location 使用 `^~` 修饰符防止静态资源 regex 拦截图片请求
- **Nginx 配置必须 Git 同步** — `deploy-auto.sh` 每次部署时将 `nginx/conf.d/tunnel.conf` 直接覆盖到 `/etc/nginx/conf.d/default.conf`。在云服务器上对 nginx 配置的任何手动修改（如 root 路径、SSL 证书路径、proxy_pass 目标等），必须同步更新到 Git 仓库的 `tunnel.conf`，否则下次 webhook 部署会覆盖丢失，导致站点 500。这条规则没有例外。
- **头像上传自动保存** — `web/src/views/SettingsView.vue` 的 `handleAvatarUpload` 上传成功后立即调 `PUT /api/v1/auth/profile` 持久化，用户无需手动点"保存资料"。HEIC 格式（iPhone 默认拍照格式）Canvas 不支持压缩，使用 try/catch 回退原文件上传
- **头像上传 Content-Type** — 切勿手动设置 `Content-Type: multipart/form-data`，FormData 需要 boundary 参数（如 `multipart/form-data; boundary=----WebKitFormBoundaryxxx`），手动覆盖后缺少 boundary 导致服务器无法解析。应让 axios 自动检测并设置正确的 Content-Type（含 boundary）
- **头像上传分步容错** — 上传涉及 3 个串行请求（POST /upload → PUT /auth/profile → GET /auth/me），若包在同一个 try/catch 中，第三步超时会阻止 localStorage 写入，导致刷新后头像回退。必须拆分为独立 try/catch：upload+save 成功后先更新 localStorage，GET /auth/me 单独容错，失败时用本地 URL 兜底
- **Nginx 多站点配置必须完整** — `nginx/conf.d/tunnel.conf` 每次部署时会被 `deploy-auto.sh` 直接覆盖到 `/etc/nginx/conf.d/default.conf`，因此这个文件必须同时包含 `agent.mnb-lab.cn` 和 `mnb-lab.cn`（+ `www.mnb-lab.cn`）的完整 server block。修改 `tunnel.conf` 后务必验证两个站点的 `server_name` 和 `root` 都正确，否则同服另一个站点会被清掉
- **侧边栏导航必须使用绝对路径** — `MainLayout.vue` 中 `el-menu-item` 的 `:index` 和移动端 `router.push` 都必须用 `'/' + route.path`（绝对路径），否则在 `/knowledge` 等嵌套路由下点击其他菜单项会解析为相对路径（如 `/knowledge/dashboard`），误匹配 `/knowledge/:id` 路由，导致 KnowledgeDetailView 错误挂载并请求不存在的 API（422）
- **menuRoutes 过滤非导航路由** — `menuRoutes` 计算属性需过滤 `r.meta?.icon`，确保 `knowledge/:id` 等详情页路由（无 icon）不出现在侧边栏
- **Vue 组件 import 完整性** — 修改 Vue 组件时，在 `<script setup>` 中添加对 `watch`、`nextTick`、`onUnmounted` 等新 API 调用后，必须同步更新 `import { ... } from 'vue'` 语句，否则生产构建后运行时抛出 `ReferenceError: xxx is not defined` 导致组件白屏
- **Vue 组件变量名笔误**（2026-06-02 教训，commit `fbffb88`）— `<script setup>` 内**对未声明标识符的引用**（如 `onUnmounted` 内写 `chartInstance` 但实际变量是 `entityChartInstance`）也是生产 bug：HMR/esbuild 不会拦下、Vite 生产构建不报 undefined 引用，**只有运行到对应生命周期才抛 `ReferenceError`**。KnowledgeView 路由到实体图谱 tab 再离开时 `onUnmounted` 触发，组件白屏。**防御**：① 同文件内多 echarts 实例要严格命名（`entityChartInstance` / `meetingChartInstance`），引用前先看顶部声明；② `onMounted` / `onUnmounted` / `watch` / `nextTick` 回调内引用的变量必须二次核对声明名；③ 可在 `web/src/views/**/onUnmounted` 加 eslint `no-undef` 规则强制
- **Webhook GitHub 连通性问题** — 阿里云服务器偶发无法连接 GitHub（TLS/GnuTLS 错误或超时），GitHub webhook 交付失败但代码已 push。此时可通过 SSH 到服务器手动触发：`curl -s -X POST http://localhost:9001/webhook -H 'Content-Type: application/json' -H 'X-GitHub-Event: push' -H 'X-Hub-Signature-256: sha256=<hmac>' -d '{"ref":"refs/heads/main","pusher":{"name":"fix"},"commits":[{"id":"fix"}]}'`（HMAC 签名用 `echo -n '<payload>' | openssl dgst -sha256 -hmac "<WEBHOOK_SECRET>"` 生成）
- **deploy-auto.sh 不重启 Python 后端** — 脚本只重载 Nginx，Python 代码变更（路由注册、新模块等）需要手动 `docker compose restart` 才能生效。数据库新列（ALTER TABLE）也需要手动执行
- **模型依赖安装** — modelscope（3D-Speaker）有大量传递依赖（addict, datasets, simplejson, sortedcontainers, **soundfile** 等），pip install 时可能遗漏。Docker 内运行 `pip install addict datasets simplejson sortedcontainers soundfile` 补全。**所有这些依赖必须固化到 `requirements.txt`**（不要只容器内临时安装，否则下次 `docker compose build` 会丢失）。torch + CUDA 包约 2GB，首次下载耗时较长
- **声纹模型懒加载** — 3D-Speaker 首次调用时从 ModelScope Hub 下载模型（~100MB），需要网络连接。下载后缓存在 `/root/.cache/modelscope/`。**正确模型 ID：`iic/speech_eres2net_sv_zh-cn_16k-common`（旧 ID `iic/speech_eres2net_sv_zh-cn_3dspeaker_16k` 已下线，加载会 404）**
- **3D-Speaker pipeline 输入类型限制** — `speaker_verification` pipeline 只接受「音频文件路径」或「numpy ndarray」，**不接受 bytes / BytesIO**。代码必须用 `tempfile.NamedTemporaryFile` 写 wav 再传路径
- **3D-Speaker 模型输入是 1D tensor** — `ERes2Net_Pipeline.preprocess` 接收 1D numpy array，模型内部自己加 batch 维。直接调 `model(x)` 必须传 1D（不要 `.unsqueeze(0)`）。实测：1D 和 2D 输出都是 `(1, 192)`，结果一样，但 1D 符合官方规范，避免无谓转换
- **声纹嵌入维度 192（不是 256）** — ERes2Net 实际输出 192 维。`voiceprint_service.py:EMBEDDING_DIM=192`，`Member.voice_embedding=Column(Vector(192))`。历史代码错误写 256，靠 `emb[:EMBEDDING_DIM]` 截断掩盖，必须保持一致
- **numpy.float32 序列化** — pgvector 读出的 `m.voice_embedding` 是 numpy array，`list()` 转后元素仍是 numpy.float32。FastAPI `jsonable_encoder` 不能处理 → 500 错误。**所有返回 embedding 的 API 必须用 `.tolist()` 转 python float 列表**
- **声纹前后端阈值必须一致** — 后端 `MATCH_THRESHOLD=0.55`（`voiceprint_service.py`）+ 前端 `markLine: yAxis: 0.55`（`ConfidenceChart.vue`）。**0.45 是误读**（早期前端写错，markLine 显示为阈值参考线而非真实数据）。修改时两边同步
- **声纹会议 live WS 静默断开**（2026-06-02 教训）— `app/api/v1/voice.py` 的 `meeting_live_ws` 和 `_run_live_loop` 函数**必须有顶层 try/except 兜底**。VAD 加载 / `transcript_history` 发送 / `pubsub.subscribe` / `await websocket.send_json` 在客户端断后抛 `ConnectionClosed` 等任何异常，如果只捕获 `WebSocketDisconnect` 会逃逸到 Uvicorn 静默关闭 WS，**没有错误日志**。**修复**：`meeting_live_ws` 顶层加 `try/except WebSocketDisconnect/Exception`（后者 `logger.error(..., exc_info=True)` + `await websocket.close(code=1011)`）；`_run_live_loop` 拆出 `_live_loop_inner` + outer try/except 同样处理。验证：改后 WS live 维持 11+ 秒，audio_level 推送正常
- **audioLevels 必须解耦 activeSpeaker**（2026-06-02 教训）— `MeetingRoom.vue` 的 `onMessage` 处理 `audio_level` 时，**之前**只在 `activeSpeaker !== null` 时写入 `audioLevels[activeId]`。但 `activeSpeaker` 只在收到 transcript 且 `speaker_confidence > 0.45` 时才设置 — 如果后端没发 transcript（比如 VAD 静默），activeSpeaker 永远 null，5 根声波条永远不跳动。**修复**：用 `key = activeId !== null ? String(activeId) : 'self'` 兜底；`LiveSpeakerPanel.getBarHeight` 读不到 activeSpeakerId 时降级到 `props.audioLevels['self']`
- **Progress WS snapshot 不能发 null**（2026-06-02 教训）— `meeting_progress.py:_send_snapshot` 之前**无条件**发 `{"type": "progress_snapshot", "data": snapshot}`，当 `get_progress(meeting_id)` 返回 None 时 `data=null`，前端 `useMeetingProgress.js` 访问 `msg.data.status` 抛 `TypeError: Cannot read properties of null (reading 'status')`，ProcessingDialog 进度条卡住。**修复**：后端 snapshot 为 None 时**不发**该消息；前端用 `if (msg.data && typeof msg.data === 'object')` 防御性检查。**经验**：WS 推送层不要把 `None` 当作"有效消息"发送，要么不发，要么发空对象 `{}` 让接收方降级处理
- **Whisper 反幻觉必须三层防护**（2026-06-02 教训，2026-06-03 重构）— faster-whisper 在静音/低能量片段会**臆造**训练集记忆（YouTube 结束语"B 站风格"如"明镜与点点""点赞订阅转发打赏"）。三层防护缺一不可：
  1. **whisper_server.py**（`app/whisper_server.py`）— `condition_on_previous_text=False` + `no_speech_threshold=0.6` + `temperature=0`，并**过滤** `segment.no_speech_prob > 0.6` 的 segment
  2. **本地模型 fallback**（`app/voice/asr.py:_transcribe_local`）— 同样三件套
  3. **后端三重判定**（`app/api/v1/voice.py`，2026-06-03 重构）— 替代旧 NOISE_PATTERNS 单一黑名单：
     - `HALLUCINATION_STRONG`（99% 幻觉词如"明镜与点点""感谢观看"）→ **无条件过滤**
     - `HALLUCINATION_WEAK`（可能是真话如"12345""测试""嗯"）→ **仅在音频能量低时过滤**（RMS < 0.02）
     - `pipeline.process_audio` 返回 `audio_rms` 字段供判定
  4. **关闭 Whisper 内置 VAD**（2026-06-03）— 已有 silero-vad 做 VAD，双重 VAD 互相干扰导致丢语音段。`vad_filter=False`
- **后端七重过滤**（`app/api/v1/voice.py:_run_live_loop`，2026-06-02 三次扩展）— NOISE_PATTERNS 之外再加：
  1. segment 时长 < 0.3s 视为噪声
  2. 文本去标点后 < 2 字符视为短噪音
  3. `_is_repetitive_text` 检测同一短子串重复（1 字 ≥ 4，2-6 字 ≥ 3，**先去标点**避免"，""。"等触发）
  4. `_is_alphanumeric_run` 检测字母+数字纯串（whisper 臆造"G6G7G10G11..."）
  5. `_is_gibberish` 检测长无意义乱码（30+ 字符但不含任何"虚词+代词+动作词"）
  6. `_is_sentence_repetitive` 检测完整句子重复 ≥ 3 次（避免误杀"2分钟后...2分钟后..."菜谱）

  七层叠加才能彻底压制 faster-whisper 在低能量片段的臆造行为。**36/36 单元测试通过**（含"M1结果中心营业G6G7..."等严重 hallucination + "微纳米气泡的zeta电位是表征..."等真实专业句）。**NOISE_PATTERNS 维护纪律**：单字（如"感谢"）太宽会误杀正常对话（如"感谢你的帮助"），只放复合关键词（"感谢观看"）
- **声纹模型加载失败必须容错**（2026-06-03 教训）— `voiceprint_service._load_pipeline()` 之前失败直接 `raise`，导致整个 WS 连接崩溃。改为：失败时设 `self._pipeline = None`，`extract_embedding` 检测到 None 时返回零向量，`identify_speaker` 检测到全零 embedding 时返回 unknown。**WS 不会因声纹模型加载失败而断开**。同理，进入通话时前端先检查 `/voiceprint/enrolled` 端点，如果 0 人录入则弹 toast 引导用户去成员管理页面录入
- **TimelineScrubber duration 不能等于 elapsed**（2026-06-02 教训）— `MeetingRoom.vue` 中 `meetingDuration` 之前用 `elapsed` 赋值，导致 el-slider 的 `max=currentTs`，用户**无法拖到未来时间点**（slider 只能停在自己当前位置）。**修复**：`meetingDuration = Math.max(MAX_MEETING_DURATION_SEC, elapsed + 60)`，给个合理上限 30 分钟，让 slider 真的能拖。**注意**：`onJumpTs` 只更新 currentTs 不真 seek 转录列表是设计妥协（Wave 3b 注释明确说明），至少 slider 要能响应用户操作
- **Celery worker 启动时 [tasks] 列表不完整**（2026-06-02 教训）— `app/core/celery.py` 用 `celery_app.autodiscover_tasks([...])` 让 worker 自动发现任务。**Celery 5+ 默认 `related_name='tasks'`**，会尝试 `from {package}.tasks import *`（找 `tasks.py` 子模块），但本项目任务直接在主模块里（如 `post_meeting_tasks.py`），找不到子模块**静默失败**。结果：worker 启动时 [tasks] 列表**缺任务**（如 `post_meeting_process`），任务入 Redis 队列后**永远不被消费**，前端 progress 卡死。**修复**：
  1. `celery.py` 改用显式 `celery_app.conf.imports = [...]` 强制 import 主模块
  2. `autodiscover_tasks(..., related_name=None)` 保留作 fallback
  3. `docker-compose.yml` 给 celery-worker 加 `./app:/app/app` volume 挂载（app 容器已有，celery 没有），让代码改动即时生效不必 rebuild 25GB 镜像。**诊断命令**：`docker logs microbubble-agent-celery-worker-1 2>&1 | grep -A 12 "^\[tasks\]$"` 看实际注册的任务列表，缺哪个就在 imports 列表加哪个
- **Celery 任务失败必须推 progress_update**（2026-06-02 教训）— `post_meeting_tasks.py` 之前外层 `try/except` 失败时只 return error dict，**前端 WS 收不到消息**，ProcessingDialog 永远卡在初始 5 步列表。**修复**：失败时在 fail_loop 里 `update_progress(..., status="error", detail=...)`，前端 `useMeetingProgress.js` 会看到 status=error 关闭弹窗并提示
- **发言者检测格式** — `_parse_summary_format()` 识别 `发言人：`/`参会人：` 等字段；`_quick_parse_speakers()` 识别 `【名称】` 格式；NON_SPEAKER 黑名单过滤文档结构标签；过滤后发言者 < 2 人时回退 Claude AI 检测
- **WebSocket 认证** — `/ws/meeting/{id}/live` 需要在 URL query param 中传 `?token=xxx`，Nginx `/api` location 需要 Upgrade/Connection 头支持 WebSocket
- **数据库列迁移** — `Base.metadata.create_all()` 不会给已有表添加新列，Member/Meeting 新增的 voice_embedding, speaker_mapping 等列需要手动 ALTER TABLE。**2026-06-04 教训**：`Meeting` 模型新增 `audio_url`/`audio_duration`/`recording_started_at`/`recording_ended_at` 4 列后，创建会议 500 报 `column "audio_url" of relation "meetings" does not exist`。**防御**：新增模型列后必须立即 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`，不要依赖 `create_all`
- **垃圾桶软删除** — `deleted_at` 字段标记软删除，3天后 Celery 定时任务自动永久删除（beat schedule 1h，最大延迟 1h）。垃圾桶 API `include_deleted=true` 必须加 `deleted_at.isnot(None)`，否则会返回活跃任务。提醒查询必须过滤 `Task.deleted_at.is_(None)`
- **垃圾桶自动清理 Celery 任务**（2026-06-03 commit `dc93bff` + `47fb2c9`）— 必须同步 3 处：
  1. `app.services.task_service.auto_purge_trash_task` 函数加 `@celery_app.task(name=...)` 装饰器（缺装饰器 worker 找不到函数）
  2. `app/core/celery.py` 的 `imports` 列表 + `autodiscover_tasks` 列表都要加 `"app.services.task_service"`（缺 import 模块不被加载）
  3. `docker-compose.yml` **celery-beat 服务也要加 `./app:/app/app` volume 挂载**（与 worker 一致；2026-06-02 修复时只补了 worker，漏了 beat 导致 beat 跑构建时烧进镜像的旧代码，schedule 改动必须 rebuild 25GB 镜像才能生效）
- **垃圾桶自动清理任务必须用独立 NullPool 引擎**（commit `dc93bff`）— 不能用全局 `async_session`，否则触发 "Future attached to different loop" 或 "another operation is in progress" 错误。正确模式（与 reminder_service.process_reminders_task 一致）：
  ```python
  engine = create_async_engine(
      settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
      poolclass=NullPool,
  )
  session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
  async with session_factory() as db:
      ...
  await engine.dispose()  # finally
  ```
- **Beat 调度粒度要与用户期望对齐**（2026-06-03 commit `47fb2c9`）— 4h 调度对 3 天 retention 太粗，用户看到 `auto_delete_at` 过期但任务还在（最坏等 4h），困惑。**1h 是"准点清理"的合理上限**（retention 3 天时仅 1.4% 误差）。如未来 retention 调到 7 天可放宽到 2h，但不要超过 1h（UX 边界）
- **Python 模块缓存**（2026-06-03 教训）— volume 挂载 `./app:/app/app` 让新文件**可见**，但**不重载已 import 的模块**。代码改完后必须 `docker compose restart worker`，否则 worker 还在用旧代码（错误日志指向旧行号是好线索）。Celery prefork worker 的 fork 子进程不共享主进程的模块更新
- **auto_delete_at 单一数据源**（2026-06-03 commit `b91e429`）— 后端 `list_tasks` / `get_task` 路由用 `setattr` 附加 `auto_delete_at = deleted_at + timedelta(days=settings.TRASH_RETENTION_DAYS)`，不持久化到 DB（避免迁移成本）。前端用这个字段显示倒计时，**前端不再硬编码 retention 天数**，与 Celery 清理任务共享同一配置，**不会漂移**
- **声纹会议系统 3a/3b 新增注意事项**（2026-06-01~02）：
  - **agenda 字段错位** — `agent/core.py` 早期版本错把议程列表写到 `description` 字段，导致议程链路断裂。MeetingCreate 时必须传入 `agenda` 形参（不是塞到 description），`PATCH /agenda` 端点更新 `Meeting.agenda` 字段。检查 `app/schemas/meeting.py` 的 `MeetingCreate` 包含 `agenda: List[str]` 字段
  - **activeSpeaker 置信度阈值** — `useMeetingRoomWS.onTranscript` 处理 speaker 切换时必须加 `speaker_confidence > 0.45` 判断，否则低置信度误识别会导致 activeSpeaker 在多人时频繁跳变
  - **Float32 → Int16 PCM 转换位置** — `useAudioCapture` 输出 Float32（AudioWorklet 标准），WS 协议用 Int16 PCM，转换放在 MeetingRoom 层（不在 capture 层），避免 capture 被多种协议复用时受污染
  - **VAD per-instance** — silero-vad 必须 per-pipeline 实例化（不能全局单例），否则 asyncio 事件循环绑定冲突会导致 VAD 异常。`MeetingPipeline` 通过依赖注入接收 VAD 实例
  - **VoiceprintHistory mapper 错误** — `app/models/__init__.py` 必须显式 `import` 所有新模型（含 `VoiceprintHistory`、`MeetingTemplate`），否则 SQLAlchemy mapper 初始化失败导致 500。新增模型后第一件事是检查 `__init__.py` 导入链
  - **HNSW 索引** — `members.voice_embedding` 和 `meetings.embedding` 必须建 HNSW 索引（`vector_cosine_ops`），否则声纹匹配和跨会议搜索在大数据量下会超时。迁移 `CREATE INDEX ... USING hnsw (embedding vector_cosine_ops)`
  - **多设备 Redis pub/sub** — 通话中 transcript/ai_response/audio_archive 事件通过 Redis pub/sub 跨设备广播，buffer 200 条上限 + LTRIM + 24h TTL。新加入设备自动从 MinIO 同步缺失音频片段
  - **audio_level 推送频率** — `/live` 端点 0.1s 间隔推送当前 active speaker 的音量级别，前端 5 根声波条根据 `audioLevels[memberId]` 实时跳动。频率不能太低（看起来不跟嘴），不能太高（WS 流量爆炸）
  - **会议模板 4 内置种子** — DB 迁移 016 启动时自动 seed 4 个内置模板（组会/一对一/立项会/自由），幂等。`app/seed/` 目录新增模板种子
  - **议程 PATCH 端点** — `PATCH /meetings/{id}/agenda` 独立端点（不是 PUT 整个 meeting），避免误改其他字段。MeetingService.update_agenda() 方法专门处理
- **声纹系统线上修复（2026-06-02 5 个 commit）**：
  - **WS 闪烁真正根因是 UnboundLocalError** — `app/api/v1/voice.py:_run_live_loop` 函数内 `if msg_type=="ai_command": import asyncio` 让 Python 把整个函数的 `asyncio` 当局部变量。后续 `asyncio.QueueFull` 抛 UnboundLocalError → WS 服务端崩 → 自动重连 → 又崩 → 循环。**修复：删除函数内冗余 `import asyncio`（文件顶部已有）**。前端 `useMeetingRoomWS` 重连策略健壮化作为补充（不要重置 attempt、加 30s 退避封顶）
  - **微信 enroll_voice 状态机** — Agent `enroll_voice` 工具在 `channel_user_id`（微信会话）模式下写 Redis `wechat:pending_enroll:{user_id}`（5min TTL）。`wechat/handler._handle_voice` 检测到 pending → 自动下载微信语音 → ffmpeg 转 16kHz mono float32 → `voiceprint_service.enroll_member` → 清除 pending → 回复"✅ 声纹录入成功"
  - **声纹维度 256→192** — 连带修改：模型 ID 换 `iic/speech_eres2net_sv_zh-cn_16k-common`、迁移 017 改列类型、Alembic 链断点修复（010 的 down_revision 指向 009 而非 008 形成两个 head）、alembic_version.version_num VARCHAR(32) 长度限制（revision 名要用短名 ≤ 32 字符）
  - **3D-Speaker pipeline 输入** — `self._pipeline(wav_bytes)` 抛 `The input type is restricted to audio address and nump array`。修复：写临时文件后传路径。**声纹服务加 3 层回退 + 底层 model 兜底**（pipeline(路径) → pipeline(numpy) → self._pipeline.model.forward()）
  - **移动端弹窗错位** — `MemberView .member-card:hover { transform: translateY(-4px) }` 创建 containing block 干扰 `el-dialog` 定位。修复：改用 `margin-top: -4px`（不创建 containing block）+ `VoiceprintEnrollDialog` 显式 `append-to-body :lock-scroll="true" top="5vh"`
  - **头像裸路径 bug** — 早期 `upload.py` 用 `Query("uploads")` 读 `prefix`，导致 `prefix=avatars` 静默回退到 `uploads`，DB 留下 `avatars/xxx` 裸路径数据。`el-avatar :src="member.avatar"` 直接用，浏览器拼成 `/avatars/xxx` → 404。前端 `member.js` store 加 `normalizeAvatarUrl` 兜底（裸路径 → `/minio/microbubble/avatars/xxx` 相对路径）
  - **fingerprint API 缓存** — 浏览器缓存旧空响应导致录入后看不到。API 用 `Response` 参数注入 `Cache-Control: no-store, no-cache, must-revalidate, max-age=0` + `Pragma: no-cache` + `Expires: 0` 三重禁缓存
  - **「置信度 0.45 直线」是 markLine 误读** — 用户看到 ConfidenceChart 里的 0.45 水平线以为是置信度数据，但实际是 `markLine: yAxis: 0.45` 阈值参考线（红色虚线）。**真实数据看 `voiceprint_history` 表**。同一历史 commit 顺手把 markLine 从 0.45 统一成 0.55（与后端 `MATCH_THRESHOLD` 一致）
  - **ERes2Net 模型实测表现**（2026-06-02 合成语音测试）— intra（同人 2 次录音）cos=0.99 ✅，inter（不同人）cos=0.92-0.97（合成信号偏高，真实人声会更低）。区分度 0.05 偏小，**实际识别需要多人会议反复调阈值**
  - **修改声纹提取时务必清旧 embedding** — 提取逻辑变更（输入维度、模型路径、归一化）后，DB 里旧 embedding 是用旧逻辑算的，跟新逻辑不兼容。**必须 `UPDATE members SET voice_embedding=NULL, voice_enrolled_at=NULL, voice_sample_count=0` 让用户重新录入**
- **VoiceTestDialog 麦克风误报（2026-06-04 教训）** — `getUserMedia` 成功后创建 `AudioContext({ sampleRate: 16000 })` 在部分手机浏览器（Safari/微信）失败，被外层 catch 误报为"麦克风权限被拒绝"。**关键对比**：`VoiceprintEnrollDialog` 不需要 AudioContext，所以录入正常但测试报错。**修复**：① `getUserMedia` 和 `AudioContext` 各自独立 try/catch ② AudioContext 失败跳过音量可视化，录音不受影响 ③ 添加 `webkitAudioContext` 前缀 + `resume()` 处理 suspended 状态 ④ 错误信息精确区分 `NotAllowedError`/`NotFoundError`/其他。**教训**：catch 块不要把所有错误统一显示为同一消息，否则用户看到的是误导性提示
- **声纹会议系统全面修复教训（2026-06-03 8 commit）**：
  - **enrolled API 返回格式** — 后端 `/voiceprint/enrolled` 返回 `{"members": [...]}` 而非数组，前端 `Array.isArray(vpData)` 永远 false。**修复**：`vpData.members`
  - **hangup 不能立即 disconnect** — `sendHangup()` 发完消息后立即 `disconnect()` 导致服务器还没处理 hangup 就断 WS。**修复**：等服务器主动关闭 WS（`watch(connected)` 检测断开再 emit call-ended），5s 超时兜底
  - **batch_polisher 必须传参** — `_run_live_loop` 创建 `batch_polisher` 但没传给 `_live_loop_inner`，hangup 处理访问时 NameError。**教训**：内部函数引用的外部变量必须显式传参
  - **Celery 后处理不能复用主 app 连接池** — `async_session` 和 `redis_pool` 在模块导入时创建，绑定主 app 事件循环。Celery worker 的 `asyncio.new_event_loop()` 创建新循环，复用旧连接池报 `Future attached to different loop` / `Event loop is closed`。**修复**：参照 `reminder_service.py` 模式，Celery 任务内创建独立引擎（`NullPool`）+ 独立 Redis 连接（`aioredis.from_url`），`update_progress` 加 `redis_override` 参数
  - **ProcessingDialog 不要全屏** — 全屏会遮挡侧边栏，改为 500px 弹窗
  - **反幻觉重复句阈值** — `_is_sentence_repetitive` 从 ≥3 降到 ≥2 次重复即过滤（Whisper 幻觉常重复 2 次）
  - **低置信度短文本过滤** — 声纹置信度 < 0.1 + 文本 < 10 字，直接过滤（"温暖气泡燃烧""临时发表展示"等 Whisper 幻觉）
- **本地运维脚本坑**（2026-06-02）：
  - **`$ErrorActionPreference = "Stop"` 会抛 native stderr** — docker compose 输出 `POSTGRES_PASSWORD not set` 等 warning 时会被 PowerShell 当 Error 抛异常，导致整个 try/catch 走 catch 分支。PowerShell 脚本必须用 `$ErrorActionPreference = "Continue"`，需要严格检查时用 `if (...) { throw }` 显式控制
  - **`2>&1` 污染 `$LASTEXITCODE`** — PowerShell 管道最后一节的退出码会覆盖 `$LASTEXITCODE`。要抑制 stderr 又保留 native command 退出码，用 `2>$null`（PowerShell 专属）而非 `2>&1 | Out-Null`
  - **`$input` 是自动变量** — 手动赋值会产生副作用。FileStream 等用 `$inputStream`
  - **PSScriptAnalyzer 警告 `PSUseApprovedVerbs`** — 自定义函数动词必须是 PowerShell 批准动词。`Speak-Alert` → `Send-Alert`，`Print-Line` → `Write-Line`
  - **TTS 中文语音** — `Microsoft Huihui Desktop` 不一定存在。必须 `try { SelectVoice } catch {}` 优雅降级
  - **Watchdog 告警去重** — 不要每次跑都 TTS 吼叫。用 `last-state.json` 记录上次状态，只在"正常 → 异常"切换时告警
  - **PowerShell 5.1 vs 7+ 兼容** — `ConvertFrom-Json -AsHashtable` 是 6.1+ 才有。统一用 `[ordered]@{...} | ConvertTo-Json` 模式构造 JSON
  - **`.bat` 中的 `^` 续行符** — 在 cmd.exe 中正确，但 **PowerShell 调用 .bat** 时 `& "x.bat"` 会让 PowerShell 先解析 `^` 当续行，导致 bat 内部命令被截断。修复：bat 内部用单行命令（无 `^`），或 PowerShell 调时用 `cmd /c "x.bat"`
  - **`.bat` 单行 `if/else` 不能嵌套括号** — `if errorlevel 1 (echo FAIL) else (echo OK (more))` 中 else 分支的括号会被 CMD 误解析为 if 结束。修复：必须用多行 `if/else`，每个分支独立括号块
  - **PowerShell 中 `\` 是转义字符** — `G:\path\to\file` 中 `\t` 会被解释为 Tab，`\b` 为退格。**路径一律用单引号** `'G:\path'` 或反引号转义 `'G:\path'`，避免路径断行
  - **PowerShell 多行粘贴 (`>>`)** — 容易触发"命令语法不正确"误报。**逐条执行**或把多命令写进 .ps1 脚本。不要直接粘贴带 `& | Out-Null` 的多行
  - **从 PowerShell 调 `.bat` 用 `cmd /c`** — 避免 PowerShell 误解析 bat 内的特殊字符。`cmd /c "scripts\install-local-ops.bat"` 是最稳健的跨 shell 调用方式
  - **schtasks 直接调 powershell.exe 会弹窗**（2026-06-02 教训）— 用当前用户身份注册 schtasks 时，Task Scheduler 在交互式会话启动 `powershell.exe -File xxx.ps1` **会创建可见控制台窗口**，脚本跑完才关闭。如果脚本 2-3 秒跑完（如 watchdog），用户会看到"窗口闪一下然后消失"，体验差。**修复**：用 VBScript 包装器 `wscript.exe run-hidden.vbs xxx.ps1`，vbs 内部用 `WshShell.Run cmd, 0, False` 隐藏窗口启动 PowerShell。`scripts/run-hidden.vbs` 已固化；`install-local-ops.bat` 已改为走 vbs 包装器路径。新增类似后台 PowerShell 任务时**必须**用 vbs 包装，不要直接 `powershell.exe -File`
  - **Task Scheduler 调度选项** — `/RU SYSTEM` 可让任务在 Session 0 跑（完全无窗口），但日志写到用户目录（如 `g:\microbubble-agent\logs\`）会因权限失败。**用 vbs 包装 + 保留用户身份**是最稳的方案
  - **Element Plus daterange/datetimerange 内部 input 没 name**（2026-06-02 教训）— `<el-date-picker type="daterange">` 组件 prop 不会传到内部 `<input class="el-range-input">`，即使外层加 `name="..."` 也只挂在外层 `<div>`。Element Plus 已知限制，**没有任何 prop 能直接修复**。**唯一方案**：拆成两个独立 `<el-date-picker type="date">`（或 `type="datetime"`）选择器，每个都有 name。**代价**：用户需选开始日期 + 结束日期（两步），但消除 a11y 警告 + 浏览器自动填充能力正常
  - **Webhook 持续失败 4 小时根因**（2026-06-02 教训）— 阿里云→GitHub HTTPS 出口网络持续 130s 超时（`curl 16 Error in HTTP2 framing layer` / `GnuTLS recv error (-110)` / `Failed to connect to github.com port 443 after 130051ms`），deploy-auto.sh 老版本 3 次重试全部失败，**14+ webhook delivery 标红**。**根因链 + 完整修复**：
    1. **网络层（HTTPS）**：阿里云到 GitHub 出口 IP 受限
    2. **deploy-auto.sh 无 SSH fallback**：HTTPS 走不通时不会切 SSH
    3. **专用 SSH key 名非默认**：`~/.ssh/github_deploy` 不是 `id_*`，git 找不到 → `Permission denied (publickey)`
    4. **修复 4 步**：
       - `ssh-keygen -t ed25519 -f ~/.ssh/github_deploy -N ""` + 贴公钥到 GitHub Deploy keys
       - `git remote set-url origin git@github.com:gg320324492-lgtm/microbubble-agent.git`（改走 SSH）
       - 写 `~/.ssh/config` 让 `Host github.com` 自动用 `IdentityFile ~/.ssh/github_deploy`（手动 + 后台都生效）
       - `deploy-auto.sh` 顶部 `export GIT_SSH_COMMAND="ssh -i /root/.ssh/github_deploy -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"`（belt-and-suspenders）
    5. **效果**：从 130s 超时 → 5s 完成，14+ webhook 全部成功
  - **Webhook 服务 alive ≠ 部署成功**（2026-06-02 教训）— `systemctl status webhook.service` 显示 `Active: active (running)` **只代表 HTTP 服务在跑**。**部署是否成功看 `/var/log/webhook-deploy.log` 的 `[DEPLOY] 部署完成` / `部署成功 ✓`**。两者**独立**。Webhook 立即返回 200 OK（避免 GitHub 10s 超时）但后台 deploy 异步跑（看 deploy-auto.sh 是否真的成功）
  - **Webhook 端口必须用 `ThreadingHTTPServer`**（2026-06-03 commit `7ec6ce0`，已部署并验证 0.001s 响应）— Python `http.server.HTTPServer` 默认**单线程顺序处理请求**。即使 `do_POST` 内用 `daemon=True` 启动 deploy 线程（避免阻塞响应），HTTP 请求的接收/响应仍是串行的。**症状**：deploy 跑 git pull（5 次重试 + 75s 退避 = 最坏 200s+）时，后续所有 GitHub webhook 健康检查都 10s+ 超时，导致 `delivery failed: time out`。**修复**：`from http.server import ThreadingHTTPServer` 替换 `HTTPServer`，每个请求独立线程，do_GET 健康检查与 do_POST deploy 完全不阻塞。**验证**：连续 5 次 curl `/` 应 < 1s（单线程时线性恶化到 20s+）。**特别注意**：修改 `scripts/webhook.py` 后 webhook 服务**不会自动重启**（deploy-auto.sh 不在重启列表里 — 否则 deploy 流程会被中断），需要**手动 SSH `systemctl restart webhook`** 才生效。`deploy-auto.sh` / `webhook.service` 同理
  - **Vue dist 提交前必须 `npm run build`**（2026-06-03 教训）— commit `d619f33` 漏 build 触发白屏事故：删了 23 个旧 dist 文件 + 改了 index.html 引用新 hash（`index-mZemtrw0.js`），但**没添加新文件**（git commit 0 个 `+`）。后果：阿里云 `git pull` 后 `/opt/microbubble-agent/web/dist/assets/index-mZemtrw0.js` 404 → Vue 不挂载 → 白屏。**防御**（2026-06-03 commit `2b38c99` 加进 deploy-auto.sh）：git pull 后 `find web/dist/assets -name 'index-*.js' | wc -l >= 1` 且 `grep -oE 'assets/index-[A-Za-z0-9_-]+\.js' dist/index.html` 引用的文件必须存在，**任一不满足则 deploy 失败**。**前端提交检查清单**（人工）：① 改 `web/src/` 后**必须** `cd web && npm run build` ② 提交前 `git status` 看新增文件数量（应该有 + 多个 dist 文件）③ `git show --stat HEAD` 确认 `index-*.js` 有新 hash
  - **三级润色流水线**（2026-06-02）— 实时转录常出现 ASR 幻觉（"你和我一样""一二三四"等），单段润色无上下文。**改用三级**：
    1. **L1 实时透传** — 每段 ASR 立即推原文 + `status: "raw"`，前端"实时"徽章
    2. **L2 聚批润色**（`app/services/meeting_batch_polisher.py`）— 每 30s 或攒满 5 段触发 1 次 LLM（`mimo-v2.5`），复用 `polish_segments_with_lock` 已有 Redis 锁 + 24h 缓存，推 `transcript_batch_polished` 消息
    3. **L3 全文精润色**（`app/services/meeting_full_polisher.py`）— hangup 时触发 1 次高质量 Sonnet（`claude-sonnet-4-20250514`），分块 + 跨块 context，**删除 ASR 幻觉孤立短句**（`removed: true` 字段），持久化到 `meeting.transcript_polished` JSON 列
    - **关键纪律**：兜底段满检测（`voice.py` LiveSegmenter 分支）也**必须调用声纹识别**（之前硬编码 "发言人"，导致用户看不到内容）
    - **降级**：LLM 失败时 `_fallback_polished` 返回原文，前端 `status` 保持 `raw`（不报错，不丢内容）
    - **配置**（`app/config.py`）：`POLISH_BATCH_INTERVAL_SECONDS=30` / `POLISH_BATCH_MAX_SEGMENTS=5` / `FULL_POLISH_MODEL=claude-sonnet-4-20250514` / `FULL_POLISH_CHUNK_CHARS=4000` / `TRANSCRIPT_BUFFER_MAX_ENTRIES=1000`
  - **async session 中不要访问 lazy relationship**（2026-06-02 commit `6bc9687`）— `meeting.participants` / `meeting.related` / `meeting.speaker_stats` 等关系属性在 async session 中**没有**预加载（`selectinload()`）时，访问触发 lazy load → 走同步 IO → `sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; can't call await_only() here`。**WS 表现**：服务端 1011 close → 客户端重连 → 服务端又触发同一 lazy load → 循环（用户看到"重连中"永远不停）。**修复**：`await db.refresh(meeting, attribute_names=["participants"])` 预加载，或**避免访问关系属性**（润色/metadata context 不依赖关系）。**错误指纹**：traceback 含 `strategies.py:1130 _emit_lazyload` 关键字 → 100% 是这个错
  - **会议上下文 metadata 字段选型**（2026-06-02）— `meeting_context` / `meeting_metadata` 等**不依赖** lazy 关系。L2/L3 润色需要的 `title`（column 属性，**不**触发 lazy load）/ `participants`（lazy 关系，**会**触发）/ `topic_line` / `context_segments` 字段应该用 column 字段或显式空值构造
- **FastAPI 路由注册顺序**（2026-06-04 教训）— `meeting_recording.py` 的 `/meetings/start-recording` 路由被 `meeting.py` 的 `/meetings/{meeting_id}` 拦截返回 405。**根因**：FastAPI 按注册顺序匹配路由，`meeting.router` 先注册时 `/meetings/start-recording` 会被当作 `meeting_id = "start-recording"` 匹配到 GET-only 的详情路由。**修复**：`meeting_recording.router` 必须在 `meeting.router` 之前注册。**通用规则**：当多个路由文件有路径前缀重叠时（如 `/meetings/xxx` 和 `/meetings/{id}`），**固定路径必须在参数路径之前注册**
- **ProcessingDialog 阶段必须与后端 ProgressStage 同步**（2026-06-04 教训）— 前端 ProcessingDialog 的 `stages` 数组和 `STAGE_ORDER` 必须与后端 `progress_service.py` 的 `ProgressStage` 枚举完全一致。本次发现前端用的是旧版阶段名（`extracting_transcript`、`polishing_transcript`、`generating_minutes`），后端已改为 `downloading_audio`、`transcribing`、`generating_analysis` 等，导致 `STAGE_ORDER.indexOf()` 返回 -1，进度条卡住不动。**规则**：修改后处理流水线阶段时，必须同步更新 `ProcessingDialog.vue` 的 `stages` + `STAGE_ORDER` 和 `progress_service.py` 的 `ProgressStage`

- **3D-Speaker 依赖链**（2026-06-05 教训）— `modelscope` 的 `speaker_verification` pipeline 有大量传递依赖：`addict`（模型配置）、`datasets`（数据集加载）、`simplejson`（JSON 序列化）、`sortedcontainers`（排序容器）、`soundfile`（音频文件读取）。这些依赖已写入 `requirements.txt`，但 Celery worker 容器如果是旧构建会缺少。**症状**：`ModuleNotFoundError: No module named 'addict'` → 声纹识别静默返回 unknown，所有发言人显示"发言人A"。**修复**：容器内 `pip install addict datasets simplejson sortedcontainers soundfile`，然后 `docker compose restart celery-worker`
- **silero-vad 模型下载失败**（2026-06-05 教训）— `torch.hub.load("snakers4/silero-vad")` 从 GitHub 下载模型，服务器出口 IP 受限时会 HTTP 403 rate limit。**修复**：手动下载 `https://github.com/snakers4/silero-vad/archive/refs/heads/master.zip` → 解压到 `/root/.cache/torch/hub/snakers4_silero-vad_master` → 代码加 `source="local"` 回退
- **datetime tz-aware 写入 tz-naive 列**（2026-06-05 教训）— `datetime.now(timezone.utc)` 创建带时区的 datetime，但 PostgreSQL `TIMESTAMP WITHOUT TIME ZONE` 列无法接收。asyncpg 报 `can't subtract offset-naive and offset-aware datetimes`。**修复**：`.replace(tzinfo=None)` 转为 naive datetime。**通用规则**：凡是写入数据库的 datetime，必须确认列类型是 `TIMESTAMP WITH TIME ZONE` 还是 `WITHOUT`，对应使用 tz-aware 或 naive

<!-- superpowers-zh:begin (do not edit between these markers) -->
# Superpowers-ZH 中文增强版

本项目已安装 superpowers-zh 技能框架（20 个 skills）。

## 核心规则

1. **收到任务时，先检查是否有匹配的 skill** — 哪怕只有 1% 的可能性也要检查
2. **设计先于编码** — 收到功能需求时，先用 brainstorming skill 做需求分析
3. **测试先于实现** — 写代码前先写测试（TDD）
4. **验证先于完成** — 声称完成前必须运行验证命令

## 可用 Skills

Skills 位于 `.claude/skills/` 目录，每个 skill 有独立的 `SKILL.md` 文件。

- **brainstorming**: 在任何创造性工作之前必须使用此技能——创建功能、构建组件、添加功能或修改行为。在实现之前先探索用户意图、需求和设计。
- **chinese-code-review**: 中文 review 沟通参考——话术模板、分级标注（必须修复/建议修改/仅供参考）、国内团队常见反模式应对。仅在用户显式 /chinese-code-review 时调用，不要根据上下文自动触发。
- **chinese-commit-conventions**: 中文 commit 与 changelog 配置参考——Conventional Commits 中文适配、commitlint/husky/commitizen 中文模板、conventional-changelog 中文配置。仅在用户显式 /chinese-commit-conventions 时调用，不要根据上下文自动触发。
- **chinese-documentation**: 中文文档排版参考——中英文空格、全半角标点、术语保留、链接格式、中文文案排版指北约定。仅在用户显式 /chinese-documentation 时调用，不要根据上下文自动触发。
- **chinese-git-workflow**: 国内 Git 平台配置参考——Gitee、Coding.net、极狐 GitLab、CNB 的 SSH/HTTPS/凭据/CI 接入差异与镜像同步配置。仅在用户显式 /chinese-git-workflow 时调用，不要根据上下文自动触发。
- **dispatching-parallel-agents**: 当面对 2 个以上可以独立进行、无共享状态或顺序依赖的任务时使用
- **executing-plans**: 当你有一份书面实现计划需要在单独的会话中执行，并设有审查检查点时使用
- **finishing-a-development-branch**: 当实现完成、所有测试通过、需要决定如何集成工作时使用——通过提供合并、PR 或清理等结构化选项来引导开发工作的收尾
- **mcp-builder**: MCP 服务器构建方法论 — 系统化构建生产级 MCP 工具，让 AI 助手连接外部能力
- **ui-design**: 前端界面设计规范 — 暖橙珊瑚色系、圆角阴影规范、动画时序曲线、骨架屏规范、玻璃拟态、20项 UI 升级检查清单
- **receiving-code-review**: 收到代码审查反馈后、实施建议之前使用，尤其当反馈不明确或技术上有疑问时——需要技术严谨性和验证，而非敷衍附和或盲目执行
- **requesting-code-review**: 完成任务、实现重要功能或合并前使用，用于验证工作成果是否符合要求
- **subagent-driven-development**: 当在当前会话中执行包含独立任务的实现计划时使用
- **systematic-debugging**: 遇到任何 bug、测试失败或异常行为时使用，在提出修复方案之前执行
- **test-driven-development**: 在实现任何功能或修复 bug 时使用，在编写实现代码之前
- **using-git-worktrees**: 当需要开始与当前工作区隔离的功能开发或执行实现计划之前使用——创建具有智能目录选择和安全验证的隔离 git 工作树
- **using-superpowers**: 在开始任何对话时使用——确立如何查找和使用技能，要求在任何响应（包括澄清性问题）之前调用 Skill 工具
- **verification-before-completion**: 在宣称工作完成、已修复或测试通过之前使用，在提交或创建 PR 之前——必须运行验证命令并确认输出后才能声称成功；始终用证据支撑断言
- **workflow-runner**: 在 Claude Code / OpenClaw / Cursor 中直接运行 agency-orchestrator YAML 工作流——无需 API key，使用当前会话的 LLM 作为执行引擎。当用户提供 .yaml 工作流文件或要求多角色协作完成任务时触发。
- **writing-plans**: 当你有规格说明或需求用于多步骤任务时使用，在动手写代码之前
- **writing-skills**: 当创建新技能、编辑现有技能或在部署前验证技能是否有效时使用

## 如何使用

当任务匹配某个 skill 时，使用 `Skill` 工具加载对应 skill 并严格遵循其流程。绝不要用 Read 工具读取 SKILL.md 文件。

如果你认为哪怕只有 1% 的可能性某个 skill 适用于你正在做的事情，你必须调用该 skill 检查。
<!-- superpowers-zh:end -->
