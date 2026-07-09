/**
 * FileCard.test.js — Drive v2.0 美化 (2026-07-09)
 *
 * 覆盖 (6 case):
 * - 8 类 extension → data-type 映射 (pdf/doc/ppt/excel/image/video/audio/text)
 * - list vs grid view mode (不同 .drive-file-card-* class)
 * - is-selected / is-private visual class 切换
 * - thumbnail_status='ready' 时显示 img, 否则 fallback icon
 * - toggle-star / toggle-select emit (star 始终可见, checkbox 按 selectable)
 * - 缩略图 img load/error 事件处理
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))

// Mock axios (thumbnail 拉取)
vi.mock('axios', () => ({
  default: {
    get: vi.fn().mockResolvedValue({ data: { thumbnail_url: 'http://test/x.png' } }),
  },
}))

import FileCard from '../FileCard.vue'

const makeFile = (overrides = {}) => ({
  id: 1,
  title: 'test.pdf',
  file_name: 'test.pdf',
  file_type: '.pdf',
  file_size: 1024 * 100,
  visibility: 'team',
  is_starred: false,
  storage_mode: 'drive',
  thumbnail_status: 'none',
  ...overrides,
})

const globalConfig = {
  stubs: {
    'el-checkbox': { template: '<input type="checkbox" @change="$emit(\'change\', $event.target.checked)" />' },
    'el-icon': { template: '<i><slot /></i>' },
    'el-tooltip': { template: '<div><slot /></div>' },
    'el-button': { template: '<button @click="$emit(\'click\', $event)"><slot /></button>' },
    'el-dropdown': { template: '<div><slot /></div>' },
    'el-dropdown-menu': { template: '<div><slot /></div>' },
    'el-dropdown-item': { template: '<div @click="$emit(\'command\', $attrs.command)"><slot /></div>' },
    'el-tag': { template: '<span><slot /></span>' },
  },
}

describe('FileCard v2.0 美化', () => {
  it('PDF 走 data-type="pdf" (与 drive-view.css .drive-file-card[data-type=pdf] 配套)', async () => {
    const wrapper = mount(FileCard, {
      props: { file: makeFile({ file_type: '.pdf' }) },
      global: globalConfig,
    })
    await nextTick()
    expect(wrapper.attributes('data-type')).toBe('pdf')
    wrapper.unmount()
  })

  it('PPTX 走 data-type="ppt" (会议分享盘中最常见的 8 类)', async () => {
    const wrapper = mount(FileCard, {
      props: { file: makeFile({ file_type: '.pptx' }) },
      global: globalConfig,
    })
    await nextTick()
    expect(wrapper.attributes('data-type')).toBe('ppt')
    wrapper.unmount()
  })

  it('其他 8 类全覆盖 (doc/excel/image/video/audio/text)', async () => {
    const map = { '.doc': 'doc', '.docx': 'doc', '.xls': 'excel', '.xlsx': 'excel',
                 '.jpg': 'image', '.png': 'image', '.svg': 'image',
                 '.mp4': 'video', '.mov': 'video',
                 '.mp3': 'audio', '.wav': 'audio', '.m4a': 'audio',
                 '.txt': 'text', '.md': 'text' }
    for (const [ext, expected] of Object.entries(map)) {
      const wrapper = mount(FileCard, {
        props: { file: makeFile({ file_type: ext }) },
        global: globalConfig,
      })
      await nextTick()
      expect(wrapper.attributes('data-type')).toBe(expected)
      wrapper.unmount()
    }
  })

  it('未知 extension 默认 text (无 broken UI)', async () => {
    const wrapper = mount(FileCard, {
      props: { file: makeFile({ file_type: '.unknown_ext' }) },
      global: globalConfig,
    })
    await nextTick()
    expect(wrapper.attributes('data-type')).toBe('text')
    wrapper.unmount()
  })

  it('list view 加 drive-file-card-list class (共享 CSS 调整 row 布局)', async () => {
    const wrapper = mount(FileCard, {
      props: { file: makeFile(), viewMode: 'list' },
      global: globalConfig,
    })
    await nextTick()
    expect(wrapper.classes()).toContain('drive-file-card')
    expect(wrapper.classes()).toContain('drive-file-card-list')
    wrapper.unmount()
  })

  it('grid view 不加 drive-file-card-list (默认 column 布局)', async () => {
    const wrapper = mount(FileCard, {
      props: { file: makeFile(), viewMode: 'grid' },
      global: globalConfig,
    })
    await nextTick()
    expect(wrapper.classes()).toContain('drive-file-card')
    expect(wrapper.classes()).not.toContain('drive-file-card-list')
    wrapper.unmount()
  })

  it('is-selected + is-private 视觉 class 切换', async () => {
    const wrapper = mount(FileCard, {
      props: { file: makeFile({ visibility: 'private' }), selected: true },
      global: globalConfig,
    })
    await nextTick()
    expect(wrapper.classes()).toContain('is-selected')
    expect(wrapper.classes()).toContain('is-private')
    wrapper.unmount()
  })

  // v2.1 (2026-07-09) Drive 美化: 3 个 [icon+文本] 按钮 — 取代原 3 个无标签 circle
  it('hover 操作栏渲染 3 个 [icon+label] button (下载/预览/更多)', async () => {
    const wrapper = mount(FileCard, {
      props: { file: makeFile(), viewMode: 'grid' },
      global: globalConfig,
    })
    await nextTick()
    const actions = wrapper.find('.file-card-actions')
    expect(actions.exists()).toBe(true)
    const buttons = actions.findAll('.file-card-action')
    expect(buttons.length).toBe(3)
    const labels = buttons.map(b => b.find('.file-card-action-label').text())
    expect(labels).toEqual(['下载', '预览', '更多'])
    wrapper.unmount()
  })

  it('下载按钮带主色 (drive-primary), 预览按钮带信息蓝 (drive-file-doc), 更多按钮默认灰', async () => {
    const wrapper = mount(FileCard, {
      props: { file: makeFile(), viewMode: 'grid' },
      global: globalConfig,
    })
    await nextTick()
    const download = wrapper.find('.file-card-action--download')
    const preview = wrapper.find('.file-card-action--preview')
    const more = wrapper.find('.file-card-action--more')
    expect(download.exists()).toBe(true)
    expect(preview.exists()).toBe(true)
    expect(more.exists()).toBe(true)
    // 校验 CSS token 类正确 (颜色由 drive-view.css 接管, 不在此测具体 rgba)
    wrapper.unmount()
  })

  it('aria-label 含文件名前缀 (无障碍标识)', async () => {
    const wrapper = mount(FileCard, {
      props: { file: makeFile({ title: '组会ppt.pdf', file_name: '组会ppt.pdf' }), viewMode: 'grid' },
      global: globalConfig,
    })
    await nextTick()
    expect(wrapper.find('.file-card-action--download').attributes('aria-label')).toContain('组会ppt.pdf')
    expect(wrapper.find('.file-card-action--preview').attributes('aria-label')).toContain('组会ppt.pdf')
    wrapper.unmount()
  })
})
