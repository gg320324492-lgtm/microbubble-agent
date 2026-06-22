#!/usr/bin/env node
/**
 * postbuild 脚本：在 vite build 完成后修复 manifest URL 引用
 *
 * 为什么不用 Vite plugin（writeBundle + enforce: 'post'）？
 *   vite-plugin-pwa 1.x 用 workbox-build 异步生成 sw.js，writeBundle 钩子
 *   触发时机不可靠 → sw.js 实际写盘可能晚于 writeBundle 钩子
 *   实测 writeBundle 跑完时 sw.js 还是老的 URL
 *
 * 解法：直接 npm run build 后跑这个脚本（加在 build 命令末尾）
 *   "build": "vite build && node scripts/postbuild-fix-manifest.js"
 *
 * 干 3 件事：
 *   1. 检查 dist/manifest.webmanifest 是否存在，若在则 rename 为 manifest.{hash}.webmanifest
 *   2. 替换 dist/index.html + dist/offline.html 的 manifest 引用
 *   3. 替换 dist/sw.js 里的 __WB_MANIFEST precache URL
 */

const fs = require('fs')
const path = require('path')
const crypto = require('crypto')

const distDir = path.resolve(__dirname, '..', 'dist')

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
  console.log(`[postbuild] ${originalEntry} → ${hashedName}`)
}

if (!hashedName) {
  console.log('[postbuild] 没找到 manifest.webmanifest，跳过')
  process.exit(0)
}

console.log(`[postbuild] 当前 hashed manifest: ${hashedName}`)

// 2. 替换 HTML 引用（带前导斜杠）
for (const file of ['index.html', 'offline.html']) {
  const p = path.join(distDir, file)
  if (!fs.existsSync(p)) continue
  let html = fs.readFileSync(p, 'utf-8')
  let changed = false
  // href="/manifest.webmanifest" 或 /manifest.{hash}.webmanifest 都要匹配 → 替换成 hashedName
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
    console.log(`[postbuild] ${file} 引用已更新 → /${hashedName}`)
  }
}

// 3. 替换 sw.js precache 引用（不带前导斜杠）
const swPath = path.join(distDir, 'sw.js')
if (fs.existsSync(swPath)) {
  let sw = fs.readFileSync(swPath, 'utf-8')
  let changed = false
  // catch-all 正则：替换所有 manifest.webmanifest / manifest.{任意hash}.webmanifest
  sw = sw.replace(/\bmanifest\.[a-zA-Z0-9]*\.webmanifest\b/g, (match) => {
    if (match === hashedName) return match  // 已是正确名字
    changed = true
    return hashedName
  })
  if (changed) {
    fs.writeFileSync(swPath, sw)
    console.log(`[postbuild] sw.js 已更新 → ${hashedName}`)
  } else {
    console.log('[postbuild] sw.js 已包含正确 manifest URL，无需修改')
  }
}

// 4. 同时检查 service-worker.js（如果有）
const swJsPath = path.join(distDir, 'service-worker.js')
if (fs.existsSync(swJsPath)) {
  let sw = fs.readFileSync(swJsPath, 'utf-8')
  let changed = false
  sw = sw.replace(/\bmanifest\.[a-zA-Z0-9]*\.webmanifest\b/g, (match) => {
    if (match === hashedName) return match
    changed = true
    return hashedName
  })
  if (changed) {
    fs.writeFileSync(swJsPath, sw)
    console.log(`[postbuild] service-worker.js 已更新`)
  }
}

console.log('[postbuild] 完成')