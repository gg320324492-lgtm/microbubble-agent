/**
 * KB 入库监控 Composable (W6 D5)
 *
 * 2026-06-30 实施 — 给 ProjectStatsView 第 3 个 tab "KB 入库监控" 提供数据
 *
 * 功能:
 * - 自动 polling 5min 拉取 /api/v1/knowledge/auto-intake-summary
 * - 5 张图: 今日入库 / 7日趋势 / 命中率 / 负反馈率 / rollback 警告
 * - 用户离开页面自动停止 polling
 *
 * 设计选择 Q5: polling 5min (而非 WebSocket)
 * - 数据本身不是高频 (一天 5-20 条入库)
 * - 简单: 5 行 setInterval
 * - 浏览器后台自动降频
 *
 * @example
 * const { summary, lastUpdate, error, refresh } = useKbMonitor()
 * // summary = { today_intake, weekly_intake[7], hit_rate, ... }
 */
import { ref, onMounted, onUnmounted } from 'vue'
import axios from 'axios'

const POLL_INTERVAL_MS = 5 * 60 * 1000  // 5 分钟
const POLL_TIMEOUT_MS = 30 * 1000       // 30 秒 (W2 T4 P2-C 2026-07-20: 后端慢响应防御)

export function useKbMonitor() {
  const summary = ref(null)
  const lastUpdate = ref(null)
  const error = ref(null)
  const loading = ref(false)

  let pollTimer = null

  async function fetchSummary() {
    loading.value = true
    try {
      // W2 T4 P2-C: axios timeout 30s 防御后端 hang, 超时 axios 会 reject with code='ECONNABORTED'
      // message='timeout of 30000ms exceeded' → 进 catch → 跳过本轮, 下个 5min tick 自然重试
      const res = await axios.get('/api/v1/knowledge/auto-intake-summary', { timeout: POLL_TIMEOUT_MS })
      summary.value = res.data
      lastUpdate.value = new Date()
      error.value = null
    } catch (e) {
      // 超时 / 网络错 / 5xx 统一进 catch, 保留上次 data (W5 T5.4 教训)
      // 不 console.error 噪音 (polling 30s timeout 在网络抖动时是正常路径)
      error.value = e.message || 'Failed to fetch KB summary'
    } finally {
      loading.value = false
    }
  }

  function startPolling() {
    if (pollTimer) return  // 避免重复启动
    fetchSummary()                                    // 立即拉一次
    pollTimer = setInterval(fetchSummary, POLL_INTERVAL_MS)  // ← 这里就是 Q5 polling 5min
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  onMounted(startPolling)
  onUnmounted(stopPolling)

  return {
    summary,
    lastUpdate,
    error,
    loading,
    refresh: fetchSummary,
    startPolling,
    stopPolling,
  }
}
