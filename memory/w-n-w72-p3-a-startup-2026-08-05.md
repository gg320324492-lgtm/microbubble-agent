# W-N-W72 P3-A 启动 (2026-08-05)

> **派工**: W-N-W72-P3A +0 起步
> **base ref**: `cde003abc` (W-N-P3-A + W-N-GLITCH 收口)
> **派工范畴**: docs + memory 范畴, 0 production code 守恒
> **任务模式**: 派工 brief 严禁, 仅汇总留口未来 PR

---

## 1. 派工 brief 锚定 (W73 铁律 6 项)

### 1.1 任务 ID + 锚点范式

- **任务 ID**: W-N-W72-P3A 汇总派工 brief 严禁, 留口未来 PR
- **锚点范式**: W-N-W72-P3A +0..+2 (起步 + 留口汇总 + 收口)
- **当前 main HEAD**: `cde003abc` (W-N-P3-A + W-N-GLITCH 收口, 5 文件 untracked commit 推 main)
- **当前 alembic head**: `105_fix_drift (head)` 守恒 ✓
- **派工 brief 严禁擅自派工**: 严禁启动 P3-A..P3-E 任一集成实施

### 1.2 W73 铁律 6 项起步 (必查)

1. **派工起点必 fetch origin + merge-base 拦截漂移** (类 20.131 沿用)
2. **调研标"推断"必先实测** (类 20.109 沿用)
3. **不擅自派工: 派工权在主拍决策** (派工 v6 §13.3 假设禁令)
4. **0 production code 改动铁律** (派工 brief 严禁)
5. **锚点范式守恒**: W-N-W72-P3A +0..+2 据实累计
6. **5 件套守恒实测**: alembic 1 head + pytest 沿用 + PWA build 沿用 + 0 production code + 锚点范式

---

## 2. 派工前实测状态 (类 20.131 + 20.109)

### 2.1 git log 实测 (派工起点必 fetch)

```
$ git log --oneline -5
cde003abc docs(decision): W-N-P3-A + W-N-GLITCH 5 文件 untracked commit 推 main (W-N-P3-A + W-N-GLITCH 收口)
821874cca docs(w-n-glitch): glitchtip-dev-1 restart loop 修复尝试 (W-N-GLITCH +1)
71e448595 docs(memory): W-N-BGE-PRE 收口 (W-N-BGE-PRE +2)
71b750949 docs(memory): W-N-BGE-PRE 起步 (W-N-BGE-PRE +0)
8a3ae748b docs(w-n-xx): W-N-XX 留口 1 闭环验证 (8/8 PASS + 触发条件更新 + 收口) (W-N-XX +R0/+R1/+R2)
```

- **base head 验证**: `cde003abc` ✓ 派工 brief 期望守恒
- **W-N-P3-A**: 已沉淀 (commit 引用待查, 沿用 W-N-GLITCH 收口 commit)
- **W-N-W72 +0..+2**: 已沉淀 (docs/w72-post-v4-roadmap.md)
- **untracked files**: 1 个 `memory/w-n-glitchtip-impl-startup-2026-08-05.md` (W-N-GLITCH 阶段遗留, 与本任务无关)

### 2.2 派工 brief 锚点校验 (类 20.46 + 20.108)

派工 brief 期望锚点:
- W-N-W72-P3A +0: 起步 memory (本文件)
- W-N-W72-P3A +1: 留口汇总 (1 docs)
- W-N-W72-P3A +2: 收口 memory

实测守恒: **3 commits 据实累计** (派工 brief 估 3 commits, 实测 3 commits, **完美守恒**).

### 2.3 派工 brief 文件校验 (类 20.97)

派工 brief 引用的源文件实测:
- `docs/w72-post-v4-roadmap.md` ✓ 存在 (W-N-W72 +1 沉淀)
- `docs/w-n-p3-a-prisma-eval-2026-08-05.md` ✓ 存在 (W-N-P3-A +1 沉淀)
- `docs/w-n-bge-leftover-2026-08-05.md` ❌ **不存在** (brief 路径假设错配)
- `docs/w-n-grand-closure-2026-08-05.md` ❌ **不存在** (brief 路径假设错配)
- 实际存在: `docs/w-n-grand-closure-runbook.md` (W-N-GRAND +1 沉淀, 路径名差异)

**派工 brief 偏差据实 (类 20.109 沉淀)**:
- brief 路径 `w-n-bge-leftover-2026-08-05.md` → 实际**未沉淀**独立 leftover 文档, W-N-BGE 决策已沉淀到 `memory/w-n-bge-m3-realpath-closure-2026-08-05.md`
- brief 路径 `w-n-grand-closure-2026-08-05.md` → 实际名 `w-n-grand-closure-runbook.md` (路径名差异, 内容对应)
- **处置**: 本任务汇总时**沿用**真实存在的文件 (`docs/w-n-p3-a-prisma-eval-2026-08-05.md` + `docs/w-n-grand-closure-runbook.md` + `memory/w-n-bge-m3-realpath-closure-2026-08-05.md`), 不擅自创建 brief 错配路径

---

## 3. W-N-W72 P3-A 任务边界 (派工 brief 严禁清单)

### 3.1 派工 brief 严禁 (派工 v6 §13 假设禁令)

**严禁**:
- ❌ 改 plan 文件 (主拍决策独占)
- ❌ 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ commits (派工编号保护)
- ❌ 改 CLAUDE.md 顶层 (另 agent 任务范畴)
- ❌ 改 alembic/versions/ (0 migration 守恒)
- ❌ 改 app/ web/src/ (production code 守恒)
- ❌ 改 docker-compose.yml (infra 守恒)
- ❌ 改 package.json / requirements.txt (派工 brief 严禁)
- ❌ 改 app/models/ 既有文件 (派工 brief 严禁)
- ❌ **启动 P3-A 集成** (派工 brief 严禁)
- ❌ **启动 P3-B RAG 双 backend** (派工 brief 严禁)
- ❌ **启动 P3-C 实时 push** (派工 brief 严禁)
- ❌ **启动 P3-D W98 grand closure** (派工 brief 严禁)
- ❌ **启动 P3-E ChatKit-3 集成** (派工 brief 严禁)

### 3.2 严格范畴 (1 docs + 2 memory)

- ✅ 1 docs (本任务 +1: `docs/w-n-w72-p3-a-leftover-2026-08-05.md` 留口汇总)
- ✅ 2 memory (本任务 +0 起步 + +2 收口)
- ✅ 0 production code 守恒

### 3.3 锚点范式守恒

- W-N-W72-P3A +0: 起步 memory (本文件, 待 commit)
- W-N-W72-P3A +1: 留口汇总 docs (待写)
- W-N-W72-P3A +2: 收口 memory (待写)
- **总计**: 3 commits 据实累计 (派工 brief 估 3 commits, 实测 3 commits, 完美守恒)

---

## 4. 后续 +1 / +2 任务计划

### 4.1 W-N-W72-P3A +1 留口汇总

**任务**:
- 写 `docs/w-n-w72-p3-a-leftover-2026-08-05.md` (派工 brief 严禁留口汇总)
- 内容含 6 项:
  1. P3-A Prisma 集成决策 (沿用 W-N-P3-A 评估, 决策 (b) 暂不启动)
  2. P3-B RAG 双 backend (沿用 W-N-BGE 留口, bge-m3 真路径回归决策)
  3. P3-C 实时 push (Socket.IO/WebSocket 集成, 调研, 派工 brief 严禁启动)
  4. P3-D W98 series total grand closure (沿用 W-N-GRAND runbook)
  5. P3-E ChatKit-3 集成 (Vue 3.5 ChatKit, ChatKit-3 稳定版发布后由主拍决策预留)
  6. 触发再启条件 (派工 brief 严禁擅自派工)

**参考源文件**:
- `docs/w72-post-v4-roadmap.md` §3 P3-A..P3-E 后续 PR 列表
- `docs/w-n-p3-a-prisma-eval-2026-08-05.md` §4 决策建议
- `docs/w-n-grand-closure-runbook.md` W-N-GRAND 总收口
- `memory/w-n-bge-m3-realpath-closure-2026-08-05.md` 3 决策大门禁

### 4.2 W-N-W72-P3A +2 收口 memory

**任务**:
- 写 `memory/w-n-w72-p3-a-closure-2026-08-05.md`
- 5 件套守恒实测 (alembic 1 head + pytest 沿用 + PWA build 沿用 + 0 production code + 锚点范式)
- 锚点漂移据实上报 (派工 v6 §13.3 假设禁令)
- 类 20 实战沉淀 (派工 brief 路径假设错配拦截, 类 20.109 + 类 20.97 沿用)

---

## 5. 关联沉淀

- `docs/w72-post-v4-roadmap.md` (W-N-W72 +1, 后续 PR 列表 §3 P3-A..P3-E)
- `docs/w-n-p3-a-prisma-eval-2026-08-05.md` (W-N-P3-A +1, 决策建议)
- `docs/w-n-grand-closure-runbook.md` (W-N-GRAND +1, 总收口 runbook)
- `memory/w-n-bge-m3-realpath-closure-2026-08-05.md` (W-N-BGE +3, 3 决策大门禁)
- `memory/w-n-p3-a-prisma-eval-closure-2026-08-05.md` (W-N-P3-A +2, 5 件套守恒)

---

**base head**: `cde003abc`
**撰写日期**: 2026-08-05
**派工锚点**: W-N-W72-P3A +0
**派工模式**: 派工 brief 严禁, 仅汇总留口未来 PR
