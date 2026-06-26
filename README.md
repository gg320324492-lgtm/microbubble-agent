# 微纳米气泡课题组智能Agent系统

> "小气" - 约 20 人研究实验室的 AI 智能助手
>
> 📝 完整更新日志见 [CHANGELOG.md](CHANGELOG.md) · 项目铁律见 [CLAUDE.md](CLAUDE.md) · 历史与路线图见 [ROADMAP.md](ROADMAP.md)

## 功能

- **智能对话** - 文字/语音/图片/文件多模态 Agent，SSE 流式 + Rich Block 渲染
- **知识库 V1+V2+V3** - 文献管理（PDF/Word/Excel/PPT/Markdown）、pgvector 语义搜索（**Qwen3-Embedding-0.6B 1024d**）、RAG 问答、知识图谱、**多模态 OCR**（图片/公式/表格/图表识别入库，4 篇 PDF 100% 端到端）
- **v28 智能论文阅读器** - PDF 12 列结构化字段 + 内嵌图 confidence ≥ 0.85 + IO Hysteresis 防跳变 + RightImageRail 精准推荐
- **任务管理** - 创建/分配/追踪 + 软删除垃圾桶（3 天自动清除，5 级紧急度颜色）
- **主动提醒** - 企业微信推送（11:00 AM 北京时间窗口，Redis 24h 去重）
- **会议系统** - 录音机模式（点"开始听会"即录）+ 离线后处理（ASR + 声纹 + AI 摘要）
- **声纹识别** - 3D-Speaker ERes2Net + pgvector 实时识别发言人（100% 段有效，已修 ERes2Net batch bug）
- **项目管理** - 课题/里程碑/进度追踪
- **企业微信** - 群机器人对话 + 任务派发 + 到期提醒
- **长期记忆** - 用户偏好 + 对话摘要 + 知识图谱
- **🐰 宠物乐园** - 仪表盘两只 CSS 3D 兔子，60fps 自主走动 + XP 成长
- **📱 移动端 PWA** - 路由级双栈（桌面 Element Plus / 移动 NutUI 4），18 个移动端页面 + iOS/Android 全兼容

## 最新里程碑（2026-06-26）

- ✅ **v31.3.1 whisper 容器 bind mount** — Dockerfile 删 `COPY` + bind mount `./app/whisper_server.py:/app/whisper_server.py:ro`，本地改源码 → `docker compose restart whisper` 即生效（commit `3f9411cb`）
- ✅ **v31.3 Whisper 常驻 + 推理加速** — 模型常驻 GPU 8GB（chat ASR 时效性优先），实测加载 18s / 端到端 ASR 1s（commit `93de5151`）
- ✅ **v31.2.5 rate-limit Redis ZSET 持久化** — `AsyncRedisRateLimiter` 启用替换 `RateLimiter`，抗 `docker compose restart` 清零，5 verify 脚本全 PASS（commit `0ea97c95`）
- ✅ **v31.2.x rate-limit 基建收官** — XFF 空 IP 兜底 + analytics regex 永久化 + `request.state.user_id` 维度 + `X-RateLimit-Policy` 头 + SSE tier 10/min + auth prefix match
- ✅ **v31 检索质量监控埋点** — 3 endpoint + 5 指标 dashboard + per-user 维度 + qa-bench 360 题 + 50 高分自动入库
- ✅ **sentence-transformers 5.6.0 升级** — 跨 3 大版本 0 破坏，删 170 行 Qwen3 wrapper，Qwen3 max_seq_length 4x → 32K，qa-bench 38%→42%（commit `c8d4df3e`）
- ✅ **v29 Qwen3 全量迁移** — GPU 启用 + Qwen3 wrapper + alembic 030 + 知识库 350/351 重算 + 列原子切换
- ✅ **v28 智能论文阅读器** — 8 phases 100% 收官，4 篇 PDF 37 张图 100% 核心不变量 + article 9 字 bug 修复
- ✅ **Phase 7 多模态知识库** — 图片/公式/表格/图表 OCR 入库

详见 [CHANGELOG.md](CHANGELOG.md) 最新条目 + [docs/upgrade-sentence-transformers-plan.md](docs/upgrade-sentence-transformers-plan.md)

**统计**（app/stats.json, 2026-06-26）：**~1380+ commits / 187K+ 行代码 / 690+ 文件 / 42 开发天数**（vue 47.5K / python 53.2K / markdown 43.0K / config 14.6K / javascript 18.5K / html 3.7K / shell 3.2K / typescript 1.5K / css 1.5K）

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.11 + FastAPI + SQLAlchemy + PostgreSQL |
| 前端 | Vue 3.5 + Element Plus + Vite 8 + Pinia + ECharts |
| AI | Claude API (Sonnet) + mimo-v2.5 多模态 |
| 语音 | faster-whisper (GPU) + Edge-TTS + silero-vad |
| 声纹 | 3D-Speaker ERes2Net + pgvector |
| 缓存 | Redis (Session + 微信状态 + 提醒 ZSET) |
| 存储 | MinIO |
| 任务队列 | Celery |
| 部署 | Docker Compose + FRP 内网穿透 |

## 快速开始

```bash
# 1. 配置
cp .env.example .env
# 编辑 .env：CLAUDE_API_KEY、SECRET_KEY、数据库密码

# 2. 启动
start.bat                       # Windows 一键启动所有服务
# 或 docker compose up -d

# 3. 访问
http://localhost:5173           # 前端（开发）
http://localhost:8000           # API
https://agent.mnb-lab.cn        # 生产
```

详细部署：[docs/deploy.md](docs/deploy.md)

## 运维工具

### 会议发言人重处理（用于修复历史会议识别质量）

```powershell
# 重处理某次会议（声纹 + DB + 纪要 + verify 一条龙）
powershell scripts/run-reprocess.ps1 -Meeting 120 -AudioPath "C:\path\audio.m4a"

# 只验证 8 字段无错标人
powershell scripts/run-reprocess.ps1 -Meeting 120 -Steps verify

# 只重生成 summary/key_points/decisions（复用 result.json）
powershell scripts/run-reprocess.ps1 -Meeting 120 -Steps regen
```

cmd.exe 用户：`scripts\run-reprocess.bat 120 verify`

详见 [docs/reprocess-meeting.md](docs/reprocess-meeting.md)。

## 项目结构

```
microbubble-agent/
├── app/           # 后端 FastAPI（agent / api / core / models / services / voice / wechat）
├── web/           # 前端 Vue 3（views / components / composables / stores）
├── scripts/       # 部署 + 运维脚本
├── frp/           # FRP 内网穿透
├── memory/        # 事件复盘笔记（incident reports / 铁律沉淀）
├── docs/          # 部署 / 迁移 / 纪要标准
├── docker-compose.yml
├── Dockerfile.whisper
├── alembic/       # 数据库迁移
├── CHANGELOG.md   # 完整更新日志
├── CLAUDE.md      # 开发铁律沉淀
└── ROADMAP.md     # 历史 + 路线图
```

## 开发工具

本地 PowerShell 三件套（已注册 schtasks）：

- `scripts/local-watchdog.ps1` — Docker 健康监控（每 5 分钟，异常时 Edge-TTS 告警）
- `scripts/local-backup.ps1` — 数据库每日备份（02:00，保留 7 天）
- `scripts/local-build-verify.ps1` — 前端 dist 校验

查看：`schtasks /Query /FO TABLE | findstr Microbubble`

## 详细文档

- 📝 [**CHANGELOG.md**](CHANGELOG.md) — 完整更新日志（按日期组织）
- 📚 [**ROADMAP.md**](ROADMAP.md) — 路线图 + 完整开发历史
- 🛡️ [**CLAUDE.md**](CLAUDE.md) — 项目开发铁律沉淀
- 🐛 [**memory/**](memory/) — 事件复盘 + 教训笔记
- 📖 [**docs/deploy.md**](docs/deploy.md) — 部署与迁移文档
- 📋 [**docs/meeting-minutes-standard.md**](docs/meeting-minutes-standard.md) — 会议纪要标准格式

## 许可证

私有项目，未经许可不得复制或分发。
