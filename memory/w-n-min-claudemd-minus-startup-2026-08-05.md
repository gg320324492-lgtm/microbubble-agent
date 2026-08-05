# W-N-MIN CLAUDE.md 顶层 mini-N 减负 — 起步 (2026-08-05)

**任务 ID**: W-N-MIN
**派工锚点**: W-N-MIN +0 (起步) → +1 (减负分析) → +2 (收口沉淀)
**派工 brief 严禁擅自扩**: 本任务仅写 1 docs + 2 memory, 不改 CLAUDE.md 顶层内容, 不改 production code
**Base head**: `e68412de4` (W-N-G+ 4 FAIL 修复顶)
**工作目录**: `E:\microbubble-agent\.claude\worktrees\bold-mendeleev-fdc0e8`

## 6 项起步 (W73 铁律)

### 1. 任务定位

CLAUDE.md 顶层 mini-N 减负 agent。任务目标: 找 CLAUDE.md 顶层历史段 (W68-W100) 可归档到 docs/CLAUDE-history.md 的 section, 减负顶层长度 (派工 brief 严禁擅自实施, 仅写决策文档)。

### 2. base 验证

- main HEAD = `e68412de4` (W-N-G+ 4 FAIL 修复 cherry-pick 自 claude/w-n-g-plus-4fail-fix)
- 上一提交: `30e7bf20a docs(memory): W-N-XX +2 收口沉淀 + MEMORY.md #26 段新增`
- 验证方式: `cd E:/microbubble-agent && git log --oneline -3` (✅ 实测一致)

### 3. Worktree 创建

本任务在 worktree `bold-mendeleev-fdc0e8` 中运行 (不创建新 worktree), 目录 `E:\microbubble-agent\.claude\worktrees\bold-mendeleev-fdc0e8\` 沿用主指挥已分配的工作目录。

### 4. 派工前读 CLAUDE.md 当前规模

- CLAUDE.md 当前行数: **1386 行** (派工 brief 估 ~1.2KB, 实测 1386 行 ≈ 50KB 量级, W68 后已 ~50KB)
- docs/CLAUDE-history.md 当前行数: **7629 行** (W68-W87 历史段已归档)
- 占比: CLAUDE.md 14% / CLAUDE-history.md 86% (历史段已大部分归档, 顶层主要是 W-N 周期状态段)

### 5. 派工 brief 严禁擅自扩

派工 brief 明确规定:
- ❌ 不改 CLAUDE.md 顶层内容 (派工 brief 严禁)
- ❌ 不改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ commits
- ❌ 不改 W-N-GC +1 / W-N-ANC +1 / W-N-ANS +1 / W-N-GRAND +1 段内容
- ❌ 不改 alembic/versions/
- ❌ 不改 plan 文件
- ✅ 仅写 1 docs (决策建议) + 2 memory (起步 + 收口)
- ✅ 锚点范式守恒: W-N-MIN +0 / +1 / +2 (本任务 3 commits)

### 6. 5 件套预期

1. alembic head 守恒 ✅ (本任务不动 alembic)
2. pytest 守恒 ✅ (本任务不动测试)
3. PWA build 守恒 ✅ (本任务不动 frontend)
4. 0 production code 守恒 ✅ (仅 docs/memory 范畴)
5. 锚点范式 +3 守恒 (W-N-MIN +0/+1/+2 据实累计)

## 关键发现 (起步)

CLAUDE.md 顶层结构 (1386 行):
- L1-L10 项目简介 (保留, 项目基础信息)
- L11-L79 W-N 周期 grand closure 总收口 + W-N 全 14 stages 据实累计 (派工 brief 严禁保留, 含 4 个 +1 段)
- L80-L100 Phase 5 DFT 工具集成 (新插入, 5 @tool + 7 FastAPI 端点 + 1 alembic migration)
- L100-L300 (后续段, 待 W-N-MIN +1 详查)

docs/CLAUDE-history.md 现有内容 (7629 行):
- L1-L80 W51-W62 跨主题收口段 (已归档)
- L80+ W62-W87 后续历史段 (待详查)

## 派工 brief vs 实测偏差预期

- brief 估 CLAUDE.md ~1.2KB → 实测 1386 行 (实测值远大于 brief 估, 偏差据实)
- brief 估 1 docs + 2 memory → 实测守恒 (3 commits 据实)
- 锚点范式 +3 守恒 (本任务 3 commits 据实, 不擅自扩 +4/+5)

## 下一步

W-N-MIN +1 减负分析:
1. 读 CLAUDE.md 顶层 L100-L300 (后续段)
2. 读 CLAUDE-history.md L80+ (W62 之后历史段)
3. 列出可归档 section
4. 写决策文档 (派工 brief 严禁实施)

## 不做的事

- ❌ 不改 CLAUDE.md 顶层任何内容
- ❌ 不发起 CLAUDE.md 改动 commit
- ❌ 不擅自扩大任务范围 (派工 brief 严禁)
- ❌ 不擅自决策归档方案 (仅写决策建议)
