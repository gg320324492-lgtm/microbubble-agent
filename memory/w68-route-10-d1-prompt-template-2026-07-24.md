# W68 Route 10 D-1：Prompt 模板沉淀

日期：2026-07-24

## 1. 交付范围

本任务是 W68 第 10 批 D-1，仅新增两类文档资产：

- `docs/w68-9th-batch-prompt-template.md`：W68 第 9 批 15 agents 的派工 prompt 模板与真实案例；
- 本 memory：记录范式、失败模式和后续执行纪律。

0 production code 改动铁律维持。本提交不修改 `app/`、`web/`、`scripts/`、数据库迁移或部署配置。

## 2. 锚点范式

本任务完成后，锚点范式记为**第 131 守恒**。该数字表示一次可复核的流程约束被沉淀，而不是代码改动数量。守恒条件是：两份文档均进入同一 commit，正文包含真实引用、可执行命令和明确边界，且主指挥可以在 merge 前独立复核。

## 3. 五段结构铁律

以后所有 agent prompt 默认使用五段结构：

1. **背景**：写明 batch、route、真实 commit、文件路径、plan 来源和约束；不接受 agent 假想。
2. **当前分支**：写明完整 branch 与绝对 worktree 路径，要求先核对 status。
3. **任务**：列出步骤、验收标准和真跑测试；失败要记录证据，不静默绕过。
4. **完成定义**：写明预期文件、commit subject、固定 Co-Authored-By、push 目标以及“不 merge”。
5. **不要做的事**：显式声明跨路径、跨任务、生成物、未经批准生产代码等禁区。

五段不是写作风格，而是 agent 执行合同。缺少任何一段，主指挥都无法稳定审计范围或完成状态。

## 4. 五条新铁律

### 铁律一：五段结构固定化

派工 prompt 必须完整包含背景、当前分支、任务、完成定义、不要做的事。任务越小越不能省略边界；小修最容易因“顺手改一下”越界。

### 铁律二：真引用优先于叙述

背景、验收和调研结论必须能回到 `git log`、`git show`、`grep`、测试输出或仓库文档。未经核对的猜测只能作为待验证假设，不能直接成为实施任务。

### 铁律三：失败模式前置写进 prompt

A-1 alembic 双头教训必须在任务开始前暴露：先查既有 head，明确 migration 的 `down_revision` 接哪个 revision，merge 后复查 head。跨 batch 的调研发现也必须写入 docs，不能只留在 memory 或聊天记录。

### 铁律四：五拍板纪律

主指挥按五条纪律选题与验收：

- 查 plans/backlog 后再派工；
- 小修只能来自调研证据；
- 调研发现必须写 docs；
- 跨 session 监控同时查看 agent worktree 与 main 的双 git log；
- 调研 agent 必须执行 grep 等真验证。

这五条把“派工正确性”从个人经验变成可复核流程。

### 铁律五：任务模式 v2 延续

W68 第 4 批拍板的“plans 优先 + 小修搭配”在第 9 批升级为“plans 优先 + 证据小修 + 路线 fallback + 文档闭环”。计划闭环优先消化既有 backlog；小修只能修真实发现；无法实施时用调研或文档 fallback，但不得制造假完成。

## 5. W68 第 9 批三个案例的沉淀

- **C-1 plans 闭环**：用 `git log`、`git show`、`grep` 复核计划状态，不能把计划自报完成当成仓库事实。
- **A-3 cleanup**：删除只能是白名单、dry-run 和 status 证据驱动；疑似重要文件宁可上报，不可猜删。
- **D-5 W69/W70 排期**：预测必须标注为预测，候选事项必须有来源、依赖和触发条件，不能把调研空白写成承诺。

三例共同说明：prompt 的价值在于把来源、范围和证据链前置，而不是增加 agent 的自由发挥空间。

## 6. A-1 alembic 双头复盘

并行 migration 若未写明接续关系，两个 agent 可能都声明相同 `down_revision`，merge 后产生多个 head，部署时 `alembic upgrade head` 直接失败。以后派工顺序固定为：

```bash
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print(s.get_heads())"
```

只有确认既有 head 后才能分配；prompt 写出“接 X”；merge 按链顺序进行；merge 后立即再查一次 `get_heads()`。文档中的失败模式要让下一批 agent 在开始前就能看到，不能等事故后只更新 memory。

## 7. 验收与回报标准

D-1 的最终回报必须包含：

- 两个绝对文件路径；
- 文档结构确认（五段结构、三案例、五纪律）；
- `git diff --check` 结果；
- `git status --short` 结果；
- commit hash 与 push 目标；
- 明确说明没有生产代码 diff。

主指挥 merge 前仍需独立运行 `git diff --name-only <base>...<commit>`，不能仅凭 agent 回报确认范围。

## 8. 后续适用范围

本模板适用于文档、调研、plan 闭环、清理和已批准的小修。涉及生产代码的例外仍需单独拍板，且必须在 prompt 中写明允许修改的路径、测试门禁、回滚方式和依赖链。任何未被授权的扩展都应拆成新任务，不应混入 D-1 类型提交。

## 9. 总结

W68 第 10 批 D-1 的成果是把第 9 批真实经验固化成一份可复制模板和一份跨 session 可检索的 memory。第 131 守恒的关键不在文字篇幅，而在每条结论都有真实引用、每个 agent 都有明确边界、每次失败都能转成下一次派工的前置检查。
