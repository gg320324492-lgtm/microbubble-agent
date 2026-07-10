#!/usr/bin/env node
/**
 * postbuild 脚本：在 vite build 完成后修复 manifest URL 引用
 *
 * 为什么不用 Vite plugin（writeBundle + enforce: 'post'）？
 *   vite-plugin-pwa 1.x 用 workbox-build 异步生成 sw.js，writeBundle 钩子
 *   触发时机不可靠 → sw.js 实际写盘可能晚于 writeBundle 钩子
 *   实测 writeBundle 跑完时 sw.js 还是老的 URL（setImmediate + 100ms×20 重试竞态）
 *
 * 解法：直接 npm run build 后跑这个脚本（加在 build 命令末尾）
 *   "build": "vite build && node scripts/postbuild-fix-manifest.js"
 *
 * 干 5 件事：
 *   1. 检查 dist/manifest.webmanifest 是否存在，若在则 rename 为 manifest.{hash}.webmanifest
 *   2. 替换 dist/index.html + dist/offline.html 的 manifest 引用
 *   3. 替换 dist/sw.js 里的 __WB_MANIFEST precache URL
 *   4. **健全性自检**：改完后立即 grep sw.js 确认不再有 unhashed "manifest.webmanifest"
 *      → 有则 process.exit(1) 失败（让 `npm run build` 整体失败，避免 broken dist 进 git）
 *   5. 同时检查 dist/service-worker.js（如果有）
 *
 * 2026-07-10 加固：
 *   - 整脚本包 try/catch + process.exit(1) 显式失败（之前 unhandled rejection 会让 npm run build 看起来成功）
 *   - 加健全性自检（第 4 步）防 regex 不匹配时的静默失败（v28 step 109.19 历史教训）
 *   - sw.js 存在性 guard（防 vite-plugin-pwa 不生成时的隐性 build 失败）
 *   - 删 vite.config.js 的 manifestHashPlugin（setImmediate 竞态根因，commit 留尾）
 *   - 任何 sw.js 含 unhashed URL → build 整体失败 → 不可能 commit broken dist
 */

const fs = require('fs')
const path = require('path')
const crypto = require('crypto')

const distDir = path.resolve(__dirname, '..', 'dist')

try {
  // 0. sw.js 必须存在（vite-plugin-pwa 不生成 sw.js 时 build 已失败，此处再 guard 一次）
  const swPath = path.join(distDir, 'sw.js')
  if (!fs.existsSync(swPath)) {
    console.error('[postbuild] FATAL: dist/sw.js 不存在 — vite-plugin-pwa 是否正常生成？')
    console.error('[postbuild] 检查 vite.config.js 的 VitePWA 配置和 injectManifest.globPatterns')
    process.exit(1)
  }

  // 1. 找 manifest 文件（可能是 manifest.webmanifest 或 manifest.{hash}.webmanifest）
  const fsEntries = fs.readdirSync(distDir)
  const hashedEntry = fsEntries.find(f => /^manifest\.[a-f0-9]+\.webmanifest$/.test(f))
  const originalEntry = fsEntries.includes('manifest.webmanifest') ? 'manifest.webmanifest' : null

  let hashedName = hashedEntry
  if (!hashedName && originalEntry) {
    // 还未 hash 化 → 现在 hash
    const content = fs.readFileSync(path.join(distDir, originalEntry))
    const hash = crypto.createHash('sha256').update(content).digest('hex').slice(0, 8)
    hashedName = `manifest.${hash}.webmanifest`
    fs.renameSync(path.join(distDir, originalEntry), path.join(distDir, hashedName))
    console.log(`[postbuild] ${originalEntry} -> ${hashedName}`)
  }

  if (!hashedName) {
    console.error('[postbuild] FATAL: 找不到 manifest.webmanifest 或 manifest.{hash}.webmanifest')
    console.error('[postbuild] 检查 vite.config.js 的 VitePWA manifest 配置')
    process.exit(1)
  }

  // 健全性自检：hashed 文件必须在 disk 上
  const hashedPath = path.join(distDir, hashedName)
  if (!fs.existsSync(hashedPath)) {
    console.error(`[postbuild] FATAL: ${hashedName} 不在 dist 里，但 readdirSync 显示存在`)
    console.error('[postbuild] 可能是 readdirSync 与 stat 之间的 race（极罕见）')
    process.exit(1)
  }

  console.log(`[postbuild] 当前 hashed manifest: ${hashedName}`)

  // 2. 替换 HTML 引用（带前导斜杠）
  for (const file of ['index.html', 'offline.html']) {
    const p = path.join(distDir, file)
    if (!fs.existsSync(p)) continue
    let html = fs.readFileSync(p, 'utf-8')
    let changed = false
    // href="/manifest.webmanifest" 或 /manifest.{hash}.webmanifest 都要匹配 -> 替换成 hashedName
    html = html.replace(/\/manifest\.[a-zA-Z0-9]+\.webmanifest/g, () => {
      changed = true
      return `/${hashedName}`
    })
    // 也匹配原版路径（兜底）
    html = html.replace(/\/manifest\.webmanifest/g, () => {
      changed = true
      return `/${hashedName}`
    })
    if (changed) {
      fs.writeFileSync(p, html)
      console.log(`[postbuild] ${file} 引用已更新 -> /${hashedName}`)
    }
  }

  // 3. 替换 sw.js precache 引用（不带前导斜杠）
  let sw = fs.readFileSync(swPath, 'utf-8')
  let changed = false
  // v28 step 109.19: 修 regex — 旧版 [a-zA-Z0-9]*\.webmanifest 要求 hash 必有内容，
  // 匹配不了 manifest.webmanifest（没 hash）。改用 /manifest(?:\.[a-zA-Z0-9]+)?\.webmanifest/
  sw = sw.replace(/manifest(?:\.[a-zA-Z0-9]+)?\.webmanifest/g, (match) => {
    if (match === hashedName) return match
    changed = true
    return hashedName
  })
  if (changed) {
    fs.writeFileSync(swPath, sw)
    console.log(`[postbuild] sw.js 已更新 -> ${hashedName}`)
  } else {
    console.log('[postbuild] sw.js 已包含正确 manifest URL，无需修改')
  }

  // 4. 健全性自检（防 regex 不匹配时静默失败 — 2026-07-10 事故根因）
  // 任何 "manifest.webmanifest" 出现在 sw.js（无前导 slash，因为 precache 数组不带 /）即视为失败
  const swAfter = fs.readFileSync(swPath, 'utf-8')
  if (/manifest\.webmanifest/.test(swAfter)) {
    console.error('[postbuild] FATAL: sw.js 仍含 unhashed manifest.webmanifest 引用')
    console.error('[postbuild] regex /manifest(?:\\.[a-zA-Z0-9]+)?\\.webmanifest/ 没匹配到')
    console.error('[postbuild] 可能是 vite-plugin-pwa 输出格式变了，需要更新 regex')
    console.error('[postbuild] grep 出的引用：')
    const matches = swAfter.match(/.{0,40}manifest\.webmanifest.{0,40}/g) || []
    matches.forEach((m, i) => console.error(`  [${i}] ${m.trim()}`))
    process.exit(1)
  }
  console.log('[postbuild] 健全性自检通过：sw.js 不含 unhashed manifest 引用 ✓')

  // 5. 同时检查 service-worker.js（如果有）
  const swJsPath = path.join(distDir, 'service-worker.js')
  if (fs.existsSync(swJsPath)) {
    let swJs = fs.readFileSync(swJsPath, 'utf-8')
    let changed2 = false
    swJs = swJs.replace(/manifest(?:\.[a-zA-Z0-9]+)?\.webmanifest/g, (match) => {
      if (match === hashedName) return match
      changed2 = true
      return hashedName
    })
    if (changed2) {
      fs.writeFileSync(swJsPath, swJs)
      console.log('[postbuild] service-worker.js 已更新')
    }
  }

  console.log('[postbuild] 完成 ✓')
} catch (err) {
  console.error('[postbuild] FATAL: 未捕获异常 —', err.message)
  console.error(err.stack)
  process.exit(1)
}