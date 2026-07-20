/**
 * FileRequestListPanel.test.js — 2026-07-20 file-request QR code 实装验证
 *
 * 覆盖 (2 case):
 *   1. 初始 (previewUrl=空) → QrCode 不渲染, 提示文字也不显示
 *   2. onPreview(req) → previewUrl 写入, QrCode 渲染, value=公开 URL
 *
 * 复用: 真实 useFileRequests composable 注入 mock 数据 (避免 fetch network)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

// Element Plus stubs
const stubs = {
  'el-dialog': {
    template: '<div v-if="modelValue" class="el-dialog-stub"><slot /></div>',
    props: ['modelValue', 'title', 'width'],
  },
  'el-input': { template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />' },
  'el-button': { template: '<button @click="$emit(\'click\', $event)"><slot /></button>' },
  'el-icon': { template: '<i><slot /></i>' },
  'el-empty': { template: '<div class="el-empty-stub"><slot /></div>' },
  'el-switch': { template: '<input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" />' },
  'el-tag': { template: '<span><slot /></span>' },
  'el-form': { template: '<form><slot /></form>' },
  'el-form-item': { template: '<div><slot /></div>' },
  'el-select': { template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>' },
  'el-option': { template: '<option :value="value"><slot /></option>' },
  'el-input-number': { template: '<input type="number" :value="modelValue" @input="$emit(\'update:modelValue\', Number($event.target.value))" />' },
}

// Mock Element Plus messages
vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
  ElMessageBox: { confirm: vi.fn().mockResolvedValue('confirm') },
}))

// Mock Element Plus icons
vi.mock('@element-plus/icons-vue', () => ({
  Plus: { template: '<i />' },
}))

// Mock useFileRequests composable
const mockRequests = ref([])
const mockFetchMy = vi.fn()
const mockCreateRequest = vi.fn()
const mockDeactivate = vi.fn()
vi.mock('@/composables/useFileRequests', () => ({
  useFileRequests: () => ({
    requests: mockRequests,
    loading: ref(false),
    error: ref(null),
    hasRequests: computed(() => mockRequests.value.length > 0),
    fetchMy: mockFetchMy,
    createRequest: mockCreateRequest,
    deactivate: mockDeactivate,
  }),
}))

// Mock drive-view.css import (避免 .css 模块解析)
vi.mock('@/views/drive/drive-view.css', () => ({}))

import { ref, computed } from 'vue'
import FileRequestListPanel from '../FileRequestListPanel.vue'

// Mock QrCode 组件 — 避免真实 qrcode 库在 jsdom 下渲染 (jsdom 不支持 SVG 测量, 会 warn)
const mockQrCode = {
  template: '<div class="qrcode-mock" :data-value="value">{{ value }}</div>',
  props: ['value', 'size', 'level', 'fgColor', 'bgColor', 'margin'],
}
const globalConfig = {
  stubs: { ...stubs, QrCode: mockQrCode },
  mocks: {},
}

const makeReq = (overrides = {}) => ({
  id: 1,
  token: 'abc123token',
  title: '2026 秋季作业',
  description: '收作业',
  submission_count: 0,
  active: true,
  expired: false,
  ...overrides,
})

describe('FileRequestListPanel QR code 实装 (2026-07-20)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockRequests.value = [makeReq()]
  })

  it('初始 (previewUrl=空) → QrCode 不渲染, .preview-qr 也不显示', async () => {
    const wrapper = mount(FileRequestListPanel, { global: globalConfig })
    await nextTick()
    // showPreview 默认 false, Dialog 整块不渲染 (el-dialog stub v-if)
    expect(wrapper.find('.preview-qr').exists()).toBe(false)
    expect(wrapper.find('.qrcode-mock').exists()).toBe(false)
  })

  it('onPreview(req) → previewUrl 写入 + .preview-qr 渲染 + QrCode value 等于公开 URL', async () => {
    const wrapper = mount(FileRequestListPanel, { global: globalConfig })
    // 触发 preview dialog
    const previewBtn = wrapper.findAll('button').find(b => b.text() === '预览')
    expect(previewBtn).toBeTruthy()
    await previewBtn.trigger('click')
    await nextTick()
    await flushPromises()
    // Dialog 应打开, QrCode 应渲染
    const qrEl = wrapper.find('.qrcode-mock')
    expect(qrEl.exists()).toBe(true)
    // value 应该是基于 origin/token 的 URL
    const expectedUrl = `${window.location.origin}/r/abc123token`
    expect(qrEl.attributes('data-value')).toBe(expectedUrl)
    // preview-qr 容器也存在
    expect(wrapper.find('.preview-qr').exists()).toBe(true)
    // 提示文字 (不带 TODO)
    const text = wrapper.text()
    expect(text).toContain('也可以让用户扫描下方二维码')
    expect(text).not.toContain('TODO')
  })
})
