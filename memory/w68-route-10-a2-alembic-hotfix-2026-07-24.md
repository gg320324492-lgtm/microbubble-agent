# 2026-07-24 W68 第 10 批 A-2: alembic 066 down_revision 串单链 hot-fix 合并 (锚点范式第 121 守恒)

> **一句话**: W68 第 9 批 B-1 (PR11 path 物化) agent 写 `066_drive_comments_path.py` 时 `down_revision` 错成 `064_drive_documents`, 应为 `065_push_subscriptions` (W68 第 7 批 B-3 已建 065)。W68 第 9 批 hot-fix agent 已修 1 行 (commit `df2609dd6`), W68 第 10 批 A-2 主指挥执行 merge 协调 (commit `67e7b06fa`)。**0 production code 改动铁律维持** (本批 hot-fix 仅 alembic 1 行 + docs 2 行 + memory 1 文件)。

## 定位

- **锚点范式**: 第 121 守恒 (W68 第 10 批 A-2 merge 协调段)
- **上游锚点**:
  - `w68-route-9-hotfix-alembic-066-2026-07-24.md` (W68 第 9 批 hot-fix 阶段, 锚点范式第 105.1)
  - `w68-alembic-chain-discipline-2026-07-24.md` (W68 第 4 批 串单链纪律, 锚点范式第 46)
- **同类先例**:
  - W68 第 4 批 `1852468a6` (062/063 并行 → 主指挥改 063 down_revision 串单链)
  - W68 第 9 批 hot-fix `df2609dd6` (066 down_revision `064` → `065_push_subscriptions`)
- **main HEAD (本批 merge 前)**: `f14cb43c1` (W68 第 8 批 A-1)
- **本批 merge 后**: `67e7b06fa` (origin/main 待 push)

## 完整时间线

### T0: 派工阶段 (W68 第 9 批 B-1)

W68 第 8 批 B-1 agent 写 `066_drive_comments_path.py` 时, 由于并行派工时未明确"接 065_push_subscriptions", 默认接到当时已 merged 的 `064_drive_documents` (W68 第 4 批 hot-fix 后 064 已是 head)。但 W68 第 7 批 B-3 agent 已经创建 `065_push_subscriptions` 并已 merge 进 main — 066 实际应接 065, 不是 064。

**派工 prompt 缺陷**: 派工时没写"down_revision 接 X", 默认接 064 → 实际应该是 065 (W68 第 7 批已有 065, 派工时未 verify 既有 head)。

### T1: W68 第 9 批 hot-fix agent 修复 (commit `df2609dd6`)

W68 第 9 批 hot-fix #16 agent 拉出独立分支 `fix/w68-9th-batch-alembic-066-down-revision-2026-07-24`, 修复 1 行:

```python
# alembic/versions/066_drive_comments_path.py
down_revision: Union[str, None] = "065_push_subscriptions"   # 原为 064_drive_documents
```

同时:
- `docs/drive-v2-pr9-comments.md` 增加 2 行串链提示
- `memory/w68-route-9-hotfix-alembic-066-2026-07-24.md` 沉淀 5 条铁律

总计 45 insertions, 1 deletion, 3 文件改动 (0 production code 改动铁律维持)。

### T2: 主指挥 merge 协调 (W68 第 10 批 A-2 本任务)

主指挥先 merge A-1 (12+1 docs/memory 分支), 然后执行 A-2:

```bash
git merge --no-ff fix/w68-9th-batch-alembic-066-down-revision-2026-07-24 \
  -m "merge: alembic 066 down_revision 串单链 (W68 第 10 批 hot-fix)"
```

**结果**: merge commit `67e7b06fa`, ort strategy 自动处理, 0 冲突 (hot-fix 与 docs/memory 改动无重叠)。

### T3: alembic 链验证

```bash
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; \
c=Config(); c.set_main_option('script_location','alembic'); \
s=ScriptDirectory.from_config(c); print(s.get_heads())"
```

**期望**: `['066_drive_comments_path']` 单 head ✅

### T4: 部署影响

- 部署前必跑 `alembic upgrade head` (单 head 无歧义)
- 066 的 SQL 内容不变, 只调整 down_revision 元数据
- 已部署过的 064 → 065 链不动, 仅 066 接续关系从 064 改为 065

## 五条新铁律

1. **hot-fix 必含 commit message 标识** — 任何 alembic 串单链 hot-fix 必须在 commit message 第一行明确写"fix(alembic): chain X after Y"格式, 方便后续 git log --grep 检索 (本次 `df2609dd6` 完全符合)。

2. **alembic 串单链验证必须在 merge 立即跑** — merge 后 5 分钟内必跑 `ScriptDirectory.get_heads()`, 期望单 head。失败立即 revert, 不要等部署才发现。

3. **不要自动修老 alembic migration** — 修复串单链只改 1 行 `down_revision` 元数据, **不要** 顺手改 SQL / 字段 / 索引。本次 `df2609dd6` 只改 1 行, 0 production code 改动铁律维持。

4. **并行派 alembic agent 必 verify 既有 head** — 派工 prompt **必须** 写"down_revision 接 X" (X = 当前 main 已 merge 的最新 alembic head), **不写就默认接 main 最新 head, 而不是默认接某个固定编号**。本次 W68 第 8 批 B-1 agent 默认接到 064 (派工时 main 最新), 实际应该是 065 (W68 第 7 批已 merge 的 push subscriptions)。

5. **派工 prompt 必写"接 X"  + verify X 是当前 head** — 派工 prompt 模板:
   ```
   1. git fetch origin main
   2. python -c "from alembic.script import ScriptDirectory; print(ScriptDirectory.from_config(Config()).get_heads())"
   3. 确认你写 down_revision = "<最新 head>"
   ```
   写不下就别接 alembic migration。

## 经验与后续

- **重复踩同一坑** — W68 第 4 批 062/063 并行 + W68 第 8 批 066 默认接 064, 两次都是"派工 prompt 没写接 X"。CLAUDE.md 已有「2026-07-24 alembic 并行 agent 串单链纪律」节 (锚点范式第 46 守恒), 但派工模板没升级。
- **加固方向** — 后续 W68 第 11 批可派 1 个 agent 升级派工 prompt 模板: 所有 alembic 派工前必加"verify 当前 head + 接 X"两行 boilerplate。
- **回滚路径** — `git revert 67e7b06fa` 一行撤销 + 重新部署。< 5 分钟恢复。
- **下一 PR 风险** — 067/068/069 alembic migration 派工时, 主指挥**必须** 亲自 verify 既有 head 写到 prompt 里, 不能依赖 agent 自行判断。

锚点范式计为第 121 守恒, 0 production code 改动铁律完全维持。
