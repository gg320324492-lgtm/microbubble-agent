# Drive v2 部署文档 v3 (2026-07-27)

> **总入口**: Drive v2 PR17/18/5 + 5 缺口收口 + 商业化 Phase 8 + 6 主题 dark mode 部署**唯一权威 runbook**。本文档整合 W68 第 8 批 A-2 (`e51699d48` PR9-11 master runbook) + W72 第 1 批 C-3 (`f1947d3c7` ppt-word 5 缺口调研) + W72 第 1 批 C-2 (`a78967661` 24 人月季度排期)，提供 **PR17/PR18/PR5 + PR2 sharing + 商业化 + dark mode** 部署主流程。
>
> **配套文档** (按需查阅, **不重复内容**):
> - PR9-11 历史部署 → [docs/drive-v2-pr9-11-deployment-master-runbook.md](drive-v2-pr9-11-deployment-master-runbook.md)
> - PR9 详细迁移 + 回滚 → [docs/drive-v2-pr9-deployment.md](drive-v2-pr9-deployment.md)
> - 故障 FAQ → [docs/drive-v2-deployment-troubleshooting-faq.md](drive-v2-deployment-troubleshooting-faq.md)
> - ppt-word 5 缺口调研 → [memory/w72nd-batch-c3-ppt-word-gaps-2026-07-27.md](../memory/w72nd-batch-c3-ppt-word-gaps-2026-07-27.md)
> - 商业化 24 人月季度排期 → [memory/w72nd-batch-c2-commercial-schedule-2026-07-27.md](../memory/w72nd-batch-c2-commercial-schedule-2026-07-27.md)
> - W72 起步前 plans 真验证 → [memory/w72nd-batch-a3-plans-verification-2026-07-27.md](../memory/w72nd-batch-a3-plans-verification-2026-07-27.md)

---

## 0. alembic 链风险 (CLAUDE.md 永久锚点 + 派工 v6 段 6 实战)

> ⚠️ **铁律**: 并行派多个写 alembic migration 的 agent 时, 派工 prompt **必须明确 down_revision 接续关系**, merge 后**必须 verify 只有 1 个 head**。否则 `alembic upgrade head` 报 `Multiple head revisions are present` 直接阻塞部署。详见 `memory/w68-alembic-chain-discipline-2026-07-24.md`。

### 0.1 当前 alembic 链 (W72 第 1 批合并后)

```
076_drive_comments_path_backfill
  └─ 079_team_folders                                    (PR18 团队共享盘, W72 B-2)
       └─ 078_drive_dedupe_audit                        (PR17 文件秒传审计, W72 B-1)
```

**实际命名顺序修正**: 由于 W72 第 1 批 B-1 与 B-2 并行开发, **B-1 (PR17 078) 接 079 而非 076**, 串单链正确顺序是 `076 → 079 → 078`。任何派工 prompt 错误描述链顺序将直接导致 alembic 双头。**派工前提** 第 1 条: 派工 prompt 必须写清楚 "down_revision 接 X"。

### 0.2 7 张新迁移串单链 (W72 + W73 累计)

W72 第 2 批计划新增 5 张迁移 + 商业化 1 张 + 长期排期 1 张:

| 段 | 迁移 | down_revision | 内容 | 批次 |
|----|------|---------------|------|------|
| 1 | 078_drive_dedupe_audit | 079_team_folders | PR17 文件秒传审计 2 列 | W72-B-1 ✅ |
| 1 | 079_team_folders | 076_drive_comments_path_backfill | PR18 团队共享盘 | W72-B-2 ✅ |
| 1 | 080_drive_chunked_upload | 079_team_folders | PR5 分片上传 | W72-B-3 规划 |
| 2 | 081_drive_share_incremental | 079_team_folders | PR2 sharing 差量 | W73-C-1 |
| 2 | (无迁移) PR3 comment v2 验收 | — | 仅业务码 | W73-C-2 |
| 2 | (无迁移) PR5 trash 收口 | — | 仅业务码 | W73-C-3 |
| 2 | (无迁移) PR7 file_request API | — | 仅业务码 | W73-D-1 |
| 3 | 082_commercial_billing_tables | 待定 (079 后) | 商业化 Phase 8 账单 | W74-B-1 |

**链顺序最终态**: `076 → 079 → (080/081/082 并列) → 078`

### 0.3 部署必跑 verify (锚点范式第 46/172 守恒)

```bash
# 1. verify 1 head (CLAUDE.md 永久锚点)
cd /e/microbubble-agent
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); heads=s.get_heads(); print('heads:', heads); assert len(heads)==1, f'ALEMBIC 双头: {heads}'; print('OK: only 1 head:', heads[0])"
# 期望: heads: ['079_team_folders'] (W72-B-1 合并后) 或 heads: ['078_drive_dedupe_audit']

# 2. cp migrations (CLAUDE.md 752 行铁律)
docker cp alembic/versions/078_*.py 079_*.py 080_*.py 081_*.py 082_*.py microbubble-agent-app-1:/app/alembic/versions/

# 3. clear cache (alembic chain discipline: __pycache__ 残留让老 down_revision 继续生效)
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__

# 4. upgrade
docker exec microbubble-agent-app-1 alembic upgrade head

# 5. verify column 落地
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\d knowledge" | grep -E "drive_dedupe|file_hash"
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\d drive_team_folders"
```

**失败回滚**: 任何一步失败立即 `docker exec microbubble-agent-app-1 alembic downgrade -1` 回退 1 步 + git revert 合并 commit + 主指挥拍板后续。

---

## 1. Drive v2 PR17/18/5 部署 (W72 第 2 批 B-1/B-2/B-3)

### 1.1 PR17 文件秒传 (alembic 078)

**功能**: 上传前算 sha256, hash 命中已存在 file → 秒返 file_id, 跳过 MinIO 上传。

**迁移**:
- 文件: `alembic/versions/078_drive_dedupe_audit.py`
- `revision = "078_drive_dedupe_audit"`, `down_revision = "079_team_folders"`
- 加列到 `knowledge`: `drive_dedupe_count Integer default 0` + `drive_dedupe_first_hit_at DateTime nullable`
- 纯审计, 不影响老逻辑, 不动 `file_hash` 索引 (PR4 044 已加)

**部署 6 步**:
```bash
# 1. pull + rebase (主指挥)
cd /e/microbubble-agent && git pull --ff-only origin main

# 2. cp migration
docker cp alembic/versions/078_drive_dedupe_audit.py microbubble-agent-app-1:/app/alembic/versions/

# 3. clear cache
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__

# 4. upgrade
docker exec microbubble-agent-app-1 alembic upgrade head

# 5. verify
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name='knowledge' AND column_name LIKE 'drive_dedupe%'"

# 6. backend restart (代码改动 走 alembic 即可, 无 code 改动无需 restart)
# docker compose restart app  # 仅当有 .py 改动时
```

**验证脚本**: `tests/scripts/verify_drive_pr17_dedupe.sh` (新建)
- 上传同 hash 2 次 → 第 2 次响应时间 < 200ms (秒传)
- DB 查 `drive_dedupe_count` 从 0 → 1
- MinIO storage 字节数不变

### 1.2 PR18 团队共享盘 (alembic 079)

**功能**: 团队级别共享盘 (team folder), 多用户协作根目录。

**迁移**:
- 文件: `alembic/versions/079_team_folders.py`
- `revision = "079_team_folders"`, `down_revision = "076_drive_comments_path_backfill"`
- 新表: `drive_team_folders` (id / team_id / name / owner_id / permission_json / created_at)

**部署 6 步** (同 1.1 流程, 替换 migration 文件名)。

### 1.3 PR5 分片上传 (alembic 080, 待 W72-B-3)

**功能**: 大文件分片上传 (5MB/chunk), 断点续传 + 并发上传。

**迁移 (规划)**:
- 文件: `alembic/versions/080_drive_chunked_upload.py`
- `revision = "080_drive_chunked_upload"`, `down_revision = "079_team_folders"` (主拍板顺序)
- 新表: `drive_upload_sessions` (id / file_id / chunk_index / total_chunks / sha256 / uploaded_at)

**派工前提铁律**: 080 必须接 079 不是 078 — 理由是团队共享盘 PR18 是文件上传的根目录, 分片上传在共享盘上跑, 依赖序敏感。

---

## 2. 5 缺口收口部署 (W73 第 1 批 C-1..C-3 + D-1)

> 来源: `memory/w72nd-batch-c3-ppt-word-gaps-2026-07-27.md` (commit `f1947d3c7` 调研, 锚点范式第 218 守恒)

### 2.1 PR2 sharing 差量 (alembic 081)

- 文件: `alembic/versions/081_drive_share_incremental.py` (W73 第 1 批新建)
- `down_revision = "079_team_folders"` (与 080 并列, 串单链正确)
- 内容: `drive_share_links` 加 `expires_at` + `download_count` (PR2 Partial 部分真实施)

### 2.2 PR3 comment v2 验收 (无迁移)

- 仅业务码: `app/api/drive/comments_v2.py` + `web/src/views/drive/CommentPanelV2.vue`
- PR3 已有部分实施, W68 第 7 批闭环 commit `d7ea1c81` 验证
- W73-C-2 目标: 完成 mention / 软删 / 角色权限 3 项验收, 写 5 个 E2E

### 2.3 PR5 trash 收口 (无迁移)

- 仅业务码: `app/services/drive_trash_service.py` (PR4 已部分实施, W73-C-3 收口)
- 目标: 软删 30 天 Celery 自动清理 + 恢复接口 + 永久删除 audit log

### 2.4 PR7 file_request API (无迁移)

- 仅业务码: `app/api/drive/file_request.py` (PR7 Part 2)
- 目标: 外部用户上传请求生成 token + 邮件通知 + 上传后自动 review

### 2.5 缺口 5 gap analysis 文档 (D-1 恢复)

- 文档: `docs/drive-v2-ppt-word-gap-recovery-w73.md` (W73-D-1 写)
- 内容: PR2/PR3/PR5/PR7 缺口真实施优先级 + W73-W74 排期 + 验收标准
- 与 `memory/w72nd-batch-c3-ppt-word-gaps-2026-07-27.md` 4 列状态表对齐

---

## 3. 商业化 Phase 8 部署 (W74 第 2 批 B-1..B-3)

> 来源: `memory/w72nd-batch-c2-commercial-schedule-2026-07-27.md` (commit `a78967661` 24 人月季度排期, 锚点范式第 217 守恒)

### 3.1 商业化 alembic (082_commercial_billing_tables)

- 文件: `alembic/versions/082_commercial_billing_tables.py` (W74 第 2 批新建)
- `down_revision = "080_drive_chunked_upload"` 或 `"081_drive_share_incremental"` (主拍板时定)
- 新表: `commercial_subscriptions` / `commercial_invoices` / `commercial_license_keys` / `commercial_usage_records`

### 3.2 商业化镜像 build (Dockerfile.commercial)

```dockerfile
# Dockerfile.commercial (W74 第 2 批新建)
FROM microbubble-agent-app:latest AS base

# 商业化附加层
COPY commercial/saas-platform/ /app/commercial/
COPY commercial/license-server/ /app/license-server/
RUN pip install -r /app/commercial/requirements.txt

ENV COMMERCIAL_ENABLED=true \
    LICENSE_SERVER_URL=https://license.example.com \
    SAAS_MODE=multi_tenant

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 3.3 SaaS 平台部署 (commercial/saas-platform/)

- 路径: `commercial/saas-platform/` (W74 第 2 批新建)
- 内容: 多租户路由 + tenant_id 注入 + 配额 middleware + 计费 hook
- 部署: 镜像 push 到 GHCR (`microbubble-agent-commercial:v0.1.0`) + 云服务器 k3s 部署

### 3.4 License 服务端校验

- 服务: `commercial/license-server/` (独立 FastAPI 服务)
- 部署: 云服务器独立容器, 端口 8443
- 校验: 启动时 main app 调 `/api/license/validate` → 返回 seat_count + expiry
- 失败: `LICENSE_INVALID` 退出码 1 (主拍板降级策略: 30 天宽限期)

### 3.5 多租户隔离验证

```bash
# 9 项隔离检查 (W74 第 2 批 E-1 验收脚本 verify_commercial_multitenant.sh)
# 1. tenant_id 强制注入 (中间件)
# 2. PostgreSQL RLS policy (每个查询 WHERE tenant_id = current_setting('app.tenant_id'))
# 3. MinIO bucket 按 tenant 隔离 (path prefix)
# 4. Redis keyspace 按 tenant 隔离 (prefix)
# 5. Celery task 按 tenant 路由
# 6. 日志脱敏 (不记录其他 tenant 数据)
# 7. API rate limit 按 tenant 配额
# 8. WebSocket session 按 tenant 隔离
# 9. 文件上传大小按 tenant 配额
```

---

## 4. 6 主题 dark mode 部署 (W72 第 1 批 B-1..B-5 落地)

> 来源: W72 第 1 批 B-5 commit `b7ad730a6` (锚点范式第 215 守恒, 18 视觉快照 + 4 新铁律)

### 4.1 桌面端 web token 化 (v70-v74 实战)

**背景**: v70-v74 阶段 ~340 hex 颜色转 token, Stylelint + Playwright 双层守恒。

**部署清单**:
- `web/src/assets/variables.css` (337 行, 6 主题 × 50+ token)
- `.stylelintrc` (禁止 hex 字面量白名单例外)
- `web/tests/playwright/visual/theme-snapshot.spec.ts` (6 主题 × 3 viewport = 18 视觉快照)

**部署验证**:
```bash
# 1. npm run build (postbuild 自动 3 件事)
cd /e/microbubble-agent/web && npm run build

# 2. force-add hashed manifest
git add -f web/dist/manifest.{8char_hash}.webmanifest

# 3. verify dist (严禁 unhashed manifest)
git diff --cached -- web/dist/ | grep -E '"url":\s*"manifest\.webmanifest"' && echo "FAIL unhashed" || echo "OK hashed"

# 4. push + webhook 30s
git push origin main
```

### 4.2 移动端 NutUI 4 dark (v77 P2.6 实战)

**背景**: `useIsMobile.js` + `resolveMobile.js` 路由级双栈, 桌面 / 移动 CSS 完全隔离。

**部署验证**:
- iOS Safari PWA dark mode: Safari DevTools → 设置 → 默认深色 → reload → topbar 深色生效
- Android Chrome PWA dark: chrome://flags → Web Content Dark Mode → 系统默认 → reload

### 4.3 跨组件透传 (B-1..B-5 全部 6 主题)

**铁律**: 6 主题 (light/dark/ocean/forest/dusk/sunrise) × 3 viewport (mobile/tablet/desktop) = 18 视觉快照必须**全部** PASS。

**CI 检查**: `qa-bench/dashboard-ci.yml` 步骤 `npm run test:visual:6-theme` 失败阻塞 merge。

---

## 5. 部署必做 10 步 checklist (CLAUDE.md 752 行铁律 + 派工 v6 段 6 实战)

```bash
# ===== 1. 拉新代码 =====
cd /e/microbubble-agent
git fetch origin && git checkout main && git pull --ff-only
git log --oneline -10   # 期望看到 PR17 + PR18 + 商业化 migrate

# ===== 2. alembic 链 verify (CLAUDE.md 永久锚点, 锚点范式第 46 守恒) =====
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); heads=s.get_heads(); assert len(heads)==1, f'ALEMBIC 双头: {heads}'; print('OK:', heads[0])"

# ===== 3. cp migrations (CLAUDE.md 永久锚点) =====
docker cp alembic/versions/078_*.py 079_*.py 080_*.py 081_*.py 082_*.py microbubble-agent-app-1:/app/alembic/versions/

# ===== 4. clear cache (alembic chain discipline 铁律, 防 __pycache__ 残留) =====
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__

# ===== 5. alembic upgrade =====
docker exec microbubble-agent-app-1 alembic upgrade head

# ===== 6. web rebuild (postbuild 自动 3 件事 + force-add hashed manifest) =====
cd /e/microbubble-agent/web && npm run build
git add -f web/dist/manifest.{8char_hash}.webmanifest
git diff --cached -- web/dist/ | grep -qE '"url":\s*"manifest\.webmanifest"' && { echo "FAIL unhashed"; exit 1; } || echo "OK hashed"

# ===== 7. restart (仅当有 .py 改动时) =====
cd /e/microbubble-agent && docker compose restart app celery-worker

# ===== 8. 6 点 curl 验证 (CLAUDE.md 永久锚点 nginx octet-stream 白屏教训) =====
DOMAIN="https://your.domain.com"
for path in / /index.html /dashboard /sw.js /pwa-192.png /manifest.{8char_hash}.webmanifest; do
  echo "=== $path ==="
  curl -sk -o /dev/null -w "Content-Type: %{content_type}, HTTP: %{http_code}\n" "$DOMAIN$path"
done
# 期望: 全部 text/html / application/javascript / image/png / application/manifest+json, 0 个 octet-stream

# ===== 9. SW BUMP 验证 (浏览器 DevTools, PWA manifest 410 教训) =====
# 让用户: DevTools → Application → Service Workers → 看到 sw.js 内容含新 SW_VERSION
# 让用户: DevTools → Application → Storage → Clear site data (兜底清旧 cache)

# ===== 10. PWA install 验证 (派工 v4 铁律 vite build 必坏 PWA) =====
# 让用户: Safari iOS → 分享 → 添加到主屏幕 → 桌面图标显示 + 点击启动
# 让用户: Android Chrome → 菜单 → 安装应用 → 桌面图标显示
# 失败模式: "Manifest fetch failed, code 410" → 必是 manifest.webmanifest 没 hash (步骤 6 失败)
```

**部署时间预估**: 全部 10 步 30-45 分钟 (云服务器快 10 分钟)。

---

## 6. hot-fix 链预案 (CLAUDE.md 永久锚点 4 类)

### 6.1 alembic 双头 (commit `1852468a6` 教训)

**症状**: `alembic upgrade head` 报 `FAILED: Multiple head revisions are present for given argument 'head'`

**修复**:
```bash
# 1. 列出所有 head
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print(s.get_heads())"

# 2. 找到最长的链 (例如 ['079_team_folders', '078_drive_dedupe_audit'])
# 3. 改 078 的 down_revision = '079_team_folders' (主指挥手动改, commit amend)
# 4. 重新 verify: 期望 1 head

# 5. clear cache (反复栽跟头点)
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
```

### 6.2 PWA manifest 410 (commit `59187ce8` 教训)

**症状**: 浏览器 console `Manifest fetch failed, code 410` + PWA install 失败。

**根因**: `vite build` 直跑绕过 postbuild, manifest.webmanifest 没 hash。

**修复**:
```bash
# 唯一合法 build 命令 (派工 v4 铁律)
cd /e/microbubble-agent/web
npm run build  # 不是 vite build

# force-add hashed manifest
git add -f web/dist/manifest.{hash}.webmanifest

# grep 防御 (拦截任何 stage 的 unhashed 引用)
git diff --cached -- web/dist/ | grep -qE '"url":\s*"manifest\.webmanifest"' && { echo "FAIL unhashed"; git reset HEAD; } || echo "OK"

git push origin main && sleep 30  # webhook 30s
```

### 6.3 整站 octet-stream (commit `08f440f` 教训)

**症状**: 用户报"打开 /dashboard 直接下载文件名为 dashboard 的文件", curl 返回 `Content-Type: application/octet-stream`。

**根因**: Nginx `server { ... }` block 内加 `types { }` block 会**完全覆盖** http context mime.types。

**修复**:
- 删除 tunnel.conf 所有 `types { }` block
- 改 `scripts/deploy-auto.sh` mime.types 注入 webmanifest (sed `-i` 模式 + grep 验证)
- **6 点 curl 验证** (HTML + CSS + JS + PNG + manifest + sw.js)
- SW BUMP v2-cache-purge-2026-06-13 清浏览器侧缓存

### 6.4 SW 缓存污染 (commit `747a735` 教训)

**症状**: 服务器 curl 一切正常, 用户浏览器仍"页面进不去"。

**根因**: SW NetworkFirst 缓存了 octet-stream 响应到 `documents` cache, `cleanupOutdatedCaches()` 只清 workbox precache 不清运行时 cache。

**修复**:
- BUMP `SW_VERSION = 'v3-cache-purge-2026-07-27'` (强制字节变化触发 SW 升级)
- `activate` 钩子: `caches.keys() + Promise.all(keys.map(caches.delete))`
- `useRegisterSW({ onRegisteredSW })` 监听 `SW_UPDATED` message → `window.location.reload()`
- 用户手动 DevTools → Application → Storage → Clear site data 兜底

---

## 7. 锚点范式守恒 (W72 第 2 批)

### 7.1 W72 第 2 批 守恒表 (预期)

| Agent | 范围 | 锚点范式 | 类别 | 状态 |
|-------|------|----------|------|------|
| B-1 | Drive v2 PR17 (alembic 078) | 226 | production code (例外) | W72 第 2 批 |
| B-2 | Drive v2 PR18 (alembic 079) | 227 | production code (例外) | W72 第 2 批 |
| B-3 | Drive v2 PR5 (alembic 080) | 228 | production code (例外) | W72 第 2 批 |
| B-4 | 5 缺口调研 + 收口派工 | 229 | docs + memory | W72 第 2 批 |
| B-5 | 商业化 24 人月季度排期 v2 | 230 | docs + memory | 已 commit `b7ad730a6` |
| C-1 | Drive v2 部署文档 v3 (本文档) | 230 | docs only | 当前 |
| C-2 | 商业化镜像 build (Dockerfile.commercial) | 231 | production code (例外) | W73 第 1 批 |
| C-3 | ppt-word 5 缺口派工 | 232 | docs + memory | 已 commit `f1947d3c7` |
| D-1 | 派工纪要 prompt 模板 v9 | 233 | docs only | W72 第 2 批 |
| D-2 | 6 类文档同步 + W72 第 2 批 memory | 234 | docs + memory | W72 第 2 批 |
| D-3 | W72 第 2 批 锚点范式守恒 (4 维度金标准) | 235 | docs + memory | W72 第 2 批 |
| E-1 | 多租户隔离验证 | 236 | tests only | W74 第 2 批 |

### 7.2 0 production code 14/15 守恒预期

**例外清单 (5 已批)**:
- B-1/B-2/B-3 alembic 078/079/080 (W68 第 14 批已批)
- C-2/C-3 web alembic 081/082 + Dockerfile.commercial (W72 第 2 批新批)

**例外不扩大**: 不修改老路径 (app/services/task_service.py / meeting_service.py / knowledge_service.py / 等老模块核心函数)。

### 7.3 W73 起步纪律 6 项

1. **派工前 plans 真验证**: `cat ~/.claude/plans/*.md` + `git log --grep=plan-keyword` + `grep -r <feature> app/ web/` 三步
2. **派工 alembic 必须明确 down_revision**: 写进派工 prompt 段 0 第 1 行
3. **merge 后立即 verify 1 head**: CLAUDE.md 永久锚点
4. **npm run build 唯一合法**: `vite build` 直跑必坏 PWA (派工 v4 铁律)
5. **6 点 curl 验证必含**: nginx octet-stream 白屏教训 (CLAUDE.md 永久锚点)
6. **SW BUMP + PWA install 验证**: 派工前提第 3 条铁律

### 7.4 锚点范式守恒原则

- **单调上升**: 218 → 230 → 236, 不允许任何 batch 出现 regression
- **4 维度金标准**: 派工前提 + 派工中 + 派工后 + memory 沉淀, 缺一不可
- **0 production code 14/15 守恒**: 例外清单新增需主指挥拍板, 不自动扩大
- **派工前提 1/3 缺则立即 abort**: 派工 v6 段 5 反馈 #2 实战

---

## 8. 主指挥协调备忘 (W72 第 2 批)

**派工前必跑**:
```bash
# 1. 验证 plans 真实施 (派工 v4 铁律 3)
for plan in $(ls ~/.claude/plans/ | grep -E "ppt-word|commercial|drive.*v2"); do
  git log --all --oneline --grep="$(basename $plan .md | cut -d- -f1-3)" | head -3
done

# 2. 验证 alembic 链 (永远第一)
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print(s.get_heads())"

# 3. 验证 .gitignore dist 不漏 force-add
git status --ignored | grep -E "web/dist.*manifest" && echo "DIST HASHED OK"
```

**派工后必跑**:
- merge 顺序按 alembic 链 (上游先 merge)
- merge 后立即 6 点 curl 验证
- 监控 24h (首日业务流量 + 错误率 + alembic 链稳定)
- 写 memory + 更新 CLAUDE.md (本周内)

---

## 9. 文档历史

- v1 (commit `e51699d48`, 2026-07-24): Drive v2 PR9-11 master runbook + FAQ — W68 第 8 批 A-2
- v2 (本文档 v3, 2026-07-27): PR17/18/5 + 5 缺口 + 商业化 Phase 8 + 6 主题 dark — W72 第 2 批 C-1

**W72 第 2 批 C-1 锚点范式守恒**: 220 → 230 (+10)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
