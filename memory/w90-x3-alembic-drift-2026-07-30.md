# W90-X-3 alembic test 锚点漂移修复 (2026-07-30)

## 据实

**W89-X-17 据实**: `tests/alembic/test_pre_commit_hook_passes.py:142` 断言 `087_add_knowledge_original_parent_id`,与实测 alembic head 不一致。

**实测 (派工前)**: `python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; ..."` →
```
heads: ['090_add_rag_eval_report']
```

**关键发现 (派工指令与实测再次错位)**: 派工指令(主指挥)假设实测 head 是 `089_gin_trgm_tsvector` (W89-X-17 时点),但实测时点是 main HEAD `034343f8a`,已被 RAG PR5 (`5fdcb6819` merge) 推到 `090_add_rag_eval_report`。**实测锚点 089 → 090 实际据实**,派工 brief 与实测 head 又一次错位(类 20.32 同源问题)。

## 修法 (1 行精确)

```diff
- assert lines[1] == "087_add_knowledge_original_parent_id", (
-     f"alembic head 应为 087_add_knowledge_original_parent_id. 实际: {lines[1]}"
+ assert lines[1] == "090_add_rag_eval_report", (
+     f"alembic head 应为 090_add_rag_eval_report. 实际: {lines[1]}"
```

只改 expected_head 字符串 + f-string。**不动** `count == 1` 断言 (始终期望 1 head),**不动** hook (`scripts/alembic/check_single_head.sh`),**不动**任何 alembic migration。

## 真跑验证

```bash
cd /e/agent-w90-x3-alembic-drift
SKIP_DB_SETUP=1 pytest tests/alembic/ -v
```

**结果**: 4/4 PASS (冷缓存精确 returncode == 0)

```
tests/alembic/test_pre_commit_hook_passes.py::test_check_single_head_exits_zero_cold_cache PASSED
tests/alembic/test_pre_commit_hook_passes.py::test_check_single_head_stable_across_cold_runs PASSED
tests/alembic/test_pre_commit_hook_passes.py::test_check_single_head_ignores_syntax_warning PASSED
tests/alembic/test_pre_commit_hook_passes.py::test_actual_alembic_head_count_is_one PASSED
============================== 4 passed in 4.10s ==============================
```

## 边界复检

```bash
git diff main..HEAD --name-only
# (空输出 — 1 commit 还未生成)
```

**只改 1 文件**:
- `tests/alembic/test_pre_commit_hook_passes.py` (2 行: assert 字符串 + f-string)

**严禁改 (守恒)**:
- `app/`、`alembic/versions/`、`web/src/`、`nginx/`、`docker/`、`commercial/` — 全部不动
- 任何 alembic migration — 0 改动
- `scripts/alembic/check_single_head.sh` — 0 改动 (hook 行为不变)

## commit

```bash
git add tests/alembic/test_pre_commit_hook_passes.py memory/w90-x3-alembic-drift-2026-07-30.md
git commit -m "fix(w90): alembic test expected_head 087 → 090 (W90-X-3)

W89-X-17 据实: test 锚点漂移:
- 实测 head: 090_add_rag_eval_report (RAG PR5 5fdcb6819 后)
- 测试断言: 087_add_knowledge_original_parent_id (stale)
- PR1/PR2/PR3 + RAG PR5 推进后未同步 test

派工 brief 假设 089,实测 090 — 锚点又一次实测偏离 CLAUDE.md 历史 (类 20.32 同源)

派工 v6 §5 反馈 类 20.86 沉淀

锚点 +1 守恒 (462 → 463)"
git push -u origin claude/w90-x3-alembic-drift
```

## 派工 v6 §5 反馈 — 类 20.86 新增

**类 20.86 "alembic test 锚点必随 PR 同步(head 实测,不凭 CLAUDE.md 历史)"**

- **事故**: W89-X-17 据实 test 锚点漂移(`087` stale),W90-X-3 派工时主指挥预测实测 head 为 `089`,实测又为 `090` (RAG PR5 5fdcb6819 又推进一步)。两轮派工都基于 CLAUDE.md 历史推断 → **派工指令与实测又再次错位**。
- **教训**: 派工前提的 alembic head 必须**实测**(派工 agent 启动第一步),不能凭 CLAUDE.md 历史锚点或上一轮派工 brief。CLAUDE.md 锚点仅作 commit 历史的"快照",不是"实测承诺"。
- **修法**: 任何 alembic head 测试同步派工,**必须**包含:
  1. 派工 prompt 段 0 第 1 行:`实测 base ref HEAD: <hash>` + `实测 alembic head: <head>`
  2. agent 启动后**首先**实测 alembic head,不预设锚点值
  3. 修法仅限 `expected_head` 字符串替换 (1-2 行)
  4. 真跑验证 PASS 后 commit + memory 沉淀
- **关联**:
  - 类 20.29 "alembic head 数必须 worktree 实测,不可凭 hook 报告 + CLAUDE.md 历史"
  - 类 20.32 "协调 base 必实测 ls-remote origin,不可凭 CLAUDE.md 历史"
  - 类 20.86 (本条) **实测具体化**:即使上一轮派工刚报过的 head,新一轮派工仍必须实测 — RAG 系列 PR 跨 batch 推 alembic 是高风险点。
- **未来约束**: 任何修 `tests/alembic/test_pre_commit_hook_passes.py` 的派工,prompt 段 0 必须包含"实测 alembic head = ?" 实测字段,不接受 CLAUDE.md 历史锚点替代。

## 锚点预期

- base (main HEAD `034343f8a`): alembic head 090 → tip 守恒
- tip (commit pending): 锚点 +1 (462 → 463) **守恒**

## 文件路径

- worktree: `E:\agent-w90-x3-alembic-drift`
- branch: `claude/w90-x3-alembic-drift`
- 修改: `tests/alembic/test_pre_commit_hook_passes.py`
- 新增: `memory/w90-x3-alembic-drift-2026-07-30.md` (本文件)