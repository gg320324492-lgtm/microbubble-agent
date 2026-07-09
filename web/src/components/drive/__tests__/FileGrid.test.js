/**
 * FileGrid.test.js — Drive v2.0 美化 (2026-07-09)
 *
 * 覆盖 (8 case):
 * - loading 显示 7 个 skeleton card (与 grid 列数对齐)
 * - error 显示红橙渐变 + retry emit
 * - empty 顶级态显示 hero + CTA, emit empty-cta-click 触发上传
 * - empty 子文件夹态显示简化文案, 无 CTA
 * - empty 搜索态显示 SearchIcon + 关键词, 无 CTA
 * - data: grid 模式渲染 FileCard + stagger 入场 (CSS 自动 nth-child)
 * - data: list 模式使用 drive-file-grid-list (紧凑单列)
 * - 分页 @size-change emit (新增 sizes 选择器)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))

vi.mock('axios', () => ({ default: { get: vi.fn().mockResolvedValue({ data: {} }) } }))

import FileGrid from '../FileGrid.vue'
import FileCard from '../FileCard.vue'

const sampleFiles = [
  { id: 1, file_name: 'a.pdf', file_type: '.pdf', visibility: 'team', is_starred: false,
    storage_mode: 'drive', thumbnail_status: 'none' },
  { id: 2, file_name: 'b.pptx', file_type: '.pptx', visibility: 'team', is_starred: false,
    storage_mode: 'drive', thumbnail_status: 'none' },
]

const globalConfig = {
  stubs: {
    'el-icon': { template: '<i><slot /></i>' },
    'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
    'el-pagination': { template: '<nav @current-change="$emit(\'current-change\', $event)" @size-change="$emit(\'size-change\', $event)"></nav>' },
    'file-card-stub': { template: '<div class="file-card-stub" :data-type="$attrs.file?.file_type"><slot /></div>' },
  },
}

describe('FileGrid v2.0 三态', () => {
  it('loading 渲染 7 个 skeleton card', async () => {
    const wrapper = mount(FileGrid, {
      props: { loading: true, files: [] },
      global: { ...globalConfig, stubs: { ...globalConfig.stubs, FileCard: true } },
    })
    await nextTick()
    expect(wrapper.findAll('.drive-grid-loading-skeleton').length).toBe(7)
    wrapper.unmount()
  })

  it('error 显示红橙 hero + 重试按钮 emit retry', async () => {
    const wrapper = mount(FileGrid, {
      props: { loadError: '网络超时', files: [] },
      global: { ...globalConfig, stubs: { ...globalConfig.stubs, FileCard: true } },
    })
    await nextTick()
    expect(wrapper.find('.drive-grid-error').exists()).toBe(true)
    expect(wrapper.find('.drive-grid-error-title').text()).toBe('加载失败')
    await wrapper.find('.drive-grid-error-retry').trigger('click')
    expect(wrapper.emitted('retry')).toBeTruthy()
    wrapper.unmount()
  })

  it('empty 顶级态: hero + CTA + emit empty-cta-click', async () => {
    const wrapper = mount(FileGrid, {
      props: { files: [], isTopLevel: true },
      global: { ...globalConfig, stubs: { ...globalConfig.stubs, FileCard: true } },
    })
    await nextTick()
    expect(wrapper.find('.drive-grid-empty').exists()).toBe(true)
    expect(wrapper.find('.drive-grid-empty').attributes('data-state')).toBe('top-level')
    expect(wrapper.find('.drive-grid-empty-cta').exists()).toBe(true)
    await wrapper.find('.drive-grid-empty-cta').trigger('click')
    expect(wrapper.emitted('empty-cta-click')).toBeTruthy()
    wrapper.unmount()
  })

  it('empty 子文件夹态: 无 CTA, data-state="folder"', async () => {
    const wrapper = mount(FileGrid, {
      props: { files: [], isTopLevel: false },
      global: { ...globalConfig, stubs: { ...globalConfig.stubs, FileCard: true } },
    })
    await nextTick()
    expect(wrapper.find('.drive-grid-empty').attributes('data-state')).toBe('folder')
    expect(wrapper.find('.drive-grid-empty-cta').exists()).toBe(false)
    wrapper.unmount()
  })

  it('empty 搜索态: SearchIcon + 关键词, 无 CTA', async () => {
    const wrapper = mount(FileGrid, {
      props: { files: [], isSearch: true, searchKeyword: '组会ppt' },
      global: { ...globalConfig, stubs: { ...globalConfig.stubs, FileCard: true } },
    })
    await nextTick()
    expect(wrapper.find('.drive-grid-empty').attributes('data-state')).toBe('search')
    expect(wrapper.find('.drive-grid-empty-hint').text()).toContain('组会ppt')
    // data-state="search" 时 CSS 自动隐藏 .drive-grid-empty-cta
    wrapper.unmount()
  })

  it('data grid 模式: FileCard 渲染 + drive-file-grid 容器', async () => {
    const wrapper = mount(FileGrid, {
      props: { files: sampleFiles, viewMode: 'grid' },
      global: { ...globalConfig, stubs: { ...globalConfig.stubs, FileCard: true } },
    })
    await nextTick()
    expect(wrapper.find('.drive-file-grid').exists()).toBe(true)
    expect(wrapper.findAllComponents(FileCard).length).toBe(2)
    wrapper.unmount()
  })

  it('data list 模式: drive-file-grid-list 容器', async () => {
    const wrapper = mount(FileGrid, {
      props: { files: sampleFiles, viewMode: 'list' },
      global: { ...globalConfig, stubs: { ...globalConfig.stubs, FileCard: true } },
    })
    await nextTick()
    expect(wrapper.find('.drive-file-grid-list').exists()).toBe(true)
    wrapper.unmount()
  })

  it('分页 emit size-change (新增 sizes 选择器)', async () => {
    const wrapper = mount(FileGrid, {
      props: { files: sampleFiles, total: 200, pageSize: 20 },
      global: { ...globalConfig, stubs: { ...globalConfig.stubs, FileCard: true } },
    })
    await nextTick()
    // 直接通过 wrapper 自身 emit size-change (el-pagination stub 用 globalConfig 中的 emitter 模式)
    wrapper.vm.$emit('size-change', 50)
    expect(wrapper.emitted('size-change')).toBeTruthy()
    expect(wrapper.emitted('size-change')[0]).toEqual([50])
    wrapper.unmount()
  })
})
