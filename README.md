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

## 最新里程碑（2026-06-28）

- 🆕 **v77 P2.6 视觉体系 4 子任务全面收官（A/B/C/D 共 7 commits）**
  - **P2.6-A paper 14 组件 + 桌面 5 view + ChartBlock token dark 全面化**（commit `36049629`，移动端 9/15 → 15/15 + Rich Block 11/11 dark 化收官）
  - **P2.6-B Bug 修复 + 移动端 14 view + 6 组件 + 1 Block dark 化 + Desktop Baseline 6 路由**（commit `8905003a`，PaperHeader plain 按钮 dark bug + FallbackBlock dark 化）
  - **P2.6-C EP 多主题透传补全 (143 条规则) + Mobile baseline 6 路由（双注入登录态）**（commit `db3a31e1`，el-tree-select / date-picker / table 展开行全覆盖）
  - **P2.6-D PWA SW + 动效 + CSS-in-JS + Baseline 9 路由**（4 commits `19f42924` + `2096d3e0` + `fe896004` + `b251fc22` + `94bbe3c6`，Background Sync 4 写场景 + 6 处重复 keyframes 清理 + 12 --animation-* + 18 张 baseline）
- 🆕 **3 个生产 bug 修复** — pgvector embedding truth value bug + SQLAlchemy JSONB flag_modified + AudioPlayer Infinity:NaN（详见 [CHANGELOG.md](CHANGELOG.md) + [memory/embedding-truth-value-bug-2026-06-28.md](memory/embedding-truth-value-bug-2026-06-28.md) + [memory/sqlalchemy-jsonb-flag-modified-2026-06-28.md](memory/sqlalchemy-jsonb-flag-modified-2026-06-28.md) + [memory/audio-player-infinity-duration-2026-06-28.md](memory/audio-player-infinity-duration-2026-06-28.md)）
- 🆕 **会议 153 ASR 谐音/错识全链路清洗 hook** — `name_aliases.HARDCODED_ALIASES` 扩容 +7 条会议 153 真实 ASR 误识（`铜鹤/同客/铜棍` → `杜同贺`）+ `post_meeting_tasks` 后处理 hook 推到主路径，所有未来会议自动获得人名清洗
- ✅ **v76.2 视觉回归测试 5 件套收官** — Playwright baseline + ci-mode + max-increase + 组件级 CSS 测试，CI hard fail 拦截视觉回归（commit `f19cb780`）
- ✅ **v75 测试稳定性** — 9 个旧 fail 修复 + PR annotation + token orphan pre-commit 拦截（commit `ee46c34a`）
- ✅ **v74 CSS variable 6 主题组合自动化测试** — CI hard fail + token 白名单（commit `0f77bc29`）
- ✅ **v73 fallback 政策** — fallback orphan 修复 + CI 集成 + font-mono token（commit `1707c660` + `d8ae2a2f`）
- ✅ **v72 P1 摘要+重点摘要合并** — 主题色 TL;DR 卡显示 `meeting.summary` 完整段落，`color-mix()` + `var(--color-primary)` 6 套主题自适应（commit `eed0c409`）
- ✅ **v71 P1 议程 timeline + 每 speaker 8 条常驻** — `el-timeline` 金橙圆 dot + per-card "展开全部" 按钮（commit `46c85892`）
- ✅ **v70 P3 会议纪要视觉精简** — 顶部 TL;DR + 默认折叠发言人卡片 + Stylelint 字面色禁用（commit `bd41497e`）
- ✅ **v70 P0~P2 字面色 → token** — ~340 处 hex 替换 CSS 变量 + dark mode 全面修复（`5ea74dd5` / `f6a2bc3d` / `e4b2eec3`）
- ✅ **pre-commit hook auto-add web/dist/** — `scripts/check-dist-before-commit.sh` 自动检测 `web/src/` 改动 + 未 tracked dist 文件，避免 dist 漏 commit 导致服务器 404（commit `6565415a`，CLAUDE.md 教训第 4 次沉淀）
- ✅ **v31.3.1 whisper 容器 bind mount** — Dockerfile 删 `COPY` + bind mount 源码（commit `3f9411cb`）
- ✅ **v31.3 Whisper 常驻 GPU 8GB** — 端到端 ASR 1s（commit `93de5151`）
- ✅ **v31.2.5 rate-limit Redis ZSET 持久化** — 抗 `docker compose restart` 清零（commit `0ea97c95`）
- ✅ **v70 性能优化** — 转录 tab 删除 LLM polish + 替换 `el-select` 为 `popover`，polish-text Redis 缓存 + 前端非阻塞润色
- ✅ **v69 P0+P1 dark mode 全面重构** — 3 阶段：P0 基础 5 token + 14 EP 覆盖；P1a 6 套主题切换；P1b 10 桌面视图 dark 适配
- ✅ **v68 主题切换按钮 + SettingsView 玻璃态视觉升级**

详见 [CHANGELOG.md](CHANGELOG.md) 最新条目 + [docs/upgrade-sentence-transformers-plan.md](docs/upgrade-sentence-transformers-plan.md)

**统计**（[app/stats.json](app/stats.json), 2026-06-28 自动重算）：**1468 commits / 283K 行代码 / 738 文件 / 44 开发天数**（json 80.9K / py 58.4K / md 50.1K / vue 49.8K / js 18.6K / sql 11.2K / html 3.5K / css 2.2K / scss 0.1K）

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
