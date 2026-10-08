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
import { useNow } from './useNow'

const POLL_INTERVAL_MS = 5 * 60 * 1000  // 5 分钟
const POLL_TIMEOUT_MS = 30 * 1000       // 30 秒 (W2 T4 P2-C 2026-07-20: 后端慢响应防御)

export function useKbMonitor() {
  const summary = ref(null)
  const lastUpdate = ref(null)
  const error = ref(null)
  const loading = ref(false)

  // 墙钟统一入口 (useNow): intervalMs=0 → 不起定时器, 完全跟随 poll 节奏。
  // lastUpdate 的语义是"KB 数据新鲜度"—— 只在 poll 成功那一刻打点, 不是每 5min 刷新一次,
  // 所以不能挂 useNow(300000) 直接读 now.value (那会让失败轮次也把时间推前, 语义变味)。
  // 正确做法: 成功分支里先 tick() 让 now.value 取当前时刻, 再把它记进 lastUpdate。
  const { now, tick } = useNow(0)

  let pollTimer = null

  async function fetchSummary() {
    loading.value = true
    try {
      // W2 T4 P2-C: axios timeout 30s 防御后端 hang, 超时 axios 会 reject with code='ECONNABORTED'
      // message='timeout of 30000ms exceeded' → 进 catch → 跳过本轮, 下个 5min tick 自然重试
      const res = await axios.get('/api/v1/knowledge/auto-intake-summary', { timeout: POLL_TIMEOUT_MS })
      summary.value = res.data
      tick()                          // 成功这一刻的墙钟值 (而非上次 tick 的时刻)
      lastUpdate.value = now.value    // tick() 每次重新赋值, lastUpdate 持有的 Date 不会被后续 tick 改动
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
