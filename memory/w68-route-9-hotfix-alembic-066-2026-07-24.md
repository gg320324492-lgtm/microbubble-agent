# W68 第 9 批 hot-fix：alembic 066 串单链修复

日期：2026-07-24

## 背景

W68 第 8 批 B-1 新增 `066_drive_comments_path.py` 时，将 `down_revision` 写成了 `064_drive_documents`。但 W68 第 7 批 B-3 已经创建 `065_push_subscriptions`，因此 066 实际应当接在 065 后面。旧写法会使 Alembic 在 065 与 066 形成两个 head，部署执行 `alembic upgrade head` 时直接失败。

本次 hot-fix 从 main `05c60e68d` 拉出独立分支，只修复一行 migration 元数据，同时同步 PR9 评论文档的链路提示；不修改 067/068/069。

## 修复内容

```python
down_revision: Union[str, None] = "065_push_subscriptions"
```

目标链路为：

```text
064_drive_documents → 065_push_subscriptions → 066_drive_comments_path → 067 → 068 → 069
```

## 验证

- `ScriptDirectory.get_heads()` 返回唯一 head：`['066_drive_comments_path']`
- `ast.parse()` 成功解析 066 migration
- 066 的 migration 文件仍只包含本次 down_revision 修正；067/068/069 未修改
- 文档顶部增加了修复提示，明确 065→066→067 串链关系

## 五条新铁律

1. Alembic `down_revision` 的派工 prompt 必须明确写“接 X”，这是 W68 第 4 批串单链纪律的直接要求。
2. 并行派发 Alembic agent 前，必须先 verify 既有 head；A-1 agent 派工前缺少这一步，导致新 migration 错接旧 head。
3. 为修复 migration 拓扑而改一行 `down_revision` 不算 production code 改动，属于已批准的 W68 第 3 批 hot-fix 同模式例外。
4. merge 前必须运行 `alembic heads`（或等价 `ScriptDirectory.get_heads()`）验证；本次 A-1 agent 的验证实际抓到了双头问题，证明门禁有效。
5. PR11 agent 必须知晓 PWA push agent 已创建 065，不能重复接 064；接链判断要基于 main 已合并的最新 migration，而不是旧工作分支快照。

## 经验与后续

迁移文件的业务 SQL 即使完全正确，只要 revision 拓扑错误，整个部署仍然不可执行。后续每个 migration PR 应在提交前检查 `git log`、当前 `alembic heads` 和相邻 migration 的 `down_revision`，并在 PR 描述中写明上下游关系。主指挥合并时按链顺序合并，并在每次 merge 后立即复跑单 head 检查；不要用 `alembic upgrade heads` 掩盖分叉。

本 hot-fix 不 push 远端，由主指挥确认后手动推送和 merge。锚点范式计为第 105.1 守恒。
