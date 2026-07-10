// useDriveFiles.js — 课题组网盘 PR3.3 drive 文件列表 composable
// 2026-07-01 (v2 PR2 加 sort/filter/star/batch)

import { ref, computed, watch } from 'vue'
import axios from 'axios'

/**
 * drive 文件列表状态管理
 *
 * 数据流:
 * 1. fetchFiles() -> GET /api/v1/drive/files -> driveFiles.value
 * 2. 监听 folderId / visibility 变化自动重新拉取
 * 3. 删除/重命名后局部刷新
 *
 * 隐私边界 (v31.2.x + PR2.10):
 * - 后端硬过滤: private 文件仅 owner 可见
 * - 前端不传 user_id, 由后端 JWT 推断
 *
 * v2 PR2 新增:
 * - sort_by / sort_order / starred_only / file_type state + 透传 fetchFiles
 * - toggleStar / listStarred / listTrash / batchSoftDelete / batchRestore / batchMove / batchUpdateVisibility / permanentDeleteBatch
 *
 * 错误处理:
 * - loadError 区分"加载失败"和"真无文件"两种空态
 */
export function useDriveFiles() {
  // 状态
  const driveFiles = ref([])
  const total = ref(0)
  const currentPage = ref(1)
  const pageSize = ref(20)
  const loading = ref(false)
  const loadError = ref(null)
  const selectedFileIds = ref([])  // 多选

  // v2 PR2: sort + filter state (用户切换后调 fetchFiles 会自动带上)
  const sortBy = ref('created_at')      // created_at | updated_at | file_name | starred_at
  const sortOrder = ref('desc')         // asc | desc
  const starredOnly = ref(false)        // 仅收藏
  const fileType = ref(null)            // pdf | image | video | office | text | null
  // v2 PR6-P19: 视图隔离 (personal | team | all) - personal 不显示 is_team_shared=true 文件
  // DesktopDriveView 切到 team 视图时调 setViewMode('team') 改这里
  const viewMode = ref('personal')       // v2 PR6-P19: personal (默认) | team | all

  // === 计算属性 ===
  const isEmpty = computed(() =>
    !loading.value && !loadError.value && driveFiles.value.length === 0
  )
  const hasSelection = computed(() => selectedFileIds.value.length > 0)

  // === API 调用 ===
  const fetchFiles = async (params = {}) => {
    loading.value = true
    loadError.value = null
    try {
      const queryParams = {
        page: currentPage.value,
        page_size: pageSize.value,
        sort_by: sortBy.value,
        sort_order: sortOrder.value,
        starred_only: starredOnly.value ? 'true' : 'false',
        // v2 PR6-P19: 默认 view=personal (个人网盘, 不显示 is_team_shared=true)
        // DesktopDriveView team 分支调 fetchFiles 时传 view='team' 覆盖
        view: viewMode.value,
        ...(fileType.value ? { file_type: fileType.value } : {}),
        ...params
      }
      // 删 None / 空字符串 params (避免污染 URL)
      Object.keys(queryParams).forEach(k => {
        if (queryParams[k] === null || queryParams[k] === '' || queryParams[k] === undefined) {
          delete queryParams[k]
        }
      })
      const resp = await axios.get('/api/v1/drive/files', { params: queryParams })
      driveFiles.value = resp.data.items || []
      total.value = resp.data.total || 0
      // 切换 folder 时清掉多选状态
      selectedFileIds.value = []
    } catch (e) {
      loadError.value = e.response?.data?.error?.message || e.message || '文件列表加载失败'
      driveFiles.value = []
      total.value = 0
    } finally {
      loading.value = false
    }
  }

  const deleteFile = async (id) => {
    try {
      await axios.delete(`/api/v1/drive/files/${id}`)
      // 局部刷新: 从 driveFiles 移除 + total -1
      driveFiles.value = driveFiles.value.filter(f => f.id !== id)
      total.value = Math.max(0, total.value - 1)
      selectedFileIds.value = selectedFileIds.value.filter(sid => sid !== id)
    } catch (e) {
      throw new Error(e.response?.data?.error?.message || '删除文件失败')
    }
  }

  const renameFile = async (id, newName) => {
    try {
      await axios.put(`/api/v1/drive/files/${id}`, { title: newName })
      const target = driveFiles.value.find(f => f.id === id)
      if (target) target.title = newName
    } catch (e) {
      throw new Error(e.response?.data?.error?.message || '重命名失败')
    }
  }

  const moveFile = async (id, targetFolderId) => {
    try {
      await axios.put(`/api/v1/drive/files/${id}`, { folder_id: targetFolderId })
      await fetchFiles()  // 重建列表
    } catch (e) {
      throw new Error(e.response?.data?.error?.message || '移动文件失败')
    }
  }

  const updateVisibility = async (id, visibility) => {
    try {
      // v2 PR1: 改用专用 PUT /visibility 端点 (带 folder 上限校验)
      const resp = await axios.put(`/api/v1/drive/files/${id}/visibility`, { visibility })
      const target = driveFiles.value.find(f => f.id === id)
      if (target) target.visibility = resp.data.visibility
    } catch (e) {
      throw new Error(e.response?.data?.error?.message || '修改可见性失败')
    }
  }

  const extractToKb = async (id, targetVisibility = 'team') => {
    try {
      await axios.post(`/api/v1/drive/files/${id}/extract-to-kb`, { target_visibility: targetVisibility })
      const target = driveFiles.value.find(f => f.id === id)
      if (target) {
        target.storage_mode = 'kb'
        target.visibility = targetVisibility
      }
    } catch (e) {
      throw new Error(e.response?.data?.error?.message || '加入公共知识库失败')
    }
  }

  const createShareLink = async (id, { expiresHours = 168, password = null } = {}) => {
    try {
      const payload = { expires_hours: expiresHours }
      if (password) payload.password = String(password)
      const resp = await axios.post(`/api/v1/drive/files/${id}/share-link`, payload)
      return {
        token: resp.data.token,
        shareUrl: resp.data.share_url,
        expiresAt: resp.data.expires_at,
        passwordRequired: resp.data.password_required
      }
    } catch (e) {
      throw new Error(e.response?.data?.error?.message || '生成分享链接失败')
    }
  }

  const revokeShareLink = async (id) => {
    try {
      await axios.delete(`/api/v1/drive/files/${id}/share-link`)
      // 局部更新: 清空目标文件 share 状态 (但列表不直接显示 share_token, 这里仅刷新)
      await fetchFiles()
    } catch (e) {
      throw new Error(e.response?.data?.error?.message || '撤销分享链接失败')
    }
  }

  // ============================================================
  // v2 PR2: 收藏 + 回收站 + 批量操作
  // ============================================================

  const toggleStar = async (id) => {
    try {
      const resp = await axios.post(`/api/v1/drive/files/${id}/toggle-star`)
      // 局部刷新: 更新目标文件的 is_starred + starred_at
      const target = driveFiles.value.find(f => f.id === id)
      if (target) {
        target.is_starred = resp.data.is_starred
        target.starred_at = resp.data.starred_at
      }
      // starredOnly 模式下如果取消收藏要从列表移除
      if (starredOnly.value && !resp.data.is_starred) {
        driveFiles.value = driveFiles.value.filter(f => f.id !== id)
        total.value = Math.max(0, total.value - 1)
      }
      return resp.data
    } catch (e) {
      throw new Error(e.response?.data?.detail || '切换收藏失败')
    }
  }

  const fetchStarred = async (params = {}) => {
    loading.value = true
    loadError.value = null
    try {
      const queryParams = {
        page: currentPage.value,
        page_size: pageSize.value,
        sort_by: sortBy.value,
        sort_order: sortOrder.value,
        ...params
      }
      Object.keys(queryParams).forEach(k => {
        if (queryParams[k] === null || queryParams[k] === '' || queryParams[k] === undefined) {
          delete queryParams[k]
        }
      })
      const resp = await axios.get('/api/v1/drive/starred', { params: queryParams })
      driveFiles.value = resp.data.items || []
      total.value = resp.data.total || 0
      selectedFileIds.value = []
    } catch (e) {
      loadError.value = e.response?.data?.detail || '收藏列表加载失败'
      driveFiles.value = []
      total.value = 0
    } finally {
      loading.value = false
    }
  }

  const fetchTrash = async (params = {}) => {
    loading.value = true
    loadError.value = null
    try {
      const queryParams = {
        page: currentPage.value,
        page_size: pageSize.value,
        ...params
      }
      const resp = await axios.get('/api/v1/drive/trash', { params: queryParams })
      driveFiles.value = resp.data.items || []
      total.value = resp.data.total || 0
      selectedFileIds.value = []
    } catch (e) {
      loadError.value = e.response?.data?.detail || '回收站加载失败'
      driveFiles.value = []
      total.value = 0
    } finally {
      loading.value = false
    }
  }

  const batchSoftDelete = async (fileIds) => {
    try {
      const resp = await axios.post('/api/v1/drive/files/batch-soft-delete', { file_ids: fileIds })
      // 局部刷新: 从列表移除
      driveFiles.value = driveFiles.value.filter(f => !fileIds.includes(f.id))
      total.value = Math.max(0, total.value - resp.data.succeeded_count)
      selectedFileIds.value = []
      return resp.data
    } catch (e) {
      throw new Error(e.response?.data?.detail || '批量删除失败')
    }
  }

  const batchRestore = async (fileIds) => {
    try {
      const resp = await axios.post('/api/v1/drive/files/batch-restore', { file_ids: fileIds })
      driveFiles.value = driveFiles.value.filter(f => !fileIds.includes(f.id))
      total.value = Math.max(0, total.value - resp.data.succeeded_count)
      selectedFileIds.value = []
      return resp.data
    } catch (e) {
      throw new Error(e.response?.data?.detail || '批量恢复失败')
    }
  }

  const batchMove = async (fileIds, targetFolderId) => {
    try {
      const resp = await axios.post('/api/v1/drive/files/batch-move', {
        file_ids: fileIds,
        target_folder_id: targetFolderId
      })
      driveFiles.value = driveFiles.value.filter(f => !fileIds.includes(f.id))
      total.value = Math.max(0, total.value - resp.data.succeeded_count)
      selectedFileIds.value = []
      return resp.data
    } catch (e) {
      throw new Error(e.response?.data?.detail || '批量移动失败')
    }
  }

  const batchUpdateVisibility = async (fileIds, visibility) => {
    try {
      const resp = await axios.post('/api/v1/drive/files/batch-update-visibility', {
        file_ids: fileIds,
        visibility
      })
      // 局部更新 visibility
      for (const f of driveFiles.value) {
        if (fileIds.includes(f.id) && !resp.data.skipped_ids?.includes(f.id)) {
          f.visibility = visibility
        }
      }
      return resp.data
    } catch (e) {
      throw new Error(e.response?.data?.detail || '批量改可见性失败')
    }
  }

  const permanentDeleteBatch = async (fileIds) => {
    try {
      const resp = await axios.post('/api/v1/drive/trash/permanent-delete', { file_ids: fileIds })
      driveFiles.value = driveFiles.value.filter(f => !fileIds.includes(f.id))
      total.value = Math.max(0, total.value - resp.data.succeeded_count)
      selectedFileIds.value = []
      return resp.data
    } catch (e) {
      throw new Error(e.response?.data?.detail || '物理删除失败')
    }
  }

  // === 内部辅助 ===
  function toggleSelect(id) {
    if (selectedFileIds.value.includes(id)) {
      selectedFileIds.value = selectedFileIds.value.filter(sid => sid !== id)
    } else {
      selectedFileIds.value = [...selectedFileIds.value, id]
    }
  }

  function clearSelection() {
    selectedFileIds.value = []
  }

  function selectAll() {
    selectedFileIds.value = driveFiles.value.map(f => f.id)
  }

  // ============================================================
  // v2 PR4: 文件秒传 + 版本历史
  // ============================================================

  /**
   * 秒传查询 — POST /files/instant-upload
   * @returns {Promise<{instant: boolean, file_id?: number, dedup_saved_bytes?: number, upload_url?: string}>}
   */
  async function instantUpload({ fileHash, fileName, fileSize, folderId = null, visibility = 'team', isTeamShared = false }) {
    const resp = await axios.post('/api/v1/drive/files/instant-upload', {
      file_hash: fileHash,
      file_name: fileName,
      file_size: fileSize,
      folder_id: folderId,
      visibility,
      is_team_shared: isTeamShared,  // v2 PR6-P19
    })
    return resp.data
  }

  /**
   * 列文件版本历史 — GET /files/{id}/versions
   * @returns {Promise<Array>} VersionItem[]
   */
  async function listVersions(fileId) {
    const resp = await axios.get(`/api/v1/drive/files/${fileId}/versions`)
    return resp.data
  }

  /**
   * 恢复历史版本 — POST /files/{id}/versions/{vid}/restore
   * @returns {Promise<object>} 新 Knowledge 行 (is_latest=True)
   */
  async function restoreVersion(fileId, versionId, changeNote = null) {
    const resp = await axios.post(
      `/api/v1/drive/files/${fileId}/versions/${versionId}/restore`,
      changeNote ? { change_note: changeNote } : {},
    )
    return resp.data
  }

  /** 获取文件下载 URL (用于历史版本"下载"按钮) */
  function downloadFileUrl(file) {
    return `/api/v1/drive/files/${file.id}/download`
  }

  return {
    // 状态
    driveFiles,
    total,
    currentPage,
    pageSize,
    loading,
    loadError,
    selectedFileIds,
    // v2 PR2: sort/filter state
    sortBy,
    sortOrder,
    starredOnly,
    fileType,
    // v2 PR6-P19: 视图隔离
    viewMode,
    // 计算
    isEmpty,
    hasSelection,
    // 方法
    fetchFiles,
    deleteFile,
    renameFile,
    moveFile,
    updateVisibility,
    extractToKb,
    createShareLink,
    revokeShareLink,
    // v2 PR2 新方法
    toggleStar,
    fetchStarred,
    fetchTrash,
    batchSoftDelete,
    batchRestore,
    batchMove,
    batchUpdateVisibility,
    permanentDeleteBatch,
    // v2 PR4 新方法
    instantUpload,
    listVersions,
    restoreVersion,
    downloadFileUrl,
    // 内部
    toggleSelect,
    clearSelection,
    selectAll
  }
}