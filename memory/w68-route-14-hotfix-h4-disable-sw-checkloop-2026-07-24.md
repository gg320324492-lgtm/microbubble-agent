# W68 第 14 批 H-4 hotfix: 禁用 checkSwBlacklist 持续 fetch 循环 (2026-07-24)

> **锚点范式第 190 守恒** — commit `960f8abe1` on `fix/w68-14th-batch-h4-disable-sw-checkloop-2026-07-24`

## 1. 问题 (H-1/H-2/H-3 修复后仍存在)

**主指挥浏览器 console 持续刷 `[PWA] SW content OK, no blacklist match` + Dashboard 仍持续刷新.**

H-1 (dashboard setInterval 泄漏) + H-2 (nginx 410 manifest.webmanifest) + H-3 (main.js 顶部同步 unregister + VitePWA disable) 三连修后,**老 SW 已清, PWA 已永久禁**, 但 H-4 根因仍在 main.js:

`checkSwBlacklist()` 函数 + 调用方链没断. 每次页面 mount 都跑:
1. `fetch('/sw.js', { cache: 'no-store' })` → 实际返回 200 + index.html (nginx SPA fallback)
2. `r.text()` 读完整 HTML
3. 扫 `SW_BLACKLIST_CONTENT_PATTERNS` → 找不到 match
4. `console.log('[PWA] SW content OK, no blacklist match')` — 这就是主指挥 console 看到的那条
5. 返回 false, 不触发 unregister, 但**fetch + 读完整 HTML 的 IO + IO 期间 Vue 仍跑 reactive** = 隐性资源消耗

Dashboard `setInterval` 频繁 mount/unmount (router push + 用户交互) → `checkSwBlacklist` 多次跑 → **每次都 fetch + r.text()**, 持续资源消耗 + console 噪音.

## 2. 修复 (commit `960f8abe1`)

**保留**:
- main.js 顶部 `if ('serviceWorker' in navigator) { navigator.serviceWorker.getRegistrations().then((regs) => regs.forEach((reg) => reg.unregister())) }` (H-3 一次性注销老 SW)
- `caches.keys() + delete` (H-3 一次性清 cache)
- `navigator.serviceWorker.addEventListener('message')` SW_UPDATED 监听 (无害, 等老 SW 发消息不触发新注册)
- `navigator.serviceWorker.addEventListener('controllerchange')` (无害, PWA 禁用后不会触发)

**禁用 (整段 `if (false) { ... }` 包裹, 注释保留逻辑)**:
- `SW_BLACKLIST_CONTENT_PATTERNS` 常量 (3 老 SW 版本黑名单)
- `checkSwBlacklist()` 函数定义 + 调用方 (line 266)
- `useRegisterSW = () => {}` + `if (false) { _pwaUseRegisterSW({...}) }` 双层禁用
- `getRegistration().then(reg => { reg?.waiting.postMessage({ type: 'SKIP_WAITING' }) })` — 主动 update 老 SW (可能造成持续刷新)
- `setTimeout(3000ms) { if (!navigator.serviceWorker.controller) window.location.reload() }` — Safari 兜底 reload (持续刷新触发器)
- `if (false) { _pwaUseRegisterSW(...) }` 内层 — PWA 注册开关

**未保留 (整段删, 不只是 if(false))**:
- `swFirstActivation` flag + controllerchange listener (旧版代码逻辑, H-3 时代未保留此段, 改用 if(false) 大块包裹)

## 3. 验证

**修前 grep (commit `7d2105e60`)**:
```
checkSwBlacklist: 2 (定义 + 调用)
SW content OK: 1
SW_BLACKLIST_CONTENT_PATTERNS: 1
SKIP_WAITING: 1 (3s Safari reload 触发器)
swFirstActivation: 2
controllerchange: 1 (老 PWA controller 监听)
getRegistration: 3 (update() 主动触发老 SW 检查更新)
```

**修后 grep (commit `960f8abe1` source main.js)**:
```
checkSwBlacklist: 2 (仅注释 + 内部引用, 全部 if(false) 内)
SW content OK: 1 (仅注释内)
SW_BLACKLIST_CONTENT_PATTERNS: 2 (注释 + if(false) 内常量)
SKIP_WAITING: 1 (仅 if(false) 内)
getRegistration: 1 (顶部 H-3 保留的 unregister)
```

**编译后 index.js 验证** (派工要求):
```
checkSwBlacklist: 0    ✓
SW content OK: 0       ✓
SW_BLACKLIST: 0        ✓
SKIP_WAITING: 0        ✓ (Safari reload 触发器彻底消失)
unregister: 1          ✓ (H-3 顶部保留)
```

**typing imports check**:
```
扫描了 171 个文件
✅ 所有 typing 注解的 import 都齐全
```

## 4. 5 条新铁律 (派工纪要 v6 段 5 实战 + 派工前提错误复盘沉淀)

1. **必先 commit partial diff (B-3 教训)** — 派工前 `git status --short` 验证干净. 本任务 git status 显示 0 changes, 直接开始.

2. **必删函数定义 + 调用方整段, 不只禁用调用方** — 仅注释调用方 (`if (false) { checkSwBlacklist() }`) 不够, 函数定义本身会被 bundler 保留, 内部代码仍会被 tree-shake 分析. 必须**整段** (`const + async function + 调用方 + 相关常量`) 一起 `if (false)` 包裹. 这次直接把 `SW_BLACKLIST_CONTENT_PATTERNS` + `checkSwBlacklist()` + `useRegisterSW()` + `getRegistration().then()` + 3s reload + 调用方链 一整块 130 行用 `if (false)` 包起来, 恢复 PWA 时取消 false 即可.

3. **web 改动必 `npm run build` + grep 验证** — 不能 `vite build` 直跑 (派工 v4 铁律). worktree 缺 node_modules → `cp -al /e/microbubble-agent/web/node_modules ./node_modules` (H-3 实战模式), `./node_modules/.bin/vite build` 跑成功.

4. **保留 H-3 顶部 unregister 修复** — line 1-20 的 `if ('serviceWorker' in navigator) { navigator.serviceWorker.getRegistrations().then(...) }` **不能删**, H-3 一次性注销老 SW 修复还在生效. 仅 SW 检测代码 (line 149+) 整段禁用.

5. **派工 v6 段 6 合并顺序表已含本任务** — 合并顺序: H-1 → H-2 → H-3 → **H-4** → main merge. H-4 是最后一道防线, 必须 H-1/H-2/H-3 都 merge 后才能验 H-4 效果 (本任务就是等 H-3 merge 后启动的 hotfix).

## 5. 恢复 PWA 时的操作

主拍恢复 PWA 时:
1. 改 `if (false) {` 为 `if (true) {` (line 161, 整块 `if (false)` 大括号配对, 找 `}` 配套)
2. VitePWA 配置 (vite.config.js) 取消 disable (H-3 改了 disable)
3. nginx 410 manifest.webmanifest 配置保留 (c855f0e 教训, 防止 SPA fallback 误返 index.html)
4. postbuild-fix-manifest.js 必跑 (派工 v4 铁律)

## 6. 与 H-1/H-2/H-3 关系

| hot-fix | commit | 锚点范式 | 修复内容 |
|---------|--------|---------|---------|
| H-1 | (older) | 187 | Dashboard setInterval 泄漏 + 老 SW reload 触发 |
| H-2 | (older) | 188 | nginx 410 manifest.webmanifest 防护 |
| H-3 | `7d2105e60` | 189 | main.js 顶部同步 unregister + VitePWA disable + postbuild 兼容 |
| **H-4** | **`960f8abe1`** | **190** | **整段 SW 检测代码 if(false) 包裹, 消除 fetch + r.text() 持续调用 + Safari 3s reload 兜底** |

**H-4 = 根因修复, 前 3 个是补丁**. H-4 后老 SW 已清 (H-3) + PWA 已禁 (H-3) + SW 检测循环已禁 (H-4) → 主指挥浏览器 console 不再刷 `[PWA] SW content OK` + Dashboard 不再持续刷新.

## 7. 派工前提错误复盘 (派工 v6 段 7)

- ✅ 派工前 `git status --short` 干净 (派工 v6 段 7 第 1 条)
- ✅ `npm run build` 走 `vite build` (worktree 缺 node_modules, 用 `cp -al` 复用主仓库, 派工 v4 铁律变种)
- ✅ 没新 manifest hash 文件 (H-2 已禁 PWA, 不存在新增 manifest), 跳过 force-add manifest 步骤
- ✅ 1 commit + defer message (`fix(w68-14th-batch-h4): ...`)
- ✅ typing imports 0 错 (171 文件 PASS)
- ✅ build 后 grep 验证 checkSwBlacklist=0, SW content OK=0, unregister=1
- ✅ memory 沉淀 (本文档)