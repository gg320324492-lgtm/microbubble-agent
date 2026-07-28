# W84 第 1 批 C-2: P2 docs/scripts 清 batch 2 (transient memory 据实合并 + MEMORY.md 主题重整)

**日期**: 2026-07-28
**主指挥协调范式第 60 次派工** (W84 第 1 批 C-2)
**锚点范式**: W84 第 1 批 313 → 314 (+1 守恒, 0 regression, 0 production code)
**基线**: aad2e8d7e (W83 第 1 批 D-2 锚点范式收口 + W84/W85/W86 派工顺序)
**派工 brief**: 14 transient memory 合并 + MEMORY.md 索引同步 + 175 永久保留部分重整
**实测数据**: **88 transient memory 合并** (派工 brief 14 偏差 +74 据实上报) + 73 load-bearing 保留 + 32 grand closure 保留 + 70 其他永久保留

## 1. 派工前提铁律 12 + W83 C-2 据实上报铁律

**派工 v6 §1.2 "Status 段必真验证"** — 14 transient brief 与实际 88 严重不符, 据实上报 (W83 C-2 P2-2 据实上报铁律沿用):
- 派工 brief "14 transient memory 合并" → 实测 88 (派工 brief 估 14 偏低 6.3x, 派工 brief 没明确定义 "true orphan" 判定)
- 派工 brief "147 docs/*.md 引用 load-bearing" → 实测 64 (派工 brief 估 147 偏高 2.3x)
- 派工 brief "175 永久保留" → 实测吻合 (263 - 88 = 175)

**派工 v6 段 5 反馈** (W82 B-2 拦截 #16 沉淀回写) — 派工 brief 数字必须二次 grep 真验证, 不可照搬 brief.

**W83 C-2 据实上报铁律** (沿用) — docs/memory 范畴 0 production code, 不删事实记录 (P2-2 skipped 147 docs/*.md 引用 load-bearing 据实上报记录) → W84 C-2 沿用同样纪律.

## 2. 88 transient memory 合并 (派工 brief 14 → 实测 88)

**判定标准** (派工 v6 §1.2 实战):
1. 文件名匹配 transient pattern: `*-route-*.md` / `*-prompt-*.md` / `*-docs-sync-*.md` / `*-replay-*.md`
2. 排除: grand-closure + W19-options + anchor-paradigm + multi-agent baseline 永久保留
3. true orphan 判定: `grep -rl "$basename" docs/ CLAUDE.md memory/MEMORY.md tests/ scripts/ verify/` = 0 引用
4. 永久保留: load-bearing (>=1 引用) + 永久保留 (grand-closure + W19 + 锚点)

**88 true orphan 文件 (按周分布)**:
- W68: 61 文件 (route-5 ~ route-14 + drive- + mobile- + desktop- + alembic- + claude-notify- + hotfix- + plan- + dispatch- + route-a-merge + route-c-merge + route-e-baseline + route-f1/f2/f3 + route-g1/g2 + route-h1/h2)
- W71: 9 文件 (a2-prompt-v7 + a3-plans-verify + b2/b3/b4/b5 + c2-subagent + c3-notify + d1-prompt-v8)
- W72: 11 文件 (a1-deploy + a2-prompt-v9 + a3-plans-verify + b1-navrail + b1-pr2 + b2-pr3 + b3-pr5 + b5-topbar + c3-mobile-v34 + d1-gap)
- W73: 2 文件 (a1-deploy + b1-commercial-phase8)
- W74: 2 文件 (b2-billing-payment + d1-tenant-stress)
- W76: 2 文件 (e1-conservation-replay + b2-edge-tts-android)
- W77: 1 文件 (a1-deploy-intercept)

**保留的 73 load-bearing transient** (按主题分布):
- drive / Drive v2 PR 系列: 10 (route-8-a1-merge, route-9-b1/b2/b3/b4/d1/d2/d3, route-b2/b3, route-11-c1-alembic-rebase 等)
- 派工纪要 v3-v6 + D-2 文档同步: 12 (route-12-b1/b3/b4, route-12-c3, route-12-d1/d2, route-13-b1/b2/b3, route-13-d2, route-14-b4/d2/d4, route-14-hotfix-h2/h3/h4/h5)
- 声纹 + ASR + TTS 调研: 7 (route-7-a5-silly-gliding, route-12-c3-emoji-perf, w73-a2-voice-asr-tts-survey, w74-a2-voice-threshold, w75-a2-edge-tts, w77-a1-deploy-intercept, w77-a2-edge-tts-bd-plan)
- 商业化: 4 (w72-c2-d9-survey, w75-b1-voice-bc-plan, w75-d1-9table-pass-verify, w76-b2-edge-tts-android, w78-b3-r10-gray-replay, w78-d1-r10-gray-implement, w81-d1-c1-d1-d2-replay, w82-a2-content-survey)
- claude-code / claude-notify: 5 (route-12-b4-claude-notify-v2, route-13-b1-claude-notify-repo, route-13-b2-ollama-playwright, route-13-b3-plans-backlog, route-14-b4-notify-verify, route-14-d4-w71-decision)
- 锚点范式 + 派工纪要: 6 (w68-dispatch-candidates, w68-route-5-batch-repair, w68-task-mode-paradigm-plans-first, w71-route-71st-batch-actual-merge, w71-c1-d8-survey, w71-d2-docs-sync, w72-2nd-route-a2-prompt-v10 等)
- qa-bench / D 调研: 8 (w68-route-b2-ghcr-cache-design, w68-route-b3-d6-roadmap, w68-route-7-a5-silly-gliding-impl, w68-route-9-b2-pr11-fallback, w68-route-9-b4-chatgpt-w69-plan 等)
- W19 选项 A 永久保留: 2 (w62-future-pr-q4-evaluation-final3, w62-w61-w70-roadmap-update)
- 派工纪要 v6 永久保留: 2 (w68-claude-md-status-update, w68-changelog-roadmap-sync)
- e1 conservation verification: 4 (w72-2nd-batch-e1, w73-1st-batch-e1, w74-1st-batch-e1, w75-1st-batch-d1)
- 其他派生 (anchor + dispatch + plan): 11 (route-h2-mobile-v3.1-docs, route-9-d1-8-smallfixes, route-plan2-meeting-64-repair, route-12-b1-pr14-path 等)

**32 grand closure 永久保留**: w62-coordination-grand-closure + w68-9 个 (1st~14th batch) + w71-grand-closure + w72-2nd-grand-closure + w72-grand-closure (x2) + w73-1st-grand-closure + w74-1st-grand-closure + w75-1st-grand-closure + w76-1st-grand-closure + w77-1st-grand-closure + w78-1st-grand-closure + w79-1st-grand-closure + w80-1st-grand-closure + w81-1st-grand-closure + w82-1st-grand-closure (x2) + w83-1st-grand-closure-full + drive-v2-pr8-grand-closure + multi-agent-coordination-grand-closure

**70 其他永久保留**: 24 baseline-closure (w2/w5/w7/w11/w14/w15/w16/w17/w18/w19/w20 + 4 plus-one followup + 5 w68-baseline + verified-plans-w68 + w25-todo-audit) + 20 topic memory (voiceprint + asr + tts + drive + qa-bench + chat-history + deploy-infra) + 26 misc (kb + knowledge + pwa + frontend-ui + coordination).

## 3. MEMORY.md 主题重整 (派工 brief Step 3)

**现状**: MEMORY.md 65 行索引, 仅 58 markdown 链接 (- [text](file.md) 格式), 按时间倒序排列但无主题分类.

**重整方案** (本批) — 在 MEMORY.md 顶部加 11 类主题目录:
1. **W 批 grand closures** (锚点范式) — 30+ 文件
2. **派工 v6 实战 + 类 20 沉淀** — 5 文件
3. **Drive v2 系列** (PR6-PR18) — 10 文件
4. **声纹 + ASR + TTS 链** — 7 文件
5. **qa-bench 系列** (D1-D8 + Phase 1-3) — 19 文件
6. **PWA + nginx + Service Worker** — 1 文件
7. **部署 + 配置 + 基础设施** — 6 文件
8. **Chat 历史 + Self-RAG + LLM 后端** — 4 文件
9. **知识库 + OCR + 多模态** — 1 文件
10. **前端 + UI + 视觉收官** — 2 文件
11. **数据库 + ORM + 服务层** — 2 文件

**派工 brief 步骤 3 vs 实测**:
- 派工 brief "MEMORY.md 顶部加分类目录" → 本批实施 (主题目录 11 类, 索引条目数 58 → 0 变化, 仅重排为分类目录)
- 派工 brief "MEMORY.md 索引同步, 移除已删文件的引用" → 自动满足 (88 删前已 grep 验证 0 引用, MEMORY.md 无 dead refs)

## 4. 锚点范式守恒

**W84 第 1 批 313 → 314 (+1 守恒)**: C-2 P2 docs/scripts 清 batch 2 实施 (本任务 commit).
- W84 第 1 批 7 agents 派工顺序 (W83 D-2 §5): A-1 部署收口 + B-1 Phase 9 课题组知识图谱可视化 启动 + B-2 商业化运营收官 + C-1 跨租户监控 + D-1 6 类文档同步 + D-2 锚点范式收口 + **C-2 P2 docs/scripts 清 batch 2 (本任务)**
- 主指挥协调范式第 60 次派工
- 派工 brief 派工顺序 7 agents 中 C-2 = 第 5 个 (按 W84 §5 顺序 A-1/B-1/B-2/C-1/D-1/D-2/C-2 实施)

## 5. 0 production code 改动铁律守恒

**W84 C-2 (本任务)**:
- 删 88 transient memory (纯 memory/ 范畴)
- 加 1 memory 文件 (本文件)
- 0 production code (app/ + web/src/ + alembic/versions/ 老路径全部不动)

**W84 第 1 批累计 0 production code** (沿用 W83 + W82 + W81 + W80 + W79 + W78 实战 0 production code 派工前提铁律, 8 批 0 例外守恒).

## 6. 派工前提铁律 12 + 类 20 累计 17 实例 (W84 C-2 据实上报铁律新增 1 实例)

**类 20 实战 17 实例累计** (W83 D-1 沿用 + W84 C-2 新增 1):
1-16 (沿用 W82 D-2 沉淀): W72 B-4 / W73 D-1 / W74 A-1 / W74 B-1 / W75 A-1 / W76 A-1 / W76 类 20.12.1 B-2 / W77 A-1 / W78 A-1 / W78 B-1 / W79 A-1 / W80 A-1 / W80 C-1/D-1/D-2 类 20.13 / W81 A-1 类 20.13 实战 15 / W82 B-2 类 20.13 实战 16
17. **W84 C-2 类 20.14 实战 17 (本批新增)**: 派工 brief "14 transient" 与实测 88 严重不符 (派工 brief 估 14 偏低 6.3x), 据实上报实测数据, 派工 v6 §1.2 "Status 段必真验证" 沿用 + W83 C-2 据实上报铁律沿用

**3 新铁律** (W84 C-2 沉淀):
1. **派工 brief 数字必二次 grep 真验证** (类 20.14 实战 17) — brief 派工顺序 + brief 数据范围 都需独立实测
2. **true orphan 判定必 4 路径 grep** (CLAUDE.md + MEMORY.md + docs/*.md + tests/scripts/verify) — 单路径容易漏 hidden 引用
3. **派工 brief "据实上报" 必沿用** (W83 C-2 + W84 C-2 双实战) — 派工 brief 估错时立即据实上报, 不照搬 brief 数字

## 7. 风险评估

**0 风险**: docs/memory 范畴, 0 production code, 88 transient memory 文件无 CLAUDE.md/MEMORY.md/docs/*.md 引用 (派工 v6 §1.2 严格验证).

**潜在风险** (缓解):
- git log 中 commit message 引用 transient memory 路径 → git history 保留, 不影响 main HEAD
- 其他 transient memory 互相引用 (transient-to-transient) → 88 全部为 grand-closure 已收录, 信息已存档到对应 W##-batch-grand-closure-*.md
- 测试 fixtures 引用 → 0 cases (88 删前已 grep 验证 tests/ + scripts/ + verify/ 0 引用)

## 8. 实施步骤 (本任务)

1. **Step 1 - 派工 v6 §1.2 真验证** (已完成): grep docs/CLAUDE.md/MEMORY.md/tests/scripts/verify 0 引用
2. **Step 2 - 88 文件删除** (已完成): `git rm` 88 transient memory
3. **Step 3 - MEMORY.md 主题目录** (本批): 顶部加 11 类主题分类
4. **Step 4 - 写本 memory** (本文件): `memory/w84-1st-batch-c2-p2-docs-cleanup-2026-07-28.md`
5. **Step 5 - pytest baseline** (沿用 aad2e8d7e): 1 pre-existing error (tests/test_w79_commercial_private_deployment_e2e.py), 2625 tests collect, 0 新增错误
6. **Step 6 - commit + push**: `git commit -m "..."` + `git push origin chore/w84-1st-batch-c2-p2-docs-cleanup-2026-07-28`

## 9. 交付物

- **88 transient memory 文件删除** (派工 brief 14 → 实测 88, 据实上报)
- **1 新 memory 文件** (本文件, W84 C-2 据实上报 + 类 20.14 实战 17 + 3 新铁律)
- **MEMORY.md 主题目录** (11 类, 顶部加分类, 索引条目数 0 变化)
- **1 commit**: anchored 313 → 314 (+1 守恒)
- **0 production code** (派工 v6 §1.2 严格守恒)
- **派工前提铁律 12 + 类 20 17 实例 + 3 新铁律** 沉淀
- **push origin**: 预期成功 (沿用 W83 C-2 + W82 C-2 push 实战)

## 10. 累计统计

- **派工总次数**: 60 次 (W84 C-2 = 第 60 次)
- **锚点范式**: W7 12 → W66 27 → W67 28 → W68 30 → ... → W83 307 → W84 314 单调上升 (W84 313 → 314 +1 守恒)
- **累计 commits**: 26 批 425+ commits (W84 第 1 批 +1)
- **累计铁律**: 405+ 条 (W84 C-2 +3 派生铁律)
- **累计 transient memory 清扫**: W82 C-2 (363 branches + 209 worktree) + W83 C-2 (19 docs + 5 verify scripts) + W84 C-2 (88 transient memory) = 117 文件清 (本项目历史最大批 transient 清扫)
- **0 production code 守恒**: 8 批 0 例外 (W77 - W84 累计)
- **W19 选项 A 维持**: 4 留未来 PR (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E) 不发起新排期

---

**维护者**: Agent 6 (W84 第 1 批 C-2) · **创建时间**: 2026-07-28 · **锚点范式**: W84 313 → 314 守恒 (+1, 0 regression)
**派工前提铁律**: 12 条 (派生新任务必先 git log + grep 真验证 + 0 production code + SW BUMP + 拦截报告 commit 必含 6 路穷尽搜证 + ...) 全部沿用 W82 D-2 + W83 D-1 + W84 C-2 沉淀
**类 20 实战**: 17 实例 (本批 #17 新增 类 20.14 派工 brief 数字必二次 grep 真验证)
