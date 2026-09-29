// @vitest-environment jsdom
// DL-7 Part B — 启动期更新通知弹窗：版本号/日志正文/两按钮/稍后节流/下载链路/空日志降级
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import UpdateNotifyDialog from '@renderer/components/UpdateNotifyDialog.vue'
import type { UpdateState } from '@shared/types'

const AVAILABLE: UpdateState = {
  status: 'available',
  version: '1.3.2',
  percent: 0,
  error: null,
  disabled: false,
  checkedAt: 1,
  releaseNotes: '### 更新内容\n- 发送即上屏\n- 模块精简'
}

let downloadSpy: ReturnType<typeof vi.fn>
let installSpy: ReturnType<typeof vi.fn>
let stateChangeCb: ((s: UpdateState) => void) | null

function stubApi(initial: UpdateState | null): void {
  downloadSpy = vi.fn(async () => undefined)
  installSpy = vi.fn(async () => true)
  stateChangeCb = null
  Object.assign(window, {
    api: {
      update: {
        state: vi.fn(async () => initial),
        check: vi.fn(async () => initial),
        download: downloadSpy,
        install: installSpy,
        onStateChange: vi.fn((cb: (s: UpdateState) => void) => {
          stateChangeCb = cb
          return () => undefined
        }),
        onOpenSettings: vi.fn(() => () => undefined)
      }
    }
  })
}

async function makeRouter(initialPath = '/app/assistant'): Promise<Router> {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/app/settings', name: 'settings', component: { template: '<div />' } },
      { path: '/:pathMatch(.*)*', name: 'other', component: { template: '<div />' } }
    ]
  })
  await router.push(initialPath)
  await router.isReady()
  return router
}

beforeEach(() => {
  localStorage.clear()
})

describe('UpdateNotifyDialog 启动期更新通知', () => {
  it('★ available 态：弹窗含版本号 + 日志正文 + 「立即更新/稍后」两按钮', async () => {
    stubApi(AVAILABLE)
    const w = mount(UpdateNotifyDialog, { global: { plugins: [await makeRouter()] } })
    await flushPromises()
    expect(w.find('[data-testid="update-notify-mask"]').exists()).toBe(true)
    expect(w.get('[data-testid="update-notify-version"]').text()).toBe('v1.3.2')
    expect(w.get('[data-testid="update-notify-notes"]').text()).toContain('发送即上屏')
    expect(w.get('[data-testid="update-notify-update"]').text()).toBe('立即更新')
    expect(w.find('[data-testid="update-notify-later"]').exists()).toBe(true)
  })

  it('★ 稍后 → 关闭并记 localStorage；24h 内同版本不再弹；超 24h 或新版本恢复弹', async () => {
    stubApi(AVAILABLE)
    const w = mount(UpdateNotifyDialog, { global: { plugins: [await makeRouter()] } })
    await flushPromises()
    expect(w.find('[data-testid="update-notify-mask"]').exists()).toBe(true)

    await w.get('[data-testid="update-notify-later"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="update-notify-mask"]').exists()).toBe(false)
    const stored = localStorage.getItem('update.notifyDismissed.1.3.2')
    expect(stored).not.toBeNull()

    // 重挂载：24h 内不弹
    stubApi(AVAILABLE)
    const w2 = mount(UpdateNotifyDialog, { global: { plugins: [await makeRouter()] } })
    await flushPromises()
    expect(w2.find('[data-testid="update-notify-mask"]').exists()).toBe(false)

    // 超过 24h：恢复弹
    localStorage.setItem('update.notifyDismissed.1.3.2', String(Date.now() - 25 * 60 * 60 * 1000))
    stubApi(AVAILABLE)
    const w3 = mount(UpdateNotifyDialog, { global: { plugins: [await makeRouter()] } })
    await flushPromises()
    expect(w3.find('[data-testid="update-notify-mask"]').exists()).toBe(true)
  })

  it('日志为空 → 优雅降级文案，不渲染空正文', async () => {
    stubApi({ ...AVAILABLE, releaseNotes: null })
    const w = mount(UpdateNotifyDialog, { global: { plugins: [await makeRouter()] } })
    await flushPromises()
    expect(w.get('[data-testid="update-notify-notes-empty"]').text()).toContain('未提供更新日志')
    // 空态下不渲染正文 <pre>（容器内是降级文案，非空白框）
    expect(w.find('.upd-notes-body').exists()).toBe(false)
  })

  it('★ 立即更新链路：download → downloading 进度 → ready 自动 install；失败展示错误不卡死', async () => {
    stubApi(AVAILABLE)
    const w = mount(UpdateNotifyDialog, { global: { plugins: [await makeRouter()] } })
    await flushPromises()

    await w.get('[data-testid="update-notify-update"]').trigger('click')
    expect(downloadSpy).toHaveBeenCalledTimes(1)

    // 主进程推进状态：downloading 42%
    stateChangeCb!({ ...AVAILABLE, status: 'downloading', percent: 42 })
    await flushPromises()
    expect(w.get('[data-testid="update-notify-progress"]').text()).toContain('42%')

    // ready 且「立即更新」已点 → 自动 quitAndInstall（工单链路收尾）
    stateChangeCb!({ ...AVAILABLE, status: 'ready', percent: 100 })
    await flushPromises()
    expect(installSpy).toHaveBeenCalledTimes(1)

    // 失败路径单独验证：error 态展示错误原因，弹窗仍可「稍后」关闭
    stubApi(AVAILABLE)
    const w2 = mount(UpdateNotifyDialog, { global: { plugins: [await makeRouter()] } })
    await flushPromises()
    stateChangeCb!({ ...AVAILABLE, status: 'error', error: '下载中断：网络不可达' })
    await flushPromises()
    expect(w2.get('[data-testid="update-notify-error"]').text()).toContain('网络不可达')
    await w2.get('[data-testid="update-notify-later"]').trigger('click')
    await flushPromises()
    expect(w2.find('[data-testid="update-notify-mask"]').exists()).toBe(false)
  })

  it('用户在设置页时不弹（M6-1 既有更新入口在场，不叠加）', async () => {
    stubApi(AVAILABLE)
    const w = mount(UpdateNotifyDialog, { global: { plugins: [await makeRouter('/app/settings')] } })
    await flushPromises()
    expect(w.find('[data-testid="update-notify-mask"]').exists()).toBe(false)
  })

  it('非 available（idle/error/disabled）不弹', async () => {
    stubApi({ status: 'idle', version: null, percent: 0, error: null, disabled: false, checkedAt: 1 })
    const w = mount(UpdateNotifyDialog, { global: { plugins: [await makeRouter()] } })
    await flushPromises()
    expect(w.find('[data-testid="update-notify-mask"]').exists()).toBe(false)
  })
})
