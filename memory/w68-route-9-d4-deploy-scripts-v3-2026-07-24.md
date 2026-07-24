# W68 第 9 批 D-4 部署脚本 v3（2026-07-24）

## 1. 任务定位

本任务是 W68 第 9 批 D-4，范围严格限制为 scripts、docs、memory。
不修改 API、service、ORM、migration 或前端生产代码。
目标是把 W68 第 8 批 A-3 的部署验收能力从 alembic 065 延伸到 069。

## 2. 锚点范式

锚点范式第 118 守恒。

本次守恒对象不是新增业务能力，而是让已经分别实现的 PR11、PR12、PR13 与 fallback migration 具备可执行、可复查、可回滚的统一部署路径。

## 3. alembic 单链

最终部署链必须保持唯一 head：

```text
061_drive_folder_share
  -> 062_drive_comments
  -> 063_drive_file_versions
  -> 064_drive_documents
  -> 065_push_subscriptions
  -> 066_drive_comments_path
  -> 067_drive_reactions
  -> 068_drive_notification_dedup
  -> 069_drive_comments_recursive_func
```

任何迁移接错上游都会重现 W68 第 3 批 062/063 双头事故。
部署前必须确认四个新增 migration 文件都已 merge。
部署时必须按编号 copy。
copy 后必须清理容器内 alembic `__pycache__`。
upgrade 前后都要确认唯一 head。

## 4. 13 段验证

升级后的 `scripts/verify_w68_7th_batch_deployment.sh` 保留既有检查，并新增：

1. W68 第 7 批 commit 落 main。
2. 065 单 head 与迁移位置。
3. 三个历史 hot-fix 真跑。
4. uploader_id 守卫。
5. PR9 endpoint 完整性。
6. PR10 协同 WS。
7. Mobile PWA Push backend。
8. PR11-PR13 增量部署边界。
9. 066 comment ancestors import 与 file_id=1 可调用性。
10. 067 add_reaction import 与 WebSocket payload 合约。
11. 068 should_send import 与 dedup table schema。
12. 069 PostgreSQL recursive function 与 Python fallback。
13. baseline 71 PASS + 7 SKIP 跨四批守恒。

脚本继续兼容 Linux 与 Windows Git Bash：
- 使用 POSIX/Bash 语法；
- Python 自动选择 python3 或 python；
- Docker、curl、Python 缺失时给出可解释 SKIP；
- worktree `.git` 文件指针视为合法仓库；
- DRY_RUN 不触发数据库和 HTTP 副作用。

## 5. 五条新铁律

### 铁律 1：九个 alembic 必须串单链

从 061 到 069 共九个 migration 是一个部署单元。
不能把 066/067/068/069 当作四个无依赖补丁并行升级。
每次合并后都必须验证 `len(get_heads()) == 1`。
唯一 head 只能是 `069_drive_comments_recursive_func`。

### 铁律 2：跨批部署必须跑满 13 段

只验证 `alembic current` 不代表功能可用。
只验证 HTTP 200 也不代表 service import、WS payload、数据库函数和 fallback 可用。
部署完成定义是 §1 至 §13 无 FAIL，而不是挑选其中几个绿色结果。

### 铁律 3：关键路径必须真跑，不能只 mock

066 至少 import `get_comment_ancestors` 并用 file_id=1 验证调用契约。
067 必须 import `add_reaction` 并验证 reaction WS payload 必需字段。
068 必须 import `should_send` 并查询真实 information_schema。
069 必须对 PostgreSQL 执行：

```sql
SELECT * FROM get_comment_ancestors_recursive(1);
```

ID=1 不存在导致空结果是合法的；函数不存在、SQL 错误不是合法结果。
mock 只能辅助，不可替代容器 import、真实 schema 与真实 SQL。

### 铁律 4：部署顺序不可交换

固定顺序：

1. git pull 最新 main；
2. 检查 066/067/068/069 文件和 down_revision；
3. 依次 copy 四个 migration；
4. 清空 alembic `__pycache__`；
5. 验证单 head；
6. alembic upgrade head；
7. 重启 app 与 celery-worker；
8. 验证 DR endpoint、PG function 与 fallback；
9. 跑 13 段脚本；
10. 最后跑 baseline。

不能先 upgrade 再 copy，不能重启前验证新 import，也不能在 baseline 失败时宣布部署完成。

### 铁律 5：baseline 71 PASS + 7 SKIP 必须守恒

新增 migration 和部署验证不能改变既有 baseline 口径。
71 PASS + 7 SKIP 是跨四批部署后的最低守恒值。
PASS 下降说明 stale path、collect error 或真实回归。
SKIP 下降或上升都需要解释，不能只看 0 FAIL。
baseline 必须放在功能真跑之后，作为最终门禁。

## 6. Runbook v3

`docs/w68-7th-batch-deployment-runbook.md` 已扩展为 24 步。
顶部明确四行部署顺序。
SSH 流程新增四个步骤，覆盖 066、067、068、069 与 DR endpoint。
§3 的链图延伸至 069。

部署者需要特别注意：
- 云服务器仍只承担 Nginx + FRP；
- migration 与 Docker 命令在主指挥本地 PC 执行；
- 每次跨 PR copy migration 后清缓存；
- 069 空查询结果不等于失败；
- fallback 必须保留，避免数据库函数不可用时评论 breadcrumb 整体失效。

## 7. 验证证据

本任务提交前执行：

```bash
bash -n scripts/verify_w68_7th_batch_deployment.sh
```

语法检查必须零输出、退出码 0。

还需静态确认：
- 脚本包含 §9、§10、§11、§12、§13；
- runbook 标题为 SSH 部署 24 步；
- runbook 链含 065→066→067→068→069；
- git diff 仅包含指定三个文件；
- 不包含 app、web、alembic production 改动。

## 8. 回滚边界

若 069 失败，先停止发布，不要跳过到多 head 或手工 stamp。
修正 migration 文件并重新 copy、清 cache、验证唯一 head。
若升级成功但 DR endpoint 失败，保留数据库证据并检查 app 镜像是否包含对应 service。
若 baseline 失败，部署不得宣告完成。

数据库 downgrade 必须按反向单链逐步执行。
不要使用 `alembic upgrade heads` 绕开唯一 head 纪律。
不要通过删除 alembic_version 行伪造恢复。

## 9. 结论

W68 第 9 批 D-4 将部署验收从 065 扩展到 069，并把 schema、service import、WS payload、PG recursive function、fallback 与 baseline 汇入同一个 13 段门禁。

0 production code 改动铁律维持。
锚点范式第 118 守恒。
