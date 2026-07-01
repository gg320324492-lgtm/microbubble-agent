// useDriveFiles.js — 课题组网盘 PR3.3 drive 文件列表 composable
// 2026-07-01

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
        ...params
      }
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

  return {
    // 状态
    driveFiles,
    total,
    currentPage,
    pageSize,
    loading,
    loadError,
    selectedFileIds,
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
    toggleSelect,
    clearSelection,
    selectAll
  }
}