/**
 * 通知偏好 Composable（v2 11AM 单一窗口）
 *
 * 2026-06-15 任务提醒体系全面优化：
 * - 用户可关闭/启用提醒
 * - 用户可改 digest_time（默认 11:00 北京）
 * - 用户可临时 snooze（snoozed_until 字段）
 *
 * @example
 * const { prefs, loading, fetchPrefs, savePrefs, unsnooze } = useNotificationPrefs()
 * await fetchPrefs()
 * await savePrefs({ digest_time: '09:00' })
 */
import { ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

export function useNotificationPrefs() {
  const prefs = ref(null)
  const loading = ref(false)

  async function fetchPrefs() {
    loading.value = true
    try {
      const { data } = await axios.get('/api/v1/members/me/notification-preferences')
      prefs.value = data
    } catch (e) {
      console.error('加载通知偏好失败', e)
      ElMessage.error('加载通知偏好失败')
    } finally {
      loading.value = false
    }
  }

  async function savePrefs(payload) {
    loading.value = true
    try {
      const { data } = await axios.put('/api/v1/members/me/notification-preferences', payload)
      prefs.value = data
      ElMessage.success('通知偏好已更新（已有提醒会按新时间重排）')
      return data
    } catch (e) {
      const msg = e.response?.data?.error?.message || e.message
      ElMessage.error(`保存失败：${msg}`)
      throw e
    } finally {
      loading.value = false
    }
  }

  /**
   * 解除 snooze（让 pending reminders 重新按 digest_time 发送）
   */
  async function unsnooze() {
    return savePrefs({ snoozed_until: null })
  }

  return {
    prefs,
    loading,
    fetchPrefs,
    savePrefs,
    unsnooze,
  }
}
