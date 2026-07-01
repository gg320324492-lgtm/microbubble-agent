// useFolderTree.js — 课题组网盘 PR3.2 文件夹树 composable
// 2026-07-01

import { ref, computed } from 'vue'
import axios from 'axios'

/**
 * 文件夹树状态管理
 *
 * 数据流:
 * 1. fetchTree() -> GET /api/v1/folders/tree -> folderTree.value
 * 2. 用户选中文件夹 -> selectedFolderId.value = id (null = 顶级)
 * 3. FileGrid 监听 selectedFolderId 重新拉取文件列表
 *
 * 错误处理:
 * - loadError 区分"加载失败"和"真无文件夹"两种空态
 * - 静默重试: retry() 重新调 fetchTree
 *
 * 写操作:
 * - createFolder(): POST /api/v1/folders
 * - deleteFolder(id): DELETE /api/v1/folders/{id} (软删)
 * - restoreFolder(id): POST /api/v1/folders/{id}/restore
 */
export function useFolderTree() {
  // 状态
  const folderTree = ref([])  // 后端返回的树形结构
  const selectedFolderId = ref(null)
  const expandedFolderIds = ref(new Set())  // 展开状态
  const loading = ref(false)
  const loadError = ref(null)

  // === 计算属性 ===
  const isEmpty = computed(() => !loading.value && !loadError.value && folderTree.value.length === 0)
  const selectedFolder = computed(() => {
    if (selectedFolderId.value === null) return null
    return findFolder(folderTree.value, selectedFolderId.value)
  })

  // === API 调用 ===
  const fetchTree = async () => {
    loading.value = true
    loadError.value = null
    try {
      const resp = await axios.get('/api/v1/folders/tree')
      folderTree.value = resp.data.tree || []
    } catch (e) {
      loadError.value = e.response?.data?.error?.message || e.message || '文件夹树加载失败'
      folderTree.value = []
    } finally {
      loading.value = false
    }
  }

  const createFolder = async ({ name, parentId = null, visibility = 'team' }) => {
    try {
      const resp = await axios.post('/api/v1/folders', {
        name,
        parent_id: parentId,
        visibility
      })
      await fetchTree()  // 重建树
      return resp.data
    } catch (e) {
      throw new Error(e.response?.data?.error?.message || '创建文件夹失败')
    }
  }

  const deleteFolder = async (id) => {
    try {
      await axios.delete(`/api/v1/folders/${id}`)
      await fetchTree()  // 重建树
      if (selectedFolderId.value === id) selectedFolderId.value = null
    } catch (e) {
      throw new Error(e.response?.data?.error?.message || '删除文件夹失败')
    }
  }

  const restoreFolder = async (id) => {
    try {
      await axios.post(`/api/v1/folders/${id}/restore`)
      await fetchTree()
    } catch (e) {
      throw new Error(e.response?.data?.error?.message || '恢复文件夹失败')
    }
  }

  const renameFolder = async (id, newName) => {
    try {
      await axios.put(`/api/v1/folders/${id}`, { name: newName })
      await fetchTree()
    } catch (e) {
      throw new Error(e.response?.data?.error?.message || '重命名失败')
    }
  }

  const updateVisibility = async (id, visibility) => {
    try {
      await axios.put(`/api/v1/folders/${id}`, { visibility })
      await fetchTree()
    } catch (e) {
      throw new Error(e.response?.data?.error?.message || '修改可见性失败')
    }
  }

  // === 内部辅助 ===
  function findFolder(nodes, targetId) {
    for (const node of nodes) {
      if (node.id === targetId) return node
      if (node.children?.length) {
        const found = findFolder(node.children, targetId)
        if (found) return found
      }
    }
    return null
  }

  function toggleExpanded(folderId) {
    if (expandedFolderIds.value.has(folderId)) {
      expandedFolderIds.value.delete(folderId)
    } else {
      expandedFolderIds.value.add(folderId)
    }
    // 触发响应式更新 (Set 需 replace 触发)
    expandedFolderIds.value = new Set(expandedFolderIds.value)
  }

  function selectFolder(id) {
    selectedFolderId.value = id
  }

  return {
    // 状态
    folderTree,
    selectedFolderId,
    expandedFolderIds,
    loading,
    loadError,
    // 计算
    isEmpty,
    selectedFolder,
    // 方法
    fetchTree,
    createFolder,
    deleteFolder,
    restoreFolder,
    renameFolder,
    updateVisibility,
    selectFolder,
    toggleExpanded
  }
}