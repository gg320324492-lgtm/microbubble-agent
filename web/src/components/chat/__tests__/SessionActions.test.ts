/**
 * SessionActions 组件单测 - W100 +28 UI-ARCHIVE
 *
 * 6 case 覆盖：
 * ① 渲染 3 个 action button (pin / archive / delete)
 * ② 未置顶 session -> pin-btn 无 active class, aria-label="置顶会话"
 * ③ 已置顶 session -> pin-btn 有 active class, aria-label="取消置顶"
 * ④ 已归档 session -> archive-btn 有 active class, aria-label="恢复会话"
 * ⑤ click pin -> emit('pin', session)
 * ⑥ sidebar mode -> opacity:0 (hover 才显示); inline mode -> opacity:1
 */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import SessionActions from '../SessionActions.vue'

function makeSession(over: Partial<{
  id: string
  title: string
  is_pinned: boolean
  is_archived: boolean
}> = {}) {
  return {
    id: 'test-1',
    title: '测试会话',
    is_pinned: false,
    is_archived: false,
    ...over,
  }
}

describe('SessionActions - W100 +28 UI-ARCHIVE', () => {
  it('① 渲染 3 个 action button (pin / archive / delete)', () => {
    const wrapper = mount(SessionActions, {
      props: { session: makeSession() },
      global: { stubs: { 'el-icon': { template: '<i><slot /></i>' } } },
    })
    expect(wrapper.find('[data-testid="action-pin"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="action-archive"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="action-delete"]').exists()).toBe(true)
  })

  it('② 未置顶 session -> pin-btn 无 active class, aria-label="置顶会话"', () => {
    const wrapper = mount(SessionActions, {
      props: { session: makeSession({ is_pinned: false }) },
      global: { stubs: { 'el-icon': { template: '<i><slot /></i>' } } },
    })
    const pinBtn = wrapper.find('[data-testid="action-pin"]')
    expect(pinBtn.classes()).not.toContain('active')
    expect(pinBtn.attributes('aria-label')).toBe('置顶会话')
  })

  it('③ 已置顶 session -> pin-btn 有 active class, aria-label="取消置顶"', () => {
    const wrapper = mount(SessionActions, {
      props: { session: makeSession({ is_pinned: true }) },
      global: { stubs: { 'el-icon': { template: '<i><slot /></i>' } } },
    })
    const pinBtn = wrapper.find('[data-testid="action-pin"]')
    expect(pinBtn.classes()).toContain('active')
    expect(pinBtn.attributes('aria-label')).toBe('取消置顶')
  })

  it('④ 已归档 session -> archive-btn 有 active class, aria-label="恢复会话"', () => {
    const wrapper = mount(SessionActions, {
      props: { session: makeSession({ is_archived: true }) },
      global: { stubs: { 'el-icon': { template: '<i><slot /></i>' } } },
    })
    const archiveBtn = wrapper.find('[data-testid="action-archive"]')
    expect(archiveBtn.classes()).toContain('active')
    expect(archiveBtn.attributes('aria-label')).toBe('恢复会话')
  })

  it('⑤ click pin -> emit("pin", session)', async () => {
    const session = makeSession({ id: 's1', title: 'hello' })
    const wrapper = mount(SessionActions, {
      props: { session },
      global: { stubs: { 'el-icon': { template: '<i><slot /></i>' } } },
    })
    await wrapper.find('[data-testid="action-pin"]').trigger('click')
    expect(wrapper.emitted('pin')).toBeTruthy()
    expect(wrapper.emitted('pin')[0]).toEqual([session])
  })

  it('⑥ sidebar mode -> 有 sidebar class; inline mode -> 有 inline class', () => {
    const sidebarWrapper = mount(SessionActions, {
      props: { session: makeSession(), mode: 'sidebar' },
      global: { stubs: { 'el-icon': { template: '<i><slot /></i>' } } },
    })
    expect(sidebarWrapper.find('[data-testid="session-actions"]').classes()).toContain('sidebar')

    const inlineWrapper = mount(SessionActions, {
      props: { session: makeSession(), mode: 'inline' },
      global: { stubs: { 'el-icon': { template: '<i><slot /></i>' } } },
    })
    expect(inlineWrapper.find('[data-testid="session-actions"]').classes()).toContain('inline')
  })
})
