// 桌面集成服务（M4）— 托盘/通知/全局快捷键/关窗行为，全部经注入原语驱动。
// 本服务零 Electron import：Tray/Notification/globalShortcut 由 ipc.ts 装配时以原语注入。
import { shouldNotify } from './notify-decision'

export interface MenuItemSpec {
  label: string
  action: () => void
}

export interface DesktopPrimitives {
  isWindowVisible(): boolean
  focusWindow(): void
  hideWindow(): void
  trayCreate(iconPath: string): void
  traySetToolTip(tip: string): void
  traySetContextMenu(items: MenuItemSpec[]): void
  trayOnLeftClick(cb: () => void): void
  trayDestroy(): void
  notify(title: string, body: string, onClick: () => void): void
  registerGlobalShortcut(accelerator: string, cb: () => void): boolean
  unregisterGlobalShortcut(accelerator: string): void
  getSetting(key: string): unknown
  setSetting(key: string, value: unknown): void
  quit(): void
}

export type CloseActionResult = 'tray' | 'quit'

export interface ShortcutApplyResult {
  ok: boolean
  accelerator: string
  error?: string
}

const SETTING_CLOSE_ACTION = 'desktop.closeAction'
const SETTING_SHORTCUT = 'desktop.globalShortcut'
const SETTING_NOTIFY = 'desktop.notifyAgentComplete'
const DEFAULT_SHORTCUT = 'Ctrl+Alt+M'

export class DesktopIntegrationService {
  private currentShortcut = ''

  constructor(private readonly p: DesktopPrimitives) {}

  // ---------- 托盘 ----------

  setupTray(iconPath: string): void {
    this.p.trayCreate(iconPath)
    this.p.traySetToolTip('小气 · 科研工作台')
    this.p.traySetContextMenu([
      { label: '显示主窗口', action: () => this.showMainWindow() },
      { label: '退出', action: () => this.p.quit() }
    ])
    this.p.trayOnLeftClick(() => this.toggleMainWindow())
  }

  destroyTray(): void {
    this.p.trayDestroy()
  }

  toggleMainWindow(): void {
    if (this.p.isWindowVisible()) this.p.hideWindow()
    else this.showMainWindow()
  }

  showMainWindow(): void {
    this.p.focusWindow()
  }

  /**
   * 主窗口关闭按钮行为：按设置分流（默认最小化到托盘）。
   * 返回 'quit' 表示允许真正关闭；'tray' 表示已隐藏到托盘（调用方需 preventDefault）。
   */
  handleMainWindowClose(): CloseActionResult {
    const action = this.getSetting(SETTING_CLOSE_ACTION) === 'exit' ? 'quit' : 'tray'
    if (action === 'quit') return 'quit'
    this.p.hideWindow()
    if (shouldNotify({ windowVisible: false, enabled: true, alreadyShownOnce: this.trayNotifyShown })) {
      this.trayNotifyShown = true
      this.p.notify('小气 · 科研工作台', '应用已最小化到托盘，点击图标恢复', () => this.showMainWindow())
    }
    return 'tray'
  }

  private trayNotifyShown = false

  // ---------- 原生通知 ----------

  /** Agent 回合完成：窗口不可见且设置开启时弹原生通知，点击聚焦主窗口 */
  onAgentTurnComplete(sessionTitle: string, replyText: string): void {
    const enabled = this.getSetting(SETTING_NOTIFY) !== false
    const visible = this.p.isWindowVisible()
    if (!shouldNotify({ windowVisible: visible, enabled })) return
    const body = replyText.split('\n').find((l) => l.trim()) ?? '回复已完成'
    this.p.notify(sessionTitle || 'AI 助手', body.slice(0, 100), () => this.showMainWindow())
  }

  // ---------- 全局快捷键 ----------

  /**
   * 应用全局快捷键（空串 = 禁用）。注册失败降级为禁用并返回错误原因。
   * 与缩放锁定（Ctrl+0/-/=）无交集：shortcut.ts 解析层已拒绝保留键。
   */
  applyGlobalShortcut(input: string): ShortcutApplyResult {
    if (this.currentShortcut) {
      this.p.unregisterGlobalShortcut(this.currentShortcut)
      this.currentShortcut = ''
    }
    const accelerator = String(input ?? '').trim()
    if (!accelerator) {
      this.setSetting(SETTING_SHORTCUT, '')
      return { ok: true, accelerator: '' }
    }
    const ok = this.p.registerGlobalShortcut(accelerator, () => this.toggleMainWindow())
    if (!ok) return { ok: false, accelerator, error: `全局快捷键 ${accelerator} 注册失败（可能与其他应用冲突）` }
    this.currentShortcut = accelerator
    this.setSetting(SETTING_SHORTCUT, accelerator)
    return { ok: true, accelerator }
  }

  /** 启动时按设置恢复全局快捷键 */
  restoreGlobalShortcut(): ShortcutApplyResult {
    const saved = this.getSetting(SETTING_SHORTCUT)
    const value = typeof saved === 'string' && saved ? saved : DEFAULT_SHORTCUT
    return this.applyGlobalShortcut(value)
  }

  currentAccelerator(): string {
    return this.currentShortcut
  }

  /** 冲突时自动探测候选快捷键；成功即注册并返回建议，全部失败返回 null */
  findAvailableAlternative(original: string): string | null {
    const candidates = ['Ctrl+Shift+M', 'Ctrl+Alt+K', 'Ctrl+Alt+P']
    for (const c of candidates) {
      if (c === original) continue
      if (this.p.registerGlobalShortcut(c, () => this.toggleMainWindow())) {
        this.p.unregisterGlobalShortcut(c) // 探测成功即释放，等用户确认后正式注册
        return c
      }
    }
    return null
  }

  // ---------- 内部 ----------

  private getSetting(key: string): unknown {
    try {
      return this.p.getSetting(key)
    } catch {
      return undefined
    }
  }

  private setSetting(key: string, value: unknown): void {
    try {
      this.p.setSetting(key, value)
    } catch {
      /* 设置写失败不阻塞主流程 */
    }
  }
}
