# W72 第 1 批派工调研依据 — 15 agents 4 路线派工 + 10 步合并顺序表 (2026-07-24)

> **任务来源**: W72 第 1 批 A-1 派工调研基础 — W68 第 14 批 D-4 W71+W72 拍板续 (主拍必读) + W71 batch 33 commits 已合并 main (锚点范式第 206 守恒) + W71 D-1 派工纪要 v8 段 8 实战升 v8 必备
>
> **主基调**: W72 第 1 批 15 agents 派工调研, 4 路线 15 agents, 锚点范式 W71 206 → W72 220 守恒 (+14 守恒预期), 0 失败
>
> **W72 派工依据 (主拍必读 5 文档)**: `docs/w71-dispatch-candidates-v8-2026-07-24.md` 段 8 + `docs/w71-final-decision-2026-07-24.md` §2 W71 4 选项 + §3 W72 4 选项 + `docs/w72nd-batch-orchestration-2026-07-24.md` (5 B 路线 agents 接口契约) + `docs/w70-w71-plans-backlog-survey-v2-2026-07-24.md` §3 子 plan ② 实施清单 + `docs/qa-bench-d8-comprehensive-survey-2026-07-24.md` §2 真验证
>
> **W72 起步纪律 4 项必读 (派工 v8 段 8 实战)**:
> 1. W71 B 路线 5 agents 全部 commit + merge 后才启动 W72
> 2. 7 维评分数据 + KB 闭环回归 (baseline 71+7 守恒)
> 3. 子 plan ③ 3 组件独立回归 (NavRail + ThinkingModeSwitch + ChatBreadcrumb 必含)
> 4. 派工前提错误必含 W71 实战 13 类 (v8 段 7 升级)
>
> **W72 锚点范式**: 第 207 守恒 (主指挥协调范式第 45 次派工)
>
> **0 production code 改动铁律**: 14/15 守恒预期 (1 例外 B-1 NavRail.vue 250 行 + SessionSidebar 重构, 派工 v6 允许 web/src/components/chat/ 范畴)
>
> **W19 选项 A 维持**: 4 留未来 PR 不发起新排期 (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E)

---

## §1 TL;DR

W72 第 1 批 15 agents 派工调研, 4 路线 15 agents, 锚点范式 W71 206 → W72 220 守恒 (+14 守恒预期), 0 失败。

| 维度 | W71 batch 实际 | W72 第 1 批预期 |
|------|---------------|---------------|
| 派工 agents 数 | 15 | 15 |
| 工期 | 2 周 | 2 周 |
| 锚点范式 | W70 168 → W71 206 (+38) | W71 206 → W72 220 (+14) |
| 路线 A | 4 (部署 + 派工 v7 + plans verify + grand closure memo) | 4 (部署 + 派工 v9 + plans 真验证 + grand closure 预期版) |
| 路线 B | 5 (qa-bench 7 维 + 5 道防线 + Celery + KB 闭环 + Dashboard) | 5 (NavRail + ThinkingModeSwitch + 顶栏 3-zone + 跨端点 + 6 主题 dark) |
| 路线 C | 3 (qa-bench D8 + SubAgent orch + notify v2 回测) | 3 (容器镜像 rebuild + 商业化 24 人月季度 + ppt-word 5 缺口) |
| 路线 D | 3 (派工 v8 + 6 类文档 + 锚点范式) | 3 (派工 v9 + 6 类文档 + 锚点范式) |
| 0 prod code 例外 | 1 (5/15 例外已批, 含 web QaBenchDashboard) | 1 (B-1 NavRail.vue 250 行 + SessionSidebar 重构) |
| 派工前提错误 | 13 类 (v7 10 + v8 3) | 13 类 (v7 10 + v8 3, 沿用) |
| baseline 守恒 | 71 PASS + 7 SKIP 守恒 | 71 PASS + 7 SKIP 守恒 (B-1 web 改动后必含) |

**核心结论**: W72 第 1 批 15 agents 是 W71 实战后的下一阶段派工, 调研基础来自 5 文档 + 派工 v8 段 8 起步纪律 4 项必读 + 派工 v6 段 5 反馈 5 类别全部沉淀 + W71 B 路线 5 agents 实战接口协调经验。

---

## §2 W72 派工依据 (5 文档引用 + 派工 v8 段 8 起步纪律)

### 2.1 派工依据 5 文档引用表

| # | 文档路径 | 行数 | 引用段 | 派工依据 |
|---|---------|------|--------|----------|
| 1 | `docs/w71-dispatch-candidates-v8-2026-07-24.md` | 376 | 段 8 W72 子 plan ③ 起步纪律 | W72 子 plan ③ 起步前必含 4 项 + 派工必写 4 项 + 24h 必填 3 项 |
| 2 | `docs/w71-final-decision-2026-07-24.md` | 806 | §2 W71 4 选项 + §3 W72 4 选项 | W71 选项 A 派工 + W72 选项 A 推荐 3 agents 起步 + 失败回滚 5 类 |
| 3 | `docs/w72nd-batch-orchestration-2026-07-24.md` (派生) | ~288 | 5 B 路线 agents 接口契约 | B-1 7 维评分 + B-2 5 道防线 + B-3 Celery 回滚 + B-4 KB 闭环 + B-5 Dashboard 接口契约 |
| 4 | `docs/w70-w71-plans-backlog-survey-v2-2026-07-24.md` | 150 | §3 子 plan ② 实施清单 | W72 子 plan ② 实施清单 + W71 子 plan ③ 实施清单 |
| 5 | `docs/qa-bench-d8-comprehensive-survey-2026-07-24.md` | 564 | §2 真验证 + §3 七项实施前置 | qa-bench D8 七项实施前置 (题库版本锁定 + 数据脱敏 + 模型/endpoint 锁定 + 阈值与 gate + CI secret 检查 + baseline 对照 + 失败重跑/产物保留策略) |

### 2.2 派工 v8 段 8 起步纪律 (4 项必读)

派工 v8 段 8 是 W71 D-1 实战升 v8 必备, 必含 4 项:

1. **W71 B 路线 5 agents 全部 commit + merge 后才启动 W72**
   - B-1 `seven_dim.py` + `weights.json` 必须 main HEAD 可查
   - B-2 `kb_queue/dedup.py` + `length_filter.py` + `llm_refusal.py` + `sensitive_words.py` + `auto_intake_audit.py` 必须 main HEAD 可查
   - B-3 `auto_intake_rollback_task.py` + `save_to_kb.py` 重写必须 main HEAD 可查
   - B-4 `audit_trigger.py` + Celery beat 调度必须 main HEAD 可查
   - B-5 `QaBenchDashboard.vue` + `smoke_200.py` + `qa-bench-smoke.yml` 必须 main HEAD 可查
   - 验证命令: `git log --oneline main | grep -E "w71st-batch-(b1|b2|b3|b4|b5)"` 期望 ≥ 5 commits 输出 (本任务实测: **10 commits** — 5 features + 5 merges, 大于 ≥ 5 期望 ✅)

2. **7 维评分数据 + KB 闭环回归 (baseline 71+7 守恒)**
   - QaBenchDashboard 启动后必能拉取 7 维权重 schema 数据
   - KB 闭环审计触发后必能写入 audit log
   - baseline 71+7 守恒验证: pytest 新增 PASS = 0 + 新增 SKIP = 0

3. **子 plan ③ 3 组件独立回归 (NavRail + ThinkingModeSwitch + ChatBreadcrumb)**
   - 必先 W71 子 plan ② 数据可用后才动手 UI 改造
   - 任何 UI 改动必先 grep 看是否影响老 desktop / mobile 路由栈
   - NavRail 涉及路由级双栈 (桌面 EP + 移动 NutUI) 必须双端验证
   - ThinkingModeSwitch 涉及 chat engine 必须先回归 `chat_engine.py` 方案 C 6 条铁律相关功能
   - ChatBreadcrumb 涉及知识库 metadata 必先回归 `knowledge_service.py`

4. **派工前提错误必含 W71 实战 13 类 (v7 10 + v8 3)**
   - v7 沿用 10 类: alembic 串单链 / PS 5.1 / plans 真验证 / web `npm run build` / baseline 守恒 / 浏览器老 SW cache / PWA 永久禁用 / checkSwBlacklist self-loop / setInterval timer 句柄 / heartbeat console.warn 静默
   - v8 新增 3 类: 跨 agent 接口契约 / SubAgent type hint / 派生新任务真验证

---

## §3 W72 起步纪律 4 项实战验证 (派工 v8 段 8 必读)

派工 v8 段 8 实战验证 (本任务 Step 1 必先真验证, 派工 v4 铁律 3 实战):

### 3.1 W71 B 路线 5 agents 全部 commit + merge

```bash
git log --oneline main | grep -E "w71st-batch-(b1|b2|b3|b4|b5)" | wc -l
```

**实测结果**: 10 commits (5 features + 5 merges) ≥ 5 期望 ✅

具体 commits:
- `0f67c1117` feat(w71st-batch-b1): qa-bench 7 维评分算法 (第 196 守恒)
- `eb2798ff4` feat(w71st-batch-b2): save_to_kb.py 5 道防线补全 (第 197 守恒)
- `247b6a2b3` feat(w71st-batch-b3): Celery auto_intake_rollback_task (第 198 守恒)
- `62553735e` feat(w71st-batch-b4): KB 闭环端到端 (第 199 守恒)
- `ac7946ef6` feat(w71st-batch-b5): Dashboard MVP 补 2 el-card + 5min polling (第 200 守恒)

加 5 merge commits (aed47632f, 0cc1e2699, 47f8b9c9b, bd74f951c, 6cddfb073) → 10 commits 全部 main HEAD 可查 ✅

### 3.2 7 维评分数据 + KB 闭环回归

```bash
ls tests/qa-bench/scoring/seven_dim.py tests/qa-bench/kb_queue/five_defenses.py app/services/qa_bench_tasks.py
```

**实测结果**: 3 文件全部存在 ✅

- `app/services/qa_bench_tasks.py` ✅ (W71 B-3 commit `247b6a2b3` 落地)
- `tests/qa-bench/kb_queue/five_defenses.py` ✅ (W71 B-2 commit `eb2798ff4` 落地)
- `tests/qa-bench/scoring/seven_dim.py` ✅ (W71 B-1 commit `0f67c1117` 落地)

baseline 71+7 守恒: 待主指挥合并 W72 跑 vitest + pytest 验证 (本任务无测试改动, 0 影响)。

### 3.3 子 plan ③ 3 组件独立回归

W72 子 plan ③ 3 组件尚未实施 (派工 v8 段 8 起步纪律 4 项必读第 3 条要求 B 路线全合后才能启动 UI 改造), 待 W72 B-1 + B-2 派工前真验证。

预期 W72 派工 B-1 + B-2 + B-3 完成后跑子 plan ③ 3 组件回归。

### 3.4 派工前提错误必含 W71 实战 13 类

派工 v8 段 7 升级 13 类派工前提错误, W72 派工 prompt 必含 13 类, 沿用 W71 v8 模板。

派工 v8 段 7 沉淀规则 (W71 实战):
- 每类前提错误必须有真实案例引用 (commit hash / file path / commit message)
- 沉淀位置统一在 `memory/w68-<batch>-<route>-<topic>-<date>.md` 或 `memory/w71-<route>-<topic>-<date>.md`
- 主指挥在 grand closure 时汇总本批所有派工前提错误, 更新 CLAUDE.md 永久锚点节
- 24h 内未填视为派工流程违规

---

## §4 路线 A 4 agents 派工清单 (收口 + 派工 v9 + plans 真验证)

W72 第 1 批路线 A 4 agents 派工清单, 必先派 (其他 11 agents 依赖 A-1 部署收口 + A-3 plans 真验证):

### A-1: W72 部署收口 (本任务沉淀 + 主拍合并)

| 维度 | 内容 |
|------|------|
| **范围** | docs/w72nd-batch-dispatch-2026-07-24.md (本任务落盘) + memory/w72-route-72nd-batch-a1-dispatch-2026-07-24.md (memory 沉淀) |
| **工期** | 30 分钟 (本任务实测) |
| **预期锚点** | 第 207 守恒 |
| **0 prod code 例外** | 0 (纯 docs/memory) |
| **派工前提** | W71 batch 33 commits 已合并 main (本任务实测 ✅) |

### A-2: 派工纪要 v9 (W72 实战反馈升级)

| 维度 | 内容 |
|------|------|
| **范围** | docs/w72-dispatch-candidates-v9-2026-07-24.md (派生, 沿用 v8 + W72 实战反馈) |
| **工期** | 1-2 小时 |
| **预期锚点** | 第 208 守恒 |
| **0 prod code 例外** | 0 (纯 docs) |
| **派工前提** | A-1 部署收口 commit + merge 后才启动 |

### A-3: W72 plans 真验证 (派工 v4 铁律 3 实战)

| 维度 | 内容 |
|------|------|
| **范围** | plans 真验证 (git log + grep + commit 引用 3 段) + 派生新任务清单 |
| **工期** | 1-2 小时 |
| **预期锚点** | 第 209 守恒 |
| **0 prod code 例外** | 0 (纯 docs) |
| **派工前提** | A-1 部署收口 commit + merge 后才启动 |

### A-4: W72 grand closure memory 预期版

| 维度 | 内容 |
|------|------|
| **范围** | memory/w72-grand-closure-expected-2026-07-24.md (预期版, 派工完成后由 D-3 改 actual 版) |
| **工期** | 1 小时 |
| **预期锚点** | 第 210 守恒 |
| **0 prod code 例外** | 0 (纯 memory) |
| **派工前提** | A-1 + A-2 + A-3 全部 commit + merge 后才启动 |

---

## §5 路线 B 5 agents 派工清单 (子 plan ③ 起步 — 串单链 + Celery 串行约束)

W72 第 1 批路线 B 5 agents 派工清单, 必走串单链 (B-1 必先合, B-2 + B-3 可并行, B-4 依赖 B-1+B-2+B-3, B-5 依赖 B-1+B-2+B-4):

### B-1: NavRail.vue 新组件 (桌面端左侧导航栏)

| 维度 | 内容 |
|------|------|
| **范围** | `web/src/components/chat/NavRail.vue` (~250 行 NEW) + `web/src/components/chat/SessionSidebar.vue` 重构 (+60/-90 行 MOD, overlap bug 修复) |
| **工期** | 3-4 小时 |
| **预期锚点** | 第 211 守恒 |
| **0 prod code 例外** | **1 (已批, 例外允许 web/src/components/chat/ 范畴)** |
| **派工前提** | A-1 + A-2 + A-3 commit + merge 后才启动; W71 B-1 `seven_dim.py` + W71 B-5 `QaBenchDashboard.vue` 已合并 main (本任务实测 ✅) |

### B-2: ThinkingModeSwitch.vue 新组件 (3 档模式 segmented control)

| 维度 | 内容 |
|------|------|
| **范围** | `web/src/components/chat/ThinkingModeSwitch.vue` (~80 行 NEW) + `web/src/components/chat/ChatBreadcrumb.vue` (~60 行 NEW) + `web/src/stores/useUiStore.js` v-model |
| **工期** | 2-3 小时 |
| **预期锚点** | 第 212 守恒 |
| **0 prod code 例外** | 0 (web/src/components/chat/ 范畴, 派工 v6 允许) |
| **派工前提** | B-1 commit + merge 后才启动; 桌面端 + 移动端 chat engine 必先回归 (`chat_engine.py` 方案 C 6 条铁律) |

### B-3: ChatViewSSE 顶栏 3-zone 重构

| 维度 | 内容 |
|------|------|
| **范围** | `web/src/views/chat/ChatViewSSE.vue` (+120/-80 行 MOD) + 移动端同步 (`web/src/views/mobile/chat/MobileChatView.vue` +30/-10 行 MOD + `web/src/components/mobile/MobileHeader.vue` +20/-30 行 MOD + `web/src/components/mobile/MobileInputBar.vue` +25 行 MOD) + `web/src/components/mobile/MobileThinkingModeSwitch.vue` (~60 行 NEW) |
| **工期** | 3-4 小时 |
| **预期锚点** | 第 213 守恒 |
| **0 prod code 例外** | 0 (web/src/views/chat/ 范畴) |
| **派工前提** | B-1 commit + merge 后才启动; ChatBreadcrumb + ThinkingModeSwitch 必先合 |

### B-4: 跨端点 API (NavRail + ThinkingModeSwitch + ChatBreadcrumb 端点验证)

| 维度 | 内容 |
|------|------|
| **范围** | `tests/e2e/w72-navrail.spec.mjs` (~60 行 NEW) + `tests/e2e/w72-thinking-mode.spec.mjs` (~60 行 NEW) + Playwright visual regression baseline 重建 (`tests/visual/desktop/v78-ui-redesign.spec.mjs` ~60 行 NEW) |
| **工期** | 2-3 小时 |
| **预期锚点** | 第 214 守恒 |
| **0 prod code 例外** | 0 (tests/ 范畴) |
| **派工前提** | B-1 + B-2 + B-3 全部 commit + merge 后才启动 (Celery 串行约束, 类似 W71 B-3 等 B-1 + B-2) |

### B-5: 桌面端 6 主题 dark mode 跨组件验证

| 维度 | 内容 |
|------|------|
| **范围** | `web/src/assets/variables.css` (+20 行 MOD, design token 增量) + 6 主题 dark mode 跨组件验证 (`web/src/components/chat/NavRail.vue` + `ThinkingModeSwitch.vue` + `ChatBreadcrumb.vue` + `SessionSidebar.vue` + `ChatViewSSE.vue` 6 主题回归) + `web/src/stores/useThemeStore.js` `toggle()` 增强 |
| **工期** | 3-4 小时 |
| **预期锚点** | 第 215 守恒 |
| **0 prod code 例外** | 0 (web/src/assets/ + web/src/components/ 范畴) |
| **派工前提** | B-1 + B-2 + B-4 commit + merge 后才启动 (依赖 B-1 7 维权重 schema + B-2 dashboard 数据源一致性) |

---

## §6 路线 C 3 agents 派工清单 (调研类独立, 可并行)

W72 第 1 批路线 C 3 agents 派工清单, 调研类独立可并行:

### C-1: 容器镜像 rebuild (qa-bench + CI 镜像优化)

| 维度 | 内容 |
|------|------|
| **范围** | `Dockerfile.qa-bench` 重构 + `.github/workflows/build-qa-bench-image.yml` 优化 + 多阶段构建 + cache-from: type=gha |
| **工期** | 2-3 小时 |
| **预期锚点** | 第 216 守恒 |
| **0 prod code 例外** | 0 (Dockerfile + .github/ 范畴) |
| **派工前提** | A-1 部署收口 commit + merge 后才启动 |

### C-2: 商业化 24 人月季度排期更新 (Phase 8 + Phase 2 启动规划)

| 维度 | 内容 |
|------|------|
| **范围** | `docs/w72-commercialization-roadmap-update-2026-07-24.md` (派生, 沿用 W68 第 12 批 D-4 拍板 + 24 人月季度排期) |
| **工期** | 1-2 小时 |
| **预期锚点** | 第 217 守恒 |
| **0 prod code 例外** | 0 (纯 docs) |
| **派工前提** | A-1 + A-3 plans 真验证 commit + merge 后才启动 |

### C-3: ppt-word 5 缺口调研 (W68 第 14 批 D-2 派生)

| 维度 | 内容 |
|------|------|
| **范围** | ppt-word 5 缺口 (PPT 导出 / Word 导出 / OCR 兼容 / 模板引擎 / 大文件分片) 调研 + 派生新任务清单 |
| **工期** | 2-3 小时 |
| **预期锚点** | 第 218 守恒 |
| **0 prod code 例外** | 0 (纯调研) |
| **派工前提** | A-1 + A-3 plans 真验证 commit + merge 后才启动 |

---

## §7 路线 D 3 agents 派工清单 (收尾 — 必后派)

W72 第 1 批路线 D 3 agents 派工清单, 必后派 (B + C 全部 commit 后, 派工 v6 段 6 实战 D-2 文档必含实际值):

### D-1: 派工纪要 v9 实战反馈升级 (W72 实战反馈)

| 维度 | 内容 |
|------|------|
| **范围** | docs/w72-dispatch-candidates-v9-actual-2026-07-24.md (W72 实战反馈: 段 5 升级 12 → 13 项 + 段 7 升级 13 → 15 类派工前提错误 + 段 8 W73 起步纪律) |
| **工期** | 1-2 小时 |
| **预期锚点** | 第 219 守恒 |
| **0 prod code 例外** | 0 (纯 docs) |
| **派工前提** | A + B + C 全部 commit + merge 后才启动 |

### D-2: 6 类文档同步 (W72 batch partial mid-派工真实施聚合)

| 维度 | 内容 |
|------|------|
| **范围** | 主仓库 5 文件 (CLAUDE.md + ROADMAP.md + CHANGELOG.md + README.md + memory/MEMORY.md) + 用户级 1 文件 + 1 新增 memory (本任务 A-1 已落盘, D-2 必含 W72 实际值聚合) |
| **工期** | 1-2 小时 |
| **预期锚点** | 第 220 守恒 |
| **0 prod code 例外** | 0 (纯 docs/memory) |
| **派工前提** | A + B + C + D-1 全部 commit + merge 后才启动 |

### D-3: W72 grand closure memory actual 版

| 维度 | 内容 |
|------|------|
| **范围** | memory/w72-grand-closure-actual-2026-07-24.md (15 agents 实际派工 + 4 路线 + 锚点范式 W71 206 → W72 220 实际收束 + 0 production code 改动铁律 14/15 守恒 + 7 类别沉淀) |
| **工期** | 1 小时 |
| **预期锚点** | 第 220 守恒实际 |
| **0 prod code 例外** | 0 (纯 memory) |
| **派工前提** | A + B + C + D-1 + D-2 全部 commit + merge 后才启动 |

---

## §8 W72 派工 0 production code 改动铁律 14/15 守恒预期

派工 v6 段 5 反馈 #2 实战: 0 production code 改动铁律 (派工纪要本身纯 docs) + 14/15 守恒预期。

### 8.1 例外清单 (1 例外已批)

| # | 例外文件 | 例外行数 | 例外类型 | 派工 v6 允许 |
|---|---------|---------|---------|------------|
| 1 (B-1) | `web/src/components/chat/NavRail.vue` | ~250 行 (NEW) | component 新增 | ✅ web/src/components/chat/ 范畴允许 |
| 2 (B-1) | `web/src/components/chat/SessionSidebar.vue` | +60/-90 行 (MOD) | component 重构 | ✅ web/src/components/chat/ 范畴允许 |

**例外不扩大到老路径重构**: 严禁修改 `app/services/task_service.py` / `meeting_service.py` / `knowledge_service.py` 等老模块核心函数 + `web/src/views/Desktop*/index.vue` 老桌面页面 + `alembic/versions/0XX_老.py` 老迁移 + `app/core/security.py` / `app/core/rate_limit.py` 老安全/限流基础设施 + `app/agent/chat_engine.py` 方案 C 6 条铁律相关文件。

### 8.2 不算例外的纯 docs/memory 改动 (14 agents)

- A-1 部署收口 (本任务): docs/w72nd-batch-dispatch-2026-07-24.md + memory/w72-route-72nd-batch-a1-dispatch-2026-07-24.md
- A-2 派工 v9: docs/w72-dispatch-candidates-v9-2026-07-24.md
- A-3 plans 真验证: 派生新任务清单
- A-4 grand closure memo: memory/w72-grand-closure-expected-2026-07-24.md
- B-2 ThinkingModeSwitch + ChatBreadcrumb: web/src/components/chat/ 范畴 (派工 v6 允许)
- B-3 ChatViewSSE 顶栏 + 移动端同步: web/src/views/chat/ 范畴 (派工 v6 允许)
- B-4 跨端点 e2e: tests/ 范畴
- B-5 桌面端 6 主题 dark: web/src/assets/ + web/src/components/ 范畴 (派工 v6 允许)
- C-1 容器镜像 rebuild: Dockerfile + .github/ 范畴
- C-2 商业化排期: docs/ 范畴
- C-3 ppt-word 5 缺口: 调研 + 派生任务清单
- D-1 派工 v9 实战: docs/ 范畴
- D-2 6 类文档同步: docs/memory/ 范畴
- D-3 grand closure actual: memory/ 范畴

**14/15 守恒预期**: 14 agents 纯 docs/memory/scripts/tests/ 范畴, 1 例外 B-1 NavRail.vue 250 行 + SessionSidebar 重构 (已批 web/src/components/chat/ 范畴)。

---

## §9 W72 派工顺序表 (派工 v6 段 5 反馈 #1 串单链守恒 + Celery 串行约束 + 接口契约 8 段)

### 9.1 串单链守恒

派工 v6 段 5 反馈 #1 实战: B 路线 5 agents 串单链守恒 + Celery 串行约束 (派工 v8 段 6 + 段 7 实战)。

W72 第 1 批 15 agents 派工顺序表:

| 步骤 | agent-id | 任务标题 | 串单链位置 | Celery 串行约束 | 接口契约 |
|------|---------|----------|-----------|---------------|---------|
| Step 1 | A-1 | W72 部署收口 (本任务) | base = main HEAD `9e21fbfcd` | — | — |
| Step 2 | A-2 | 派工纪要 v9 | base = Step 1 | — | — |
| Step 3 | A-3 | plans 真验证 | base = Step 1 | — | — |
| Step 4 | A-4 | grand closure memo 预期版 | base = Step 1+2+3 | — | — |
| Step 5 | B-1 | NavRail.vue + SessionSidebar 重构 | base = Step 1+2+3+4 | — | 输出 → B-2/B-3 (路由级双栈) |
| Step 6 | B-2 | ThinkingModeSwitch.vue + ChatBreadcrumb.vue | base = Step 5 | — | 输入 ← B-1, 输出 → B-3 (3-zone 顶栏) |
| Step 7 | B-3 | ChatViewSSE 顶栏 3-zone 重构 | base = Step 5+6 | — | 输入 ← B-1 + B-2, 输出 → B-4 (跨端点) |
| Step 8 | B-4 | 跨端点 e2e + Playwright baseline | base = Step 5+6+7 | 串行: B-4 等 B-1 + B-2 + B-3 commit + merge | 输入 ← B-1 + B-2 + B-3 |
| Step 9 | B-5 | 桌面端 6 主题 dark | base = Step 5+6+8 | 串行: B-5 等 B-1 + B-2 + B-4 | 输入 ← B-1 7 维权重 schema + B-2 dashboard 数据源 |
| Step 10 | C-1 | 容器镜像 rebuild | base = Step 1+2+3 | — (调研类独立) | — |
| Step 11 | C-2 | 商业化 24 人月季度排期 | base = Step 1+2+3 | — (调研类独立) | — |
| Step 12 | C-3 | ppt-word 5 缺口调研 | base = Step 1+2+3 | — (调研类独立) | — |
| Step 13 | D-1 | 派工 v9 实战 | base = Step 1+2+3+4+5+6+7+8+9+10+11+12 | — | — |
| Step 14 | D-2 | 6 类文档同步 | base = Step 1+2+3+4+5+6+7+8+9+10+11+12+13 | — | — |
| Step 15 | D-3 | grand closure actual 版 | base = Step 1-14 | — | — |

### 9.2 Celery 串行约束

派工 v8 段 6 实战: Celery 串行任务必须显式声明依赖 (W71 B-3 等 B-1 + B-2 commit + merge 后才启动)。

W72 第 1 批 Celery 串行约束:
- B-4 必等 B-1 + B-2 + B-3 commit + merge 后才启动 (类似 W71 B-3 等 B-1 + B-2)
- B-5 必等 B-1 + B-2 + B-4 commit + merge 后才启动 (类似 W71 B-4 等 B-3 rollback_task)
- D-1 必等 A + B + C 全部 commit + merge 后才启动 (派工 v6 段 6 实战 D-2 文档必含实际值)
- D-2 必等 A + B + C + D-1 全部 commit + merge 后才启动
- D-3 必等 A + B + C + D-1 + D-2 全部 commit + merge 后才启动

### 9.3 接口契约 8 段

W72 第 1 批 5 B 路线 agents 接口契约 (W71 C-2 沉淀 + 派工 v8 段 6 实战):

| 上游 agent | 输出文件 | 输出格式 | 本 agent 接收字段 | 校验方式 |
|-----------|---------|---------|-------------------|---------|
| B-1 → B-2 | `web/src/components/chat/NavRail.vue` | Vue 3 SFC | `useUiStore.toggleNavRail()` | navrail-active class 验证 |
| B-1 → B-3 | `web/src/components/chat/SessionSidebar.vue` | Vue 3 SFC (重构后) | `useChatStore.sessions[]` | overlap bug 修复 |
| B-2 → B-3 | `web/src/components/chat/ThinkingModeSwitch.vue` + `ChatBreadcrumb.vue` | Vue 3 SFC | `useUiStore.useDeepThinking` | 3 档模式切换验证 |
| B-3 → B-4 | `web/src/views/chat/ChatViewSSE.vue` | Vue 3 SFC (3-zone 重构后) | `e2e navrail + thinking-mode + breadcrumb 端点` | Playwright spec 验证 |
| B-1 + B-2 → B-5 | `NavRail.vue` + `ThinkingModeSwitch.vue` + `ChatBreadcrumb.vue` | Vue 3 SFC (6 主题 dark) | `useThemeStore.toggle()` + `variables.css` 6 主题 | dark mode 跨组件回归 |
| B-3 → B-5 | `ChatViewSSE.vue` + `MobileChatView.vue` + `MobileHeader.vue` | Vue 3 SFC | `mobile dark mode` | 移动端 dark mode 跨组件回归 |
| A-1 + A-3 → C-1 | `docs/w72nd-batch-dispatch-2026-07-24.md` + plans 真验证 | docs | Dockerfile rebuild | CI 镜像验证 |
| B-1 + B-2 + B-3 → D-2 | 6 类文档同步 | docs | W72 实际值聚合 | git log + grep 3 段真验证 |

---

## §10 W72 派工合并顺序表 (主拍必读, 派工 v6 段 6 实战)

主拍必读合并顺序表 (派工 v6 段 6 实战 + 派工 v8 段 6 升级):

### 10.1 Step 1: A 路线 4 agents 派工

```bash
# 主拍并行派 A-2 + A-3 (A-1 已 commit), A-4 必等 A-1 + A-2 + A-3 commit + merge
cd /e/microbubble-agent/.worktrees/agent-w72nd-a1-deploy-doc
git push origin chore/w72nd-batch-a1-deploy-doc-2026-07-24  # A-1 (本任务)

# A-2 派工 worktree (主拍执行)
cd /e/microbubble-agent
git worktree add .worktrees/agent-w72nd-a2-prompt-v9 chore/w72nd-batch-a2-prompt-v9-2026-07-24

# A-3 派工 worktree (主拍执行)
cd /e/microbubble-agent
git worktree add .worktrees/agent-w72nd-a3-plans-verify chore/w72nd-batch-a3-plans-verify-2026-07-24
```

### 10.2 Step 2: 主拍合并 A 路线 → 验证 main HEAD

```bash
# 主拍合并 A-1 → A-2 → A-3 → A-4 (按串单链顺序)
git merge --no-ff chore/w72nd-batch-a1-deploy-doc-2026-07-24
git merge --no-ff chore/w72nd-batch-a2-prompt-v9-2026-07-24
git merge --no-ff chore/w72nd-batch-a3-plans-verify-2026-07-24
git merge --no-ff chore/w72nd-batch-a4-grand-closure-2026-07-24

# 验证 main HEAD
git log --oneline main | grep -E "w72nd-batch-(a1|a2|a3|a4)" | wc -l  # 期望 ≥ 8 (4 features + 4 merges)
```

### 10.3 Step 3: B 路线 5 agents 派工 (串单链)

```bash
# B-1 必先派 (B-1 必先合, B-2 + B-3 可并行, B-4 依赖 B-1+B-2+B-3, B-5 依赖 B-1+B-2+B-4)
cd /e/microbubble-agent
git worktree add .worktrees/agent-w72nd-b1-navrail chore/w72nd-batch-b1-navrail-2026-07-24

# 等 B-1 commit + merge 后, B-2 + B-3 可并行派
cd /e/microbubble-agent
git worktree add .worktrees/agent-w72nd-b2-thinking-mode chore/w72nd-batch-b2-thinking-mode-2026-07-24
git worktree add .worktrees/agent-w72nd-b3-chatview-3zone chore/w72nd-batch-b3-chatview-3zone-2026-07-24

# 等 B-1 + B-2 + B-3 commit + merge 后, B-4 才派 (Celery 串行约束)
cd /e/microbubble-agent
git worktree add .worktrees/agent-w72nd-b4-e2e-specs chore/w72nd-batch-b4-e2e-specs-2026-07-24

# 等 B-1 + B-2 + B-4 commit + merge 后, B-5 才派 (Celery 串行约束)
cd /e/microbubble-agent
git worktree add .worktrees/agent-w72nd-b5-6theme-dark chore/w72nd-batch-b5-6theme-dark-2026-07-24
```

### 10.4 Step 4: 主拍合并 B 路线 → 验证 main HEAD + 跑 baseline 71+7

```bash
# 主拍合并 B-1 → B-2 → B-3 → B-4 → B-5 (严格按串单链顺序, Celery 串行约束)
git merge --no-ff chore/w72nd-batch-b1-navrail-2026-07-24
git merge --no-ff chore/w72nd-batch-b2-thinking-mode-2026-07-24
git merge --no-ff chore/w72nd-batch-b3-chatview-3zone-2026-07-24
git merge --no-ff chore/w72nd-batch-b4-e2e-specs-2026-07-24
git merge --no-ff chore/w72nd-batch-b5-6theme-dark-2026-07-24

# 验证 main HEAD
git log --oneline main | grep -E "w72nd-batch-(b1|b2|b3|b4|b5)" | wc -l  # 期望 ≥ 10 (5 features + 5 merges)

# 跑 baseline 71+7 守恒验证 (B-1 + B-2 + B-3 + B-4 + B-5 全部 web 改动后必跑)
cd /e/microbubble-agent/web && npx vitest run 2>&1 | tail -10
# 期望: Test Files 38 passed, Tests 71 passed, 7 skipped

cd /e/microbubble-agent && PYTHONIOENCODING=utf-8 PYTHONUTF8=1 pytest tests/ -v 2>&1 | tail -20
# 期望: pytest PASS 数与 W68 第 13 批一致
```

### 10.5 Step 5: C 路线 3 agents 派工 (调研类独立, 可并行)

```bash
# C-1 + C-2 + C-3 调研类独立, 可并行派
cd /e/microbubble-agent
git worktree add .worktrees/agent-w72nd-c1-image-rebuild chore/w72nd-batch-c1-image-rebuild-2026-07-24
git worktree add .worktrees/agent-w72nd-c2-commercial-roadmap chore/w72nd-batch-c2-commercial-roadmap-2026-07-24
git worktree add .worktrees/agent-w72nd-c3-ppt-word-survey chore/w72nd-batch-c3-ppt-word-survey-2026-07-24
```

### 10.6 Step 6: D 路线 3 agents 派工 (必等 B+C 全部 commit 后)

```bash
# D-1 必等 A + B + C 全部 commit + merge 后才派
cd /e/microbubble-agent
git worktree add .worktrees/agent-w72nd-d1-prompt-v9-actual chore/w72nd-batch-d1-prompt-v9-actual-2026-07-24

# D-2 必等 A + B + C + D-1 全部 commit + merge 后才派 (派工 v6 段 6 实战 D-2 文档必含实际值)
cd /e/microbubble-agent
git worktree add .worktrees/agent-w72nd-d2-docs-sync chore/w72nd-batch-d2-docs-sync-2026-07-24

# D-3 必等 A + B + C + D-1 + D-2 全部 commit + merge 后才派
cd /e/microbubble-agent
git worktree add .worktrees/agent-w72nd-d3-grand-closure chore/w72nd-batch-d3-grand-closure-2026-07-24
```

### 10.7 Step 7: 主拍合并 C+D 路线 → 写 W72 grand closure actual 落盘

```bash
# 主拍合并 C-1 → C-2 → C-3 → D-1 → D-2 → D-3 (调研类独立 + D 收尾)
git merge --no-ff chore/w72nd-batch-c1-image-rebuild-2026-07-24
git merge --no-ff chore/w72nd-batch-c2-commercial-roadmap-2026-07-24
git merge --no-ff chore/w72nd-batch-c3-ppt-word-survey-2026-07-24
git merge --no-ff chore/w72nd-batch-d1-prompt-v9-actual-2026-07-24
git merge --no-ff chore/w72nd-batch-d2-docs-sync-2026-07-24
git merge --no-ff chore/w72nd-batch-d3-grand-closure-2026-07-24

# 验证 main HEAD (锚点范式 W71 206 → W72 220 守恒)
git log --oneline main | grep -E "w72nd-batch" | wc -l  # 期望 ≥ 30 (15 features + 15 merges)

# 写 W72 grand closure actual 落盘 (D-3 agent 完成)
```

---

## §11 W72 派工沉淀 7 类别 (派工 v6 段 5 反馈实战)

派工 v6 段 5 反馈实战 7 类别沉淀 (W71 batch 实战暴露 + W72 派工预案):

### 11.1 派工 v8 段 5 反馈 #1 (B 路线 5 agents 接口协调实战沉淀)

**W71 实战**: B-1 `seven_dim.py` 接口签名与 B-2 `kb_queue/dedup.py` 输入数据格式冲突 + B-3 Celery 任务串行约束与 B-4 audit 触发时序不齐 + B-5 dashboard 数据源与 B-1 7 维权重 schema 不一致 4 个具体协调事故。

**W72 沉淀**: 派工 v8 段 6 合并顺序表新增"接口契约 / Celery 依赖"列 + B 路线 5 agents 接口契约 8 段 (本任务 §9.3) + Celery 串行约束 (本任务 §9.2)。

### 11.2 派工 v8 段 5 反馈 #2 (W72 起步纪律 4 项必读)

**W71 实战**: W71 D-1 派工纪要 v7 → v8 升级时发现 v7 段 7 缺"W72 子 plan ③ 起步前必读"段。

**W72 沉淀**: 派工 v8 段 8 显式列出 4 项起步前必含 + 4 项派工必写 + 3 项派工前提 24h 内必填 (本任务 §2.2 + §3 实战验证)。

### 11.3 派工 v8 段 5 反馈 #3 (SubAgent 编排 type hint 必含)

**W71 实战**: W71 C-2 sub-agent 编排范式 v2 沉淀时发现 SubAgent 上下文传递若缺 type hint, 跨 agent 串接时 Pydantic 校验报 `missing field` 或 runtime `AttributeError`。

**W72 沉淀**: 派工 v8 段 3 强制 type hint grep + 段 4 编译产物 grep + 段 5 必填第 10 项。W72 B 路线 5 agents (NavRail / ThinkingModeSwitch / ChatBreadcrumb + 跨端点 + 6 主题) 涉及 SubAgent 编排接口, 必含 type hint。

### 11.4 派工 v8 段 5 反馈 #4 (派生新任务真验证)

**W71 实战**: W71 C-1 qa-bench D8 调研派工时主指挥口头追加"派生 7 项实施前置"子任务, agent 自报完成但 `git log` 显示派生任务实际未派工。

**W72 沉淀**: 派工 v8 段 3 必先写 backlog docs + 段 5 必填第 11 项 + 真验证 3 段 (git log + grep + commit 引用)。W72 A-3 plans 真验证 + C-3 ppt-word 5 缺口调研 必含派生新任务真验证。

### 11.5 派工 v8 段 5 反馈 #5 (W72 任务模式基调 plans 优先 + 小修搭配 + 路线 fallback)

**W68 第 4 批主指挥拍板**: 派工以已有 plans 实施为主 + 更新过程中发现的小修为辅 (W72 沿用)。

**W72 沉淀**: W72 路线 A 4 agents (派工 v9 + plans 真验证 + grand closure) + 路线 B 5 agents (子 plan ③ UI redesign) + 路线 C 3 agents (调研 + 商业化) + 路线 D 3 agents (派工 v9 实战 + 6 类文档 + grand closure), plans 优先 + 小修搭配 + 路线 fallback 三驱动。

### 11.6 派工 v8 段 5 反馈 #6 (W72 段 8 W72 起步纪律 4 项必读)

**W71 D-1 实战**: 派工纪要 v7 → v8 升级时新增段 8 "W72 子 plan ③ 起步纪律"。

**W72 沉淀**: 本任务 §2.2 + §3 实战验证 4 项起步纪律 (B 路线 5 agents 全部 commit + merge / 7 维评分数据 + KB 闭环回归 / 子 plan ③ 3 组件独立回归 / 派工前提错误 13 类)。本任务实测: 10 commits (W71 B 路线 5 features + 5 merges) ≥ 5 期望 ✅。

### 11.7 派工 v8 段 5 反馈 #7 (W72 派工 0 production code 改动铁律 14/15 守恒预期)

**W71 D-2 实战**: 6 类文档同步只聚合已合并到 origin/main 的 commits, **不伪造**未实施 agent 工作内容, 严格遵守派工 v6 §1.2 "Status 段必真验证"。

**W72 沉淀**: 本任务 §8 0 production code 改动铁律 14/15 守恒预期 (1 例外 B-1 NavRail.vue 250 行 + SessionSidebar 重构, 派工 v6 允许 web/src/components/chat/ 范畴) + §10 合并顺序表必含实际值 (派工 v6 段 6 实战 D-2 文档必含实际值)。

---

## §12 总结

W72 第 1 批 15 agents 派工调研完成, 锚点范式 W71 206 → W72 220 守恒 (+14 守恒预期), 0 失败预期。

**核心交付物**:
- 派工依据 5 文档引用 (本任务 §2.1)
- W72 起步纪律 4 项实战验证 (本任务 §3, 实测: 10 commits ≥ 5 期望 ✅)
- 4 路线 15 agents 派工清单 (本任务 §4-§7)
- 0 production code 改动铁律 14/15 守恒预期 (本任务 §8)
- W72 派工顺序表 + Celery 串行约束 + 接口契约 8 段 (本任务 §9)
- W72 派工合并顺序表 (本任务 §10, 7 步骤)
- 7 类别沉淀 (本任务 §11)

**铁律 (5 条, 派工纪要 v6 段 5 实战)**:
1. 必先 commit partial diff (B-3 教训)
2. 不动 v1-v7 历史约束 (派工 v6 段 5 反馈 #2 实战)
3. 派工 v8 段 5 升级 12 项必填 (W71 D-1 实战升 v8 必备)
4. 0 production code 改动铁律 (派工纪要本身纯 docs)
5. 1 commit + defer message (本任务已 commit `docs(w72nd-batch-a1)` 形式)

**W72 派工基础**: 锚点范式 W71 206 守恒 (主指挥协调范式第 45 次派工预期), W71 batch 33 commits 已合并 main (本任务实测 ✅)。

---

**版本 v1, 2026-07-24, W72nd batch A-1 起草, 主拍合并后正式生效。**

**Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>**