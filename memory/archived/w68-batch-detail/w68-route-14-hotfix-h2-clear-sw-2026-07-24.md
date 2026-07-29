# W68 第 14 批 hotfix H-2: 强制清 SW 缓存 (锚点范式第 188 守恒, 2026-07-27)

## 背景

主指挥浏览器 (W68 第 14 批多次 rebuild 后) console 仍报
`GET /assets/index-b2d5fe95.js net::ERR_ABORTED 404`,
且 `Force refresh` (Ctrl+Shift+R) 不一定能清 SW precache。这是 **W68 第 14 批派工闭环**后仍未根除的浏览器侧症状。

## 根因 (2 层)

1. **W68 第 14 批 5+ 次 rebuild + push 后**, 服务器 dist 哈希每次都变 (`index-{new}.js`),
   但浏览器**仍持有老 SW**, 老 SW precache 了老 chunk 列表
2. **SW 升级机制不完美**:
   - commit `4b658cbb2` 加了 `Cach-Control: no-store` for `/sw.js` (避免 SW 自身被浏览器缓存)
   - commit `89a34c28f` 修了 `useRegisterSW` heartbeat
   - **但** 浏览器仍会**重新安装**老 SW (server 一直 200), 仍引用老 chunk 列表 → 404
3. **NGINX `add_header` + `return 410` 优先级**:
   - 之前的 `location = /sw.js { add_header Cache-Control "no-store" }` **不返回 410**,
     没有 `return 410` 让浏览器**卸载** SW, 仅让我每次重拉 sw.js
   - 浏览器用 NetworkFirst 重新拉到了新 SW, 但 SW install 事件里仍有 `self.skipWaiting()` +
     老 precache 列表 → 拿到 InvalidResponse / 老 chunk 404

## 修复 (4 文件, 1 commit, 锚点范式第 188 守恒)

commit `72eaae07f` on branch `fix/w68-14th-batch-h2-clear-sw-cache-2026-07-24`:

### 1. `web/vite.config.js` — PWA plugin `disable: true`

替换完整 PWA 配置 (registerType/injectRegister/strategies/injectManifest/devOptions) → 单行 `disable: true`,
让 vite-plugin-pwa **完全不生成 sw.js + manifest.* + 注入任何 SW 逻辑**,
浏览器再访问 `/sw.js` 会拿到 nginx 410, 卸载老 SW, 后续走纯 nginx 静态资源路径。

### 2. `web/package.json` — `build` 脚本禁 PWA postbuild

```diff
- "build": "vite build && node scripts/postbuild-fix-manifest.js",
+ "build": "vite build",
+ "build:pwa": "vite build && node scripts/postbuild-fix-manifest.js",  // 恢复 PWA 时用
  "build:raw": "vite build",
- "postbuild:fix-manifest": "node scripts/postbuild-fix-manifest.js",
```

postbuild 脚本**强依赖** dist/sw.js 存在 (作为健全性自检), 禁用 PWA 后会 `process.exit(1)` 失败。
恢复 PWA 时 `npm run build:pwa` 即可。

### 3. `web/dist/` — 删 sw.js + manifest + registerSW.js (重新 build 后自动)

`npm run build` 重新生成 dist, 不再含 sw.js + manifest.{hash}.webmanifest (旧 `manifest.4f8d6b64.webmanifest` 也删除)。
dist/assets 已经重新生成新 chunk (201 个 assets, 0 PWA 文件)。

### 4. `nginx/conf.d/tunnel.conf` + `http-only.conf` — `location = /sw.js { return 410; }`

在 80 block + 443 block + http-only.conf (3 个 server block) **都**加 `location = /sw.js { return 410; }` + `location = /registerSW.js { return 410; }` (跟 443/80 一致):

```nginx
# W68 第 14 批 H-2: Service Worker 临时禁用
location = /sw.js {
    add_header Cache-Control "no-store, no-cache, must-revalidate" always;
    add_header X-Content-Type-Options "nosniff" always;
    return 410;  # 410 触发浏览器 SW 卸载流程
}
location = /registerSW.js {
    return 410;
}
location = /manifest.webmanifest {
    return 410;
}
```

之前 `location = /sw.js` 只加 `add_header Cache-Control "no-store"` 但不返回 410,
浏览器收到 200 + 老 SW 内容 → 不会卸载老 SW → 老 chunk 列表仍在 precache。
**410 是触发浏览器卸载 SW 的关键**: 浏览器对 SW 抓取失败 4xx (404/410) 时, 会**卸载当前 SW**。

## 5 条铁律 (新增)

1. **浏览器 SW 卸载必须 410 (不是 no-store)** — `Cache-Control: no-store` 让浏览器重拉 sw.js,
   但不会卸载当前注册的老 SW。仅 `return 410` (或 404) 触发 SW 卸载流程。
2. **vite-plugin-pwa `disable: true`** 比 postbuild 删 sw.js 更彻底 — postbuild 删了 sw.js 但
   vite-plugin-pwa 已在 build 阶段生成了 SW + 注入 `useRegisterSW` 调用, 浏览器仍可注册。
   `disable: true` 从源头关闭 PWA plugin, build 产物完全无 SW 相关代码。
3. **postbuild 脚本强依赖 sw.js 存在** — `scripts/postbuild-fix-manifest.js:38` 用 `fs.existsSync(swPath)` 健全性自检,
   禁用 PWA 后**必须**从 `build` 移除 `&& node scripts/postbuild-fix-manifest.js`, 否则 build 失败。
   提供 `build:pwa` 别名用于恢复 PWA 时一键重建。
4. **nginx 3 个 server block 必须都加 410 (80 + 443 + http-only)** — 服务器有 3 个 server block
   (tunnel.conf 80 + tunnel.conf 443 + http-only.conf 80), 缺一个浏览器就可能命中 200 路径。
   W68 第 14 批 D-2 文档同步纪律强化。
5. **恢复 PWA 时**:
   - `web/vite.config.js` 删 `disable: true`, 恢复完整 VitePWA 配置
   - `web/package.json` `build` 改回 `vite build && node scripts/postbuild-fix-manifest.js`
   - `nginx/conf.d/tunnel.conf` 改回 `location = /sw.js { add_header Cache-Control "no-store" }` (无 410)
   - `web/src/main.js` 改 `if (false) { _pwaUseRegisterSW(...) }` → `if (true) { ... }` 真实注册
   - `web/src/sw.js` 重新写 SW_VERSION BUMP 触发字节变化
   - `npm run build:pwa` 重建 dist (含 sw.js + manifest.{hash}.webmanifest)
   - 部署前 verify `curl -I /sw.js` 返回 200 + no-store (而非 410)

## 验证 (post-merge 主指挥操作)

1. **服务器端**:
   - `curl -I https://xxx/sw.js` → 期望 `HTTP/1.1 410 Gone` + `Cache-Control: no-store`
   - `curl -I https://xxx/registerSW.js` → 期望 `HTTP/1.1 410 Gone`
   - `curl -I https://xxx/manifest.webmanifest` → 期望 `HTTP/1.1 410 Gone`
   - `curl -I https://xxx/index.html` → 期望 `HTTP/1.1 200 OK` + `text/html` (整站仍正常)
2. **浏览器端**:
   - DevTools → Application → Service Workers → 看到 SW 状态为 `redundant` (已卸载)
   - DevTools → Application → Cache Storage → 手动 `Clear site data` 兜底
   - 硬刷 (Ctrl+Shift+R) → 浏览器拉新 dist, 不再 ERR_ABORTED 404
3. **资源验证**:
   - DevTools → Network → 看不到 `/sw.js` 200 响应
   - 看不到 `/assets/index-{oldhash}.js` 404 响应
   - 首页加载完整 (HTML + CSS + JS + 字体 + 图片)

## 守恒

- 0 production code 改动铁律 11/15 守恒 (新增 1 例外 H-2: nginx + web config)
- W19 选项 A 维持 (4 留未来 PR)
- 锚点范式第 188 守恒 (W68 第 14 批 175 → 188, 单批 13 守恒)
- 派工纪要 v6 派工前提 5/5 守恒 (commit partial diff + npm run build + manifest force-add + nginx/dist/main.js 三同步 + 1 commit defer)
- B-3 7 文件丢失事故未再现 (派工前 `git status --short` 验证干净)

## commit / branch

- branch: `fix/w68-14th-batch-h2-clear-sw-cache-2026-07-24`
- commit: `72eaae07f`
- 105 files changed (44 insertions, 190 deletions)
- pushed: pending (主拍合并)
- worktree: `E:/microbubble-agent/.worktrees/agent-w68-14-h2-clear-sw`
