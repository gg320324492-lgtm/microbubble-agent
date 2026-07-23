import { ref } from 'vue'
import axios from 'axios'

/** Version list item consumed by the desktop comparison picker and metadata view. */
export interface DriveVersionOption {
  id: number
  version_number: number
  size?: number
  uploader_id?: number
  uploader_name?: string | null
  created_at?: string | null
  is_current?: boolean
}

/** Metadata returned for one file version. */
export interface VersionDiffMeta {
  version_id: number
  version_number: number
  size: number
  uploader_id: number
  comment?: string | null
  is_current: boolean
  created_at?: string | null
  warning?: string | null
}

/** Unified response shared by text and binary comparisons. */
export interface VersionDiffResult {
  file_id: number
  file_name: string
  from_version_number: number
  from_version_id: number
  to_version_number: number
  to_version_id: number
  is_text: boolean
  unified_diff?: string | null
  changed_lines?: number[] | null
  additions?: number | null
  deletions?: number | null
  size_delta: number
  uploader_delta: boolean
  from_meta: VersionDiffMeta
  to_meta: VersionDiffMeta
}

function authHeaders() {
  const token = typeof localStorage === 'undefined'
    ? ''
    : localStorage.getItem('access_token') || ''
  return { Authorization: `Bearer ${token}` }
}

function errorMessage(error: any, fallback: string) {
  return error?.response?.data?.error?.message
    || error?.response?.data?.detail
    || error?.message
    || fallback
}

export function formatVersionSize(bytes?: number | null) {
  if (bytes === null || bytes === undefined) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

/**
 * Desktop-only state for Drive file version comparison.
 *
 * Query parameters are encoded into the URL instead of axios `params` because
 * the Drive UI has previously observed query loss in production builds.
 */
export function useVersionDiffDesktop() {
  const loading = ref(false)
  const error = ref<string | null>(null)
  const notFound = ref(false)
  const diffResult = ref<VersionDiffResult | null>(null)
  let requestEpoch = 0

  function clearDiff() {
    requestEpoch += 1
    loading.value = false
    error.value = null
    notFound.value = false
    diffResult.value = null
  }

  async function compareVersions(
    fileId: number | string,
    fromVersion: number,
    toVersion: number,
  ): Promise<VersionDiffResult | null> {
    const fid = Number(fileId)
    const from = Number(fromVersion)
    const to = Number(toVersion)

    error.value = null
    notFound.value = false
    diffResult.value = null

    if (!Number.isInteger(fid) || fid < 1) {
      error.value = '文件编号无效，无法加载版本对比'
      return null
    }
    if (!Number.isInteger(from) || from < 1 || !Number.isInteger(to) || to < 1) {
      error.value = '请选择有效的起始版本和目标版本'
      return null
    }
    if (from === to) {
      error.value = '请选择两个不同的版本进行对比'
      return null
    }

    loading.value = true
    const epoch = ++requestEpoch
    try {
      const query = new URLSearchParams({ from: String(from), to: String(to) })
      const response = await axios.get(
        `/api/v1/drive/versions/files/${fid}/diff?${query.toString()}`,
        { headers: authHeaders() },
      )
      if (epoch !== requestEpoch) return null
      diffResult.value = response.data as VersionDiffResult
      return diffResult.value
    } catch (requestError: any) {
      if (epoch !== requestEpoch) return null
      const status = requestError?.response?.status
      notFound.value = status === 404
      error.value = status === 404
        ? '未找到指定文件或版本，请刷新版本历史后重试'
        : errorMessage(requestError, '版本对比加载失败，请稍后重试')
      return null
    } finally {
      if (epoch === requestEpoch) loading.value = false
    }
  }

  return {
    loading,
    error,
    notFound,
    diffResult,
    compareVersions,
    clearDiff,
  }
}
