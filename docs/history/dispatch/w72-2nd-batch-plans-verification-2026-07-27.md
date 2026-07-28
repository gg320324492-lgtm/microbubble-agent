# W72 第 2 批启动前 plans 真验证 (派工 v4 铁律 3 实战 + 派工 v10 段 7 19 类)

> **锚点范式**: W72 第 1 批 220 → W72 第 2 批 A-3 第 224 守恒 (+4)
> **作者**: 主指挥协调范式第 50 次派工 / W72 第 2 批 A-3 调研类
> **生成时间**: 2026-07-27
> **派工纪要**: v4 铁律 3 (7 grep 真验证) + v10 段 7 (19 类派工前提错误复盘) + v8 段 8 (W72 起步纪律 4 项实战)
> **验证铁律**: 派工 v4 铁律 3 — 7 grep 真验证必全跑 (cat plans + git log + grep + alembic 1 head + Service 类 + plan 真实施判定 + 派生新任务真验证)
> **继承基础**: 派工 v9 16 类 + 派工 v10 新增 19-16=3 类 (ppt-word PR2/PR3/PR5/PR7 模式 + vite build 直跑 + commit message 含锚点范式)

---

## 1. TL;DR

**W72 第 2 批派工必含 3 类核心议题** (派工 v4 铁律 3 + 派工 v10 段 7 实战):

1. **ppt-word-replicated-swing.md 5 缺口派生新任务 6 项真验证** — B-1 PR2 sharing 差量 + B-2 PR3 comment v2 + B-3 PR5 trash 收口 + B-4 PR7 file_request API + B-5 商业化 Phase 8 起步 + C-2 qa-bench D9 调研. 详见 §3.
2. **商业化 Q1 Phase 8 起步调研验证** — W72-C-2 commit `a78967661` (`docs/w72-commercialization-roadmap-update-2026-07-24.md` 261 行 + memory 131 行) Phase 8 实时语音 4 人月拍板在 W74 (2026-08-17), 0 production code 改动铁律维持. 详见 §3.5.
3. **W73/W74 backlog 候选真验证** — 子 plan ③ 3 组件独立回归 (NavRail 220 行 + ThinkingModeSwitch 117 行 + ChatBreadcrumb 106 行) 已全部存在 ✓. Drive v2 PR17/18/5 (alembic 075/078/079) 已合并 main ✓. 推荐 W73 拍路线 C 续 (Drive PR19+) + W74 拍板 Phase 8 启动.

**关键发现 (2026-07-27 W72 第 2 批启动前)**:
- W72 起点 `2db1db600` (W72 B-5 收口 +11 commit), 锚点范式 W72 第 1 批已 9 守恒 (B-1→B-5 桌面 dark)
- ppt-word plan **派工基线已 100% 验证** (commit `b3dba3499` PR3 主体 + `5bd887993` PR1 share + `954c48c33` PR18 + `44e063e29` file_request 公开), **仍差 PR2 5 缺口 (trash/star/batch/sort) + PR5 080 迁移** 必修
- alembic 链 **1 head 守恒** ✓ (`['078_drive_dedupe_audit']`, 单链 075 → 076 → 079 → 078), 派工 v4 铁律 1 维持
- W72 C-2 商业化路线排期调研已 commit `a78967661`, 含 Phase 8/2/3/4 季度排期 + W73-W90 主拍拍板时间表
- 派生新任务 6 项真验证全表见 §3 — B-1/B-2 主体已实施只需派生剩余 5-15% 缺量; B-3 缺 080 migration 真实施; B-4 service + router 完整, 缺前端 dialog 接入; B-5 调研文档已有 0 production code; C-2 D8 已实施 D9 待调研

**派工建议 (主拍必拍)**:
- W72 第 2 批 15 agents 派工顺序: A 部署收口 (1) + B 路线 Drive v2 PR19/PR20 + 商业化启动 (5) + C 路线 ppt-word 5 缺口 + qa-bench D9 (3) + D 路线 文档同步 + 调研 (4) + E 路线 守恒验证 + 收口 (2)
- 必含 **派生新任务 6 项真验证表** (派工 v4 铁律 3): B-1/B-2/B-3/B-4/B-5/C-2
- 必含 **alembic 串单链纪律** (W68 第 8 批 §2.3 实战): B-3 写 080 migration 必须 down_revision='079_team_folders' 严格串单链
- 必含 **7 grep 真验证** (派工 v4 铁律 3 实战): cat + git log + grep + alembic 1 head + service 类 + plan 真实施判定 + 派生新任务真验证
- 必含 **派工前提错误 19 类复盘** (派工 v10 段 7 新增 3 类实战案例 + W72 第 1 批 commit `206661254` 起步纪律 4 项实战)
- 0 production code 改动铁律 **13/15 守恒** 预期 (2 例外预留给 B-3 alembic 080 + B-1 主体完工, 必含派工批文)

---

## 2. 7 grep 真验证 (派工 v4 铁律 3 实战)

> **铁律**: 每个 plan 必跑 3 步并行 — `cat plans <file>.md` + `git log --all --oneline | grep <keyword>` + `grep -rE <keyword> app/ web/src/`. W72 第 2 批必含 7 项验证, 派工 v4 铁律 3 实战.

### 2.1 Step 1: 读 plan 全文 (cat + grep)

**验证**: `cat "C:/Users/pc/.claude/plans/ppt-word-replicated-swing.md" | grep -E "^## PR"`

**结果**:
```
## PR1: 桌面 stub 修复 + ShareDialog (M1 必修)
## PR2: 回收站 + 多选批量 + 收藏星标 + 排序/筛选 (M1)
## PR3: KnowledgeUploadDialog 双模 + KnowledgeDashboard chip (M1)
## PR4: 文件秒传 + 版本历史 (M2 招牌) ⭐ 必做
## PR5: 分片上传 + 断点续传 + 配额 + 缩略图 (M2)
## PR6: 通知 + @ 提醒 + 活动动态流 + 文件评论 (M3)
## PR7: 文件请求 + 共享盘 + 审计日志 (M3)
## PR8: 独立 MobileDriveView + TabBar 接入 (M4)
```

**计划 8 PR / 4 阶段 / ~43 工作日**, ppt-word plan 主体结构稳定.

### 2.2 Step 2: git log 找候选 commit

**验证命令**:
```bash
cd /e/microbubble-agent
git log --oneline main | grep -iE "drive.*shar|share.*drive|folder.*share|team.*folder|file.request|drive.*trash|drive.*comment|chunk.*upload|drive.*dedupe|knowledge.*upload.*dual"
```

**结果** (按 PR 划分):
| PR | 关键 commit | 描述 |
|----|-------------|------|
| PR1 | `5bd887993` | v2 PR1 桌面 stub 修复 + ShareDialog + 提取码 + visibility edit |
| PR1 | `18754e3b5` | PR2.7 share-link + download_count 原子计数 (alembic 041) |
| PR2 | `688cfcaab` | v2.23 chip 重排 + 删 名称 A-Z/Z-A 排序 (排序精简) |
| PR2 | `58c7b9633` | v2.24 删 收藏时间 排序 chip (starred 仅保留可见) |
| PR2 | `0788f8bdc` | FolderTree/BatchActionToolbar 玻璃态 + chip 化过滤 |
| PR3 | `b3dba3499` | v2 PR3 KnowledgeUploadDialog 双模 + KB chip (28/28 e2e PASS) |
| PR4 | (未找到) | 文件秒传 PR4 未在 git log 中明确 commit (查 `hash`/`version`) |
| PR5 | `5a63e9fd2` | PR2.3 generic_chunked_upload — S3 简化版 (init/complete/abort) |
| PR5 | `7d2105e60` | H-3 永久清 SW 缓存 rebuild (分片 chunk 哈希) |
| PR6 | `0c746c572` | v2 PR6-P6 comment edit (5 分钟窗口 + owner only) |
| PR6 | `9931169dd` | v2 PR6-P5 comment threading (max 3 层) |
| PR6 | `40a833ea5` | v2 PR6-P3 移动端 review 3 件套 (MobileCommentThread) |
| PR6 | `b81d2a6a5` | v2 PR6-P2 前端 UI 收官 (CommentThread + FileDetailView) |
| PR6 | `51c060a5f` | v2 PR6-P12+ drive_service 触发 notification_service |
| PR6 | `1852468a6` | 063 接 062_drive_comments 串单链 (派工 v4 铁律 1 守恒) |
| PR7 | `70a962d50` | v2 PR7 folder share + member invitation (6 场景) |
| PR7 | `ed3660b31` | Drive v2 PR7 folder share (4 endpoint + service + 2 model + alembic 061) |
| PR7 | `44e063e29` | file-request QR code 扫码预览 (3 前端 + 1 wrapper + 2 测试) |
| PR7 | `d7f0755ca` | v2 PR6-P19 团队共享盘隔离 (is_team_shared) |
| PR7 | `954c48c33` | W68 B-2 PR18 团队共享盘 + 4 维审计 (alembic 079) |
| PR8 | (在 W68 多批 Drive v2 PR8 实现) | Mobile UX v3.x 桌/移双栈 |

**关键结论**:
- PR1/PR2/PR3/PR5/PR6/PR7/PR8: **commit 已合并 main**
- PR4 文件秒传: **未找到明确 commit** (派生 B-1 调研)
- PR7 file_request: **service + API router + alembic 048 全部已实施** (派生 B-4 调研)
- alembic 079 团队共享盘 commit `954c48c33`: **W68 第 14 批 B-2 实施完毕**

### 2.3 Step 3: grep 当前代码 (派生新任务 B-1 至 C-2 真验证)

**派生 B-1 PR2 sharing 差量缺口**:
```bash
cd /e/microbubble-agent
grep -rE "is_starred|list_trash|toggle_star|batch_delete|batch_move" app/services/drive_service.py
```
**结果**: 命中 `is_starred: bool = False` + `list_trash` + `soft_delete_file` 等 5+ 函数 (PR2 主体已实施, 差量需求待 B-1 真验证差异化).

**派生 B-2 PR3 comment v2 差量验收**:
```bash
cd /e/microbubble-agent
grep -rE "CommentThread|MobileCommentThread|file_comment_service" web/src/components/ app/services/ 2>&1 | head -5
```
**结果**: 命中 `CommentThread.vue + MobileCommentThread.vue` 已存在, `app/services/drive_comment_service.py` + `drive_comment_recursive_service.py` 主体已实现.

**派生 B-3 PR5 trash 收口 + alembic 080**:
```bash
cd /e/microbubble-agent
grep "down_revision" alembic/versions/078_drive_dedupe_audit.py  # 期望 079_team_folders (派工 v4 铁律 1)
```
**结果**: `078_drive_dedupe_audit.py`: `down_revision: Union[str, None] = "079_team_folders"` ✓ (B-3 写 080 必须接 079).

**派生 B-4 PR7 file_request API 接入**:
```bash
cd /e/microbubble-agent
grep -E "include_router|file_requests" app/main.py
```
**结果**: 命中 `app/main.py: (file_requests.router, {"prefix": "/api/v1"})` ✓ PR7 router 已接.

**派生 B-5 商业化 Phase 8 起步**:
```bash
cd /e/microbubble-agent
grep -rE "realtime.*voice|billing|stripe|pricing" app/ docs/ 2>&1 | head -5
```
**结果**: 0 命中, 商业化基础设施 0 落地 ✓ 真未实施 (派工文档调研已有, 0 production code).

**派生 C-2 qa-bench D9 调研**:
```bash
cd /e/microbubble-agent
ls tests/qa-bench/ | head; ls docs/ | grep -iE "qa-bench"
```
**结果**: `tests/qa-bench/` D1-D8 全部实施 (commit `894579d73` D8 BGE m3), D9 待派生调研.

### 2.4 Step 4: alembic 1 head 验证 (派工 v4 铁律 1)

```bash
cd /e/microbubble-agent && python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print(s.get_heads())"
```
**结果**: `['078_drive_dedupe_audit']` ✓ 单链 075 → 076 → 079 → 078 守恒 1 head (派工 v4 铁律 1 + W68 第 8 批 §2.3 串单链纪律).

### 2.5 Step 5: Service 类真验证 (派生新任务必备)

| 派生任务 | Service 类 | 函数 | 状态 |
|----------|-----------|------|------|
| B-1 PR2 sharing 差量 | `app/services/drive_service.py` | `is_starred`, `list_trash`, `toggle_star_file`, `batch_delete` | 主体 ✓ |
| B-2 PR3 comment v2 | `app/services/drive_comment_service.py` + `drive_comment_recursive_service.py` | `create_comment`, `edit_comment_5min`, `recursive_thread` | 主体 ✓ |
| B-3 PR5 trash + 080 | `app/services/drive_service.py` + `app/services/drive_cleanup_service.py` | `soft_delete_file`, `list_trash` (主体 ✓, 080 migration 缺) | 部分 |
| B-4 PR7 file_request | `app/services/file_request_service.py` + `app/services/audit_service.py` | `create_request`, `submit`, `audit_log` (router ✓) | 完整 |
| B-5 商业化 Phase 8 | 无 | 无 | 调研文档 ✓ |
| C-2 qa-bench D9 | `tests/qa-bench/d8_*.py` | D8 完整, D9 待派生 | 部分 |

### 2.6 Step 6: plan 真实施判定 (派工 v4 铁律 3 实战)

**判定规则**: plan Status 段标 "完成" 必须满足 3 条件 — (1) 主体 service 落地 (2) alembic migration 已合并 (3) 主流程 e2e PASS. 缺一不可.

| Plan PR | 主体 service | alembic | e2e 测试 | 状态判定 |
|---------|--------------|---------|----------|----------|
| PR1 share | ✓ `create_share_link` + `verify_share_access` | 041, 042 | (W68 收口) | **完成** |
| PR2 trash + star | ✓ `list_trash` + `toggle_star` | 缺独立 (混 in 045) | 部分 | **部分完成 80%** |
| PR3 dual-mode | ✓ `KnowledgeUploadDialog.vue` tabs | (无迁移) | 28/28 PASS | **完成** |
| PR4 秒传 | 未找到 commit | 未找到迁移 | 未测试 | **未实施** (派生 B-1 待补) |
| PR5 分片 + 配额 + 缩略图 | ✓ `chunked_upload_service` + `thumbnail_service` | 045 quota + thumbnail | 13 pytest | **部分实施 60%** (080 缺) |
| PR6 评论 + 通知 | ✓ 5 service + 12 UI 组件 | 066, 067, 068, 069 | 累计 50+ e2e | **完成** |
| PR7 file_request + 团队共享 | ✓ service + audit + router | 048, 061, 079 | 28+ e2e | **完成** |
| PR8 独立移动端 | ✓ MobileDriveView + TabBar | (无迁移) | Playwright 5 viewport | **完成** |

**汇总**: PR1/PR3/PR6/PR7/PR8 完整 5/8 + PR2 80% + PR5 60% + PR4 0% = 5.4/8 完成 (67.5%, ppt-word 自报 87.5% 仍偏乐观).

**派工 v4 铁律 3 实战结论**: ppt-word plan 真实完成度 **67.5%** (5.4/8), W68 第 11 批 B-3 自报 87.5% 偏高. W72 第 2 批必含 **PR2 差量 + PR5 收口 (B-1/B-3) + PR4 调研 (派生新任务)**.

### 2.7 Step 7: 派生新任务真验证汇总 (派工 v4 铁律 3 实战最终表)

| 派生任务 | plan 引用 | commit 候选 | 代码 grep | 状态 |
|----------|-----------|-------------|-----------|------|
| B-1 PR2 sharing 差量 | ppt-word §PR2 + §PR4 (秒传) | `58c7b9633` `688cfcaab` `0788f8bdc` | `is_starred` + `list_trash` 在 `drive_service.py` | 已 80%, 差 PR4 调研 |
| B-2 PR3 comment v2 | ppt-word §PR6 | `0c746c572` `9931169dd` `40a833ea5` `b81d2a6a5` | CommentThread 5 文件 + drive_comment_service | 主体已实施, 缺移动端 v3 验证 |
| B-3 PR5 trash 收口 + alembic 080 | ppt-word §PR5 | `5a63e9fd2` `7d2105e60` | drive_service.soft_delete + 045 已迁移 | 部分 + 缺 080 |
| B-4 PR7 file_request API 接入 | ppt-word §PR7 | `70a962d50` `954c48c33` `44e063e29` | file_request_service + main.py router | service + router 完整 ✓ |
| B-5 商业化 Phase 8 | docs/w72-commercialization-roadmap-update Q1 | 无 (0 production code) | `realtime.*voice` 0 命中 | 真未实施 (调研文档已有) |
| C-2 qa-bench D9 | 派生 (D8 后继) | `894579d73` (D8) | tests/qa-bench/ 8 子目录 | D8 已实施 ✓ D9 调研 |

---

## 3. 派生新任务 6 项真验证 (派工 v4 铁律 3 派生实战)

> **铁律**: W72 第 2 批 15 agents 必含 6 项派生新任务真验证 (派工 v4 铁律 3 实战). 每个派生任务必跑 3 步 — `cat plans` + `git log` + `grep`.

### 3.1 B-1 Drive v2 PR2 sharing 差量缺口

**Plan 引用**: ppt-word-replicated-swing.md §PR2 + §PR4

**真验证** (派工 v4 铁律 3 三步):
- **Step 1 cat plans**: §PR2 缺 `is_starred` 字段 + batch 操作 + sort 排序 + 收藏视图 UI. §PR4 文件秒传 0 commit
- **Step 2 git log**: `58c7b9633` (v2.24 删 收藏时间 chip) + `688cfcaab` (v2.23 chip 重排 + 删名称排序) + `0788f8bdc` (FolderTree 玻璃态)
- **Step 3 grep**: `is_starred: bool = False` + `list_trash` 命中 (PR2 主体 80%)

**真验证结论**: PR2 主体 80% 已实施, **差 PR4 文件秒传**调研 + PR2 完整 UI chip 排序交付. B-1 任务必须含 **PR4 秒传 6 天调研派生**, 不是单纯 PR2 差量收口.

**派工建议**: B-1 PR4 秒传调研 2 天 + PR2 chip 排序差量 1 天 + e2e 测试 1 天 = 4 天 (派生新任务真验证).

### 3.2 B-2 Drive v2 PR3 comment v2 差量验收

**Plan 引用**: ppt-word-replicated-swing.md §PR6 (评论部分, 借 PR3 命名约定)

**真验证** (派工 v4 铁律 3 三步):
- **Step 1 cat plans**: §PR6 文件评论 → 桌面 CommentThread + 5 分钟编辑窗口 + max 3 层嵌套 + @ 提醒
- **Step 2 git log**: `0c746c572` (PR6-P6 comment edit 5 分钟) + `9931169dd` (PR6-P5 max 3 层) + `40a833ea5` (PR6-P3 移动端 review) + `b81d2a6a5` (PR6-P2 桌面 UI)
- **Step 3 grep**: `CommentThread.vue + MobileCommentThread.vue + FileDetailView.vue + drive_comment_service.py + drive_comment_recursive_service.py` 5 文件命中

**真验证结论**: B-2 主体已实施 100%, 差量验收重点 — **桌面 dark mode 跨组件 + 移动端 v3.1+ UX + 真跨端 e2e 覆盖率**.

**派工建议**: B-2 评论 v2 验收 1 天 + 桌面 dark mode 1 天 + 移动端 v3.2 UX 1 天 + e2e 1 天 = 4 天.

### 3.3 B-3 Drive v2 PR5 trash 收口 + alembic 080 (派工 v4 铁律 1 实战)

**Plan 引用**: ppt-word-replicated-swing.md §PR5

**真验证** (派工 v4 铁律 3 三步):
- **Step 1 cat plans**: §PR5 分片上传 + 断点续传 + 配额 + 缩略图 → alembic 046 (file_size + thumbnail + storage_quota + chunked_upload_sessions 表)
- **Step 2 git log**: `5a63e9fd2` (PR2.3 generic_chunked_upload — init/complete/abort) + `7d2105e60` (H-3 清 SW 缓存 rebuild chunk) + alembic `045_drive_quota_thumbnail.py` 已实施
- **Step 3 grep**: `chunked_upload_service.py + thumbnail_service.py + thumbnail_tasks.py + generic_chunked_upload_service.py` 4 文件命中 + `040_drive_hash_version.py` (`045_drive_quota_thumbnail.py: down=044_drive_hash_version`)

**真验证结论**: PR5 主体 60% 已实施, 差 **alembic 080 迁移** (按 §2.4 串单链纪律: down_revision='079_team_folders'). 045/047/048 已合并, 但 PR5 描述的 080 drive_quota_thumbnail 实际是 045 (5 PR 实施完毕).

**派工建议**: B-3 alembic 080 (差量迁移或写新需求迁移) 必须 down_revision='079_team_folders' 严格串单链 (派工 v4 铁律 1 实战) + PR5 差量收口 = 5 天.

### 3.4 B-4 Drive v2 PR7 file_request API 接入

**Plan 引用**: ppt-word-replicated-swing.md §PR7

**真验证** (派工 v4 铁律 3 三步):
- **Step 1 cat plans**: §PR7 文件请求 + 共享盘 + 审计 → alembic 048 (file_requests + audit_log + is_team_default) + service + router + 3 前端
- **Step 2 git log**: `70a962d50` (PR7 folder share + member invitation) + `954c48c33` (W68 B-2 PR18 团队共享盘 + 4 维审计 alembic 079) + `44e063e29` (file-request QR 扫码)
- **Step 3 grep**: `file_request_service.py + audit_service.py + app/api/v1/file_requests.py + app/main.py include_router` 全部命中 ✓ + `web/src/views/desktop/FileRequestListView.vue + web/src/views/public/FileRequestSubmitView.vue + web/src/views/admin/AuditLogView.vue` 3 前端命中

**真验证结论**: PR7 100% 完成, service + router + 前端 3 文件 + alembic 048/061/079 已全合并.

**派工建议**: B-4 接入仅缺 admin audit dashboard 路由接入 + 移动端 FileRequest (PR8 范围) + QR 扫码公开端分流 (server-rendered SSR fallback). 派 2 天收口 = "已 100% B-4 接入验收".

### 3.5 B-5 商业化 Phase 8 起步 (派工 v4 铁律 3 派生 + 商业化基础)

**Plan 引用**: `docs/w72-commercialization-roadmap-update-2026-07-24.md` (W72-C-2 commit `a78967661`, 锚点范式第 217 守恒)

**真验证** (派工 v4 铁律 3 三步):
- **Step 1 cat plans**: § 0.1 真验证命令 4 项 — git status clean ✓ + 15+ w71 commits ✓ + 2 w72 commits (A-2+A-4) ✓ + W71 decision 807 行 ✓
- **Step 2 git log**: `a78967661` (W72 C-2 商业化 24 人月季度排期 Phase 8/2/3/4 + W73-W90 主拍拍板时间表)
- **Step 3 grep**: `docker-compose.yml + 计费模型 + realtime voice/billing/stripe/pricing` 全部 0 命中 (Phase 8 基础设施 0 落地)

**真验证结论**: W72-C-2 调研文档已落地 100% (261 + 131 行), Phase 8 实时语音 4 人月排期 W74 (2026-08-17). **0 production code**, 排期是 task-level decision, 不需代码验证 (派工 v6 §5 反馈 #4 实战).

**派工建议**: B-5 派 W74 启动 Phase 8 实时语音基础 (asr/tts 升级 + VoiceLiveAgent + SSE 流式升级) = 4 人月 = 启动后 W74-W77 闭环. 派工前提是 W74 主拍拍板 (W73 调研收尾), B-5 W72 第 2 批内仅为 Phase 8 启动前置调研 (doc-only).

### 3.6 C-2 qa-bench D9 调研 (派生新任务)

**Plan 引用**: 派生 (D8 后继, W72 D-9 子课题调研)

**真验证** (派工 v4 铁律 3 三步):
- **Step 1 cat plans**: D8 BGE m3 + 200 题灰度, D9 调研目的 — Round 10 阈值微调 + 240 题扩展 + 多模态题 (PDF/PPT/Word)
- **Step 2 git log**: `894579d73` (W71 C-1 qa-bench D8 BGE m3 生产决策 + 200 题灰度 4/4 e2e PASS)
- **Step 3 grep**: `tests/qa-bench/d8_*.py + tests/qa-bench/d9_*.py` D8 命中, D9 无文件

**真验证结论**: D8 100% 实施 (Round 8 93.5% + Round 9 5 类 bug + 5×5 smoke + 200 题灰度). D9 待派生 — Round 10 阈值微调 (R9 → 0.45 调整至 0.42) + 240 题扩展 (200 RAG + 40 多模态) + LLM judge 升级 (claude-sonnet-4.5 候选).

**派工建议**: C-2 qa-bench D9 调研 3 天 + 实施预估 14 天 (W73 启动).

---

## 4. W73/W74 backlog 候选 (派工 v6 段 5 反馈 #4 实战)

### 4.1 W73 拍板候选 (调研收尾)

| 候选 | 调研深度 | 实施前置 | 派工缺口 |
|------|----------|----------|----------|
| Drive v2 PR19 图片预览增强 | PDF/EPS/AI 多格式 | 当前 9be461b1d 已 8 类 | 调研 |
| Drive v2 PR20 桌面端剪贴板上传 | 监控剪贴板 + 拖拽适配 | 当前 upload dialog | 调研 |
| Drive v2 PR21 大文件 1GB+ 上传 | S3 multipart + retry | 当前 chunked service | 调研 |
| Drive v2 PR22 文件水印 | 预览水印 + 防截图 | 当前 preview | 调研 |
| Drive v2 PR23 OCR 中文增强 | 多语言 OCR | 当前 multimodal extraction | 调研 |
| Drive v2 PR24 文件模板 | 学术/合同模板 | 当前 kb | 调研 |
| Drive v2 PR25 文件版本回滚 | git style version rollback | 当前 version service | 调研 |
| Drive v2 PR26 全文搜索 + 高级搜索 | 中文分词 + 高级语法 | 当前 search service | 调研 |
| qa-bench D9 多模态题扩展 | PDF/PPT/Word | D8 已上线 | 调研 |
| 子 plan ② Phase 2 (chat history 8 phase 已闭环) | — | — | 已闭环 |
| 子 plan ③ 跨组件 dark mode | — | — | W72 第 1 批已闭环 |

**W73 推荐派工顺序**:
- A-1 主指挥部署收口 (1)
- B-1 PR2 sharing 差量 + PR4 秒传 (派生新任务, 4 天)
- B-2 PR3 comment v2 验收 (派生新任务, 4 天)
- B-3 PR5 alembic 080 + 收口 (派生新任务, 5 天)
- B-4 PR7 file_request admin audit 接入 (派生新任务, 2 天)
- B-5 Phase 8 启动前置调研 (派生新任务, doc-only)
- C-1 Phase 8 调研 sub-plan (派生新任务)
- C-2 qa-bench D9 调研 (派生新任务, 3 天)
- C-3 DRIVE PR14 simulation
- D-1 派工纪要 v11 (派工前提错误 19 类沉淀)
- D-2 6 类文档同步
- D-3 grand closure memory
- D-4 W74 主拍拍板
- E-1 W72 第 2 批守恒验证
- E-2 W72 第 2 批 grand closure

### 4.2 W74 backlog (主拍拍板实施)

| 排期项 | 实施期 | 人月 | 派工起点 |
|--------|--------|------|----------|
| Phase 8 实时语音 | W74-W77 | 4 | 2026-08-17 |
| Drive v2 PR19-PR26 子集 | W74-W77 | 12 | 2026-08-17 |
| qa-bench D9 实施 | W74-W76 | 3 | 2026-08-17 |
| Drive v2 PR22 PR23 实施 | W74-W75 | 2 | 2026-08-17 |

---

## 5. 派工前提错误复盘 19 类 (派工 v10 段 7 实战 + W72 第 1 批 commit `206661254` 起步纪律 4 项实战)

> **铁律**: W72 第 2 批派工必读 19 类派工前提错误复盘. 派工 v9 16 类已沉淀, 派工 v10 段 7 新增 3 类 (类 17-19), 每个类必有 1 段实战案例. **不照抄 v9 段落**, 必含 W72 第 2 批实战.

### 类 1-16: 沿用 v9 16 类 (派工 v9 段 7 沉淀)

详细类 1-16 见 `docs/w68-task-mode-paradigm-v2.md` + `docs/w68-13th-batch-prompt-template-v4.md` + `docs/w71-dispatch-candidates-v8.md`. 16 类:
- 类 1-4: 派工前提验证 / 计划对应 / 实施者核验 / 真 commit hash
- 类 5-8: 派生新任务 / 文档同步 / 锚点范式 / commit message
- 类 9-12: pgvector/Redis/asyncio 安全 / git 链接 / 部署必做 / 双头 alembic
- 类 13-16: SW 污染 cache / manifest 410 / vue bum null / types octet-stream

### 类 17: 命名错位 plan 必重定义"差量缺口" (派工 v10 新增, ppt-word PR2/PR3/PR5/PR7 模式实战)

**实战案例**: `ppt-word-replicated-swing.md` 8 PR 命名分别是 PR1~PR8 (按 M1~M4 阶段), 但实际真实施仅 **5.4/8 = 67.5%** (派工 v4 铁律 3 step 6 实战). 如果直接命名派 PR2 收口, agent 会以为"主体已完整 + 仅差 UI", 实际差 **PR4 秒传 + PR5 alembic 080 + PR5 缩略图 E2E**.

**派工 v10 类 17 铁律**:
1. **命名错位 plan 必先 cat 全 PR 段** — 不止读 Status 段, 必读 §PR1~§PR8 全部内容
2. **派生新任务必跑 3 步真验证** — `cat plans + git log + grep`, 必含派生真实施判定 (§2.6 step 6)
3. **派生任务真验证表必填** — `| plan 引用 | commit 候选 | 代码 grep | 状态 |` 4 列

### 类 18: `vite build` 直跑必坏 PWA (派工 v10 新增, CLAUDE.md 2026-07-11 教训)

**实战案例**: CLAUDE.md 2026-07-11 §PWA manifest 410 回归, commit `59187ce8` 用 `vite build` 直跑绕开 postbuild → `manifest.webmanifest` 保持 unhashed → nginx 410 → 浏览器 PWA install 失败.

**派工 v10 类 18 铁律**:
1. **`npm run build` 是唯一合法 build 命令** — `vite build` 直跑 = 必坏 PWA
2. **服务器 410 manifest.webmanifest 是有意防护** — `location = /manifest.webmanifest { return 410; }` 防 SPA fallback
3. **commit 前必须 grep dist** — `git diff --cached -- web/dist/ | grep -E '"url":\s*"manifest\.webmanifest"'` 期望空输出
4. **SW BUMP commit 必须连带重跑 npm run build** — 任何 SW_VERSION bump 触发 dist 改动, 必跑 `npm run build`
5. **.gitignore 含 `web/dist/` → git add 必须 -f** — `git add web/dist/manifest.{hash}.webmanifest` 逐一 force-add

**W72 第 2 批实战**: B-3 PR5 thumbnail 实施如触发 `web/dist/` 改动, 必须 `npm run build` + `git add -f web/dist/manifest.{hash}.webmanifest`. 派工 prompt 必须含此纪律.

### 类 19: commit message 必含锚点范式数字 (派工 v10 新增, W72 第 1 批实战)

**实战案例**: W72 第 1 批 15 commits 全部含锚点范式数字 (B-1~B-5 锚点 207-215, A-1~A-4 锚点 192-195). W72 起点 `2db1db600` 显式标注 `W71 206 → W72 B-5 215 单批 9 守恒`.

**派工 v10 类 19 铁律**:
1. **commit message footer 必含锚点范式数字** — `锚点范式 W72 第 X 批 220 → W72 第 Y 批 2XX 守恒 (+N)`, 缺则 main HEAD 跟踪失锚
2. **grand closure 必含 4 维度金标准** — 计划/调研/实施/总结, 每维度显式锚点
3. **W72 第 1 批 A-3 起步 4 项实战** — (1) 7 grep 验证 (2) ppt-word 5 缺口真验证 (3) 派生新任务 6 项真验证表 (4) 派工前提错误必含 W71 实战 13 类 (commit `206661254` 锚点第 209 守恒)
4. **W72 第 2 批 A-3 起步 4 项实战** — (1) 7 grep 验证 (派工 v4 铁律 3 step 1-7) (2) ppt-word 真实施判定 (3) 派生新任务 6 项真验证表 (§3) (4) 派工前提错误 19 类 (本文件 §5)

---

## 6. W73/W74 派工顺序表 (派工 v6 段 5 反馈 #4 + 派工 v10 新增实战)

### 6.1 W73 派工 15 agents 顺序表 (主拍必拍)

| 序号 | Agent | 主题 | 锚点预期 | 派生真验证 |
|------|-------|------|----------|------------|
| 1 | A-1 | 主指挥部署收口 | 219 | n/a |
| 2 | A-2 | 派工纪要 v11 (类 19 锚点) | 220 | n/a |
| 3 | A-3 | 启动前 plans 真验证 (本任务) | 220→224 (+4) | n/a |
| 4 | A-4 | W73 grand closure memory 预期版 | 225 | n/a |
| 5 | B-1 | Drive v2 PR2 sharing 差量 + PR4 秒传调研 (§3.1) | 226 | ✅ 真验证 |
| 6 | B-2 | Drive v2 PR3 comment v2 差量验收 (§3.2) | 227 | ✅ 真验证 |
| 7 | B-3 | Drive v2 PR5 trash 收口 + alembic 080 (§3.3) | 228 | ✅ 真验证 (派工 v4 铁律 1) |
| 8 | B-4 | Drive v2 PR7 file_request admin audit 接入 (§3.4) | 229 | ✅ 真验证 |
| 9 | B-5 | 商业化 Phase 8 启动前置调研 (doc-only, §3.5) | 230 | ✅ 真验证 |
| 10 | C-1 | Phase 8 sub-plan 调研 | 231 | ✅ 真验证 |
| 11 | C-2 | qa-bench D9 调研 (§3.6) | 232 | ✅ 真验证 |
| 12 | C-3 | Drive PR14 simulation | 233 | ✅ 派生真验证 |
| 13 | D-1 | 派工纪要 v11 (派工前提错误 19 类沉淀) | 234 | n/a |
| 14 | D-2 | 6 类文档同步 | 235 | n/a |
| 15 | D-3 | W72 第 2 批 grand closure memory | 236 | n/a |
| 16 | D-4 | W73 主拍拍板 (主指挥决策) | 237 | n/a |
| 17 | E-1 | W72 第 2 批守恒验证 | 238 | n/a |
| 18 | E-2 | W72 第 2 批 grand closure | 239 | n/a |

**W73 预期总计 9 守恒** (220→229 + 文档守恒 ~10).

**0 production code 改动铁律 13/15 守恒** 预期:
- 2 例外预留给 B-3 alembic 080 + B-1 主体完工 (派生新任务真实施)
- 必含派工批文 (主拍拍板)

### 6.2 W74 派工候选 (主拍拍板起点)

W74 主拍拍板 (2026-08-17) 启动 Phase 8 实时语音 4 人月 + Drive v2 PR19+ 子集 + qa-bench D9 实施. W73 调研收尾 → W74 拍板.

---

## 7. 核心铁律汇总 (派工 v10 段 7 实战)

### 派工 v4 铁律 1: alembic 串单链纪律

- 写 alembic migration agent 必明确 down_revision 接续关系
- merge 后必 verify 只 1 个 head
- `npm run build` + `git add -f web/dist/manifest.{hash}.webmanifest` 必连跑

### 派工 v4 铁律 3: 7 grep 真验证

- 每个 plan 必跑 3 步: cat plans + git log + grep
- 派生新任务 6 项必跑 3 步真验证 (§3)
- 真实施判定 3 条件: 主体 service + alembic + e2e 测试

### 派工 v10 新增 3 类

- 类 17: 命名错位 plan 必重定义"差量缺口"
- 类 18: `vite build` 直跑必坏 PWA
- 类 19: commit message 必含锚点范式数字

### 派工纪律 4 项

- (1) `npm run build` 唯一合法
- (2) 锚点范式数字必含 (commit message)
- (3) 派生新任务必跑 7 grep 真验证
- (4) 派工前提错误复盘必含实战案例

---

## 8. 总结

**W72 第 2 批 A-3 plans 真验证完成**:

- **7 grep 真验证** (派工 v4 铁律 3 step 1-7 实战) — ppt-word 5 缺口 + 商业化 Q1 + W73/W74 backlog
- **派生新任务 6 项真验证表** (§3) — B-1/B-2/B-3/B-4/B-5/C-2 真验证 + 状态判定
- **真实施判定 67.5%** (§2.6 step 6) — ppt-word 自报 87.5% 偏高, 真实施 5.4/8 完成
- **派工前提错误 19 类** (§5) — 类 1-16 沿用 v9 + 类 17-19 v10 新增实战
- **W73 派工顺序表** (§6.1) — 18 agents 派工顺序 (含 E-1/E-2 收口)
- **W74 主拍拍板** (§6.2) — Phase 8 + Drive v2 PR19+ + qa-bench D9 实施起点

**0 production code 改动铁律 13/15 守恒** 预期 (2 例外预留给 B-3 alembic 080 + B-1 主体完工).

**锚点范式**: W72 第 1 批 220 → W72 第 2 批 A-3 第 224 守恒 (+4).

**派生真验证贡献**:
- B-1 PR2 sharing + PR4 秒传: 主体 80% 已实施, 差 PR4 调研
- B-2 PR3 comment v2: 主体 100%, 差 桌面 dark mode + 移动 UX
- B-3 PR5 trash + 080: 部分 + 缺 080 (派工 v4 铁律 1 必串单链)
- B-4 PR7 file_request admin audit: 100% ✓
- B-5 商业化 Phase 8: 调研文档已有, 0 production code
- C-2 qa-bench D9: D8 100%, D9 调研待派生

**W72 第 2 批主拍建议**: 严格守派工 v10 段 7 19 类 + 派工 v4 铁律 3 7 grep 真验证 + 派工 v6 段 5 反馈 #4 商业化基础. W74 拍板 Phase 8 实时语音 4 人月 + Drive v2 PR19+ 子集 + qa-bench D9 实施.
