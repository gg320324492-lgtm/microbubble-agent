# W68 第 11 批 C-1: B-2/B-3/B-4 alembic 串单链冲突修复 (锚点范式第 139 守恒)

> **主基调**: 0 production code 改动铁律维持, 仅 alembic migration metadata + docs + memory. 主指挥协调范式第 40 次派工. 锚点范式第 139 守恒 (W68 第 10 批 130 → W68 第 11 批 C-1 139, 9 守恒).
>
> **W68 第 10 批 B 派工 (B-2 save_to_kb 5 道防线 + B-3 auto_intake rollback + B-4 KB 闭环) alembic 全部基于 stale main 写**, 没 fetch origin/main, 没跑 alembic heads, 没在派工 prompt 注明 main 当前 head. 直接 merge 会触发 alembic 双头阻塞 + 重复 revision 字符串冲突.

## 时间线 (2026-07-24)

| 时间 | 事件 |
|------|------|
| 14:00 | W68 第 10 批 B 派工 prompt 派 3 个 agent (B-2/B-3/B-4), prompt 未含 alembic heads check + 接续关系 |
| 15:51 | B-4 commit `0066087c8` 写 alembic 072/073 接 `065_push_subscriptions` (stale main) |
| 15:55 | B-3 commit `64660718d` 写 alembic 066/067 接 `065_push_subscriptions` (stale main) |
| 16:00 | B-2 commit 写 alembic (实际由 B-3 同 agent 实施 066/067) |
| 16:30 | W68 第 10 批 grand closure 主指挥 merge A 路线 + hot-fix (commit `b0b889b9e` 066 hot-fix + `67e7b06fa` 066 down_revision 串单链) |
| 17:00 | 主指挥协调范式第 38-39 次派工: B-2/B-3/B-4 merge 进 main (含 alembic 066/067/072/073 重复) |
| 18:00 | 主指挥发现 alembic 重复 + 双头风险, 决定派 B-1 调研 + C-1 rebase |
| 18:30 | B-1 调研完成: `memory/w68-route-11-b1-b234-alembic-investigation-2026-07-24.md` 确认 066/067/068/069 已合 main, B-2/B-3/B-4 alembic 必须 renumber + 重定向 |
| 19:00 | C-1 agent (本任务) 派工, 重新规整 4 个 alembic 文件 (066 → 070, 067 → 071, 072 → 072, 073 → 073) |
| 19:30 | alembic chain 验证单 head `073_kb_links_placeholder` ✓ |
| 20:00 | 本 memory + docs 沉淀完成 |

## 5 新铁律 (永久锚点, 跟 docs §5 同步)

### 铁律 1: alembic migration 必先 verify main 已有哪些 migration (派工 prompt 必含)

派工 prompt 模板必含 3 段:
1. 当前 main alembic head 是: `<revision>` (派工前一日 git log 查 main HEAD)
2. 你的 migration 必须接续: `down_revision = "<revision>"`
3. 实施前必跑 `alembic heads` 验证单 head

### 铁律 2: worktree base 必 fetch 同步

写 alembic migration 的 agent worktree 必须基于 `origin/main`:
```bash
git fetch origin main
git checkout -b feat/xxx origin/main   # 基于 origin/main, 不是 local main
```

### 铁律 3: 派工 prompt 必写"接 X" + "X 是当前 head" (3 步 boilerplate)

任一缺失, agent 默认接 `065_push_subscriptions` 老 anchor, 必撞 main 新链路.

### 铁律 4: B 派工 agent 必先跑 `alembic heads`

实施前第一件事:
```bash
python -c "
from alembic.config import Config
from alembic.script import ScriptDirectory
c = Config(); c.set_main_option('script_location', 'alembic')
s = ScriptDirectory.from_config(c)
print('current heads:', s.get_heads())
"
```

期望只 1 个 head. 多个 head 立刻报告主指挥.

### 铁律 5: merge 时 alembic 冲突必主指挥拍板

B 派工 agent **不**自动修 down_revision, 必须主指挥派 C-1 rebase agent:
- B agent 报告冲突 → 主指挥派 rebase agent 重新规整 metadata
- 或主指挥直接 `git revert` + 派新 B agent 重写
- (CLAUDE.md W68 第 3 批纪律, 锚点范式第 46 守恒)

## 重新规整的 alembic 链 (新 4 节点)

```text
069_drive_comments_recursive_func (main head)
  └─ 070_knowledge_rejected (B-2 save_to_kb)
      └─ 071_knowledge_rejected_retry (B-3 auto_intake rollback)
          └─ 072_kb_closed_loop (B-4 KB 闭环)
              └─ 073_kb_links_placeholder (B-4 占位) ← 新 single head
```

**完整链**: `062 → 063 → 064 → 065 → 066 → 067 → 068 → 069 → 070 → 071 → 072 → 073`

## 验证结果

```bash
$ python -c "
from alembic.config import Config
from alembic.script import ScriptDirectory
c = Config(); c.set_main_option('script_location', 'alembic')
s = ScriptDirectory.from_config(c)
print('alembic heads:', s.get_heads())
"
alembic heads: ['073_kb_links_placeholder']
```

**PASS**: 单 head = `073_kb_links_placeholder`. merge 部署后 `alembic upgrade head` 不会报 multiple heads.

## 0 production code 改动铁律维持

- **不动**: `app/`、`web/src/`、`tests/`、`alembic/versions/066-069_*.py` 老路径
- **可改**: `alembic/versions/0{70,71,72,73}_*.py` (新加文件 + revision/down_revision metadata)
- **可加**: `docs/w68-11th-batch-alembic-chain-rebase.md` + 本 memory

## 主指挥合并顺序 (按 alembic 链依赖)

1. **A-2 hot-fix**: 066_drive_comments_path down_revision 改 065_push_subscriptions (已合并, commit `b0b889b9e`)
2. **A-3 B 路线 5 分支**: 066/067/068/069 入 main (已合并, W68 第 10 批 grand closure)
3. **B 派工 4 分支**: B-2/B-3/B-4 alembic rebase 后 merge (本 PR 收尾)
4. **本 PR merge**: `fix/w68-11th-batch-alembic-rebase-2026-07-24` 直接 add 4 个 rebase 后 alembic 文件 + docs + memory

## 关联沉淀

- **docs**: `docs/w68-11th-batch-alembic-chain-rebase.md` (5 新铁律 + 完整链路 + 部署/回滚步骤)
- **CLAUDE.md 永久锚点升级**: `## W68 第 6+7+8 批纪律沉淀 (永久锚点)` → §2.3 alembic 串单链纪律 + 本节 5 新铁律
- **W68 第 11 批 grand closure**: 待派 1 个 D 路线 agent 写 `memory/w68-grand-closure-11th-batch-2026-07-24.md`

## 锚点范式

W68 第 10 批 130 → **W68 第 11 批 C-1 139** (9 守恒: alembic 重新规整 + 5 新铁律 + docs + memory + grand closure prep).