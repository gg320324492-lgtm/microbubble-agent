# W72 第 2 批 D-1：Drive v2 roadmap gap analysis 恢复

> 日期：2026-07-27
> 任务：W72 第 2 批 D-1 缺口 5 gap analysis 恢复
> 依据：W72 第 1 批 C-3 commit `f1947d3c7` §2.6 真验证（文档缺失）+ `ppt-word-replicated-swing.md` §缺口 5
> 基线：main HEAD `2db1db600`
> 分支：`docs/w72-2nd-batch-d1-drive-v2-roadmap-gap-2026-07-27`
> 锚点范式：W72 第 1 批 220 → W72 第 2 批 D-1 233 守恒（+13，预测值）
> 范畴：纯 docs，**0 production code 改动守恒**

## 1. 背景

W72 第 1 批 C-3（`f1947d3c7`）§2.6 执行真验证后显式报缺：plan §Status 引用的
`docs/drive-v2-roadmap-gap-analysis-2026-07-24.md` 在 worktree 不存在，因此「缺口 5」
不能建立在缺失文档上宣布完成，状态应为「调研基础」（2h / P1）。

C-3 铁律 6 要求：缺失的权威文档必须显式报缺，不得伪造已读内容，也不得用相似文件名代替。
本 D-1 任务即该报缺项的收口。

## 2. 交付物

1. `docs/drive-v2-roadmap-gap-analysis-2026-07-24.md`（新增）
   - §0 恢复背景与文档缺失真根因
   - §1 Drive v2 路线总图（PR1-PR18 清单 + alembic 链真验证 + 商业化 24 人月 + 5 缺口收口状态）
   - §2 8 行 4 列状态表（现状/估时/优先级/派工建议）+ 状态漂移汇总
   - §3 W73（7 项）/ W74（6 项）派工顺序表 + 串单链守恒顺序
   - §4 锚点范式守恒预期（W72-2 230 / W73 240 / W74 248）+ 0 prod code 14/15
   - §5 4 类风险与缓解（alembic 链 / 多租户隔离 / 移动端 dark / 计费网关）
2. `memory/w72-route-72nd-batch-d1-gap-recovery-2026-07-27.md`（本文件）

## 3. 真验证方法与 3 项新发现

### 3.1 方法

```bash
ls docs/drive-v2-roadmap*                              # 确认缺失
git log --all --oneline | grep -iE "drive.*roadmap|gap.*analysis"
git branch -a --contains 8a3dde4f1                     # 定位真根因
git show 8a3dde4f1:docs/drive-v2-roadmap-gap-analysis-2026-07-24.md
git show f1947d3c7:docs/w72nd-batch-c3-pptword-gap-survey-2026-07-24.md
ls alembic/versions/ | sort | tail -12                 # 链状态
grep -H "down_revision" alembic/versions/078_*.py alembic/versions/079_*.py
python -c "...ScriptDirectory...get_heads()"           # 单 head 验证
grep -rn "file_request" app/main.py                    # PR7 前提核查
```

### 3.2 发现 1：文档缺失真根因 = 分支从未合并（C-3 未定位）

原始 gap analysis 由 **W68 第 11 批 B-3** 写成（commit `8a3dde4f1`，410 行，8 段），
但该 commit **只存在于分支 `docs/drive-v2-roadmap-gap-2026-07-24`（本地 + origin 双在），从未 merge 进 main**。

- ❌ 不是 refactor 意外删除（对比 `15-17-18-cozy-bengio` Part 2 在 `4b215220` 被删的事故模式）
- ❌ 不是 git 历史丢失
- ✅ 是**分支未合并** — plan §Status 提前引用尚未落 main 的文档路径，形成「引用悬空」

### 3.3 发现 2：PR7「router 未接」前提不成立

派工输入称 PR7「service 已有 router 未接」，真验证：

```
app/main.py:49   file_requests,
app/main.py:110  (file_requests.router, {"prefix": "/api/v1"}),
```

router **已注册**。B-4 派工 prompt 必须修正前提，否则会重复注册。

### 3.4 发现 3：alembic 078/079 编号与链序倒挂 ⚠️ 最高风险

```
079.down_revision = "076_drive_comments_path_backfill"
078.down_revision = "079_team_folders"
→ 真链序 076 → 079 → 078，文件名数字顺序与拓扑顺序相反
get_heads() → ['078_drive_dedupe_audit']  COUNT=1  ✅ 单 head 守恒
077_* 缺号（无 revision 引用，链完整）
080_* 缺失（与派工输入一致）
```

**推论**：W73/W74 agent 若按「文件名最大即链尾」直觉把 080 接到 `079_team_folders`，
将与既有 `078.down_revision = 079` 冲突形成**双头** → `alembic upgrade head` 报
`Multiple head revisions are present` 阻塞部署。

**结论**：**080 的 down_revision 必须 = `"078_drive_dedupe_audit"`，不是 079**。
此句须逐字写入 B-3 派工 prompt。

### 3.5 其他 grep 物证（main `2db1db600`）

```
app/services/drive_share_service.py        ✅
app/services/drive_comment_service.py      ✅
app/services/file_request_service.py       ✅
app/api/v1/file_requests.py                ✅
app/services/drive_service.py              ✅ list_trash/deleted_at 40 处 + is_team_shared_filter:236
web/src/views/desktop/DriveTrashView.vue   ✅
web/src/components/drive/DriveTrashPanel.vue ✅
web/src/views/mobile/MobileDriveView.vue   ✅
web/src/views/mobile/*DriveTrash*          ❌ 不存在（仅 MobileTaskTrash.vue）→ PR5 真缺口
```

## 4. 8 行 4 列状态表（摘要）

| 缺口 | 现状 | 估时 | 优先级 | 派工 |
|---|---|---|---|---|
| PR2 sharing 差量 | 已有 folder share + team folder（命名错位） | 8h | P0 | B-1 必先合 |
| PR3 comment v2 验收 | thread/软删/reaction/path 已多批 | 6h | P1 | B-2 后合 |
| PR5 trash 收口 + 080 | 后端+桌面在；移动端缺；080 缺 | 6.5h | P0 | B-3 依赖 PR2+PR3 |
| PR7 file_request | 主体完整，router 已接（前提修正） | 12h | P2 | B-4 最后收口 |
| 缺口 5 gap analysis | 缺失 → 本任务恢复 | 2h | P1 | D-1 ✅ |
| 商业化 Phase 8 | 真未实施 | 24h | P0 | B-5 |
| Mobile v3.4 暗色 | 真未实施 | 16h | P1 | C-3 |
| qa-bench D9 调研 | D8 已实施，D9 纯调研 | 4h | P2 | C-2 |

合计 78.5h ≈ 2 人周，跨 W73 + W74 消化。

## 5. 锚点范式口径不自洽的如实处理

派工输入同时给出两个口径：

- agent 级：W72 第 2 批 D-1 **233**（+13）
- 批级：W72 第 2 批 **220 → 230**

二者不自洽（233 > 230）。本文件与 doc §4.1 **如实并列**，不做静默调和，
并明示两者均为**预测值**，最终实际值须由 A-1 主拍在全部 agent 合并后按
4 维度金标准（W71 D-3 `0c9d33ec0`）实测收束。

遵守 CLAUDE.md §「Status 段必真验证」+ W68 第 11 批 D-2 铁律 3「预测值明示」。

## 6. 新铁律沉淀

### 铁律 1：plan §Status 引用 docs 路径前必须确认已在 main

`git ls-tree main -- <path>` 或 `ls` 验证。不能引用仅存在于 agent 分支的文件，
否则后续批次真验证必然报缺，浪费一轮调研工时。本次 `8a3dde4f1` 即典型案例。

### 铁律 2：alembic 文件名数字顺序 ≠ 迁移拓扑顺序

必须读 `down_revision` 字段判定真链尾，不能按 `ls | tail -1` 猜。
078/079 倒挂即反例。新增 migration 前必跑：

```bash
grep -H "^revision\|down_revision" alembic/versions/*.py | tail -20
python -c "...get_heads()"
```

### 铁律 3：派工输入的技术前提也须真验证，不只验 plan Status

本次「PR7 router 未接」来自派工输入而非 plan，同样被证伪。
**任何前提陈述（无论出处）都须 grep 验证**，否则会派出重复实现的工。

### 铁律 4：估时须覆盖真验证发现的隐藏缺口

C-3 给 PR5 trash 4h，未计入移动端回收站缺失 + 080 migration；
本文件调整为 6.5h。估时应在真验证后修订，不照抄上游。

### 铁律 5：锚点范式口径冲突必须如实并列 + 明示预测值

不静默取其一、不静默调和。冲突本身是主拍需要拍板的信息。

### 铁律 6：资金流风险与代码 bug 风险须分级处理

计费网关是唯一触碰真实资金流的任务，事故不可回滚。
支付链路**禁止 best-effort 静默吞异常**（与 CLAUDE.md 铁律 5「持久化失败 best-effort」相反 —
资金流必须显式失败）。W73 只预留接口（`BILLING_GATEWAY_ENABLED = False`），
W74 真接入须主指挥单独拍板，不由调研文档自动授权。

## 7. 0 production code 守恒

本任务仅新增：

- `docs/drive-v2-roadmap-gap-analysis-2026-07-24.md`
- `memory/w72-route-72nd-batch-d1-gap-recovery-2026-07-27.md`

未触碰 `app/`、`web/src/`、`alembic/versions/`。**0 production code 改动守恒** ✅

## 8. 收口

W72 第 1 批 C-3 §2.6 报缺项已收口，gap analysis 恢复为 main 上的权威底稿，
供 W73/W74 派工引用。5 段全覆盖 + 8 行 4 列状态表 + 两批派工顺序表 +
锚点范式预期 + 4 类风险缓解 + 6 新铁律。锚点范式第 233 守恒（预测）。
