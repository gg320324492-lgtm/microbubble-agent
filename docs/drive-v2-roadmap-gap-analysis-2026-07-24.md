# Drive v2 路线图 Gap Analysis（权威底稿 · W72 第 2 批 D-1 恢复版）

> **日期**：2026-07-24（原始调研日）/ 2026-07-27（W72 第 2 批 D-1 恢复日）
> **任务**：W72 第 2 批 D-1 缺口 5 gap analysis 恢复
> **依据**：W72 第 1 批 C-3 commit `f1947d3c7` §2.6 真验证（文档缺失）+ `ppt-word-replicated-swing.md` §缺口 5 引用
> **范围**：纯 docs（**0 production code 改动** — 不动 `app/`、`web/src/`、`alembic/versions/`）
> **锚点范式**：W72 第 1 批 220 → W72 第 2 批 D-1 233 守恒（+13）
> **基线**：`main` HEAD `2db1db600`
> **分支**：`docs/w72-2nd-batch-d1-drive-v2-roadmap-gap-2026-07-27`

---

## §0 恢复背景与文档缺失真根因（W72 第 1 批 C-3 §2.6 派生）

### 0.1 C-3 报缺原文

W72 第 1 批 C-3（commit `f1947d3c7`）§2.6 执行真验证后显式报缺：

- `docs/drive-v2-roadmap-gap-2026-07-24.md` 不存在
- plan §Status 引用的 `docs/drive-v2-roadmap-gap-analysis-2026-07-24.md` 在当前 worktree 同样不存在
- 因此「缺口 5」不能建立在缺失文档上宣布完成，其状态应为**调研基础**

C-3 铁律 6 明确：**缺失的权威文档必须显式报缺**，不得伪造已读内容，也不得用相似文件名代替。本 D-1 任务即为该报缺项的收口。

### 0.2 D-1 真验证：文档不是"丢失"，而是"从未合并"

本任务先复核缺失事实，再定位真根因：

```bash
ls docs/drive-v2-roadmap*                                    # → No such file or directory
git log --all --oneline | grep -iE "drive.*roadmap|gap.*analysis"
#   8a3dde4f1 docs: Drive v2 路线图 Gap Analysis（长期调研, W68 第 11 批 B-3）
git branch -a --contains 8a3dde4f1
#   + docs/drive-v2-roadmap-gap-2026-07-24
#     remotes/origin/docs/drive-v2-roadmap-gap-2026-07-24
```

**真根因（本任务新发现，C-3 未定位）**：

原始 gap analysis 由 **W68 第 11 批 B-3** 于 2026-07-24 16:57 写成（commit `8a3dde4f1`，410 行，8 段结构），但该 commit **只存在于分支 `docs/drive-v2-roadmap-gap-2026-07-24`（本地 + origin 双在），从未 merge 进 main**。

因此：

- ❌ 不是文件被 refactor 意外删除（对比 `15-17-18-cozy-bengio` Part 2 在 `4b215220` 被删的事故模式）
- ❌ 不是 git 历史丢失
- ✅ 是**分支未合并** — plan §Status 提前引用了尚未落 main 的文档路径，形成"引用悬空"

**沉淀纪律（新）**：plan §Status 引用 `docs/` 路径时，必须确认该路径已在 **main** 上（`git ls-tree main -- <path>`），不能引用仅存在于 agent 分支的文件。否则后续批次真验证必然报缺，浪费一轮调研工时。

### 0.3 本恢复版与原始 `8a3dde4f1` 的关系

| 维度 | 原始 `8a3dde4f1`（W68 第 11 批 B-3） | 本恢复版（W72 第 2 批 D-1） |
|---|---|---|
| 结构 | 8 段（现状/已实施/部分/未实施/W69-W71 派工/8 铁律/锚点 138/总结） | 5 段（总图/4 列状态表/W73-W74 派工/锚点预期/风险缓解）+ §0 恢复背景 |
| 基线 | main HEAD `7b6f0305e` | main HEAD `2db1db600` |
| 口径 | PR1-PR8 覆盖度盘点（7/8 完整） | PR1-PR18 + 商业化 + Mobile + qa-bench 全景派工底稿 |
| 用途 | 回答"plan 到底做了多少" | 回答"W73/W74 派哪些工、按什么顺序" |

原始版结论（**7/8 PR 完整 + 后端 8/8 完整，实际覆盖度远高于 W66 自报的 30-40%**）在本版 §1 中予以继承并按 `2db1db600` 重新验证。本版不推翻原始版，而是把口径从 PR1-PR8 扩展到 PR1-PR18 + 商业化路线。

---

## §1 Drive v2 路线总图

### 1.1 PR1-PR18 已实施清单（commit 引用）

以下清单继承原始 `8a3dde4f1` §1.2 + §2 的三验证结论（`git log` + `git show` + `grep`），并叠加 W68 第 12-14 批 / W71 / W72 的增量。

| PR | 主题 | 状态 | 主要 commit | alembic |
|---|---|---|---|---|
| **PR1** | 桌面 stub 修复 + ShareDialog | ✅ 完整 | `5bd887993`（12 文件 / 1406 行 / 7 e2e group PASS） | 042 |
| **PR2** | 回收站 + 多选批量 + 星标 + 排序筛选 | ✅ 完整 | `a19413ffe`（Drive service/API + BatchActionToolbar + DriveTrashView） | 043 |
| **PR3** | KB/Drive 双模上传 + Dashboard chip | ✅ 完整 | `b3dba3499`（28/28 e2e PASS） | — |
| **PR4** | 文件秒传 + 版本历史 | ✅ 完整 | `60b81bccc`（26/26 e2e PASS） | — |
| **PR5** | 分片上传 + 断点续传 + 配额 + 缩略图 | 🟡 后端完整 / 前端部分 | `5a63e9fd2` chunked + `7d0daadfb` rate-limit | 045 |
| **PR6 旧** | 通知 + @ + 活动流 + 评论 | ❌ 部分废弃（W66 用户决策"活动流删去"） | 表建于 047，`/activities` 端点 2026-07-03 删除 | 047 |
| **PR6 新** | 评论 thread / 版本 / WS push / 协同 / path / reactions | ✅ 完整（8 子 PR） | `0bfe36751` 评论 + `04e06f6fd` 版本 + `0d511ddcb` 协同 + `2bd208489` WS + `e6f240911` mention + `e46781ddf` path + `53a2ea40c` reactions + `1e5f93938` combined + `abf3f1132` fallback | 062-069 串单链 |
| **PR7** | 文件请求 + 审计日志 + 团队共享盘 | ✅ 主体完整 | `70a962d50` folder share + member invitation + `44e063e29` QR 扫码 + `f2c7bd7a9` TODO 实装 | 048 |
| **PR8** | 独立 MobileDriveView + TabBar | 🟡 后端完整 / 前端 90% | `c82f588da` MobileDriveView + `022225d09` 预览滑动 + `fdf33b2a7` preview 端点 + `8be9f3470` file-level lock | — |
| **PR9** | 评论软删 + 3 角色权限 | ✅ 完整 | `2f7143a53` + merge `596e85450` | 074 |
| **PR12** | Emoji reactions | ✅ 完整 | `53a2ea40c`（12 emoji 白名单 + 3 端点） | 067 |
| **PR13** | 合并通知（mention + reaction 去重） | ✅ 完整 | `1e5f93938`（notification_dedup） | 068 |
| **PR14** | 评论 path 自动重建 | ✅ 完整 | `abf3f1132`（recursive CTE + 错误码白名单） | 069 |
| **PR15** | 版本 tags | ✅ 完整 | W68 第 12 批 | 075 |
| **PR16** | 回收站版本清理 | ✅ 完整 | W68 第 13 批 | 076 → path_backfill |
| **PR17** | 文件秒传（dedupe + audit） | ✅ 完整 | W68 第 14 批 B-1 | **078** |
| **PR18** | 团队共享盘 | ✅ 完整 | `954c48c33`（team folder 全栈 + FolderTree 入口） | **079** |
| **PR5-新** | 分片上传收口 | 🟡 主体已实施 / migration 缺 | W68 第 14 批 B-3 派工 | **080 缺失** ⚠️ |

**当前 main（`2db1db600`）代码物证**（本任务 `grep` 实测）：

```
app/services/drive_share_service.py        ✅ 存在
app/services/drive_comment_service.py      ✅ 存在
app/services/file_request_service.py       ✅ 存在
app/api/v1/file_requests.py                ✅ 存在
app/main.py:110  (file_requests.router, {"prefix": "/api/v1"})   ✅ 已注册
app/services/drive_service.py              ✅ list_trash / deleted_at 相关 40 处命中
app/services/drive_service.py:236          ✅ is_team_shared_filter 实装
web/src/views/desktop/DriveTrashView.vue   ✅ 存在
web/src/components/drive/DriveTrashPanel.vue ✅ 存在
web/src/views/mobile/MobileDriveView.vue   ✅ 存在
web/src/views/mobile/*DriveTrash*          ❌ 不存在（仅 MobileTaskTrash.vue）
```

### 1.2 alembic 链真验证（⚠️ 2 项状态漂移，本任务新发现）

```bash
ls alembic/versions/ | sort | tail -12
#   ... 074 075 076 078_drive_dedupe_audit 079_team_folders
```

| 发现 | 事实 | 影响 |
|---|---|---|
| **077 缺号** | `077_*` 文件不存在 | 编号跳空，非链断（无 revision 引用 077） |
| **080 缺失** | `080_*` 文件不存在 | ✅ 与派工输入「PR5 trash 收口 + 080 migration 缺」一致 |
| **078/079 编号与链序倒挂** | `079.down_revision = 076_drive_comments_path_backfill`；`078.down_revision = 079_team_folders` | 链序实为 `076 → 079 → 078`，**文件名数字顺序与迁移拓扑顺序相反** |
| **单 head 守恒** | `get_heads() → ['078_drive_dedupe_audit']`，COUNT = 1 | ✅ **0 双头**，部署不阻塞 |

单 head 验证命令（CLAUDE.md §alembic 串单链纪律 铁律 3）：

```bash
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; \
c=Config(); c.set_main_option('script_location','alembic'); \
s=ScriptDirectory.from_config(c); print(s.get_heads())"
# → ['078_drive_dedupe_audit']   ✅ 1 个 head
```

**结论**：链健康（单 head），但 **078/079 编号倒挂**是后续新增 080 的高风险点 — 若 W73 agent 按"文件名最大即链尾"的直觉把 080 接到 `079_team_folders`，将与既有 `078.down_revision = 079` 冲突形成**双头**。**080 必须接 `078_drive_dedupe_audit`（真链尾），不是 079。** 此项须写入派工 prompt（见 §5.1）。

### 1.3 商业化 24 人月 Q1 起点

- **依据**：W72 第 1 批 C-2 commit `a78967661`「W72 商业化 24 人月季度排期更新（Phase 8/2/3/4 + W73-W90 主拍拍板时间表）」
- **总量**：24 人月，Q1 为起点季度
- **Phase 8**（商业化起步）：**真未实施**，估 24h，P0 — W72 第 2 批 B-5 派工目标
- **拍板时间表**：W73-W90 主拍，逐批推进；本 gap analysis 只提供 W73/W74 两批粒度（§3），W75+ 由 C-2 排期文档主拍

### 1.4 W72 第 2 批 5 缺口收口状态

| 缺口 | C-3 原始标签 | D-1 真验证判定 | 收口口径 |
|---|---|---|---|
| PR2 sharing | 未实施 / 8h / P0 | **命名错位 + 已有 sharing 基础** | 差量定义后派工，不重做 |
| PR3 comment v2 | 未实施 / 6h / P1 | **命名错位 + 主体已实施** | 差量验收，不复制后端 |
| PR5 trash | 部分 / 4h / P0 | **部分（证据一致）** | 收口验收 + 080 migration |
| PR7 request | 未实施 / 12h / P2 | **主体已有，完整度待验收** | 缺项补齐，非从零 |
| 缺口 5 gap analysis | 调研基础 / 2h / P1 | **文档缺失 → 本任务恢复** | ✅ 本 commit 收口 |

**C-3 最大真验证发现（本版继承）**：不是"5 项都没有代码"，而是**任务标签与 plan 编号错位**，且 sharing / comment / trash / request 已有不同程度实现。因此后续派工的正确粒度是**差量验收 + 缺项补齐**，不是从零重做。

---

## §2 4 列状态表（现状 / 估时 / 优先级 / 派工建议）

> **口径说明**：本表「现状」列以 main HEAD `2db1db600` 的 `git log + git show + grep` 三验证物证为准，不照抄 plan §Status 自报。估时/优先级沿用派工输入口径。

| 缺口 | 现状 | 估时 | 优先级 | 派工建议 |
|---|---|---|---|---|
| **PR2 sharing 差量** | 已有 folder share（`70a962d50`）+ team folder（`954c48c33`，alembic 079）+ `drive_share_service.py` + ShareDialog + 成员邀请。**命名错位**：原 plan PR2 实为 trash/batch/star，已完整落地 | 8h | **P0** | **B-1 派工**。必先合，作为共享/权限/空间语义基线。开工前须先列"现有 4 类分享（分享链接 / 文件夹分享 / 成员邀请 / 团队共享盘）之后仍缺哪些用户场景"，禁止按"全新 sharing"重做 |
| **PR3 comment v2 验收** | thread（`0bfe36751`，062）/ 软删（`2f7143a53`，074）/ reaction（`53a2ea40c`，067）/ path（`e46781ddf` + `abf3f1132`）已跨多批实施；`drive_comment_service.py` + `drive_comments.py` + `test_drive_v2_pr9_comments.py` 均在 | 6h | **P1** | **B-2 派工**。可与 D-1 并行开发，但合并须 rebase 到 PR2 后的 main 并验接口契约。范围限"桌面/移动评论 UI × thread × 软删 × 权限 × reaction × breadcrumb"端到端组合验收 |
| **PR5 trash 收口 + 080** | 后端 `drive_service.py` 40 处 `list_trash`/`deleted_at` 命中；桌面 `DriveTrashView.vue` + `DriveTrashPanel.vue` 在；**⚠️ 移动端 drive 回收站不存在**（仅 `MobileTaskTrash.vue`）；**⚠️ alembic 080 缺失** | 6.5h | **P0** | **B-3 派工**。依赖 PR2 + PR3 权限入口稳定。验收：恢复原路径 / 永久删除权限 / 剩余天数 / 批量恢复 / specialView 路由保持 / **移动端可达性（真缺口）** / E2E。**080 必须接 `078_drive_dedupe_audit`**（§1.2 倒挂风险） |
| **PR7 file_request API** | ⚠️ **派工输入称"router 未接"，真验证不成立** — `app/main.py:110` 已注册 `(file_requests.router, {"prefix": "/api/v1"})`；service + QR（`44e063e29`）+ `audit_service.py` + `audit_middleware.py` 均在 | 12h | **P2** | **B-4 派工**。最后收口，依赖 PR2+PR3+PR5。**派工 prompt 须修正前提**（router 已接）。验收：匿名提交 / token 过期 / 扩展名限制 / 上传者姓名 / 请求列表计数 / QR / 审计查询 / 权限 / 团队共享盘依赖 |
| **缺口 5 gap analysis 文档** | **缺失** — 原始 `8a3dde4f1` 仅在未合并分支 `docs/drive-v2-roadmap-gap-2026-07-24`（§0.2 真根因） | 2h | **P1** | **D-1 派工（本任务）** ✅ 已收口。产物即本文件，作为 W73/W74 派工权威底稿 |
| **商业化 Phase 8 起步** | **真未实施**。依据 W72 C-2 `a78967661` 24 人月季度排期，Phase 8 为 Q1 起点 | 24h | **P0** | **B-5 派工**。多租户数据隔离为最大风险（§5.2），须先出隔离方案再动代码。计费网关只预留接口，不接真支付（§5.4） |
| **Mobile v3.4 商业化暗色** | **真未实施**。已有 `mobile-dark-overrides.css` + W72 B-5 桌面 6 主题 dark（`b7ad730a6`，18 视觉快照）可复用范式 | 16h | **P1** | **C-3 派工**。必须跨组件透传（路由级双栈 + EP/NutUI 边界 + **非 scoped token** + 系统 light/dark 切换 + 持久化）。单页面截图不构成通过（§5.3） |
| **qa-bench D9 调研** | D8 已实施（W68 第 14 批 C-1 七项实施前置）；D9 为**纯调研** | 4h | **P2** | **C-2 派工**。调研完成 ≠ 生产实施。须含商业化 7 维评分改造前置 + 240 题灰度可行性 |

**合计估时**：8 + 6 + 6.5 + 12 + 2 + 24 + 16 + 4 = **78.5h**（≈ 2 人周），跨 W73 + W74 两批消化。

### 2.1 状态漂移汇总（派工输入 vs D-1 真验证）

| # | 派工输入表述 | D-1 真验证 | 处置 |
|---|---|---|---|
| 1 | PR7「service 已有 router 未接」 | ❌ **不成立** — `app/main.py:110` 已注册 | B-4 prompt 必须改前提，否则会重复注册 router |
| 2 | PR5「080 migration 缺」 | ✅ **成立** — `080_*` 不存在 | B-3 保留，但须补 078/079 倒挂警示 |
| 3 | PR5 估时 4h（C-3）vs 6.5h（本表） | 本表取 6.5h — C-3 的 4h 未计入移动端缺口 + 080 migration | 采用 6.5h |
| 4 | PR2 / PR3「未实施」 | ❌ **标签错位** — 均有实质代码 | 改「差量验收」口径，禁止从零重做 |

**纪律（继承 C-3 铁律 1/4）**：「未实施」是派工输入的 gap 标签，**不等于仓库完全无代码**。每个 W73/W74 worker 开工前必须在**当时的 main HEAD** 重跑三步真验证，不得复用本报告的 commit 搜索结果作为完成证明（main 会继续前进）。

---

## §3 W73 / W74 派工顺序表

### 3.1 W73 优先（第 1 批）

| Step | 派工内容 | agent | 并行/依赖 | 合并门禁 |
|---|---|---|---|---|
| 1 | 商业化 Phase 8 收口（24h，P0） | B-5 | 独立起步，可与 2/3 并行 | 多租户隔离方案先行评审 + 计费仅预留接口 |
| 2 | PR2 sharing 差量（8h，P0） | B-1 | **必先合**（Drive 侧基线） | sharing 差量定义书 + 现有 4 类分享矩阵 + 必要时 alembic 单 head |
| 3 | PR3 comment v2 差量验收（6h，P1） | B-2 | 可与 1/2 并行开发；**合并须在 PR2 后** | 评论能力矩阵 + 接口回归 + 重复实现检查 |
| 4 | 4 类 hot-fix 监控 | — | 独立 | commit message 含 `hotfix` 标识 + root cause/修复/验证 3 段（CLAUDE.md §2.4） |
| 5 | 7 维评分商业化改造 | C-2 前置 | 依赖 1 的 Phase 8 语义 | qa-bench D9 调研结论支撑 |
| 6 | 6 主题 dark mode 推广到 Admin 页面 | C-3 前置 | 可与 1-3 并行 | 复用 B-5 `b7ad730a6` 18 视觉快照范式 |
| 7 | 声纹 + ASR + TTS 链 W73 调研启动 | 调研 | 独立 | 纯调研，0 production code |

**W73 主拍点**：开工前确认 gap 标签的**新定义**（§2.1 4 项漂移）；合并后确认接口契约 + alembic 唯一 head。

### 3.2 W74 优先（第 2 批）

| Step | 派工内容 | agent | 并行/依赖 | 合并门禁 |
|---|---|---|---|---|
| 1 | PR5 trash 收口 + alembic 080（6.5h，P0） | B-3 | 依赖 W73 PR2 + PR3 | 恢复/永久删除/批量/**移动端可达性**/E2E 全验收 + **080 接 078** |
| 2 | PR7 request 收口（12h，P2） | B-4 | 依赖 PR2 + PR3 + PR5（横切面最大，最后收口） | 匿名提交/token 过期/扩展名/QR/审计/团队盘/生命周期 |
| 3 | 240 题灰度 | qa-bench | 依赖 W73 D9 调研 | 灰度比例 + baseline 对照 + 失败重跑策略 |
| 4 | 多租户实战 | 商业化 | 依赖 W73 Phase 8 | 数据隔离真实压测（§5.2） |
| 5 | 计费网关真支付接入 | 商业化 | 依赖 4 | **须主指挥单独拍板**；W73 仅预留接口（§5.4） |
| 6 | Mobile v3.4 商业化暗色（16h，P1） | C-3 | 依赖 W73 Step 6 Admin 推广 | 跨组件透传 5 项全验（§5.3），单页面截图不算通过 |

**W74 主拍点**：开工前确认已有 request/trash 代码**不被重复实现**；收口后更新 plan §Status + 本 gap analysis。

### 3.3 串单链守恒顺序解释（继承 C-3 铁律 3）

```
PR2 sharing  ──必先合──►  PR3 comment v2  ──►  PR5 trash  ──►  PR7 request
   (W73)                      (W73, 后合)         (W74)           (W74, 最后)
```

- **Step 1** 先把事实底稿（本文件）与 sharing 权限基线稳定下来
- **Step 2** 不阻塞调研，但**不能抢在 PR2 前合并**
- **Step 3** 处理删除生命周期，必须建立在分享 + 评论权限已稳定的基础上
- **Step 4** 涉及公开提交、团队空间与审计，横切面最大，最后收口最安全
- **任何阶段**若三步真验证显示目标已完整，应把任务改为**验证/文档闭环**，不为凑派工制造重复代码

---

## §4 锚点范式守恒预期

### 4.1 当前批次

| 项 | 值 | 性质 |
|---|---|---|
| W72 第 1 批 | **220** | 守恒预期（D-2 `02b7b4dcb` + D-3 `41fe8f0f9` 口径） |
| W72 第 2 批 D-1（本任务） | **233** | 单 agent 锚点（+13） |
| W72 第 2 批批级收束 | **230** | 批级聚合守恒目标 |

> ⚠️ **数字口径说明**：派工输入同时给出「D-1 233」（agent 级）与「W72 第 2 批 220 → 230」（批级）两个口径，二者不自洽（233 > 230）。本文件**如实并列**两者，不做静默调和。**最终实际值须由 W72 第 2 批 A-1 主拍在全部 agent 合并后按 4 维度金标准（W71 D-3 `0c9d33ec0` 沉淀）实测收束**，本文件的 233 / 230 均为**预测值**，非实际值。此处遵守 CLAUDE.md §"Status 段必真验证"与「预测值明示」纪律（W68 第 11 批 D-2 铁律 3）。

### 4.2 W73 / W74 预期

| 批次 | 锚点范式 | 增量 | 驱动 |
|---|---|---|---|
| W72 第 2 批 | 220 → **230** | +10 | 5 缺口收口 + 商业化 + Mobile + qa-bench |
| **W73** | 230 → **240** | **+10** | 商业化 B-5 收口 + PR2/PR3 差量 + hot-fix 监控 + 7 维评分改造 + Admin dark + 声纹调研 |
| **W74** | 240 → **248** | **+8** | PR5 trash + 080 + PR7 request + 240 题灰度 + 多租户实战 + Mobile v3.4 |

**单调上升链完整轨迹**：

```
W7 12 → W66 27 → W67 28 → W68 30 → W68-3 42 → W68-4 57 → W68-5 72 → W68-6 88
→ W68-7 89 → W68-8 102 → W68-9 116 → W68-10 134 → W68-11 144 → W68-12 156
→ W68-13 168 → W68-14 175 → W71 206 → W72-1 220 → W72-2 230 → W73 240 → W74 248
```

### 4.3 0 production code 改动铁律守恒预期

| 批次 | 守恒比 | 例外清单 |
|---|---|---|
| W72 第 1 批 | 14/15 | B-1 NavRail + B-2 ThinkingModeSwitch/Breadcrumb + B-3/B-4/B-5 ChatViewSSE（web 例外已批） |
| **W72 第 2 批** | **14/15 预期** | 待 A-1 主拍拍板；D-1（本任务）**纯 docs，0 production code 守恒** ✅ |
| **W73 预期** | **持续 14/15** | B-5 商业化 Phase 8（新模块，不动老路径）+ B-1/B-2 Drive 差量 + C-3 Admin dark（web） |
| **W74 预期** | **持续 14/15** | B-3 alembic 080 + B-4 PR7 收口 + C-3 Mobile v3.4（web） |

**例外边界（CLAUDE.md §3 增补）**：Drive v2 / 商业化 / Mobile / qa-bench 均属**新业务模块**，算已批例外；但**例外不扩大到老路径重构** — 禁止改 `task_service.py` / `meeting_service.py` / `knowledge_service.py` 核心函数、`web/src/views/Desktop*/index.vue` 老桌面页、老 alembic 的 `down_revision`、`app/core/security.py`、`app/agent/chat_engine.py`（方案 C 6 铁律相关）。

---

## §5 风险与缓解

### 5.1 alembic 链 7 串单链风险 ⚠️ **本批最高风险**

**风险**：

1. **078/079 编号倒挂**（§1.2 实测）— 真链序 `076 → 079 → 078`，文件名数字顺序与拓扑顺序**相反**。W73/W74 agent 若按"文件名最大即链尾"直觉把 080 接到 `079_team_folders`，将与既有 `078.down_revision = 079` **冲突形成双头** → `alembic upgrade head` 报 `Multiple head revisions are present` 直接阻塞部署
2. **077 缺号** — 编号跳空，易被误认为链断（实际无 revision 引用 077，链完整）
3. **W74 并行派工** — B-3（080）若与其他写 migration 的 agent 并行，重演 W68 第 3 批 F-1/F-2 双头事故（`1852468a6`）

**缓解**（CLAUDE.md §alembic 串单链纪律 5 铁律 + 本批增补）：

- ✅ **080 的 `down_revision` 必须 = `"078_drive_dedupe_audit"`**（真链尾），**不是 079** — 此句须逐字写入 B-3 派工 prompt
- ✅ 并行派 migration agent 必须在 prompt 明确 `down_revision` 接续关系，不写即默认接最新 → 必双头
- ✅ merge 顺序按 alembic 链，先上游后下游，不并行 merge
- ✅ **每次 merge 后立即 verify 单 head**：
  ```bash
  python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; \
  c=Config(); c.set_main_option('script_location','alembic'); \
  s=ScriptDirectory.from_config(c); print(s.get_heads())"
  # 期望输出恰好 1 个元素
  ```
- ✅ 部署文档**第 0 节**必含 alembic 链风险段（参考 `docs/drive-v2-pr9-deployment.md`）
- ✅ 跨 PR 部署必 `docker cp` + **清 `__pycache__`**（否则老 `down_revision` 继续生效 → 双头假修复）：
  ```bash
  docker cp alembic/versions/080_*.py microbubble-agent-app-1:/app/alembic/versions/
  docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
  docker exec microbubble-agent-app-1 alembic upgrade head
  ```
- 🔧 **建议 W73 顺带修编号倒挂**：把 078/079 重命名为拓扑一致的编号（参考 W68 第 11 批 C-1 alembic rebase 例外已批模式），但**须主指挥单独拍板** — 重命名已 merge 的 migration 属高危操作，若生产库已 stamp 则不可动

### 5.2 商业化多租户数据隔离

**风险**：

- Phase 8（24h，P0）引入租户维度，**所有既有查询若漏 `tenant_id` 过滤即成跨租户数据泄漏** — 比 CLAUDE.md 已记录的「跨用户 ID 撞车」（`chat-history-append-message-404-cross-user-collision-2026-07-15`）严重一个量级
- Drive 侧 `is_team_shared` + folder share + PR18 team folder 已有三层共享语义，叠加租户维度后**权限矩阵组合爆炸**
- 老路径（task / meeting / knowledge）未租户化，混合期存在"半隔离"窗口

**缓解**：

- ✅ 复用 CLAUDE.md 铁律 8：**所有查询强制 `WHERE tenant_id = current.tenant_id`**，service 函数签名前置 `tenant_id` 参数（与 `user_id` 同级强制），不靠调用方自觉
- ✅ **先出隔离方案再动代码** — W73 B-5 开工前须交付隔离设计评审（表级 vs 行级 vs schema 级），主指挥拍板后才实施
- ✅ 越权单测必须覆盖：跨租户读 / 写 / 删 / 共享链接跨租户访问 / 团队盘跨租户邀请 — 每项独立 test case
- ✅ 混合期用 feature flag 隔离新旧路径（CLAUDE.md 方案 C 铁律 6：**保留老路径代码，不 git revert**）
- ✅ 商业化属**新模块例外**，禁止顺手重构老 service 核心函数（§4.3 边界）

### 5.3 移动端跨组件 dark mode

**风险**：

- Mobile v3.4（16h，P1）+ W73 Admin 推广，历史上 dark mode 跨组件已在 **CLAUDE.md v60-v67 第 5 次强化**仍反复回归
- 根因固定：**scoped 样式块内写 dark 覆盖 → 子组件不生效**；EP（桌面）/ NutUI（移动）**双组件库边界**处 token 断裂
- 路由级双栈架构下，同一 URL 桌面/移动**不同组件树**，桌面通过 ≠ 移动通过

**缓解**：

- ✅ **dark mode 覆盖必须写在非 scoped 块**（CLAUDE.md 铁律 13，第 6 次强化）
- ✅ 5 项全验，缺一不算通过：① 路由级双栈 ② EP/NutUI 边界 ③ 非 scoped token ④ 系统 light/dark 切换 ⑤ 持久化
- ✅ **单页面截图不构成通过**（W68 第 14 批 C-2 沉淀）— 须跨组件透传验证
- ✅ 复用 W72 B-5 `b7ad730a6` 范式：**6 主题 × 3 viewport = 18 视觉快照** Playwright 回归，Mobile v3.4 同规格
- ✅ 复用既有 `web/src/assets/mobile-dark-overrides.css`，不新建平行覆盖文件（避免双份 token 漂移）

### 5.4 计费网关真支付接口预留

**风险**：

- W74 Step 5「计费网关真支付接入」是**唯一触碰真实资金流**的任务，事故不可回滚（与代码 bug 性质不同）
- 支付回调是**外部不可信输入** → 幂等 + 验签缺失即导致重复扣费 / 伪造订单
- W73 若把"预留接口"做成"半接通"，存在误触发真实扣费风险

**缓解**：

- ✅ **W73 只预留接口，绝不接真支付** — 接口层返回 mock，配置项默认 `BILLING_GATEWAY_ENABLED = False`
- ✅ W74 真支付接入**须主指挥单独拍板**，不由本 gap analysis 自动授权（继承 C-3 铁律 5：调研文档不自动授权生产改动）
- ✅ 回调必须：**幂等键**（复用 CLAUDE.md 铁律 9 `client_msg_id` 模式）+ **验签** + 金额二次校验 + 全量审计落库（复用既有 `audit_service.py` + `audit_middleware.py`）
- ✅ 沙箱环境先行全链路，生产灰度从**单租户 + 金额上限**起
- ✅ 失败必须 fail loud（复用 CLAUDE.md nginx mime 注入教训）— 支付链路**禁止 best-effort 静默吞异常**（与铁律 5「持久化失败 best-effort」相反：**资金流必须显式失败**）

---

## 收口结论

本文件完成 W72 第 1 批 C-3 §2.6 报缺项的收口，恢复 `docs/drive-v2-roadmap-gap-analysis-2026-07-24.md` 为 **main 上的权威底稿**。

**5 段全覆盖**：§1 Drive v2 路线总图（PR1-PR18 + 商业化 24 人月 + 5 缺口状态）+ §2 8 行 4 列状态表 + §3 W73/W74 派工顺序表 + §4 锚点范式守恒预期 + §5 4 类风险与缓解。

**3 项真验证新发现**（C-3 未定位，本任务补齐）：

1. **文档缺失真根因 = 分支从未合并**（`8a3dde4f1` 仅在 `docs/drive-v2-roadmap-gap-2026-07-24`），非 refactor 删除 → 沉淀「plan §Status 引用 docs 路径前必须确认已在 main」纪律
2. **PR7「router 未接」前提不成立** — `app/main.py:110` 已注册，B-4 派工 prompt 必须修正
3. **alembic 078/079 编号与链序倒挂** — 真链尾是 078，**080 必须接 078 而非 079**，否则必双头阻塞部署

**本任务范畴**：纯 docs 新增，**0 production code 改动守恒**。锚点范式 W72 第 1 批 220 → W72 第 2 批 D-1 233 守恒（+13，预测值，待 A-1 主拍实测收束）。
