// useFolderTree.js — 课题组网盘 PR3.2 文件夹树 composable
// 2026-07-01

import { ref, computed } from 'vue'
import axios from 'axios'

/**
 * 提取后端错误消息，支持两种响应格式：
 *   - AppException 统一格式: {error: {code, message, details}} (项目标准)
 *   - FastAPI 默认格式: {detail: "..."} (兜底, 用于未迁移的旧 endpoint)
 *
 * 2026-07-10 加固: 之前只找 .error.message, FastAPI 默认 {detail: "folder 28 不存在"}
 * 找不到 → 落兜底字符串 "删除文件夹失败" → 用户截图 [FolderContextMenu] delete folder
 * 28 failed: undefined 删除文件夹失败。后端已统一改用 NotFoundException /
 * ForbiddenException / ValidationException (AppException 子类), 前端兜底也兼容旧格式。
 *
 * 2026-07-10 v2 加固: `wrapApiError` 保留 e.response 给 caller (FolderTree.vue 等) 读 status/code
 *   之前 `throw new Error(msg)` 丢失 e.response → caller `e.response?.status` 永远 undefined
 *   → console.error "[FolderContextMenu] delete folder 158 failed: undefined Folder不存在"
 *   现在 wrapApiError 把 status/code/response 都附到 Error 上, caller 一行不改
 */
function extractErrorMessage(e, fallback) {
  const data = e.response?.data
  return data?.error?.message || data?.detail || e.message || fallback
}

function wrapApiError(e, fallback) {
  const err = new Error(extractErrorMessage(e, fallback))
  // 保留原始 axios 响应信息，让 caller (FolderTree.vue) 可以读 status / code
  err.response = e.response
  err.status = e.response?.status
  err.code = e.response?.data?.error?.code || null
  err.details = e.response?.data?.error?.details || null
  return err
}

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
      loadError.value = extractErrorMessage(e, '文件夹树加载失败')
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
      throw wrapApiError(e, '创建文件夹失败')
    }
  }

  const deleteFolder = async (id) => {
    try {
      await axios.delete(`/api/v1/folders/${id}`)
      await fetchTree()  // 重建树
      if (selectedFolderId.value === id) selectedFolderId.value = null
    } catch (e) {
      throw wrapApiError(e, '删除文件夹失败')
    }
  }

  const restoreFolder = async (id) => {
    try {
      await axios.post(`/api/v1/folders/${id}/restore`)
      await fetchTree()
    } catch (e) {
      throw wrapApiError(e, '恢复文件夹失败')
    }
  }

  const renameFolder = async (id, newName) => {
    try {
      await axios.put(`/api/v1/folders/${id}`, { name: newName })
      await fetchTree()
    } catch (e) {
      throw wrapApiError(e, '重命名失败')
    }
  }

  const updateVisibility = async (id, visibility) => {
    try {
      await axios.put(`/api/v1/folders/${id}`, { visibility })
      await fetchTree()
    } catch (e) {
      throw wrapApiError(e, '修改可见性失败')
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