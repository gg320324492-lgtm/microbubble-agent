// M6-1 更新服务 — 通知触发判定（复用 M4 模式）+ 编排 + 提示式边界
import { describe, expect, it, vi } from 'vitest'
import { UpdateService, type UpdaterPort } from '@main/services/update/update.service'
import type { UpdateState } from '@shared/types'

function makePort(overrides: Partial<UpdaterPort> = {}): {
  port: UpdaterPort
  progressCbs: ((p: number) => void)[]
  downloadedCbs: (() => void)[]
  checkSpy: ReturnType<typeof vi.fn>
  downloadSpy: ReturnType<typeof vi.fn>
  installSpy: ReturnType<typeof vi.fn>
} {
  const progressCbs: ((p: number) => void)[] = []
  const downloadedCbs: (() => void)[] = []
  const checkSpy = vi.fn().mockResolvedValue({ version: '0.1.5-alpha' })
  const downloadSpy = vi.fn().mockResolvedValue(undefined)
  const installSpy = vi.fn()
  const port: UpdaterPort = {
    checkForUpdates: checkSpy,
    downloadUpdate: downloadSpy,
    quitAndInstall: installSpy,
    onProgress: (cb) => progressCbs.push(cb),
    onDownloaded: (cb) => downloadedCbs.push(cb),
    ...overrides
  }
  return { port, progressCbs, downloadedCbs, checkSpy, downloadSpy, installSpy }
}

function makeService(opts: {
  port: UpdaterPort
  windowVisible?: boolean
  envSupported?: boolean
  autoCheck?: boolean
}): { svc: UpdateService; notify: ReturnType<typeof vi.fn>; states: UpdateState[] } {
  const notify = vi.fn()
  const states: UpdateState[] = []
  const svc = new UpdateService({
    currentVersion: '0.1.4-alpha',
    envSupported: opts.envSupported ?? true,
    port: opts.port,
    getSetting: (key) => (key === 'update.autoCheck' ? opts.autoCheck : undefined),
    isWindowVisible: () => opts.windowVisible ?? false,
    notify,
    onOpenSettings: vi.fn(),
    onStateChange: (s) => states.push(s)
  })
  return { svc, notify, states }
}

describe('更新服务 — 通知触发判定（复用 M4 窗口可见性模式）', () => {
  it('窗口不可见 + 发现新版本 → 弹系统通知；窗口可见 → 不打扰', async () => {
    const hidden = makePort()
    const a = makeService({ port: hidden.port, windowVisible: false })
    await a.svc.check('manual')
    expect(a.svc.snapshot().status).toBe('available')
    expect(a.notify).toHaveBeenCalledTimes(1)
    expect(a.notify.mock.calls[0][0]).toContain('0.1.5-alpha')

    const visible = makePort()
    const b = makeService({ port: visible.port, windowVisible: true })
    await b.svc.check('manual')
    expect(b.svc.snapshot().status).toBe('available')
    expect(b.notify).not.toHaveBeenCalled()
  })

  it('无更新（feed 返回更旧或同版本）不通知，状态回到 idle', async () => {
    const older = makePort({ checkForUpdates: vi.fn().mockResolvedValue({ version: '0.1.3-alpha' }) })
    const { svc, notify } = makeService({ port: older.port, windowVisible: false })
    await svc.check('manual')
    expect(svc.snapshot().status).toBe('idle')
    expect(svc.snapshot().version).toBeNull()
    expect(notify).not.toHaveBeenCalled()

    const same = makePort({ checkForUpdates: vi.fn().mockResolvedValue({ version: '0.1.4-alpha' }) })
    const b = makeService({ port: same.port })
    await b.svc.check('manual')
    expect(b.svc.snapshot().status).toBe('idle')
  })
})

describe('更新服务 — 开关与禁用态边界', () => {
  it('「自动检查更新」关闭只拦截启动自动检查，手动检查仍可用', async () => {
    const off = makePort()
    const a = makeService({ port: off.port, autoCheck: false })
    await a.svc.check('auto')
    expect(off.checkSpy).not.toHaveBeenCalled()
    expect(a.svc.snapshot().status).toBe('idle')

    await a.svc.check('manual')
    expect(off.checkSpy).toHaveBeenCalledTimes(1)
    expect(a.svc.snapshot().status).toBe('available')
  })

  it('环境不支持（非打包且无 feed 覆盖）→ 完全禁用，不发起检查也不通知', async () => {
    const p = makePort()
    const { svc, notify } = makeService({ port: p.port, envSupported: false, windowVisible: false })
    expect(svc.snapshot().disabled).toBe(true)

    await svc.check('manual')
    await svc.check('auto')
    expect(p.checkSpy).not.toHaveBeenCalled()
    expect(notify).not.toHaveBeenCalled()
    expect(svc.snapshot().status).toBe('idle')

    svc.setEnvSupported(true)
    expect(svc.snapshot().disabled).toBe(false)
    await svc.check('manual')
    expect(p.checkSpy).toHaveBeenCalledTimes(1)
  })
})

describe('更新服务 — 提示式下载与安装（绝不自动）', () => {
  it('available 才能下载；下载完成由端口回调推到 ready；安装需显式调用', async () => {
    const { port, progressCbs, downloadedCbs, downloadSpy, installSpy } = makePort()
    const { svc } = makeService({ port })

    // idle 态下载是空操作
    await svc.download()
    expect(downloadSpy).not.toHaveBeenCalled()
    expect(svc.installAndRestart()).toBe(false)
    expect(installSpy).not.toHaveBeenCalled()

    await svc.check('manual')
    await svc.download()
    expect(downloadSpy).toHaveBeenCalledTimes(1)
    expect(svc.snapshot().status).toBe('downloading')

    progressCbs.forEach((cb) => cb(66.6))
    expect(svc.snapshot().percent).toBe(67)

    downloadedCbs.forEach((cb) => cb())
    expect(svc.snapshot().status).toBe('ready')

    expect(svc.installAndRestart()).toBe(true)
    expect(installSpy).toHaveBeenCalledTimes(1)
  })

  it('检查抛错 → error 态并记录原因（后台检查静默不抛）', async () => {
    const p = makePort({ checkForUpdates: vi.fn().mockRejectedValue(new Error('feed 不可达')) })
    const logs: string[] = []
    const svc = new UpdateService({
      currentVersion: '0.1.4-alpha',
      envSupported: true,
      port: p.port,
      getSetting: () => undefined,
      isWindowVisible: () => true,
      notify: vi.fn(),
      onOpenSettings: vi.fn(),
      log: (m) => logs.push(m)
    })

    await expect(svc.check('auto')).resolves.toBeDefined()
    expect(svc.snapshot().status).toBe('error')
    expect(svc.snapshot().error).toBe('feed 不可达')
    expect(logs.some((l) => l.includes('feed 不可达'))).toBe(true)
  })
})
