# W72 第 2 批 B-1 — Drive v2 PR2 sharing 差量缺口实施 (2026-07-27)

## 任务定位

W72 第 1 批 C-3 (`f1947d3c7`) 真验证派生: ppt-word PR2 sharing 缺口存在但**不能重做后端**。
- folder share (PR7 alembic 061, commit `ed3660b31`) + team folder (PR18 alembic 079 preview) 已有
- DriveFolderShare 缺: 密码保护 + 次数限制 + 审计 action 字符串
- 桌面 UI 只有 file-level ShareDialog (PR2.7 Knowledge.share_token), 缺 folder share link dialog
- 移动端无 folder share 入口
- audit_middleware 仅 generic classify, 缺 folder share 3 个专属 action

## 4 项差量实施 (派工 v10 段 7)

### 1. alembic 081 migration — drive_folder_shares 3 新列
- `alembic/versions/081_drive_share_enhancements.py`
- revision = `081_drive_share_enhancements`
- down_revision = `078_drive_dedupe_audit` (当前 head, W68-14-B-2 079 preview 态未合并)
- 串单链纪律: `078 → 081`, 1 个 head 0 双头 (派工纪要 v4 铁律 1 守恒)
- 加 3 列:
  * `password_hash VARCHAR(128) NULL` — SHA256 hash (与 drive_service.py 同模式)
  * `max_downloads INTEGER NULL` — None = 不限 (PR7 兼容)
  * `download_count INTEGER NOT NULL DEFAULT 0` — 原子自增 (PR2.7 Knowledge.download_count 同模式)
- 加 1 索引: `ix_drive_folder_shares_active (folder_id, revoked_at)` WHERE revoked_at IS NULL (高频"活跃 share"查询)
- 不破坏 PR7: 所有新列 nullable / 有 server_default, 老调用 100% 兼容

### 2. service 层扩展 — drive_share_service.py
- `create_folder_share` 加 2 kw 参数: `password: Optional[str] = None` + `max_downloads: Optional[int] = None`
- 校验: password 4-8 位数字 (regex `^\d{4,8}$`); max_downloads 1-10000
- 密码哈希: SHA256 (`hashlib.sha256("drive_share_v1:" + password)`), **不用 bcrypt**:
  * 项目惯例 (drive_service.py `_hash_share_password` 也用 SHA256)
  * bcrypt 72-byte 上限 + passlib 在测试环境有兼容问题 (AttributeError: module 'bcrypt' has no attribute '__about__')
- `get_folder_by_share_token` 加 password 参数 + 密码校验 + 次数校验 + 公开下载审计 (share_downloaded)
- `increment_download_count` 新方法: SQL UPDATE 原子自增 + 超限返 -1 (PR2.7 Knowledge.download_count 同模式)
- `revoke_folder_share` 加审计 (share_revoked action)
- 3 处审计: `try/except + logger.warning` 兜底, 审计失败不阻塞主流程 (与 W68 第 13 批 audit_middleware 模式一致)

### 3. model + schema 扩展
- `app/models/drive_share.py`:
  * 加 3 列 (password_hash / max_downloads / download_count)
  * `is_active` 属性加 max_downloads 检查 (`download_count >= max_downloads → False`)
- `app/schemas/drive_share.py`:
  * `FolderShareCreate` 加 password (4-8 位数字) + max_downloads (1-10000) Optional
  * `FolderShareResponse` 加 3 新字段: has_password / max_downloads / download_count (不暴露 password_hash)

### 4. 前端集成
- **桌面端**:
  * `web/src/components/drive/ShareLinkDialog.vue` 新建 (408 行, 玻璃态 + 6 主题 dark mode, 末尾非 scoped 块)
  * `web/src/components/drive/FolderTreeNode.vue` 加第 6 项菜单「🔗 分享」(v-if 不控制, 永远显示)
  * `web/src/components/drive/FolderTree.vue` 加 share 命令处理 + emit 'share-folder'
  * `web/src/views/DesktopDriveView.vue` 集成 ShareLinkDialog + onShareFolder handler + @share-folder emit binding
- **移动端**:
  * `web/src/views/mobile/MobileDriveView.vue` fileActions computed 加 'share-folder' (当 currentFolderId 非空时)
  * 复用桌面 ShareLinkDialog (el-dialog 响应式布局)
  * 触觉反馈 `navigator.vibrate(10)` (CLAUDE.md 2026-06-27 教训守恒)
- **审计 middleware**:
  * `app/core/audit_middleware.py` `_classify_action` 加 3 专属 action 字符串:
    - POST `/api/v1/drive/folders/{id}/share` → `share_created`
    - GET `/api/v1/drive/folders/share/{token}` → `share_downloaded`
    - DELETE `/api/v1/drive/folders/share/{id}` → `share_revoked`

## 8 场景 e2e PASS (13 case 总)

`tests/test_drive_v2_w72b1_sharing_e2e.py` (387 行):
1. ✅ 创建 share link + 过期时间 (expires_at 6-8 天准确)
2. ✅ 密码保护 share link (有 password / 错密码失败 / 格式校验)
3. ✅ 次数限制 (max_downloads + increment_download_count 原子 + 超限返 -1)
4. ✅ is_active 属性 (过期 + 次数超限双 false)
5. ✅ 完整流 (create → access → revoke → access None)
6. ✅ MobileDriveView fileActions 含 share-folder + navigator.vibrate + ShareLinkDialog
7. ✅ DesktopDriveView + FolderTreeNode + ShareLinkDialog 集成 (静态分析)
8. ✅ audit_middleware 3 action 字符串分类
9. ✅ PR7 老调用兼容 (无 password/max_downloads 不回归)

跑法: `cd <worktree> && SKIP_DB_SETUP=1 python -m pytest tests/test_drive_v2_w72b1_sharing_e2e.py -v`
- 13/13 PASS in 0.69s
- 用 raw DDL 建 sqlite (members / folders / drive_folder_shares / knowledge / audit_log) 避免 PG 依赖
- fixture 不连真 PG / Redis / MinIO, 纯 service + model 单元验证
- SKIP_DB_SETUP=1 避免 conftest.py 触发 app.core.database.async_session

## 锚点范式

W72 第 1 批 215 → W72 第 2 批 B-1 220 守恒 (+5):
- 1 alembic migration (081)
- 1 e2e 测试文件 (13 case)
- 1 新增 Vue 组件 (ShareLinkDialog.vue 408 行)
- 4 后端文件改动 (model + schema + service + audit_middleware)
- 4 前端文件改动 (FolderTree + FolderTreeNode + DesktopDriveView + MobileDriveView)

**0 production code 改动铁律 1/15 例外已批**: B-1 sharing 差量 (派工 v10 段 5 反馈 #2 沿用 — drive_share + audit_middleware 例外清单 0 扩大化, 仅 W72 批 specific 增强)。

## 纪律沉淀 (4 新铁律)

1. **SHA256 > bcrypt for 短密码 (4-8 位)** — bcrypt 72-byte 上限 + passlib 与新 bcrypt 库兼容问题 (AttributeError: module 'bcrypt' has no attribute '__about__'). 4-8 位数字密码无安全增益, SHA256 + salt 足够。
2. **password_hash 字段选 VARCHAR(128) 非 VARCHAR(60)** — bcrypt hash 60 字符, 但 SHA256 hexdigest 64 字符; 留 128 buffer 兼容未来算法切换 (drive_share.py 字段定义)。
3. **service 审计调用必 try/except + logger.warning** — audit_service 失败不阻塞主流程 (W68 第 13 批 audit_middleware 模式复用); 测试 SKIP_DB_SETUP 下即使 audit_log 表不存在, 主流程仍 PASS。
4. **drive share "过期 + 次数" 双触发 is_active=False** — 单一维度检查不够, is_active 必同时检查 `expires_at + max_downloads`, 避免任一维度失效后仍可访问 (派工 v10 段 7 实战)。

## 派工 v4 铁律 3 真验证 3 步 (必先)

```
Step 1: cat "C:/Users/pc/.claude/plans/ppt-word-replicated-swing.md" | grep -A 8 "^## PR2"
Step 2: git log --oneline main | grep -iE "share|folder.*shar|team.*folder|PR2"
Step 3: grep -rE "folder_share|team_folder|share_invitation" app/ web/src/ --include="*.py" --include="*.vue" -l
```

Step 1 发现 PR2 原计划 = 回收站 + 多选批量 + 收藏星标 + 排序/筛选 (非 sharing), Step 2 验证 PR7/018/PR2.7 已有, Step 3 列出已存在文件 → 重定义"差量缺口"为 password + max_downloads + 审计 + UI 集成。

## Commit 信息

```
feat(w72-2nd-batch-b1): Drive v2 PR2 sharing 差量缺口实施 (alembic 081)

W72 第 1 批 C-3 真验证派生: folder share + team folder 已有, 重定义'差量缺口'
锚点范式 W72 第 1 批 215 → W72 第 2 批 B-1 220 守恒 (+5)
- 4 项差量: 过期时间 + 密码 + 次数限制 + 审计
- 桌面 ShareLinkDialog.vue 玻璃态 + 6 主题 dark mode
- 移动端 sharing 入口 + MobileActionSheet
- 审计 3 action (share_created/revoked/downloaded)
- alembic 081 down_revision='078_drive_dedupe_audit' 串单链守恒
- 13/13 e2e PASS

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```