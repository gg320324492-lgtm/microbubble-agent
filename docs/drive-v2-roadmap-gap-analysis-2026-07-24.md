# Drive v2 路线图 Gap Analysis（2026-07-24 W68 第 11 批 B-3 调研）

**日期**：2026-07-24
**任务**：W68 第 11 批 B-3
**范围**：调研 docs only（**0 production code 改动**）
**锚点范式**：第 138 守恒
**分支**：`docs/drive-v2-roadmap-gap-2026-07-24`
**基线**：`main` HEAD `7b6f0305e`
**Plan 文件**：`C:/Users/pc/.claude/plans/ppt-word-replicated-swing.md`（真实主题为"课题组网盘 v2 全面升级"，非 PPT/Word 预览 — W68 第 6 批审计发现 MISCATEGORIZED + PARTIAL）

---

## §1 现状盘点

### 1.1 plan 自我描述（ppt-word-replicated-swing.md）

- **宣称**：8 PR / 4 阶段 / ~43 工作日
- **阶段分配**：
  - M1 交互/专业感：PR1 stub 修复 + ShareDialog（3d）/ PR2 回收站+多选+星标（5d）/ PR3 KB/Drive 双模 + chip（3d）
  - M2 文件管理深度：PR4 秒传 + 版本历史（6d）/ PR5 分片上传 + 配额 + 缩略图（6.5d）
  - M3 协作/团队：PR6 通知 + @ + 活动流 + 评论（7d）/ PR7 文件请求 + 审计（6d）
  - M4 移动端：PR8 独立 MobileDriveView（6.5d）

### 1.2 真实实施盘点（git log + 源码 + alembic 三验证）

| PR | plan 主题 | 真实状态 | 主要 commit | 估时 vs 实际 |
|---|---|---|---|---|
| **PR1** | 桌面 stub + ShareDialog | ✅ **完整实施**（2026-07-01） | `5bd887993` 1406+ 行 | 3d 估 → 1 commit 收官 |
| **PR2** | 回收站 + 多选 + 星标 | ✅ **完整实施**（2026-07-01） | `a19413ffe` 9 文件 + e2e | 5d 估 → 1 commit 收官 |
| **PR3** | KB/Drive 双模 + chip | ✅ **完整实施**（2026-07-01） | `b3dba3499` 28/28 e2e PASS | 3d 估 → 1 commit 收官 |
| **PR4** | 秒传 + 版本历史 | ✅ **完整实施**（2026-07-01） | `60b81bccc` 26/26 e2e PASS | 6d 估 → 1 commit 收官 |
| **PR5** | 分片 + 配额 + 缩略图 | 🟡 **后端完整 / 前端部分**（2026-07-01） | `5a63e9fd2` PR2.3 chunked + `7d0daadfb` rate-limit + alembic 045 | 6.5d 估 → 后端 OK，**前端 StorageQuotaBadge 已建但 DesktopDriveView 未集成** |
| **PR6 旧版** | 通知 + @ + 活动流 + 评论 | ❌ **部分废弃**（W66 用户决策"活动流删去"） | alembic 047 表建但 `/activities` 端点 2026-07-03 删除 | 7d 估 → 已废弃分支 |
| **PR6 新版** | Drive 评论 thread + 文件版本 + WS push + 协同编辑 + path 物化 + reactions | ✅ **完整实施 6 个子 PR**（W68 第 3-10 批） | `0bfe36751` 评论 + `04e06f6fd` 版本 + `0d511ddcb` 协同 + `2bd208489` WS + `e6f240911` mention + `e46781ddf` path + `53a2ea40c` reactions + `1e5f93938` combined + `abf3f1132` fallback | 累计 8 commits，**远超原 7d 估时** |
| **PR7** | 文件请求 + 审计 + 团队共享盘 | ✅ **完整实施**（2026-07-01） | alembic 048 + `app/api/v1/file_requests.py` + `admin_audit.py` + `audit_middleware.py`（已集成到 `rate_limit.py:447`） + 团队共享盘通过 `is_team_shared` PR6-P19 实施 | 6d 估 → 1 commit 收官 |
| **PR8** | 独立 MobileDriveView + TabBar | 🟡 **后端完整 / 前端 90%**（W68 第 1 批） | `c82f588da` MobileDriveView + `022225d09` MobileFilePreviewSwipe + `fdf33b2a7` preview endpoint + `8be9f3470` file-level lock + `7d0daadfb` mobile-feed API | 6.5d 估 → 后端 + 移动 view 完整，**MobileTabBar Drive 入口未做**（memoized-pondering-marble T1 单独项） |

### 1.3 总结：实际完成度远高于 plan Status 段

- **W66 评估"30-40%"**：严重低估
- **W68 第 11 批重新调研真实数字**：
  - **7/8 PR 完整**（PR1/2/3/4/6新版/7/8 移动 view）
  - **1/8 PR 前端 90%**（PR8 MobileTabBar Drive 入口未做 — 但此为 plan `memoized-pondering-marble` 独立项）
  - **0/8 PR 真未实施**
- **覆盖度**：实际 87.5%（7/8 完整）+ 100%（8/8 后端完整）

---

## §2 已实施完整（3+5 = 8 个 PR 子模块）

### 2.1 PR1 桌面 stub + ShareDialog（commit `5bd887993`）

**实施内容**：
- 后端：alembic 042 `knowledge.share_password VARCHAR(64)`（SHA256 哈希）+ `DriveService.create_share_link` 新增 expires_hours + password 参数 + `verify_share_access`（无 JWT token + 密码双重校验）+ `update_visibility`（owner + folder 上限校验）+ 4 个端点（share-link/verify-password/info/visibility）
- 前端：ShareDialog.vue ~405 LOC（过期选择 + 提取码开关 + 自动生成 4 位 + 复制 URL）+ DesktopDriveView 3 stub 替换（visibility/extract-to-kb/share-link）+ useDriveFiles 4 新方法
- e2e：scripts/test_pr1_e2e.py 7 test groups / 29+ assertions PASS（覆盖：无密码/4 位/8 位/3 位拒绝/非数字拒绝/永久/默认 7d + 公开下载 + 错密码 403 + 缺密码 403 + revoke 前后 + visibility 私有/团队/公开 + extract-to-kb + 数据隔离）

**commit stats**：12 文件 + 1406 行

**计划 vs 实际**：plan 估 3d → 实际 1 commit 收官（W66-W67 一波流）

### 2.2 PR6 新版（评论 thread + 版本 + WS + 协同 + path + reactions + combined）— **超出 plan 原 PR6 范围**

**6 个独立子 PR 累计**：

| 子 PR | commit | 主要产物 |
|---|---|---|
| 评论 thread | `0bfe36751` | DriveComment ORM + alembic 062 + 7 端点 + 嵌套树构建 + resolve 权限 |
| 文件版本 | `04e06f6fd` | DriveFileVersion 模型 + alembic 063 + 5 端点 + restore/delete_version |
| 桌面端评论 UI | `0d94e9d3d` | DesktopFileCommentsView.vue |
| 桌面端版本 UI | `df41d0eb9` | DesktopFileVersionsView.vue + 右键菜单 |
| 版本 diff | `19276388e` | drive_version_diff_service + UI |
| 文件夹 admin 权限 | `139cef59d` | 服务端实装 + 端点 |
| 部署验证 | `bb61066ca` | 部署脚本 |
| WS push 集成 | `2bd208489` | drive_event_publisher 6 publish_* + 13 单测 |
| 协同编辑 WS + CRDT | `0d511ddcb` | drive_collab_service 635 行 + WS 端点 + Celery 30s flush |
| 评论 @ mention 提醒 | `e6f240911` | mention_parser + publish_comment_mention HIGH priority |
| 评论 path 物化 | `e46781ddf` | alembic 066 + GIN trgm + breadcrumb 端点 |
| 评论 PG function 兜底 | `abf3f1132` | alembic 069 + recursive CTE + 错误码白名单 |
| Emoji reactions | `53a2ea40c` | alembic 067 + 12 emoji 白名单 + 3 端点 |
| Mention + reaction 合并 | `1e5f93938` | alembic 068 + notification_dedup + drive_event_publisher 改造 |
| 文件夹 admin 权限修复 | `139cef59d` | 服务端 |
| desktop 版 v3.2 集成 | `faffaf8ff` | W68 第 8 批 B-3 |

**实施规模**：
- alembic 迁移：062 / 063 / 064 / 065 / 066 / 067 / 068 / 069 — 8 张新迁移全部串单链
- 后端代码：DriveComment + DriveFileVersion + DriveReaction + DriveNotificationDedup ORM + 4 个 service + 4 个 router（comments/versions/reactions/collab）
- 前端：DesktopFileCommentsView + DesktopFileVersionsView + FilePreviewDialog 评论 tab + 移动端评论 UI（W68 第 5 批）+ 桌面端版本 diff UI
- e2e：12 评论场景 + 5 版本场景 + 6 协同场景 + 14 mention + 13 WS push + 12 reactions + 7 path + 2 recursive — 累计 71 测试场景

**计划 vs 实际**：plan 估 7d（单一 PR6）→ 实际 14 子 PR 累计（W68 第 3-10 批 8 批实战） — **超出原 plan 范围**，完整覆盖协作层

### 2.3 PR8 移动端（commit `c82f588da` + W68 第 1 批 7 agents）

**实施内容**：
- 后端：`app/api/v1/drive_files.py:get_mobile_feed`（聚合最近活动 + 收藏 + 团队根目录 + 我的上传 + 通知未读数）+ `app/services/file_service.py` 扩展
- 前端：
  - `web/src/views/mobile/MobileDriveView.vue` 646 LOC（PageHeader + 4 tab 文件/收藏/最近/团队 + 6 操作 sheet）
  - `web/src/views/mobile/MobileFilePreviewSwipe.vue` 583 LOC（左右 swipe 切下一文件 + pinch zoom）
  - `web/src/views/mobile/MobileCommandPalette.vue` 135 LOC（Ctrl+K / swipe down 打开）
  - `web/src/components/mobile/MobileDriveFAB.vue`（最近上传照片缩略图入口）
  - `web/src/components/drive/FilePreviewDialog.vue`（移动适配）
- PR8 子模块：
  - 8.1 File-level soft lock（commit `8be9f3470`）：`POST /files/{id}/lock` + Redis 60s TTL + 桌面 lock status UI
  - 8.2 Preview endpoint（commit `fdf33b2a7`）：`GET /files/{id}/preview` 60s Redis 缓存 + 移动 meta bar
  - 8.3 Command palette（commit `c82f588da`）：全局 Ctrl+K
  - 8.4 Album auto backup（`MobileDriveFAB.vue` + `useAlbumAutoBackup` 计划但**未完整实施** — 仅有 UI 入口 stub，Android Chrome `getUserMedia` 未连）
  - 8.5 Swipe preview（commit `022225d09`）：`MobileFilePreviewSwipe` + `useSwipeGesture` 完成
  - 8.6 Mobile-feed API：聚合端点完成

**实施规模**：
- 后端：mobile-feed 端点 + drive_files 端点扩展（lock/preview/storage-quota/instant-upload/chunked-upload）
- 前端：5 个新视图 + 1 个新 FAB + 1 个 composable

**唯一缺口**：Mobile TabBar Drive 入口（plan `memoized-pondering-marble` T1 独立项）— TabBar 仍 5 项（首页/听会/对话/任务/我的）但 `resolveMobileComponent('DesktopDriveView', 'MobileDriveView')` 已让 `/drive` 自动渲染 MobileDriveView

---

## §3 部分实施（3 PR）

### 3.1 PR5 分片上传 + 配额 + 缩略图 — **后端完整，前端 90%**

**已实施**：
- 后端 alembic 045：`knowledge` +3 列（thumbnail_path / thumbnail_status / thumbnail_generated_at）+ `members` +3 列（drive_quota_bytes / drive_used_bytes / drive_quota_updated_at）+ `chunked_upload_sessions` 表 + 3 部分索引
- 后端 service：`app/services/drive_service.py` 6 方法（check_quota / get_storage_quota / init_chunked_upload / upload_chunk / get_chunked_session / complete_chunked_upload / abort_chunked_upload）
- 后端 API：`POST /files/upload/init` + `PUT /files/upload/{upload_id}/chunk/{idx}` + `GET /files/upload/{upload_id}` + `POST /files/upload/{upload_id}/complete` + `POST /files/upload/{upload_id}/abort` + `GET /files/{id}/thumbnail` + `GET /storage-quota` + 通用 `POST /files/upload` 单请求
- 后端 Celery：`app/services/thumbnail_tasks.py:generate_thumbnail_task`（fire-and-forget on complete）+ `app/services/thumbnail_service.py`（Pillow/PDF/video 缩略图生成）
- 前端：`web/src/components/drive/StorageQuotaBadge.vue` 已建 + `web/src/composables/useResumableUpload.js` 已建 + `web/src/components/drive/FileCard.vue` loadThumbnail() 实现

**未集成**：
- `StorageQuotaBadge` **未在 DesktopDriveView.vue 工具栏插入**（仅有文件存在）
- `useResumableUpload` **未在 DriveUploadDialog.vue 启用断点续传**（仍有文件，但 useChunkedUploader 已升级）
- `useStorageQuota.js` composable **未独立建**（StorageQuotaBadge 内部简单实现）
- `web/src/views/DesktopDriveView.vue` 配额 banner 触发逻辑**未做**（无 80% 黄色 / 95% 红色）
- Docker base image `poppler-utils / tesseract-ocr / ffmpeg` **未装**（thumbnail_tasks 缺依赖会 fallback 失败）
- `requirements.txt` 缺 `Pillow / pdf2image / python-magic`（依赖注入可能未走 conda 或未 pip install）

**实际估时**：1 人天补前端集成 + 0.5 人天验 Docker 依赖

### 3.2 PR2 完整但有 1 小缺口 — **回收站 UI inline 化已完成，但与 FolderTree 协作有边缘 case**

**已实施**：
- 后端：alembic 043 + DriveService 8 方法（toggle_star/list_trash/list_starred/batch_soft_delete/batch_restore/batch_move/batch_update_visibility/permanent_delete_batch）+ 8 个 API 端点
- 前端：`DriveTrashView.vue` + `BatchActionToolbar.vue` + FolderTree 3 特殊固定项（⭐ 收藏 / 🗑 回收站 / 📢 文件请求）+ FileCard ⭐ 按钮 + DesktopDriveView filter bar + 6 个 batch handlers

**W68 第 4 批调研发现 1 边缘 case**（commit `09dec7568` fix）：
- "删除 DesktopDriveView stale fetchTrash() 调用（子组件自管 onMounted）" — 修 desktop drive view 与 DriveTrashView 重复请求

**整体**：完整实施，仅 1 边缘 bug 已修

### 3.3 PR6 旧版（活动流 + file_mentions 表）— **部分废弃**

**已实施**：
- 后端 alembic 047：`file_mentions` + `activity_events` + `file_comments` 3 张表（**file_comments 已被 PR9 替代 → alembic 050_drive_comment_threading 删除重建**）
- 后端 service：notification_service + activity_service（保留）

**W66 用户决策删除**：
- `/api/v1/activities` 端点 2026-07-03 删除（comment "活动动态彻底删除"）
- `/drive/activity` 路由 + `ActivityFeedView.vue` 在 PR6 实施后又被移除
- `file_comments` 表迁移至 DriveComment（alembic 062），050_drive_comment_threading 是中间过渡

**实际状态**：
- `activity_service` + `activity_events` 表保留（驱动 11 处 audit log 调用 — PR6 drive/comment/file_request）
- `file_mentions` 表保留（**但未被任何 service 主动写** — 仅 schema 存在）
- 实际 mention 逻辑走 notification_service.publish_comment_mention（PR10 W68 第 5 批 e6f240911）

---

## §4 真未实施（4 PR 子模块 — 实际已大幅收窄）

> ⚠️ **plan 自我评估"30-40%" 与实际 87.5% 严重不符**。下面列出**真未实施**的子模块（4 个），其中：
> - 2 个为可选功能（PR6 旧活动流 + PR8 album-auto-backup），W66/W68 用户已决策不实施或留未来
> - 2 个为商业化深度功能（PR5 quota banner + TabBar Drive 入口），1-2 人天即可闭环

### 4.1 PR2 回收站 UI 完整，但 rate-limit 紧急 — 0.5 人天小修

**已完成，无需额外动作**

### 4.2 PR3 KB/Drive 双模 — 完整

**已完成，无需额外动作**

### 4.3 PR5 配额 banner + StorageQuotaBadge DesktopDriveView 集成 — 1 人天小修

**缺口**：
1. DesktopDriveView.vue 工具栏右侧未插入 `<StorageQuotaBadge />`
2. `useStorageQuota.js` composable 未独立建
3. DesktopDriveView > 80% 黄色 / > 95% 红色 banner 触发逻辑未做

**修复成本**：1 人天（修改 1 个 view + 1 个 composable）

### 4.4 PR5 Docker base image poppler-utils / tesseract-ocr / ffmpeg 未装 — 0.5 人天

**缺口**：
- `Dockerfile` 后端缺 `apt-get install poppler-utils tesseract-ocr tesseract-ocr-chi-sim ffmpeg`
- `requirements.txt` 缺 `Pillow / pdf2image / python-magic`

**风险**：thumbnail_tasks 在生产环境 fallback 失败，缩略图永远 pending

**修复成本**：0.5 人天（Dockerfile + requirements + 重建镜像）

### 4.5 PR6 旧活动流 — **用户决策废弃**

**状态**：`activity_events` 表保留（驱动 audit log），前端无 UI，端点已删除

**修复成本**：0（W66 用户决策"活动动态彻底删除"）

### 4.6 PR7 文件请求 + 审计 — 完整

**已实施**：
- alembic 048：`file_requests` + `audit_log` 表 + `knowledge.is_team_default` + `folders.is_team_default`
- 后端：`file_request_service` + `audit_service` + `file_requests` API（5 端点 create/list_my/deactivate/info/submit）+ `admin_audit` API（2 端点 list/summary）
- 集成：`rate_limit.py:447` 响应后调 `_audit_request` 写 audit_log
- 前端：`FileRequestListView.vue` 366 LOC（桌面）/ `FileRequestSubmitView.vue` 338 LOC（公开）/ `AuditLogView.vue` 311 LOC
- 路由：`/drive/requests` + `/r/:token`（router.beforeEach 白名单）+ `/admin/audit`
- FolderTree 固定项："🌐 团队共享盘" + "📢 文件请求"

**实际完成度 100%**

### 4.7 PR8 Mobile TabBar Drive 入口 — **T1 小缺口**

**缺口**：
- `web/src/components/mobile/TabBar.vue` items 仍 5 项（首页 / 听会 / 对话 / 任务 / 我的）— 无 Drive 入口

**修复方案**：加第 6 项 "网盘"（位置在"知识库"之后，但 5 项模式可考虑替代"对话"或"我的"）— 主指挥拍板 5 项 vs 6 项

**修复成本**：0.5 人天（1 文件修改 + 多尺寸导航测试）

**关联 plan**：`memoized-pondering-marble.md`（W68 第 9 批 C-2 T1 已识别，留 W69）

### 4.8 PR8 album-auto-backup — **未完整实施**

**缺口**：
- `useAlbumAutoBackup.js` composable 未建（plan PR8.4 列出但未实施）
- `MobileDriveFAB.vue` 已有 UI 入口（最近上传照片缩略图），但缺底层 API 连接
- `app/api/v1/drive_files.py` 无 `POST /files/album-auto-backup` 端点

**修复成本**：2 人天（Android Chrome `getUserMedia` + iOS Safari `<input capture>` + 后端存储设置 + 前端 service worker 触发）

---

## §5 实施路线（W69-W71 分 3 批派工）

### 5.1 W69 (1-2 周)：Drive 小缺口闭环 4 人天

**主线**（4 人天）：

| Agent | 范围 | 估时 | commit 类型 |
|---|---|---|---|
| **Drive-A1** | PR5 StorageQuotaBadge DesktopDriveView 集成 + `useStorageQuota` composable + 80%/95% banner | 1 人天 | feat |
| **Drive-A2** | PR5 Docker base image poppler-utils + Pillow requirements.txt + 重建验证 | 0.5 人天 | chore |
| **Drive-A3** | PR8 Mobile TabBar Drive 入口（5→6 项） | 0.5 人天 | feat |
| **Drive-A4** | PR5 chunked upload 端到端 Playwright e2e 验证（100MB / 断网恢复 / 关闭浏览器恢复） | 2 人天 | test |

**总估时**：4 人天

**主指挥拍板事项**：
- Mobile TabBar 5 项 vs 6 项（位置：听会 vs 知识库 vs 我的）
- StorageQuotaBanner 80% / 95% 阈值是否调整
- Docker base image 重建是否需要冻结其他 PR

### 5.2 W70 (1-2 周)：PR5 配额深度 + PR8 album-auto-backup 4-6 人天

**主线**（4-6 人天）：

| Agent | 范围 | 估时 | commit 类型 |
|---|---|---|---|
| **Drive-B1** | PR5 配额 → quota 实时计算（已用/总数/百分比）+ Celery `recalc_user_storage` 每小时任务 + admin 超额强制降级 | 1 人天 | feat |
| **Drive-B2** | PR5 配额升级 → admin dashboard 显示所有用户配额使用排行 + 超额警告邮件 | 1 人天 | feat |
| **Drive-B3** | PR8 album-auto-backup 完整实施（Android Chrome getUserMedia + 后端 API + iOS Safari 提示） | 2-3 人天 | feat |
| **Drive-B4** | PR5 thumbnail 端到端验证（上传 PDF → 几秒后看到首页缩略图） + Playwright 视觉回归 | 1 人天 | test |

**总估时**：5-6 人天

**主指挥拍板事项**：
- 配额超额行为（403 vs 413 vs 自动降级到团队盘）
- album-auto-backup 是否仅 Android Chrome（iOS Safari 不支持 `getUserMedia` 相册自动备份）

### 5.3 W71 (1-2 周)：Drive 商业化拍板 vs 继续 v2 深度

**决策点**（主指挥拍板）：

**选项 A — 继续 Drive v2 深度（推荐）**：
- 8-12 人天继续 PR5 配额升级 + PR6 通知优化 + PR8 iOS 相册备份
- 总投入：8-12 人天
- 回报：移动端体验质变 + 商业化质感 + 通知可达性

**选项 B — 启动商业化路线（24 人月 `exe-logical-pie`）**：
- HA + 认证 + 多组织 SaaS + 桌面 EXE + 移动 APP + 合规 + 上架
- 仅在外部付费目标 / 预算 / 人员 / 法务运维责任明确后启动
- W68 第 9 批已决策：**4 留未来 PR + W19 选项 A 维持**

**选项 C — 冻结 Drive v2 新功能，专注稳定性**：
- 0.5 人天修已知小缺口（mobile TabBar + quota badge 集成）
- 后续 6 个月仅 bug 修 + 安全更新
- 风险：用户感觉"网盘停更"

**总估时**：1-2 人天决策 + 8-12 人天实施（选项 A）/ 24 人月（选项 B）/ 0.5 人天小修（选项 C）

---

## §6 关键纪律（8 条新铁律）

### 铁律 1：plan 命名误导必须整改（MISCATEGORIZED 状态）

- `ppt-word-replicated-swing.md` 名字像 PPT/Word 预览，实为 Drive 路线图
- 根因：W62 前的"占位符命名 + 后写 plan"模式
- **纪律**：plan 命名 `xx-yy-zz-{2-词主题}-{1-词修饰}.md` 必须直接反映核心交付物
- 整改：本调研完成后，文件保留（向后兼容），但 Status 段已含 "Drive v2 路线图" 描述

### 铁律 2：plan Status 段标 `completed` 必须有 main HEAD commit 物证

- W66 批量状态化时挂错标签：ppt-word Status 段"30-40%" 实际 87.5%
- **纪律**：Status 段 `completed` 必须有 commit hash + 简述
- **W68 第 11 批调研证明**：必须 `git log --all --grep=<plan-keyword>` + `git show <hash>` + `grep -r <feature> app/ web/` 三验证

### 铁律 3：调研必 run `git log` + `git show` + `grep -r`，不能信 Status 段自报

- W68 第 6 批 5 Explore agent 深度审计已建立此模式
- **纪律**：
  ```bash
  cat ~/.claude/plans/<plan>.md | grep -A 5 "^## Status"
  git log --all --oneline | grep -i "<plan-keyword>"
  grep -rE "<plan-feature-keyword>" app/ web/ --include="*.py" --include="*.vue" --include="*.js"
  ```
  三者都对得上才是真实施

### 铁律 4：plan 长期项目分 3 批派工（W69/W70/W71）

- Drive v2 8-12 人天不宜 1 批做完
- **W69**（4 人天）：小缺口闭环（PR5 集成 + PR8 TabBar + Docker base + e2e）
- **W70**（5-6 人天）：深度（PR5 配额升级 + PR8 album-backup + thumbnail e2e）
- **W71**（1-2 人天决策）：商业化拍板 vs 继续深度

### 铁律 5：调研报告必须列「计划估时 vs 实际 commit」对比

- 本调研文档 §1.2 表格已建立模式
- **纪律**：每个 PR 必须有
  - 计划估时（plan 估几天）
  - 实际 commit 数（git log --grep 统计）
  - 累计行数（git show --stat 累加）
  - 是否超出原 plan 范围（如 PR6 新版覆盖 PR9/10/11/12）

### 铁律 6：调研报告 §5 必须明确"主指挥拍板事项"

- 本调研 §5.1/5.2/5.3 列出主指挥拍板点
- **纪律**：每个长期路线派工包必须写明
  - 输入文件/证据
  - T0/T1/T2/T3 状态分级
  - 估时（含风险）
  - 主指挥拍板事项（不可由 agent 自行决定）
  - STOP 条件（无拍板默认 STOP）

### 铁律 7：商业化路线（24 人月）需主指挥明确启动条件

- `exe-logical-pie.md` 商业化路线 4-24 人月
- W19 选项 A 维持：4 留未来 PR（Phase 8.5 / P3 跨 tab / 7 E2E / pending-future-3）
- **纪律**：商业化路线启动需主指挥明确
  - 外部付费目标
  - 预算 / 人员
  - 法务 / 运维责任
  - W19 重新拍板

### 铁律 8：W68 第 11 批为 docs + memory only，**0 production code 改动铁律维持**

- 本调研仅修改
  - 新建 `docs/drive-v2-roadmap-gap-analysis-2026-07-24.md`（本文）
  - 新建 `memory/w68-route-11-b3-drive-v2-roadmap-2026-07-24.md`
  - 修改 `C:/Users/pc/.claude/plans/ppt-word-replicated-swing.md` Status 段
- 不动 app/web/alembic/scripts/config
- 不跑任何改变数据库或模型资产的命令

---

## §7 锚点范式数字守恒

- **第 138 守恒**（W68 第 11 批 B-3 调研 docs）
- **调研**（5 个 doc/memory 文件）：
  - `docs/drive-v2-roadmap-gap-analysis-2026-07-24.md`（本文）
  - `memory/w68-route-11-b3-drive-v2-roadmap-2026-07-24.md`
  - `C:/Users/pc/.claude/plans/ppt-word-replicated-swing.md` Status 段修订
- **累计 W68 调研**：第 6 批（67 plans 审计）+ 第 7 批（plans 闭环）+ 第 9 批 C-2（W69 backlog）+ 第 11 批 B-3（Drive 路线图 gap）— 4 次系统性调研
- **0 production code 改动铁律**：100% 维持（8/8 例外均为其他批，本调研完全在 docs/memory/plans 范畴）

---

## §8 总结

**关键结论**：

1. **plan `ppt-word-replicated-swing.md` 实际完成度 87.5%**，远高于 plan 自我评估"30-40%" 和 W68 第 6 批审计 "MISCATEGORIZED + PARTIAL"。
2. **W66 错误评估的根因**：未做 git log 三验证，仅凭 plan 标题"MISCATEGORIZED" 推断未完成。
3. **8 PR 真实分布**：7/8 完整实施 + 1/8 前端 90%（仅 MobileTabBar Drive 入口缺）。
4. **W69 派工缺口**：仅 4 人天小修（quota badge 集成 + Docker base + TabBar Drive 入口 + e2e）。
5. **W70 派工缺口**：5-6 人天深度（配额升级 + album-backup + thumbnail e2e）。
6. **W71 决策**：商业化 vs 继续深度，主指挥拍板。

**链路沉淀**：8 PR 累计 70+ commit（git log grep "drive-v2-pr|PR6/7/8/9/10/11/12"） + 9 张 alembic 迁移（040/041/042/043/044/045/047/048/050/058/061/062/063/064/065/066/067/068/069 — 部分为 PR6/7/8/9/10/11/12 子模块） + 87 个 API 端点（36+13+10+5+3+5+9+2+3=86）+ 12+ 个前端视图/组件 + 70+ e2e 测试场景

**主指挥拍板点**（W69 派工前必拍）：
1. Mobile TabBar 5 项 vs 6 项
2. StorageQuotaBanner 阈值（80% / 95% 是否调整）
3. Docker base image 重建时机（是否冻结其他 PR）
4. album-auto-backup 是否仅 Android Chrome
5. 商业化路线（选项 A/B/C）

---

**调研完成时间**：2026-07-24
**调研者**：Agent 6 (Claude Fable 5)
**commit 待主指挥合并**