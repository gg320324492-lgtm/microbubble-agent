import { ref, onMounted, onUnmounted } from 'vue'

/**
 * v2 网络状态 — 心跳探测版 (2026-07-02)
 *
 * 修复点：
 *   - v1 完全依赖 navigator.onLine，浏览器偶发报 offline 导致 UI 误报"网络已断开"
 *   - v2 改为：navigator.onLine 仅作 hint + 触发立即重探测；状态翻转必须由实测驱动
 *
 * 设计：
 *   - 单例模块级 ref；useNetworkStatus() 与 getNetworkStatus() 共享同一 ref 树
 *   - 心跳：10s 一次 fetch，5s AbortController timeout，连续 3 次失败 → offline
 *   - 探测并发去重：多个 useNetworkStatus 同时触发也只发一次
 *   - 端点自学习：探测成功一次后缓存 workingEndpoint，优先复用
 *   - 卸载：refCount 归零时停 timer + 解绑事件
 *
 * 公共 API（向后兼容 v1）：
 *   useNetworkStatus() → { online, effectiveType, status, pendingCount, setPendingCount }
 *   getNetworkStatus() → { online, effectiveType, status, pendingCount }   // 非组件上下文
 *   markReachable()     // 强制置 online=true，reset 失败计数（供 uploadOne 成功调用）
 *   markUnreachable()   // 强制置 online=false（供 uploadOne 5 次失败后调用）
 *   _resetForTesting()  // 单测 reset 单例状态
 */

// ===== 可调参数 =====
const PROBE_INTERVAL = 10_000
const PROBE_TIMEOUT = 5_000
const FAIL_THRESHOLD = 3
// v2.1 修复: /api/v1/health 返 404 (路径不存在), 改用 /health (200 真存在)
// 注意顺序: 已知最快的端点放前面 (自学习会缓存, 优先用)
const PROBE_ENDPOINTS = ['/health', '/api/v1/auth/me', '/api/v1/health']

// ===== 模块级单例状态 =====
const online = ref(typeof navigator !== 'undefined' ? navigator.onLine : true)
const effectiveType = ref('4g')
const pendingCount = ref(0)
const status = ref(computeStatus(online.value, effectiveType.value))

let probeTimer = null
let probing = false
let failStreak = 0
let workingEndpoint = null
let mountedCount = 0
let listenersAttached = false

// ===== 内部工具 =====

function computeStatus(isOnline, effType) {
  if (!isOnline) return 'offline'
  if (['slow-2g', '2g', '3g'].includes(effType)) return 'weak'
  return 'online'
}

function recompute() {
  status.value = computeStatus(online.value, effectiveType.value)
}

async function probeOnce(url) {
  if (typeof AbortController === 'undefined' || typeof fetch === 'undefined') return false
  const ctl = new AbortController()
  const timer = setTimeout(() => ctl.abort(), PROBE_TIMEOUT)
  try {
    const res = await fetch(url, {
      method: 'GET',
      cache: 'no-store',
      credentials: 'same-origin',
      signal: ctl.signal,
    })
    // 任何有 status 的响应都视为 alive（200/304/401/403/5xx 都算后端在响应）
    return typeof res.status === 'number' && res.status > 0
  } catch {
    return false
  } finally {
    clearTimeout(timer)
  }
}

async function probe() {
  if (probing) return                          // 探测并发去重
  if (typeof fetch === 'undefined') return
  probing = true
  try {
    const endpoints = workingEndpoint
      ? [workingEndpoint, ...PROBE_ENDPOINTS.filter(e => e !== workingEndpoint)]
      : PROBE_ENDPOINTS
    let ok = false
    for (const ep of endpoints) {
      if (await probeOnce(ep)) {
        workingEndpoint = ep
        ok = true
        break
      }
    }
    if (ok) {
      if (!online.value || failStreak > 0) {
        online.value = true
        failStreak = 0
        recompute()
      }
    } else {
      failStreak++
      workingEndpoint = null                  // 端点可能挂了，重新学习
      if (failStreak >= FAIL_THRESHOLD && online.value) {
        online.value = false
        recompute()
      }
    }
  } finally {
    probing = false
  }
}

// ===== 浏览器事件桥接 =====

function onBrowserOnline() {
  // 浏览器恢复时立即探测一次以验证；探测成功前不强行翻状态
  failStreak = 0
  probe()
}

function onBrowserOffline() {
  // 关键修复：浏览器报 offline 不立即翻状态！
  // 让心跳在 FAIL_THRESHOLD 次连续失败后才置 offline（避免原 v1 的误报）
  // 但立刻触发一次探测以加速收敛
  probe()
}

function onConnChange() {
  if (typeof navigator !== 'undefined' && navigator.connection?.effectiveType) {
    effectiveType.value = navigator.connection.effectiveType
    recompute()
  }
}

function attachListeners() {
  if (listenersAttached || typeof window === 'undefined') return
  listenersAttached = true
  window.addEventListener('online', onBrowserOnline)
  window.addEventListener('offline', onBrowserOffline)
  if (typeof navigator !== 'undefined' && navigator.connection) {
    effectiveType.value = navigator.connection.effectiveType || '4g'
    navigator.connection.addEventListener?.('change', onConnChange)
  }
}

function detachListeners() {
  if (!listenersAttached || typeof window === 'undefined') return
  listenersAttached = false
  window.removeEventListener('online', onBrowserOnline)
  window.removeEventListener('offline', onBrowserOffline)
  if (typeof navigator !== 'undefined' && navigator.connection) {
    navigator.connection.removeEventListener?.('change', onConnChange)
  }
}

function startProbing() {
  if (probeTimer || typeof window === 'undefined') return
  probe()                                     // 立即探测一次
  probeTimer = setInterval(probe, PROBE_INTERVAL)
}

function stopProbing() {
  if (probeTimer) {
    clearInterval(probeTimer)
    probeTimer = null
  }
}

// ===== 外部命令接口（供 uploadOne 等非组件上下文调用） =====

function markReachable() {
  if (!online.value || failStreak > 0) {
    online.value = true
    failStreak = 0
    recompute()
  }
}

function markUnreachable() {
  // v2.1 修复: 累积式翻红, 不是立即翻
  // 5xx/网络错只 +1, 累积到 failStreak >= FAIL_THRESHOLD (3) 才翻红
  // 之前设计: 1 次 markUnreachable 立即翻红 → 每次录音 chunk 5xx 翻红一次 → 视觉上持续红
  // 实际: 5xx 持续 (cloud 8000 没人听) 应该累积到 3 次才翻红
  // 单次 5xx (瞬时网络抖) 不该翻红 (probe 10s 内会拉回)
  if (failStreak < FAIL_THRESHOLD) {
    failStreak++
  }
  if (failStreak >= FAIL_THRESHOLD && online.value) {
    online.value = false
    recompute()
    console.warn(`[useNetworkStatus] markUnreachable 触发 failStreak=${failStreak}, online=false`)
  }
}

// ===== 公共 API =====

export function useNetworkStatus() {
  onMounted(() => {
    mountedCount++
    if (mountedCount === 1) {
      attachListeners()
      startProbing()
    }
  })
  onUnmounted(() => {
    mountedCount--
    if (mountedCount <= 0) {
      mountedCount = 0
      stopProbing()
      detachListeners()
    }
  })

  function setPendingCount(n) {
    pendingCount.value = n
  }

  return { online, effectiveType, status, pendingCount, setPendingCount }
}

export function getNetworkStatus() {
  return { online, effectiveType, status, pendingCount }
}

export { markReachable, markUnreachable }

// ===== 单测用：reset 模块级单例 =====
export function _resetForTesting() {
  online.value = typeof navigator !== 'undefined' ? navigator.onLine : true
  effectiveType.value = '4g'
  pendingCount.value = 0
  status.value = computeStatus(online.value, effectiveType.value)
  failStreak = 0
  probing = false
  workingEndpoint = null
  mountedCount = 0
  if (probeTimer) clearInterval(probeTimer)
  probeTimer = null
  if (listenersAttached) detachListeners()
  listenersAttached = false
}

// ===== 单测钩子（让测试可访问内部状态） =====
export function _test_probe() { return probe() }
export function _test_getFailStreak() { return failStreak }
export function _test_setFailStreak(n) { failStreak = n }
export function _test_isProbing() { return probeTimer !== null }
export function _test_setWorkingEndpoint(ep) { workingEndpoint = ep }
