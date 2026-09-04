/**
 * MobileFileRequestView.test.js — 批次② F1 mount-smoke (薄包装)
 * 覆盖: PageHeader 标题 + FileRequestListPanel 被渲染 (stub)
 */
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('@/views/drive/drive-view.css', () => ({}))

const PanelStub = { name: 'FileRequestListPanel', template: '<div class="panel-stub">panel</div>' }
vi.mock('@/components/drive/FileRequestListPanel.vue', () => ({
  default: { name: 'FileRequestListPanel', template: '<div class="panel-stub">panel</div>' },
}))

const PageHeaderStub = {
  template: '<div class="page-header-stub">{{ title }}</div>',
  props: ['title', 'showBack'],
}

import MobileFileRequestView from '../MobileFileRequestView.vue'

describe('MobileFileRequestView (F1 mount-smoke)', () => {
  it('渲染 PageHeader "文件请求" + 内嵌 FileRequestListPanel', () => {
    const w = mount(MobileFileRequestView, {
      global: {
        stubs: { PageHeader: PageHeaderStub, FileRequestListPanel: PanelStub },
        mocks: { $router: { back: vi.fn() } },
      },
    })
    expect(w.text()).toContain('文件请求')
    expect(w.find('.panel-stub').exists()).toBe(true)
    w.unmount()
  })
})
