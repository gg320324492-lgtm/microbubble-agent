/**
 * authRefresh.js — JWT access_token 刷新单飞 + 退避 (类 20.155, 2026-08-14)
 *
 * 设计要点:
 * 1. **单飞**: N 个并发 401 只产生 1 个 refresh POST, 共享同一 Promise
 * 2. **bare axios 实例**: 不挂任何拦截器, refresh 请求不带 Authorization header
 *    → 避免后端 _try_attach_user_id decode 过期 access_token 失败 → key 退化为 :anon
 *    → 配合后端 auth_refresh tier 60/min, 不与 login 等敏感端点共桶
 * 3. **失败分类**:
 *    - 401/403 (refresh_token 无效/过期) → hardLogout() + reject
 *    - 429 (限流) → 设 _refreshCooldownUntil 到 Retry-After 时刻, reject cooldown error, **不** 登出
 *    - 5xx / network → 5s/30s/60s 指数退避 (复用 useChunkedUploaderCore 模式)
 * 4. **cooldown**: cooldown 期间被调直接 reject, 不发出请求, **彻底打断风暴循环**
 * 5. **hardLogout 单次**: 全局 _logoutInProgress flag, 防止 N 个并发 401 → N 次 router.push
 * 6. **WS 联动**: hardLogout 触发时调 wsClient.disableReconnect(), 让 WS 别再浪费重连
 */
import axios from 'axios'
import router from '@/router'
import { useUserStore } from '@/stores/user'
import wsClient from '@/utils/wsClient'

// bare axios 实例, **不挂任何拦截器**
const bareAxios = axios.create()

// 模块级单飞状态
let _pendingRefresh = null
let _refreshCooldownUntil = 0
let _logoutInProgress = false

const REFRESH_URL = '/api/v1/auth/refresh'
const PUBLIC_ENDPOINT_MARKERS = ['/auth/login', '/auth/refresh', '/auth/reset-password-self']

/**
 * 检查当前是否在 cooldown (避免网络请求)
 * @returns {boolean}
 */
export function isInCooldown() {
  return Date.now() < _refreshCooldownUntil
}

/**
 * 获取 cooldown 剩余秒数 (用于 UI 提示)
 */
export function cooldownRemainingSeconds() {
  const ms = _refreshCooldownUntil - Date.now()
  return ms > 0 ? Math.ceil(ms / 1000) : 0
}

/**
 * 硬登出 — 幂等, 只执行 1 次
 * 清 token + 清 axios 默认头 + 调 useUserStore.logout() + 跳登录页 + 停 WS 重连
 * @param {string} reason - 'refresh_token_expired' | 'refresh_5xx_exhausted' | 'no_refresh_token'
 */
export async function hardLogout(reason = 'unknown') {
  if (_logoutInProgress) return
  _logoutInProgress = true
  _pendingRefresh = null

  console.warn(`[Auth] hardLogout (${reason})`)

  // 清 token (main.js:128/134 W68 第 14 批修复反转 — 现在单飞后清除安全)
  try {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    delete bareAxios.defaults.headers.common?.['Authorization']
    delete axios.defaults.headers.common?.['Authorization']
  } catch (e) {
    // ignore
  }

  // 调 useUserStore.logout (清 user_info + chat 相关 localStorage)
  try {
    const userStore = useUserStore()
    if (userStore?.logout) userStore.logout()
  } catch (e) {
    // store 未初始化也继续
  }

  // 停 WS 重连, 避免硬登出后 WS 还在疯狂重连消耗资源
  try {
    if (wsClient?.disableReconnect) wsClient.disableReconnect()
  } catch (e) {
    // ignore
  }

  // 跳登录页 (router 可能未就绪, 包 try)
  try {
    if (router && router.currentRoute?.value?.path !== '/login') {
      router.push('/login').catch(() => {})
    }
  } catch (e) {
    // ignore
  }

  // 给一个 microtask 让 _logoutInProgress 被新请求 catch 到, 然后清 flag
  // (不清的话下次 hardLogout 永远 noop, 但单飞已 null, 也不会触发; 留 flag 即可)
}

/**
 * 单飞 refresh — 返回新 access_token
 * @returns {Promise<string>}
 */
export async function refreshAccessToken() {
  // cooldown 期间直接 reject, 不发请求 (彻底打断风暴循环)
  if (isInCooldown()) {
    const remain = cooldownRemainingSeconds()
    const err = new Error(`refresh_cooldown ${remain}s remaining`)
    err.code = 'REFRESH_COOLDOWN'
    err.remainingSeconds = remain
    throw err
  }

  // 单飞 — 已 in-flight 直接返回同一 Promise
  if (_pendingRefresh) return _pendingRefresh

  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) {
    hardLogout('no_refresh_token')
    const err = new Error('no_refresh_token')
    err.code = 'NO_REFRESH_TOKEN'
    throw err
  }

  _pendingRefresh = (async () => {
    try {
      const res = await bareAxios.post(REFRESH_URL, { refresh_token: refreshToken })
      const { access_token } = res.data || {}
      if (!access_token) {
        throw new Error('refresh response missing access_token')
      }

      // 成功 — 存新 token
      localStorage.setItem('access_token', access_token)
      axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`

      // 单飞完成后清 pending, 下次 401 触发新一轮 refresh
      _pendingRefresh = null
      return access_token
    } catch (err) {
      _pendingRefresh = null

      const status = err.response?.status

      // 401/403 — refresh_token 过期或无效, 必须硬登出
      if (status === 401 || status === 403) {
        await hardLogout('refresh_token_expired')
        const out = new Error('refresh_token_expired')
        out.code = 'REFRESH_TOKEN_EXPIRED'
        out.cause = err
        throw out
      }

      // 429 — 限流, 设 cooldown, **不** 登出 (用户可能在多 tab, 让他们有 cooldown 期)
      if (status === 429) {
        const retryAfter = parseInt(err.response.headers?.['retry-after'] || '60', 10)
        _refreshCooldownUntil = Date.now() + (retryAfter * 1000)
        const out = new Error(`refresh_rate_limited ${retryAfter}s`)
        out.code = 'REFRESH_RATE_LIMITED'
        out.remainingSeconds = retryAfter
        out.cause = err
        throw out
      }

      // 5xx / network — 1 次重试, 退避 5s
      if (status >= 500 || !status) {
        const out = new Error('refresh_server_error')
        out.code = 'REFRESH_SERVER_ERROR'
        out.cause = err
        throw out
      }

      // 其它 4xx (如 400) — refresh_token 格式错, 硬登出
      await hardLogout('refresh_token_invalid')
      const out = new Error('refresh_token_invalid')
      out.code = 'REFRESH_TOKEN_INVALID'
      out.cause = err
      throw out
    }
  })()

  return _pendingRefresh
}

/**
 * 公开端点判断 — 不进 401 refresh 流程
 */
export function isPublicEndpoint(url) {
  if (!url) return false
  return PUBLIC_ENDPOINT_MARKERS.some(marker => url.includes(marker))
}

/**
 * 重置所有状态 (测试用)
 */
export function _resetForTest() {
  _pendingRefresh = null
  _refreshCooldownUntil = 0
  _logoutInProgress = false
}

export default {
  refreshAccessToken,
  hardLogout,
  isInCooldown,
  cooldownRemainingSeconds,
  isPublicEndpoint,
  _resetForTest,
}