# 微纳米气泡课题组智能Agent系统

"小气" - 微纳米气泡课题组AI智能助手（约20人研究实验室）

## 功能特性

- **智能对话** - 支持文字/语音/图片/文件与Agent交互，多模态识别，拖拽上传，对话记录持久化（切换页面/刷新不丢失）
- **联网搜索** - 搜狗微信+必应双引擎并发搜索，自动获取最新信息
- **任务管理** - 创建、分配、追踪任务，自定义提醒时间，角色权限控制（管理员可分配给任何人，普通成员只能管理自己的任务），支持垃圾桶软删除（**3 天后自动清除**，每小时清理一次，垃圾桶 UI 实时显示精确倒计时：`< 1h` 精确到分钟 + 5 级紧急度颜色 + 双行展示「X 小时 Y 分后删除 / 06-04 14:30 删除」）
- **主动提醒** - 自动检查即将到期、已逾期、未确认的任务，通过企业微信主动提醒成员（每15分钟检查，Redis 去重24小时不重复，北京时间显示）
- **知识库** — 文献管理（支持 PDF/Word/Excel/**PPT**/TXT/Markdown）、语义搜索（pgvector）、AI 自动分类标签（动态生成具体研究方向）、对话知识自动入库、**RAG 优先问答**（基于知识库合成答案+来源引用）、**自主研究**（检测知识空白自动联网搜索补充）、**知识图谱**（自动关联 + ECharts 力导向图可视化）、**CP/动态分类体系**（从实际数据自动聚合涌现分类）、**公式计算**（内置 32 个微纳米气泡领域公式 + 分类树浏览 + 安全计算引擎 + LLM 自动提取映射）
- **长期记忆** - 用户偏好记忆、对话摘要、知识图谱构建
- **项目管理** - 课题管理、进度追踪、里程碑管理
- **成员管理** - 课题组成员信息管理
- **语音交互** - 语音输入自动转文字（faster-whisper GPU large-v3），领域术语提示词优化，AI 回复可语音播报（Edge-TTS）
- **会议系统** — 创建/管理会议、粘贴文本 AI 自动分析、**录音机模式**（点击「开始听会」即录，音量指示器 + 波形渲染 + 回放）、**离线后处理**（ASR 转写 + 声纹识别发言人 + AI 摘要/要点/决议 + 自动创建任务）
- **企业微信集成** - 群机器人对话、任务派发通知、到期/逾期提醒、进度回复（消息格式兼容微信插件端）
- **微信插件支持** - 通过微信插件在普通微信内与机器人对话（需一次性注册企业微信）
- **文件管理** - MinIO 文件上传，支持对话文件
- **自动部署** - GitHub Webhook 触发，push 后自动构建部署

### 近期新增（按时间倒序）

- **声纹会议系统重构 — 录音机 + 离线后处理（2026-06-04）** —
  - **完全替代**实时 WS 流式处理，改为「录音机 + 离线后处理」模式
  - **零配置开录** — 点击「开始听会」即录，无需填写任何信息
  - **录音中有反馈** — 音量指示器（竖条跳动）+ 计时器
  - **录音后可回放** — Canvas 波形渲染 + 播放/进度拖拽
  - **AI 自动补信息** — 后处理自动填充标题、参会人（声纹匹配）、摘要、要点、决议
  - **6 阶段离线流水线** — 音频转码 → ASR 转写 → 声纹识别 → AI 分析 → 自动任务 → 存储
  - **代码大幅精简** — 删除实时 WS 系统（pipeline/batch_polisher/LiveTranscript 等 3000+ 行）
- **前端优化 + 对话持久化 + PPT 支持（2026-06-04，7 commit）** —
  - **对话记录持久化** — 消息自动保存到 localStorage，切换页面/刷新不丢失，版本升级自动清除旧数据
  - **知识库支持 PPT** — python-pptx 提取文本+表格，按页分隔
  - **对话重复回复修复** — 去掉简要/详细轮询机制，直接显示回复，消除闪烁和常驻"查看详情"
  - **ECharts 升级** — 5.4.3→5.6.0 + vue-echarts 6.6.7→6.7.3
  - **Chrome 性能警告消除** — passive event listener 全局补丁（wheel/mousewheel/touchstart/touchmove）
  - **Element Plus 废弃警告修复** — el-pagination `small`→`size="small"` + el-radio `label`→`value`（6 处）
- **知识库大脑 V2 全面升级（2026-06-03，Phase 1-6）** —
  - **Phase 1: 混合检索** — BM25 关键词检索（jieba 分词 + BM25L）+ Cross-encoder 重排序（ms-marco-MiniLM）+ 三路并发（向量 + BM25 + 图谱）+ 合并去重 + 归一化
  - **Phase 2: 知识图谱** — Neo4j 5 社区版 + Neo4jService（CRUD + Cypher 查询）+ KnowledgeGraphBuilder（LLM 实体/关系提取）+ 8 种实体类型 + 8 种关系类型 + 优雅降级
  - **Phase 3: GraphRAG** — GraphRetriever（实体引导检索 + 多跳推理 + 社区摘要 + 路径发现）
  - **Phase 4: Agent 集成** — 8 个知识工具（search_knowledge/explore_knowledge_graph/find_knowledge_gaps/auto_research/compare_knowledge/summarize_topic/suggest_research）+ 混合检索集成
  - **Phase 5: Self-RAG** — SelfRAGChecker（相关性检查 + 检索判断）+ ContextCompressor（去重 + 摘要压缩）
  - **Phase 6: RAG 评估** — RAGEvaluator（faithfulness/relevancy/precision/recall + DB 持久化）
  - **关键修复** — BM25 改用 BM25L（修复 2 文档返回 0 分 bug）+ RAG 评估器语法修复
- **声纹会议系统全面修复（2026-06-03，8 commit）** —
  - **声纹全链路测试**（`8460016`）：新增 `POST /api/v1/voiceprint/test` 端点 + `VoiceTestDialog` 组件，录音→VAD→ASR→声纹一步验证
  - **声纹 enrolled API 解析修复**（`cbc503f`）：`Array.isArray(vpData)` → `vpData.members`，修复声纹状态始终显示 0
  - **参会人自拉取 + avatar schema 补全**（`cbc503f`）：MeetingRoom onMounted 自拉取 participants，`MeetingParticipant` 新增 avatar property
  - **startVoiceCreate 自动添加当前用户**（`cbc503f`）：声纹创建会议不再产生空参会人列表
  - **hangup 后处理任务派发**（`086db70` + `5a3b864` + `fddff52`）：WS hangup 时触发 `post_meeting_process`，修复 ProcessingDialog 永远卡住
  - **batch_polisher 传参修复**（`63a3e82`）：`batch_polisher` 未传入 `_live_loop_inner` 导致 hangup 处理 NameError
  - **Celery 后处理事件循环隔离**（`00b399b` + `1ed628a` + `095938a`）：独立引擎（NullPool）+ 独立 Redis 连接 + `new_event_loop`，修复 `Event loop is closed` / `Future attached to different loop`
  - **反幻觉过滤强化**（`1659f55`）：重复句阈值 3→2 + 低置信度短文本过滤（`confidence < 0.1 && len < 10`）+ 新增黑名单（"高级化链""空气机器"）
  - **ProcessingDialog 改为弹窗**（`87a33b5`）：从全屏改为 500px 弹窗，不再遮挡侧边栏
  - **头像裸路径修复**：DB 中 2 个 `avatars/xxx` 裸路径修正为完整 MinIO URL
- **声纹会议 WS 崩溃循环修复（2026-06-02 commit `6bc9687`）** — `meeting_live_ws` 在 BatchPolisher 初始化时访问 `meeting.participants` 触发 SQLAlchemy lazy load，在 async session 中走 sync IO 抛 `MissingGreenlet` → WS 关闭 (1011) → 客户端重连 → 服务端又崩 → 循环（用户看到"重连中"永远不停）。**修复**：传空数组（润色 context 不依赖 participants）
- **L3 全文精润色 3 项优化（2026-06-02 commit `e01ffdb`）**：
  - L3 `key_points` 回写到 `meeting.key_points`（从 `[{text,ts,kind}]` 提取纯 text 写 `ARRAY(String)` 列）
  - voice.py `_broadcast_loop` 订阅 `transcript_polished:{id}` 频道，L3 全文精润结果通过 Redis pub/sub 推给其他设备
  - L3 `_polish_one_chunk` 加 Redis 缓存（`key = full_polish:sha1(chunk+model)[:16]`，24h TTL），重入会话/测试环境重复触发命中
- **三级润色流水线（2026-06-02 5 commit `f57abc7..793d61e`）** — 替代逐段单条润色，消除 ASR 幻觉：
  - Phase 1：三级配置 + 消灭 3 处"发言人"硬编码 + buffer 200→1000
  - Phase 2：L2 聚批润色（BatchPolisher 攒批 30s/5段，复用 Redis 锁 + 24h 缓存）
  - Phase 3：L3 全文精润色（alembic 018 + claude-sonnet-4 + run_full_polish_pipeline 分块 + 跨块 context）
  - Phase 4+5：前端协议 + UI（useTranscript 状态机 + Tab 切换 + 状态徽章 + L3 section）
- **Webhook 持续失败 4 小时根因 + SSH 修复（2026-06-02，5 commit）** — 阿里云→GitHub HTTPS 出口 130s 超时（`curl 16 Error in HTTP2 framing layer` / `GnuTLS recv error (-110)` / `Connection timed out after 130051ms`），导致 14+ webhook delivery 失败。**4 步修复**：
  - `cd92ad6` `deploy-auto.sh` 显式 `export GIT_SSH_COMMAND="ssh -i /root/.ssh/github_deploy ..."`（belt-and-suspenders）
  - `1b8429a` `webhook.py` POST 端点加详细诊断日志（`delivery_id` / `event` / `sig_head` / `secret_len` / `payload_head`）
  - `6124b88` `deploy-auto.sh` 5 次重试 + 指数退避 + `git fetch + reset` fallback
  - 服务器端：生成 `~/.ssh/github_deploy` 密钥 + 改 `git remote set-url origin git@github.com:...` + 写 `~/.ssh/config` 让 `Host github.com` 自动用专用 key
  - **效果**：从 130s 超时 → 5s 完成，14+ webhook 全部成功
- **A11y 警告彻底清零（2026-06-02，2 commit）** — Element Plus 2.4.4 的 `el-date-picker` **所有类型**（date/datetime/daterange/datetimerange）内部 input 都用 `el-range-input` 类，prop 不会传到内部 input，没有任何 prop 能加 name。**唯一方案**：全部用原生 `<input type="date">` / `<input type="datetime-local">` + 自定义 CSS。影响 5 个文件 + 11 个 el-date-picker
  - `909eecf` `MeetingDetailView` / `ProjectView` / `TaskView` / `Dashboard` / `PasteAnalyzeDialog` 全部替换
  - `87cdd9c` `MeetingView` / `ProjectView` 改用原生 input（首次尝试 type=date 拆开但仍触发，改用原生彻底解决）
- **声纹会议全方位热修（2026-06-02，9 commit）** — 一次会话连续修了 9 个生产 bug：
  - `c5ca909` 声纹会议 live WS 静默断开（`_run_live_loop` 顶层 try/except 兜底）+ 前端 `audioLevels` 解耦 `activeSpeaker`（用 `self` 兜底，声波条不再卡死）
  - `9e827a7` Progress WS snapshot `data=null` 致前端 `TypeError`（后端不发空快照 + 前端防御性 `if (msg.data && typeof msg.data === 'object')`）
  - `3260bc2` **Celery worker [tasks] 列表缺 `post_meeting_process`**（autodiscover `related_name='tasks'` 静默失败 → 显式 `conf.imports` + `autodiscover_tasks(related_name=None)` + celery-worker 加 `./app` volume 挂载）
  - `190015f` A11y 警告修复：全项目 50+ 个 `el-input/select/textarea/date-picker/checkbox` 加 `name` 属性
  - `3e1c475` `el-date-picker type="daterange"` 内部 input 没 name（拆成两个独立 `type="date"` 选择器）
  - `58a4bf2` 声纹会议反幻觉**四重过滤**（`NOISE_PATTERNS` + segment 时长 + 短文本 + 重复模式）+ TimelineScrubber 跳转修复（`meetingDuration=elapsed` 导致 `max=currentTs`）
  - `4098d91` 声纹会议 ASR 幻觉修复（whisper_server 漏加 `condition_on_previous_text=False`）
  - `66428c4` 反幻觉**七重过滤**扩展（字母+数字纯串 / 乱码启发式 / 句子重复 / `_is_repetitive_text` 先去标点，36/36 单元测试通过）
  - `d6ec60b` 文档同步
- **KnowledgeView 白屏修复（2026-06-02）** — `onUnmounted` 钩子引用了未声明的 `chartInstance` 触发 `ReferenceError: chartInstance is not defined`，路由跳转到 `/knowledge`（实体图谱 tab 渲染后）即白屏。文件内实际变量是 `entityChartInstance`（632 行 `let entityChartInstance = null`），是 onUnmounted 内的变量名笔误。已修并重新构建 dist（`KnowledgeView-B1cCcwL2.js`），commit `fbffb88`
- **声纹系统线上修复（2026-06-02 9 个 commit）** —
  - **微信 enroll_voice 状态机**：Agent `enroll_voice` 工具在微信通道下写 Redis pending_enroll，用户发语音后自动完成声纹录入（无需手动上传音频）
  - **WS 闪烁根因**：`voice.py` 函数内冗余 `import asyncio` 触发 UnboundLocalError，已修
  - **声纹模型 + 维度修正**：旧 ID `iic/speech_eres2net_sv_zh-cn_3dspeaker_16k` 已下线，换成 `iic/speech_eres2net_sv_zh-cn_16k-common`；嵌入维度 256→192（3D-Speaker 实际输出）
  - **3D-Speaker pipeline 健壮化**：3 层回退（临时文件路径 → numpy 数组 → 底层 model）；临时文件传路径 + ffmpeg 转 16kHz mono float32 抽到 `app/utils/audio.py` 复用
  - **成员管理加声纹录入入口**：右上角"声纹✓/未录入"徽章 + 底部"录入声纹"按钮 + 麦克风录制/上传文件两种方式
  - **依赖固化到 `requirements.txt`**：sortedcontainers / simplejson / soundfile 等 modelscope 传递依赖，避免 `docker compose build` 时丢失
  - **声纹库中心缓存修复**：API 注入 `Cache-Control: no-store` + `get_fingerprints` 用 `.tolist()` 避免 numpy.float32 序列化崩
  - **移动端弹窗定位修复**：`VoiceprintEnrollDialog` 显式 `append-to-body lock-scroll`，`.member-card:hover` 用 `margin-top` 代替 `transform`（不创建 containing block）
  - **头像裸路径兜底**：前端 member store `normalizeAvatarUrl` 把脏数据 `avatars/xxx` 转 `/minio/microbubble/avatars/xxx`
  - **声纹提取精修 + 阈值统一**：`_extract_via_model` 改用 1D tensor（符合 ERes2Net 规范）；ConfidenceChart markLine 0.45→0.55 统一前后端阈值；清空 2 个旧 embedding 让用户重新录入
  - **重要提示**：ConfidenceChart 里的"水平线"是 markLine 阈值参考线（红色虚线），**不是真实置信度数据**。真实数据看 `voiceprint_history` 表
- **会议系统第三波 3b（2026-06-02）** — 4 个内置会议模板（组会/一对一/立项会/自由）+ 用户自建模板 + 模板→议程全链路（MeetingCreate → DB → PATCH /agenda → 通话中勾选 → 详情页展示）；通话主屏升级为大头像 + 16 声波条 LiveSpeakerPanel + AgendaPanel 议程勾选进度 + 5s 轮询 SpeakerStatsLive + TimelineScrubber 时间轴跳转；静音全屏遮罩 + NetworkStatusBar 网络状态条（显式弱网/离线 + pending 块数）+ 移动端横屏 media query；修复 activeSpeaker bug（`onTranscript` 加 `speaker_confidence > 0.45` 阈值判断）；修复 agent/core.py agenda 字段错位（写到 description → 正确字段）
- **声纹会议系统第三波 3a（2026-06-01）** — 声纹库中心（256 竖条指纹图 + 置信度历史 + 跨会议搜索）；跨会议相似度推荐（pgvector cosine）；5 分钟前会议提醒（企业微信）；voice_embedding / meeting.embedding HNSW 索引
- **声纹会议系统第二波 2b（2026-06-01）** — 4 个 AI 触发按钮：📝 总结 30s / 🌐 中英翻译 / 📋 现在总结 / 🤔 AI 提问 + Edge-TTS 播报；MinIO opus 音频存档 + 多设备同步；Redis 滑窗 + 多设备 pub/sub 广播
- **声纹会议系统第二波 2a（2026-06-01）** — 声纹识别真正启用（VAD → 3D-Speaker → pgvector → speaker_name 实时回传）；SpeakerUnidentifiedDialog 未识别说话人弹窗 + 候选成员列表；audio_level 0.1s 推送 + SpeakerStrip 5 根声波条实时跳动；speaker_claim 写入映射；VAD per-instance 避免事件循环冲突
- **第六阶段（2026-05-29）** — 粘贴会议文本 AI 自动分析 + 实时声纹通话 + AI 实时对话（VAD → 声纹 → ASR 实时流水线）
- **知识库二次升级（2026-05-27）** — 实体级知识图谱 + 科研假设生成引擎 + 量化推理（32 个内置公式 + 6 大类 24 子分类）
- **知识库升级为自主进化知识大脑（2026-05-26）** — 动态 LLM 分析 + 自动关联引擎 + RAG 优先问答 + 自主研究引擎 + 动态分类体系

---

**📜 详细历史和完整 commit 列表见 [ROADMAP.md](ROADMAP.md)**（按时间倒序的全部修复记录）

## 开发工具

- **Claude Code 任务通知** - 任务完成时语音提醒（Edge-TTS），音量最大，语速适中
- **本地运维三件套** (2026-06-02 已注册) - 3 个 PowerShell 脚本 + 3 个 schtasks 任务计划，云服务器 0 负载增加：
  - `scripts/local-watchdog.ps1` — Docker 服务健康监控（每 5 分钟），异常时 Edge-TTS 告警
  - `scripts/local-backup.ps1` — 数据库每日备份（02:00），保留 7 天，结构化日志
  - `scripts/local-build-verify.ps1` — 前端 dist 校验（`npm run build` 后跑），本地拦截异常 dist
  - `scripts/install-local-ops.bat` — 一键注册上述 3 个 Windows 任务计划
  - ✅ **3 个 schtasks 已注册并验证**（2026-06-02 03:32）：`MicrobubbleWatchdog`（每 5 分钟）/ `MicrobubbleDBBackup`（每日 02:00）/ `MicrobubbleBuildVerify`（手动）
  - 查看：`schtasks /Query /FO TABLE | findstr Microbubble`
  - 卸载：`schtasks /Delete /TN "MicrobubbleWatchdog" /F`（其他两个同理）

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.11 + FastAPI + SQLAlchemy + PostgreSQL |
| 前端 | Vue 3 + Element Plus + Vite + Pinia + ECharts |
| AI | Claude API (支持代理地址) + mimo-v2.5 多模态 |
| 语音 | faster-whisper (GPU) + Edge-TTS + silero-vad |
| 声纹识别 | 3D-Speaker ERes2Net (ModelScope) + pgvector 余弦匹配 |
| 向量搜索 | pgvector + text2vec-base-chinese（余弦相似度语义搜索） |
| 知识图谱 | 自动关联引擎（语义相似 + 概念重叠 + 主题共享），ECharts 可视化 |
| RAG 问答 | 检索增强生成（语义搜索 → 阈值分类 → LLM 合成 → 来源引用） |
| 自主研究 | 知识空白检测 → 联网搜索（搜狗+必应）→ LLM 提取 → 自动入库 |
| 缓存 | Redis (Session + 微信状态 + 提醒调度 ZSET) |
| 存储 | MinIO |
| 任务队列 | Celery + Redis |
| 部署 | Docker Compose + FRP 内网穿透 |

## 部署架构

支持两种部署模式：

### 模式 A：云服务器 + 本地电脑 FRP 穿透（当前）

```
用户 → 云服务器 (Nginx + SSL + FRP 服务端) → FRP 隧道 → 本地电脑 (全部 Docker 服务 + GPU Whisper)
```

- **云服务器**（2核 2G）：只运行 Nginx 反向代理 + FRP 服务端，轻量无压力
- **本地电脑**（有 GPU）：运行全部应用服务（app、PostgreSQL、Redis、MinIO、Whisper GPU、Celery）
- **FRP 隧道**：本地 8000 端口穿透到云服务器，用户通过 `https://agent.mnb-lab.cn` 访问

### 模式 B：单机部署（高性能服务器）

如需迁移到一台高性能服务器独立运行（不再需要云服务器 + FRP），硬件建议：

| 组件 | 最低 | 推荐 |
|------|------|------|
| CPU | 8核16线程 | 9950X3D / 9950X |
| GPU | NVIDIA 8GB VRAM | RTX 5090 32GB |
| 内存 | 32GB | 128GB DDR5 |
| 存储 | 2TB SSD | 1TB NVMe(系统) + 8TB SSD(数据) |

完整迁移指南详见 [docs/deploy.md](docs/deploy.md#八服务器迁移单机部署)，包含数据迁移清单、配置修改列表、Nginx + SSL 配置、运维脚本等。

## 快速开始

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的配置
# 必填项：CLAUDE_API_KEY、SECRET_KEY、数据库密码等
```

### 2. 本地电脑部署（一键脚本）

```bash
# Windows
start.bat   # 启动所有服务
stop.bat    # 停止所有服务
status.bat  # 查看服务状态

# 或手动启动
docker compose up -d

# 开发模式（热重载，改代码自动重启）
docker compose -f docker-compose.dev.yml up -d
```

### 3. 云服务器部署

```bash
# 首次部署
sudo bash scripts/deploy-cloud.sh

# 配置自动部署（GitHub Webhook）
cp scripts/webhook.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable webhook && systemctl start webhook
# 然后在 GitHub 仓库 Settings → Webhooks 添加:
# URL: https://agent.mnb-lab.cn/webhook
# Secret: 与 .env.webhook 中 WEBHOOK_SECRET 一致
# Events: Just the push event
```

配置完成后，每次 `git push` 到 main 分支会自动部署。

> **注意**：阿里云服务器偶发无法连接 GitHub，若 push 后未自动部署，可通过 SSH 手动触发：
> ```bash
> # 生成 HMAC 签名
> SIG=$(echo -n '{"ref":"refs/heads/main","pusher":{"name":"fix"},"commits":[{"id":"fix"}]}' | openssl dgst -sha256 -hmac "microbubble-deploy-2026" | awk '{print "sha256="$2}')
> # 触发部署
> ssh deploy@60.205.93.8 "curl -s -X POST http://localhost:9001/webhook -H 'Content-Type: application/json' -H 'X-GitHub-Event: push' -H 'X-Hub-Signature-256: $SIG' -d '{\"ref\":\"refs/heads/main\",\"pusher\":{\"name\":\"fix\"},\"commits\":[{\"id\":\"fix\"}]}'"
> ```

> **警告：Nginx 配置必须与 Git 同步！** webhook 部署时 `deploy-auto.sh` 会用 Git 仓库中的 `nginx/conf.d/tunnel.conf` 直接覆盖云服务器的 `/etc/nginx/conf.d/default.conf`。如果在云服务器上手动修改了 nginx 配置，必须同步更新 Git 中的 `tunnel.conf`，否则下次部署会将手动修改覆盖丢失，导致站点不可用。

### 多站点说明

云服务器同时托管 `agent.mnb-lab.cn`（Vite SPA）和 `mnb-lab.cn`（Next.js 静态导出），Nginx 配置在仓库 `nginx/conf.d/tunnel.conf` 中统一维护。修改此文件时必须确保两个站点配置完整，否则部署时会将另一个站点清掉。

### 4. FRP 穿透配置

```bash
# 本地电脑启动 FRP 客户端
cd frp
./frpc.exe -c frpc.toml
```

### 5. 访问系统

- **生产环境**: https://agent.mnb-lab.cn
- **本地开发**: http://localhost:5173 (前端) / http://localhost:8000 (API)
- **API文档**: https://agent.mnb-lab.cn/docs
- **MinIO控制台**: http://localhost:9001

## 项目结构

```
microbubble-agent/
├── app/                     # 后端应用
│   ├── agent/              # AI Agent核心（工具调用、对话管理）
│   ├── api/                # API接口（31个端点，全部带认证）
│   │   └── v1/            # 版本化API
│   ├── core/               # 核心模块（安全、Redis、Celery、日志、限流）
│   ├── models/             # SQLAlchemy数据模型
│   ├── schemas/            # Pydantic验证模型
│   ├── services/           # 业务服务层（10个服务）
│   ├── voice/              # 语音服务（ASR、TTS）
│   └── wechat/             # 企业微信模块（消息、身份、分析、调度）
├── web/                     # 前端应用
│   └── src/
│       ├── views/          # 页面组件（含ChatView图片识别）
│       ├── layouts/        # 布局组件
│       ├── stores/         # Pinia状态管理
│       └── router/         # 路由配置
├── scripts/                 # 部署和工具脚本
├── frp/                     # FRP内网穿透配置
├── docker-compose.yml       # Docker编排（7个服务）
├── Dockerfile.whisper       # Whisper GPU镜像
├── alembic/                 # 数据库迁移
└── .env.example             # 环境变量示例
```

## 开发指南

### 后端开发

```bash
# 安装依赖
pip install -r requirements.txt

# 运行开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端开发

```bash
cd web

# 安装依赖
npm install

# 运行开发服务器
npm run dev
```

## API接口

所有接口均需 JWT 认证（除登录外）。

### 核心模块
- `POST /api/v1/chat` - 智能对话（支持工具调用）
- `POST /api/v1/chat/image` - 图片识别对话
- `POST /api/v1/chat/file` - 文件对话（PDF/Word/Excel）
- `WebSocket /api/v1/chat/ws` - 流式对话

### 业务模块
- `GET/POST /api/v1/tasks` - 任务管理（CRUD + 统计 + Dashboard）
- `GET/POST /api/v1/meetings` - 会议管理（含转写分析）
- `GET/POST /api/v1/members` - 成员管理
- `GET/POST /api/v1/projects` - 项目管理（含里程碑）
- `GET/POST /api/v1/knowledge` - 知识库（语义搜索 + 文件上传 + 动态分类 + 标签云 + 知识图谱）
- `GET/POST /api/v1/memory` - 长期记忆管理

### 集成模块
- `POST /api/v1/wechat/callback` - 企业微信回调
- `POST /api/v1/tencent-meeting/webhook` - 腾讯会议回调
- `POST /api/v1/upload` - 文件上传

### Agent 工具（17个）
- `create_task` / `query_tasks` / `update_task` - 任务管理
- `create_meeting` / `query_meetings` - 会议管理
- `query_members` - 成员查询
- `query_projects` / `generate_project_plan` - 项目管理
- `search_knowledge` / `save_conversation_knowledge` - 知识库
- `web_search` - 联网搜索
- `save_memory` / `search_memory` / `forget_memory` - 长期记忆
- `summarize_meeting_transcript` - 会议转录总结
- `query_all_member_tasks` - 全员任务状况（仅管理员/组长）

详细文档: https://agent.mnb-lab.cn/docs

## 当前状态（2026-06-03）

✅ **已上线运行** — 核心功能已完成，生产环境部署成功（https://agent.mnb-lab.cn）

### 🔧 最新改进（2026-06-03）
- **会议模板重构**（commit `d619f33`）— 删除独立 MeetingTemplatesView 页面（91 行），模板选择/管理内嵌到 MeetingView 创建会议对话框。卡片式选择器（4 builtin + 自定义模板）+ 行内 CRUD（编辑/删除/新建）+ 编辑功能**真正可用**（之前是 stub）
- **Webhook 性能修复**（commit `7ec6ce0`）— `HTTPServer` → `ThreadingHTTPServer` 多线程，0.001s 响应（之前 15-22s）
- **垃圾桶系统全修**（4 commit 链）— 3 bug 全修 + beat 调度 1h + 前端双行精准倒计时

### 后端能力
- **会议系统**（声纹通话）— VAD → 3D-Speaker 声纹（192 维 ERes2Net）→ pgvector 匹配 → ASR 流水线；4 内置会议模板 + 议程全链路；**微信 enroll_voice 状态机**（自动完成声纹录入）
- **知识库**（自主进化知识大脑）— 动态 LLM 分析 / 自动关联引擎 / RAG 优先问答 / 自主研究 / 实体级知识图谱 / 科研假设生成 / 量化推理（32 内置公式）
- **任务管理** — 软删除垃圾桶（3 天后自动清理，**1h 巡检**）+ 精准倒计时（5 级颜色 + 双行显示）+ Redis 精确提醒（10s 精度）+ 双向通知
- **长期记忆** — 用户偏好 / 对话摘要 / 知识图谱
- **企业微信** — 微信插件方案（私聊 + 群聊 + 外部用户兼容）
- **三级润色流水线** — L1 实时透传 / L2 聚批润色（30s 攒批）/ L3 全文精润色（claude-sonnet-4）
- **反幻觉七重过滤** — 36/36 单元测试通过

### 前端能力
- 设计系统：暖橙珊瑚色 CSS 设计令牌（`web/src/assets/variables.css`）
- 9 个页面全部完成 UI 升级：Dashboard / TaskView / ChatView / MeetingView / KnowledgeView / MemberView / ProjectView / MemoryView / LoginView
- 移动端：独立抽屉架构 + 横屏 media query + 紧凑顶栏
- 声纹录入 UI（MemberView 卡片徽章 + 录入弹窗）
- 声纹库中心（256 竖条指纹图 + 跨会议相似度推荐）

### 部署 / 运维
- 阿里云 2核2G：Nginx + FRP 服务端 + Webhook（多线程，0.001s 响应）
- 本地 Windows（32核+GPU）：Docker 8 services + GPU Whisper
- **Webhook 自动部署**：GitHub push → SSH 拉取（130s→5s）+ ThreadingHTTPServer（0.001s 响应）
- 本地运维三件套：watchdog / backup / build-verify（schtasks 注册）

### 详细历史

完整 commit 链和按时间倒序的修复记录见 [ROADMAP.md](ROADMAP.md)（2320 行）

### 待解决问题

- 9 位成员未在企业微信通讯录中，无法接收提醒推送（需在企业微信管理后台添加成员）
- 腾讯会议 API 凭据待配置

## 许可证

MIT License
