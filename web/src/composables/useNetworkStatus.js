import { ref, onMounted, onUnmounted } from 'vue'

/**
 * 网络状态检测 composable
 * - online: navigator.onLine
 * - effectiveType: '4g' | '3g' | '2g' | 'slow-2g'（来自 navigator.connection）
 * - status: 'online' | 'weak' | 'offline'
 * - pendingCount: 待发送音频块数（外部 setPendingCount 注入）
 */
export function useNetworkStatus() {
  const online = ref(typeof navigator !== 'undefined' ? navigator.onLine : true)
  const effectiveType = ref('4g')
  const status = ref('online')
  const pendingCount = ref(0)

  function updateStatus() {
    if (!online.value) {
      status.value = 'offline'
    } else if (
      typeof navigator !== 'undefined' &&
      navigator.connection?.effectiveType &&
      ['slow-2g', '2g', '3g'].includes(navigator.connection.effectiveType)
    ) {
      status.value = 'weak'
    } else {
      status.value = 'online'
    }
  }

  function onOnline() {
    online.value = true
    updateStatus()
  }

  function onOffline() {
    online.value = false
    updateStatus()
  }

  onMounted(() => {
    if (typeof navigator === 'undefined') return
    updateStatus()
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)
    if (navigator.connection) {
      effectiveType.value = navigator.connection.effectiveType || '4g'
      navigator.connection.addEventListener?.('change', updateStatus)
    }
  })

  onUnmounted(() => {
    if (typeof window === 'undefined') return
    window.removeEventListener('online', onOnline)
    window.removeEventListener('offline', onOffline)
    navigator.connection?.removeEventListener?.('change', updateStatus)
  })

  function setPendingCount(n) {
    pendingCount.value = n
  }

  return { online, effectiveType, status, pendingCount, setPendingCount }
}
