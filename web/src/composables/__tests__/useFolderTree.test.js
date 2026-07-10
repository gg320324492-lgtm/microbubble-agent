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

      // 5. 验证 axios DELETE 真调过
      expect(mockAxiosDelete).toHaveBeenCalledWith('/api/v1/folders/1')
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
