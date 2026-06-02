import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

// MinIO bucket 名（与后端 settings.MINIO_BUCKET 保持一致）
const MINIO_BUCKET = 'microbubble'

/**
 * 把后端返回的 avatar 字段规范成可访问的 URL
 * - 完整 URL (http/https) → 原样返回
 * - 绝对路径 (/xxx) → 原样返回
 * - 裸路径 (avatars/xxx) → 转成 /minio/{bucket}/{path} 相对路径，
 *   浏览器自动拼当前域名，避免 /avatars/xxx 404
 */
function normalizeAvatarUrl(avatar) {
  if (!avatar) return null
  if (avatar.startsWith('http://') || avatar.startsWith('https://') || avatar.startsWith('/')) {
    return avatar
  }
  return `/minio/${MINIO_BUCKET}/${avatar}`
}

export const useMemberStore = defineStore('member', () => {
  const members = ref([])
  const loading = ref(false)
  let lastFetchTime = 0
  const CACHE_DURATION = 60000 // 缓存1分钟

  async function fetchMembers(params = {}) {
    // 如果有搜索参数或成员列表为空，强制获取新数据
    const now = Date.now()
    const hasSearchParams = params.name || params.grade
    const needsRefresh = members.value.length === 0 || hasSearchParams

    if (!needsRefresh && (now - lastFetchTime) < CACHE_DURATION) {
      return
    }

    loading.value = true
    try {
      const res = await axios.get('/api/v1/members', {
        params: { page_size: 100, ...params }
      })
      // 防御性：补全裸路径 avatar（早期 upload.py Query→Form 修复前的脏数据）
      const items = (res.data.items || []).map(m => ({
        ...m,
        avatar: normalizeAvatarUrl(m.avatar),
      }))
      members.value = items
      lastFetchTime = now
    } catch (e) {
      console.error('获取成员列表失败:', e)
    } finally {
      loading.value = false
    }
  }

  // 强制刷新成员数据（用于头像更新后）
  async function refreshMembers() {
    members.value = []
    lastFetchTime = 0
    await fetchMembers()
  }

  function getMemberName(id) {
    const m = members.value.find(m => m.id === id)
    return m ? m.name : '未分配'
  }

  function getMemberAvatar(id) {
    const m = members.value.find(m => m.id === id)
    return m?.avatar || null
  }

  return { members, loading, fetchMembers, refreshMembers, getMemberName, getMemberAvatar }
})
