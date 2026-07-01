// useStorageQuota.js — v2 网盘 PR5 配额 composable
// 2026-07-01

import { ref, computed, watch } from 'vue'
import axios from 'axios'

/**
 * 网盘配额状态管理
 *
 * 数据流:
 * 1. fetchQuota() -> GET /api/v1/drive/storage-quota -> quotaInfo.value
 * 2. 监听 upload 完成后 (useDriveFiles.uploaded) 调 fetchQuota 刷新
 * 3. 提供 isOverQuota / isWarn 计算属性 (UI badge 颜色阈值)
 *
 * 阈值约定 (与 UI 视觉对齐):
 * - < 80%: success (绿)
 * - 80% ~ 95%: warning (黄)
 * - >= 95%: danger (红)
 * - >= 100%: isOverQuota=true → 上传按钮 disable
 */
export function useStorageQuota() {
  const quotaInfo = ref(null)
  const loading = ref(false)
  const error = ref(null)

  const usedBytes = computed(() => quotaInfo.value?.used_bytes ?? 0)
  const quotaBytes = computed(() => quotaInfo.value?.quota_bytes ?? 0)
  const percent = computed(() => quotaInfo.value?.percent ?? 0)
  const fileCount = computed(() => quotaInfo.value?.file_count ?? 0)
  const isOverQuota = computed(() => quotaInfo.value?.is_over_quota ?? false)

  // 80% 警告阈值
  const isWarn = computed(() => percent.value >= 0.8 && percent.value < 0.95)
  // 95% 危险阈值
  const isDanger = computed(() => percent.value >= 0.95 && !isOverQuota.value)

  /**
   * 获取配额 (可重复调用, 内部防并发)
   */
  async function fetchQuota() {
    if (loading.value) return
    loading.value = true
    error.value = null
    try {
      const resp = await axios.get('/api/v1/drive/storage-quota')
      quotaInfo.value = resp.data
    } catch (e) {
      error.value = e.response?.data?.detail || e.message || '配额加载失败'
      // 不清空 quotaInfo, 保留旧数据 (避免徽章闪烁)
    } finally {
      loading.value = false
    }
  }

  /**
   * 上传前检查是否会超额
   * @param {number} additionalBytes - 待上传字节数
   * @returns {boolean} true=允许上传, false=配额不足
   */
  function canUpload(additionalBytes) {
    if (!quotaInfo.value) return true  // 数据未加载, 乐观放行
    return (usedBytes.value + additionalBytes) <= quotaBytes.value
  }

  /**
   * 格式化字节数为人类可读字符串
   */
  function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return `${(bytes / Math.pow(k, i)).toFixed(i === 0 ? 0 : 1)} ${sizes[i]}`
  }

  return {
    quotaInfo,
    loading,
    error,
    usedBytes,
    quotaBytes,
    percent,
    fileCount,
    isOverQuota,
    isWarn,
    isDanger,
    fetchQuota,
    canUpload,
    formatBytes,
  }
}