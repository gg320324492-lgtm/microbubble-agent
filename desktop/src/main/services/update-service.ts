// UpdateService — Phase 8-M1-A
// 本地占位更新服务. R6 hardening: 稳定版不应伪造下载成功.
//
// 历史 (Phase 8-M1-A): downloadUpdate() 总是返回 { ok: true, progress: 100 },
// 用户看到一个虚假的"已下载"提示, 但实际从未从任何 manifest 拉取字节.
// R6 把行为收敛到 MANUAL_UPDATE_REQUIRED, 直到真实 publish 配置 + electron-updater
// 落地. 同时 installUpdate() 也变为手动提示.

import { resolveApplicationInfo, type ApplicationInfo } from '../application-info'

export interface UpdateCheckResult {
  available: boolean
  currentVersion: string
  latestVersion?: string
  message?: string
}

export interface UpdateDownloadResult {
  ok: boolean
  reason?: string
  progress?: number
}

export interface UpdateInstallResult {
  ok: boolean
  reason?: string
}

export interface UpdateService {
  checkUpdate(): Promise<UpdateCheckResult>
  downloadUpdate(): Promise<UpdateDownloadResult>
  installUpdate(): Promise<UpdateInstallResult>
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

  /**
   * R6: 稳定版不再伪造下载成功.
   *
   * 当前 Phase 8-M1-A 没有真实的发布通道 (electron-updater 尚未接入),
   * 因此 downloadUpdate 始终返回 MANUAL_UPDATE_REQUIRED, UI 应引导用户前往
   * releases.mnb-lab.cn/desktop 手动下载. 一旦 R7 接入 electron-updater,
   * 这里应改为调用 autoUpdater.download() 并把进度回流到 result.progress.
   */
  async downloadUpdate(): Promise<UpdateDownloadResult> {
    return { ok: false, reason: 'MANUAL_UPDATE_REQUIRED', progress: 0 }
  }

  /**
   * R6: 配套 downloadUpdate — 在没有真实下载产物的阶段, installUpdate 也必须
   * 拒绝执行, 避免用户被误导.
   */
  async installUpdate(): Promise<UpdateInstallResult> {
    return { ok: false, reason: 'MANUAL_UPDATE_REQUIRED' }
  }

  async getCurrentVersion(): Promise<string> {
    return this.info().version
  }
}

export const updateService: UpdateService = new LocalUpdateService()
