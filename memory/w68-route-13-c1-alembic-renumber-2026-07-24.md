# W68 第 13 批 C-1：Alembic 070 重编号与单链守恒

> 日期：2026-07-24  
> 锚点范式：第 164 守恒  
> 任务：把 W68 第 12 批 B-1 / B-2 / C-2 并行产生的三个临时 070 规整为 074 / 075 / 076。  
> 范围：3 个 migration metadata + docs + memory；0 production code 改动铁律维持。

## 1. 任务背景

W68 第 11 批 C-1 已把知识库 migration 串为：

```text
069_drive_comments_recursive_func
  → 070_knowledge_rejected
  → 071_knowledge_rejected_retry
  → 072_kb_closed_loop
  → 073_kb_links_placeholder
```

W68 第 12 批又有三个并行任务新增 migration：

- B-1：PR14 评论 path 历史回填；
- B-2：PR15 文件版本标签；
- C-2：PR9 评论软删除。

三个 agent 启动时共同看到 069 为最新稳定上游，因而都临时声明：

```text
revision = 070_...
down_revision = 069_drive_comments_recursive_func
```

如果不在主指挥合并后统一收口，Alembic 会从 069 分叉并产生多个 head，重演 W68 第 3 批及第 9 批的 migration 双头事故。

## 2. 本次处理

三个 migration 的 `upgrade()` / `downgrade()` 内容全部保持不变，只修改 `revision` 与 `down_revision`。

### 2.1 评论软删除

文件：

```text
alembic/versions/070_drive_comments_soft_delete.py
```

修改：

```text
070_drive_comments_soft_delete
  → 074_drive_comments_soft_delete
```

接续：

```text
073_kb_links_placeholder
  → 074_drive_comments_soft_delete
```

### 2.2 文件版本标签

文件：

```text
alembic/versions/070_drive_version_tags.py
```

修改：

```text
070_drive_version_tags
  → 075_drive_version_tags
```

接续：

```text
074_drive_comments_soft_delete
  → 075_drive_version_tags
```

### 2.3 评论 path 回填

文件：

```text
alembic/versions/070_drive_comments_path_backfill.py
```

修改：

```text
070_drive_comments_path_backfill
  → 076_drive_comments_path_backfill
```

接续：

```text
075_drive_version_tags
  → 076_drive_comments_path_backfill
```

## 3. 最终 Alembic 链

完整相关链为：

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

唯一 head：

```text
076_drive_comments_path_backfill
```

本任务明确不修改：

```text
071_knowledge_rejected_retry
072_kb_closed_loop
073_kb_links_placeholder
```

它们属于 W68 第 11 批 C-1 已完成的 rebase 链，当前仅作为稳定上游被接续。

## 4. 合并顺序

主指挥按以下顺序合并：

1. W68 第 12 批 A-1 plans 状态；
2. W68 第 12 批 B-1 path backfill 来源分支；
3. W68 第 12 批 B-2 version tags 来源分支；
4. W68 第 12 批 C-2 comment soft delete 来源分支；
5. W68 第 13 批 C-1 renumber 补丁。

B-1 / B-2 / C-2 来源分支里的 070 是临时编号。只有三个来源 migration 都进入集成分支后，C-1 补丁才能一次性把它们串成最终单链。

C-1 不应提前合并，否则可能因目标文件尚不存在而无法应用，或被后合入的来源分支覆盖回临时 070。

## 5. 验证方法

仓库根目录执行：

```bash
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print(s.get_heads())"
```

预期严格等于：

```text
['076_drive_comments_path_backfill']
```

如果输出超过一个 revision，说明仍有分叉；如果输出 073、074 或 075，说明下游未正确接续；如果输出任何 `070_drive_*`，说明临时 metadata 未全部替换。

部署到容器前还必须清理：

```bash
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  rm -rf /app/alembic/versions/__pycache__
```

避免旧字节码保留旧 `down_revision`。

## 6. 0 production code 改动守恒

本任务不修改：

- `app/`；
- `web/src/`；
- 三个 migration 的 schema/data 操作；
- 071 / 072 / 073；
- 既有模型、service、API、前端组件。

允许的唯一代码类改动是三个新 migration 的 Alembic graph metadata：

```text
revision
down_revision
```

因此业务行为、数据库操作内容与运行时路径均不改变。

## 7. 五条新铁律

### 铁律 1：三个临时 070 必须固定映射为 074 / 075 / 076

W68 第 12 批三个 migration 的最终编号不可再自由排列：

```text
soft delete: 070 → 074
version tags: 070 → 075
path backfill: 070 → 076
```

这样才能接在 W68 第 11 批稳定链尾 073 后，并得到唯一 head 076。

### 铁律 2：串单链合并顺序必须与补丁依赖一致

先合并产生目标文件的 B-1、B-2、C-2，再合并 C-1 renumber 补丁。功能分支先、统一元数据补丁后，避免补丁丢失或被覆盖。

### 铁律 3：rebase 必须由掌握全局顺序的主指挥拍板

并行 agent 只看到局部分支，不能可靠判断其他 migration 的最终顺序。跨分支 `revision` / `down_revision` 重排必须由主指挥明确指定，agent 不得自行扩展修改范围。

### 铁律 4：不要为了消除本分支 head 而自动改别人的 migration

单个 agent 不得扫描到多 head 后就自动重写其他 migration。`down_revision` 是部署顺序契约，修改前必须有主指挥明确指令和最终链设计。

### 铁律 5：merge 后 `alembic heads` 单 head 是硬门禁

合并完成后必须验证 `ScriptDirectory.get_heads()`，并且结果严格为：

```text
['076_drive_comments_path_backfill']
```

不满足时禁止部署、禁止创建下游 migration、禁止宣布批次收官。

## 8. 锚点范式第 164 守恒

本任务作为 W68 第 13 批 C-1，完成以下守恒闭环：

1. 识别 B-1 / B-2 / C-2 三个临时 070 的必然冲突；
2. 复用 W68 第 11 批 C-1 的 073 稳定链尾；
3. 由主指挥明确最终编号 074 / 075 / 076；
4. 只改 metadata，不触碰 migration 主体；
5. 以 `get_heads()` 单 head 作为可验证物证；
6. 写入 docs 与 memory，避免同类事故再次依赖口头提醒。

锚点范式第 164 的核心不是“编号变化”本身，而是把并行开发的局部正确性收敛为主分支 migration graph 的全局唯一性。

## 9. 风险与边界

### 9.1 未部署前

若 074 / 075 / 076 尚未在数据库执行，本补丁可安全进入集成分支；Alembic 会按最终 graph 顺序升级。

### 9.2 已部署临时 070 时

如果任何环境已执行临时 revision，不得只替换代码后直接运行 upgrade。必须检查：

```sql
SELECT version_num FROM alembic_version;
```

再由主指挥决定 stamp、downgrade 或 forward-fix。revision ID 是数据库状态的一部分，不能在已部署后无计划改名。

### 9.3 文件名与 revision 不一致

本任务按完成定义保留三个 `070_*.py` 文件名，仅修改内部 metadata。Alembic 解析依据是 `revision` / `down_revision`，因此 graph 正确。

若未来决定同步物理重命名文件，应单独处理并避免与来源分支产生 rename 冲突。

## 10. 结论

W68 第 13 批 C-1 将三个并行临时 070 收敛为：

```text
073 → 074 soft delete → 075 version tags → 076 path backfill
```

它不改变业务代码，不改变 schema 操作内容，不修改 071 / 072 / 073。

最终唯一验收物证为：

```text
['076_drive_comments_path_backfill']
```

由此完成锚点范式第 164 守恒，并为后续 migration 提供唯一、明确、可继续接续的 head。
