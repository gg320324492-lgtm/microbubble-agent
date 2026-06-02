# MicroBubble Agent - 项目上下文

## 项目简介

"小气" - 微纳米气泡课题组智能Agent系统，约20人研究实验室的AI助手。

- 后端: Python 3.11 + FastAPI + SQLAlchemy + PostgreSQL + Redis + Celery
- 前端: Vue 3 + Vite + Element Plus
- AI: Claude API (Sonnet) + faster-whisper + pgvector
- 部署: 云服务器 (Nginx + FRP 服务端) + 本地电脑 (Docker 8 services + GPU Whisper)，通过 FRP 隧道连接。也支持单机部署，详见 `docs/deploy.md` 服务器迁移章节

## 当前开发阶段

**Phase 1-6 全部完成，部署已上线。** 知识库已升级为**自主进化的课题组知识大脑**。会议系统已全面升级为**实时声纹识别通话系统**，支持粘贴文本 AI 自动分析、实时语音转写 + 声纹识别 + AI 对话。详见 `ROADMAP.md`。

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
- **任务软删除/垃圾桶** — 删除任务进入垃圾桶（deleted_at 字段），支持恢复或永久删除，3天后自动清除
- **微信对话双消息模式** — 收到消息后 0.5 秒内先发"🤔 收到，让我思考一下..."，后台异步处理后发正式回复，解决等待无反馈问题
- **移动端独立抽屉架构** — 移动端侧边栏使用 el-container 外部独立 div + Vue Transition，完全绕过 Element Plus aside 的全局 CSS 干扰。桌面端 `v-if="!isMobile"` 零影响
- **通知面板** — 铃铛使用 el-popover 弹窗面板，显示每条提醒的具体内容（任务标题+提醒时间）、全部标为已读、点击跳转任务；头像读取 userStore.userInfo.avatar 真实 URL
- **任务权限模型** — 所有成员可见全部任务（降低认知负担），仅创建人/负责人/管理员可编辑、删除、恢复、永久删除
- **状态统一** — "待办"(todo) 和 "进行中"(in_progress) 语义高度重合，已统一为"进行中"。新建任务默认 in_progress，现有 todo 任务兼容显示

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
| `app/services/file_parser_service.py` | 文件内容提取（PDF/Word/Excel） |
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
| `app/voice/pipeline.py` | VAD → 声纹 → ASR 实时流水线 |

## 开发注意事项

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
- **Whisper 反幻觉必须三层防护**（2026-06-02 教训）— faster-whisper 在静音/低能量片段会**臆造**训练集记忆（YouTube 结束语"B 站风格"如"明镜与点点""点赞订阅转发打赏"）。三层防护缺一不可：
  1. **whisper_server.py**（`app/whisper_server.py`）— `condition_on_previous_text=False` + `no_speech_threshold=0.6` + `temperature=0`，并**过滤** `segment.no_speech_prob > 0.6` 的 segment（这个值在 server 里之前只读不写不过滤，浪费关键信号）
  2. **本地模型 fallback**（`app/voice/asr.py:_transcribe_local`）— 同样三件套（之前 commit `b4a5dc0` 加过，OK）
  3. **后端 NOISE_PATTERNS 兜底**（`app/api/v1/voice.py:NOISE_PATTERNS`）— 列入"明镜与点点""点赞""订阅""MING PAO"等关键词，所有 ASR 结果二次过滤。**bug 历史**：commit `b4a5dc0` 加反幻觉参数时**只改了本地模型路径，whisper_server（远程服务）漏改** — 这就是为什么线上仍出现"明镜与点点"幻觉。**验证**：用 2 秒静音（amplitude=0.001）调 /transcribe 之前会输出"明镜与点点"，修复后返回 `text: ''` `segments: []`
- **发言者检测格式** — `_parse_summary_format()` 识别 `发言人：`/`参会人：` 等字段；`_quick_parse_speakers()` 识别 `【名称】` 格式；NON_SPEAKER 黑名单过滤文档结构标签；过滤后发言者 < 2 人时回退 Claude AI 检测
- **WebSocket 认证** — `/ws/meeting/{id}/live` 需要在 URL query param 中传 `?token=xxx`，Nginx `/api` location 需要 Upgrade/Connection 头支持 WebSocket
- **数据库列迁移** — `Base.metadata.create_all()` 不会给已有表添加新列，Member/Meeting 新增的 voice_embedding, speaker_mapping 等列需要手动 ALTER TABLE
- **垃圾桶软删除** — `deleted_at` 字段标记软删除，3天后 Celery 定时任务自动永久删除。垃圾桶 API `include_deleted=true` 必须加 `deleted_at.isnot(None)`，否则会返回活跃任务。提醒查询必须过滤 `Task.deleted_at.is_(None)`
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
