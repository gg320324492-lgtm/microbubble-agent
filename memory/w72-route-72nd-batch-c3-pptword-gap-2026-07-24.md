# W72 第 72 批 C-3 ppt-word 5 缺口调研沉淀

> 日期：2026-07-24  
> 任务：W72-C-3 纯调研  
> 锚点：锚点范式第 218 守恒  
> 主报告：`docs/w72nd-batch-c3-pptword-gap-survey-2026-07-24.md`

## 任务结论

W72 C-3 完成 `ppt-word-replicated-swing.md` 派生 5 缺口的真验证与 W73/W74 派工规划。
本任务只新增 docs/memory，不修改生产代码。

## 真验证方法

严格执行三步物证链：

1. `git log` 查 feature 相关提交。
2. `git show --stat` 核对候选提交真实文件。
3. `grep/rg` 核对当前 HEAD 中代码仍存在。

同时读取 plan §Status 与 PR2/PR3/PR5/PR7 body，避免只信状态自报。

## 关键发现

派工标签与原 plan 编号存在明显错位：

- 原 plan PR2 是 trash/batch/star/sort，不是 sharing。
- 原 plan PR3 是 KB/Drive upload dual-mode，不是 comment v2。
- 原 plan PR5 是 chunk/resume/quota/thumbnail，不是 trash。
- 原 plan PR7 才是 request/team/audit。

因此未来派工必须给标签重新下定义，不能把编号直接当功能事实。

## 5 缺口真验证状态

### PR2 sharing

派工口径：未实施、8h、P0。
物证：`70a962d50` folder share + member invitation；`954c48c33` team folder。
判定：已有 sharing 基础，属于命名错位，需先列差量缺口再实施。

### PR3 comment v2

派工口径：未实施、6h、P1。
物证：`0bfe36751` 评论 thread；`2f7143a53` 软删与角色权限；另有 reaction/path/breadcrumb。
判定：评论主体已实现，后续应做跨能力 E2E 差量验收。

### PR5 trash

派工口径：部分、4h、P0。
物证：`a19413ffe` 包含 DriveTrashView、trash API/service、批量恢复等。
判定：部分状态合理，后续收口权限、恢复原路径、永久删除、移动端和 E2E。

### PR7 request

派工口径：未实施、12h、P2。
物证：`file_request_service.py`、router、audit middleware、前端列表、`44e063e29` QR。
判定：主体已有，后续验证匿名提交、限制条件、计数、QR、审计、团队盘联动。

### 缺口 5

派工口径：调研基础、2h、P1。
发现：plan 引用的 `docs/drive-v2-roadmap-gap-analysis-2026-07-24.md` 当前 worktree 不存在；任务命令中的无 `analysis` 文件也不存在。
判定：W73 必先恢复或重建权威 gap analysis。

## W73/W74 规划

W73 第 1 批：

- 缺口 5 调研基础。
- PR2 sharing 必先合。
- PR3 comment v2 可与缺口 5 并行开发，合并依赖 PR2。

W74 第 2 批：

- PR5 trash 依赖 PR2 + PR3。
- PR7 request 最终收口，依赖 PR2 + PR3 + PR5。

## 串单链纪律

固定顺序：

1. 缺口 5 + PR2 sharing。
2. PR3 comment v2。
3. PR5 trash。
4. PR7 request。

如产生 migration，派工必须写明 down_revision，按链合并，并在每次合并后验证唯一 head。

## 新铁律

1. 派生新任务必先 `git log + git show + grep` 三步真验证。
2. 必须同时引用 plan §Status 与 plan body，编号错位必须显式说明。
3. 必须执行派工 v6 段 6 实战 #1 串单链守恒。
4. 历史 Status 与旧调研不能代替当前 main 物证。
5. 必须包含 W73/W74 主拍时间表。
6. 权威文档缺失必须报缺，不能伪造已读或用近似文件名替代。

## 守恒说明

- production code：0 修改。
- 历史约束：不动 v1-v7。
- 输出：1 份约 200 行调查报告 + 本 memory。
- 锚点范式：第 218 守恒。
