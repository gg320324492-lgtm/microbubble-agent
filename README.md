# 微纳米气泡课题组智能 Agent 系统

"小气" —— 面向约 20 人科研实验室的 AI 智能助手。一套部署在课题组自有服务器上的 **Web 系统**，加一个 **Windows 桌面客户端**。

> 📥 **桌面客户端下载**：<https://releases.mnb-lab.cn/>（国内直连，免代理）
>
> 📝 更新日志见 [CHANGELOG.md](CHANGELOG.md) · 开发铁律见 [CLAUDE.md](CLAUDE.md) · 历史与路线图见 [ROADMAP.md](ROADMAP.md) · RAG 系列见 [docs/rag/README.md](docs/rag/README.md)

## 功能

### Web 系统（[agent.mnb-lab.cn](https://agent.mnb-lab.cn)）

- **智能对话** — 文字/语音/图片/文件多模态 Agent，SSE 流式渲染
- **知识库** — 文献管理（PDF/Word/Excel/PPT/Markdown）、语义搜索、RAG 问答、知识图谱、多模态 OCR
- **课题组网盘** — 团队共享文件、分块上传、版本管理与回收站
- **智能论文阅读器** — PDF 结构化字段抽取 + 内嵌图识别
- **会议系统** — 录音转写（ASR + 声纹识别 + AI 摘要）
- **任务管理 / 项目管理** — 任务分配追踪、课题里程碑
- **主动提醒 / 长期记忆** — 站内推送、用户偏好与对话摘要
- **移动端 PWA** — 18 个移动页面，iOS/Android 兼容

### 桌面客户端（Windows）

- **统一登录** — 与网页端同一套账号，登录一次即可用，断网也能继续工作
- **远程知识库 / 网盘** — 数据与网页端同源互通，原生体验（检索、筛选、分页、拖拽上传、文件夹导航）
- **AI 助手** — 本地优先，读写工作区、工具调用可视
- **零感托管备份** — 登录即全自动备份（AES-256-GCM 加密容器 + 密钥托管），笔记本报废数据可救

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.11 + FastAPI + SQLAlchemy + PostgreSQL |
| Web 前端 | Vue 3.5 + Element Plus + Vite + Pinia + ECharts |
| 桌面客户端 | Electron + Vue 3 + TypeScript + better-sqlite3 |
| AI | Claude API (Sonnet) + mimo-v2.5 多模态 |
| 语音 | faster-whisper (GPU) + Edge-TTS + silero-vad |
| 声纹 | 3D-Speaker ERes2Net + pgvector |
| 缓存 | Redis |
| 存储 | MinIO |
| 任务队列 | Celery |
| 部署 | Docker Compose + FRP 内网穿透 |

## 快速开始

```bash
# 1. 配置
cp .env.example .env
# 编辑 .env：CLAUDE_API_KEY、SECRET_KEY、数据库密码
# ⚠️ SECRET_KEY 不能用默认占位符 `change-this-to-a-...`！必须生成强随机
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

## 项目结构

```
microbubble-agent/
├── app/               # 后端 FastAPI（agent / api / core / models / services / voice）
├── web/               # Web 前端 Vue 3（views / components / composables / stores）
├── apps/desktop/      # Windows 桌面客户端（Electron + Vue 3 + TypeScript）
├── packages/          # 共享包（design-tokens 等）
├── scripts/           # 部署 + 运维脚本
├── alembic/           # 数据库迁移
├── docs/              # 部署 / 迁移 / 纪要标准
├── memory/            # 事件复盘笔记（incident reports / 铁律沉淀）
├── CHANGELOG.md       # 完整更新日志
├── CLAUDE.md          # 开发铁律沉淀
└── ROADMAP.md         # 历史 + 路线图
```

## 运维工具

### 会议发言人重处理（修复历史会议识别质量）

```powershell
powershell scripts/run-reprocess.ps1 -Meeting 120 -AudioPath "C:\path\audio.m4a"   # 一条龙
powershell scripts/run-reprocess.ps1 -Meeting 120 -Steps verify                    # 只验证
powershell scripts/run-reprocess.ps1 -Meeting 120 -Steps regen                     # 只重生成摘要
```

详见 [docs/reprocess-meeting.md](docs/reprocess-meeting.md)。

### 本地定时任务（已注册 schtasks）

- `scripts/local-watchdog.ps1` — Docker 健康监控（每 5 分钟）
- `scripts/local-backup.ps1` — 数据库每日备份（02:00，保留 7 天）
- `scripts/local-build-verify.ps1` — 前端 dist 校验

## 详细文档

- 📝 [**CHANGELOG.md**](CHANGELOG.md) — 完整更新日志
- 📚 [**ROADMAP.md**](ROADMAP.md) — 路线图 + 开发历史
- 🛡️ [**CLAUDE.md**](CLAUDE.md) — 项目开发铁律沉淀
- 🐛 [**memory/**](memory/) — 事件复盘 + 教训笔记
- 📖 [**docs/deploy.md**](docs/deploy.md) — 部署与迁移文档
- 🧠 [**docs/rag/**](docs/rag/README.md) — RAG 系列设计文档（RUNBOOK / SCHEMAS / EVAL）

## 许可证

私有项目，未经许可不得复制或分发。
