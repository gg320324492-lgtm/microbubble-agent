// electron / electron-builder 缓存目录统一指向 E 盘 —— 避免每次依赖升级把
// 几百 MB 的 zip 落到 C 盘 %LOCALAPPDATA%。
//
// 背景（2026-10-22 实测）：本仓对 C 盘的贡献里最大的两项就是
//   %LOCALAPPDATA%\electron\Cache          625 MB（electron-v32.3.3-win32-x64.zip）
//   %LOCALAPPDATA%\electron-builder\Cache    86 MB（nsis / winCodeSign 等）
// 两者都是**每次 electron / builder 版本升级就重新下载**的缓存，可随时重建，
// 不含任何业务数据。
//
// 目标目录：<repo>/data/{electron-cache,electron-builder-cache}
//   · `data/` 已被 .gitignore 第 29 行覆盖，不会进 git
//   · 与仓库同盘（E:），不占 C 盘
//
// 生效面（三处，缺一不可 —— 只做仓库内的话，"从别处跑 pnpm install" 仍会落 C 盘）：
//   ① 本模块 —— 供 package.json 的 pack/dist 与 scripts/release.mjs 注入
//   ② 用户级环境变量（[Environment]::SetEnvironmentVariable 'User'）
//   ③ electron 自身的 install.js（pnpm install 时下载 zip）读同一个环境变量
import { mkdirSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

/** apps/desktop 目录（lib -> scripts -> desktop） */
export const DESKTOP_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..')
/** 仓库根（apps/desktop -> apps -> <repo>） */
export const REPO_ROOT = resolve(DESKTOP_ROOT, '..', '..')

export const ELECTRON_CACHE_DIR = join(REPO_ROOT, 'data', 'electron-cache')
export const ELECTRON_BUILDER_CACHE_DIR = join(REPO_ROOT, 'data', 'electron-builder-cache')

/**
 * 注入缓存环境变量。返回**新的** env 对象，不改 process.env。
 * @param {Record<string,string|undefined>} [extra] 额外覆盖项
 */
export function withCacheEnv(extra = {}) {
  mkdirSync(ELECTRON_CACHE_DIR, { recursive: true })
  mkdirSync(ELECTRON_BUILDER_CACHE_DIR, { recursive: true })
  // 本地 node_modules/.bin 提到 PATH 最前 —— 这样即便不是经 npm/pnpm script
  // 启动（PATH 里没有 .bin），`electron-builder` 也能被解析到。
  const binDir = join(DESKTOP_ROOT, 'node_modules', '.bin')
  const pathKey = Object.keys(process.env).find((k) => k.toUpperCase() === 'PATH') || 'Path'
  const pathValue = [binDir, process.env[pathKey]].filter(Boolean).join(';')
  return {
    ...process.env,
    [pathKey]: pathValue,
    ELECTRON_CACHE: ELECTRON_CACHE_DIR,
    ELECTRON_BUILDER_CACHE: ELECTRON_BUILDER_CACHE_DIR,
    ...extra
  }
}
