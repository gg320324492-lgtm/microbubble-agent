# W-N-XX 留口 1 复盘 收口 (2026-08-06)

> **派工**: W-N-XX-RC +2 (收口 memory)
> **基线 HEAD**: `cde003abc` (W-N-P3-A + W-N-GLITCH 收口)
> **派工 brief 严守**: 仅复盘 + 验证, **不再生成新 commit**
> **闭环状态**: 已闭环 (派工 brief 不再需要任何额外动作)

---

## 任务完成总结

W-N-XX 留口 1 复盘 agent 跑完 W-N-XX-RC +0 (起步 memory 沿用 W-N-XX +R0 已落 main) / +1 (复盘 docs 备用, 不入 git) / +2 (本收口 memory) 三阶段.

### 1. W-N-XX-RC +0 起步 (沿用 W-N-XX +R0 物证)

`memory/w-n-xx-r1-replay-startup-2026-08-05.md` 已落 main at `8a3ae748b`, 沉淀 W73 铁律 6 项:
- base HEAD 验证 `74d1a965e` (派工 brief 当时预期) → 当前基线 `cde003abc` (主仓库 advance, 派工 brief 据实上报)
- W-N-G+ 4 FAIL 修复 commit `e68412de4` 已 push main ✓ (`merge-base --is-ancestor` 守恒)
- 测试文件 `tests/test_w_n_g_plus_chunk_late_recall.py` 存在 (6475 字节, e68412de4 修复版) ✓
- 未来派工留口文档 `docs/w-n-future-leftover-2026-08-05.md` §1 已存在 ✓
- 派工 brief v6 §13 仓库实情真查 3 项实测对账 ✓
- 派工锚点 W-N-XX-RC +0..+2 确认 ✓ (内部标识, 不入 git)

### 2. W-N-XX-RC +1 复盘验证

`docs/w-n-xx-r1-replay-final-2026-08-05.md` (备用复盘 docs, 不入 git):
- W-N-G+ 4 FAIL 修复兑现 (`e68412de4`) — 1 test + 2 memory, 0 production code ✓
- W-N-VERIFY 决策文档兑现 (`8a3ae748b` 关联 `docs/w-n-xx-r1-replay-2026-08-05.md`) ✓
- 8/8 PASS 本次复跑 — `SKIP_DB_SETUP=1 pytest tests/test_w_n_g_plus_chunk_late_recall.py -v` → 8 passed in 42.15s (与历史 43.65s 一致) ✓
- 触发再启条件更新 (替代) — 旧 3 基础设施条件 → "W-N-G+ 修复回归" 单条件 ✓
- 决策: W-N-XX 留口 1 完全闭环 ✓
- 类 20.183 / 20.184 沉淀 ✓

### 3. W-N-XX-RC +2 收口 (本文件)

5 件套守恒实测 + 闭环验证 8/8 PASS + 派工 brief 严禁条目全部 0 触碰.

---

## 5 件套守恒实测 (本任务 + 历史对齐)

| # | 件 | 本次复跑实测 | 历史对齐 | 状态 |
|---|----|-------------|---------|------|
| 1 | alembic 1 head | `python -m alembic heads` → `105_fix_drift (head)` | e68412de4 body 沉淀 `105_fix_drift` | ✓ 守恒 |
| 2 | DB version | `SELECT version_num FROM alembic_version;` → `105_fix_drift` | e68412de4 body 沉淀 `105_fix_drift` | ✓ 守恒 |
| 3 | pytest | 本次 8/8 PASS (42.15s, 7 warnings) | 8a3ae748b 报告 43.65s + e68412de4 修复 56.29s / 69.56s | ✓ 守恒 |
| 4 | 0 production code | 本任务 0 commit + 0 文件修改 | e68412de4 1 test + 2 memory + 8a3ae748b 1 doc + 2 memory | ✓ 守恒 |
| 5 | 锚点范式 | W-N-G+ +4..+6 (e87cc9a51 / 54ac813c3 / 7d1292c0b) + W-N-XX +R0..+R2 (8a3ae748b) | 历史 7 commit 守恒 | ✓ 守恒 |

**5 件套 5/5 守恒** ✓

---

## 闭环验证 8/8 PASS (本次复跑实测)

```
$ SKIP_DB_SETUP=1 pytest tests/test_w_n_g_plus_chunk_late_recall.py -v
======================= 8 passed, 7 warnings in 42.15s ========================
```

- 4 个 schema drift 测试全部 PASS (W-N-G+ +1 修复 3 列 + 类型检查)
- 4 个 retrieve 行为测试全部 PASS (16GB+ RAM 跑通, 0 OOM)
- 警告 7 条 (Pydantic v2 deprecation / asyncio loop / SwigPy / pkg_resources / jieba / redis setex) 全部为预存 deprecation, 不影响 PASS

---

## 锚点范式 (派工 brief 严禁擅自扩)

派工 brief 期望的 `W-N-XX-RC +0..+2` 三锚点**仅作任务内部标识**, 不进 `git log --grep`. 历史锚点 W-N-XX +R0/+R1/+R2 (落 main at `8a3ae748b`) 与 W-N-G+ +4/+5/+6 (落 main at `e68412de4`) 保持守恒.

| 锚点 | 用途 | git 状态 |
|------|------|---------|
| W-N-G+ +4 / +5 / +6 | 修复 cherry-pick | 落 main at `e68412de4` |
| W-N-XX +R0 / +R1 / +R2 | 闭环决策 | 落 main at `8a3ae748b` |
| W-N-XX-RC +0 / +1 / +2 | 本次复盘 (内部标识) | **不入 git** |

---

## 0 production code 守恒 (本任务)

本任务严守派工 brief 严禁:
- `git status --short` 在主仓库 / 唯一 worktree 仅有与本任务**无关**的预存 untracked (docker-compose.dev.yml 修改 / prisma_dft_jobs.py / 几个 memory md / prisma/) — 本任务**未触碰**这些预存变更
- `tests/test_w_n_g_plus_chunk_late_recall.py` 0 修改 (e68412de4 修复版 6475 字节保持原样)
- `app/` `web/src/` `alembic/versions/` 0 修改
- 0 commit / 0 push (派工 brief 严禁)
- 复盘 docs (`docs/w-n-xx-r1-replay-final-2026-08-05.md`) + 收口 memory (本文件) 2 份仅作 agent 留痕, 不入 git

**0 production code 改动铁律 守恒** ✓

---

## 类 20 沉淀 (W-N-XX-RC 据实)

### 类 20.183 (新, W-N-XX-RC 据实)

**复盘 agent 不开 commit, 仅物证 + 触发条件更新**. 复盘派工的本质是 "核对闭环物证 + 复验触发条件 + 沉淀类 20", 不是 "新增 commit 推翻原决策". 派工 brief 若以 "复盘 + 验证" 为名, 必须严禁复盘 agent 自行重写闭环报告 / 修测试 / 改 W-N-* commit.

### 类 20.184 (新, W-N-XX-RC 据实)

**闭环决策文档必含触发条件 "替代" 而非 "附加"**. 8/8 PASS 后旧 3 基础设施条件已隐含满足, 闭环报告必须把旧条件**替代**为新条件 (本次: W-N-G+ 修复回归 = 列变化), 不许 "附加" 含糊条件 (例如 "再派一次").

---

## W-N-XX 留口 1 决策

**闭环决策**: W-N-G+ 4 FAIL 修复兑现 (`e68412de4`), 决策文档落 main (`8a3ae748b`), 本次复跑 8/8 PASS (42.15s), 5 件套守恒实测 5/5. **W-N-XX 留口 1 完全闭环**, 派工 brief 严禁再启 W-N-G+ +N, 除非触发条件 (W-N-G+ 修复回归 = 新 commit 引入列变化导致 FAIL) 真的出现.

**何时不触发**:
- 8/8 PASS 现状保持 → 不触发
- 测试文件内容稳定 → 不触发
- schema drift 列名无变化 → 不触发

**新触发路径** (如未来再 FAIL):
- 跑 `SKIP_DB_SETUP=1 pytest tests/test_w_n_g_plus_chunk_late_recall.py -v` 出现任意 1 个 FAIL
- 修复路径沿用 W-N-G+ +1 commit `7cb6bf0d1` 4 步 stamp+upgrade (见 `docs/w-n-future-leftover-2026-08-05.md` §1.4)
- 派工 brief 必含 4 项 checklist: DB 可达 / 列名类型 DSN version_num / RAM ≥ 16GB / 引用本决策文档

---

## 关联沉淀

- `docs/w-n-xx-r1-replay-final-2026-08-05.md` (W-N-XX-RC +1 备用复盘 docs, 不入 git)
- `memory/w-n-xx-r1-replay-closure-2026-08-05.md` (W-N-XX +R2 收口, 落 main at `8a3ae748b`)
- `docs/w-n-xx-r1-replay-2026-08-05.md` (W-N-XX +R1 闭环报告, 落 main at `8a3ae748b`)
- `memory/w-n-xx-r1-replay-startup-2026-08-05.md` (W-N-XX +R0 起步, 落 main at `8a3ae748b`)
- `memory/w-n-g-plus-4fail-fix-closure-2026-08-05.md` (W-N-G+ +6 收口, 落 main at `e68412de4`)
- `memory/w-n-g-plus-4fail-fix-startup-2026-08-05.md` (W-N-G+ +4 startup, 落 main at `e68412de4`)
- `memory/w-n-verify-4fail-archive-2026-08-05.md` (W-N-VERIFY +1 决策留口, 派工 brief 严禁擅自扩)
- `docs/w-n-future-leftover-2026-08-05.md` §1 W-N-G+ 4 FAIL (W-N-XX +1 留口 runbook, commit `c2acc536d`)
- `tests/test_w_n_g_plus_chunk_late_recall.py` (e68412de4 修复版, 6475 字节, 8/8 PASS 复跑 42.15s)
- commit `e68412de4` (W-N-G+ +4..+6 cherry-pick 推 main)
- commit `8a3ae748b` (W-N-XX +R0/+R1/+R2 闭环推 main)
- commit `7cb6bf0d1` (W-N-G+ +0/+1 schema drift 修复迁移)

---

**W-N-XX-RC 收口结论**: 闭环物证全部守恒, 派工 brief 严禁条目全部 0 触碰, W-N-XX 留口 1 完全闭环, 未来再启条件已显式化为 "W-N-G+ 修复回归". 本任务不增 commit, 不 push, 仅作 agent 留痕.
