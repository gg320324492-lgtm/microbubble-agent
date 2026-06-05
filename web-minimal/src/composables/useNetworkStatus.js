import { ref, onMounted, onUnmounted } from 'vue'

export function useNetworkStatus() {
  const isOnline = ref(navigator.onLine)
  const connectionType = ref(null)
  const effectiveType = ref(null)
  const downlink = ref(null)
  const rtt = ref(null)

  const updateNetworkStatus = () => {
    isOnline.value = navigator.onLine

    // 获取连接信息（如果可用）
    if ('connection' in navigator) {
      const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection
      if (connection) {
        connectionType.value = connection.type || null
        effectiveType.value = connection.effectiveType || null
        downlink.value = connection.downlink || null
        rtt.value = connection.rtt || null
      }
    }
  }

  const handleOnline = () => {
    isOnline.value = true
    updateNetworkStatus()
  }

  const handleOffline = () => {
    isOnline.value = false
  }

  const handleConnectionChange = () => {
    updateNetworkStatus()
  }

  onMounted(() => {
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    // 监听连接变化
    if ('connection' in navigator) {
      const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection
      if (connection) {
        connection.addEventListener('change', handleConnectionChange)
      }
    }

    updateNetworkStatus()
  })

  onUnmounted(() => {
    window.removeEventListener('online', handleOnline)
    window.removeEventListener('offline', handleOffline)

    // 移除连接变化监听
    if ('connection' in navigator) {
      const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection
      if (connection) {
        connection.removeEventListener('change', handleConnectionChange)
      }
    }
  })

  return {
    isOnline,
    connectionType,
    effectiveType,
    downlink,
    rtt
  }
}
