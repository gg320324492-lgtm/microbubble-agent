/**
 * DriveTrashPanel.toggle-select.test.js — 2026-09-13 回归
 *
 * 缺陷: FileGrid 行复选框 emit 的 toggle-select 事件在回收站两个宿主
 * (DriveTrashPanel / DriveTrashView) 都没接线 → 单独勾选任何行均无响应
 * (用户报告「这个文件不能单独选中」; 全选走 selectAll 不受影响, 更具迷惑性)。
 *
 * 断言: FileGrid 抛 toggle-select(id) 时, 面板调用 composable 的 toggleSelect(id)。
 */
import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'

const toggleSelect = vi.fn()
const fetchTrash = vi.fn(async () => {})
const selectedFileIds = ref([])

vi.mock('@/composables/useDriveFiles', () => ({
  useDriveFiles: () => ({
    driveFiles: ref([]),
    total: ref(0),
    currentPage: ref(1),
    pageSize: ref(50),
    loading: ref(false),
    loadError: ref(null),
    selectedFileIds,
    fetchTrash,
    batchRestore: vi.fn(),
    permanentDeleteBatch: vi.fn(),
    toggleSelect,
    clearSelection: vi.fn(),
    selectAll: vi.fn(),
  }),
}))

vi.mock('@/components/drive/FileGrid.vue', () => ({
  default: {
    name: 'FileGrid',
    props: ['files', 'total', 'currentPage', 'pageSize', 'selectedFileIds', 'loading', 'loadError', 'viewMode', 'isTopLevel', 'trashContext'],
    emits: ['toggle-select', 'retry', 'file-click', 'file-restore', 'file-delete', 'page-change'],
    template: '<div class="filegrid-stub" />',
  },
}))

vi.mock('@/components/drive/BatchActionToolbar.vue', () => ({
  default: {
    name: 'BatchActionToolbar',
    props: ['selectedCount', 'totalCount', 'context'],
    emits: ['select-all', 'clear', 'batch-restore', 'batch-permanent-delete'],
    template: '<div class="toolbar-stub" />',
  },
}))

vi.mock('element-plus', () => ({
  ElMessage: { info: vi.fn(), success: vi.fn(), error: vi.fn(), warning: vi.fn() },
  ElMessageBox: { confirm: vi.fn() },
}))

import DriveTrashPanel from '@/components/drive/DriveTrashPanel.vue'
import FileGrid from '@/components/drive/FileGrid.vue'

describe('DriveTrashPanel 行复选框接线 (2026-09-13)', () => {
  it('FileGrid emit toggle-select(id) → 调用 toggleSelect(id)', async () => {
    const wrapper = mount(DriveTrashPanel)
    await flushPromises()

    expect(fetchTrash).toHaveBeenCalled()
    const grid = wrapper.findComponent(FileGrid)
    expect(grid.exists()).toBe(true)

    grid.vm.$emit('toggle-select', 5)
    expect(toggleSelect).toHaveBeenCalledWith(5)
  })
})
