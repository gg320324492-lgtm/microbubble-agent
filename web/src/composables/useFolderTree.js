// useFolderTree.js — 课题组网盘 PR3.2 文件夹树 composable
// 2026-07-01
// 2026-07-11 v2.15: 改 Pinia store (defineStore) 替代 factory 模式, 让所有 caller 共享单例 state
//   修复: 用户测试「删除 folder 不消失」— 根因 = 8 处独立 useFolderTree() 实例, FolderTree.vue
//         的 fetchTree 只更新自己的 ref, 父 DesktopDriveView 的 folderTree prop 不联动
//   同步受益: CreateFolderDialog / DriveUploadDialog / MoveDialog / KnowledgeUploadDialog /
//             MobileDriveView / MobileFileList 等同问题的所有场景
//   兼容: useFolderTree() factory 函数保留, 内部转调 useFolderTreeStore() — 零 callsite 改动

import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
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

/**
 * Folder Tree Pinia store (v2.15 单例)
 *
 * 为什么 Pinia:
 * - 8 个组件调 useFolderTree() 都需要共享同一份 tree / selectedFolderId / expandedFolderIds
 * - factory 模式 (旧实现) 每调用一次 = 一份独立 ref, 互不联动
 * - Pinia store 是 app-level 单例, 所有 component 共享同一份 reactive state
 *
 * 数据流:
 * 1. fetchTree() -> GET /api/v1/folders/tree -> folderTree.value (全局共享)
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
export const useFolderTreeStore = defineStore('folderTree', () => {
  // === 状态 (单例, 全 app 共享) ===
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
      await fetchTree()  // 重建树 (单例 store 自动同步到所有 caller)
      return resp.data
    } catch (e) {
      throw wrapApiError(e, '创建文件夹失败')
    }
  }

  /**
   * v2.14 (2026-07-10): 查 folder 下未删子 folder + 文件数 (前置 confirm 弹窗用)
   * Returns: { folder_id, folder_count, file_count }
   * 错误 fallback: 返 { folder_count: 0, file_count: 0 } 让 confirm 走默认文案
   */
  const getChildrenStats = async (id) => {
    try {
      const resp = await axios.get(`/api/v1/folders/${id}/children-stats`)
      return resp.data
    } catch (e) {
      // 兜底: 查询失败 → 返零计数让 confirm 走默认文案
      return { folder_id: id, folder_count: 0, file_count: 0 }
    }
  }

  const deleteFolder = async (id) => {
    try {
      await axios.delete(`/api/v1/folders/${id}`)
      await fetchTree()  // 重建树 (单例 store 自动同步)
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
    getChildrenStats,
    selectFolder,
    toggleExpanded
  }
})

/**
 * 兼容层: 8 处 callsite 调 `useFolderTree()` 不需改 import, 内部转 Pinia store
 * v2.15 之前所有调用方: `const { ... } = useFolderTree()`
 * 之后调用方式完全不变, 内部拿的是同一份单例 state
 *
 * 注意: 当 store 还没在 setup() 中被激活时, useFolderTreeStore() 可能要 Pinia 上下文
 * Vue 3 + Pinia 2 setup-store: 必须在 setup() 顶层第一次调 useFolderTreeStore() →
 * 之后任一 caller 都拿到同一份 store. 这个兼容 wrapper 让 caller 不必知道 Pinia 存在.
 */
export function useFolderTree() {
  return useFolderTreeStore()
}
