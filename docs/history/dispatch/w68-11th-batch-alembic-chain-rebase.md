# W68 第 11 批 C-1: B-2/B-3/B-4 alembic 串单链冲突修复 (2026-07-24)

> **任务**: W68 第 11 批 C-1 子任务. 主基调: 0 production code 改动铁律维持, 仅 alembic migration metadata + docs + memory. 不动 app/ + tests/ + alembic/versions 老文件 (066-069 已合 main).

## §1 问题: B 派工 agent 写 alembic 跟 main 066/067/068/069 冲突

### 1.1 现状 (W68 第 10 批 B-2/B-3/B-4 agent 报告)

W68 第 10 批派 3 个 B 路线 agent 写 alembic migration, 全部基于 **stale main** 写 (worktree base 没 fetch 同步 W68 第 9+10 批合并的 066/067/068/069):

| Agent | 文件 | 当前 down_revision (stale) | 期望接续 (main 当前) |
|-------|------|---------------------------|---------------------|
| **B-2** save_to_kb 5 道防线 | `alembic/versions/066_knowledge_rejected.py` | `065_push_subscriptions` | `069_drive_comments_recursive_func` (main head) |
| **B-3** auto_intake rollback | `alembic/versions/067_knowledge_rejected_retry.py` | `066_knowledge_rejected` (B-2 stale) | `070_knowledge_rejected` (B-2 新位置) |
| **B-4** KB 闭环 | `alembic/versions/072_kb_closed_loop.py` | `065_push_subscriptions` | `071_knowledge_rejected_retry` (B-3 新位置) |
| **B-4** KB 闭环占位 | `alembic/versions/073_kb_links_placeholder.py` | `072_kb_closed_loop` | `072_kb_closed_loop` (保持) |

### 1.2 直接 merge 的 3 重阻塞

如果直接 merge 这 3 个分支, 部署时会报 3 个问题:

1. **alembic 双头阻塞**: B-2/B-3 都接 `065_push_subscriptions` (main 实际链 `065 → 066 → 067 → 068 → 069`), merge 后 alembic heads 至少有 2 个 head (068_drive_notification_dedup + 066_knowledge_rejected), `alembic upgrade head` 报 `Multiple head revisions are present`.
2. **重复 revision 字符串**: main 已有 `066_drive_comments_path` / `067_drive_reactions` / `068_drive_notification_dedup`, B-2/B-3 用 066/067 字符串直接冲突.
3. **跨 PR 部署错乱**: 066/067/068/069 已在 main, B 派工 agent 又写一遍, 部署时无法确定哪个是真.

### 1.3 B-1 调研 (W68 第 11 批 B-1)

W68 第 11 批 B-1 调研报告 (`memory/w68-route-11-b1-b234-alembic-investigation-2026-07-24.md`) 已确认:
- 066/067/068/069 在 main HEAD 已存在, 链路清晰 (`062 → 063 → 064 → 065 → 066 → 067 → 068 → 069`)
- B-2/B-3/B-4 alembic 文件是基于 stale main 写的, 必须 renumber + 重定向 down_revision
- 修复方案 = 重新规整 (rebase metadata), 不动 app/ + tests/ + 老 alembic 文件

## §2 重新规整: 改 4 个 migration 的 revision + down_revision

### 2.1 新 alembic 链 (rebase 后)

```text
062 (PR9 评论) → 063 (PR9 版本) → 064 (PR10 文档) → 065 (PWA push) → 066 (PR11 path) → 067 (PR12 reactions) → 068 (PR13 dedup) → 069 (PR11 recursive) → 070 (B-2 knowledge_rejected) → 071 (B-3 retry) → 072 (B-4 kb_closed_loop) → 073 (B-4 kb_links)
```

### 2.2 4 文件详细修改

| 文件 | 修改前 revision | 修改后 revision | 修改前 down_revision | 修改后 down_revision |
|------|----------------|----------------|---------------------|---------------------|
| `alembic/versions/066_knowledge_rejected.py` → **`070_knowledge_rejected.py`** | `066_knowledge_rejected` | `070_knowledge_rejected` | `065_push_subscriptions` | `069_drive_comments_recursive_func` |
| `alembic/versions/067_knowledge_rejected_retry.py` → **`071_knowledge_rejected_retry.py`** | `067_knowledge_rejected_retry` | `071_knowledge_rejected_retry` | `066_knowledge_rejected` (stale) | `070_knowledge_rejected` |
| `alembic/versions/072_kb_closed_loop.py` | `072_kb_closed_loop` (保持) | `072_kb_closed_loop` | `065_push_subscriptions` | `071_knowledge_rejected_retry` |
| `alembic/versions/073_kb_links_placeholder.py` | `073_kb_links_placeholder` (保持) | `073_kb_links_placeholder` | `072_kb_closed_loop` (保持) | `072_kb_closed_loop` |

### 2.3 改动范围

- **文件名 (git mv)**: 066_knowledge_rejected.py → 070_knowledge_rejected.py, 067_knowledge_rejected_retry.py → 071_knowledge_rejected_retry.py
- **文件名保持**: 072_kb_closed_loop.py, 073_kb_links_placeholder.py (072-073 数字正好不撞 main 066-069)
- **revision 字符串**: 4 文件全部更新 (含 2 文件名不变但 revision 字符串更新: 072 + 073)
- **down_revision**: 4 文件全部更新
- **docstring**: 4 文件 docstring 的"下接"和"实施纪律"段同步更新 (W68 第 3 批纪律说明 → W68 第 11 批 C-1 rebase 说明)

### 2.4 0 production code 改动铁律维持

- **不动**: `app/`、`web/src/`、`tests/`、`alembic/versions/066_drive_comments_path.py`、`067_drive_reactions.py`、`068_drive_notification_dedup.py`、`069_drive_comments_recursive_func.py` 老路径
- **可改**: `alembic/versions/0{70,71,72,73}_*.py` (新加文件 + revision/down_revision metadata)
- **可加**: `docs/w68-11th-batch-alembic-chain-rebase.md` (本文件) + `memory/w68-route-11-c1-alembic-rebase-2026-07-24.md` (锚点范式第 139 守恒)

## §3 验证

### 3.1 alembic 单 head 验证

```bash
$ python -c "
from alembic.config import Config
from alembic.script import ScriptDirectory
c = Config()
c.set_main_option('script_location', 'alembic')
s = ScriptDirectory.from_config(c)
print('alembic heads:', s.get_heads())
"
alembic heads: ['073_kb_links_placeholder']
```

**PASS**: 单 head = `073_kb_links_placeholder`. merge 部署后 `alembic upgrade head` 不会报 multiple heads.

### 3.2 链路 walk (从 073 反向回溯)

```
073_kb_links_placeholder
  └─ down_revision: 072_kb_closed_loop
      └─ down_revision: 071_knowledge_rejected_retry
          └─ down_revision: 070_knowledge_rejected
              └─ down_revision: 069_drive_comments_recursive_func
                  └─ down_revision: 068_drive_notification_dedup
                      └─ down_revision: 067_drive_reactions
                          └─ down_revision: 066_drive_comments_path
                              └─ down_revision: 065_push_subscriptions
                                  └─ down_revision: 064_drive_documents
                                      └─ ... (链路继续回溯)
```

**PASS**: 073 → 069 段链路正确, 069 → 064 段链路与 main 一致. 完整单链.

### 3.3 baseline 守恒

- **Lint CSS baseline 71 PASS + 7 SKIP 守恒**: 本任务未改任何 CSS/JS/Python source code (仅 alembic migration metadata docstring + 升级), baseline 必须维持
- **pytest 守恒**: alembic metadata 修改不影响 pytest 业务测试 (test_baseline_audit.py + 其他)
- **alembic 链历史 049 之前的 fork (041/048)**: 与本任务无关, 是 W66 前的历史遗留, 不在 C-1 范围

## §4 主指挥合并步骤 (按 alembic 链依赖)

按 alembic 串单链依赖关系, 主指挥 merge 必须按以下顺序, 否则 merge 后 alembic 会再分叉:

### 4.1 Merge 顺序 (4 步)

```bash
# 第 1 步 (A-2 hot-fix): merge `feat/w68-10th-batch-a2-alembic-066-hotfix-2026-07-24`
#   - 066_drive_comments_path 改 down_revision 接 065_push_subscriptions (已在 W68 第 10 批合并 commit `b0b889b9e`, 跳过)
#   - 实际状态: 已合并 ✓

# 第 2 步 (A-3 B 路线 5 分支): merge 5 个 Drive v2 PR11/12/13 分支
#   - feat/drive-v2-pr11-path-materialized-2026-07-24 → 066
#   - feat/drive-v2-pr12-reactions-2026-07-24 → 067
#   - feat/drive-v2-pr13-combined-notifications-2026-07-24 → 068
#   - feat/drive-v2-pr11-recursive-fallback-2026-07-24 → 069
#   - feat/desktop-comment-v32-2026-07-24 (前端, 不含 alembic)
#   - 实际状态: 已合并 ✓ (W68 第 10 批 grand closure 收口)

# 第 3 步 (B 派工 4 分支 + 本次 C-1 rebase): merge B-2/B-3/B-4 alembic rebase 后分支
#   - feat/w68-10th-batch-b2-save-to-kb-2026-07-24 → alembic 070 段 (B-2 主 commit 内 070 替换原 066)
#   - feat/w68-10th-batch-b3-auto-intake-rollback-2026-07-24 → alembic 071 段 (B-3 主 commit 内 071 替换原 067)
#   - feat/w68-10th-batch-b4-kb-closed-loop-2026-07-24 → alembic 072/073 段 (B-4 down_revision 改 071)
#   - 实际建议: 主指挥在本 PR (fix/w68-11th-batch-alembic-rebase-2026-07-24) merge 后, 派 1 个 agent 把 4 个新 alembic 文件 cherry-pick 进 B-2/B-3/B-4 分支, 再 merge B 分支到 main

# 第 4 步 (本 PR): merge `fix/w68-11th-batch-alembic-rebase-2026-07-24`
#   - 本 PR 直接 add 4 个 rebase 后的 alembic 文件 + 1 个 docs + 1 个 memory
#   - 主指挥在本 PR merge 后, 派 1 个 B 路线收尾 agent 删 B-2/B-3/B-4 分支里的 alembic 文件 (避免 double-merge)
```

### 4.2 部署验证步骤 (merge 后, 生产部署前)

```bash
# 1. cp 4 个 alembic 文件到 docker app 容器
docker cp alembic/versions/070_knowledge_rejected.py microbubble-agent-app-1:/app/alembic/versions/
docker cp alembic/versions/071_knowledge_rejected_retry.py microbubble-agent-app-1:/app/alembic/versions/
docker cp alembic/versions/072_kb_closed_loop.py microbubble-agent-app-1:/app/alembic/versions/
docker cp alembic/versions/073_kb_links_placeholder.py microbubble-agent-app-1:/app/alembic/versions/

# 2. 清 alembic pycache (CLAUDE.md 752 行铁律)
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__

# 3. 验证单 head (生产环境)
docker exec microbubble-agent-app-1 alembic heads
# 期望输出: 073_kb_links_placeholder (head)

# 4. 跑迁移
docker exec microbubble-agent-app-1 alembic upgrade head

# 5. 验证 4 张表存在 (knowledge_rejected, knowledge_pending_review, kb_closed_loop_log, kb_links)
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\dt" | grep -E "knowledge_rejected|knowledge_pending_review|kb_closed_loop_log|kb_links"

# 6. 重启 Python 进程
docker compose restart app celery-worker
```

### 4.3 回滚路径

如部署后发现 alembic 链异常:

```bash
# 1. alembic 降级 4 个新迁移
docker exec microbubble-agent-app-1 alembic downgrade 069_drive_comments_recursive_func

# 2. 回滚本 PR (git revert)
git revert <commit-hash-of-this-fix-branch>
git push origin main

# 3. 重跑 alembic
docker exec microbubble-agent-app-1 alembic upgrade head

# 4. 重启 Python 进程
docker compose restart app celery-worker
```

## §5 5 新铁律 (永久固化)

### 5.1 alembic migration 必先 verify main 已有哪些 migration (派工 prompt 必含)

**铁律 1**: 任何写 alembic migration 的 agent 在派工 prompt 里必须明确:
- "当前 main 已有 N 个 migration, 最新 revision 是 X (派工前一日 git log 查 main HEAD 得出)"
- "你的 migration 必须接续 X, 编号用 X+1"
- "实施前必跑 `python -c "from alembic.script import ScriptDirectory; ..."` 拿 main 当前 heads"

**反向事故**: B-2/B-3/B-4 派工时 prompt 没写 main 当前 head, agent 默认接 `065_push_subscriptions`, 跟 main 实际链路 (`065 → 066 → 067 → 068 → 069`) 冲突.

### 5.2 worktree base 必 fetch 同步

**铁律 2**: 写 alembic migration 的 agent worktree 必须基于 `origin/main` (not stale local main), 派工 prompt 模板:
```bash
git fetch origin main
git checkout -b feat/xxx origin/main   # 基于 origin/main 建 worktree, 不是 local main
```

**反向事故**: B-2/B-3/B-4 worktree base 是 local main, 没 fetch origin/main, 导致 main HEAD 已经 merge 066/067/068/069 但 worktree 看不到.

### 5.3 派工 prompt 必写"接 X" + "X 是当前 head" (3 步 boilerplate)

**铁律 3**: 派工 alembic migration agent 的 prompt 模板 (W68 第 11 批 C-1 起强制):
```
1. 当前 main alembic head 是: <revision> (派工前一日 git log 查 main HEAD)
2. 你的 migration 必须接续: down_revision = "<revision>"
3. 实施前必跑 `alembic heads` 验证单 head
```

3 步 boilerplate 任一缺失, agent 默认接 `065_push_subscriptions` 老 anchor, 必撞 main 新链路.

### 5.4 B 派工 agent 必先跑 `alembic heads`

**铁律 4**: 任何 alembic migration agent 开始实施前, 第一件事必跑:
```bash
python -c "
from alembic.config import Config
from alembic.script import ScriptDirectory
c = Config(); c.set_main_option('script_location', 'alembic')
s = ScriptDirectory.from_config(c)
print('current heads:', s.get_heads())
"
```

期望只 1 个 head. 若多个 head, 立刻报告主指挥, **不**自行修复 (主指挥拍板, 见铁律 5).

### 5.5 merge 时 alembic 冲突必主指挥拍板

**铁律 5**: alembic 冲突 (双 head / 重复 revision / down_revision 接错) **不**由 B 派工 agent 自动修, 必须主指挥拍板:
- B 派工 agent 报告冲突 → 主指挥派 C-1 类 rebase agent 重新规整 metadata
- 或主指挥直接 `git revert` 老 commit + 派新 B agent 重写
- **不**允许 B 派工 agent 自己改 down_revision 跨 PR 重接 (CLAUDE.md W68 第 3 批纪律, 锚点范式第 46 守恒)

## §6 关联记忆 + 后续

- **锚点范式第 139 守恒**: `memory/w68-route-11-c1-alembic-rebase-2026-07-24.md`
- **W68 第 11 批 B-1 调研**: `memory/w68-route-11-b1-b234-alembic-investigation-2026-07-24.md`
- **CLAUDE.md 永久锚点**: `## W68 第 6+7+8 批纪律沉淀 (永久锚点)` → §2.3 alembic 串单链纪律 + 本节 5 新铁律升级
- **W68 第 11 批 grand closure**: 待派 1 个 D 路线 agent 写 `memory/w68-grand-closure-11th-batch-2026-07-24.md`