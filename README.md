# 微纳米气泡课题组智能Agent系统

"小气" - 微纳米气泡课题组AI智能助手（约20人研究实验室）

## 功能特性

- **智能对话** - 支持文字/语音/图片/文件与Agent交互，多模态识别，拖拽上传，**先简要后详细双层回复**
- **联网搜索** - 搜狗微信+必应双引擎并发搜索，自动获取最新信息
- **任务管理** - 创建、分配、追踪任务，自定义提醒时间，角色权限控制（管理员可分配给任何人，普通成员只能管理自己的任务），支持垃圾桶软删除（3天后自动清除）
- **主动提醒** - 自动检查即将到期、已逾期、未确认的任务，通过企业微信主动提醒成员（每15分钟检查，Redis 去重24小时不重复，北京时间显示）
- **知识库** — 文献管理、语义搜索（pgvector）、AI 自动分类标签（动态生成具体研究方向）、对话知识自动入库、**RAG 优先问答**（基于知识库合成答案+来源引用）、**自主研究**（检测知识空白自动联网搜索补充）、**知识图谱**（自动关联 + ECharts 力导向图可视化）、**CP/动态分类体系**（从实际数据自动聚合涌现分类）、**公式计算**（内置 32 个微纳米气泡领域公式 + 分类树浏览 + 安全计算引擎 + LLM 自动提取映射）
- **长期记忆** - 用户偏好记忆、对话摘要、知识图谱构建
- **项目管理** - 课题管理、进度追踪、里程碑管理
- **成员管理** - 课题组成员信息管理
- **语音交互** - 语音输入自动转文字（faster-whisper GPU large-v3），领域术语提示词优化，AI 回复可语音播报（Edge-TTS）
- **会议系统** — 创建/管理会议、粘贴文本 AI 自动分析（智能识别摘要/对话两种格式）、实时语音转写、**声纹识别通话**（VAD + 3D-Speaker 自动识别发言人 + AI 实时对话）
- **企业微信集成** - 群机器人对话、任务派发通知、到期/逾期提醒、进度回复（消息格式兼容微信插件端）
- **微信插件支持** - 通过微信插件在普通微信内与机器人对话（需一次性注册企业微信）
- **文件管理** - MinIO 文件上传，支持对话文件
- **自动部署** - GitHub Webhook 触发，push 后自动构建部署

### 近期新增（按时间倒序）

- **声纹系统线上修复（2026-06-02 7 个 commit）** —
  - **微信 enroll_voice 状态机**：Agent `enroll_voice` 工具在微信通道下写 Redis pending_enroll，用户发语音后自动完成声纹录入（无需手动上传音频）
  - **WS 闪烁根因**：`voice.py` 函数内冗余 `import asyncio` 触发 UnboundLocalError，已修
  - **声纹模型 + 维度修正**：旧 ID `iic/speech_eres2net_sv_zh-cn_3dspeaker_16k` 已下线，换成 `iic/speech_eres2net_sv_zh-cn_16k-common`；嵌入维度 256→192（3D-Speaker 实际输出）
  - **3D-Speaker pipeline 健壮化**：3 层回退（临时文件路径 → numpy 数组 → 底层 model）；临时文件传路径 + ffmpeg 转 16kHz mono float32 抽到 `app/utils/audio.py` 复用
  - **成员管理加声纹录入入口**：右上角"声纹✓/未录入"徽章 + 底部"录入声纹"按钮 + 麦克风录制/上传文件两种方式
  - **依赖固化到 `requirements.txt`**：sortedcontainers / simplejson / soundfile 等 modelscope 传递依赖，避免 `docker compose build` 时丢失
  - **声纹库中心缓存修复**：API 注入 `Cache-Control: no-store` + `get_fingerprints` 用 `.tolist()` 避免 numpy.float32 序列化崩
  - **移动端弹窗定位修复**：`VoiceprintEnrollDialog` 显式 `append-to-body lock-scroll`，`.member-card:hover` 用 `margin-top` 代替 `transform`（不创建 containing block）
  - **头像裸路径兜底**：前端 member store `normalizeAvatarUrl` 把脏数据 `avatars/xxx` 转 `/minio/microbubble/avatars/xxx`
- **会议系统第三波 3b（2026-06-02）** — 4 个内置会议模板（组会/一对一/立项会/自由）+ 用户自建模板 + 模板→议程全链路（MeetingCreate → DB → PATCH /agenda → 通话中勾选 → 详情页展示）；通话主屏升级为大头像 + 16 声波条 LiveSpeakerPanel + AgendaPanel 议程勾选进度 + 5s 轮询 SpeakerStatsLive + TimelineScrubber 时间轴跳转；静音全屏遮罩 + NetworkStatusBar 网络状态条（显式弱网/离线 + pending 块数）+ 移动端横屏 media query；修复 activeSpeaker bug（`onTranscript` 加 `speaker_confidence > 0.45` 阈值判断）；修复 agent/core.py agenda 字段错位（写到 description → 正确字段）
- **声纹会议系统第三波 3a（2026-06-01）** — 声纹库中心（256 竖条指纹图 + 置信度历史 + 跨会议搜索）；跨会议相似度推荐（pgvector cosine）；5 分钟前会议提醒（企业微信）；voice_embedding / meeting.embedding HNSW 索引
- **声纹会议系统第二波 2b（2026-06-01）** — 4 个 AI 触发按钮：📝 总结 30s / 🌐 中英翻译 / 📋 现在总结 / 🤔 AI 提问 + Edge-TTS 播报；MinIO opus 音频存档 + 多设备同步；Redis 滑窗 + 多设备 pub/sub 广播
- **声纹会议系统第二波 2a（2026-06-01）** — 声纹识别真正启用（VAD → 3D-Speaker → pgvector → speaker_name 实时回传）；SpeakerUnidentifiedDialog 未识别说话人弹窗 + 候选成员列表；audio_level 0.1s 推送 + SpeakerStrip 5 根声波条实时跳动；speaker_claim 写入映射；VAD per-instance 避免事件循环冲突
- **第六阶段（2026-05-29）** — 粘贴会议文本 AI 自动分析 + 实时声纹通话 + AI 实时对话（VAD → 声纹 → ASR 实时流水线）
- **知识库二次升级（2026-05-27）** — 实体级知识图谱 + 科研假设生成引擎 + 量化推理（32 个内置公式 + 6 大类 24 子分类）
- **知识库升级为自主进化知识大脑（2026-05-26）** — 动态 LLM 分析 + 自动关联引擎 + RAG 优先问答 + 自主研究引擎 + 动态分类体系

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

## 当前状态

✅ **已上线运行** - 核心功能已完成，生产环境部署成功

- 云服务器部署成功（https://agent.mnb-lab.cn）
- GitHub Webhook 自动部署已配置
- 前端支持图片上传、拖拽上传
- 知识库已升级为**自主进化知识大脑**（动态 LLM 分类/标签、RAG 优先问答合成答案+来源引用、自动关联引擎建知识图谱、联网自主研究补充知识空白、健康监控检测矛盾/重复/过期、公式计算引擎 32 个内置公式 + 6 大类 24 子分类体系 + LLM 自动分类映射）
- 长期记忆系统已上线（用户偏好/对话摘要/知识图谱）
- 企业微信集成已上线（支持私聊/群聊@机器人，微信插件在普通微信内对话）
- 企业微信通知已可靠化（任务分配/到期提醒/逾期通知均可送达，消息格式兼容微信插件端）
- 任务双向通知（创建任务和即将到期时同时通知管理员和负责人）
- 语音识别准确性全面优化（修复 SILK 采样率 bug、领域提示词、beam_size 优化、结果后处理）
- 主动提醒已上线（Redis 精确调度 + Celery 10秒轮询，秒级精度，24小时内不重复提醒）
- 时间精度全面升级（分钟级截止日期、精确逾期判断、系统提示词实时注入当前时间）
- 任务权限控制已上线（管理员可分配任务给任何人，普通成员可编辑自己创建或被分配的任务）
- 自定义提醒已上线（创建任务时可设置多个自定义提醒时间点，支持"5分钟后提醒我"等自然语言）
- 微信插件身份识别已升级（多信号识别、重名消歧、验证缓存失效、插件用户 UserId 自动绑定）
- 联网搜索已上线（搜狗微信+必应双引擎并发搜索）
- 管理员身份感知（系统提示词注入当前用户姓名和角色，Agent 知道谁是管理员）
- Agent 回答准确性优化（query_tasks 返回真实负责人姓名，禁止编造人名）
- Agent 回复完整性优化（系统提示词强制完整输出 + max_tokens 提升至 8192 + 截断自动续写机制）
- 代码质量优化第一批（清理 25 处无效代码 + 9 个未使用依赖，净减 118 行）
- 代码质量优化第二批（提取 7 处后端重复逻辑 + 7 处前端重复逻辑，新建 3 个共享模块，净减 57 行）
- 代码质量优化第三批（10 个硬编码值提取到 Settings + .env.example 补全 + Docker/Nginx 优化 + 安全加固）
- 代码质量优化第四批（Dashboard/UserStore/resize 清理 + LiveTranscript WebSocket 协议自适应）
- **先简要后详细回复** -- 用户提问时先快速返回【简要】核心结论，后台并行生成【详细】展开内容并自动追加
- 开发环境 Docker 配置（docker-compose.dev.yml，热重载，轻量化）
- 部署文档已完善（docs/deploy.md），生产环境已加固（Docker 健康检查+资源限制、Nginx 限流+server_tokens off、JSON 日志、数据库备份脚本）
- **MCP 视觉服务架构预写**（切换 DeepSeek 等文本模型时支持图片识别，通过 MCP Server 解耦视觉能力）
- **前端 UI 全面升级**（2026-05-24）：建立 CSS 设计令牌（暖橙珊瑚色系）、全部 9 个页面完成升级（Dashboard、TaskView、ChatView、MeetingView、KnowledgeView、MemberView、ProjectView、MemoryView、LoginView）、玻璃拟态、丰富动效、骨架屏
- **Webhook 自动部署**（2026-05-25）：GitHub push 到 main 分支触发 webhook，云服务器自动 SSH 到本地 Windows 执行 git pull + docker compose restart app
- **微信对话响应优化**（2026-05-25）：双消息模式，用户发送后 0.5 秒内先发"🤔 收到，让我思考一下..."，后台处理完再发正式回复，解决等待无反馈问题
- **文件对话存入知识库**（2026-05-25）：上传文件给小气助手后，Agent 回复后追加"存入知识库"按钮，可一键将文件内容存入公共知识库
- **知识库前端修复**（2026-05-25）：修复文件上传失败问题（移除错误的 Content-Type 手动设置，改为由 axios 自动处理 FormData boundary）；修复 KnowledgeView/ProjectView 弹窗被遮挡问题（height: 100% + overflow-y: auto）
- **移动端侧边栏修复与动画**（2026-05-25）：修复移动端侧边栏只显示图标不显示文字的问题（根因云服务器部署流水线未生效，独立 div 抽屉绕过 Element Plus CSS），弹性滑入/遮罩模糊渐变/菜单弹簧 stagger/汉堡图标旋转过渡
- **移动端顶部栏全面优化**（2026-05-25）：汉堡按钮增大至 44px 触控区，铃铛改为 el-popover 提醒面板，头像读取真实 URL，header 移动端紧凑布局
- **任务权限简化**（2026-05-25）：所有成员可查看全部任务，仅创建人/负责人/管理员可编辑删除，降低认知负担
- **待办与进行中统一**（2026-05-25）：todo 和 in_progress 语义高度重合，统一为"进行中"，新建任务默认 in_progress，现有 todo 任务兼容显示
- **首页任务数一致性修复**（2026-05-25）：TaskView 默认 pageSize 从 20 提升至 100，匹配 Dashboard 统计数量
- **个人设置页面**（2026-05-25）：成员可编辑个人信息、上传头像（MinIO 存储 + 公网可读）
- **MinIO 头像公网访问**（2026-05-25）：头像 URL 运行时生成新鲜签名，bucket 名称自动补全，支持 nginx 代理公网访问
- **任务排序优化**（2026-05-25）：Dashboard/TaskView 中同一人的任务按优先级高→中→低排列，同优先级按截止时间早→晚排列
- **Dashboard 完成任务 UI 优化**（2026-05-25）：去掉任务行前的复选框，统一为醒目的绿色"✓ 完成"圆角按钮，避免功能重复
- **创建任务不填截止日期修复**（2026-05-25）：前端 `due_date` 初始值从空字符串改为 `null`，避免 Pydantic 422 验证错误
- **Dashboard 列表顺序修复**（2026-05-25）：后端 `list_tasks` 添加 `ORDER BY created_at DESC`，Dashboard `page_size` 从 60 提升至 100，确保最新任务始终显示
- **Webhook 异步部署**（2026-05-25）：`webhook.py` 改用 `threading.Thread` 后台执行部署脚本，先返回 200 再部署，彻底解决 GitHub 10 秒超时
- **通知面板显示具体提醒**（2026-05-25）：新增 `GET /api/v1/reminders` 端点返回待处理提醒列表（含任务标题），铃铛弹窗显示每条提醒的具体内容和时间，点击可跳转到任务管理
- **企业微信回复修复**（2026-05-25）：修复 WECHAT_API_BASE_URL 指向错误代理地址导致所有微信 API 调用 JSON 解析失败，改为直接调用 qyapi.weixin.qq.com
- **Dashboard 500 修复**（2026-05-25）：移除 `get_dashboard_stats` 中不存在的 `_get_visible_member_ids` 调用，统一使用简单的软删除过滤
- **成员登录修复**（2026-05-25）：修复 4 位成员（刘莫菲、孟祥琪、吴怡霏、蒋芦笛）password_hash 为空导致无法登录的问题，设定默认密码
- **头像上传修复**（2026-05-26）：修复 upload.py 中 `Query` 与前端 FormData 不匹配导致 prefix 回退默认值，所有头像存到 `uploads/` 的问题
- **铃铛通知去重**（2026-05-26）：`GET /reminders` 使用 `DISTINCT ON (task_id)` 按任务去重，每个任务只显示最早的待处理提醒，避免一个任务多个提醒导致铃铛数量翻倍
- **头像上传修复**（2026-05-26）：上传后自动持久化无需手动保存、Nginx `^~` 修复 MinIO 图片 404、HEIC 格式兼容、Content-Type boundary 修复手机端、MemberView 不再污染 DB 头像数据、分步错误处理确保刷新不回退
- **Dashboard 布局简化**（2026-05-27）：移除"即将到期"统计卡片、"即将到期任务"列表、"最近会议"列表，简化仪表盘布局
- **Webhook 前端构建修复**（2026-05-27）：修复 dist 未重新构建导致前端改动不生效的问题，npm run build 后重新提交 dist，端到端验证改动生效

### 待解决问题

- 9 位成员未在企业微信通讯录中，无法接收提醒推送（需在企业微信管理后台添加成员）
- 腾讯会议 API 凭据待配置

详见 [ROADMAP.md](ROADMAP.md)

## 许可证

MIT License
