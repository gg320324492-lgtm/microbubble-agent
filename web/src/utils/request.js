/**
 * request.js — 全局 axios 拦截器 (类 20.155, 2026-08-14)
 *
 * 替代 main.js:86-141 inline 拦截器, 拆分为:
 * - request 拦截器: 注入 Authorization header (每个请求)
 * - response 拦截器:
 *   - 401: 调 refreshAccessToken() (单飞), retry 一次; 失败由 hardLogout 副作用处理
 *   - 429: 读 Retry-After, jittered sleep, retry 一次; 仍 429 reject
 *   - 其它: 直接 reject
 *
 * 与 authRefresh.js 配合实现:
 * - D1 (无单飞) → refreshAccessToken 单飞解决
 * - D2 (20/min 易爆) → refresh 走 auth_refresh 60/min tier (后端)
 * - D3 (refresh 带 token 触发 key 退化) → bare axios 不挂拦截器
 * - D4 (429/401 等同) → 429 单独 retry 一次, 不登出
 * - D5 (token 不清导致 reload 循环) → hardLogout 副作用清 token
 */
import axios from 'axios'
import { refreshAccessToken, hardLogout, isPublicEndpoint } from './authRefresh'

// 429 retry 配置
const RL_MAX_RETRIES = 2  // 每个请求最多重试 2 次 429

// 抖动 sleep
function jitteredSleep(ms) {
  const jitter = Math.floor(Math.random() * 250)
  return new Promise(resolve => setTimeout(resolve, ms + jitter))
}

// request 拦截器 — 注入 Authorization
axios.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// response 拦截器 — 401 refresh + 429 retry
axios.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config
    if (!config) return Promise.reject(error)

    const status = error.response?.status
    const url = config.url || ''

    // 公开端点 (login/refresh) 不进 401 refresh 流程
    if (status === 401 && isPublicEndpoint(url)) {
      return Promise.reject(error)
    }

    // 401 处理 — refresh + retry 一次
    if (status === 401 && !config._retry) {
      config._retry = true
      try {
        const newToken = await refreshAccessToken()
        if (newToken) {
          config.headers.Authorization = `Bearer ${newToken}`
          return axios(config)
        }
      } catch (refreshErr) {
        // refreshAccessToken 失败: REFRESH_TOKEN_EXPIRED/INVALID → hardLogout 已触发
        // REFRESH_COOLDOWN / RATE_LIMITED / SERVER_ERROR → 让请求方正常 reject (用户留在 dashboard)
        return Promise.reject(refreshErr)
      }
      // refresh 返回 falsy (不应发生, 但保险)
      return Promise.reject(error)
    }

    // 429 处理 — 读 Retry-After, retry 最多 2 次
    if (status === 429) {
      const retries = config._rlRetry || 0
      if (retries < RL_MAX_RETRIES) {
        config._rlRetry = retries + 1
        const retryAfterHeader = error.response.headers?.['retry-after']
        const retryAfterMs = retryAfterHeader
          ? parseInt(retryAfterHeader, 10) * 1000
          : Math.min(1000 * Math.pow(2, retries), 30000)
        await jitteredSleep(retryAfterMs)
        return axios(config)
      }
      // 重试上限, 直接 reject
      return Promise.reject(error)
    }

    return Promise.reject(error)
  }
)

export default axios