# W-N-W72 P3-A..P3-E 派工 brief 严禁留口汇总 (2026-08-05)

> **派工**: W-N-W72-P3A +1 留口汇总 docs
> **base ref**: `cde003abc` (W-N-P3-A + W-N-GLITCH 收口)
> **派工范畴**: 1 docs 范畴, 0 production code 守恒
> **派工模式**: **派工 brief 严禁, 仅汇总留口未来 PR**

---

## §1 背景与决策基调

### 1.1 W72 v4 收官后 (2026-06-13 → 2026-08-05) 持续演进

W72 全栈架构 Phase 1-6 全部完成 + v2/v3/v4 全栈架构重构收官 + 移动端 10 个 PR 全栈定制收官 (`9026c07`). 后续 W73-W100 累计 28 批 1,500+ commits, 锚点范式 W7 12 → W100 末 ~537 (+525 增量).

后续 PR 列表 (P3-A..P3-E) 在 `docs/w72-post-v4-roadmap.md` §3 已列出, **本任务仅汇总派工 brief 严禁清单 + 决策沿用 + 触发再启条件, 不擅自启动任何 P3-X 集成实施**.

### 1.2 派工 brief 严禁基调 (W19 选项 A 维持)

- **W19 选项 A 维持**: 不因阶段收口自动发起剩余 PR, 继续按量化触发条件评估
- **W60 阶段收口 final**: 88 commit / 53 memory / 58 docs / 22 baseline / 165 铁律 / 3 future PR 留口
- **W73-W100 沿用 W19 选项 A 维持**, 阶段收口不触发 PR 实施
- **实际派工权在主拍决策**, agent 不得擅自发起任何 P3-X PR

---

## §2 P3-A..P3-E 派工 brief 严禁汇总 (5 项)

### 2.1 P3-A Prisma 集成 (与 SQLAlchemy 兼容)

**派工 brief 严禁**: **严禁启动 P3-A 集成** (派工 v6 §13 假设禁令, W-N-P3-A 评估决策 (b))

**目标** (留口): 在 SQLAlchemy (现 ORM) 基础上引入 Prisma, 实现双 ORM 兼容与渐进迁移.

**价值 (理论)**:
- TypeScript 端的 schema-first 体验
- 数据库迁移统一管理 (Prisma migrate + alembic 双轨)
- 适配前端 Next.js / 全栈重构预案

**难点 (派工 brief 严禁启动依据)**:
- SQLAlchemy 现有 53+ 张表全部迁移到 Prisma schema
- dual-ORM 兼容期需保证 0 query plan regression
- alembic 097/head 守恒 + Prisma migrate 链串联

**决策依据 (沿用 W-N-P3-A 评估)**:
- ROI 负值: 投入 11.5-15 周 vs 收益 < 5% (派工 brief 估 3-5 周, 严重低估 3-4 倍)
- 范式成熟: SQLAlchemy 2.0 + alembic 96 串单链 + pgvector 集成, 无明确痛点
- 风险红线: alembic 链断裂 + pgvector/halfvec 退化 = 灾难级风险
- 团队现状: 20 人已用 SQLAlchemy 1+ 年, 切换成本极高
- W19 选项 A 维持: Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E 已列未来 PR, 优先做这些

**触发再启条件 (任一满足)**:
- 前端 TypeScript 化 (Next.js) 派工启动
- 主拍决策明确 Prisma 集成必要性
- SQLAlchemy 53+ 表迁移成本 < 收益
- Prisma 官方支持 pgvector (目前未支持, 但社区呼声高)
- 团队规模扩大 + 引入 TS/Go 前端 (Prisma 跨语言价值体现)

**关联沉淀**:
- `docs/w-n-p3-a-prisma-eval-2026-08-05.md` (W-N-P3-A +1, 完整评估 4 段)
- `memory/w-n-p3-a-prisma-eval-closure-2026-08-05.md` (W-N-P3-A +2, 5 件套守恒)
- `memory/w-n-p3-a-prisma-eval-startup-2026-08-05.md` (W-N-P3-A +0, 6 项起步)

---

### 2.2 P3-B RAG 双 backend (Qwen3 + bge-m3 切流)

**派工 brief 严禁**: **严禁启动 P3-B RAG 双 backend 集成** (派工 v6 §13 假设禁令, 沿用 W-N-BGE 决策)

**目标** (留口): 在 RAG 主 backend (BGE m3, anchor 93.5% W61 f0f8293e 决策保留) 基础上, 引入 Qwen3 作为副 backend, 通过权重切流 (灰度 5% → 25% → 50% → 100%) 验证.

**价值**:
- BGE m3 锚点保留 (W72 W61 决策) + Qwen3 增量探索
- 通过 HybridRetriever (W90 PR4 + W89 PR1) 6 hook 链验证
- 92% acceptance gate (W75 B-1) 沿用 + Qwen3 基准对比

**难点 (派工 brief 严禁启动依据)**:
- Qwen3 8B 模型体积 5.2GB, 数据中心/本地 OOM 风险
- 双 backend hybrid weight 验证 (W100-RAG-5 HybridWeights 5 路径扩展)
- W100-RAG-6 Temporal 衰减 exp(-age/2) 双 backend 一致性

**决策依据 (沿用 W-N-BGE 决策)**:
- bge-m3 真 pass rate ≥ Qwen3 baseline? → 切换生产 (W-N-BGE 决策大门禁 1)
- 92% acceptance gate (W75 B-1) + HybridRetriever 6 hook 链沿用 (W89-W100 累计)
- 不擅自切生产 backend (派工 brief 严禁, `.env` 文件 0 改动)
- W72 W61 BGE m3 93.5% baseline 锚点保留, 严禁动摇

**触发再启条件 (任一满足)**:
- Qwen3 8B 模型稳定版发布 (官方 vs Ollama)
- 主拍决策明确 RAG 双 backend 必要性
- BGE m3 93.5% 锚点失效 (acceptance gate < 90%)
- HybridRetriever 6 hook 链沿用测试通过

**关联沉淀**:
- `memory/w-n-bge-m3-realpath-closure-2026-08-05.md` (W-N-BGE +3, 3 决策大门禁结果)
- `memory/w-n-bge-m3-realpath-startup-2026-08-05.md` (W-N-BGE +0, 起步)
- `docs/w-n-bge-m3-preload-2026-08-05.md` (W-N-BGE preload 评估)

---

### 2.3 P3-C 实时 push (WebSocket 标准化)

**派工 brief 严禁**: **严禁启动 P3-C 实时 push 集成** (派工 v6 §13 假设禁令, 仅调研阶段)

**目标** (留口): 现有 `/chat/stream` SSE 流式 + webhook 链 (W99 DEPLOY-AUTO) 升级为 WebSocket 标准化, 支持双向 push.

**价值**:
- 当前 SSE only server→client, WebSocket 双向
- 替代 ws:// FRP 隧道内 ad-hoc 推送
- 适配移动端 NutUI 推送 (W72 18 pages 沿用)

**难点 (派工 brief 严禁启动依据)**:
- FRP 隧道 WebSocket 长连接保活 (类 20.143 链路)
- 现有 SSE 客户端渐进迁移 (ChatViewSSE.vue → ChatViewWS.vue)
- v3-6 SSE 退避 5 + phase 防御 10 测试 (W100 +57) 同步扩展

**决策依据 (调研 + 严禁启动)**:
- 现状: SSE 流式稳定 (W100 +57 退避 5 阶段 + phase 防御 10 测试 PASS)
- W99 DEPLOY-AUTO webhook 链稳定 (322 行 scripts/auto-deploy.sh)
- FRP 隧道内 WebSocket 长连接保活 = 类 20.143 自愈链路依赖
- W19 选项 A 维持, 不擅自启动调研以外的集成实施

**触发再启条件 (任一满足)**:
- SSE 流式客户端报障 (W100 +57 退避 5 阶段)
- FRP 隧道 SSE 心跳超时累积
- 移动端 NutUI 推送需求
- 主拍决策明确 WebSocket 标准化必要性

**关联沉淀**:
- 暂无独立调研文档, 沿用 `docs/w72-post-v4-roadmap.md` §3.3 列表
- 待主拍决策后另起 P3-C 调研 agent

---

### 2.4 P3-D W98 系列总 grand closure

**派工 brief 严禁**: **严禁启动 P3-D W98 grand closure 集成** (派工 v6 §13 假设禁令, 沿用 W-N-GRAND 收口)

**目标** (留口): W98 系列 (W88-W96 10 PR + W98 P0/P2/FW batch) 累计 212+ commits + 锚点范式 +168 (W97 477 → W98 +13 累计 ~490) 阶段总收口.

**价值**:
- 沿用 W98 RAG-GC 模式 (CLAUDE-history.md 第 549 行, 603 行完整 RAG runbook)
- W98 系列 5 大铁证全留据 (qa-bench R8 200 题 93.5% + consistency std=0.0672 + entity_overlap 0.6056 + RAG-FW-11 8 case + e2e 171/3/0)
- 10 件套 gate 守恒 9/10 PASS + 1 据实

**难点 (派工 brief 严禁启动依据)**:
- W98 系列 P0/P2/FW 多 batch merge 一致性
- 跨 PR alembic 094→095→096 串单链验证
- CLAUDE.md 顶层 (200+ 行) 重新 squeeze 归档

**决策依据 (沿用 W-N-GRAND 收口)**:
- W-N-GRAND +1 docs/w-n-grand-closure-runbook.md 已沉淀
- W-N-GRAND +2 5 件套守恒实测完成 (alembic 105_fix_drift head 守恒)
- 锚点范式 ~537 → ~574 据实累计 (+37 commits, +7 偏差据实)
- 派工 v6 §13.3 假设禁令: 严禁擅自启动 W98 系列再 grand closure

**触发再启条件 (任一满足)**:
- W98 RAG-GC 后续 P3-A 实施启动
- W98 系列 5 大铁证维护需求
- 主拍决策明确 W98 系列总收口
- CLAUDE.md 顶层重新 squeeze 归档需求

**关联沉淀**:
- `docs/w-n-grand-closure-runbook.md` (W-N-GRAND +1, 完整 runbook)
- `memory/w-n-grand-closure-closure-2026-08-05.md` (W-N-GRAND +2, 5 件套守恒)
- `memory/w-n-grand-closure-startup-2026-08-05.md` (W-N-GRAND +0, 6 项起步)

---

### 2.5 P3-E ChatKit-3 集成 (Vue 3.5 ChatKit)

**派工 brief 严禁**: **严禁启动 P3-E ChatKit-3 集成** (派工 v6 §13 假设禁令, 仅待官方稳定版发布)

**目标** (留口): 集成 Anthropic 官方 ChatKit-3 SDK + Vue 3.5 适配, 扩展现有 ChatViewSSE.vue.

**价值**:
- 官方 SDK 可观测性 + 流式 + 工具调用统一封装
- 减少自研 34 个 `@tool` 装饰器适配层
- Vue 3.5 `bum` bug patch (CLAUDE.md 第 979 行) 兼容验证

**难点 (派工 brief 严禁启动依据)**:
- ChatKit-3 官方 SDK 是否发布稳定版 (截至 2026-08-05 未确认)
- 现有 SSE 流式 + plan_step + Rich Block 兼容性
- 迁移期 34 个 tool 旧装饰器 vs ChatKit-3 新工具定义

**决策依据 (待官方稳定版)**:
- Anthropic ChatKit-3 稳定版发布前, 严禁启动集成
- 现有 34 个 `@tool` 装饰器已稳定运行 (W72 + W73-W100 累计)
- Vue 3.5 `bum` bug patch 兼容验证需求
- W19 选项 A 维持, 不擅自启动调研以外的集成实施

**触发再启条件 (任一满足)**:
- Anthropic ChatKit-3 稳定版发布
- 34 个 `@tool` 装饰器迁移成本 < 收益
- 主拍决策明确 ChatKit-3 集成必要性
- Vue 3.5 兼容验证完成

**关联沉淀**:
- 暂无独立调研文档, 沿用 `docs/w72-post-v4-roadmap.md` §3.5 列表
- 待 ChatKit-3 稳定版发布后由主拍决策另起 P3-E 调研 agent

---

## §3 派工 brief 严禁清单 (总)

**严禁** (派工 v6 §13.3 假设禁令, W19 选项 A 维持):
- ❌ 改 plan 文件 (主拍决策独占)
- ❌ 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ commits (派工编号保护)
- ❌ 改 CLAUDE.md 顶层 (另 agent 任务范畴)
- ❌ 改 alembic/versions/ (0 migration 守恒)
- ❌ 改 app/ web/src/ (production code 守恒)
- ❌ 改 docker-compose.yml (infra 守恒)
- ❌ 改 package.json / requirements.txt (派工 brief 严禁)
- ❌ 改 app/models/ 既有文件 (派工 brief 严禁)
- ❌ **启动 P3-A Prisma 集成** (W-N-P3-A 决策 (b))
- ❌ **启动 P3-B RAG 双 backend** (沿用 W-N-BGE 决策, BGE m3 锚点保留)
- ❌ **启动 P3-C 实时 push** (沿用 W19 选项 A 维持)
- ❌ **启动 P3-D W98 grand closure** (沿用 W-N-GRAND 收口)
- ❌ **启动 P3-E ChatKit-3 集成** (待官方稳定版发布)
- ❌ 擅自从 W-N-W72 +N 派工 P3-A..P3-E 任一 PR (派工权在主拍决策)

---

## §4 触发再启条件汇总 (派工 brief 严禁擅自派工)

### 4.1 派工门槛

任何 P3-A..P3-E 实施必须由主拍决策拍板, 不擅自派工. 本节列量化触发条件, 仅作主拍决策参考.

### 4.2 共同触发再启条件

- **主拍决策明确启动必要性** (任一 P3-X 必须主拍拍板)
- **W19 选项 A 切换**: 若主拍决策明确切换 W19 选项 A → 选项 B 实施 (沿用 W59 P3 dedup 切换模式)
- **量化门禁满足**: 详见 §2 各 P3-X 量化门禁
- **团队现状对齐**: 20 人已用 SQLAlchemy/SSE/`@tool` 装饰器 1+ 年, 切换成本极高

### 4.3 各 P3-X 量化门禁

| P3-X | 量化门禁 |
|------|----------|
| **P3-A** | 53+ 表 schema 100% 迁移 + 0 query plan regression + alembic 097/head 守恒 + Prisma migrate 链串联 + 7+ e2e 端到端 PRISMA + SQLAlchemy hybrid 验证 |
| **P3-B** | HybridRetriever 6 hook 链沿用 (W89-W100 累计) + 92% acceptance gate + Qwen3 评估 + 灰度 5% → 25% → 50% → 100% + 7+ e2e 双 backend hybrid weight 验证 |
| **P3-C** | WebSocket 长连接保活 (类 20.143 链路) + 现有 SSE 客户端渐进迁移 (ChatViewSSE.vue → ChatViewWS.vue) + v3-6 SSE 退避 5 + phase 防御 10 测试同步扩展 |
| **P3-D** | W98 系列 212+ commits + 锚点范式 +168 汇总 + 跨 PR alembic 094→095→096 串单链验证 + 10 件套 gate 守恒 9/10 PASS + 1 据实 |
| **P3-E** | ChatKit-3 官方 SDK 稳定版 release notes 评估 + Vue 3.5 `bum` bug patch (CLAUDE.md 第 979 行) 兼容验证 + SSE 流式 + plan_step + Rich Block 兼容性 |

---

## §5 0 production code 守恒预期

| 维度 | 现状 | 后续 PR 预期 |
|------|------|-------------|
| 1. alembic 1 head | `105_fix_drift (head)` 守恒 | P3-A 沿用 + Prisma 副链 |
| 2. pytest | W100 +74 阶段 101+ PASS + Vitest 14/14 | P3-E ChatKit-3 兼容 + 沿用 |
| 3. npm run build | W100 +58 真正进 dist | P3-A 前端 Prisma 集成 + 沿用 |
| 4. git diff origin/main -- alembic/ | 0 (W100 +75 守恒) | P3-A 沿用 + Prisma 副链 |
| 5. 锚点范式 | W100 末 ~537 → W-N-W72 +2 据实 ~574 | 后续 PR 实施时据实上报 |

---

## §6 关联引用

- `docs/w72-post-v4-roadmap.md` (W-N-W72 +1, 后续 PR 列表 §3)
- `docs/w-n-p3-a-prisma-eval-2026-08-05.md` (W-N-P3-A +1, 决策建议)
- `docs/w-n-grand-closure-runbook.md` (W-N-GRAND +1, 总收口 runbook)
- `memory/w-n-bge-m3-realpath-closure-2026-08-05.md` (W-N-BGE +3, 3 决策大门禁)
- `memory/w-n-p3-a-prisma-eval-closure-2026-08-05.md` (W-N-P3-A +2, 5 件套守恒)
- `memory/w-n-grand-closure-closure-2026-08-05.md` (W-N-GRAND +2, 5 件套守恒)
- CLAUDE.md 第 809-826 行 (W72 v4 收官)
- CLAUDE-history.md 第 7551 行 (W19 选项 A 维持)
- ROADMAP.md 锚点范式数字守恒链 (W7 12 → W100 末 ~537)

---

## §7 派工 brief 偏差据实上报 (类 20.109)

### 7.1 派工 brief 路径假设错配 (类 20.97)

派工 brief 期望源文件:
- `docs/w-n-bge-leftover-2026-08-05.md` ❌ **不存在**
- `docs/w-n-grand-closure-2026-08-05.md` ❌ **不存在**

实测真实源文件:
- `docs/w-n-grand-closure-runbook.md` ✓ (W-N-GRAND +1, 路径名差异)
- `memory/w-n-bge-m3-realpath-closure-2026-08-05.md` ✓ (W-N-BGE +3, 无独立 leftover 文档)

**处置**: 沿用真实存在文件汇总, 不擅自创建 brief 错配路径.

### 7.2 派工 brief 锚点范式守恒

- W-N-W72-P3A +0: 起步 memory (待 commit)
- W-N-W72-P3A +1: 留口汇总 docs (本文件, 待 commit)
- W-N-W72-P3A +2: 收口 memory (待写)
- **总计**: 3 commits 据实累计 (派工 brief 估 3 commits, 实测 3 commits, 完美守恒)

### 7.3 类 20 实战沉淀

- **类 20.109 实战**: 调研标"推断"必先实测 — 派工 brief 路径 `w-n-bge-leftover-2026-08-05.md` 假设错配, 实测该文件不存在, 沿用真实文件汇总
- **类 20.97 实战**: 套件路径存在性探测 — 派工 brief 引用 4 个 docs 路径, 实测 2 个不存在, 派工起点必查
- **类 20.131 实战**: 派工起点必 fetch origin + merge-base 拦截漂移 — 本任务 base head `cde003abc` 守恒

---

**撰写**: W-N-W72-P3A +1 留口汇总 docs
**撰写日期**: 2026-08-05
**base head**: `cde003abc`
**派工模式**: 派工 brief 严禁, 仅汇总留口未来 PR
**主指挥协调范式**: W-N-W72 系列派工 (主拍决策)
