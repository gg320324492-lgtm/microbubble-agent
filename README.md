# 微纳米气泡课题组智能 Agent 系统

"小气" —— 面向约 20 人科研实验室的 AI 智能助手。一套部署在课题组自有服务器上的 **Web 系统**，加一个 **Windows 桌面客户端**。

> 📥 **桌面客户端下载**：<https://releases.mnb-lab.cn/>（国内直连，免代理）
>
> 📝 更新日志见 [CHANGELOG.md](CHANGELOG.md) · 开发铁律见 [CLAUDE.md](CLAUDE.md) · 历史与路线图见 [ROADMAP.md](ROADMAP.md) · RAG 系列见 [docs/rag/README.md](docs/rag/README.md)

---

## 功能

### Web 系统（[agent.mnb-lab.cn](https://agent.mnb-lab.cn)）

| 模块 | 能力 |
|---|---|
| **智能对话** | 文字 / 语音 / 图片 / 文件多模态 Agent，SSE 流式渲染，32 个工具 |
| **知识库** | 文献管理（PDF / Word / Excel / PPT / Markdown）、语义搜索、RAG 问答、知识图谱、多模态 OCR |
| **课题组网盘** | 团队共享文件、分块上传、版本管理、回收站、三栏工作台 |
| **智能论文阅读** | PDF 结构化字段抽取 + 内嵌图识别 + 页级定位 |
| **会议系统** | 录音转写（ASR + 声纹识别 + AI 摘要），长录音断线可续、防误杀 |
| **任务 / 项目管理** | 任务分配追踪、课题里程碑、软删除垃圾桶 |
| **主动提醒** | 站内推送、用户偏好与对话摘要长期记忆 |
| **移动端** | 18 个移动页面（NutUI），iOS / Android 兼容 |

### 桌面客户端（Windows / Electron）

- **统一登录** — 与网页端同一套账号，登录一次即可用，断网也能继续工作
- **远程知识库 / 网盘** — 数据与网页端同源互通，原生体验（检索、筛选、分页、拖拽上传、文件夹导航）
- **AI 助手** — 本地优先，读写工作区，工具调用可视
- **零感托管备份** — 登录即全自动备份（AES-256-GCM 加密容器 + 密钥托管），笔记本报废数据可救；备份容器与密钥仅本人可见，且不会进入知识库与语义检索
- **自动更新通知** — 启动时自动检查（每日至多一次），发现新版本弹窗显示版本号与更新日志，一键下载安装；更新源国内直连，不依赖 GitHub

---

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.11 + FastAPI + SQLAlchemy + PostgreSQL |
| Web 前端 | Vue 3.5 + Element Plus + Vite + Pinia + ECharts |
| 移动端 | Vue 3 + NutUI 4（独立组件树，与桌面端**同 URL 不同组件**） |
| 桌面客户端 | Electron + Vue 3 + TypeScript + better-sqlite3 |
| **LLM** | **MiniMax `MiniMax-Text-01`**（OpenAI 兼容网关，现役）· 可切 Claude / 本地 ollama |
| **视觉 / OCR** | 同网关的 `VISION_MODEL`（**必须用支持图片输入的模型**） |
| 嵌入 | Qwen3-Embedding-0.6B（1024d，GPU 本地） |
| **语音** | **SenseVoice**（GPU 容器服务，现役）· faster-whisper 保留为紧急回滚 · Edge-TTS |
| 声纹 | 3D-Speaker ERes2Net + pgvector |
| 检索 | pgvector HNSW + BM25（jieba）+ tsvector 词法路 + 融合排序 |
| 缓存 / 存储 | Redis · MinIO |
| 任务队列 | Celery（worker / beat / meeting-worker 三进程） |
| 部署 | Docker Compose + FRP 内网穿透 |

> ⚠️ **切换 LLM 后端时注意**：`CLAUDE_*`（含 `VISION_MODEL`）与 `MIMO_*` / `LLM_OPENAI_COMPAT_*`
> 是**两条独立路径**。OCR / 多模态走前者、主对话走后者，**改一处不等于改另一处**。

---

## 快速开始

```bash
# 1. 配置
cp .env.example .env
# 编辑 .env：CLAUDE_API_KEY、SECRET_KEY、数据库密码
# ⚠️ SECRET_KEY / POSTGRES_PASSWORD 不能用示例值！必须生成强随机
#    python -c "import secrets; print(secrets.token_urlsafe(64))"

# 2. 安装 git hooks (新成员必做, 防止 secrets 误入库 + dist 漏 commit)
bash scripts/setup-hooks.sh

# 3. 启动
start.bat                       # Windows 一键启动所有服务
# 或 docker compose up -d

# 4. 访问
http://localhost:5173           # 前端（开发）
http://localhost:8000           # API
https://agent.mnb-lab.cn        # 生产
```

**Hook 检查**：
```bash
bash scripts/setup-hooks.sh --check   # 验证所有 hook 是否正确配置
```

详细部署：[docs/deploy.md](docs/deploy.md)

---

## 项目结构

### 根目录

```
microbubble-agent/
│
├── 核心代码 ────────────────────────────────────────────
├── app/                  # 后端 FastAPI
├── web/                  # Web 前端 Vue 3（dist/ 入库，见构建纪律）
├── apps/desktop/         # Windows 桌面客户端（Electron + Vue 3 + TS）
├── packages/             # 共享包（design-tokens 等，pnpm workspace）
├── alembic/              # 数据库迁移（严格单链，见 [CLAUDE.md]）
├── mcp_server/           # MCP 视觉服务
│
├── 部署与配置 ──────────────────────────────────────────
├── docker-compose.yml            # 生产编排
├── docker-compose.dev.yml        # 开发
├── docker-compose.test.yml       # CI 测试
├── docker-compose.override.yml   # 本地覆盖
├── Dockerfile                    # 主应用镜像
├── Dockerfile.db                 # 数据库镜像
├── Dockerfile.funasr             # ASR (FunASR/SenseVoice)
├── Dockerfile.mcp                # MCP 服务
├── Dockerfile.voice-pipeline     # 声纹流水线
├── Dockerfile.whisper            # faster-whisper（回滚用）
├── nginx/                # 反向代理配置
├── tunnel/               # FRP 内网穿透
├── config/               # 配置文件
├── observability/        # Grafana 面板（RAG observability）
├── commercial/           # 商业化私有化部署包
│
├── 数据与运行时（多数不入库）────────────────────────────
├── data/                 # MinIO / ollama / 录音运行时（⚠️ 勿删）
├── models/               # 模型缓存（HF / torch / modelscope）
├── backups/              # 数据备份
├── logs/                 # 运行日志
├── results/              # 评测与 bench 结果
│
├── 测试与工具 ──────────────────────────────────────────
├── tests/                # pytest（400 文件 / 4133 用例，实测 2026-10-10）
├── scripts/              # 部署 + 运维 + 一次性修复脚本
├── memory/               # 事件复盘笔记 + 铁律沉淀
├── docs/                 # 部署 / 迁移 / RAG / 事故复盘 / 会议纪要标准
├── desktop-conversion/   # 桌面端改造（独立 git 仓）
│
├── 入口脚本 ────────────────────────────────────────────
├── setup.ps1                     # 环境初始化
├── restart_gpu_workers.bat       # GPU worker 重启
├── funasr_entrypoint.sh          # ASR 容器入口
├── whisper_entrypoint.sh         # whisper 容器入口
│
└── 文档与配置 ──────────────────────────────────────────
    ├── README.md                 # 本文件
    ├── CLAUDE.md                 # 开发铁律（**改代码前必读**）
    ├── CHANGELOG.md              # 完整更新日志
    ├── ROADMAP.md                # 路线图 + 开发历史
    ├── AGENTS.md                 # Agent 协作说明
    ├── pyproject / requirements.txt   # Python 依赖
    ├── package.json + pnpm-*     # Node workspace
    ├── pytest.ini                # 测试配置
    └── .pre-commit-config.yaml   # 提交前门禁（5 个 hook）
```

### `app/` 后端分层

```
app/
├── agent/          # 对话引擎（intent → agentic_loop → critique）
│   └── tools/      #   工具注册表（15 模块 / 32 个 @tool）
├── api/            # 路由层（342 个路由装饰器）
│   └── v1/         #   meetings / knowledge / drive / chat ...
├── core/           # 安全 / 限流 / 审计 / LLM 客户端 / 异常
├── models/         # SQLAlchemy ORM
├── schemas/        # Pydantic 出入参
├── services/       # 业务服务层（见 CLAUDE.md 服务层表）
├── rag/            # 检索配置与评测
├── voice/          # VAD 等语音处理
└── gpu_worker/     # GPU 任务进程
```

**文档入口**：

| 文档 | 内容 |
|---|---|
| [CLAUDE.md](CLAUDE.md) | 开发铁律 · 类 20.xx 永久纪律（**改代码前必读**） |
| [docs/README.md](docs/README.md) | 文档总索引（按性质查找表） |
| [docs/incident/](docs/incident/) | 事故复盘 |
| [docs/rag/](docs/rag/README.md) | RAG 系列设计文档 |

---

## 开发须知

### 构建纪律（`web/dist` 入库，必须两段式）

```bash
# ① 先提交源码
git add web/src/ && git commit -m "fix(web): ..."
# ② 再构建、再提交产物
cd web && npm run build && cd ..
git add -f web/dist/ && git commit -m "chore(git): web/dist 重建入库 —— 配套 <上面的 hash>"
```

⚠️ **严禁** src + dist 原子同 commit（会让构建时间戳滞后一个源提交，该提交上重建不恒等）
⚠️ **唯一合法构建命令是 `npm run build`**，不要直跑 `vite build`

### 部署后必做

```bash
# 改完 Python 代码必须重启容器
docker compose up -d --force-recreate app celery-worker celery-meeting-worker celery-beat
# 重建 app 后必须 reload nginx（否则 nginx 缓存旧容器 IP，表现为 502）
docker exec microbubble-agent-nginx-1 nginx -s reload
```

### 测试

```bash
# 后端（容器内跑；注意 tests/ 不是 bind mount，需先 docker cp）
docker exec microbubble-agent-app-1 pytest tests/ -x

# 前端
cd web && npx vitest run
```

---

## 运维工具

### 会议发言人重处理（修复历史会议识别质量）

```powershell
powershell scripts/run-reprocess.ps1 -Meeting 120 -AudioPath "C:\path\audio.m4a"   # 一条龙
powershell scripts/run-reprocess.ps1 -Meeting 120 -Steps verify                    # 只验证
powershell scripts/run-reprocess.ps1 -Meeting 120 -Steps regen                     # 只重生成摘要
```

详见 [docs/reprocess-meeting.md](docs/reprocess-meeting.md)。

### 多模态索引（PPT 图片内容 → 可检索）

```bash
# 装饰横幅噪声清理（幂等，默认 dry-run，加 --apply 真执行）
docker exec microbubble-agent-app-1 python scripts/purge_banner_image_noise.py --apply
docker exec microbubble-agent-app-1 python scripts/purge_banner_image_block_extractions.py --apply

# 整页视觉转写补齐（需先部署最新代码；支持断点续跑）
docker exec -d microbubble-agent-app-1 python scripts/a46_pptx_page_pipeline.py --resume-from N
```

### 本地定时任务（已注册 schtasks）

| 任务 | 作用 | 频率 |
|---|---|---|
| `MicroBubble-SSH-Tunnel-Guard` | 反向隧道判活守护 | 每 5 分钟 |
| `MicroBubble-Daily-Backup` | 数据库备份 | 每日 02:00 |
| `MicroBubble-SeqSync-Daily` | 序列同步 | 每日 03:00 |
| `MicroBubble-GPU-ASR-Daemon` | GPU ASR 服务 | 开机 |
| `MicroBubble-Auto-Recovery` | 全链路自愈 | 开机（+2 分钟延迟） |

> ⚠️ `MicroBubble-DFT-Cleanup` 属于 **`E:\dft-service` 独立项目**，不在本仓范围。

---

## 详细文档

- 📝 [**CHANGELOG.md**](CHANGELOG.md) — 完整更新日志
- 📚 [**ROADMAP.md**](ROADMAP.md) — 路线图 + 开发历史
- 🛡️ [**CLAUDE.md**](CLAUDE.md) — 项目开发铁律沉淀（改代码前必读）
- 🐛 [**docs/incident/**](docs/incident/) — 事故复盘
- 🗂️ [**memory/**](memory/) — 事件复盘 + 教训笔记
- 📖 [**docs/deploy.md**](docs/deploy.md) — 部署与迁移文档
- 🧠 [**docs/rag/**](docs/rag/README.md) — RAG 系列设计文档（RUNBOOK / SCHEMAS / EVAL）

---

## 许可证

本仓库自 2026-09-29 起为**公开仓库**（公开前已完成历史凭据清洗）。

项目为课题组内部科研用途，未经许可不得复制或分发。
