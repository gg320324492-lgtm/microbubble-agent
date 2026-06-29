/**
 * TemplatesView Vitest 单元测试 (v77 P2.6-G.2)
 *
 * el-table / el-pagination 等 EP 组件在 jsdom 中 slot 渲染会触发 row.name 访问,
 * 测试通过 global.stubs 阻止 EP 内部 slot 渲染, 只测 setup() 暴露的函数.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import TemplatesView from '../TemplatesView.vue'

vi.mock('axios', () => ({
  default: {
    get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn(),
  },
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
    ElMessageBox: { confirm: vi.fn().mockResolvedValue('confirm') },
  }
})

vi.mock('@element-plus/icons-vue', () => ({
  Edit: { template: '<span />' },
  Check: { template: '<span />' },
  Close: { template: '<span />' },
  Delete: { template: '<span />' },
}))

const EP_STUBS = {
  'el-table': true, 'el-table-column': true, 'el-pagination': true,
  'el-card': true, 'el-form': true, 'el-form-item': true,
  'el-input': true, 'el-select': true, 'el-option': true,
  'el-button': true, 'el-tag': true, 'el-switch': true,
  'el-icon': true, 'el-popconfirm': true,
}

const mockTemplates = [
  { id: 1, name: '组会', is_builtin: true, is_active: true, agenda: ['议题1', '议题2'] },
  { id: 2, name: '一对一', is_builtin: true, is_active: true, agenda: [] },
  { id: 3, name: '我的组会', is_builtin: false, is_active: true, agenda: ['议题A'] },
]

function mountView() {
  return mount(TemplatesView, { global: { stubs: EP_STUBS } })
}

describe('TemplatesView (v77 P2.6-G.2)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    axios.get.mockResolvedValue({ data: { items: mockTemplates, total: 3, page: 1, page_size: 20 } })
  })

  afterEach(() => vi.restoreAllMocks())

  it('组件正确挂载', () => {
    const wrapper = mountView()
    expect(wrapper.exists()).toBe(true)
  })

  it('默认 filters 正确 (search=\"\", type=null, status=null, page=1, page_size=20)', () => {
    const wrapper = mountView()
    expect(wrapper.vm.filters).toEqual({
      search: '', type: null, status: null, page: 1, page_size: 20,
    })
  })

  it('setup 暴露 17 个 handler 函数', () => {
    const wrapper = mountView()
    const fns = [
      'fetchTemplates', 'handleSearch', 'handleReset', 'handlePageChange',
      'handleSizeChange', 'handleSelectionChange', 'toggleEditMode',
      'handleBatchEnable', 'handleBatchDisable', 'batchToggleActive',
      'handleBatchDelete', 'handleToggleSingle', 'handleDeleteSingle',
      'handleClone', 'handleEdit', 'formatTime', 'selectable',
    ]
    fns.forEach((fn) => {
      expect(typeof wrapper.vm[fn], `${fn} 应是函数`).toBe('function')
    })
  })

  it('onMounted 触发 fetchTemplates 调 GET /meeting-templates 携带 include_inactive=true', async () => {
    mountView()
    await new Promise((r) => setTimeout(r, 10))
    expect(axios.get).toHaveBeenCalledWith(
      '/api/v1/meeting-templates',
      expect.objectContaining({ params: expect.objectContaining({ include_inactive: true }) }),
    )
  })

  it('selectable 拒绝 builtin 允许 custom', () => {
    const wrapper = mountView()
    expect(wrapper.vm.selectable({ is_builtin: true, id: 1 })).toBe(false)
    expect(wrapper.vm.selectable({ is_builtin: false, id: 2 })).toBe(true)
  })

  it('handleSearch 重置 page=1', async () => {
    const wrapper = mountView()
    wrapper.vm.filters.page = 5
    await wrapper.vm.handleSearch()
    expect(wrapper.vm.filters.page).toBe(1)
  })

  it('handleReset 清空所有 filter', async () => {
    const wrapper = mountView()
    wrapper.vm.filters.search = 'foo'
    wrapper.vm.filters.type = 'builtin'
    wrapper.vm.filters.status = 'active'
    wrapper.vm.filters.page = 3
    await wrapper.vm.handleReset()
    expect(wrapper.vm.filters.search).toBe('')
    expect(wrapper.vm.filters.type).toBe(null)
    expect(wrapper.vm.filters.status).toBe(null)
    expect(wrapper.vm.filters.page).toBe(1)
  })

  it('handleBatchEnable 调 POST /batch-toggle-active 携带 {ids, is_active: true}', async () => {
    const wrapper = mountView()
    axios.post.mockResolvedValue({ data: { updated: 2, is_active: true } })
    wrapper.vm.selectedRows = [{ id: 3 }, { id: 4 }]
    await wrapper.vm.handleBatchEnable()
    expect(axios.post).toHaveBeenCalledWith(
      '/api/v1/meeting-templates/batch-toggle-active',
      { ids: [3, 4], is_active: true },
    )
  })

  it('handleBatchDisable 调 POST /batch-toggle-active 携带 {ids, is_active: false}', async () => {
    const wrapper = mountView()
    axios.post.mockResolvedValue({ data: { updated: 2, is_active: false } })
    wrapper.vm.selectedRows = [{ id: 3 }, { id: 4 }]
    await wrapper.vm.handleBatchDisable()
    expect(axios.post).toHaveBeenCalledWith(
      '/api/v1/meeting-templates/batch-toggle-active',
      { ids: [3, 4], is_active: false },
    )
  })

  it('handleBatchDelete 调 POST /batch-delete + skipped_builtin 提示', async () => {
    const wrapper = mountView()
    ElMessageBox.confirm.mockResolvedValue('confirm')
    axios.post.mockResolvedValue({ data: { deleted: 1, skipped_builtin: [1] } })
    wrapper.vm.selectedRows = [{ id: 3 }, { id: 1 }]
    await wrapper.vm.handleBatchDelete()
    expect(ElMessageBox.confirm).toHaveBeenCalledWith(
      expect.stringContaining('批量删除'),
      '批量删除确认',
      expect.objectContaining({ type: 'warning' }),
    )
    expect(axios.post).toHaveBeenCalledWith(
      '/api/v1/meeting-templates/batch-delete',
      { ids: [3, 1] },
    )
    expect(ElMessage.success).toHaveBeenCalledWith(
      expect.stringContaining('已删除 1 个模板, 1 个内置模板已跳过'),
    )
  })

  it('handleBatchDelete 用户取消时不调 API', async () => {
    const wrapper = mountView()
    ElMessageBox.confirm.mockRejectedValue('cancel')
    wrapper.vm.selectedRows = [{ id: 3 }]
    await wrapper.vm.handleBatchDelete()
    expect(axios.post).not.toHaveBeenCalled()
  })

  it('handleToggleSingle 调 PUT 携带 is_active', async () => {
    const wrapper = mountView()
    axios.put.mockResolvedValue({ data: { id: 3, is_active: false } })
    await wrapper.vm.handleToggleSingle({ id: 3 }, false)
    expect(axios.put).toHaveBeenCalledWith(
      '/api/v1/meeting-templates/3',
      { is_active: false },
    )
  })

  it('handleDeleteSingle 调 DELETE', async () => {
    const wrapper = mountView()
    axios.delete.mockResolvedValue({ data: { status: 'deleted' } })
    await wrapper.vm.handleDeleteSingle({ id: 3 })
    expect(axios.delete).toHaveBeenCalledWith('/api/v1/meeting-templates/3')
  })

  it('handleClone 调 POST /clone', async () => {
    const wrapper = mountView()
    axios.post.mockResolvedValue({ data: { id: 99 } })
    await wrapper.vm.handleClone({ id: 1 })
    expect(axios.post).toHaveBeenCalledWith('/api/v1/meeting-templates/1/clone')
  })

  it('formatTime null 返 — 正常时间含年份', () => {
    const wrapper = mountView()
    expect(wrapper.vm.formatTime(null)).toBe('—')
    const result = wrapper.vm.formatTime('2026-06-30T12:00:00')
    expect(result).toContain('2026')
  })

  it('fetchTemplates 失败时 ElMessage.error', async () => {
    const wrapper = mountView()
    axios.get.mockRejectedValue(new Error('网络错误'))
    await wrapper.vm.fetchTemplates()
    expect(ElMessage.error).toHaveBeenCalled()
  })

  it('toggleEditMode 切 editMode 状态 + 清 selectedRows + tableRef.clearSelection', async () => {
    const wrapper = mountView()
    wrapper.vm.editMode = true
    wrapper.vm.selectedRows = [{ id: 1 }]
    const mockClear = vi.fn()
    wrapper.vm.tableRef = { clearSelection: mockClear }
    await wrapper.vm.toggleEditMode()
    expect(wrapper.vm.editMode).toBe(false)
    expect(wrapper.vm.selectedRows).toEqual([])
    expect(mockClear).toHaveBeenCalled()
  })
})
