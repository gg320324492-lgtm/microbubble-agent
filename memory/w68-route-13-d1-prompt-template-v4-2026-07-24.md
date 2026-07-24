# W68 Route 13 D-1：Prompt Template v4

日期：2026-07-24  
范围：仅 docs + memory；0 production code 改动。  
锚点范式：第 168 守恒。

## 交付与背景

本路线新增 `docs/w68-13th-batch-prompt-template-v4.md`，将 W68 第 12 批派工纪要 v3 升级为可直接复用的五段 prompt 模板。v4 针对第 12 批暴露的三类真实错误，把经验变成前置验证和完成门禁：Alembic 070 双头、PowerShell 5.1 参数 binding、plans 状态自报。

## 五条新铁律

1. **Alembic 双头预防**：迁移派工前必须 `git fetch origin main && cd main && alembic heads`；检查 revision 唯一且 `down_revision` 指向最新 head。发现双头必须报主指挥，不得私改；合并后由主指挥 rebase 重命名并串单链，再验证唯一 head。
2. **PS 5.1 binding**：PowerShell 派工器必须使用 `--mode <value>` 空格分隔、`[string]$Mode`，并以 `$Mode -eq 'session'` 严格判断；交付需有两种模式实跑证据。
3. **plans 调研真验证**：派工前对关键字执行 `grep -rn`，不能把 plan status 当事实；发现的 5 个真未实施项写 backlog docs，完成项标 `COMPLETED` 并引用真实 commit。
4. **v1/v2/v3/v4 兼容**：v4 只增加门禁，不破坏旧模板的角色、范围、证据和交接语义；兼容矩阵和升级路径写入文档，便于历史任务和 W71 复用。
5. **W71 派工应用**：W71 新派工默认采用 v4，尤其是 migration、PowerShell 和 plans 审计任务，必须把对应门禁原样写进 prompt 与完成定义。

## W68 第 13 批应用记录

- A-1 plans 派工已应用 §5.3：grep 验证、区分自报/事实、真未实施 backlog。
- B-1 仓库模板已应用 §5.1：空格参数、`[string]`、严格 `-eq`。
- C-1 Alembic renumber 已应用 §5.1：检查 head、由主指挥拍板重编号、串单链。
- W71 留待派工默认应用 v4，不再回退到仅凭 status 或本地单 head 的旧流程。

## 三个错误案例沉淀

### B-1 Alembic 双头

B-1 与 B-2/C-2 三方在 070 附近并行，预检不足导致合并后双头。正确做法是先报主指挥，按合并顺序 rebase、重命名、串链；不能让 agent 自己猜 down_revision。

### B-4 PS 5.1 参数 binding

等号参数、switch 类型或 contains 判断在 Windows PowerShell 5.1 下可能落入错误分支。v4 固定空格参数、`[string]` 和严格 `-eq`，并要求 session/非 session 两条证据。

### A-1 plans 调研自报

仅依据 status 段会把未实施项误判为完成。必须 grep plans 并交叉 git、文件、测试；五个真未实施项必须留下 backlog docs，完成项需真实 commit。

## 验证与交接

本任务应验证两文件存在、关键短语齐全、Markdown diff 无空白错误；不得修改 production code，不 merge。提交信息末尾必须包含：

`Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`

主指挥合并后需确认远端分支、两个文件和单一 migration head（若本批涉及迁移交接）。
