// 桌面集成服务契约（M4）— 托盘关窗分流 / Agent 完成通知 / 全局快捷键应用 / 设置往返
import { describe, expect, it } from 'vitest'
import { openNodeSqlite } from '@main/db/adapters'
import { runMigrations } from '@main/db/migrations'
import { SettingsService } from '@main/services/settings.service'
import { DesktopIntegrationService, type DesktopPrimitives } from '@main/services/desktop/desktop-integration.service'

interface FakeState {
  notifyCalls: { title: string; body: string }[]
  focusCalls: number
  hideCalls: number
  quitCalls: number
  registered: Map<string, () => void>
  unregisterCalls: string[]
}

function makeFake(visible: boolean = false) {
  const st: FakeState = {
    notifyCalls: [], focusCalls: 0, hideCalls: 0, quitCalls: 0,
    registered: new Map(), unregisterCalls: []
  }
  const prims: DesktopPrimitives = {
    isWindowVisible: () => visible,
    focusWindow() { st.focusCalls++ },
    hideWindow() { st.hideCalls++ },
    trayCreate() {},
    traySetToolTip() {},
    traySetContextMenu() {},
    trayOnLeftClick() {},
    trayDestroy() {},
    notify(title: string, body: string) { st.notifyCalls.push({ title, body }) },
    registerGlobalShortcut(acc: string, cb: () => void) { st.registered.set(acc, cb); return true },
    unregisterGlobalShortcut(acc: string) { st.unregisterCalls.push(acc); st.registered.delete(acc) },
    getSetting: () => undefined,
    setSetting: () => undefined,
    quit() { st.quitCalls++ }
  }
  return { prims, st }
}

function makeSvc(prims: DesktopPrimitives): DesktopIntegrationService {
  return new DesktopIntegrationService(prims)
}

describe('Agent 回合完成通知', () => {
  it('窗口可见 → 不通知', () => {
    const { prims, st } = makeFake(true)
    const svc = makeSvc(prims)
    svc.onAgentTurnComplete('会话', '回复首行')
    expect(st.notifyCalls).toHaveLength(0)
  })

  it('窗口不可见 → 通知恰一次，标题与截断正文正确', () => {
    const { prims, st } = makeFake(false)
    const svc = makeSvc(prims)
    svc.onAgentTurnComplete('臭氧组会', '第一行回复\n第二行\n第三行')
    expect(st.notifyCalls).toHaveLength(1)
    expect(st.notifyCalls[0].title).toBe('臭氧组会')
    expect(st.notifyCalls[0].body).toBe('第一行回复')
  })

  it('通知点击 → 聚焦回调注入正确', () => {
    const { prims, st } = makeFake(false)
    const svc = makeSvc(prims)
    svc.onAgentTurnComplete('会话', '回复')
    expect(st.notifyCalls).toHaveLength(1)
    expect(st.focusCalls).toBe(0) // 尚未点击
  })
})

describe('关窗行为分流', () => {
  it('默认 → 最小化到托盘 + 首次通知告知', () => {
    const { prims, st } = makeFake(true)
    const svc = makeSvc(prims)
    const r = svc.handleMainWindowClose()
    expect(r).toBe('tray')
    expect(st.hideCalls).toBe(1)
    expect(st.notifyCalls).toHaveLength(1)
    expect(st.notifyCalls[0].body).toContain('托盘')
  })

  it('第二次关窗 → 仍走托盘但不再重复通知', () => {
    const { prims, st } = makeFake(true)
    const svc = makeSvc(prims)
    svc.handleMainWindowClose()
    svc.handleMainWindowClose()
    expect(st.hideCalls).toBe(2)
    expect(st.notifyCalls).toHaveLength(1) // 仅首次
  })

  it('closeAction=exit → 返回 quit（放行关闭，不隐藏）', () => {
    const { prims, st } = makeFake(true)
    const prims2 = { ...prims, getSetting: (key: string) => (key === 'desktop.closeAction' ? 'exit' : undefined) }
    const svc = new DesktopIntegrationService(prims2 as DesktopPrimitives)
    const r = svc.handleMainWindowClose()
    expect(r).toBe('quit')
    expect(st.hideCalls).toBe(0)
  })
})

describe('全局快捷键应用', () => {
  it('注册成功 — registerGlobalShortcut 收到 accelerator', () => {
    const { prims, st } = makeFake()
    const svc = new DesktopIntegrationService(prims)
    const r = svc.applyGlobalShortcut('Ctrl+Alt+M')
    expect(r.ok).toBe(true)
    expect(st.registered.get('Ctrl+Alt+M')).toBeDefined()
  })

  it('注册失败降级 — 返回 ok:false + 错误原因', () => {
    const { prims } = makeFake()
    const svc = new DesktopIntegrationService(
      { ...prims, registerGlobalShortcut: () => false }
    )
    const r = svc.applyGlobalShortcut('Ctrl+Alt+M')
    expect(r.ok).toBe(false)
    expect(r.error).toContain('冲突')
  })

  it('空串 = 禁用 — 注销旧快捷键', () => {
    const { prims, st } = makeFake()
    const svc = new DesktopIntegrationService(prims)
    svc.applyGlobalShortcut('Ctrl+Alt+M')
    const r = svc.applyGlobalShortcut('')
    expect(r.ok).toBe(true)
    expect(st.unregisterCalls).toContain('Ctrl+Alt+M')
    expect(st.registered.size).toBe(0)
  })

  it('重新应用 — 先注销旧组合再注册新组合', () => {
    const { prims, st } = makeFake()
    const svc = makeSvc(prims)
    svc.applyGlobalShortcut('Ctrl+Alt+M')
    svc.applyGlobalShortcut('Ctrl+Alt+N')
    expect(st.unregisterCalls).toContain('Ctrl+Alt+M')
    expect(st.registered.has('Ctrl+Alt+M')).toBe(false)
    expect(st.registered.has('Ctrl+Alt+N')).toBe(true)
  })
})

describe('设置往返', () => {
  it('关闭行为与全局快捷键经 SettingsService 存取', () => {
    const db = openNodeSqlite(':memory:')
    runMigrations(db)
    const settings = new SettingsService(db)
    settings.set('desktop.closeAction', 'exit', 'user-a')
    settings.set('desktop.globalShortcut', 'Ctrl+Alt+P', 'user-a')
    expect(settings.get('desktop.closeAction', 'user-a')).toBe('exit')
    expect(settings.get('desktop.globalShortcut', 'user-a')).toBe('Ctrl+Alt+P')
    db.close()
  })
})
