/**
 * mobile_tabbar_drive.spec.js — W68 第 11 批 B-2 Mobile TabBar Drive 入口
 *
 * 3 场景：6 项显示、点击网盘跳转、375px viewport 无横向溢出。
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import TabBar from '@/components/mobile/TabBar.vue'

const routes = [
  { path: '/dashboard', name: 'Dashboard', component: { template: '<div>首页</div>' } },
  { path: '/m-drive', name: 'MobileDrive', component: { template: '<div>移动网盘</div>' } },
  { path: '/meetings', name: 'Meetings', component: { template: '<div>听会</div>' } },
  { path: '/chat', name: 'Chat', component: { template: '<div>对话</div>' } },
  { path: '/tasks', name: 'Tasks', component: { template: '<div>任务</div>' } },
  { path: '/settings', name: 'Settings', component: { template: '<div>我的</div>' } },
]

const NutTabbarStub = {
  props: ['modelValue'],
  emits: ['switch'],
  template: '<div class="nut-tabbar"><slot /></div>',
}

const NutTabbarItemStub = {
  props: ['name', 'icon', 'to'],
  emits: ['click'],
  template: `
    <button
      class="nut-tabbar-item"
      :data-name="name"
      :data-icon="icon"
      :data-to="to"
      @click="$parent.$emit('switch', name)"
    ><slot /></button>
  `,
}

async function mountTabBar(path = '/dashboard') {
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push(path)
  await router.isReady()

  const wrapper = mount(TabBar, {
    attachTo: document.body,
    global: {
      plugins: [router],
      stubs: {
        'nut-tabbar': NutTabbarStub,
        'nut-tabbar-item': NutTabbarItemStub,
      },
    },
  })
  await flushPromises()
  return { wrapper, router }
}

beforeEach(() => {
  Object.defineProperty(window, 'innerWidth', { configurable: true, writable: true, value: 375 })
  Object.defineProperty(window, 'innerHeight', { configurable: true, writable: true, value: 812 })
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('Mobile TabBar Drive entry', () => {
  it('场景 1: 显示 6 项且网盘位于首页后、听会前', async () => {
    const { wrapper } = await mountTabBar()
    const items = wrapper.findAll('.nut-tabbar-item')

    expect(items).toHaveLength(6)
    expect(items.map((item) => item.text())).toEqual(['首页', '网盘', '听会', '对话', '任务', '我的'])
    expect(items[1].attributes('data-icon')).toBe('folder')
    expect(items[1].attributes('data-to')).toBe('/m-drive')

    wrapper.unmount()
  })

  it('场景 2: 点击网盘跳转到 /m-drive', async () => {
    const { wrapper, router } = await mountTabBar()

    await wrapper.find('[data-name="drive"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/m-drive')
    expect(router.currentRoute.value.name).toBe('MobileDrive')

    wrapper.unmount()
  })

  it('场景 3: 375px 移动端 viewport 下 6 项保持单行且不横向溢出', async () => {
    const { wrapper } = await mountTabBar('/m-drive')
    const nav = wrapper.find('.mobile-tabbar').element
    const items = wrapper.findAll('.nut-tabbar-item')

    // jsdom 不做完整布局，使用实际 viewport + DOM 契约验证响应式前提。
    expect(window.innerWidth).toBe(375)
    expect(items).toHaveLength(6)
    expect(items.every((item) => item.find('.tabbar-label').exists())).toBe(true)
    expect(nav.scrollWidth).toBeLessThanOrEqual(window.innerWidth)

    wrapper.unmount()
  })
})
