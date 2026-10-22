#!/usr/bin/env node
// CLI 包装器：node scripts/with-cache-env.mjs <cmd> [args...]
//
// 用途：把 electron / electron-builder 的缓存目录指到 E 盘再执行命令。
// 跨平台（不依赖 cross-env），供 package.json 的 pack / dist 使用。
//
//   "pack": "npm run build && node scripts/with-cache-env.mjs electron-builder --dir -c.npmRebuild=false"
//
// 退出码透传子进程；子进程被信号杀死时用同信号结束自身。
import { spawn } from 'node:child_process'
import { withCacheEnv } from './lib/cache-env.mjs'

const argv = process.argv.slice(2)
const cmd = argv[0]
if (!cmd) {
  console.error('[with-cache-env] 用法: node scripts/with-cache-env.mjs <cmd> [args...]')
  process.exit(2)
}

const child = spawn(cmd, argv.slice(1), {
  stdio: 'inherit',
  shell: process.platform === 'win32',
  env: withCacheEnv()
})

child.on('error', (err) => {
  console.error(`[with-cache-env] 无法启动 ${cmd}: ${err.message}`)
  process.exit(127)
})
child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal)
    return
  }
  process.exit(code ?? 0)
})
