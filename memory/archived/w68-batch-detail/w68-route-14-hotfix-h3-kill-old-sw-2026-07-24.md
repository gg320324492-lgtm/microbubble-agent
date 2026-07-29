# W68 第 14 批 H-3 hot-fix: 强制注销浏览器老 SW (2026-07-24)

**锚点范式第 189 守恒** | commit `ff9b6b3e2` | push OK

## 背景

W68 第 14 批 H-2 (commit `84ac66440`) 已删 `web/dist/sw.js` + `web/dist/manifest*` + 改 nginx 加 `return 410` 防 sw.js. 但**主指挥浏览器 console 仍报 `[PWA] SW content OK, no blacklist match`** — 浏览器 SW 在 Service Worker Registration Cache 里**有老 sw.js 内容**, 即使 nginx 现在 410, 老 SW 实例仍 active 在浏览器进程.

**症状**: 用户每次访问新页面, 老 SW 仍拦截 fetch → 持续触发 dashboard 刷新循环 + 提示 "页面进不去".

## H-3 修复 (4 步)

### Step 1: `web/src/main.js` 顶部插入强制清老 SW 代码

在 file top (所有 import 之前) 加 unregister + 清 Cache Storage 逻辑:

```javascript
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.getRegistrations().then((regs) => {
    regs.forEach((reg) => {
      reg.unregister().catch(() => { /* ignore */ })
    })
  })
  if ('caches' in window) {
    caches.keys().then((keys) => {
      keys.forEach((k) => {
        caches.delete(k).catch(() => {})
      })
    })
  }
}
```

### Step 2: `web/vite.config.js` VitePWA 全禁

加 `disable: true`:
```javascript
VitePWA({
  disable: true,  // W68 第 14 批 H-3: 强制禁用 PWA
  registerType: 'autoUpdate',
  ...
})
```

### Step 3: `web/scripts/postbuild-fix-manifest.js` 加 disable 兼容

postbuild 原逻辑第 0 步: `if (!fs.existsSync(swPath))` 报 FATAL 退出 1. PWA 禁用后 sw.js 不存在, 必报 FATAL. 改为: 检测到 sw.js 缺失时, 直接 `process.exit(0)` (PWA 已禁用不需要后处理).

### Step 4: `npm run build` 重生成 dist

- 编译产物 `dist/assets/index-*.js` 头部包含 `navigator.serviceWorker.getRegistrations().then(e=>{e.forEach(e=>{e.unreg...`
- `dist/sw.js` 已不存在 (PWA disable 后)
- `dist/manifest*.webmanifest` 已不存在
- typing imports 0 错 (171 文件 PASS)

## 3 新铁律

1. **PWA 永久禁用时 vite-plugin-pwa 必须 `disable: true`** — 不只是 main.js 不调 useRegisterSW, build 时 vite-plugin-pwa 也不该生成 sw.js + manifest (它们会进 nginx 410 列表但仍占带宽)
2. **postbuild 脚本必须兼容 PWA 禁用态** — 原 `if (!fs.existsSync(swPath))` 报 FATAL, 禁用 PWA 时 sw.js 不存在, 改为 `process.exit(0)` 友好跳过
3. **浏览器老 SW 必须在 main.js 顶部强制 unregister** — 仅靠 nginx 410 + 删 dist 文件不够, 浏览器 SW Registration Cache 仍保留老 SW 实例, 必在每次页面加载顶部同步 unregister + 清 Cache Storage

## 完成验证

- commit hash: `ff9b6b3e2`
- main.js 顶部 unregister 代码 grep: `navigator.serviceWorker.getRegistrations().then(e=>{e.forEach(e=>{e.unreg...`
- vite.config.js VitePWA: `disable: true`
- dist/sw.js 不存在
- dist/manifest*.webmanifest 不存在
- typing imports: 171 文件 0 错
- push: `fix/w68-14th-batch-h3-kill-old-sw-2026-07-24` → `origin/...` OK

## 预期效果

用户访问新页面后:
1. main.js 顶部同步 unregister 老 SW (浏览器 Registration Cache 清空)
2. 清 Cache Storage (所有老 precache 删除)
3. 后续 fetch 走纯 nginx, 不再触发 dashboard 刷新循环
4. console 不再报 `[PWA] SW content OK, no blacklist match`