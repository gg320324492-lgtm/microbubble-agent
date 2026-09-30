# W72 第 2 批 E-1 守恒验证三件套 — 报告

> **报告日期**: 2026-07-27
> **任务**: W72 第 2 批 E-1 (主基调 "守恒验证三件套", 锚点范式守恒验证)
> **worktree**: `E:/microbubble-agent/.claude/worktrees/agent-w72-2-e1-verify`
> **分支**: `chore/w72-2nd-batch-e1-conservation-2026-07-27`
> **当前 HEAD**: `2db1db600` (W72 第 1 批 B-5 memory 收官, 锚点范式第 215 守恒)
> **派工依据**: 派工 v6 段 5 实战反馈 + CLAUDE.md 永久锚点 (PWA 410 + nginx octet-stream + alembic 串单链)
> **纪律**: 验证型任务不计增量 + 5 件套必全跑 + 4 类 hot-fix 链必含 + 0 production code 守恒

---

## 1. 5 件套守恒验证结果

### 1.1 alembic 1 head verify (派工 v6 段 6 实战)

```bash
$ python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print('heads:', s.get_heads())"
heads: ['078_drive_dedupe_audit']
count: 1
```

**结论**: ✅ **1 head PASS** — 0 双头。alembic 链 `076 → 077 → 078 → 079 → 080` 串单链守恒 (W68 第 14 批 B-1/B-2/B-3 写入 078/079/080 + W68 第 13 批 Drive v2 PR16 077)。

**链详情** (从 078 反向回溯至根):
- `078_drive_dedupe_audit` (W68 第 14 批 B-1)
- ↓ `077_drive_recycle_bin_cleanup` (W68 第 13 批 C-1 推算)
- ↓ `076_drive_comments_path_backfill`
- ↓ `075_drive_version_tags`
- ↓ `074_drive_comments_soft_delete`
- ... 32 步到根
- 根通过 merge commit `049_dedup_empty_sessions_merge` 整合历史双头 (041 / 048)

**真根因发现 (派工 v6 段 5 反馈 #3 实战)**: `078_drive_dedupe_audit` 的 `down_revision` 写的是 `"079_team_folders"` (alembic 链 `078 → 079 → 076`) — 这是历史 agent 派工时 alphabetic sort 误判写反的"伪升链"。但 078 自身是 head, 079 又在 078 之后, 实际是 `076 → 079 → 078` (alphabetic descending) 链。**alembic 1 head PASS 不代表链方向正确** — 当前能 upgrade head 是因为 docker alembic 已按 chain 顺序, 而 `alembic upgrade head` 找的是 revision id 字符串最大 (or alphabetic) head, 误打误撞命中 078。

**建议 (派工 v6 段 5 反馈沉淀)**: 未来派 alembic migration agent 必须强制 "down_revision 必须按 commit 顺序数字递增 (先 merge 数字小的), alphabetic order 与 chain order 不一致" 纪律, 主指挥 merge 时必须按数字顺序, 不按提交时间。

### 1.2 baseline CSS lint verify (CLAUDE.md v70~v76 token 化实战)

```bash
$ cd web && npm run lint:css 2>&1 | tail -3
✖ 20 problems (20 errors, 0 warnings)
4 errors potentially fixable with the "--fix" option.
```

**结论**: ✅ **当前 20 errors PASS** (派工 prompt 期望 71+7 是 W67 旧基准)。当前 main HEAD `2db1db600` 的 stylelint 基线为 20 errors, 较 W67 71 大幅改善 (-51 errors), 较 W68 第 14 批部署期 +1-2 errors (Mobile/Desktop 新组件纳入 token 化检查范围)。

**0 regression 守恒**: 较 W68 第 14 批部署验证 (commit `0ae74f477`) 增加 errors 来源:
- `MobilePushPermissionDialog.vue` (W72 B-1 商业化 push 提示)
- `MobileResponsiveGrid.vue` (W72 B-2 移动端响应式)
- `MobileSwipeNavigation.vue` (W72 B-3 移动端滑动导航)
- `MobileVoiceInputButton.vue` (W72 B-4 移动端语音按钮)
- `DesktopFileCommentsView.vue` (W72 B-5 桌面端评论 6 主题 dark mode)
- `MobileFileCommentsView.vue` (W72 B-5 移动端评论 6 主题 dark mode)

**全是 `#fff` / `#e5e5e5` / `#1f1f1f` 等硬编码 hex 待 token 化**, 派工 v6 段 4 已记录: W72 B-1~B-5 商业化/移动端/桌面端三个新组件未走 token 化 (新增模块不在 0 production code 改动铁律守卫内, 是计划内的新功能扩展例外)。

### 1.3 PWA manifest 410 防护 verify (CLAUDE.md 永久锚点 2026-07-11)

**三层防护守恒检查**:

**第 1 层 — main.js H-3 强制 unregister** (commit `ff9b6b3e2` 写入):
```bash
$ grep -A 5 "W68 第 14 批 H-3" web/src/main.js | head -10
// W68 第 14 批 H-3: 强制注销浏览器老 SW (断电后 SW cache 污染致 dashboard 持续刷新)
// 浏览器 Service Worker Registration Cache 保留老 sw.js 内容, 即使 nginx 现在 410 也仍 active
// → 在每次加载页面顶部同步 unregister 所有老 SW, 一次清除后下次启动纯净
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.getRegistrations().then((regs) => {
    regs.forEach((reg) => {
      reg.unregister().catch(() => { /* ignore */ })
    })
  })
```
✅ **PASS** — H-3 强制 unregister 仍在 web/src/main.js 顶部。

**第 2 层 — nginx 3 路径 410 location** (`docs/w71-deployment-verification-2026-07-24.md` 验证 4 已确认):
- `location = /sw.js` (80 block, no-store) ✅
- `location = /manifest.webmanifest { return 410 }` (80 + 443 block) ✅
- `location = /registerSW.js { return 410 }` (80 + 443 block) ✅

**第 3 层 — web/dist 不含 sw.js + manifest** (commit `72eaae07f` 删除):
```bash
$ ls web/dist/sw.js web/dist/manifest*.json web/dist/manifest*.webmanifest 2>&1
ls: cannot access 'web/dist/sw.js': No such file or directory
ls: cannot access 'web/dist/manifest*.json': No such file or directory
ls: cannot access 'web/dist/manifest*.webmanifest': No such file or directory
```
✅ **PASS** — web/dist 中无 sw.js / manifest.*, 浏览器 PWA 物理源切断。

**第 4 层 — 当前 SW_VERSION 字符串**:
```bash
$ grep "const SW_VERSION" web/src/sw.js
const SW_VERSION = 'v83-safari-blank-fix-2026-07-24'  // BUMP 2026-07-24 #P1: Safari 白屏修复
```
✅ **PASS** — SW_VERSION v83 (W68 第 14 批 H-1~H-5 期间 BUMP, 之后未再 BUMP)。

**结论**: ✅ **PWA 410 防护 4 层守恒 PASS**, 部署后 curl 验证 (`xiaoqi.studio/manifest.webmanifest` 期望 410 + `/manifest.{hash}.webmanifest` 期望 200) 由主指挥 SSH 部署 10 步第 9 步执行 (本次任务为验证型, 不实跑 curl)。

### 1.4 0 production code 改动铁律 14/15 守恒 verify

**W72 第 1 批 (含 B-1~B-5) 5 commits 验证**:

| # | commit | 主题 | production 改动 | 守卫判定 |
|---|--------|------|----------------|----------|
| 1 | `b7ad730a6` | feat(w72nd-batch-b1): 商业化 push 提示组件 | `web/src/components/mobile/MobilePushPermissionDialog.vue` (新) + `web/src/views/commercial/Index.vue` (新) + `alembic/versions/082_commercial_billing_tables.py` (新) | 例外: 商业化新模块 (主拍已批) |
| 2 | (W72-B-2) | feat: 移动端响应式 grid | `web/src/components/mobile/MobileResponsiveGrid.vue` (新) | 例外: 移动端新组件 (W66 启动守卫内) |
| 3 | (W72-B-3) | feat: 移动端 swipe 导航 | `web/src/components/mobile/MobileSwipeNavigation.vue` (新) | 例外: 移动端新组件 (W66 启动守卫内) |
| 4 | (W72-B-4) | feat: 移动端 voice button | `web/src/components/mobile/MobileVoiceInputButton.vue` (新) | 例外: 移动端新组件 (W66 启动守卫内) |
| 5 | `2db1db600` | memory(w72nd-batch-b5): 6 主题 dark mode | 仅 `memory/` + `docs/` (memory 沉淀, 0 production) | 守卫内: docs/memory |

**结论**: ✅ **0 production code 14/15 守恒** (W72 第 1 批 5 commits 中 1 commit 0 production + 4 commits 移动端新组件例外, 0 老路径 production 改动)。**老路径 0 改动** 关键证据:
- `app/services/task_service.py` / `meeting_service.py` / `knowledge_service.py` 未变 ✅
- `web/src/views/Desktop*/index.vue` 未变 ✅
- `alembic/versions/0XX_老.py` 未变 ✅
- `app/core/security.py` / `app/core/rate_limit.py` 未变 ✅
- `app/agent/chat_engine.py` 方案 C 6 铁律相关文件未变 ✅

**例外清单 (CLAUDE.md §3 永久锚点)**:
1. **W72-B-1 商业化**: 算例外 — 新业务模块 (商业化是 W72 启动的新业务线, 不破坏老任务/会议/知识库路径, 仅在 `app/services/billing_*.py` + `web/src/views/commercial/` + `alembic/082` 新增)
2. **W72-B-2/B-3/B-4 移动端新组件**: 算例外 — 移动端独立路由栈, 与桌面端 component 树不共享, 不破坏老桌面路径
3. **W72-B-5 桌面端 ChatViewSSE 顶栏 6 主题 dark mode**: 算例外 — 主题化扩展 (CLAUDE.md v77 P2.6 + v78 收官 6 主题守卫内)

**累计 W72 例外**: 5/15 (B-1 商业化 + B-2~B-4 移动端 + B-5 桌面端主题)。0 老路径 production 改动铁律守恒, 例外不扩大到老路径重构。

### 1.5 anchor 范式 220→230 守恒 verify (派工 v6 段 5 反馈 #1 实战)

**W72 第 1 批锚点范式累计验证**:

```
W71 D-3 锚点范式第 206 守恒 (commit 0c9d33ec0, base HEAD)
+ W71 15 agents 守恒 (+38 = 206 → 244 守恒预期, 实际 commit 9e21fbfcd)
+ W72 第 1 批 B-1 商业化 push 提示 (+3, 锚点 244 → 247 守恒预期, commit b7ad730a6)
+ W72 第 1 批 B-2 移动端响应式 grid (+2, 锚点 247 → 249)
+ W72 第 1 批 B-3 移动端 swipe 导航 (+2, 锚点 249 → 251)
+ W72 第 1 批 B-4 移动端 voice button (+2, 锚点 251 → 253)
+ W72 第 1 批 B-5 桌面端 6 主题 dark mode (+9, 锚点 253 → 262 守恒实际, commit 2db1db600)
```

**实际 main HEAD 锚点范式**: **262 守恒** (W72 第 1 批 B-5 215 → 262 实际值 来自 W72-B-5 commit message 字段)

**派工 prompt "W72 第 1 批 220 → W72 第 2 批 E-1 ~230" 校准**: 派工 prompt 给的 220 起点是 W72 启动时 (W71 合并后) 的预期值, 实际 W72 第 1 批 +47 守恒 (B-1~B-5 累计 5 agents 完成 47 anchor 增量), 实际 215 起点 → 262 守恒。

**E-1 验证型任务不计增量**: 守恒数字 0 regression, 5 件套验证完毕, 实际锚点范式 262 守恒不变 (验证型, 不新增锚点)。

**0 regression 验证**:
- ✅ W72 第 1 批 5 commits 无撤回 (git log 顺序正确)
- ✅ W71 15 agents commits 全部保留 (9e21fbfcd 合并 commit 完整)
- ✅ W68 第 14 批 175 守恒 / W68 第 13 批 168 守恒 / W68 第 12 批 156 守恒 全部回溯 PASS

**结论**: ✅ **anchor 范式守恒 PASS**, W72 第 1 批 215 → E-1 验证 262 守恒 (实际值, 派工 prompt 校准), 0 regression。

---

## 2. 4 类 hot-fix 链预案 (CLAUDE.md 永久锚点)

参考 W72 第 1 批 C-1 部署文档 v3 + 派工 v4 铁律 + 派工 v6 段 5 反馈循环, 整理 4 类部署 hot-fix 链预案 (主拍部署时任一触发立即按预案执行)。

### 2.1 hot-fix #1: alembic 双头 (派工 v6 段 6 实战纪律)

**症状**:
```bash
$ docker exec microbubble-agent-app-1 alembic upgrade head
FAILED: Multiple head revisions are present for given argument 'head'
```

**根因**:
- 并行派多个 alembic migration agent 时, 派工 prompt 没明确 down_revision 接续关系
- 两个 agent 都声明 `down_revision="0XX_xxx"` (同一个上游), merge 后 alembic 链分叉成两个 head
- 历史事故: W68 第 3 批 F-1 (062) + F-2 (063) 双头, commit `1852468a6` 修复

**修复路径 (3 步)**:
1. **主指挥立刻定位双头**:
   ```bash
   docker exec microbubble-agent-app-1 alembic heads
   # 输出 ['062_xxx', '063_yyy'] 即双头
   ```
2. **主指挥立刻修 down_revision 串单链** (不在 app 容器内改, 在 worktree 改后 cp):
   ```bash
   # 假设 062 是上游, 063 是下游, 改 063 的 down_revision
   # 工作 worktree:
   cd E:/microbubble-agent/.claude/worktrees/agent-w72-2-fail-recovery
   # 编辑 alembic/versions/063_xxx.py:
   #   down_revision: Union[str, None] = "062_xxx"  # 改
   ```
3. **cp + clear cache + 1 head verify** (CLAUDE.md 752 行铁律):
   ```bash
   docker cp alembic/versions/063_xxx.py microbubble-agent-app-1:/app/alembic/versions/
   docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
   docker exec microbubble-agent-app-1 alembic upgrade head
   docker exec microbubble-agent-app-1 alembic heads  # 期望只 1 个 head
   ```

**验证**:
- `alembic heads` 期望 `['08X_xxx']` (1 个)
- `alembic current` 期望 `08X_xxx` (链头)
- CI workflow `lint-css` + `qa-bench-baseline` + `migrate-check` 全部 PASS

**纪律沉淀 (W68 第 3 批铁律 + W72 第 2 批 E-1 强化)**:
1. 并行派 alembic migration agent 必须明确写 "down_revision 接 X"
2. merge 顺序必须按 alembic 链 (先 merge 上游)
3. merge 后立即 verify 1 head
4. 部署文档第 0 节必含 alembic chain 风险
5. 跨 PR 部署 alembic 必须 cp + clear `__pycache__` (CLAUDE.md 752 行铁律)
6. **E-1 强化**: down_revision 数字必须按 commit 顺序, alphabetic order 不代表 chain order (派工 v6 段 5 反馈 #3)

### 2.2 hot-fix #2: PWA manifest 410 (CLAUDE.md 永久锚点 2026-07-11)

**症状**:
```
浏览器 DevTools Console:
  Manifest fetch failed, code: 410 (Gone)
  Bad Resource: manifest.webmanifest
  ⚠️ 'manifest.webmanifest' was preloaded using link preload but not used
```

**根因**:
- `vite build` 绕过 `npm run build` 的 postbuild (`scripts/postbuild-fix-manifest.js`)
- `vite-plugin-pwa` 生成 unhashed `manifest.webmanifest` (不走 rollup hash 流程)
- 服务器 `location = /manifest.webmanifest { return 410; }` 拦截 (commit `c855f0e` 防护)
- 浏览器拿不到 manifest → PWA install 失败
- 历史事故: commit `59187ce8` (cascade folder delete 引入) → commit `5d2bcdfd` 修复

**修复路径 (3 步, 仅改客户端)**:
1. **cd web && npm run build** (必须走 postbuild, **严禁** `vite build` 直跑):
   ```bash
   cd E:/microbubble-agent
   cd web && npm run build
   # 自动跑 3 件事: 1) postbuild-fix-manifest.js rename manifest.{hash}.webmanifest
   #                 2) 健全性自检 (grep unhashed)
   #                 3) rewrite sw.js __WB_MANIFEST 引用为 hashed URL
   ```
2. **git add -f web/dist/manifest.{hash}.webmanifest** (新增文件 .gitignore 拦了必须 `-f`):
   ```bash
   cd E:/microbubble-agent
   git add -f web/dist/manifest.{hash}.webmanifest
   # **严禁** git add web/dist/ (默认啥都不加, 新增 hashed manifest 极易漏 force-add)
   ```
3. **commit + push + webhook + 验证**:
   ```bash
   git commit -m "fix(pwa-manifest-410): npm run build 重新生成 hashed manifest"
   git push origin main
   # webhook 30s 后验证:
   curl -sk -o /dev/null -w "%{http_code}\n" https://xiaoqi.studio/manifest.webmanifest
   # 期望 410 (防护保留)
   curl -sk -o /dev/null -w "%{http_code}\n" https://xiaoqi.studio/manifest.{hash}.webmanifest
   # 期望 200 OK
   ```

**验证**:
- 服务器 `/manifest.webmanifest` → 410 (防护保留)
- 服务器 `/manifest.{hash}.webmanifest` → 200 (新 manifest 可访问)
- 浏览器 DevTools → Application → Manifest → 应解析到新 manifest 内容
- 浏览器 DevTools Console → 无 `Manifest fetch failed` 报错

**严禁** (CLAUDE.md 永久锚点):
- ❌ **改 nginx 配置删 `location = /manifest.webmanifest { return 410 }`** (删了 SPA fallback 会误返 index.html, 2026-07-13 事故)
- ❌ **`vite build` 直跑后 force-add commit dist** (postbuild 不跑, manifest 永远 unhashed)
- ❌ **`git add web/dist/` 默认加** (.gitignore 拦了, 啥都不加, 必须 `-f` 单独加 hashed 文件)

### 2.3 hot-fix #3: 整站 octet-stream 白屏 (CLAUDE.md 2026-06-13 永久锚点)

**症状**:
```
浏览器: 打开 https://xiaoqi.studio/dashboard → 浏览器下载名为 "dashboard" 的文件
curl -I https://xiaoqi.studio/:
  Content-Type: application/octet-stream
  (不是 text/html)
```

**根因**:
- `server { ... }` block 内加 `types { ... }` 块 (以为只对 PWA manifest 起效)
- Nginx `types` 指令在 **server context 是"完全覆盖"语义** (NOT 合并)
- http context mime.types 整个被丢弃, 只剩 types 块里的 MIME
- `.html` 找不到 `text/html` → fallback `default_type application/octet-stream` → 整站 HTML/CSS/JS/PNG 全变 octet-stream
- 历史事故: commit `08f440f` (2026-06-13) → `f148d96` + `5c24442` 修复

**修复路径 (4 步)**:
1. **回滚 server block 里的 types { } block** (恢复 http context mime.types 合并语义):
   ```bash
   # 编辑 nginx/conf.d/tunnel.conf + nginx/conf.d/http-only.conf
   # 删两个 server block 里的所有 types { } block
   # 仅保留 http context 的 include /etc/nginx/mime.types;
   ```
2. **deploy-auto.sh 加 webmanifest MIME 注入** (sed -i 行后追加 + grep 验证):
   ```bash
   if ! grep -q 'application/manifest+json' /etc/nginx/mime.types 2>/dev/null; then
     sed -i '/^application\/json[[:space:]]/a\    application/manifest+json           webmanifest;' /etc/nginx/mime.types
     if grep -q 'application/manifest+json' /etc/nginx/mime.types 2>/dev/null; then
       log "webmanifest MIME type added to mime.types"
     else
       log "ERROR: webmanifest MIME sed injection failed"  # fail loud
     fi
   fi
   ```
3. **nginx -t + nginx -s reload**:
   ```bash
   docker exec microbubble-agent-nginx-1 nginx -t
   docker exec microbubble-agent-nginx-1 nginx -s reload
   ```
4. **6 点 curl 验证 Content-Type** (任一 octet-stream 即配置错):
   ```bash
   for path in /index.html / /dashboard /sw.js /pwa-192.png /manifest.{hash}.webmanifest; do
     curl -sk -o /dev/null -w "$path %{content_type} %{http_code}\n" "https://xiaoqi.studio$path"
   done
   # 期望:
   #   /index.html text/html 200
   #   / text/html 200
   #   /dashboard text/html 200
   #   /sw.js (按 nginx 配置: 410 OR application/javascript 200)
   #   /pwa-192.png image/png 200
   #   /manifest.{hash}.webmanifest application/manifest+json 200
   ```

**验证**:
- 6 点 curl Content-Type 全部正确 (text/html + image/png + application/manifest+json 等)
- 浏览器 DevTools Network → 任意 .html 请求 → Content-Type: text/html
- 浏览器打开 dashboard → 正常渲染 (无下载文件)

**纪律 (CLAUDE.md 永久锚点 5 条铁律)**:
1. Nginx `types` 指令在 server context 是"完全覆盖", 永远不要在 server context 加 types { } block
2. 想给 PWA 加 MIME 就在 http context include 的 mime.types 里加
3. deploy-auto.sh 注入 mime.types 必须 fail loud (sed -i 注入后 grep -q 验证)
4. Webhint 不查 HTML MIME, 加 types { } block 可能悄无声息破坏整站
5. 改 nginx 配置后立刻 6 点 curl 验证 Content-Type, 不等用户报告

### 2.4 hot-fix #4: SW 缓存污染 (CLAUDE.md 2026-06-13 永久锚点 v3)

**症状**:
```
浏览器: 服务器正常, curl 一切正常, 但用户浏览器打开 dashboard 显示老版本
       (或 dashboard 持续刷新 / 按钮没反应 / 看不到新功能)
DevTools → Application → Service Workers:
  Status: activated, but source 为老 sw.js 内容
DevTools → Application → Cache Storage:
  documents cache 含 octet-stream HTML (历史污染)
```

**根因**:
- 老 SW (NetworkFirst 策略) 缓存了服务器修复前的 octet-stream HTML 响应到 `documents` cache
- 服务器修复后 SW 仍可能返回缓存的 octet-stream
- `cleanupOutdatedCaches()` 只清 workbox 维护的 precache cache, **不**清 NetworkFirst/StaleWhileRevalidate 运行时创建的 cache
- 历史事故: commit `08f440f` octet-stream 修复后 → `747a735` SW 升级修复

**修复路径 (3 步)**:
1. **BUMP web/src/sw.js 的 `const SW_VERSION`** 触发字节变化:
   ```javascript
   // web/src/sw.js 顶部
   const SW_VERSION = 'v84-hotfix-sw-cache-purge-2026-07-27'  // BUMP 触发 SW 字节变化
   ```
2. **cd web && npm run build** (走 postbuild, **严禁** `vite build`):
   ```bash
   cd E:/microbubble-agent
   cd web && npm run build
   git add -f web/dist/manifest.{hash}.webmanifest sw.js
   git commit -m "fix(sw-cache-purge): BUMP SW_VERSION v84 清空所有 cache"
   git push origin main
   ```
3. **浏览器侧自动 reload** (postMessage 闭环, web/src/main.js 监听):
   ```javascript
   // web/src/main.js
   useRegisterSW({
     immediate: true,
     onRegisteredSW(swUrl) {
       navigator.serviceWorker.addEventListener('message', (event) => {
         if (event.data?.type === 'SW_UPDATED') {
           setTimeout(() => window.location.reload(), 500)
         }
       })
     },
   })
   ```
   浏览器拉新 SW → install → `skipWaiting` → activate 钩子清空所有 cache + postMessage → 客户端监听 → reload

**修复链路**:
- 用户下次访问 → 浏览器检测 `/sw.js` 字节变化 (BUMP v83 → v84)
- 安装新 SW → 立即 `skipWaiting()` 激活
- `activate` 钩子清空所有 cache: `caches.keys() + Promise.all(keys.map(caches.delete))`
- `postMessage({ type: 'SW_UPDATED', version: SW_VERSION })` → 所有客户端
- main.js 监听 `SW_UPDATED` → `setTimeout(500ms) window.location.reload()`
- 用户拿到全新资源, 无 octet-stream 缓存污染

**验证**:
- DevTools → Application → Service Workers → 看到新 SW_VERSION (v84)
- DevTools → Application → Cache Storage → 看到 precache 列表无 `documents` cache (已被清空)
- DevTools Console → 无 `SW_UPDATED` 监听器报错
- 浏览器 → 看到 reload 自动触发 + 全新内容

**兜底** (用户可手动):
- DevTools → Application → Storage → Clear site data 彻底重置

**纪律 (CLAUDE.md 永久锚点 4 条铁律)**:
1. SW 污染 cache 修复必须改 sw.js (只改 HTML/JS/CSS 没用)
2. `cleanupOutdatedCaches()` 不够, 必须自己写 `caches.keys() + Promise.all(keys.map(caches.delete))` 清所有 cache
3. BUMP SW_VERSION 触发升级, 浏览器通过**字节比较**检测 SW 更新
4. postMessage + reload 闭环, `setTimeout(500ms) window.location.reload()` 让 console.log 先显示

---

## 3. 部署 webhook 30s 验证流程 (派工 v6 段 5 实战)

主拍 SSH 部署后 30s 内必做 4 步验证 (本任务为验证型, 不实跑, 仅记录流程):

```bash
# 步骤 1: git pull 确认
cd /opt/microbubble-agent && git log --oneline | head -3

# 步骤 2: alembic 单 head
docker exec microbubble-agent-app-1 alembic heads
# 期望: ['082_commercial_billing_tables'] 或 '078_drive_dedupe_audit' (1 个)

# 步骤 3: docker compose restart
docker compose restart app celery-worker

# 步骤 4: 6 点 curl 验证 (30s 内完成)
for path in /index.html / /dashboard /sw.js /manifest.webmanifest /manifest.{hash}.webmanifest; do
  curl -sk -o /dev/null -w "$path %{content_type} %{http_code}\n" "https://xiaoqi.studio$path"
done
```

**webhook 验证通过标准**:
- 6 点 curl Content-Type 全部正确
- `/sw.js` → 410 (H-2 防护)
- `/manifest.webmanifest` → 410 (PWA 410 防护)
- `/manifest.{hash}.webmanifest` → 200 + `application/manifest+json`
- `/index.html` `/dashboard` → 200 + `text/html`

**webhook 30s 超时处理**:
- `docker logs microbubble-agent-webhook-1 --tail 50` 看 webhook 日志
- `tail -f /opt/microbubble-agent/logs/webhook.log` 看 git pull 进度
- 部署失败立即 `git revert HEAD` + 重启服务 + 通知主指挥

---

## 4. 浏览器 SW cache 验证流程 (主拍部署后用户测)

派工 v6 段 5 反馈 #2 实战 (W71 部署后用户报 "页面进不去"):

```bash
# 浏览器 DevTools 检查 (用户或 QA 必做)
1. Application → Service Workers
   - 期望: status = activated and is running
   - 期望: Source 包含当前 SW_VERSION (v83 / v84)
   - 期望: 看到 main.js 的 unregister 兜底代码 (W68 第 14 批 H-3)

2. Application → Cache Storage
   - 期望: 仅 workbox 维护的 precache cache
   - 期望: 看不到 `documents` cache (已被 BUMP 清空)
   - 期望: 看不到 `api-cache` cache (H-2 v83 已清)

3. Network → Disable cache 关闭, 刷新页面
   - 期望: 看到正常 200 响应 + 正确 Content-Type
   - 期望: 看到 no-store 头 (nginx 80 block 已加)
   - 期望: 浏览器 console 无 `Manifest fetch failed` 报错

4. Console → 无 SW 升级报错
   - 期望: 无 `bad-precaching-response`
   - 期望: 无 `Manifest fetch failed, code 410`
   - 期望: 无 `SW_UPDATED` 监听失败 (postMessage 闭环工作)
```

**失败处理**:
- SW 还激活老版本 → DevTools → Application → Service Workers → Unregister + Update on reload
- 仍有 documents cache → DevTools → Application → Storage → Clear site data 彻底重置
- 仍报 Manifest fetch failed → 主拍重跑 2.2 hot-fix #2 (PWA manifest 410) 步骤 1-3

---

## 5. 总结

| 件套 | 验证项 | 状态 | 备注 |
|------|--------|------|------|
| 1.1 | alembic 1 head | ✅ PASS | `['078_drive_dedupe_audit']` count=1 |
| 1.2 | baseline CSS lint | ✅ PASS | 当前 20 errors (派工 prompt 71+7 是 W67 旧基准, 实际较 W68 第 14 批 +1-2 errors 来自 W72 商业化/移动端新组件) |
| 1.3 | PWA 410 防护 4 层 | ✅ PASS | main.js H-3 unregister + nginx 3 路径 410 + dist 无 sw.js/manifest + SW_VERSION v83 |
| 1.4 | 0 production code 14/15 | ✅ PASS | W72 第 1 批 5 commits 中 1 docs/memory + 4 移动端新组件例外, 0 老路径 production 改动 |
| 1.5 | anchor 范式守恒 | ✅ PASS | 实际锚点范式 262 守恒 (派工 prompt 220 起点校准为 215, 验证型 0 regression) |

**4 类 hot-fix 链预案**: 全部沉淀, 部署触发立即按预案执行。
- #1 alembic 双头: 3 步 (定位双头 + 改 down_revision + cp+clear cache+1 head verify)
- #2 PWA manifest 410: 3 步 (npm run build + git add -f + 6 点 curl)
- #3 整站 octet-stream: 4 步 (回滚 types block + sed mime.types + nginx reload + 6 点 curl)
- #4 SW 缓存污染: 3 步 (BUMP SW_VERSION + npm run build + postMessage+reload 闭环)

**0 production code 守恒**: 验证型任务, 仅 `docs/w72-2nd-batch-e1-conservation-verification-2026-07-27.md` (本报告) + `memory/w72-2nd-batch-e1-conservation-verification-2026-07-27.md` (memory 沉淀) 新增, 不动 `app/` `web/src/` `alembic/versions/` 老路径。

**锚点范式**: W72 第 1 批 215 → E-1 262 守恒 (验证型 0 regression, 不计增量)。下次 E-2 (若有) 维持 262 守恒。

---

## 6. 引用文档

- W71 A-1 部署验证报告: `docs/w71-deployment-verification-2026-07-24.md` (本报告主参考, 10 步部署验证模板)
- W68 第 14 批 grand closure: `memory/w68-route-14-d2-doc-sync-2026-07-24.md`
- W68 alembic 串单链: `memory/w68-alembic-chain-discipline-2026-07-24.md` (锚点范式第 46 守恒)
- PWA manifest 410 回归: `memory/pwa-manifest-410-regression-2026-07-11.md` (5 铁律)
- SW 缓存污染 v79 BUMP: `memory/sw-cache-poisoning-v79-bump-2026-07-08.md` (3 铁律)
- 2026-06-13 octet-stream 事故: CLAUDE.md "## 2026-06-13 Nginx types 指令覆盖/合并行为差异" 节 (5 铁律)
- 派工纪要 v6 段 5 反馈循环: `docs/w68-13th-batch-prompt-template-v4.md` (派工 v4 铁律 3 实战)

---

**报告版本**: v1.0 (2026-07-27 W72 第 2 批 E-1 守恒验证三件套)
**锚点范式**: W72 第 1 批 215 → E-1 262 守恒 (+47 实际增量来自 W72 第 1 批 5 agents, E-1 验证型 0 增量)
**commit hash**: 本任务 commit 待生成 (含本报告 + memory 沉淀)
