// @vitest-environment jsdom
// M6-1 设置页「关于与更新」区块 — 渲染与交互契约
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { UpdateState } from '@shared/types'

const { confirmMock } = vi.hoisted(() => ({ confirmMock: vi.fn() }))

vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
  ElMessageBox: { confirm: confirmMock }
}))

// eslint-disable-next-line import/first
import AboutUpdateSection from '@renderer/components/settings/AboutUpdateSection.vue'

function stateOf(patch: Partial<UpdateState>): UpdateState {
  return { status: 'idle', version: null, percent: 0, error: null, disabled: false, checkedAt: null, ...patch }
}

function stubApi(state: UpdateState, installResult = true): {
  install: ReturnType<typeof vi.fn>
  download: ReturnType<typeof vi.fn>
  setSetting: ReturnType<typeof vi.fn>
} {
  const install = vi.fn().mockResolvedValue(installResult)
  const download = vi.fn().mockResolvedValue(state)
  const setSetting = vi.fn().mockResolvedValue(undefined)
  Object.assign(window, {
    api: {
      app: { info: vi.fn().mockResolvedValue({ version: '0.1.4-alpha', platform: 'win32', dbPath: 'x', appName: '小气' }) },
      settings: { get: vi.fn().mockResolvedValue(undefined), set: setSetting },
      update: {
        state: vi.fn().mockResolvedValue(state),
        check: vi.fn().mockResolvedValue(state),
        download,
        install,
        onStateChange: vi.fn().mockReturnValue(() => undefined),
        onOpenSettings: vi.fn().mockReturnValue(() => undefined)
      }
    }
  })
  return { install, download, setSetting }
}

beforeEach(() => {
  confirmMock.mockReset()
  confirmMock.mockResolvedValue('confirm')
})

describe('「关于与更新」区块 — 渲染', () => {
  it('展示当前版本，并按状态渲染可用动作', async () => {
    stubApi(stateOf({ status: 'downloading', version: '0.1.5-alpha', percent: 37 }))
    const w = mount(AboutUpdateSection)
    await flushPromises()

    expect(w.get('[data-testid="update-current-version"]').text()).toBe('v0.1.4-alpha')
    expect(w.get('[data-testid="update-status"]').text()).toContain('正在下载 v0.1.5-alpha')
    expect(w.get('[data-testid="update-progress"]').text()).toContain('37%')
    expect(w.get('[data-testid="update-install-btn"]').attributes('disabled')).toBeDefined()
    expect(w.find('[data-testid="update-download-btn"]').exists()).toBe(false)
  })

  it('开发环境（disabled）显示说明且「检查更新」按钮禁用', async () => {
    stubApi(stateOf({ status: 'idle', disabled: true }))
    const w = mount(AboutUpdateSection)
    await flushPromises()

    expect(w.get('[data-testid="update-disabled-hint"]').text()).toContain('开发环境')
    expect(w.get('[data-testid="update-check-btn"]').attributes('disabled')).toBeDefined()
    expect(w.get('[data-testid="update-install-btn"]').attributes('disabled')).toBeDefined()
  })
})

describe('「关于与更新」区块 — 交互', () => {
  it('available 态出现「下载更新」，点击调用 download', async () => {
    const { download } = stubApi(stateOf({ status: 'available', version: '0.1.5-alpha' }))
    const w = mount(AboutUpdateSection)
    await flushPromises()

    const btn = w.get('[data-testid="update-download-btn"]')
    expect(btn.text()).toContain('下载更新')
    await btn.trigger('click')
    await flushPromises()
    expect(download).toHaveBeenCalledTimes(1)
  })

  it('ready 态「安装并重启」可用；二次确认后才真正安装，取消则不安装', async () => {
    const { install } = stubApi(stateOf({ status: 'ready', version: '0.1.5-alpha', percent: 100 }))
    const w = mount(AboutUpdateSection)
    await flushPromises()

    const btn = w.get('[data-testid="update-install-btn"]')
    expect(btn.attributes('disabled')).toBeUndefined()

    // 取消 → 不安装
    confirmMock.mockRejectedValueOnce(new Error('cancel'))
    await btn.trigger('click')
    await flushPromises()
    expect(confirmMock).toHaveBeenCalledTimes(1)
    expect(install).not.toHaveBeenCalled()

    // 确认 → 安装
    await btn.trigger('click')
    await flushPromises()
    expect(install).toHaveBeenCalledTimes(1)
  })

  it('「自动检查更新」开关写入 settings 通道（键 update.autoCheck）', async () => {
    const { setSetting } = stubApi(stateOf({ status: 'idle' }))
    const w = mount(AboutUpdateSection)
    await flushPromises()

    const input = w.get('[data-testid="update-auto-switch"]')
    expect((input.element as HTMLInputElement).checked).toBe(true) // 默认开
    await input.setValue(false)
    await flushPromises()
    expect(setSetting).toHaveBeenCalledWith('update.autoCheck', false)
  })
})

describe('「关于与更新」区块 — 跳过场景文案诚实性（M6-1 打回项 2）', () => {
  it('disabled 时状态为「更新检查不可用（开发环境）」，绝不出现「已是最新」', async () => {
    // 故意带上 checkedAt（模拟"曾经检查过"），disabled 必须压过"已是最新"语义
    stubApi(stateOf({ status: 'idle', disabled: true, checkedAt: Date.now() }))
    const w = mount(AboutUpdateSection)
    await flushPromises()

    expect(w.get('[data-testid="update-status"]').text()).toBe('更新检查不可用（开发环境）')
    expect(w.text()).not.toContain('已是最新')
    expect(w.get('[data-testid="update-disabled-hint"]').text()).toContain('更新检查不可用（开发环境）')
  })

  it('对照：正常 idle + checkedAt 仍显示「已是最新版本」（未误伤正常语义）', async () => {
    stubApi(stateOf({ status: 'idle', disabled: false, checkedAt: Date.now() }))
    const w = mount(AboutUpdateSection)
    await flushPromises()

    expect(w.get('[data-testid="update-status"]').text()).toContain('已是最新版本')
    expect(w.find('[data-testid="update-disabled-hint"]').exists()).toBe(false)
  })
})
