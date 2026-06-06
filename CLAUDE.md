# MicroBubble Agent - 项目上下文

## 项目简介

"小气" - 微纳米气泡课题组智能Agent系统，约20人研究实验室的AI助手。

- 后端: Python 3.11 + FastAPI + SQLAlchemy + PostgreSQL + Redis + Celery
- 前端: Vue 3 + Vite + Element Plus（原版 `web/`，极简版 `web-minimal/`）
- AI: Claude API (Sonnet) + faster-whisper + pgvector
- 部署: 云服务器 (Nginx + FRP 服务端) + 本地电脑 (Docker 8 services + GPU Whisper)，通过 FRP 隧道连接。也支持单机部署，详见 `docs/deploy.md` 服务器迁移章节

## 当前开发阶段

**Phase 1-6 全部完成，部署已上线。** 知识库已升级为**自主进化的课题组知识大脑**。会议系统已重构为**录音机 + 离线后处理模式**（替代实时 WS 流式处理），支持零配置开录、音量指示器、波形回放、AI 自动填充会议信息。**2026-06-05 最新进展**：创建极简风格前端项目 `web-minimal/`（完全独立，可直接运行）+ UI 设计风格展示（5 种风格示例）。详见 [ROADMAP.md](ROADMAP.md#极简风格前端项目2026-06-05) 和 [README.md](README.md#近期新增按时间倒序)。

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
