// ApplicationInfo — Phase 8-M1-A
// 应用元信息收集: 从 package.json + 环境变量 + git commit (可选) + 构建时间派生.
// 严禁在源码硬编码版本字符串 (CI 必须通过 MICRORB_BUILD_NUMBER / COMMIT_HASH 注入).

import { readFileSync, existsSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

export type ReleaseChannel = 'stable' | 'beta' | 'dev'
export type AppEnvironment = 'production' | 'development'

export interface ApplicationInfo {
  name: string
  version: string
  buildNumber: string
  commitHash: string
  buildTime: string
  channel: ReleaseChannel
  environment: AppEnvironment
}

const PRODUCT_NAME = 'Scientific Research OS'
const APP_ID = 'com.scientific.research.os'

function readPackageJson(): { version?: string; name?: string } {
  // 兼容 ESM (fileURLToPath) 与 CJS (__dirname) 双模式
  let here: string
  try {
    here = dirname(fileURLToPath(import.meta.url))
  } catch {
    // CJS 环境
    here = typeof __dirname !== 'undefined' ? __dirname : process.cwd()
  }
  const candidates = [
    resolve(here, '..', '..', 'package.json'),
    resolve(here, '..', 'package.json'),
    resolve(process.cwd(), 'package.json')
  ]
  for (const p of candidates) {
    if (existsSync(p)) {
      try {
        const raw = readFileSync(p, 'utf8')
        const parsed = JSON.parse(raw) as { version?: string; name?: string }
        return parsed
      } catch {
        return {}
      }
    }
  }
  return {}
}

function resolveBuildNumber(): string {
  // CI / 本地构建注入:
  //   MICRORB_BUILD_NUMBER=42
  //   MICRORB_BUILD_NUMBER=local-dev
  const envBuild = process.env['MICRORB_BUILD_NUMBER']
  if (envBuild && envBuild.length > 0 && envBuild.length <= 64) return envBuild
  // 本地开发: 用 ISO 时间戳简化形式 (YYYYMMDD-HHMMSS)
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `local-${now.getUTCFullYear()}${pad(now.getUTCMonth() + 1)}${pad(now.getUTCDate())}-${pad(now.getUTCHours())}${pad(now.getUTCMinutes())}${pad(now.getUTCSeconds())}`
}

function resolveCommitHash(): string {
  const envCommit = process.env['COMMIT_HASH'] || process.env['GIT_COMMIT']
  if (envCommit && /^[0-9a-f]{7,40}$/i.test(envCommit)) return envCommit
  // 本地构建无 git 环境: 返回 unknown, 绝不抛错
  return 'unknown'
}

function resolveChannel(): ReleaseChannel {
  const raw = process.env['MICRORB_CHANNEL']
  if (raw === 'stable' || raw === 'beta' || raw === 'dev') return raw
  // CI 注入: stable 默认, 显式 dev 环境 (NODE_ENV=development 或 CI 缺失) → dev
  if (process.env['CI'] === 'true' || process.env['NODE_ENV'] === 'production') return 'stable'
  return 'dev'
}

function resolveEnvironment(): AppEnvironment {
  // 打包后的 production 二进制: NODE_ENV=production
  // 开发态 (electron-vite dev 或 vitest): 默认 development
  if (process.env['NODE_ENV'] === 'production') return 'production'
  return 'development'
}

function resolveBuildTime(): string {
  // CI 注入固定时间 (保证构建可复现); 本地默认 ISO now
  const envTime = process.env['MICRORB_BUILD_TIME']
  if (envTime && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(envTime)) return envTime
  return new Date().toISOString()
}

let cached: ApplicationInfo | null = null

/**
 * 解析应用元信息. 多次调用安全 (cache 命中); 任何 IO 失败都返回安全 fallback.
 */
export function resolveApplicationInfo(): ApplicationInfo {
  if (cached) return cached
  const pkg = readPackageJson()
  const version = pkg.version || '0.0.0'
  const info: ApplicationInfo = {
    name: PRODUCT_NAME,
    version,
    buildNumber: resolveBuildNumber(),
    commitHash: resolveCommitHash(),
    buildTime: resolveBuildTime(),
    channel: resolveChannel(),
    environment: resolveEnvironment()
  }
  cached = info
  return info
}

/** 测试 / HMR 场景下重置缓存, 重新解析. */
export function resetApplicationInfoCache(): void {
  cached = null
}

export { APP_ID }
