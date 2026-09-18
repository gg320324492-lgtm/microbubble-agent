// 更新服务（M6-1）— 编排层：把注入的 updater 端口 + 设置 + 通知串成提示式更新流程。
// 零 Electron 依赖：electron-updater 只在 updater-adapter 出现，主进程装配时注入端口。
// 状态推进全部交给纯 reducer（update-state），本类只负责副作用编排与通知判定。
import { shouldNotify } from '../desktop/notify-decision'
import { initialUpdateState, isBusy, reduceUpdate, type UpdateState } from './update-state'
import { isNewer } from './version'

/** 更新端口 — 由适配层实现（真实 electron-updater / 测试 fake） */
export interface UpdaterPort {
  /** 查询更新源；返回可用新版本号，无更新返回 null */
  checkForUpdates(): Promise<{ version?: string | null } | null>
  downloadUpdate(): Promise<void>
  quitAndInstall(): void
  onProgress(cb: (percent: number) => void): void
  onDownloaded(cb: () => void): void
}

export interface UpdateServiceDeps {
  /** 当前运行版本（APP_VERSION） */
  currentVersion: string
  /** 环境是否支持更新检查：已打包，或显式注入了 feed 覆盖（供真机/联调） */
  envSupported: boolean
  port: UpdaterPort
  getSetting: (key: string) => unknown
  isWindowVisible: () => boolean
  notify: (title: string, body: string, onClick: () => void) => void
  /** 通知点击后的落点：聚焦窗口并切到设置页 */
  onOpenSettings: () => void
  onStateChange?: (state: UpdateState) => void
  log?: (message: string) => void
}

/** 设置键 — 复用现有 settings 通道（按用户隔离） */
export const SETTING_AUTO_CHECK = 'update.autoCheck'
/** 启动后延迟自动检查（不阻塞启动） */
export const AUTO_CHECK_DELAY_MS = 5000

export class UpdateService {
  private state: UpdateState
  private autoCheckTimer: ReturnType<typeof setTimeout> | null = null

  constructor(private readonly deps: UpdateServiceDeps) {
    this.state = initialUpdateState(!deps.envSupported)
    deps.port.onProgress((percent) => this.dispatch({ type: 'download-progress', percent }))
    deps.port.onDownloaded(() => this.dispatch({ type: 'download-done' }))
  }

  snapshot(): UpdateState {
    return { ...this.state }
  }

  /** 环境是否支持更新（非打包且无 feed 覆盖 = 不支持） */
  isEnvSupported(): boolean {
    return !this.state.disabled
  }

  /** 「自动检查更新」开关，默认开 */
  isAutoCheckEnabled(): boolean {
    return this.deps.getSetting(SETTING_AUTO_CHECK) !== false
  }

  /**
   * 检查更新。
   * @param trigger 'auto' = 启动后台检查（受开关约束、失败静默）；'manual' = 设置页按钮
   */
  async check(trigger: 'auto' | 'manual' = 'manual'): Promise<UpdateState> {
    // 禁用态以状态机为准（setEnvSupported 可运行时变更），不读构造期快照
    if (this.state.disabled) return this.snapshot()
    if (trigger === 'auto' && !this.isAutoCheckEnabled()) return this.snapshot()
    if (isBusy(this.state) || this.state.status === 'ready') return this.snapshot()

    this.dispatch({ type: 'check-start' })
    if (this.state.status !== 'checking') return this.snapshot()

    try {
      const res = await this.deps.port.checkForUpdates()
      const version = res?.version ?? null
      if (version && isNewer(version, this.deps.currentVersion)) {
        this.dispatch({ type: 'check-available', version })
        this.notifyAvailable(version)
      } else {
        this.dispatch({ type: 'check-none' })
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e)
      // 后台检查失败静默：只记日志，不打扰用户
      this.deps.log?.(`[update] ${trigger} check failed: ${message}`)
      this.dispatch({ type: 'check-error', message })
    }
    return this.snapshot()
  }

  /** 用户确认后开始下载；完成后由端口回调推到 ready */
  async download(): Promise<UpdateState> {
    if (this.state.status !== 'available') return this.snapshot()
    this.dispatch({ type: 'download-start' })
    try {
      await this.deps.port.downloadUpdate()
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e)
      this.deps.log?.(`[update] download failed: ${message}`)
      this.dispatch({ type: 'download-error', message })
    }
    return this.snapshot()
  }

  /** 安装并重启 — 仅 ready 态可执行；全程不自动安装，必须由用户点击触发 */
  installAndRestart(): boolean {
    if (this.state.status !== 'ready') return false
    this.deps.port.quitAndInstall()
    return true
  }

  /** 启动后延迟自动检查（失败静默）；定时器 unref 以免阻塞进程退出 */
  scheduleAutoCheck(delayMs: number = AUTO_CHECK_DELAY_MS): void {
    if (this.state.disabled) return
    if (this.autoCheckTimer) clearTimeout(this.autoCheckTimer)
    this.autoCheckTimer = setTimeout(() => {
      this.autoCheckTimer = null
      void this.check('auto')
    }, delayMs)
    const t = this.autoCheckTimer as unknown as { unref?: () => void }
    t.unref?.()
  }

  /** 环境支持性变化时同步禁用态（装配层在 feed 覆盖变更时调用） */
  setEnvSupported(supported: boolean): void {
    this.dispatch({ type: 'set-disabled', disabled: !supported })
  }

  /** 测试/退出清理 */
  dispose(): void {
    if (this.autoCheckTimer) clearTimeout(this.autoCheckTimer)
    this.autoCheckTimer = null
  }

  // ---------- 内部 ----------

  private dispatch(event: Parameters<typeof reduceUpdate>[1]): void {
    const next = reduceUpdate(this.state, event)
    if (next === this.state) return
    this.state = next
    this.deps.onStateChange?.(this.snapshot())
  }

  private notifyAvailable(version: string): void {
    const visible = this.deps.isWindowVisible()
    if (!shouldNotify({ windowVisible: visible, enabled: true })) return
    this.deps.notify(`发现新版本 v${version}`, '点击查看并更新', () => this.deps.onOpenSettings())
  }
}
