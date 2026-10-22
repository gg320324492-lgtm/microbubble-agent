// pnpmfile.cjs —— 在 pnpm 主进程里设置环境变量，供依赖的 install（postinstall）脚本继承。
//
// 用途：electron 包的 install.js 会下载 electron-vXX-win32-x64.zip，默认落到
// %LOCALAPPDATA%\electron\Cache（2026-10-22 实测 625 MB）。该下载由 pnpm 的生命周期
// 子进程执行，子进程继承 pnpm 进程的 env —— 所以在这里设 ELECTRON_CACHE 就能把它
// 指到 E 盘，而不是 C 盘。
//
// 为什么不只靠用户级环境变量：用户级变量只对**新开**的终端/进程生效。
// 从"环境变量写入之前就开着的"终端跑 pnpm install，仍会落 C 盘。
// 本文件让"在仓库内执行"这条路径不依赖终端何时开的。
//
// 兜底：与用户级环境变量同值（E:\microbubble-agent\data\electron-cache）。
// 用户级变量优先（若用户改过，本文件不覆盖已有值 —— 用 setdefault 语义）。
//
// ⚠️ 本文件不得抛异常 —— pnpmfile 抛错会让整个 pnpm install 失败。
//     故所有逻辑都包在 try/catch 里，失败即静默降级回默认行为。
try {
  const path = require('node:path')
  const fs = require('node:fs')
  const repoRoot = __dirname
  const dataDir = path.join(repoRoot, 'data')

  const electronCache = path.join(dataDir, 'electron-cache')
  const electronBuilderCache = path.join(dataDir, 'electron-builder-cache')
  fs.mkdirSync(electronCache, { recursive: true })
  fs.mkdirSync(electronBuilderCache, { recursive: true })

  if (!process.env.ELECTRON_CACHE) process.env.ELECTRON_CACHE = electronCache
  if (!process.env.ELECTRON_BUILDER_CACHE) process.env.ELECTRON_BUILDER_CACHE = electronBuilderCache
} catch {
  // 静默降级 —— pnpmfile 失败不应阻断安装
}
