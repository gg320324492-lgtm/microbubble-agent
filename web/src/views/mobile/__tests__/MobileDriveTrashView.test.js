/**
 * MobileDriveTrashView.test.js — 批次② F1 mount-smoke
 *
 * 覆盖:
 * 1. mount 不炸 + 文件/文件夹 trash 各渲染一行 (mock useDriveFiles + axios)
 * 2. 恢复文件 → batchRestore([id]) 一次
 * 3. 空态渲染
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'

vi.mock('@/views/drive/drive-view.css', () => ({}))
vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))

const mockAxiosGet = vi.fn()
const mockAxiosPost = vi.fn()
vi.mock('axios', () => ({
  default: { get: (...a) => mockAxiosGet(...a), post: (...a) => mockAxiosPost(...a) },
}))

const driveFiles = ref([])
const total = ref(0)
const loading = ref(false)
const loadError = ref(null)
const fetchTrash = vi.fn(async () => {})
const batchRestore = vi.fn(async () => ({ succeeded_count: 1 }))
const permanentDeleteBatch = vi.fn(async () => ({ succeeded_count: 1 }))
vi.mock('@/composables/useDriveFiles', () => ({
  useDriveFiles: () => ({
    driveFiles, total, loading, loadError,
    fetchTrash, batchRestore, permanentDeleteBatch,
  }),
}))

const PageHeaderStub = {
  template: '<div class="page-header-stub"><slot /><slot name="right" /></div>',
  props: ['title', 'showBack'],
}

import MobileDriveTrashView from '../MobileDriveTrashView.vue'

const mountView = () => mount(MobileDriveTrashView, {
  global: {
    stubs: { PageHeader: PageHeaderStub, RouterLink: true },
    mocks: { $router: { back: vi.fn(), push: vi.fn() } },
  },
})

describe('MobileDriveTrashView (F1 mount-smoke)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    driveFiles.value = []
    total.value = 0
    loadError.value = null
    mockAxiosGet.mockResolvedValue({ data: { items: [{ id: 9, name: '旧组会归档', deleted_at: '2026-09-01T10:00:00' }] } })
  })

  it('渲染文件 + 文件夹 trash 行, folder trash 拉 /folders/trash/list', async () => {
    driveFiles.value = [{ id: 1, file_name: 'a.pdf', file_size: 1024 }]
    total.value = 1
    const w = mountView()
    await flushPromises()
    expect(w.text()).toContain('a.pdf')
    expect(w.text()).toContain('旧组会归档')
    expect(mockAxiosGet).toHaveBeenCalledWith('/api/v1/drive/folders/trash/list', expect.anything())
    expect(fetchTrash).toHaveBeenCalledTimes(1)
    w.unmount()
  })

  it('恢复文件 → batchRestore([id]) 一次 + 刷新', async () => {
    driveFiles.value = [{ id: 1, file_name: 'a.pdf', file_size: 10 }]
    total.value = 1
    const w = mountView()
    await flushPromises()
    await w.find('button.restore').trigger('click')
    await flushPromises()
    expect(batchRestore).toHaveBeenCalledTimes(1)
    expect(batchRestore).toHaveBeenCalledWith([1])
    w.unmount()
  })

  it('恢复文件夹 → POST /folders/{id}/restore', async () => {
    const w = mountView()
    await flushPromises()
    const btns = w.findAll('button.restore')
    const folderBtn = btns[btns.length - 1]
    await folderBtn.trigger('click')
    await flushPromises()
    expect(mockAxiosPost).toHaveBeenCalledWith('/api/v1/drive/folders/9/restore')
    w.unmount()
  })

  it('空回收站 → 空态文案', async () => {
    mockAxiosGet.mockResolvedValue({ data: { items: [] } })
    const w = mountView()
    await flushPromises()
    expect(w.text()).toContain('回收站是空的')
    w.unmount()
  })
})
