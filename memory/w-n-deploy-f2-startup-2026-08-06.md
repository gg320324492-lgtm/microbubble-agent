# W-N-DEPLOY-F2 起步 (2026-08-06)

> **派工**: W-N-DEPLOY-F2 +0 起步 (部署验证 agent, W-N 周期 19 stages 收口后最终部署状态验证)
> **base HEAD**: `6d8f0226f` (W-N-FILL-REAL-N 测试回归断言修正, 12/12 PASS)
> **派工锚点**: W-N-DEPLOY-F2 +0 (本文件) / +1 (部署报告 + commit) / +2 (收口 memory)
> **前序**: W-N-DEPLOY-FINAL (`74d1a965e` W-N-DEPLOY +0/+1/+2) → 本任务 F2 为 19 stages 收口后复验

---

## 1. 6 项起步 (W73 铁律)

### 1.1 base HEAD 验证

```
6d8f0226f fix(test): W-N-FILL-REAL-N 测试回归断言修正 (12/12 PASS)
8c50c777a perf(rag): bge-m3 1000 题真测 encoder-only 数据 (W-N-BGE-A 收尾)
c34e6739f docs(memory): W-N-FILL-REAL-N +2 收口沉淀
```

`git log --oneline -3` 实测 base HEAD = `6d8f0226f` ✅ 与派工 brief 一致, 0 偏差.

### 1.2 派工范畴 (严格)

**允许写**: 1 docs (`docs/deploy-status-final-2026-08-06-f2.md`) + 2 memory (本 startup + closure).

**严禁改** (派工 brief 逐条):
- 0 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++/FILL-IMPL/FILL-REAL/FILL-REAL-N 既有 commits
- 0 改 `alembic/versions/`
- 0 改 `app/` `web/src/`
- 0 改 `docker-compose*`
- 0 改 `.env`
- 0 改 `tests/` 任何文件 (**本次派工新增严禁项**, 前序 W-N-FILL-REAL-N 曾改测试断言, 本任务严禁)

### 1.3 8 步验证清单 (派工 brief 据实)

| Step | 任务 | 判定 |
|------|------|------|
| 1 | `git log --oneline origin/main -5` vs local 一致 | 0/0 divergence |
| 2 | `docker ps -a` 容器状态 | 核心 Up |
| 3 | `python -m alembic heads` 1 head `105_fix_drift` | 单 head |
| 4 | 3 套件 pytest PASS | 全 PASS |
| 5 | `curl http://localhost:8000/health` | 200 |
| 6 | `git status --short` clean | clean |
| 7 | 写 `docs/deploy-status-final-2026-08-06-f2.md` (6 节) | 6 节齐 |
| 8 | commit 1 docs + 1 memory 范畴 | 范畴守恒 |

### 1.4 环境实情 (类 20.13 据实, 起步先记)

- **worktree 拓扑**: 派工 cwd 落在 `E:/microbubble-agent/.claude/worktrees/bold-mendeleev-fdc0e8`, 实测该目录**为空壳** (`ls -a` 仅 `.` `..`), git 解析回落主仓库 `E:/microbubble-agent` @ `main`. 本任务全程用**绝对路径**操作主仓库, 不在空壳 worktree 内写文件.
- **并发批次共存**: `git status --short` 有 1 个 untracked `memory/w-n-clean-f2-startup-2026-08-06.md`, 属**并发 W-N-CLEAN-F2 agent** 产物, **本任务不 add 不改不删** (类 20.140 并发批次共存纪律沿用).
- **`git worktree list`**: 16 worktree 在册, 多个 HEAD 为 `000000000` (prunable), 本任务**不清理** (归 W-N-CLEAN-F2 范畴).

### 1.5 5 件套预期 (起步先声明, +2 收口实测)

| # | 件 | 预期 |
|---|----|------|
| 1 | alembic 1 head | `105_fix_drift` 守恒 |
| 2 | pytest | 3 套件全 PASS (12 + 8 + 22 = 42) |
| 3 | PWA build | 沿用 W100 +75 基线 (0 frontend 改动) |
| 4 | 0 production code | 仅 1 docs + 2 memory, `app/` `web/src/` `alembic/versions/` `docker-compose*` `tests/` 全 0 |
| 5 | 锚点范式 | W-N-DEPLOY-F2 +0/+1/+2 据实累计 |

### 1.6 风险预判

- **风险 1**: 前序 `docs/deploy-status-final-2026-08-06.md` (224 行, W-N-DEPLOY-FINAL 产出) 已存在, 本任务写 **`-f2` 后缀新文件**, **不覆盖不改**前序文档 (类 20.171 主拍收口必复核纪律沿用).
- **风险 2**: 前序文档 stage 表锚点列全为 "W-N +0" 且主题为通用占位, 与实测 commit log 不符. 本报告 stage 表**从 `git log` 实测数据重建**, 不复制前序表 (§1.1 plans 审计纪律: 禁止批量复制粘贴).
- **风险 3**: Step 4 pytest 若 FAIL, **严禁改 tests/** (派工 brief 新增严禁项), 只能据实上报 FAIL.

---

## 2. 关联

- 前序部署报告: `docs/deploy-status-final-2026-08-06.md` (W-N-DEPLOY-FINAL) / `docs/deploy-status-2026-08-05.md` (W-N-DEPLOY)
- 收口 memory: `memory/w-n-deploy-f2-closure-2026-08-06.md` (W-N-DEPLOY-F2 +2)
- 本报告: `docs/deploy-status-final-2026-08-06-f2.md` (W-N-DEPLOY-F2 +1)
