# MicroBubble Agent - 项目上下文
## 项目简介

"小气" - 微纳米气泡课题组智能Agent系统，约20人研究实验室的AI助手。

- 后端: Python 3.11 + FastAPI + SQLAlchemy + PostgreSQL + Redis + Celery
- 前端: Vue 3 + Vite + Element Plus（原版 `web/`，极简版 `web-minimal/`）
- AI: Claude API (Sonnet) + faster-whisper + pgvector
- 部署: 云服务器 (Nginx + FRP 服务端) + 本地电脑 (Docker 8 services + GPU Whisper)，通过 FRP 隧道连接。也支持单机部署，详见 `docs/deploy.md` 服务器迁移章节

## 当前状态 (2026-07-24 W68 第 9 批 grand closure — 锚点范式第 116 守恒)

**W68 第 9 批 grand closure**: Drive v2 PR11 (评论 path 物化 + GIN trgm + breadcrumb 端点) + plans 闭环 (8 plans Status 修正 + 8 留 W69) + 8 小修整合 + 任务模式基调 v2 (5 拍板纪律 + 4 阶段流程 v2) + docs 同步. 主指挥协调范式第 39 次派工. 锚点范式单调上升 W7 12 → W66 27 → W67 28 → W68 30 → W68 第 3 批 42 → W68 第 4 批 57 → W68 第 5 批 72 → W68 第 6 批 88 → W68 第 7 批 89 → W68 第 8 批 104 → **W68 第 9 批 116** (12 守恒, plans 闭环 + 任务模式基调 v2 双驱动). 累计 9 批 60+ agent commits + W68 跨主题 220+ commits (main HEAD `f14cb43c1`). **0 production code 改动铁律维持** (W68 第 9 批 docs/memory 范畴, 仅 Drive v2 PR11 路径物化例外已批). W19 选项 A 维持. 详见 `memory/w68-grand-closure-9th-batch-2026-07-24.md` (待主指挥写).

**W68 第 1+2+3+4+5+6+7+8 批完成**: W68 第 1 批 14 agents (路线 A Drive v2 PR8 + 路线 C Mobile UX v3.0) + Safari iOS 空白页修复 + W68 第 2 批 3 agents (路线 B D6 调研 + 路线 D 文档同步 + 路线 E baseline 守恒验证) + W68 第 3 批 11 agents (Drive v2 PR9 评论 thread + 文件版本历史 + 移动端评论 UI + qa-bench D6 调研 + Mobile UX v3.1 + 文档部署收口) + W68 第 4 批 15 agents (跨主题收口 + Plan 闭环 2/2) + W68 第 5 批 15 agents (Drive v2 PR10 collab + Mobile v3.2 push + 评论 hotfix 系列) + W68 第 6 批 16 agents (Verified Plans 深度审计 + 70+ plans 重整) + W68 第 7 批 1 agent (grand closure 闭环) + W68 第 8 批 14 agents (Drive v2 部署文档 + 永久纪律沉淀 + docs 同步 + 6 commit qa-bench/QA D6 Phase 2/3 + 部署验证).

**跨周期累计**: 67 plans 状态化 (W66) → 59 plans 活跃 + 8 plans archived (W68 第 7 批) → W68 第 9 批 plans Status 闭环 8 + 8 留 W69 + qa-bench D5 gate docs/CI 占位 (W67) + Lint CSS 守恒 (71 PASS + 7 SKIP baseline 38+ 守恒) + W68 第 6 批 plans 审计 70+ plans 100% 真实状态化.

**W68 累计 commits: 140 → 155 (第 8 批) → 第 9 批 12 守恒. 锚点范式 90 → 104 → 116 单调上升预期.**

**任务模式基调**: 派工以已有 plans 实施为主 + 更新过程中发现的小修为辅 (W68 第 4 批主指挥拍板, W68 第 9 批 D-3 升级 v2 加 5 拍板纪律 + 4 阶段流程 v2). 详见 `memory/w68-task-mode-paradigm-plans-first-2026-07-24.md` + `docs/w68-task-mode-paradigm-v2.md`.

**W68 第 6+7+8+9 批纪律沉淀锚点范式**: `## W68 第 6+7+8 批纪律沉淀 (永久锚点)` 章节 (见下) — 永久纪律固化, 未来会话读到 CLAUDE.md 即可了解所有审计/闭环纪律.

### W68 第 8 批 grand closure (2026-07-24)

**W68 第 8 批 grand closure** (主基调 "W68 第 7 批合并 + 路线驱动 + hot-fix #18 跟踪"). 主指挥协调范式第 36 次派工. 锚点范式单调上升 W7 12 → W66 27 → W67 28 → W68 30 → W68 第 3 批 42 → W68 第 4 批 57 → W68 第 5 批 72 → W68 第 6 批 88 → W68 第 7 批 89 → **W68 第 8 批 102** (单批 15 守恒). 累计 8 批 50+ agent commits + W68 跨主题 200+ commits (main HEAD `05c60e68d`). **0 production code 改动铁律 12/15 守恒** (3 例外已批: B-1 Drive v2 PR11 + B-2 Drive v2 PR12 + B-3 Mobile v3.2 iOS 分享 + 生物识别). W19 选项 A 维持 (4 留未来 PR). 详见 `memory/w68-grand-closure-8th-batch-2026-07-24.md` + `memory/w68-route-9-a2-claudmd-anchor-2026-07-24.md`.

**W68 第 8 批 15 agents 派工清单** (主基调 "W68 第 7 批合并 + 路线驱动 + hot-fix #18 跟踪"):
- **A-1**: W68 第 7 批 15 分支合并到 main + 5 新铁律 (锚点范式第 90 守恒, commit `62d4a59f7`)
- **A-2**: Drive v2 PR9-11 master runbook + FAQ (commit `e51699d48`)
- **A-3**: W68 第 7 批 + 3 hot-fix 部署验证 8 段 (锚点范式第 92 守恒, commit `c6399df32`)
- **B-1**: Drive v2 PR11 评论 path 物化 + GIN trgm 索引 + breadcrumb 端点 (commit `a2a00ad73`)
- **B-2**: Drive v2 PR12 emoji reactions (锚点范式第 94 守恒, commit `21a1906a8`)
- **B-3**: Mobile v3.2 iOS Safari 分享 + 生物识别集成 (commit `faffaf8ff`)
- **B-4**: qa-bench D6 Phase 3 matrix 4 runner 并行 (commit `c496862b7`)
- **C-1**: hot-fix #18 (Knowledge.uploader_id → created_by) 实施报告 (锚点范式第 97 守恒, commit `5c28059d5`)
- **C-2**: W68 第 7 批 worktree + 分支清理脚本 + runbook (锚点范式第 98 守恒, commit `cf03425a0`)
- **C-3**: W68 第 8 批 grand closure memory (锚点范式 90 → 104 预期, commit `79b44d171`)
- **D-1**: W68 第 7 批 15 agents 调研发现 6 小修整合 (锚点范式第 88 守恒, commit `353ba295a`)
- **D-2**: 6 类文档同步 + W68 第 8 批 grand closure memory 引用 (锚点范式 90 → 104 预期, commit `014585813`)
- **D-3**: W68 第 6+7 批纪律沉淀到 CLAUDE.md (锚点范式第 102 守恒, commit `6f78e4cec`)
- **D-4**: hot-fix #18 监控日志 + 5 新铁律 (锚点范式第 103 守恒, commit `1ce813e38`)
- **D-5**: W68 任务模式基调最终验证 (锚点范式第 104 守恒)

**W68 第 8 批核心成果**:
- **alembic 单链纪律强化**: 062 (PR9 评论) → 063 (PR9 版本) → 064 (PR10 协同) → 065 (PWA push) → 066 (PR11 path) → 067 (PR12 reactions) — 6 串单链迁移 0 双头
- **永久纪律固化**: W68 第 6+7 批审计/闭环纪律从 memory/ 提升到 CLAUDE.md `## W68 第 6+7 批纪律沉淀 (永久锚点)` 节 (D-3), 未来会话读到 CLAUDE.md 即可了解所有审计/闭环/守恒纪律
- **任务模式基调实战彻底验证**: plans 优先 + 小修搭配 经 W68 第 4+5+6+7+8 批 5 批实战 (累计 60+ agents 派工) 彻底验证, 0 regression
- **0 production code 改动铁律 12/15 守恒**: 路线 A/C/D/E 完全维持 (纯 docs/memory/scripts/ 范畴), 路线 B (3 个新功能扩展) 例外已批: B-1 PR11 评论 path 物化 + B-2 PR12 reactions + B-3 Mobile v3.2 iOS 分享 + 生物识别
- **W19 选项 A 维持**: 4 留未来 PR (Phase 8.5 / P3 跨 tab / 7 E2E / pending-future-3). 量化触发条件维持.

**W68 累计 commits**: 30+8+12+30+30+15+15+15 = **155 commits** (W68 第 1+2+3+4+5+6+7+8 批累计).

**锚点范式数字正确性**: W68 第 7 批 87 → W68 第 8 批 102 (单批 15 守恒, 0 regression).

## 当前开发阶段

**Phase 1-6 全部完成 + v2/v3/v4 全栈架构重构收官 + 移动端 10 个 PR 全栈定制收官。** 知识库已升级为**自主进化的课题组知识大脑**。会议系统已重构为**录音机 + 离线后处理模式**。**小气助手后端 Agent 架构**：从 1 个 1469 行单文件（`app/agent/core.py`）拆为 7 个职责清晰模块 + 13 个按业务域拆分的 tools/ 文件，**34 个工具全部走 `@tool` 装饰器 + Pydantic 校验**。前端用 ChatViewSSE.vue 接入真实 SSE 流式 + 12 类 Rich Block 组件 + 多会话侧栏 + dark mode + ASR/TTS 完整语音链路 + 代码高亮。**移动端**采用 NutUI 4 + Element Plus **路由级双栈**架构（`useIsMobile.js` 判定 + `resolveMobile.js` 路由适配），**18 个移动端页面 + 12 个移动端组件 + 4 个 PWA 离线策略**全部交付，**iOS Safari + Android Chrome 全兼容**。**当前状态（2026-06-13 收官后，commit `9026c07`）**：
- **43 commits 累计**（v1 修复 + v2 6 + v3 5 + v4 6 + 文档 2 + 深夜收尾 4 + 多会话并行 2 + 移动端 PR #1-10 共 10 + 文档/webhint 5 + 部署加固 1）
- **160+ 测试全过**（87 后端 + 73 前端 + 21 录音断网防御 + 2 移动端组件 + 21 多模态 OCR）
- **1014 次提交 / 135K 行代码 / 578 文件 / 30 开发天数**（`app/stats.json` 由本地 Python 准确计算；排除 frp/.git/node_modules/dist/.meta/.log/.wav/.exe 等非源代码）
- **140 项待做清单**已整合到 README.md（107 项老 + 33 项 v4 收官遗留），移动端 10 PR 完成后清单大幅缩短

**Phase 7 多模态知识库（2026-06-19）**：
- **2 张新表**：`knowledge_images`（图片 + OCR 结果）+ `knowledge_extractions`（统一 formula/table/chart/image_block）
- **OCR 服务抽象层**（`app/services/ocr_service.py`）：主后端 LLM-Vision 复用 vision_service，可选 Tesseract 备选（settings.MULTIMODAL_OCR_BACKEND 切换）
- **多模态解析管线**（`app/services/multimodal_extraction_service.py`）：PDF/PPTX 提取嵌入图片 → 缩放 → MinIO → asyncio.Semaphore 并发 OCR → 写表
- **3 个新 API**：`GET /knowledge/{id}/images`、`GET /knowledge/{id}/extractions`、`POST /knowledge/{id}/extract-multimodal`（老 PDF 手动重提）
- **KnowledgeService step 7**：上传时自动触发多模态提取；独立容错
- **5 个新 settings**：`MULTIMODAL_OCR_BACKEND` / `_CONCURRENCY=4` / `_MAX_IMAGES_PER_DOC=20` / `_MAX_IMAGE_PIXELS=2.5MP` / `_MIN_IMAGE_PIXELS=10k`
- **2 个新前端组件**：`KnowledgeImageGallery.vue`（图片网格 + 放大预览 + OCR 文本）+ `KnowledgeExtractionsPanel.vue`（公式 LaTeX + 表格 HTML + 图表描述）
- **KnowledgeCard 缩略图** + `KnowledgeUploadDialog` PDF/PPTX 多模态提示
- **端到端验证**：PDF id=19 OCR 10/10 + 10 OCR 块 + 4 图表描述成功

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

## 2026-06-29 #043 账号持久化聊天历史（Phase 4+5 收官 6/8, Phase 6 UI 升级待启动）

> **用户原始需求**：每个人与小气助手的对话的聊天记录要跟随账号一直记住，就像 ChatGPT、豆包一样。用户登录就可以看到过往聊天记录。
>
> **痛点（现状）**：前端 100% `localStorage`（`chat_msgs_<sid>` + `chat_sessions_v3`），per-browser 不跨账号。换浏览器/换电脑/清缓存/移动端新设备 = 历史清零。多人共用一台电脑 = A 账号登入看到 B 账号的会话。后端 Redis `agent_session:{sid}:msgs` 有持久化但**无 user_id 反查**，且 `micro_bubble_agent.py:111 chat_stream()` 流式场景**不写 Redis**。

**用户决策**（2026-06-29）：
- 存储后端：**PostgreSQL SQL 表**（质量与效果最好；不是 Redis 扩展）
- 旧数据迁移：**首次登录自动迁移 localStorage → server**
- 功能范围：**尽可能全**（搜索 + 导出 + 标签/收藏/归档 + 分享链接 + 软删除 + 跨设备同步）

**完整规划**：[C:/Users/pc/.claude/plans/chatgpt-structured-floyd.md](C:/Users/pc/.claude/plans/chatgpt-structured-floyd.md)（8 phase / 22-30h / 3 PR 收官）

**8 phase 实施计划**：
1. ✅ **Phase 1（commit `558962b1` 收官）**：ORM 模型 + alembic `039_chat_history.py`（chat_sessions / chat_messages / chat_shares 三表 + 索引 + 触发器）+ Pydantic schemas
2. ✅ **Phase 2（commit `558962b1` 收官）**：11 个后端 API 端点（`/chat/sessions` CRUD + `/messages` + `/export` + `/share` + `/search` + `/sync` + `/shares/{token}`）— 17/17 e2e PASS
3. ✅ **Phase 3（commit `5bf7c5c7` 收官）**：流式 chat 持久化修复（`micro_bubble_agent.py:111` + `partial_assistant_buffer` + SSE 事件 `message_persisted` / `sync_required`）— 25/25 e2e PASS
4. ⏸ **Phase 4（待启动）**：前端 store 重构（chatHistory.ts + chatSessions.ts 同步 + useChatStream 持久化钩子 + 监听 sync_required 自动 reload）
5. ⏸ **Phase 5（待启动）**：旧数据自动迁移（useChatMigration.js + localStorage `chat_migrated_v1` 标记 + 幂等键）
6. ⏸ **Phase 6（待启动）**：UI 升级（搜索栏 + 标签 chip + 分享对话框 + 导出对话框 + 移动端长按 ActionSheet）
7. ⏸ **Phase 7（待启动）**：Celery 30 天清理任务（`cleanup_soft_deleted_sessions` 每天凌晨 3:30）
8. ⏸ **Phase 8（待启动）**：测试 + memory 沉淀（4 后端 + 2 前端单测 + 10 E2E + memory/chat-history-persistent-2026-06-29.md）

**PR 分批**：
- PR 1（Phase 1-3+7-8，~10h）✅ 已收官（含 558962b1 + 5bf7c5c7 + 后续 Phase 7/8）
- PR 2（Phase 4-5，~6h）⏸ 待启动
- PR 3（Phase 6，~8h）⏸ 待启动

**复用现有 utilities**：`app.core.security.get_current_user`（JWT 鉴权） / `app.core.rate_limit`（write tier 30/min） / `app.services.task_service.auto_purge_trash_task`（30 天清理模式） / `web/src/composables/chat/useChatStream.ts`（多会话并行 8 铁律保留） / v77 P2.6-C EP 多主题透传 dark mode 适配

**部署必做**（CLAUDE.md 752 行铁律）：
```bash
# 1. 跑迁移
docker cp alembic/versions/039_chat_history.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
docker exec microbubble-agent-app-1 alembic upgrade head
# 2. 重启后端
docker compose restart app celery-worker
# 3. 验证表（chat_sessions / chat_messages / chat_shares）
```

**关键风险与缓解**：
- 流式 chat 中断 → partial 消息：`is_partial=True` 标记 + 重新生成机制（Phase 3 SSE 限制：连接断开时 partial 可能不落库，但 user 必落）
- localStorage 迁移冲突：`client_msg_id` 幂等键 + `last_synced_at` 时间戳
- 越权访问：`WHERE user_id = current_user.id` 强制 + 单元测试
- alembic 链断：接 `038_*` 下游（v77 P2.6-F.5 cloned_from_id 已存在）

**进度跟踪**（8/8 phase 完整收官）：
- [x] Phase 1：ORM + alembic（commit 558962b1）
- [x] Phase 2：11 API 端点（commit 558962b1）
- [x] Phase 3：流式持久化（commit 5bf7c5c7）
- [x] Phase 4：前端 store（commit af8c8f7d）
- [x] Phase 5：旧数据迁移（commit af8c8f7d）
- [x] Phase 4+5 fix：sync_from_local tz-aware datetime 500 bug（commit a1dfca2c，2026-06-30）
- [x] **Phase 6：UI 升级（11 sub-tasks：SearchPalette/ShareDialog/ExportDialog/TagsEditor/useGlobalShortcuts/SessionSidebar/MobileSessionDrawer/LongPressWrapper/MobileActionSheet/MobileSearchSheet + 桌面 ChatViewSSE + 移动 MobileChatView/MobileHeader 集成）— vitest 492/492 PASS**
- [x] **Phase 7：Celery 30 天清理（`app/services/chat_history_tasks.py:cleanup_soft_deleted_sessions_task` + `CHAT_HISTORY_RETENTION_DAYS=30` + beat schedule 3600s + `celery_app.conf.imports` + autodiscover 双注册）— pytest 7/7 PASS + 端到端 15 个过期会话 100% 物理清除验证**
- [x] **Phase 8：测试 + 沉淀（5 新测试文件：test_chat_history_service.py 24 test + test_chat_history_tasks.py 7 test + useGlobalShortcuts.test.js 9 test + useChatMigration.test.js 9 test + chatHistory.test.js 9 test）— vitest 492 + pytest 7 + memory 完整沉淀**

**Phase 3 已沉淀的 5 条新铁律**（详见 [memory/chat-history-stream-persistence-2026-06-29.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/chat-history-stream-persistence-2026-06-29.md)）：
1. **流式 chat 持久化必须入场 append user** — 不能 defer 到流结束（中断时 user 消息就丢）
2. **assistant 落库必须在 done 事件 yield 之后立即** — 客户端收到 done 后才看到 message_persisted，事件顺序清晰
3. **CancelledError 必须 try/except + 落 partial + 重 raise** — 不能吞，否则上层不知道中断 SSE 不关闭
4. **JSONB 字段 mutate 后必须 `flag_modified`** — CLAUDE.md 2026-06-28 教训（rich_blocks / tool_trace / message_metadata 全部要）
5. **持久化失败必须 best-effort** — 所有持久化操作 try/except + logger.error(exc_info=True)，不阻塞流式（用户体验优先）

**Phase 4-8 已沉淀的 7 条新铁律**（详见 [memory/chat-history-persistent-2026-06-30.md](C:/Users/pc/.claude/projects/e--microbubble-agent/memory/chat-history-persistent-2026-06-30.md)）：
6. 跨设备同步：消息主存 PostgreSQL，Redis 仅短期缓存（MVP 拉取模式，WebSocket push 留待 #009 Self-RAG）
7. 软删除：30 天保留期（与 task / meeting 对齐，Celery NullPool + asyncio.run + logger.warning）
8. 越权防护：所有查询 `WHERE user_id = current_user.id`（service 函数签名 `(db, user_id, session_id, ...)` 强制 user_id 过滤）
9. 迁移幂等：`client_msg_id` 唯一约束 + `last_synced_at` 增量同步（服务端 `sync_from_local` 内部用 `hash(sid:role:ts:content[:50])` 生成）
10. 异步不阻塞登录：迁移后台跑（`useChatStream.onMounted setTimeout 1000ms`），UI 立即可用
11. localStorage 兜底：网络失败降级到本地（`chat_migrated_v1` 标志缺失时重试，**失败时不设标志**）
12. tz-aware vs naive datetime 严格隔离：Celery task 用 `datetime.now(timezone.utc)` 传 cutoff，service 内部统一 `_to_naive_datetime()` 转换（CLAUDE.md 2026-06-05 教训复用，避免 "can't subtract offset-naive and offset-aware datetimes" 500）
13. mobile long-press 必带 `navigator.vibrate(10)` 触觉反馈（CLAUDE.md 2026-06-27 教训）+ dark mode 跨组件必须非 scoped 块（CLAUDE.md v60-v67 第 5 次强化）

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

### 2026-06-13 webhint PWA 5 警告全栈修复新增（commit `08f440f` + `c855f0e`）

- **Nginx 缺 `.webmanifest` MIME（commit `08f440f`）** — Nginx 默认 `mime.types` 不包含 `.webmanifest`（到 1.27 才内置），回退 `application/octet-stream` → 浏览器拒绝解析 PWA manifest → 添加桌面图标失败。**修复**：server block 加 `types { application/manifest+json webmanifest; }` + `charset_types` 同步加 `application/manifest+json`（让 `charset utf-8` 生效）。**诊断**：`curl -I https://xxx/manifest.webmanifest | grep Content-Type` 看是不是 octet-stream。**纪律**：所有 PWA 项目上线前必须验证 manifest MIME，**仅一次**而不是每个 server 都加。
- **`vite-plugin-pwa` 输出 manifest 不带 hash（commit `08f440f`）** — `manifest.webmanifest` 文件名固定不走 rollup hash 流程，webhint cache-busting 永远警告。**修复**：写一个 Vite 插件 `manifestHashPlugin`（closeBundle 钩子）→ `crypto.createHash('sha256').update(content).digest('hex').slice(0, 8)` → 重命名为 `manifest.{8char_hash}.webmanifest` + 同步改 `index.html`/`offline.html` 的 link 引用。**8 字符 hex 满足 webhint 默认 `[0-9a-f]+` 正则**。**Vite 5+ emitFile 不适用**（manifest 是 vite-plugin-pwa 输出，emitted by another plugin），必须 fs.renameSync。
- **`/registerSW.js` 静态注入无法 cache-busting（commit `08f440f`）** — `VitePWA({ injectRegister: 'auto' })` 自动注入 `<script src="/registerSW.js">`，文件名固定无 hash。**修复**：`injectRegister: null` + `main.js` 用 `import { useRegisterSW } from 'virtual:pwa-register/vue'` 替代。**Vue composable 在生产 build 时被 rollup 处理，运行时通过 sw 注册的副作用自动跑**，无需手动写 `<script>`。**纪律**：PWA 项目**避免** `injectRegister: 'auto'`，除非真的需要纯静态（非 SPA）站点。
- **删除 manifest.webmanifest 后 SPA fallback 误返 index.html（commit `c855f0e`）** — git 删除旧 manifest 文件后，Nginx `try_files $uri $uri/ /index.html` 找不到文件 → fallback `/index.html`（1924 字节 HTML 内容） → 任何残留引用/书签/扫描器拿到 HTML 内容物以为是 manifest。**修复**：在 `/` location 前加 `location = /manifest.webmanifest { return 410; }` 精确 410 Gone。**纪律**：SPA 部署时**所有被废弃的资源路径**都应该有明确返回（410 / 404），不能依赖 try_files fallback。
- **theme-color Firefox 不支持** — Edge DevTools 内置 webhint 不读 `.hintrc`，永远警告。**纪律**：`.hintrc` 配 `meta-theme-color: "off"`（webhint CLI 0 警告），接受 Edge DevTools 误报。Chrome/Safari/iOS Safari PWA 顶部栏颜色价值 > Edge DevTools 警告噪音。**永远不要**完全删除 theme-color meta（损失浏览器原生美化）。

### 2026-07-11 PWA manifest 410 回归 (commit `59187ce8` cascade folder delete 引入, `5d2bcdfd` 修复)

> ⚠️ **铁律**: `web/package.json` `"build": "vite build && node scripts/postbuild-fix-manifest.js"` 是**唯一**合法 build 命令。**严禁** `vite build` 直跑然后 force-add commit dist — manifest.webmanifest 保持 unhashed → nginx `location = /manifest.webmanifest { return 410; }` 拦截 → 浏览器 `Manifest fetch failed, code 410` → PWA install 失败。`package.json` 有 `build:raw` 别名但**仅供调试 sw.js 内容用**, 调试完必须重跑 `npm run build` 才能 commit。

- **根因**: commit `59187ce8` 用 `vite build` 直跑绕开 postbuild → `git show 59187ce8 -- web/dist/manifest.webmanifest` 显示 `manifest.4f8d6b64.webmanifest => manifest.webmanifest` (rename 回 unhashed) → 服务器 410 → 用户浏览器 PWA install 失败。
- **修复 (commit `5d2bcdfd`)**: `cd web && npm run build` → postbuild 自动 3 件事 + 健全性自检 + `git add -f web/dist/manifest.{hash}.webmanifest` (新增文件 .gitignore 拦了必须 `-f`) + push → webhook 30s → 浏览器 DevTools Clear site data + 硬刷。云端验证: `/manifest.webmanifest` 410 (防护保留) + `/manifest.4f8d6b64.webmanifest` 200 (`application/manifest+json`)。
- **纪律**:
  1. **`npm run build` 是唯一合法 build 命令** — `vite build` 直跑 = 必坏 PWA (服务器 410 + 浏览器 install 失败)
  2. **服务器 410 manifest.webmanifest 是有意防护** — 防 SPA `try_files` fallback 误返 index.html (c855f0e 教训)。修法只能改客户端 dist, 不能动 nginx
  3. **commit 前必须 grep dist** — `git diff --cached -- web/dist/ | grep -E '"url":\s*"manifest\.webmanifest"'` 期望空输出
  4. **SW BUMP commit 必须连带重跑 npm run build** — 任何 SW_VERSION bump 都会触发 dist 改动, 调试时必须用 `npm run build`
  5. **.gitignore 含 `web/dist/` → git add 必须 -f** — `git add web/dist/` 默认啥都不加, 新增 hashed manifest 文件**极易漏 force-add**, 修法 `git add -f web/dist/manifest.{hash}.webmanifest` 逐一加
- **下次加固 PR**: `scripts/deploy-auto.sh` line 134 (v80 修复加入) `grep -oE '"url":"manifest\.webmanifest"' dist/sw.js` 只检查**新 build**, 不检查 git staged。建议加 `git diff --cached -- web/dist/sw.js | grep -qE '"url":\s*"manifest\.webmanifest"'` 拦截任何 stage 的 unhashed 引用 (commit 59187ce8 这条恰好能拦下)。
- **memory 沉淀**: [`pwa-manifest-410-regression-2026-07-11.md`](./memory/pwa-manifest-410-regression-2026-07-11.md) (含 5 铁律 + commit 链 + deploy-auto.sh 加固代码)

### 2026-07-24 alembic 并行 agent 串单链纪律 (commit `1852468a6`)

> ⚠️ **铁律**: 并行派多个写 alembic migration 的 agent 时, 派工 prompt **必须明确 down_revision 接续关系**, merge 后**必须 verify 只有 1 个 head**。否则 `alembic upgrade head` 报 `Multiple head revisions are present` 直接阻塞部署。

- **根因**: W68 第 3 批 F-1 (062 drive_comments) + F-2 (063 drive_file_versions) 两个 agent **并行**开发, 派工 prompt 没写接续关系 → 都声明 `down_revision="061_drive_folder_share"` → merge 进 main 后 alembic 链在 061 处分叉成**两个 head** → `alembic upgrade head` 报 `FAILED: Multiple head revisions are present for given argument 'head'`。
- **修复 (commit `1852468a6`)**: 主指挥在 merge 062 后改 063 `down_revision="062_drive_comments"` 串成单链 `061 → 062 → 063`。这是本项目 053/054/055/056 四连 CI unique 迁移用过的模式 (每张迁移严格单链)。**不用**解法 B (`alembic upgrade heads` 保持双头) — `downgrade -1` 语义歧义 + 未来 064 接链需要 `alembic merge` 留坑。H-1 agent 已在 `docs/drive-v2-pr9-deployment.md` 第 0 节 + `docs/drive-v2-pr9-rollout-checklist.md` 1.1 记录此流程。
- **纪律 (5 条)**:
  1. **并行派 alembic migration agent 必须明确接续关系** — 派工 prompt 必须写清楚"down_revision 接 X", 不写就默认接最新。两个 agent 同时接同一个上游 = merge 必双头
  2. **merge 顺序必须按 alembic 链** — 先 merge 最上游的 migration, 再 merge 下游的。不能并行 merge (无依赖关系时除外)
  3. **merge 后立即 verify** — 期望只 1 个 head:
     ```bash
     python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print(s.get_heads())"
     ```
  4. **部署文档第 0 节必含 alembic chain 风险** — 任何写 alembic migration 的 PR 必须在部署文档顶部加"alembic 链风险"段, 提醒主指挥 merge 顺序 (参考 `docs/drive-v2-pr9-deployment.md` 第 0 节)
  5. **跨 PR 部署 alembic 必须 cp + clear cache** — `docker cp alembic/versions/0XX_*.py microbubble-agent-app-1:/app/alembic/versions/` 后必跑 `docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__` (CLAUDE.md 752 行铁律升级 — `__pycache__` 残留会让老 down_revision 继续生效, 双头假修复)
- **memory 沉淀**: [`memory/w68-alembic-chain-discipline-2026-07-24.md`](./memory/w68-alembic-chain-discipline-2026-07-24.md) (锚点范式第 46 守恒 + 完整时间线)

### 2026-06-13 Vue 3.5 'bum' null bug 真根因 + Vite plugin patch（commit `79305b7`）

- **Vue 3.5 unmountComponent 仍缺 instance null 检查** — 之前 CLAUDE.md 误记"Vue 3.5.34 PR #11487 已修 `bum` bug"，**实际未修**。`@vue/runtime-core/dist/runtime-core.esm-bundler.js:6763`（3.5.34）和 `:6763`（3.5.38 raw 检查）：
  ```js
  const unmountComponent = (instance, parentSuspense, doRemove) => {
    if (__DEV__ && instance.type.__hmrId) { ... }   // ← instance 仍可能为 null
    const { bum, scope, job, subTree, um, m, a } = instance  // ← 爆点
  ```
  只有 line 6572 的 `unmount()` 函数 vnode 解构加了 null 检查，`unmountComponent()` 的 instance 解构**漏修**。minify 后报 `Cannot destructure property 'bum' of 'e' as it is null`（`e` = `instance`）。
- **触发链路** — Element Plus el-table/el-table-column/el-checkbox/el-tooltip/el-popper 递归 unmount 时，**某子 vnode.component 已是 null**（HMR/路由切换/keep-alive 边界状态）→ `vnode.type.remove(...)` 调 `unmountComponent(null)` → 爆。常见触发页：`AgentTracesView`（19 el-table）/ `TaskTrash`（18）/ `SpeakerMappingPanel`（8）/ `KnowledgeView`（4 tab lazy）/ `VoiceprintEnrollDialog`（el-dialog + el-tabs + lazy）。
- **修复：Vite plugin transform 阶段 patch esm-bundler.js**（commit `79305b7`）—
  ```js
  // vite.config.js
  function vueBumNullPatchPlugin() {
    return {
      name: 'vue-bum-null-patch',
      enforce: 'pre',
      transform(code, id) {
        if (!/node_modules\/@vue\/runtime-core\/dist\/runtime-core\.esm-bundler\.js$/.test(id)) return null
        if (code.includes('/* patch:vue-3.5-bum-null */')) return null  // 防重复
        const pattern = /(const\s+unmountComponent\s*=\s*\([^)]*\)\s*=>\s*\{)/
        if (!code.match(pattern)) { console.warn('...pattern not found'); return null }
        return code.replace(pattern, `$1\n    /* patch:vue-3.5-bum-null */ if (!instance) return;`)
      },
    }
  }
  ```
  验证产物 grep `(e,t,n)=>{if(!e)return;let{bum` 即生效。
- **纪律** — ① 这种"上游已知 bug 但未修复"的场景，**Vite plugin transform 阶段 patch** 比 npm postinstall patch 更稳（postinstall 会被 reinstall 覆盖；plugin 在 build 时每次生效）② `enforce: 'pre'` 确保在 esbuild/rollup 处理前 patch③ 防御性 `if (code.includes('...')) return` 防重复 patch④ pattern 未命中要 `console.warn` 而非静默吞（升级 Vue 后能立即发现 plugin 失效，需要重新适配）⑤ **只 patch build 产物，不 patch dev mode**（dev 保留原始报错方便定位应用层问题）
- **临时性 + 自动失效** — 升级到 Vue 3.5.36+/3.6+ 若官方修了 `unmountComponent` instance null 检查，plugin 自动 skip（pattern 未命中 → warn）。监控 console 是否有 `[vue-bum-null-patch] pattern not found` 警告

### 2026-06-13 Nginx types 指令覆盖/合并行为差异 — 整站 octet-stream 白屏事故（commit `08f440f` 留尾 → `f148d96` + `5c24442` 修复）

- **事故** — 用户报告"打开 /dashboard /members 直接下载名为 dashboard / members 的文件"。curl 验证 `/index.html` 返回 `Content-Type: application/octet-stream` → 浏览器把 HTML 当二进制下载而非渲染。
- **根因（极隐蔽，2 层）** —
  1. `commit 08f440f` 在 `server { ... }` block 内加 `types { application/manifest+json webmanifest; }` 块想修 webmanifest MIME 问题
  2. **Nginx `types` 指令在 server context 是"完全覆盖"语义（NOT 合并）**：从 http context 继承的 mime.types 整个被丢弃，只剩 types 块里的 MIME → `.html` 找不到 `text/html` → fallback 到 `default_type application/octet-stream` → 整站 HTML/CSS/JS/PNG 全变 octet-stream
  3. **极其隐蔽**：webhint 只查 manifest.webmanifest 不查 HTML，所以没暴露这个问题；用户浏览器可能缓存了 08f440f 之前的 HTML 没刷新，所以没立即发现
- **修复路径（commit `f148d96` + `5c24442`）**—
  - **第一步（f148d96）**：删除 tunnel.conf 两个 server block 里的所有 `types { }` block，恢复 http context mime.types 默认合并语义
  - **第二步（f148d96）**：改 `scripts/deploy-auto.sh` 增加 webmanifest MIME 注入：
    ```bash
    if ! grep -q 'application/manifest+json' /etc/nginx/mime.types 2>/dev/null; then
        sed -i '/^application\/json[[:space:]]/a\    application/manifest+json           webmanifest;' /etc/nginx/mime.types
        if grep -q 'application/manifest+json' /etc/nginx/mime.types 2>/dev/null; then
            log "webmanifest MIME type added to mime.types"
        else
            log "ERROR: webmanifest MIME sed injection failed"  # fail loud
        fi
    fi
    ```
  - **第三步（5c24442）**：原 awk 模式注入失败（猜测 mime.types 行尾 `\r` 导致 awk `next+print` 行为异常）→ 改 sed `-i` 行后追加模式 + 注入后 grep 验证
- **纪律（5 条铁律）** —
  ① **Nginx `types` 指令上下文敏感**——
  - `http` context：**合并**（additive，可加新 MIME 不丢默认）
  - `server`/`location` context：**完全覆盖**（覆盖后必须列全用到的 MIME，否则 fallback octet-stream）
  - 缺省 default：`application/octet-stream bin;`（最小集）
  ② **永远不要在 server context 加 types { } block** —— 想给 PWA 加 MIME 就在 mime.types 里加（http context include 的那个文件）
  ③ **deploy-auto.sh 注入 mime.types 必须 fail loud** ——
  - sed/awk 注入后必须 `grep -q` 验证成功才 log success，否则 `log "ERROR: ..."`
  - 注入幂等（先 grep 是否已存在）
  - 优先用 sed `-i` 而非 awk（awk 在行尾 `\r` 时行为异常）
  ④ **Webhint 不查 HTML MIME** ——
  - webhint 报 manifest MIME 错误时**只查** manifest 不查 HTML/CSS/JS
  - 加 types { } block 可能悄无声息破坏整站 MIME，**改 nginx 配置后必须 curl 验证所有响应 Content-Type**（HTML + CSS + JS + PNG + manifest + sw.js 至少 6 点）
  ⑤ **改 nginx 配置后立刻 6 点 curl 验证** —
    ```bash
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/index.html
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/  # SPA fallback
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/dashboard  # SPA route
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/sw.js
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/pwa-192.png
    curl -sk -o /dev/null -w "%{content_type}\n" https://xxx/manifest.{hash}.webmanifest
    ```
    任一返回 octet-stream 即配置错误，不要等用户报告
- **事故链时间线** —
  1. 08f440f（18:27 加 types block，覆盖 mime.types，**事故起点**）
  2. c855f0e（18:30 加 manifest.webmanifest 410）
  3. ef130ce（18:32 CLAUDE.md）
  4. 79305b7（18:40 Vue patch）
  5. 7a077dd（18:42 CLAUDE.md）
  6. 0a29290（18:49 试图"修复"types block，加完整 MIME 列表，但 types 指令在 server context 行为不变，整站仍 octet-stream）
  7. 用户报告"下载文件"
  8. f148d96（18:58 真修复：回滚 types block + 改 deploy-auto.sh）
  9. 5c24442（19:05 修 awk → sed）

### 2026-06-13 SW 污染 cache 修复 — 整站 HTML 修复后浏览器仍进不去（commit `747a735`）

- **第二阶段事故** — 服务器 MIME 修好后（`f148d96` + `5c24442`）curl 验证 `/` 返回正确 `text/html`，但**用户报告"网站还是进不去"**。curl 服务器一切正常 → 100% 是浏览器侧问题。
- **根因** — Service Worker 污染 cache：
  1. `08f440f` 部署后服务器开始返回 octet-stream HTML
  2. 用户访问时浏览器 SW（NetworkFirst 策略）**缓存了 octet-stream 响应到 `documents` cache**
  3. 服务器修复后 SW 仍可能返回缓存的 octet-stream（虽然 NetworkFirst 应优先网络，但浏览器 SW 缓存逻辑 + activate 时机导致老 cache 没及时清）
  4. `cleanupOutdatedCaches()` 只清 workbox 维护的 precache cache，**不**清 NetworkFirst/StaleWhileRevalidate 运行时创建的 cache
- **修复：sw.js 升级模式**（commit `747a735`）—
  ```js
  // web/src/sw.js
  const SW_VERSION = 'v2-cache-purge-2026-06-13'  // BUMP 触发 SW 字节变化
  self.__SW_VERSION__ = SW_VERSION

  self.skipWaiting()
  self.addEventListener('activate', (event) => {
    event.waitUntil((async () => {
      // 清空所有 cache（不只是 workbox 默认的）
      const keys = await caches.keys()
      await Promise.all(keys.map((n) => caches.delete(n)))
      await self.clients.claim()
      // 通知所有客户端 reload
      const clients = await self.clients.matchAll({ type: 'window' })
      clients.forEach((c) => c.postMessage({ type: 'SW_UPDATED', version: SW_VERSION }))
    })())
  })
  ```
  ```js
  // web/src/main.js
  useRegisterSW({
    immediate: true,
    onRegisteredSW(swUrl) {
      navigator.serviceWorker.addEventListener('message', (event) => {
        if (event.data?.type === 'SW_UPDATED') {
          setTimeout(() => window.location.reload(), 500)
        }
      })
    },
  })
  ```
- **修复链路** — 用户下次访问 → 浏览器检测 `/sw.js` 字节变化 → 安装新 SW → 立即 `skipWaiting` 激活 → `activate` 钩子清空所有 cache + `postMessage` → 客户端 `useRegisterSW` 收到 `SW_UPDATED` → `window.location.reload()` → 用户拿到全新资源
- **纪律（4 条铁律）** —
  ① **SW 污染 cache 修复必须改 sw.js** ——
  - 只改 HTML/JS/CSS 没用，浏览器 SW 还在用老 SW 文件
  - 改 sw.js 触发 SW 升级 + activate 钩子清 cache 是**唯一**标准修复路径
  ② **`cleanupOutdatedCaches()` 不够** ——
  - 它只清 workbox 维护的 precache cache
  - **不**清 NetworkFirst/StaleWhileRevalidate/CacheFirst 运行时创建的 cache
  - 真正"清空所有 cache"必须自己写：`caches.keys() + Promise.all(keys.map(caches.delete))`
  ③ **BUMP SW_VERSION 触发升级** ——
  - 浏览器通过**字节比较**检测 SW 更新（不是 SW 内容里的 manifest）
  - 改 sw.js 文件加一行 const 都会触发字节变化 → 浏览器拉新 SW → 升级流程
  - 每次事故修复或 SW 大改动时**都**应 bump 版本号
  ④ **postMessage + reload 闭环** ——
  - SW 升级后**不会**自动刷新页面（skipWaiting + clients.claim 立即接管但页面不 reload）
  - 必须 SW postMessage → 客户端监听 → `window.location.reload()`
  - 用 `setTimeout(..., 500)` 让 console.log 先显示出来再 reload
- **调试技巧** ——
  - 用户报"页面进不去"但服务器 curl 一切正常 → 100% 是 SW/浏览器 cache 问题
  - 让用户 DevTools → Application → Service Workers → 看到 SW 状态为 `activated` 且内容含新 `SW_VERSION` → SW 已升级
  - 让用户 DevTools → Application → Cache Storage → 应该看到 precache 列表**无 documents cache**（已被清空）
  - **兜底**：用户可手动 DevTools → Application → Storage → Clear site data 彻底重置

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

## 2026-06-14 方案 C：Agent 单阶段流式渐进综合架构（plan: eager-juggling-dewdrop.md）

**6 个 stage 已收官**（commits `5ce1203` `8a76750` `9862546` `d3f74df` `59cbbb1` `2f2b619` `bf61456`）。
核心改造：取消 brief/detail 双层 → 单阶段流式综合（intent → agentic_loop → critique → done）。

### 方案 C 6 条铁律（必读）

**铁律 1：跨 event loop 安全（CLAUDE.md 752/812 行铁律升级）**
所有外部 IO 客户端（AsyncAnthropic / aioredis / async_session）**禁止在模块顶部 import 阶段创建**。统一通过 `ctx: ToolContext` 注入：
```python
# ❌ 反模式（agentic_loop.py 模块顶部）
from app.core.redis import async_redis_client  # 绑定 app loop 的全局单例
client = AsyncAnthropic(...)                   # 同上

# ✅ 正模式（ctx 注入）
async def run(self, ..., ctx: ToolContext):
    redis = ctx.redis or aioredis.from_url(settings.REDIS_URL)
    llm = ctx.llm or LLMClient()
```
`ToolContext` 字段：`redis` / `llm` / `loop_id`（debugging）。Celery worker 跨 event loop 调用时由调用方注入新 client，否则触发 "Future attached to different loop"。

**铁律 2：typing import CI 检查**
任何 `app/agent/*.py` 新文件**必须**在 commit 前跑：
```bash
bash scripts/check_typing_imports.sh   # 106 文件 0 错误
```
新代码若用了 `Dict`/`List`/`Optional` 但没 `from typing import ...` → 整个模块加载失败 → 工具一调就报。Docker 模块缓存会掩盖该 bug 数天。建议集成到 pre-commit hook。

**铁律 3：SSE 事件 delta 语义显式标注**
[app/agent/protocol.py](app/agent/protocol.py) 每个 `StreamEventType` 必须在源码注释里标注 `[increment]` 或 `[snapshot]`：
- `[increment]` delta 是新增 token，前端必须 `content += delta`
- `[snapshot]` delta 是完整快照文本，前端必须 `content = delta`（替换）或不 append
- 混用会导致 2026-06-12 brief 重复输出 bug（commit `cf70ff5`）再现
- 前端 useChatStream.ts switch case 也必须标注

**铁律 4：流式 abort 安全（trace 持久化 + 悬空 tool_use sanitize）**
`chat_engine.synthesize_stream()` 必须用 `async with TraceCollector(...) as trace` 包裹：
- `TraceCollector.__aexit__` 收到 `CancelledError`/`BaseException` 时**同步**落库（不走 Celery），保证 trace 至少有 partial 记录
- `agentic_loop.run()` 在收到 `CancelledError` 或循环达到 `max_rounds` 时，必须调 `_sanitize_pending_tool_uses(messages, reason=...)`：给悬空 tool_use 追加 `tool_result: "用户已中断"` 哨兵，否则下次拼回 context 时 Anthropic API 报 400
- `_sanitize_pending_tool_uses` 必须在调下一次 LLM 前调

**铁律 5：LLMClient 接口加 model 参数用 keyword-only**
```python
async def complete(self, messages, *, model=None, system=None, ...):
    # `*` 强制所有调用走关键字
```
老代码传位置 model 必报 TypeError（炸得明显），不会静默走错模型。LRU cache key 必须含 model 维度（防不同模型互相污染缓存）。

**铁律 6：feature flag 必须保留老路径代码（不是 git revert）**
3 个 kill switch（**2026-06-29 已全部删除**，见 [## 2026-06-29 chat_engine_legacy 收官](#2026-06-29-chat_engine_legacy-30-天承诺提前-15-天收官)）：
- `AGENT_NEW_ARCHITECTURE_ENABLED: bool = True`（全局开关）
- `AGENT_REFLECTION_ENABLED: bool = True`
- `AGENT_COMPRESSION_ENABLED: bool = True`
- 关闭时由 `chat_engine.py` 内部调 `chat_engine_legacy.py`（保留作为 30 天回滚资产，**不是 in-file dead code**）
- 30 天后（2026-07-14）单独 commit 删除 `chat_engine_legacy.py` → **已提前 15 天（2026-06-29）收官** (commit `817f1ffa`)

### 2026-06-29 chat_engine_legacy 30 天承诺提前 15 天收官

**触发**：方案 C 2026-06-14 上线，配套保留 `app/agent/chat_engine_legacy.py`（460 行老 brief+detail 双层架构）作为 30 天回滚资产，配合 3 个 feature flag。30 天观察期（15 天已过 + 0 流量走 legacy + 生产 100% 走新架构）决定提前收官。

**评估结果**：
- ✅ 生产 0 流量走 legacy（3 flag 默认 `True`，`.env` / `docker-compose` 0 覆盖为 `False`）
- ✅ 无运行时 ImportError 兜底，删文件不会触发异常
- ⚠️ 4 个 unit test 断言依赖 legacy 文件 / flag，必须同步删除
- ⚠️ 提前 15 天违反 30 天承诺 → docs 加注"提前于 2026-06-29 删除"

**原子 1 commit 收官**（详见 git log）：
- **删除（1）**：`app/agent/chat_engine_legacy.py`（460 行）
- **修改（10）**：
  - `app/agent/chat_engine.py` — 移除 kill switch + `_legacy_chat_stream` 委托方法 + 相关注释
  - `app/agent/critic.py` — 移除 `AGENT_REFLECTION_ENABLED` 短路
  - `app/agent/result_compressor.py` — 移除 `AGENT_COMPRESSION_ENABLED` 短路
  - `app/agent/agentic_loop.py` — 移除 `AGENT_COMPRESSION_ENABLED` 包裹
  - `app/config.py` — 删除 3 个 settings 字段
  - `tests/unit/test_chat_engine_synthesize.py` — 删除 3 个 legacy 相关测试
  - `tests/unit/test_agent_v2_main.py` — 删除 1 个 legacy 相关测试
  - `tests/perf/conftest.py` + `test_synthesis_latency.py` — docstring 清理
  - `docs/stage5-rollout-runbook.md` — 改写回滚步骤
  - `CLAUDE.md` — 本节加注

**回滚路径**：`git revert <commit-hash>` 一行撤销 + 重新部署。< 5 分钟恢复。

### 部署必做

```bash
# 1. 跑数据库迁移（Stage 3 加 7 列）
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble \
  -f scripts/alter_agent_traces_stage3.sql

# 2. 重启 Python 进程（CLAUDE.md 752 行铁律）
docker compose restart app celery-worker
```

不跑这两步，新架构写入 `intent_category` 等列会报 `column does not exist` 500。

### 方案 C 没做的（plan 明确范围外）

- LangGraph 风格 state machine 重写
- 多 agent 独立服务（planner / executor / critic）
- 流式 ChartBlock 渐进渲染（边输出文字边出图）
- RAG 引用图谱可视化
- ASR/TTS 真流式（边录音边出文字）
- ~~30 天后删除 `chat_engine_legacy.py`（2026-07-14）~~ — **已于 2026-06-29 提前 15 天完成** (commit `817f1ffa`)（见上节"## 2026-06-29 chat_engine_legacy 30 天承诺提前 15 天收官"）


## W68 第 6+7 批纪律沉淀 (永久锚点)

> **锚点范式**: W68 第 6 批 (Verified Plans 深度审计发现) + W68 第 7 批 (grand closure 闭环) 的关键纪律固化到 CLAUDE.md. 不只在 memory 文件. 这是**永久任务模式纪律**, 未来会话启动读 CLAUDE.md 即可了解所有审计/闭环纪律.

### §1 plans 审计纪律 (W68 第 6 批 5 agent 深度审计发现)

W68 第 6 批派 5 个 Explore agent 并行全项目 plans 审计 (67 plans), 发现 5 类事故, 必须永久遵守:

1.1 **Status 段必须描述真实 commit, 不能借用同 wave 别的 plan commit** —
- **W66 批量状态化时挂错标签事故**: 状态化的 67 plans 中, 部分 Status 段描述直接复制同 wave 别的 plan commit, 而非自己 plan 真实实施的 commit. 后续审计发现多处 commit 和 plan 内容对不上 (commit 引用 `feat/xxx` 实际是别的 plan 派工分支).
- **纪律**: 每个 plan 的 Status 段必须独立验证 — `git log --all --grep="<plan-keyword>"` + `git show <commit-hash>` 必须能确认是本 plan 真实产物. 禁止批量复制粘贴

1.2 **必须读 plan 全文 + git show + grep -r 验证, 不能信 Status 段自报** —
- **盲信自报事故**: 多处 plan 的 Status 段写"已完成"但 `git log` 显示 plan 提到的功能实际从未落地. 例如 `15-17-18-cozy-bengio.md` Part 2 在 commit `4b215220` refactor 中意外删除, Status 段仍写"完成".
- **纪律**: 审计 plan 时必须 3 步并行:
  ```bash
  cat ~/.claude/plans/<plan>.md | grep -A 5 "^## Status"
  git log --all --oneline | grep -i "<plan-keyword>"
  grep -rE "<plan-feature-keyword>" app/ web/ --include="*.py" --include="*.vue" --include="*.ts"
  ```
  三者都对得上才是真实施, 缺一不可

1.3 **plans 命名应与实际内容一致 (60% 命名误导需整改)** —
- **真相**: W68 第 6 批审计发现约 60% plan 文件名与实际内容不匹配 (命名像 A 实际做 B). 命名误导 root cause 是 W62 前的"占位符命名 + 后写 plan"模式.
- **纪律**:
  - 写新 plan 时, 文件名 `xx-yy-zz-{2-词主题}-{1-词修饰}.md` 必须直接反映 plan 核心交付物
  - 不写"preparation"/"investigation"/"exploration"这类模糊词当主标题 (改用具体动作: `qa-bench-d6-benchmark-notebook.md` > `qa-bench-investigation.md`)
  - 模糊命名 plan 在 W68 第 6 批已批量重命名, 未来不允许再产生

1.4 **AGENT_STUB 必须真合并, 不能 MISCATEGORIZED** —
- **事故**: 多个 plan 状态化时被标 `AGENT_STUB` 但实际从未 merge, 仅是 plan 本身被审计 agent 阅读; 或反之, 实际已 merge 但状态标错. W68 第 6 批发现 6 个 `AGENT_STUB` 实际是 `COMPLETED` + 5 个 `COMPLETED` 实际是 `AGENT_STUB`.
- **纪律**: `AGENT_STUB` 含义精确化:
  - `AGENT_STUB` = plan 本身存在 + 没有对应的 agent 派工 + main HEAD 无相关 commit (即还没派工, 待派)
  - `COMPLETED` = plan 全部交付 + main HEAD 找到对应 commit + 实际代码落地
  - `MISCATEGORIZED` = 审计 agent 发现命名/状态与实际不符, 等待主指挥整改 (新状态)
  - 状态化必须 4 维度验证 (plan-file + git-log + grep-代码 + 审计单证), 不能仅凭 plan 内的 Status 自述

### §2 plans 实施闭环纪律 (W68 第 7 批)

W68 第 7 批 1 个 agent 收敛: 深度审计发现 5 个 NOT_IMPLEMENTED + 12 PARTIAL. 真实施 ≠ plan Status 段标 completed. 必须主指挥协调闭环.

2.1 **plans 优先 + 小修搭配 (W68 第 4 批主指挥拍板基调)** —
- **基调**: 派工以已有 plans 实施为主 + 更新过程中发现的小修为辅. 路线 A/B/C/D/E 任意组合, plans 优先 + 小修搭配, 不强制单一路线.
- **实战验证**: W68 第 4 批 (2 plan 闭环 + 13 小修) 与 W68 第 5 批 (全小修 + plans fallback) 双实战验证, 0 regression.
- **纪律**: 未来 4-9 阶段流程先 plans-list-remaining → 拍板 plan 实施 → 顺路小修 → 不强求 plans 100% (主指挥拍板决定节奏).

2.2 **plans 真实施 ≠ plans Status 段标 completed (审计出 5 个 NOT_IMPLEMENTED + 12 PARTIAL)** —
- **真相**: W68 第 6 批审计发现 67 plans 中 5 个标 completed 但实际未实施 (NOT_IMPLEMENTED) + 12 个标 completed 但仅实施 50% 以下 (PARTIAL). W68 第 7 批派 1 个 agent 100% 闭环整改 (git show + grep + commit 引用三验证).
- **纪律**:
  - Status 段标 `completed` 必须有 main HEAD commit 物证 (commit hash + 简述)
  - 部分实施标 `partial`, 不能凑 `completed`
  - 主指挥在 merge plan 实施 commit 后, 必须回头更新 plan Status 段 (闭环的核心)
  - W68 第 6+7 批沉淀的模式: **Plan 闭环 = 派 1 个 agent (A1) 重新审计全部 plans + 主指挥协调补 commit + 派 1 个 agent (A2) 写 verified plans 总报告**

2.3 **alembic 串单链纪律 (062→063→064→065, 066→067 等)** —
- 详见上方 §"2026-07-24 alembic 并行 agent 串单链纪律 (commit `1852468a6`)" 5 条铁律
- **W68 第 6+7 批新增案例**: Drive v2 PR10 (062) + Drive v2 PR11 (064) + Drive v2 PR12 (065) 串成单链 `061 → 062 → 064 → 065`; Mobile v3.2 push (066) + Drive comment mention (067) 串 `065 → 066 → 067`.
- **不变铁律**: 并行派 alembic migration agent 必须明确 down_revision 接续关系, merge 后立即 verify 只 1 个 head

2.4 **跨 session hot-fix 必须 commit message 含 "hotfix" 标识 + 主指挥 git log 跟踪** —
- **事故**: 多个 hot-fix 跨 session 派工, commit message 仅写"W68 第 5 批 hot-fix"但缺乏详细 traceback + root cause + 修复 3 段, 主指挥后续追溯困难.
- **纪律**:
  - hot-fix commit message 模板: `<type>(<scope>): W68-N-th-batch-hotfix-<short-desc> (<short-bug-id>)` + body 含 root cause 1 段 + 修复 1 段 + 验证 1 段
  - 主指挥每次 session 启动先 `git log --oneline -30 | grep -i hotfix` 跟踪上次 hot-fix chain
  - hot-fix 必须 commit 单做, 不与 feature 合并 (回滚粒度独立)

### §3 0 production code 改动铁律例外清单 (CLAUDE.md W67 第 41 步已记录 + 增补)

CLAUDE.md W67 第 41 步已记录基线: 锚点范式守卫 — 0 production code 改动 = `app/`、`web/src/`、`alembic/versions/` 老路径全部不动, 只允许 `docs/`、`memory/`、`scripts/`、`tests/` 新增. W68 第 6+7+8 批增补明确"什么算例外":

**Drive v2 系列 (PR6/PR7/PR8/PR9/PR10/PR11/PR12)** —
- 算例外: 新功能扩展 (网盘系统是 W67 后启动的新业务模块), 不破坏老任务/会议/知识库路径. 仅在 `app/services/drive_*` + `app/api/drive_*` + `web/src/views/drive/` + `web/src/views/mobile/drive/` 新增.

**Mobile UX 系列 (v3.0/v3.1/v3.2)** —
- 算例外: 移动端独立路由栈 (W66 启动), 与桌面端 component 树不共享, 不破坏老桌面路径. 仅在 `web/src/views/mobile/*` + `web/src/views/mobile/components/*` + `nut-*` 组件库新增.

**qa-bench 系列 (D1-D8 + Phase 1-3)** —
- 算例外: 测试目录, 不算业务代码. 仅在 `qa-bench/` (git submodule) + `tests/qa_bench/` 新增.

**alembic 迁移本身** —
- 算例外: 新功能必需的 schema 扩展, 不算破坏老路径. 但必须按 §2.3 串单链纪律进行, 不允许双 head.

**Plan 闭环实施 (W68 第 4 批已批)** —
- 算例外: 业务代码新增独立模块 (例如 15-17-18-cozy-bengio Part 2 重实施弥补 commit 4b215220 refactor 意外删除), 不动老路径, 仅新增 `app/services/新模块/` + 对应测试 + `docs/` + `memory/`.

**scripts/ 自动化脚本** —
- 算例外: `scripts/` 目录新增 (如 `scripts/purge_dup_owners.py`), 不算 production code.

**什么不算例外 (违规) — 明确禁止**:
- ❌ 修改 `app/services/task_service.py`/`meeting_service.py`/`knowledge_service.py` 等老模块的核心函数
- ❌ 修改 `web/src/views/Desktop*/index.vue` 老桌面页面组件
- ❌ 修改 `alembic/versions/0XX_老.py` 老迁移的 down_revision/up_revision
- ❌ 修改 `app/core/security.py`/`app/core/rate_limit.py` 老安全/限流基础设施
- ❌ 修改 `app/agent/chat_engine.py` 方案 C 6 条铁律相关文件

### §4 W68 grand closure memory 索引 (永久)

未来会话读 CLAUDE.md 即可访问所有 W68 batch grand closure 沉淀文件:

- W68 第 1 批 grand closure: `memory/w68-grand-closure-2026-07-24.md` (跨主题收口, 14 agents + Safari iOS 修复)
- W68 第 2 批 grand closure: `memory/w68-grand-closure-2026-07-24.md` (整合在第 1 批文件, 3 agents 调研/文档/baseline)
- W68 第 3 批 grand closure: `memory/w68-grand-closure-2026-07-24.md` (整合在第 1 批文件, 11 agents Drive v2 PR9 + Mobile v3.1 + qa-bench D6)
- W68 第 4 批 grand closure: `memory/w68-grand-closure-4th-batch-2026-07-24.md` (15 agents 跨主题 + Plan 闭环 2/2)
- W68 第 5 批 grand closure: `memory/w68-grand-closure-5th-batch-2026-07-24.md` (15 agents Drive v2 PR10 + Mobile v3.2 + 评论 hotfix 系列)
- W68 第 6 批 verified plans: `memory/verified-plans-w68-2026-07-24.md` (5 Explore agent 深度审计发现)
- W68 第 7 批 grand closure: `memory/w68-grand-closure-7th-batch-2026-07-24.md` (1 agent 闭环 5 NOT_IMPLEMENTED + 12 PARTIAL)
- W68 第 8 批 grand closure: `memory/w68-grand-closure-8th-batch-2026-07-24.md` (永久纪律沉淀 + 文档收口)
- 任务模式基调: `memory/w68-task-mode-paradigm-plans-first-2026-07-24.md` (plans 优先 + 小修搭配)
- alembic 串单链: `memory/w68-alembic-chain-discipline-2026-07-24.md` (锚点范式第 46 守恒 + commit 链)


## 完整历史任务链

所有"## 2026-XX-XX" 历史任务链 / "### lesson learned" 子章节 / "## 开发注意事项（历史）" 段都已迁移到 [docs/CLAUDE-history.md](./docs/CLAUDE-history.md) (P3-15 拆分于 2026-07-08).

**为什么拆分**: CLAUDE.md 拆前 645KB (8082 行) 含 60+ 历史任务链, Claude 会话启动需全量 read, 减慢 system prompt 处理. 拆分后核心 ≈ 50KB, Claude 启动更快.

**Claude 行为**:
- 新会话默认只读 CLAUDE.md 核心 (50KB) — 不再加载历史 lesson
- 历史相关查询可主动 \`@ docs/CLAUDE-history.md\` 或 \`@<path>\` 引用
- 不破坏现有所有引用 (CLAUDE.md 顶部 "当前任务链" 块保留)
