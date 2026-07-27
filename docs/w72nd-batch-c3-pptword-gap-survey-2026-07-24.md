# W72 第 72 批 C-3：ppt-word 5 缺口真验证调研

> 日期：2026-07-24  
> 范围：纯调研与后续派工规划，不修改 `app/`、`web/src/`、`alembic/versions/` 生产代码  
> 依据：`C:/Users/pc/.claude/plans/ppt-word-replicated-swing.md` §Status、派工纪要 v4/v6、W72 起步纪律  
> 锚点：锚点范式第 218 守恒

## 1. TL;DR

W72 C-3 是从 `ppt-word-replicated-swing.md` 的 `PARTIAL_REGRESSION` 状态派生出的新调研任务。
本次没有照抄 Status 自报，而是先执行三步真验证：`git log` 找提交、`git show` 看真实文件、`grep` 查当前代码。
额外核对了 plan body 中 PR2、PR3、PR5、PR7 的目标、依赖、验证项与关键文件。
结论必须区分“原始命名标签”和“当前仓库事实”，因为当前仓库已有同名或近义功能，不能再笼统写成全部未实施。

本任务沿用派工输入给定的五项规划状态表，供 W73/W74 排程使用；同时记录真验证发现的状态漂移：

- PR2 sharing：若指“分享能力总项”，已有 PR7 folder share 与 PR18 team folder；若指原 plan PR2，则实际是 trash/batch/star，已完整落地。后续仅能按 sharing 缺口重新定义后派工。
- PR3 comment v2：原 plan PR3 是 KB/Drive 上传双模，不是评论；评论 thread、软删、reaction、path 已有多批提交。后续应做差量验收，不得从零重做。
- PR5 trash：原 plan PR5 是分片/配额/缩略图；trash 已有 PR2 后端和桌面 UI，但可按“部分”继续做收口验收。
- PR7 request：文件请求后端、前端和 QR 已存在；团队共享盘与 folder share 也存在。后续重点是整体验收、依赖核对和缺失场景，而不是宣称完全未实施。
- 缺口 5：调研基础成立，但引用的 `docs/drive-v2-roadmap-gap-analysis-2026-07-24.md` 在当前 worktree 不存在，必须作为 W73 调研首项补齐或恢复权威来源。

因此，W73/W74 派工前必须再次对当时 main HEAD 执行 `git log + git show + grep`，并把派工目标写成具体未覆盖验收点。

## 2. `ppt-word-replicated-swing.md` 5 缺口真验证

### 2.1 验证方法与证据门槛

本次遵守派工 v4 铁律 3 与派工 v6 段 5 反馈 #4：

1. 读 plan 全文与 §Status，确认原目标和依赖。
2. `git log --oneline main --grep=...` 找候选提交。
3. 对候选提交执行 `git show --stat <hash>`，确认真实文件与实现范围。
4. 在当前 worktree 对 `app/`、`web/src/`、`tests/` 做关键词 grep。
5. 只有 plan、提交、代码三者一致，才能标为完整；否则标 partial、misnamed 或待差量验收。

### 2.2 PR2 sharing 真验证

**Plan body 对照**：原 plan §PR2（约第 116 行）主题是“回收站 + 多选批量 + 收藏星标 + 排序/筛选”，并非 sharing。

**git log 证据**：

- `a19413ffe feat(drive): v2 PR2 收藏星标 + 多选批量 + 排序/筛选 + 回收站路由`
- `70a962d50 feat(drive): v2 PR7 folder share + member invitation (6 场景端到端)`
- `ed3660b31 merge: Agent 2 Drive v2 PR7 folder share ...`
- `954c48c33 merge: ... PR18 团队共享盘 ...`

**git show 证据**：

- `a19413ffe` 实际修改 migration 043、Drive service/API、BatchActionToolbar、DriveTrashView 等，证明原 plan PR2 已落地。
- `70a962d50` 实际新增 folder share model/schema/service/API 与 E2E，证明 sharing 并非空白。
- `954c48c33` 实际新增 team folder 全栈后端、测试和 FolderTree 入口，进一步覆盖团队共享。

**grep 证据**：当前仓库可见 `drive_share_service.py`、team folder 相关实现与 FolderTree 共享入口。

**当前状态**：派工输入表保留“PR2 sharing / 未实施 / 8h / P0”作为后续任务标签，但真验证判定为 **命名错位 + 已有 sharing 基础，待定义差量缺口**。W73 不得按“全新 sharing”重做；必须先列出现有分享链接、文件夹分享、成员邀请、团队共享盘之后仍缺哪些用户场景。

### 2.3 PR3 comment v2 真验证

**Plan body 对照**：原 plan §PR3（约第 160 行）主题是 `KnowledgeUploadDialog` KB/Drive 双模与 Dashboard drive chip，并非 comment v2。

**git log 证据**：

- `0bfe36751 feat(drive): v2 PR9 文件/文件夹 评论 thread`
- `2f7143a53 feat(drive-pr9): 评论软删 + 3 角色权限`
- `596e85450 merge: ... PR9 comment delete`
- `53a2ea40c feat(drive): v2 PR12 emoji reactions`
- `e46781ddf feat(drive-v2-pr11): 评论 path 物化 ... breadcrumb`

**git show 证据**：`0bfe36751` 新增 migration 062、comment API/model/schema/service、文档和 616 行测试，不能认定评论未实施。

**grep 证据**：当前仓库包含 `app/services/drive_comment_service.py`、`app/api/v1/drive_comments.py`、`tests/test_drive_v2_pr9_comments.py` 与评论软删测试。

**当前状态**：派工输入表保留“PR3 comment v2 / 未实施 / 6h / P1”，但真验证判定为 **命名错位 + 评论 v2 主体已实施，待差量验收**。W73 应核对桌面/移动评论 UI、thread、软删、权限、reaction、breadcrumb 的端到端组合，不得复制已有后端。

### 2.4 PR5 trash 真验证

**Plan body 对照**：原 plan §PR5（约第 240 行）主题是分片上传、断点续传、配额与缩略图，并非 trash。

**git log 证据**：

- `a19413ffe feat(drive): v2 PR2 ... 回收站路由`
- `712393789 feat(drive): FolderTree 特殊节点 inline 化 (trash/requests 不离开 /drive)`
- `09dec7568 fix(drive): 删除 DesktopDriveView stale fetchTrash() 调用`
- `196cd9e4a feat(drive): ... 回收站/请求 panel hero header`

**git show 证据**：`a19413ffe` 含 `DriveTrashView.vue`、trash/list/restore/batch API 与 service，证明 trash 主体不是空白。

**grep 证据**：`app/services/drive_service.py` 有 `list_trash`、deleted-only 过滤、restore/永久删除相关逻辑；前端有 DriveTrashView 与 FolderTree special view。

**当前状态**：与任务状态表一致，标为 **部分**。建议 4h 用于核验恢复原路径、永久删除权限、剩余天数、批量恢复、specialView 路由保持、移动端可达性和 E2E，而不是重写 trash。

### 2.5 PR7 request 真验证

**Plan body 对照**：原 plan §PR7（约第 370 行）主题是 File Request + 共享盘 + 审计日志。

**git log 证据**：

- `44e063e29 feat(file-request): QR code 扫码预览`
- `f2c7bd7a9 merge: 代码 TODO 实装 (embedding/paper/file-request/dist)`
- `954c48c33 ... PR18 团队共享盘`
- `70a962d50 ... folder share + member invitation`

**git show 证据**：`44e063e29` 实际修改 FileRequestListPanel/ListView、增加 QR 组件与测试；PR18 提交包含 team folder 全栈实现。

**grep 证据**：

- `app/services/file_request_service.py` 存在并声明 v2 PR7 CRUD + 公开 submit。
- `app/main.py` 注册 file_requests router。
- `app/services/audit_service.py` 与 `app/core/audit_middleware.py` 覆盖 request create/submit/deactivate 审计动作。

**当前状态**：派工输入表保留“未实施 / 12h / P2”，但真验证判定为 **主体已有、完整度待差量验收**。W74 收口应验证匿名提交、token 过期、扩展名限制、上传者姓名、请求列表计数、QR、审计查询、权限与团队共享依赖。

### 2.6 缺口 5 真验证

任务要求核对 Drive v2 roadmap gap analysis 文档。实际执行发现：

- `docs/drive-v2-roadmap-gap-2026-07-24.md` 不存在。
- plan §Status 引用的是 `docs/drive-v2-roadmap-gap-analysis-2026-07-24.md`。
- 当前 worktree 中该 `*-analysis-*` 文件同样不存在。

这意味着“缺口 5”不能直接建立在缺失文档上宣布完成。
其当前状态应为 **调研基础**：先恢复/重建权威 gap analysis，逐项映射 plan body、main commit、现存代码、测试、部署依赖，再给 W73/W74 工程派工提供差量清单。

## 3. 5 缺口当前状态表

下表保留本任务指定的 W72 派工规划口径；“真验证备注”用于防止把错位标签误当仓库事实。

| 缺口 | 状态 | 估时 | 优先级 |
|------|------|------|------|
| PR2 sharing | 未实施 | 8h | P0 |
| PR3 comment v2 | 未实施 | 6h | P1 |
| PR5 trash | 部分 | 4h | P0 |
| PR7 request | 未实施 | 12h | P2 |
| 缺口 5 | 调研基础 | 2h | P1 |

真验证解释：

- “未实施”是派工输入的 gap 标签，不等于仓库完全无代码。
- PR2 sharing 已有 folder share/team folder 基础，派工前需重定义差量。
- PR3 comment v2 已有完整后端链与多轮增强，派工应偏整体验收。
- PR5 trash 确有后端与桌面 UI，使用“部分”最符合证据。
- PR7 request 已有 service/router/frontend/QR/audit 证据，应按缺失场景收口。
- 缺口 5 的 gap analysis 文档缺失，2h 首先用于恢复事实底稿。

## 4. W72 batch 派工建议

### 4.1 每个派生任务的固定前置

每次派工必须在目标分支当时的 main HEAD 上重新执行：

```bash
git log --oneline main --grep='<feature keyword>'
git show --stat <candidate-commit>
rg -n '<feature keyword>' app web/src tests
```

不能复用本报告的 commit 搜索结果作为未来完成证明；main 会继续前进。
每个 worker 的完成汇报必须列候选提交、关键文件、测试证据及尚未覆盖项。

### 4.2 plan body 引用要求

派工 prompt 必须引用 `C:/Users/pc/.claude/plans/ppt-word-replicated-swing.md`：

- §Status：`PARTIAL_REGRESSION` 与分批派工背景。
- §PR2：原始 trash/batch/star/sort 目标。
- §PR3：原始 KB/Drive upload dual-mode 目标。
- §PR5：原始 chunk/resume/quota/thumbnail 目标。
- §PR7：原始 request/team/audit 目标。

如果 W72 标签与 plan section 含义不同，必须在 prompt 中明确“本次标签的定义”，避免编号复用造成误派。

### 4.3 串单链守恒

按派工 v6 段 6 实战 #1：

1. PR2 sharing 必先合并，作为后续共享、权限与空间语义基线。
2. PR3 comment v2 可与缺口 5 调研并行，但合并前必须 rebase 到 PR2 后的 main 并验证接口契约。
3. PR5 trash 依赖 PR2 sharing 与 PR3 comment v2 的权限/操作入口稳定后再收口。
4. PR7 request 最后收口，依赖前三项的分享、评论/审计语义和 trash 生命周期。
5. 若新增 alembic，必须在 prompt 写清 `down_revision`，按链顺序 merge，并在每次 merge 后验证唯一 head。

### 4.4 W73/W74 主拍规划

**W73 第 1 批**：

- 缺口 5 gap analysis 恢复与差量清单（2h，P1）。
- PR2 sharing 差量实现/验收（8h，P0，必先合）。
- PR3 comment v2 差量实现/验收（6h，P1，可与缺口 5 并行开发，按顺序合并）。

**W74 第 2 批**：

- PR5 trash 收口（4h，P0，依赖 PR2 + PR3）。
- PR7 request 收口（12h，P2，最终依赖 PR2 + PR3 + PR5）。

主指挥拍板点：W73 开工前确认 gap 标签的新定义；W73 合并后确认接口与 alembic 唯一 head；W74 开工前确认已有 request/trash 代码不被重复实现；W74 结束后更新 plan §Status 与权威 gap analysis。

### 4.5 0 production code 纪律

本 C-3 任务只新增 docs/memory，0 production code 改动守恒。
W73/W74 若进入实现，必须由主指挥单独批准 Drive v2 例外范围；不得以本调研文档自动授权修改生产代码。

## 5. W72 ppt-word 5 缺口派工顺序表

| Step | 派工内容 | 并行/依赖 | 合并门禁 | 预期批次 |
|------|----------|-----------|----------|----------|
| 1 | 缺口 5 调研 + PR2 sharing | PR2 必先合；缺口 5 可并行 | 三步真验证、sharing 差量定义、必要时 alembic 单 head | W73 第 1 批 |
| 2 | PR3 comment v2 | 可与缺口 5 并行；合并依赖 PR2 | 评论现有能力矩阵、接口回归、重复实现检查 | W73 第 1 批 |
| 3 | PR5 trash | 依赖 PR2 + PR3 | 恢复/永久删除/批量/移动端/E2E 全验收 | W74 第 2 批 |
| 4 | PR7 request | 依赖 PR2 + PR3 + PR5 | 匿名提交/限制/QR/审计/团队盘/生命周期收口 | W74 第 2 批 |

顺序解释：

- Step 1 先把事实底稿和 sharing 权限基线稳定下来。
- Step 2 不阻塞调研，但不能抢在 PR2 前合并。
- Step 3 处理删除生命周期，必须建立在分享和评论权限已稳定的基础上。
- Step 4 涉及公开提交、团队空间与审计，横切面最大，最后收口最安全。
- 任何阶段若三步真验证显示目标已完整，应把任务改为验证/文档闭环，不为凑派工制造重复代码。

## 6. W72 ppt-word 5 缺口调研沉淀新铁律

### 铁律 1：派生新任务必须三步并行真验证

必先 `git log + git show + grep`。
`git log` 只说明提交标题存在，`git show` 才能确认真实文件，`grep` 才能确认代码仍在当前 HEAD。
三者缺一不可，沿用派工 v4 铁律 3。

### 铁律 2：必须引用 plan body 与 §Status

Status 提供审计结论，plan body 提供原始目标、依赖和验收。
本次发现“PR2 sharing / PR3 comment v2 / PR5 trash”与原 plan 编号含义错位，证明只读标签会误派。
未来 prompt 必须明确 section 与派生标签的映射。

### 铁律 3：必须执行派工 v6 段 6 实战 #1 串单链守恒

PR2 必先合，PR3 可并行开发但后合，PR5 依赖 PR2+PR3，PR7 最终收口。
涉及 migration 时必须显式指定 down_revision、按链 merge、每次验证唯一 head。

### 铁律 4：派生新任务不能把历史自报当完成度

派工 v6 段 5 反馈 #4 要求新任务重新验证，而不是继承旧调查结论。
本次已证明 plan §Status 的概括、派工标签和当前 main 代码存在时间差与命名错位。
必须以当前 main 的物证为准，保留差异说明。

### 铁律 5：必须有 W73/W74 主拍时间表

W72 只提供调研基础，不自动批准实现。
W73 第 1 批主拍缺口 5 + PR2 + PR3；W74 第 2 批主拍 PR5 + PR7。
每批开工前、合并中、收口后均需主指挥确认依赖、例外范围、单链和 Status 更新。

### 铁律 6：缺失的权威文档必须显式报缺

`docs/drive-v2-roadmap-gap-analysis-2026-07-24.md` 在当前 worktree 不存在。
不得伪造已读内容，也不得用相似文件名代替。
W73 缺口 5 必先恢复或重建权威差量清单，再据此修改实施排程。

## 收口结论

本报告完成 6 段要求、5 缺口状态表、W73/W74 两批规划与四步串单链顺序。
最大真验证发现不是“5 项都没有代码”，而是任务标签与 plan 编号错位，且 sharing/comment/trash/request 已有不同程度实现。
因此后续派工的正确粒度是“差量验收 + 缺项补齐”，不是从零重做。
本任务保持纯 docs/memory 范畴，锚点范式第 218 守恒。
