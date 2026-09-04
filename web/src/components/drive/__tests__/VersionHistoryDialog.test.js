/**
 * VersionHistoryDialog.test.js — 批次②: 版本对比接入 (diff 按钮 + dialog 接线)
 *
 * 覆盖:
 * 1. versions >= 2 → [data-testid=open-version-diff] 按钮出现
 * 2. 点击按钮 → DesktopVersionDiffDialog 收到 modelValue=true (v-model 接线)
 * 3. versions < 2 → 按钮不出现
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'

vi.mock('@/views/drive/drive-view.css', () => ({}))
vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))
vi.mock('@element-plus/icons-vue', () => ({
  DocumentCopy: { template: '<i />' },
}))

const versions = ref([])
vi.mock('@/composables/useDriveFiles', () => ({
  useDriveFiles: () => ({
    listVersions: async () => versions.value,
    restoreVersion: vi.fn(),
    downloadFileUrl: () => '/api/v1/drive/files/1/download',
  }),
}))

const epStubs = {
  'el-dialog': {
    template: '<div class="el-dialog-stub" v-if="modelValue"><slot /><slot name="footer" /></div>',
    props: ['modelValue', 'title', 'width', 'top'],
  },
  'el-empty': { template: '<div class="el-empty-stub" />' },
  'el-table': {
    template: '<div class="el-table-stub"><slot /></div>',
    props: ['data'],
    // 暴露 rows 让 el-table-column 默认 slot 渲染 (本测试只数按钮, 不需要真实行)
  },
  'el-table-column': { template: '<div class="el-table-col" />' },
  'el-tag': { template: '<span><slot /></span>' },
  'el-button': {
    template: '<button v-bind="$attrs" @click="$emit(\'click\', $event)"><slot /></button>',
    props: ['size', 'link', 'type', 'icon'],
  },
  'el-popconfirm': { template: '<div />' },
  'el-icon': { template: '<i><slot /></i>' },
}

const DiffDialogStub = {
  name: 'DesktopVersionDiffDialog',
  template: '<div class="diff-dialog-stub" :data-open="String(modelValue)" />',
  props: ['modelValue', 'fileId', 'fileName', 'versions'],
}

import VersionHistoryDialog from '../VersionHistoryDialog.vue'

const file = { id: 1, file_name: 'a.pdf', version_number: 3 }

// 组件 watch(visible,file.id) 非 immediate (生产靠打开 dialog 的 visible 翻转触发拉取),
// 测试同样先 false 再 setProps(true) 模拟打开。
const mountDialog = () => mount(VersionHistoryDialog, {
  props: { visible: false, file },
  global: {
    stubs: { ...epStubs, DesktopVersionDiffDialog: DiffDialogStub },
    directives: { loading: {} },
  },
})

async function openDialog(w) {
  await w.setProps({ visible: true })
  await flushPromises()
}

describe('VersionHistoryDialog 版本对比接入 (批次②)', () => {
  beforeEach(() => { versions.value = [] })

  it('versions>=2 → 对比按钮出现, 点击后 diff dialog modelValue=true', async () => {
    versions.value = [
      { id: 10, version_number: 2, file_hash: 'aa', file_size: 10, created_at: '', uploaded_by: 1 },
      { id: 11, version_number: 3, file_hash: 'bb', file_size: 11, created_at: '', uploaded_by: 1, is_current: true },
    ]
    const w = mountDialog()
    await openDialog(w)
    const btn = w.find('[data-testid="open-version-diff"]')
    expect(btn.exists()).toBe(true)
    expect(w.find('.diff-dialog-stub').attributes('data-open')).toBe('false')
    await btn.trigger('click')
    expect(w.find('.diff-dialog-stub').attributes('data-open')).toBe('true')
    // props 接线: file-id + versions 透传
    expect(w.findComponent(DiffDialogStub).props('fileId')).toBe(1)
    expect(w.findComponent(DiffDialogStub).props('versions')).toHaveLength(2)
    w.unmount()
  })

  it('versions<2 → 无对比按钮', async () => {
    versions.value = [
      { id: 11, version_number: 1, file_hash: 'bb', file_size: 11, created_at: '', uploaded_by: 1, is_current: true },
    ]
    const w = mountDialog()
    await openDialog(w)
    expect(w.find('[data-testid="open-version-diff"]').exists()).toBe(false)
    w.unmount()
  })
})
