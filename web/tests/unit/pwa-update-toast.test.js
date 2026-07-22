import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import PwaUpdateToast from '../../src/components/PwaUpdateToast.vue'

function makeServiceWorker() {
  const listeners = new Map()
  return {
    addEventListener: vi.fn((type, handler) => listeners.set(type, handler)),
    removeEventListener: vi.fn((type) => listeners.delete(type)),
    emit(type, event) {
      listeners.get(type)?.(event)
    },
  }
}

describe('PwaUpdateToast — Service Worker 更新提示', () => {
  let serviceWorker

  beforeEach(() => {
    localStorage.clear()
    serviceWorker = makeServiceWorker()
    Object.defineProperty(navigator, 'serviceWorker', {
      configurable: true,
      value: serviceWorker,
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('收到 SW_UPDATED 后显示版本提示', async () => {
    const wrapper = mount(PwaUpdateToast)
    serviceWorker.emit('message', { data: { type: 'SW_UPDATED', version: 'v81' } })
    await nextTick()

    expect(wrapper.find('[data-testid="pwa-update-toast"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('v81')
    wrapper.unmount()
  })

  it('点击点此刷新会调用 window.location.reload', async () => {
    const reload = vi.spyOn(window.location, 'reload').mockImplementation(() => {})
    const wrapper = mount(PwaUpdateToast)
    serviceWorker.emit('message', { data: { type: 'SW_UPDATED', version: 'v81' } })
    await nextTick()

    await wrapper.find('[data-testid="pwa-update-toast-refresh"]').trigger('click')
    expect(reload).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('点击忽略会按版本持久化并关闭提示', async () => {
    const wrapper = mount(PwaUpdateToast)
    serviceWorker.emit('message', { data: { type: 'SW_UPDATED', version: 'v81' } })
    await nextTick()

    await wrapper.find('[data-testid="pwa-update-toast-dismiss"]').trigger('click')
    expect(localStorage.getItem('pwa_update_dismissed_v81')).toBe('1')
    expect(localStorage.getItem('pwa_update_dismissed_v81_at')).not.toBeNull()
    expect(wrapper.find('[data-testid="pwa-update-toast"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('同一版本在 7 天内不会再次显示', async () => {
    localStorage.setItem('pwa_update_dismissed_v81', '1')
    localStorage.setItem('pwa_update_dismissed_v81_at', String(Date.now() - 24 * 60 * 60 * 1000))
    const wrapper = mount(PwaUpdateToast)
    serviceWorker.emit('message', { data: { type: 'SW_UPDATED', version: 'v81' } })
    await flushPromises()

    expect(wrapper.find('[data-testid="pwa-update-toast"]').exists()).toBe(false)
    wrapper.unmount()
  })
})
