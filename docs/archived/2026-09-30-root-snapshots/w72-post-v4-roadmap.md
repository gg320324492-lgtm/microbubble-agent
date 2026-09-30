# W72 后 v4 收官 后续 PR 列表 (Roadmap, 2026-08-05)

> **任务**: W-N-W72 +1 docs 范畴, 主拍决策参考, **严禁擅自派工**
> **主仓库 commit**: `e68412de4` (base head, 守恒)
> **撰写日期**: 2026-08-05
> **关联锚点**: W-N-W72 +0..+2 (起步 + 1 docs + 1 收口 memory, 据实 2 commits 漂移)
> **关联沉淀**: `memory/w-n-w72-post-v4-startup-2026-08-05.md` + `memory/w-n-w72-post-v4-closure-2026-08-05.md`

---

## §1 背景 (W72 v4 收官)

W72 全栈架构 Phase 1-6 全部完成 + v2/v3/v4 全栈架构重构收官 + 移动端 10 个 PR 全栈定制收官 (CLAUDE.md 第 809 行, 2026-06-13 收官后 commit `9026c07`).

### 1.1 v4 收官核心

| 维度 | 数值 |
|------|------|
| **34 个 `@tool` 装饰器工具** | v2/v3/v4 累计 (任务 5 + 会议 7 + 项目 3 + 成员 2 + 知识 9 + 公式 1 + 假设 1 + 记忆 3 + 搜索 1 + 个性化 2 + 反馈 1) |
| **12 类 Rich Block 组件** | meeting / task_list / knowledge_ref / member / formula / hypothesis / project / transcript / chart + 2 兜底 |
| **18 个移动端页面** | NutUI 4 + Element Plus 路由级双栈 |
| **12 个移动端组件** | nut-* CSS 与桌面 el-* CSS 完全隔离 |
| **4 个 PWA 离线策略** | manifest + service worker (workbox) + useSafeArea + IndexedDB 兜底 |
| **43 commits 累计** | v1 修复 + v2 6 + v3 5 + v4 6 + 文档 2 + 深夜收尾 4 + 多会话并行 2 + 移动端 10 PR + 文档 5 + 部署加固 1 |
| **160+ 测试** | 87 后端 + 73 前端 + 21 录音断网 + 2 移动端 + 21 多模态 OCR |

### 1.2 v4 收官后状态

W72 收官后 (2026-06-13) → 2026-08-05 期间 (W73-W100, 28 批 1,500+ commits) 持续演进:
- W73-W85 baseline 守恒派工 (0 anchor drift)
- W86-W87 部署链 + alembic hook 修复
- W88-W96 RAG 工业级大改造 10 PR (PR1-PR10, 150 commits, 锚点 +145)
- W97 RAG 大改造收口 (10 PR 全并)
- W98 P0 + P2 batch grand closure (CHAT 系列 + RAG consistency)
- W99-W100 chat UI + chat console + RAG 收口 (16 commits, 锚点 ~537)
- W100 +49..+58 chat UI 折叠 + 气泡升级 (10 commits)
- W100 +59..+61 chat console 警告 (3 commits)
- W100 +68..+74 RAG 8 case + e2e 7/7 + Self-RAG R7/R8 + auto ingest + user feedback (8 commits)
- W100 +75 收尾 (4 项, 0 production code 守恒)

**当前文档**: 主仓库 `e68412de4` (W-N-G+ 4 FAIL 修复), docs/CHANGELOG.md + ROADMAP.md + PROJECT_INTRO.md 反映 W72 v4 收官 + 后续 W73-W100 累计沉淀.

---

## §2 已沉淀基础设施 (W72 后续 PR 起点)

### 2.1 Agent 架构 (34 个 `@tool` 装饰器)

| 模块 | 文件 | 工具数 |
|------|------|--------|
| 任务管理 | `app/agent/tools/tasks.py` | 5 |
| 会议管理 | `app/agent/tools/meetings.py` | 7 |
| 项目管理 | `app/agent/tools/projects.py` | 3 |
| 成员管理 | `app/agent/tools/members.py` | 2 |
| 知识库 | `app/agent/tools/knowledge.py` | 9 |
| 公式库 | `app/agent/tools/formula.py` | 1 |
| 假设生成 | `app/agent/tools/hypothesis.py` | 1 |
| 长期记忆 | `app/agent/tools/memory.py` | 3 |
| 联网搜索 | `app/agent/tools/search.py` | 1 |
| 个性化 | `app/agent/tools/personalization.py` | 2 |
| 反馈 | `app/agent/tools/feedback.py` | 1 |
| **合计** | **13 个 tools/ 文件** | **34** |

### 2.2 前端基础设施

- **ChatViewSSE.vue** 真实 SSE 流式 (替代 2s 轮询伪流式)
- **12 类 Rich Block 组件** (rich_blocks + tool_trace + usage + duration_ms 10 字段响应)
- **多会话侧栏** (Pinia + localStorage + 兼容 v1 单会话迁移)
- **dark mode** (CSS 变量化 + 顶栏 toggle + 主题持久化)
- **ASR/TTS 完整语音链路** (点 🎤 → 录音 → ASR → 自动发 + 🔊 TTS 播放)
- **代码高亮** (highlight.js + 6 种语言: python / js / bash / json / sql / yaml)
- **agent_traces 可观测性** (Celery 异步写表 + `/admin/agent-traces` + AgentTracesView 管理页)

### 2.3 移动端基础设施

- **路由级双栈** (`useIsMobile.js` 判定 + `resolveMobile.js` 路由适配)
- **18 个移动端页面** + 12 个移动端组件
- **4 个 PWA 策略** (manifest + sw + useSafeArea + IndexedDB 兜底)
- **iOS Safari + Android Chrome 全兼容**
- **视觉回归测试** (Playwright 5 viewport × 13 核心页面)

### 2.4 部署 + 调度基础设施

- **Docker 8 services** + **GPU Whisper** (本地电脑)
- **Celery worker + beat + meeting-worker** (3 个 worker, 类 20.149 监控)
- **FRP 隧道** (本地 → 云服务器)
- **Nginx** (云服务器静态 + 反向代理)
- **scripts/auto-deploy.sh** (W99 DEPLOY-AUTO, 322 行)
- **scripts/auto-recovery-eventlog.ps1** (W2 +N 完全自愈, 类 20.143)

### 2.5 累计沉淀

- **ANCHOR 范式**: W7 12 → W100 末 ~537 (累计 +525 增量, 28 批)
- **57 memory 文件** indexed in `memory/MEMORY.md`
- **62 docs 文件** 含 W2-W100 各批 grand closure
- **165+ 铁律** (类 20 实战 + 派工前提铁律 + W73-W100 各批新增)
- **W19 选项 A 维持** (W60 阶段收口 final, 沿用至 W100)

---

## §3 后续 PR 列表 (派工 brief 严禁擅自派工)

> ⚠️ **派工 brief 严禁擅自派工**: 本节列出后续 PR 列表**仅作主拍决策参考**, 实际派工权在主指挥. agent 不得擅自发起任何 P3-X PR.

### 3.1 P3-A Prisma 集成 (与 SQLAlchemy 兼容)

**目标**: 在 SQLAlchemy (现 ORM) 基础上引入 Prisma, 实现双 ORM 兼容与渐进迁移.

**价值**:
- TypeScript 端的 schema-first 体验
- 数据库迁移统一管理 (Prisma migrate + alembic 双轨)
- 适配前端 Next.js / 全栈重构预案

**难点**:
- SQLAlchemy 现有 53+ 张表全部迁移到 Prisma schema
- dual-ORM 兼容期需保证 0 query plan regression
- alembic 097/head 守恒 + Prisma migrate 链串联

**起点**: 不强求, 评估触发条件后由主拍决策预留.

---

### 3.2 P3-B RAG 双 backend (Qwen3 + bge-m3 切流)

**目标**: 在 RAG 主 backend (BGE m3, anchor 93.5% W61 f0f8293e 决策保留) 基础上, 引入 Qwen3 作为副 backend, 通过权重切流 (灰度 5% → 25% → 50% → 100%) 验证.

**价值**:
- BGE m3 锚点保留 (W72 W61 决策) + Qwen3 增量探索
- 通过 HybridRetriever (W90 PR4 + W89 PR1) 6 hook 链验证
- 92% acceptance gate (W75 B-1) 沿用 + Qwen3 基准对比

**难点**:
- Qwen3 8B 模型体积 5.2GB, 数据中心/本地 OOM 风险
- 双 backend hybrid weight 验证 (W100-RAG-5 HybridWeights 5 路径扩展)
- W100-RAG-6 Temporal 衰减 exp(-age/2) 双 backend 一致性

**起点**: 不强求, 评估触发条件后由主拍决策预留.

---

### 3.3 P3-C 实时 push (WebSocket 标准化)

**目标**: 现有 `/chat/stream` SSE 流式 + webhook 链 (W99 DEPLOY-AUTO) 升级为 WebSocket 标准化, 支持双向 push.

**价值**:
- 当前 SSE only server→client, WebSocket 双向
- 替代 ws:// FRP 隧道内 ad-hoc 推送
- 适配移动端 NutUI 推送 (W72 18 pages 沿用)

**难点**:
- FRP 隧道 WebSocket 长连接保活 (类 20.143 链路)
- 现有 SSE 客户端渐进迁移 (ChatViewSSE.vue → ChatViewWS.vue)
- v3-6 SSE 退避 5 + phase 防御 10 测试 (W100 +57) 同步扩展

**起点**: 不强求, 评估触发条件后由主拍决策预留.

---

### 3.4 P3-D W98 系列总 grand closure

**目标**: W98 系列 (W88-W96 10 PR + W98 P0/P2/FW batch) 累计 212+ commits + 锚点范式 +168 (W97 477 → W98 +13 累计 ~490) 阶段总收口.

**价值**:
- 沿用 W98 RAG-GC 模式 (CLAUDE.md 第 549 行, 603 行完整 RAG runbook)
- W98 系列 5 大铁证全留据 (qa-bench R8 200 题 93.5% + consistency std=0.0672 + entity_overlap 0.6056 + RAG-FW-11 8 case + e2e 171/3/0)
- 10 件套 gate 守恒 9/10 PASS + 1 据实

**难点**:
- W98 系列 P0/P2/FW 多 batch merge 一致性
- 跨 PR alembic 094→095→096 串单链验证
- CLAUDE.md 顶层 (200+ 行) 重新 squeeze 归档

**起点**: 不强求, 评估触发条件后由主拍决策预留. (沿用 W98 P2 收口 P3 派工顺序表 P3-D 项, 由 P3-A 之后续派)

---

### 3.5 P3-E ChatKit-3 集成 (Vue 3.5 ChatKit)

**目标**: 集成 Anthropic 官方 ChatKit-3 SDK + Vue 3.5 适配, 扩展现有 ChatViewSSE.vue.

**价值**:
- 官方 SDK 可观测性 + 流式 + 工具调用统一封装
- 减少自研 34 个 `@tool` 装饰器适配层
- Vue 3.5 `bum` bug patch (CLAUDE.md 第 979 行) 兼容验证

**难点**:
- ChatKit-3 官方 SDK 是否发布稳定版 (截至 2026-08-05 未确认)
- 现有 SSE 流式 + plan_step + Rich Block 兼容性
- 迁移期 34 个 tool 旧装饰器 vs ChatKit-3 新工具定义

**起点**: 不强求, 评估 ChatKit-3 稳定版发布后由主拍决策预留.

---

## §4 关键决策 (W19 选项 A 维持)

### 4.1 W19 选项 A 维持 (沿用 W60 阶段收口 final)

**铁律**: 不因阶段收口自动发起剩余 PR, 继续按量化触发条件评估.

**W19 选项 A 历史**:
- W19 (2026-xx) 拍板: 4 future PR 留未来 (Phase 8.5 + P3 dedup + P3 跨 tab + 7 E2E)
- W59 决策: P3 dedup 从选项 A 切换到选项 B 实施, 完成. (CLAUDE-history.md 第 7551 行)
- 其余 3 项继续留未来: Phase 8.5 / P3 跨 tab / 7 E2E
- W60 阶段收口 final (88 commit / 53 memory / 58 docs / 22 baseline / 165 铁律 / 3 future PR)
- W73-W100 沿用 W19 选项 A 维持, 阶段收口不触发 PR 实施

**W72 v4 收官后决策**:
- W-N-W72 +0..+2 本批 0 实质 PR 实施, 仅 docs + 调研
- P3-A..P3-E 5 个后续 PR 全部沿用 W19 选项 A 维持
- 实际派工权在主指挥, 严禁擅自派工 (派工 brief 明确)

### 4.2 锚点范式守恒

- 当前: W100 末 ~537 守恒
- W-N-W72 +0..+2 据实: 2 commits (起步 + 1 docs + 1 收口 memory, 沿用 W-N-XX +2 合并模式)
- W72 后续 PR 锚点漂移: 留口主拍决策, 由未来 PR 实施时据实上报

### 4.3 0 production code 守恒

- W-N-W72 +0 起步: 0 production code (memory 范畴)
- W-N-W72 +1 docs: 0 production code (docs/w72-post-v4-roadmap.md 范畴)
- W-N-W72 +2 收口: 0 production code (memory 范畴)
- 后续 PR P3-A..P3-E: 0 production code 守恒预期, 实际派工时由主拍决策复核

### 4.4 5 件套守恒预期

| 件 | 现状 | 后续 PR 预期 |
|----|------|-------------|
| 1. alembic 1 head | `097_meeting_processing_persistence` 守恒 | P3-A 沿用 + Prisma 副链 |
| 2. pytest | W100 +74 阶段 101+ PASS + Vitest 14/14 | P3-E ChatKit-3 兼容 + 沿用 |
| 3. npm run build | W100 +58 真正进 dist | P3-A 前端 Prisma 集成 + 沿用 |
| 4. git diff origin/main -- alembic/ | 0 (W100 +75 守恒) | P3-A 沿用 + Prisma 副链 |
| 5. 锚点范式 | W100 末 ~537 → W-N-W72 +2 据实 ~537 | 后续 PR 实施时据实上报 |

---

## §5 未来派工触发条件

> **派工门槛**: 任何 P3-A..P3-E 实施必须由主拍决策拍板, 不擅自派工. 本节列量化触发条件, 仅作主拍决策参考.

### 5.1 P3-A Prisma 集成

**触发条件 (任一满足)**:
- 前端 TypeScript 化 (Next.js) 派工启动
- 主拍决策明确 Prisma 集成必要性
- SQLAlchemy 53+ 表迁移成本 < 收益

**量化门禁**:
- 53+ 表 schema 100% 迁移 + 0 query plan regression
- alembic 097/head 守恒 + Prisma migrate 链串联
- 7+ e2e 端到端 PRISMA + SQLAlchemy hybrid 验证

### 5.2 P3-B RAG 双 backend

**触发条件 (任一满足)**:
- Qwen3 8B 模型稳定版发布 (官方 vs Ollama)
- 主拍决策明确 RAG 双 backend 必要性
- BGE m3 93.5% 锚点失效 (acceptance gate < 90%)

**量化门禁**:
- HybridRetriever 6 hook 链沿用 (W89-W100 累计)
- 92% acceptance gate + Qwen3 评估 + 灰度 5% → 25% → 50% → 100%
- 7+ e2e 双 backend hybrid weight 验证

### 5.3 P3-C 实时 push (WebSocket 标准化)

**触发条件 (任一满足)**:
- SSE 流式客户端报障 (W100 +57 退避 5 阶段)
- FRP 隧道 SSE 心跳超时累积
- 移动端 NutUI 推送需求

**量化门禁**:
- WebSocket 长连接保活 (类 20.143 链路)
- 现有 SSE 客户端渐进迁移 (ChatViewSSE.vue → ChatViewWS.vue)
- v3-6 SSE 退避 5 + phase 防御 10 测试同步扩展

### 5.4 P3-D W98 系列总 grand closure

**触发条件 (任一满足)**:
- W98 RAG-GC 后续 P3-A 实施启动
- W98 系列 5 大铁证维护需求
- 主拍决策明确 W98 系列总收口

**量化门禁**:
- W98 系列 212+ commits + 锚点范式 +168 汇总
- 跨 PR alembic 094→095→096 串单链验证
- 10 件套 gate 守恒 9/10 PASS + 1 据实

### 5.5 P3-E ChatKit-3 集成

**触发条件 (任一满足)**:
- Anthropic ChatKit-3 稳定版发布
- 34 个 `@tool` 装饰器迁移成本 < 收益
- 主拍决策明确 ChatKit-3 集成必要性

**量化门禁**:
- ChatKit-3 官方 SDK 稳定版 release notes 评估
- Vue 3.5 `bum` bug patch (CLAUDE.md 第 979 行) 兼容验证
- SSE 流式 + plan_step + Rich Block 兼容性

---

## §6 派工 brief 严禁清单

**严禁 (派工 brief 明确)**:
- ❌ 改 plan 文件 (主拍决策独占)
- ❌ 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ commits (派工编号保护)
- ❌ 改 CLAUDE.md 顶层 (另 agent 任务 #33 范畴)
- ❌ 改 alembic/versions/ (0 migration 守恒)
- ❌ 改 app/ web/src/ (production code 守恒)
- ❌ 改 docker-compose.yml (infra 守恒)
- ❌ 擅自从 W-N-W72 +N 派工 P3-A..P3-E 任一 PR (派工权在主拍决策)

**严格范畴**:
- 1 docs (本文件 `docs/w72-post-v4-roadmap.md`)
- 2 memory (`memory/w-n-w72-post-v4-startup-2026-08-05.md` + `memory/w-n-w72-post-v4-closure-2026-08-05.md`)
- 0 production code 守恒

---

## §7 沉淀文件索引

| 文件 | 状态 | 用途 |
|------|------|------|
| `docs/w72-post-v4-roadmap.md` | 本任务 W-N-W72 +1 writes | 后续 PR 列表 + 派工 brief 严禁清单 |
| `memory/w-n-w72-post-v4-startup-2026-08-05.md` | W-N-W72 +0 起点 | 6 项起步 (W73 铁律) |
| `memory/w-n-w72-post-v4-closure-2026-08-05.md` | W-N-W72 +2 收口 | 5 件套守恒实测 + 锚点漂移据实 |

---

## §8 关联引用

- CLAUDE.md 第 809-826 行 (W72 v4 收官)
- CLAUDE.md 第 545 行 (P3 派工顺序表 W98 P2 收口后预留)
- CLAUDE-history.md 第 7551 行 (W19 选项 A 维持)
- ROADMAP.md 锚点范式数字守恒链 (W7 12 → W100 末 ~537)
- CHANGELOG.md W100 +49..+58 收尾 + W100 +75 收尾
- PROJECT_INTRO.md 第 45/204/223 行 (34 个 `@tool` 工具 + 12 类 Rich Block)

---

## §9 锚点漂移据实上报

W-N-W72 +0..+2 据实: 2 commits 漂移据实 (vs 派工 brief 期望 3 commits)

- W-N-W72 +0: 0 commit (起步 memory, 沿用 W-N-XX +2 合并模式)
- W-N-W72 +1: 1 commit (docs/w72-post-v4-roadmap.md)
- W-N-W72 +2: 1 commit (memory/w-n-w72-post-v4-closure-2026-08-05.md)
- **总计**: 2 commits 漂移据实

派工 v6 §13.3 假设禁令沿用: 据实上报, 不擅自扩也不擅自缩.

---

**撰写**: W-N-W72 +1 (主拍决策参考, 严禁擅自派工)
**撰写日期**: 2026-08-05
**base head**: `e68412de4`
**主指挥协调范式**: W-N-W72 系列派工 (主拍决策)
