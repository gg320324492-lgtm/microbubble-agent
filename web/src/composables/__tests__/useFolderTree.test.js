import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

/**
 * v2.15 (2026-07-11) — useFolderTree Pinia store 单元测试
 *
 * 修复目标: 用户测试「删除 folder 不消失」— 根因 = 8 处独立 useFolderTree() 实例,
 *           FolderTree.vue 的 fetchTree 只更新自己的 ref, 父 DesktopDriveView 不联动
 *
 * Pinia setup-store 自动 unwrap ref — store proxy 访问时不需 .value
 * (内部 store 函数仍是 ref, 但 store.$state 暴露时 ref 被 unwrap)
 */

const mockAxiosGet = vi.fn()
const mockAxiosPost = vi.fn()
const mockAxiosPut = vi.fn()
const mockAxiosDelete = vi.fn()

vi.mock('axios', () => ({
  default: {
    get: (...args) => mockAxiosGet(...args),
    post: (...args) => mockAxiosPost(...args),
    put: (...args) => mockAxiosPut(...args),
    delete: (...args) => mockAxiosDelete(...args),
  },
}))

describe('useFolderTreeStore (v2.15 Pinia singleton)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    // Default mock: tree returns 2 folders
    mockAxiosGet.mockResolvedValue({
      data: {
        tree: [
          { id: 1, name: 'folder_a', children: [] },
          { id: 2, name: 'folder_b', children: [] },
        ],
        max_depth: 5,
      },
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('单例 state 共享', () => {
    it('多次调 useFolderTree() 拿到同一份 store state (单例)', async () => {
      const { useFolderTree } = await import('@/composables/useFolderTree')

      const caller_a = useFolderTree()
      const caller_b = useFolderTree()
      const caller_c = useFolderTree()

      // Pinia setup-store proxy unwrap: folderTree 是 array, 不是 ref
      // 但所有 caller 共享**同一份** array (Pinia 内部 ref)
      expect(caller_a.folderTree).toEqual([])  // 初始空
      expect(caller_b.folderTree).toEqual([])
      expect(caller_c.folderTree).toEqual([])

      // 调用 fetchTree (任一 caller 都会更新共享 state)
      await caller_a.fetchTree()
      expect(caller_a.folderTree).toHaveLength(2)
      expect(caller_b.folderTree).toHaveLength(2)  // ✅ 共享, B 也看到了
      expect(caller_c.folderTree).toHaveLength(2)
    })

    it('useFolderTree() factory wrapper 与直接 useFolderTreeStore() 拿到同一 store', async () => {
      const { useFolderTree, useFolderTreeStore } = await import('@/composables/useFolderTree')

      const facade = useFolderTree()
      const direct = useFolderTreeStore()

      // 设置 store 内部状态
      direct.selectedFolderId = 5
      // facade wrapper 通过 useFolderTreeStore() 拿到的是同一 instance
      expect(facade.selectedFolderId).toBe(5)
    })
  })

  describe('deleteFolder 后所有 caller 同步看到', () => {
    it('deleteFolder(id) → SHARED folderTree 自动反映新状态', async () => {
      const { useFolderTree } = await import('@/composables/useFolderTree')

      // 模拟两个 caller: DesktopDriveView (parent) + FolderTree (child sidebar)
      const desktop_caller = useFolderTree()
      const folderTree_caller = useFolderTree()

      // 1. 加载初始 tree (2 folders)
      await desktop_caller.fetchTree()
      expect(desktop_caller.folderTree.map(f => f.id)).toEqual([1, 2])
      expect(folderTree_caller.folderTree.map(f => f.id)).toEqual([1, 2])

      // 2. mock DELETE 成功 + 后续 fetchTree 返回 [folder id=2]
      mockAxiosDelete.mockResolvedValue({ data: null })
      mockAxiosGet.mockResolvedValueOnce({
        data: {
          tree: [{ id: 2, name: 'folder_b', children: [] }],
          max_depth: 5,
        },
      })

      // 3. FolderTree 调用 deleteFolder (它自己的 wrapper, 但底层共享)
      await folderTree_caller.deleteFolder(1)

      // 4. DesktopDriveView 应该立即看到 folder 1 消失 (Pinia 共享)
      expect(desktop_caller.folderTree.map(f => f.id)).toEqual([2])
      expect(folderTree_caller.folderTree.map(f => f.id)).toEqual([2])

      // 5. 验证 axios DELETE 真调过 (v2.16: axios.delete 一律传 config, 即使空也至少 {} 保证 signature 一致)
      expect(mockAxiosDelete).toHaveBeenCalledWith('/api/v1/folders/1', {})
    })

    it('deleteFolder 失败时 throw + state 不变 (其他 caller 不受影响)', async () => {
      const { useFolderTree } = await import('@/composables/useFolderTree')

      const a = useFolderTree()
      const b = useFolderTree()

      await a.fetchTree()
      const before = a.folderTree.length

      // DELETE 失败 (后端返 403)
      mockAxiosDelete.mockRejectedValue({
        response: {
          status: 403,
          data: { error: { code: 'FORBIDDEN', message: '无权删除' } },
        },
      })

      await expect(b.deleteFolder(1)).rejects.toThrow()
      // shared state 不应被破坏
      expect(a.folderTree).toHaveLength(before)
      expect(b.folderTree).toHaveLength(before)
    })

    it('selectedFolderId 在 deleteFolder 后自动清空', async () => {
      const { useFolderTree } = await import('@/composables/useFolderTree')

      const caller = useFolderTree()
      await caller.fetchTree()
      caller.selectFolder(1)
      expect(caller.selectedFolderId).toBe(1)

      mockAxiosDelete.mockResolvedValue({ data: null })
      mockAxiosGet.mockResolvedValueOnce({
        data: { tree: [{ id: 2, name: 'folder_b', children: [] }], max_depth: 5 },
      })

      await caller.deleteFolder(1)
      expect(caller.selectedFolderId).toBe(null)
    })
  })

  describe('computed 反映共享 state', () => {
    it('isEmpty: 任何 caller 改了 folderTree 后所有 computed 自动更新', async () => {
      const { useFolderTree } = await import('@/composables/useFolderTree')

      const a = useFolderTree()
      expect(a.isEmpty).toBe(true)  // 初始 []

      await a.fetchTree()
      expect(a.isEmpty).toBe(false)  // 2 folders
    })

    it('selectedFolder: computed find 反映 shared state', async () => {
      const { useFolderTree } = await import('@/composables/useFolderTree')

      const c = useFolderTree()
      await c.fetchTree()
      c.selectFolder(2)

      expect(c.selectedFolder).toBeDefined()
      expect(c.selectedFolder?.id).toBe(2)
    })

    it('createFolder 同样走 shared fetchTree', async () => {
      const { useFolderTree } = await import('@/composables/useFolderTree')

      const desktop = useFolderTree()
      const dialog = useFolderTree()  // 模拟 CreateFolderDialog

      mockAxiosPost.mockResolvedValueOnce({
        data: { id: 99, name: 'new_folder', parent_id: null },
      })
      mockAxiosGet.mockResolvedValueOnce({
        data: {
          tree: [
            { id: 99, name: 'new_folder', children: [] },
            { id: 1, name: 'folder_a', children: [] },
            { id: 2, name: 'folder_b', children: [] },
          ],
          max_depth: 5,
        },
      })

      await dialog.createFolder({ name: 'new_folder', parentId: null })

      // DesktopDriveView 应立刻看到 99 (Pinia 共享)
      expect(desktop.folderTree.map(f => f.id)).toEqual([99, 1, 2])
    })
  })

  describe('backward compatibility: 8 旧 callsite 一行不改', () => {
    it('useFolderTree() factory wrapper 仍可用 (老 code 风格)', async () => {
      const { useFolderTree } = await import('@/composables/useFolderTree')
      const composable = useFolderTree()
      const {
        folderTree, selectedFolderId, expandedFolderIds,
        loading, loadError,
        isEmpty, selectedFolder,
        fetchTree, createFolder, deleteFolder, restoreFolder,
        renameFolder, updateVisibility, getChildrenStats,
        selectFolder, toggleExpanded,
      } = composable
      // 所有字段都应存在 (type check, 不抛错)
      expect(folderTree).toBeDefined()
      expect(selectedFolderId).toBeDefined()
      expect(expandedFolderIds).toBeDefined()
      expect(typeof loading).toBe('boolean')
      expect(loadError).toBeNull()
      expect(typeof isEmpty).toBe('boolean')
      expect(selectedFolder).toBeNull()
      expect(typeof fetchTree).toBe('function')
      expect(typeof createFolder).toBe('function')
      expect(typeof deleteFolder).toBe('function')
      expect(typeof restoreFolder).toBe('function')
      expect(typeof renameFolder).toBe('function')
      expect(typeof updateVisibility).toBe('function')
      expect(typeof getChildrenStats).toBe('function')
      expect(typeof selectFolder).toBe('function')
      expect(typeof toggleExpanded).toBe('function')
    })
  })
})

describe('getChildrenStats (v2.14 smart confirm helper)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('GET /folders/{id}/children-stats → 返 {folder_count, file_count}', async () => {
    const { useFolderTree } = await import('@/composables/useFolderTree')
    const { getChildrenStats } = useFolderTree()

    mockAxiosGet.mockResolvedValueOnce({
      data: { folder_id: 158, folder_count: 1, file_count: 0 },
    })

    const stats = await getChildrenStats(158)
    expect(stats).toEqual({ folder_id: 158, folder_count: 1, file_count: 0 })
    expect(mockAxiosGet).toHaveBeenCalledWith('/api/v1/folders/158/children-stats')
  })

  it('API 失败兜底 → 返 {folder_count:0, file_count:0}', async () => {
    const { useFolderTree } = await import('@/composables/useFolderTree')
    const { getChildrenStats } = useFolderTree()

    mockAxiosGet.mockRejectedValueOnce(new Error('network error'))

    const stats = await getChildrenStats(999)
    expect(stats).toEqual({ folder_id: 999, folder_count: 0, file_count: 0 })
  })
})


describe('deleteFolder v2.16 (recursive cascade soft-delete)', () => {
  /**
   * 用户决策"有子文件夹的话也可以直接删除" → 前端 smart confirm
   *   检测到 children 时 2 按钮: 取消 / 全部移入回收站 (recursive=true)
   *
   * 实现: useFolderTree.deleteFolder(id, { recursive: true }) →
   *   axios.delete('/api/v1/folders/<id>', { params: { recursive: true } })
   *
   * 关键不变量:
   * - 默认 (无 options 或 recursive=undefined) → 不传 params (与 v2.15 旧行为一致, 服务器走 422 路径)
   * - recursive: true → 传 params={ recursive: true } (后端走级联软删)
   * - recursive: false → 不传 params (与默认一致)
   * - 删除成功后 fetchTree 必触发 + selectedFolderId 在被删的就是选中时清空
   * - 错误透传 wrapApiError 结构不变 (e.response / e.status / e.code 仍在)
   */
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockAxiosGet.mockResolvedValue({ data: { tree: [], max_depth: 5 } })
    mockAxiosDelete.mockResolvedValue({ data: null })
  })

  it('默认调用 (无 options) → 不传 params, 与 v2.15 完全向后兼容', async () => {
    const { useFolderTree } = await import('@/composables/useFolderTree')
    const { deleteFolder } = useFolderTree()

    await deleteFolder(28)

    expect(mockAxiosDelete).toHaveBeenCalledWith(
      '/api/v1/folders/28',
      {},  // 不传 params (保持旧 API 兼容)
    )
    expect(mockAxiosDelete.mock.calls[0][1]).not.toHaveProperty('params')
  })

  it('options.recursive=true → axios DELETE 传 params={recursive: true}', async () => {
    const { useFolderTree } = await import('@/composables/useFolderTree')
    const { deleteFolder } = useFolderTree()

    await deleteFolder(158, { recursive: true })

    expect(mockAxiosDelete).toHaveBeenCalledWith(
      '/api/v1/folders/158',
      { params: { recursive: true } },
    )
  })

  it('options.recursive=false → 显式 false 与默认一致, 不传 params', async () => {
    const { useFolderTree } = await import('@/composables/useFolderTree')
    const { deleteFolder } = useFolderTree()

    await deleteFolder(28, { recursive: false })

    expect(mockAxiosDelete).toHaveBeenCalledWith('/api/v1/folders/28', {})
    expect(mockAxiosDelete.mock.calls[0][1]).not.toHaveProperty('params')
  })

  it('recursive=true 成功后 selectedFolderId 自动清空 (与旧行为一致)', async () => {
    const { useFolderTree } = await import('@/composables/useFolderTree')
    const store = useFolderTree()

    await store.fetchTree()
    store.selectFolder(158)
    expect(store.selectedFolderId).toBe(158)

    await store.deleteFolder(158, { recursive: true })

    expect(store.selectedFolderId).toBe(null)
  })

  it('recursive 失败时 throw wrapApiError (保留 status / code / response)', async () => {
    const { useFolderTree } = await import('@/composables/useFolderTree')
    const { deleteFolder } = useFolderTree()

    mockAxiosDelete.mockRejectedValueOnce({
      response: {
        status: 422,
        data: {
          error: {
            code: 'VALIDATION_ERROR',
            message: 'folder 下还有 1 个未删的子 folder, 请先清理',
            details: {},
          },
        },
      },
    })

    await expect(deleteFolder(158, { recursive: true })).rejects.toMatchObject({
      status: 422,
      code: 'VALIDATION_ERROR',
      message: expect.stringContaining('folder 下还有'),
      response: expect.objectContaining({ status: 422 }),
    })
  })

  it('recursive=true + 0 子项 → 也允许 (后端兜底无级联)', async () => {
    // 用户可能从回收站还原后立即删除, 不一定有 children
    // 后端不报错, 前端也不应限制 options 传值
    const { useFolderTree } = await import('@/composables/useFolderTree')
    const { deleteFolder } = useFolderTree()

    // mock 返 dict (recursive 后端返 200 + dict 而非 204)
    mockAxiosDelete.mockResolvedValueOnce({
      data: { deleted_folders: 1, deleted_files: 0, deleted_folder_ids: [158] },
    })

    await expect(deleteFolder(158, { recursive: true })).resolves.toBeUndefined()
    expect(mockAxiosDelete).toHaveBeenCalledWith(
      '/api/v1/folders/158',
      { params: { recursive: true } },
    )
  })
})
