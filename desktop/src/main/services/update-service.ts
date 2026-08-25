// UpdateService — Phase 8-M1-A
// 本地占位更新服务. Phase 8-M1-A 不连接真实服务器, 仅返回 { available: false, currentVersion, message }.
// 未来 Phase: 接入 GitHub Releases / 自建 releases.mnb-lab.cn (electron-updater).

import { resolveApplicationInfo, type ApplicationInfo } from '../application-info'

export interface UpdateCheckResult {
  available: boolean
  currentVersion: string
  latestVersion?: string
  message?: string
}

export interface UpdateService {
  checkUpdate(): Promise<UpdateCheckResult>
  downloadUpdate(): Promise<{ ok: true; progress?: number }>
  installUpdate(): Promise<{ ok: true }>
  getCurrentVersion(): Promise<string>
}

/**
 * 比较两个 semver 字符串. 返回 -1 / 0 / 1.
 * 非法格式降级为字符串比较, 永不抛错.
 */
export function compareVersions(a: string, b: string): number {
  const pa = String(a || '').split('.').map((n) => Number.parseInt(n, 10) || 0)
  const pb = String(b || '').split('.').map((n) => Number.parseInt(n, 10) || 0)
  const len = Math.max(pa.length, pb.length)
  for (let i = 0; i < len; i++) {
    const x = pa[i] ?? 0
    const y = pb[i] ?? 0
    if (x > y) return 1
    if (x < y) return -1
  }
  return 0
}

class LocalUpdateService implements UpdateService {
  private cachedInfo: ApplicationInfo | null = null

  private info(): ApplicationInfo {
    if (!this.cachedInfo) this.cachedInfo = resolveApplicationInfo()
    return this.cachedInfo
  }

  async checkUpdate(): Promise<UpdateCheckResult> {
    // Phase 8-M1-A placeholder: 永远返回 available=false.
    // 测试场景下允许通过环境变量注入 mock 结果, 但默认行为不变.
    const info = this.info()
    const envOverride = process.env['MICRORB_UPDATE_OVERRIDE']
    if (envOverride && /^\d+\.\d+\.\d+/.test(envOverride)) {
      const cmp = compareVersions(info.version, envOverride)
      return {
        available: cmp < 0,
        currentVersion: info.version,
        latestVersion: envOverride,
        message: cmp < 0 ? `检测到新版本 ${envOverride}` : '当前已是最新版本'
      }
    }
    return {
      available: false,
      currentVersion: info.version,
      message: '当前已是最新版本'
    }
  }

  async downloadUpdate(): Promise<{ ok: true; progress?: number }> {
    // Phase 8-M1-A placeholder: 无真实下载, 立即返回 ok
    return { ok: true, progress: 100 }
  }

  async installUpdate(): Promise<{ ok: true }> {
    // Phase 8-M1-A placeholder: 无真实安装, 立即返回 ok
    return { ok: true }
  }

  async getCurrentVersion(): Promise<string> {
    return this.info().version
  }
}

export const updateService: UpdateService = new LocalUpdateService()
