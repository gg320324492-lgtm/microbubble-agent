# W-N-DEPLOY 部署状态验证 — 起步 (2026-08-05, W-N-DEPLOY +0)

> **派工**: W-N-DEPLOY +0..+2 (主指挥协调范式第 N 次派工, 部署状态验证 agent)
> **目标 base**: main HEAD = `97225717b` (W-N-W72 +2 收口), 实际 base = `97225717b`, 实测 main HEAD = `347c38f43` (W-N-MIN +3 + +4 共 2 commits 在 base 之上)
> **0 production code 守恒**: 严格仅 1 docs + 2 memory 文件新增, 禁止改 W-N 任何 stage commit, 禁止改 docker-compose.yml / .env / alembic / app / web/src

---

## 1. 6 项起步 (W73 铁律)

### 1.1 工作区身份

- **cwd**: `E:\microbubble-agent` (主仓库, main branch)
- **git rev-parse HEAD**: `347c38f43` (real, after `git fetch origin main`)
- **git rev-parse origin/main**: `347c38f43` (fetch 后一致, **实测未 ensure match** — 派工 v6 §13 仓库实情真查)
- **git status --short**: 空 (clean, 完全守恒 W-N-MIN 提交后状态)
- **git worktree list**: 16 个 worktree (含本主仓库), `claude/bold-mendeleev-fdc0e8` 不在列表 (本 worktree 路径是 bash cwd 概念, git 解析到主仓库)
- **branch**: `main`

### 1.2 W-N-MIN 据实状态

派工 brief 期望 base = `97225717b + W-N-MIN +3`, 实测 base 之上 commits:

```
347c38f43 docs(memory): W-N-MIN 3 文件 commit 推 main (W-N-MIN +3)   <- W-N-MIN +3
11a41509d docs(memory): W-N-MIN (b) 实施起步 (W-N-MIN +4)            <- W-N-MIN +4 (本批 +0 起步时已存在)
```

**派工 brief vs 实测据实**:
- 派工 brief 估 "W-N-MIN +3" → 实测 main HEAD 之上有 W-N-MIN +3 **和** W-N-MIN +4 (2 commits, 不是 1)
- W-N-MIN +4 (commit `11a41509d`) 是 W-N-MIN 周期"实施起步"的 4 个文件 commit, 已在 W-N-DEPLOY +0 起步时存在于 main
- 本任务从 W-N-MIN +4 之上继续, 锚点 W-N-DEPLOY +0..+2 据实累计

### 1.3 W-N 周期 14 stages 据实 (派工 brief 与 CLAUDE.md 顶部"~577"一致)

W-N-ANS +1 顶部同步累计 (commit `14fb4ab44`, 后续 revert + 重做 `f0656493a`): **W-N-G+/OBS/RAG/BGE/GRAND 16 commits + W-N-FILL 0** + 派工 brief vs 实测偏差据实 (5 项). W-N-W72 +0/+2 (本次 base 锚点) + W-N-MIN +3/+4 (本批 base 之上) + W-N-DEPLOY +0..+2 (本任务) = W-N 全周期 ~21 commits 据实.

### 1.4 派工 brief vs 实测据实 5 项

| 派工 brief 假设 | 实测 | 据实 |
|-----------------|------|------|
| base = `97225717b + W-N-MIN +3` | base = `97225717b` + 2 commits (+3 + +4) | base HEAD = `347c38f43` (锚点漂移 +1, 派工 brief 估 -1 据实) |
| main HEAD = `97225717b` | main HEAD = `347c38f43` (W-N-MIN +3 + +4 已推) | 锚点漂移 +1, 不擅自改号 |
| 工作区允许 W-N-MIN 3 files untracked | `git status --short` 完全 clean | 守恒, 0 untracked |
| 8/8 PASS 测试存在 | `tests/test_w_n_g_plus_chunk_late_recall.py` 存在 | 守恒 |
| alembic head `105_fix_drift` 守恒 | `python -m alembic heads` = `105_fix_drift (head)` 1 head | 守恒 (单链) |

### 1.5 5 件套预期状态 (起步时假定, +1 验证)

1. alembic: `python -m alembic heads` → 1 head `105_fix_drift` 守恒预期
2. pytest: `tests/test_w_n_g_plus_chunk_late_recall.py` 8/8 PASS 预期
3. PWA build: W-N 不涉及 frontend 改动预期, 沿用基线
4. 0 production code: 严格仅 1 docs + 2 memory 范畴预期
5. 锚点范式: W-N-DEPLOY +0..+2 据实累计预期 (W-N 全周期 ~21 → ~23)

### 1.6 风险预判 (起步, +1 验证后再确认)

- `glitchtip-dev-1` 容器显示 `Restarting (1) 20 seconds ago` — 不是 microbubble-agent-app 链路组件, 不影响主链路 /health 200
- `app-1` 显示 `Up 3 hours (healthy)` — 与最新 commit 时间合理 (W-N-MIN +3/+4 都是 docs 范畴, 无需重启)
- 本地电脑 Docker Desktop 运行中 (8 services + 11+ hours up)

---

## 2. 下一步 (W-N-DEPLOY +1)

- **Step 1**: 实测 `git log origin/main -5` vs local 一致 ✅ (本起步时已 fetch, HEAD = `347c38f43`)
- **Step 2**: `docker ps` 10 个核心服务 + 1 glitchtip Restarting 状态记录
- **Step 3**: `python -m alembic heads` 1 head 守恒
- **Step 4**: pytest 8/8 PASS
- **Step 5**: `git status --short` clean
- **Step 6**: 写 `docs/deploy-status-2026-08-05.md`
- **Step 7**: commit docs + 2 memory

详见 `docs/deploy-status-2026-08-05.md` (Step 6 输出).

## 3. 沉淀路径

- 起步 memory: `memory/w-n-deploy-verify-startup-2026-08-05.md` (本文件, W-N-DEPLOY +0)
- 部署报告: `docs/deploy-status-2026-08-05.md` (W-N-DEPLOY +1)
- 收口 memory: `memory/w-n-deploy-verify-closure-2026-08-05.md` (W-N-DEPLOY +2)
