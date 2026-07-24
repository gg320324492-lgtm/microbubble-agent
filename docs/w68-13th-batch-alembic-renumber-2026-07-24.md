# W68 第 13 批 C-1：Alembic 070 冲突重编号与单链收口

> 日期：2026-07-24  
> 范围：仅修改 3 个新 migration 的 `revision` / `down_revision` 元数据，并记录合并纪律。  
> 目标：将 W68 第 12 批 B-1、B-2、C-2 并行产生的三个临时 `070` 规整为 `074 → 075 → 076`，最终 Alembic 仅保留一个 head。  
> 约束：不修改 071、072、073；不修改 migration 的 `upgrade()` / `downgrade()` 业务内容；不改 production code。

## §1 问题：三个并行任务同时占用 070

### 1.1 背景

W68 第 11 批 C-1 已完成知识库相关 migration 的 rebase，既有链尾为：

```text
069_drive_comments_recursive_func
  → 070_knowledge_rejected
  → 071_knowledge_rejected_retry
  → 072_kb_closed_loop
  → 073_kb_links_placeholder
```

与此同时，W68 第 12 批三个独立 agent 从各自工作分支并行开发：

- B-1：Drive v2 PR14，历史评论 path backfill；
- B-2：Drive v2 PR15，文件版本 tags；
- C-2：Drive v2 PR9 评论软删除。

三个任务开始时看到的共同上游都是 `069_drive_comments_recursive_func`，因此都临时使用了 `070`：

```text
070_drive_comments_path_backfill
070_drive_version_tags
070_drive_comments_soft_delete
```

它们的 `down_revision` 也都指向：

```python
down_revision = "069_drive_comments_recursive_func"
```

### 1.2 冲突表现

如果主指挥直接合并三个分支而不做统一重编号，Alembic revision graph 会从 069 分叉：

```text
                         ┌─ 070_drive_comments_path_backfill
069_recursive_func ──────┼─ 070_drive_version_tags
                         └─ 070_drive_comments_soft_delete
```

再叠加 W68 第 11 批 C-1 已存在的 `070_knowledge_rejected → 071 → 072 → 073`，会同时出现：

1. 多个 migration 文件占用相同的数字前缀 `070`；
2. 多个 revision 从同一个 `069` 分叉；
3. `alembic upgrade head` 无法确定唯一 head；
4. `downgrade -1` 的前驱语义不再唯一；
5. 后续新增 migration 无法安全决定应接哪个 head。

典型错误是：

```text
FAILED: Multiple head revisions are present for given argument 'head'
```

### 1.3 根因

根因不是 migration 的 schema 内容，而是并行派工期间缺少最终 revision 号的全局协调。

各 agent 在隔离分支里只能基于任务启动时的 main HEAD 编号。只要多个任务都要新增 migration，单靠“各自接当前最新 revision”无法保证合并后的全局唯一性。

因此，临时编号可以存在于 agent 分支，但不能未经主指挥规整就进入最终部署链。

### 1.4 影响边界

本次冲突只涉及 Alembic 元数据：

- `revision`；
- `down_revision`。

三个 migration 的实际 schema/data 操作保持不变：

- path backfill 仍只重建历史评论路径；
- version tags 仍创建版本标签表；
- comment soft delete 仍增加 `deleted_at` / `deleted_by`。

因此本补丁不改变业务行为，只修复 migration graph。

## §2 重新规整：073 → 074 → 075 → 076

### 2.1 最终链

以 W68 第 11 批 C-1 已修复的 `073_kb_links_placeholder` 为稳定上游，三个临时 070 依次排列为：

```text
069_drive_comments_recursive_func
  → 070_knowledge_rejected
  → 071_knowledge_rejected_retry
  → 072_kb_closed_loop
  → 073_kb_links_placeholder
  → 074_drive_comments_soft_delete
  → 075_drive_version_tags
  → 076_drive_comments_path_backfill
```

此链满足：

- 每个 revision ID 全局唯一；
- 每个 migration 只有一个直接前驱；
- graph 不分叉；
- 最终只有一个 head；
- 未来 migration 可直接接 `076_drive_comments_path_backfill`。

### 2.2 C-2：评论软删除 070 → 074

文件：

```text
alembic/versions/070_drive_comments_soft_delete.py
```

元数据从：

```python
revision = "070_drive_comments_soft_delete"
down_revision = "069_drive_comments_recursive_func"
```

改为：

```python
revision = "074_drive_comments_soft_delete"
down_revision = "073_kb_links_placeholder"
```

选择 074 的原因：它是既有稳定链尾 073 后的第一个可用 revision，并且软删除 schema 是后续两个 Drive migration 的统一前驱。

### 2.3 B-2：版本标签 070 → 075

文件：

```text
alembic/versions/070_drive_version_tags.py
```

元数据从：

```python
revision = "070_drive_version_tags"
down_revision = "069_drive_comments_recursive_func"
```

改为：

```python
revision = "075_drive_version_tags"
down_revision = "074_drive_comments_soft_delete"
```

这样 PR15 tags 不再与已有知识库 070 或其他临时 070 冲突，并明确接在评论软删除之后。

### 2.4 B-1：path backfill 070 → 076

文件：

```text
alembic/versions/070_drive_comments_path_backfill.py
```

元数据从：

```python
revision = "070_drive_comments_path_backfill"
down_revision = "069_drive_comments_recursive_func"
```

改为：

```python
revision = "076_drive_comments_path_backfill"
down_revision = "075_drive_version_tags"
```

path backfill 成为最终链尾，因此唯一预期 head 是：

```text
076_drive_comments_path_backfill
```

### 2.5 为什么不修改文件名

本任务完成定义要求修改现有三个文件中的 Alembic metadata，未要求物理重命名文件。

Alembic 识别 revision graph 的依据是文件内 `revision` / `down_revision`，不是文件名前缀。因此即使文件名保留临时 `070_...`，graph 仍按 074、075、076 正确解析。

后续如果主指挥希望文件名与 revision ID 完全一致，应另行拍板并在同一合并窗口处理，避免与当前三个来源分支产生 rename 冲突。本补丁不扩大范围。

### 2.6 明确不动 071 / 072 / 073

以下文件由 W68 第 11 批 C-1 rebase 修复，当前保持原样：

```text
alembic/versions/071_knowledge_rejected_retry.py
alembic/versions/072_kb_closed_loop.py
alembic/versions/073_kb_links_placeholder.py
```

本任务仅将三个新 migration 接到 073 之后，不回写、不重排、不改动 071/072/073 的内容或 metadata。

## §3 验证：Alembic heads 必须为单 head

### 3.1 标准验证命令

在仓库根目录运行：

```bash
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print(s.get_heads())"
```

### 3.2 预期结果

```text
['076_drive_comments_path_backfill']
```

任何以下结果都不允许进入主分支：

- 返回两个或更多 head；
- 返回 073、074 或 075；
- 返回任意 `070_drive_*` 临时 revision；
- 报 revision 找不到；
- 报重复 revision ID。

### 3.3 静态核对

除 `get_heads()` 外，主指挥还应核对：

```text
073_kb_links_placeholder
  ↓
074_drive_comments_soft_delete
  ↓
075_drive_version_tags
  ↓
076_drive_comments_path_backfill
```

并确认三个 migration 的 `upgrade()` / `downgrade()` 未被本补丁修改。

### 3.4 部署前核对

部署前须清理容器中的 Alembic Python cache，避免旧 `down_revision` 字节码残留造成“源码已修、运行仍双头”的假象：

```bash
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  rm -rf /app/alembic/versions/__pycache__
```

然后再运行：

```bash
docker exec microbubble-agent-app-1 alembic heads
docker exec microbubble-agent-app-1 alembic upgrade head
```

容器内 `alembic heads` 同样必须只显示 `076_drive_comments_path_backfill`。

## §4 主指挥合并步骤

### 4.1 推荐合并顺序

按任务协调顺序执行：

1. merge W68 第 12 批 A-1 plans 状态；
2. merge W68 第 12 批 B-1（其 migration 在来源分支仍是临时 070，最终改为 076）；
3. merge W68 第 12 批 B-2（其 migration 在来源分支仍是临时 070，最终改为 075）；
4. merge W68 第 12 批 C-2（其 migration 在来源分支仍是临时 070，最终改为 074）；
5. merge W68 第 13 批 C-1 主指挥补丁，统一修改为 074 / 075 / 076 并串成单链。

### 4.2 为什么修复补丁最后合并

本 C-1 补丁引用三个来源 migration 文件。只有 B-1、B-2、C-2 都已进入主指挥集成分支后，补丁中的三个 metadata 修改才都有目标文件可应用。

若提前合并补丁，可能出现：

- 文件不存在导致补丁无法应用；
- 后合并来源分支把修复覆盖回临时 070；
- cherry-pick 时产生 add/add 或 content conflict；
- 主指挥误以为已单链，最终合并后又重新分叉。

因此顺序必须是“来源功能分支先进入，统一 renumber 补丁最后收口”。

### 4.3 每步检查

完成第 2～4 步后出现多 head 是已知的临时集成态，但不能部署，也不能把该状态作为最终 main HEAD 发布。

完成第 5 步后立即运行单 head 验证。只有输出：

```text
['076_drive_comments_path_backfill']
```

才允许继续后续合并或部署。

### 4.4 冲突处理原则

如果主指挥在合并时发现 migration metadata 冲突：

- 保留三个 migration 的业务主体；
- 以本文件 §2 的最终 revision graph 为准；
- 不自动猜测新编号；
- 不把多个 revision 合成 Alembic merge revision；
- 不使用 `alembic upgrade heads` 绕过单链门禁；
- 冲突处理完再次运行 `ScriptDirectory.get_heads()`。

### 4.5 回滚原则

若该补丁尚未部署，可直接 revert metadata commit 后重新协调。

若已在任一数据库执行 074 / 075 / 076，不应只改文件内 revision 字符串后强行部署；必须先核对 `alembic_version` 表与实际 schema，再由主指挥制定 stamp / downgrade / forward-fix 方案。

## §5 五条新铁律

### 铁律 1：多个 B 路线派工包含 Alembic migration 时必须预分配唯一 revision

并行任务不能都写“接当前 head + 使用下一个编号”。派工 prompt 必须显式指定每个任务的最终 revision，或明确写成临时编号并指定主指挥收口任务。

### 铁律 2：主指挥合并前必须按 W68 第 11 批 C-1 模式 rebase migration chain

功能分支可并行开发，但最终 revision graph 必须由掌握全局合并顺序的主指挥统一 rebase。agent 不得根据不完整分支视图自行重排其他任务的 migration。

### 铁律 3：`alembic heads` 单 head 是合并硬门禁

每次合并新增 migration 后必须运行 `ScriptDirectory.get_heads()`。输出不是长度 1 时，禁止部署、禁止宣布收官、禁止继续创建下一个 migration。

### 铁律 4：不要自动修改其他 migration 的 `down_revision`

`down_revision` 代表部署顺序，不只是文本引用。除非主指挥任务明确拍板，不得为了让本分支“看起来单 head”而自动改动别人的 migration。

### 铁律 5：W68 第 12 批 B-1 / B-2 / C-2 的 070 是临时编号，合并后必须改

三个临时编号的最终映射固定为：

```text
C-2 soft delete: 070 → 074
B-2 version tags: 070 → 075
B-1 path backfill: 070 → 076
```

主指挥完成来源分支合并后，必须应用本补丁并验证唯一 head，不能把临时 070 直接部署。

## 结论

本次补丁只调整三个新 migration 的 `revision` / `down_revision`：

```text
073_kb_links_placeholder
  → 074_drive_comments_soft_delete
  → 075_drive_version_tags
  → 076_drive_comments_path_backfill
```

071、072、073 保持不变；三个 migration 的 schema/data 操作保持不变；production code 保持不变。

最终验收标准只有一个：

```text
['076_drive_comments_path_backfill']
```

该输出是 W68 第 13 批 C-1 合并完成与允许部署的硬门禁。
