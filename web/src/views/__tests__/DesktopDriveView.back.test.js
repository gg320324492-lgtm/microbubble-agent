// DesktopDriveView.back.test.js — 后退箭头与「文件请求详情层」(2026-11-10)
//
// 事故 (主指挥实测): 在「文件请求 → 某个请求收到的文件」里按全局后退箭头,
// 界面直接回主界面 (课题组网盘根), 而不是回到文件请求列表。
// 根因: 详情是 FileRequestListPanel 的组件内部状态, 不在 DesktopDriveView 的
// navHistory 里 ⇒ 后退跳过这一层。
//
// 修法: 详情层不进历史 (不可重放), 但 navGo(-1) 遇到打开的详情时**先关详情**
// 且本次不消耗历史; 下一次后退才真正回上一个视图。
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))

import DesktopDriveView from '@/views/DesktopDriveView.vue'

// FileRequestListPanel 用 stub 替身: 暴露 closeDetail 供父层调用
const closeDetail = vi.hoisted(() => vi.fn())
const PanelStub = {
  name: 'FileRequestListPanel',
  template: '<div class="panel-stub" />',
  setup(_props, { expose }) { expose({ closeDetail }) },
  emits: ['detail-change'],
}

function mountView() {
  return shallowMount(DesktopDriveView, {
    global: { stubs: { FileRequestListPanel: PanelStub } },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal('fetch', vi.fn(async (url) => ({
    ok: true,
    json: async () => String(url).includes('/folders/tree')
      ? { tree: [], max_depth: 5 }
      : { items: [], total: 0 },
  })))
})
afterEach(() => { vi.unstubAllGlobals() })

describe('文件请求详情层的后退', () => {
  async function enterRequestDetail(w) {
    // 切到「文件请求」视图, 再模拟面板点进某个请求
    await w.vm.$refs.requestPanelRef // eslint-disable-line no-unused-expressions
    const panel = w.findComponent(PanelStub)
    // shallowMount 下 specialView 由 FolderTree 的 update:special-view 驱动;
    // 这里直接通过 vm 暴露的 setup 状态不可访问, 改用侧栏 stub 触发
    await w.findComponent({ name: 'FolderTree' }).vm.$emit('update:specialView', 'requests')
    await flushPromises()
    const p = w.findComponent(PanelStub)
    p.vm.$emit('detail-change', { open: true, title: '外部学习会议视频' })
    await flushPromises()
    return p
  }

  it('详情打开时按后退 ⇒ 只关详情, 不切视图 (不回主界面)', async () => {
    const w = mountView()
    await flushPromises()
    await enterRequestDetail(w)

    const backBtn = w.find('button[aria-label="后退"]')
    expect(backBtn.exists()).toBe(true)
    await backBtn.trigger('click')
    await flushPromises()

    expect(closeDetail).toHaveBeenCalledTimes(1)
    // 仍在文件请求视图 (specialView='requests'), 面包屑不再显示第三级
    expect(w.text()).toContain('文件请求')
    expect(w.text()).not.toContain('外部学习会议视频')
    w.unmount()
  })

  it('详情打开时面包屑显示第三级请求名; 关掉后回到两级', async () => {
    const w = mountView()
    await flushPromises()
    await enterRequestDetail(w)
    expect(w.text()).toContain('外部学习会议视频')

    await w.find('button[aria-label="后退"]').trigger('click')
    await flushPromises()
    expect(w.text()).not.toContain('外部学习会议视频')
    w.unmount()
  })
})
