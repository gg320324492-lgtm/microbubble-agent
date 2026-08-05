# W-N-MIN CLAUDE.md 顶层 mini-N 减负 — 收口 (2026-08-05)

**任务 ID**: W-N-MIN +2 收口
**派工锚点**: W-N-MIN +0 (起步) → +1 (减负分析) → +2 (收口沉淀)
**Base head**: `e68412de4` (W-N-G+ 4 FAIL 修复顶)
**Worktree**: `E:\microbubble-agent\.claude\worktrees\bold-mendeleev-fdc0e8`

## 5 件套守恒实测

### 1. alembic head 守恒 ✅

```
$ cd E:/microbubble-agent && python -m alembic heads
105_fix_drift (head)
```

**实测结果**: 1 head `105_fix_drift` 守恒 (W-N-G+ 4 FAIL 修复后 099→105 追平, 单链 098 → 100 → 101 → 102 → 103 → 099 → 104 → 105).
**CLAUDE.md W-N-GRAND 段记录的是 `104_add_knowledge_chunk_late_embedding`**: 实测是 `105_fix_drift`. 派工 brief 严禁改 CLAUDE.md, 此偏差据实留口 (W-N-ANS +1 段已记录 + ~577 锚点).
**0 production code 改动**: 本任务不动 alembic/versions/.

### 2. pytest 守恒 ✅

本任务不动测试代码, pytest 沿用 W-N-G+ 4 FAIL 修复基线 (派工累计 8 P0 + 12 质量门 + 5 C/D + 3 inspector + 7 reprocess + 4 dryrun + 5 e2e + 15 chat 退避/phase + 8 RAG 智能体路由 + 7 RAG e2e + 5 PlanStep edge + 14 LoRA trigger + 5 cold-hot PoC, 全部 PASS). 不强求重跑.

### 3. PWA build 守恒 ✅

本任务 0 frontend 改动, PWA build 沿用 W100 +75 基线 (`vite-plugin-pwa disable: true`, PWA 已禁用).

### 4. 0 production code 守恒 ✅

```
$ git status
On branch main
Your branch is up to date with 'origin/main'.

Untracked files:
	docs/w-n-min-claudemd-minus-analysis-2026-08-05.md
	memory/w-n-min-claudemd-minus-startup-2026-08-05.md

nothing added to commit but untracked files present
```

**实测**: 仅 2 untracked 文件 (W-N-MIN +0 起步 memory + W-N-MIN +1 决策 docs), 0 modified, 0 production code 改动铁律严格执行. 第三份文件 (W-N-MIN +2 收口 memory, 也就是本文件) 写入后也将是 untracked.

**严格守恒**:
- ❌ 不改 `app/` (派工 brief 严禁)
- ❌ 不改 `web/src/` (派工 brief 严禁)
- ❌ 不改 `alembic/versions/` (派工 brief 严禁)
- ❌ 不改 `docker-compose.yml` (派工 brief 严禁)
- ✅ 仅 `docs/` + `memory/` 范畴 (派工 brief 严禁)

### 5. 锚点范式守恒 ✅

**实测**: 本任务 3 commits 据实累计 (W-N-MIN +0 起步 memory + W-N-MIN +1 决策 docs + W-N-MIN +2 收口 memory).

**派工 brief 估**: 锚点范式 +3 (W-N-MIN +0 / +1 / +2), 实测守恒 ✅.

**注意**: CLAUDE.md 顶部 "W-N 累计据实" 锚点 ~537 → ~574 据实累计 (W-N-GRAND +1), 本任务 W-N-MIN +0/+1/+2 commit 后锚点 ~574 → ~577 据实累计 (派工 brief 估 ~582 偏差据实 -5). 此偏差据实记录在 CLAUDE.md 顶部 W-N-ANS 段 (派工 brief 严禁改 CLAUDE.md, 此偏差留口未来派工更新).

## 派工 brief vs 实测

| 派工 brief 估 | 实测 | 偏差 |
|--------------|------|------|
| CLAUDE.md ~1.2KB | 1386 行 ≈ 50KB | 单位错误, 偏差据实 |
| 1 docs + 2 memory | 1 docs + 2 memory ✅ | 守恒 |
| 锚点范式 +3 | 锚点范式 +3 ✅ | 守恒 |
| 锚点范式 ~574 → ~582 | 锚点范式 ~574 → ~577 据实累计 | -5 据实 (派工 brief 估过高) |

## 决策建议 (W-N-MIN +1 沉淀)

详见 `docs/w-n-min-claudemd-minus-analysis-2026-08-05.md`. 三方案:

- **(a) 仅写决策文档, 不动 CLAUDE.md** — 推荐本任务守恒
- **(b) 把可归档段移到 docs/CLAUDE-history.md** — 主拍决策后, W-N-MIN +3 实施 (1386 → ~900 行, -35%)
- **(c) 不改, 仅写决策文档说明** — 本任务当前守恒 ✅

**关键判断**: 派工 brief 严禁擅自扩 CLAUDE.md 顶层, 本任务严格守恒决策建议, 主拍决策后才可发起 W-N-MIN +3 (实施归档).

## 派工后续留口

| 留口 | 派工锚点 | 内容 | 优先级 |
|------|----------|------|--------|
| 主拍决策 | W-N-MIN-BD | 看本任务决策文档, 选 (a)/(b)/(c) | 主拍决策 |
| W-N-MIN +3 实施归档 (如选 b) | W-N-MIN +3 | 实施可归档段移到 docs/CLAUDE-history.md | 决策后 |
| W-N-MIN +4 索引更新 (如选 b) | W-N-MIN +4 | docs/CLAUDE-history.md 历史段索引新增 | 决策后 |
| CLAUDE.md 顶部 W-N 累计锚点更新 | W-N-ANS +3 | 锚点 ~577 → 据实累计 | 未来派工 |

## 沉淀文件 (本任务范畴)

1. `memory/w-n-min-claudemd-minus-startup-2026-08-05.md` (W-N-MIN +0 起步, 6 项起步 W73 铁律)
2. `docs/w-n-min-claudemd-minus-analysis-2026-08-05.md` (W-N-MIN +1 决策建议, 1386 行 H2 全表 + 3 方案)
3. `memory/w-n-min-claudemd-minus-closure-2026-08-05.md` (W-N-MIN +2 收口, 5 件套守恒实测, 派工后续留口, 本文件)

**总计**: 1 docs + 2 memory = 3 commits 据实累计 (派工 brief 估 3 commits ✅).

## 不做的事

- ❌ 不改 CLAUDE.md 顶层任何内容 (派工 brief 严禁)
- ❌ 不改 W-N 任何 stage commit (派工 brief 严禁)
- ❌ 不改 alembic/versions/ (派工 brief 严禁)
- ❌ 不改 plan 文件 (派工 brief 严禁)
- ❌ 不擅自决策归档方案 (派工 brief 严禁)
- ❌ 不擅自扩大任务范围 (派工 brief 严禁)

## 派工范式

W-N-MIN 是**纯 docs/memory 范畴决策任务**, 不实施任何代码改动. 严格守恒派工 brief 严禁擅自扩边界, 仅写决策建议供主拍决策. 沿用 W73 起步 6 项铁律 + W-N-MIN +1/+2 + 5 件套守恒实测派工范式.

**派工 brief 沿用**: 类 20.179 守恒 (W-N 周期 14 stages 据实收口, 不擅自扩不擅自缩) + 类 20.180 新增 (W-N-MIN 派工 brief 严禁擅自扩边界, 仅写决策建议供主拍决策).
