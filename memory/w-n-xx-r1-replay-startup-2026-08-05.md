# W-N-XX 留口 1 复盘 — 起步 (2026-08-05)

> **派工**: W-N-XX +R0 / +R1 / +R2
> **基线 HEAD**: `74d1a965e` (W-N-DEPLOY +0/+1/+2 收口)
> **目的**: W-N-G+ 4 FAIL 修复 (`e68412de4`) 已 cherry-pick 推 main, 验证闭环

## 起步 6 项 (W73 铁律)

### 1. base HEAD 验证

```
$ git log --oneline -3
74d1a965e docs(deploy-status): W-N-DEPLOY 部署状态验证报告 + 起步 + 收口 (W-N-DEPLOY +0/+1/+2)
3d45465c1 docs(memory): W-N-MIN (b) 实施收口 (W-N-MIN +6)
d49057d39 docs(memory): CLAUDE.md 顶层 mini-N 减负 (W-N-MIN +5)
```

base HEAD = `74d1a965e` ✓ (派工 brief 要求守恒)

### 2. W-N-G+ 4 FAIL 修复 commit 验证

```
$ git log --oneline | grep -i "4 FAIL"
e68412de4 fix(rag): W-N-G+ 4 FAIL 修复 (cherry-pick 自 claude/w-n-g-plus-4fail-fix)
```

commit `e68412de4` 已 push main, 内容:
- `tests/test_w_n_g_plus_chunk_late_recall.py` (1 文件)
- `memory/w-n-g-plus-4fail-fix-{startup,closure}-2026-08-05.md` (2 份 memory)

**0 production code 改动**: 仅 1 测试文件 + 2 memory ✓

### 3. 测试文件存在性确认

```
$ ls -la tests/test_w_n_g_plus_chunk_late_recall.py
-rw-r--r-- 1 ... 10944 Aug  5 22:47 tests/test_w_n_g_plus_chunk_late_recall.py
```

文件存在 ✓

### 4. 未来派工留口文档定位

`docs/w-n-future-leftover-2026-08-05.md` §1 W-N-G+ 4 FAIL 章节已存在 (W-N-XX +1 commit `c2acc536d`).

### 5. 派工 brief 验证 (派工 v6 §13 仓库实情真查)

- 派工 brief `base HEAD` 预期 `74d1a965e` → 实测 `74d1a965e` ✓
- 派工 brief `W-N-G+ 4 FAIL 修复 commit` 预期 `e68412de4` → 实测 `e68412de4` ✓
- 派工 brief `未来派工留口文档` 预期 `docs/w-n-future-leftover-2026-08-05.md` §1 → 实测存在 ✓

### 6. 派工锚点确认

W-N-XX +R0 (本 memory) → +R1 (闭环验证 docs) → +R2 (收口 memory)

## 下一步

进入 W-N-XX +R1 闭环验证:
- 跑 `SKIP_DB_SETUP=1 pytest tests/test_w_n_g_plus_chunk_late_recall.py -v` 验证 8/8 PASS
- 写 `docs/w-n-xx-r1-replay-2026-08-05.md` 闭环验证报告