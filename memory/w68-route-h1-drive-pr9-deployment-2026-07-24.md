# W68 路线 H-1: Drive v2 PR9 部署 + 用户文档 (2026-07-24)

> **锚点范式第 41 守恒**。0 production code 改动铁律维持 — 仅 3 docs + 1 memory, 无 app/ web/ 任何改动。
> 分支 `docs/drive-v2-pr9-deployment-2026-07-24`, base main HEAD `37e0de62a`, 不 merge (主指挥来 merge)。

## 任务与产出

W68 第 2 批路线 F 三个 PR9 特性分支完工后, 路线 H-1 补齐部署 + 用户文档:

| 文件 | 行数 | 内容 |
|------|------|------|
| `docs/drive-v2-pr9-deployment.md` | ~300 | 0 节 alembic 双头警告 + 4 节标准结构 (alembic 升级 / SSH 部署流程 / 验证清单 / 回滚) + 端点速查附录 |
| `docs/drive-v2-pr9-user-guide.md` | ~130 | 评论 thread 教程 (移动/桌面对照表) + 版本历史教程 (上传/回滚/对比) + 4 FAQ + 移动端提示 |
| `docs/drive-v2-pr9-rollout-checklist.md` | ~110 | 部署前 4 组检查 + 执行/验证勾选 + 回滚触发条件 + 用户通知模板 (微信群文案) |
| 本 memory | ~120 | 沉淀 |

## 上游事实核查 (docs 写前逐一验证, 非凭空编)

三个特性分支均已 push origin, **尚未 merge 进 main** (main HEAD 37e0de62a 无 PR9 代码):

1. **F-1 评论** `feat/drive-v2-pr9-comments-2026-07-24` @ `0bfe36751`:
   - 新表 `drive_comments` (alembic `062_drive_comments.py`, down_revision=061)
   - file_id/folder_id XOR CHECK + parent_id 嵌套不限 + author_id NOT NULL CASCADE + resolved_at/by
   - 7 endpoints, router prefix `/drive/comments`
2. **F-2 版本** `feat/drive-v2-pr9-versions-2026-07-24` @ `04e06f6fd`:
   - 新表 `drive_file_versions` (alembic `063_drive_file_versions.py`, **down_revision=061 同样**)
   - 5 endpoints, 路径 `/versions/files/{file_id}/versions` 系 (无 prefix, tags=网盘文件版本)
   - rollback = 创建新版本; 禁删中间版; is_current Integer 0/1
3. **F-3 移动 UI** `feat/mobile-drive-comments-ui-2026-07-24` @ `a6f183511`:
   - 纯前端 8 文件 (MobileFileCommentsView / MobileCommentThread / MobileCommentInput / useFileComments.ts + Playwright spec)
   - 路由 `drive/file/:id/comments` mobileOnly, 无迁移

## 关键发现: alembic 双头 (本次最重要的文档价值)

**062 和 063 都声明 `down_revision = "061_drive_folder_share"`** — 两 agent 并行开发各自接 061, merge 后 alembic 出现 multi-head, `alembic upgrade head` 直接报 `Multiple head revisions are present`。

deployment 文档第 0 节给出两解法:
- **解法 A (推荐)**: merge 时改 063 `down_revision` → `062_drive_comments`, 串成单链 061→062→063 (对齐 053/054/055/056 四连单链模式)
- **解法 B (不推荐)**: `alembic upgrade heads` 双头共存, downgrade 需分支限定语法, 给 064 留 `alembic merge` 坑

⚠️ **主指挥 merge 时必须先做解法 A 的一行改动**, 否则部署第一步就卡死。rollout checklist 1.1 已加勾选项。

## 新铁律沉淀 (3 条)

1. **并行 agent 各建 alembic 迁移必撞 down_revision** — 派工时若 2+ agent 都可能建表, 主指挥应预先分配 revision 序号链 (062 给 A, 063 给 B 且声明 down_revision=062), 或 merge 时固定由后 merge 者改链。本次 062/063 双头即教训。
2. **部署文档必须基于 git show 分支实读, 不基于任务描述** — 任务书写"4 张新表"易误读为 PR9 建 4 张; 实读后确认 PR9 只建 2 张 (062+063), 另 2 张 (drive_folder_shares/members) 是 061 前置。文档按 "psql 验证 4 张 drive_* 表 (061 两张 + 062/063 各一张)" 表述, 避免误导主指挥以为迁移丢表。
3. **未 merge 特性的 docs 要写"merge 后"视角 + 标注 commit hash** — 三分支 hash (0bfe36751 / 04e06f6fd / a6f183511) 写死进 checklist, 主指挥 merge 时可核对; 回滚节用 `git revert -m 1 <merge hash>` 占位而非编造 hash。

## 锚点范式第 41 守恒声明

- **0 production code 改动**: 本分支 diff 仅 `docs/*.md` × 3 + `memory/*.md` × 1
- baseline 不触碰: 71 PASS + 7 SKIP Lint CSS 基线无涉; pytest/vitest 无涉
- 锚点单调链: W67 28 → W68 29 (grand closure) → … → 路线 F-1 36 / F-2 37 / H-2 42 → **H-1 41** (按派工序号归位)
- W19 选项 A 维持; 不 merge 不动 main; push origin 后由主指挥收口

## 遗留 (交主指挥)

1. merge 三分支 + 解法 A 改 063 down_revision (一行)
2. 按 rollout checklist 执行部署 (本地 PC Docker, 云端仅 curl 验证)
3. 部署后回填实际 merge hash 到本 memory + checklist 归档
4. PR10 排期项: WS 评论实时推送 / 版本内容 diff / 版本保留策略 / folder 维度版本
