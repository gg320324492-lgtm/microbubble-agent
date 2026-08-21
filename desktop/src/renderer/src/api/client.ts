// renderer axios 客户端（Phase 2+ 业务模块直连后端使用）。
//
// 设计原则：
// - baseURL 从 @shared/config 读（与 main 进程一致）
// - 401 拦截器占位（Phase 2 接入 refresh 单飞逻辑）
// - access_token 不直接持有；通过 IPC 从 main 拿（main 才是 token vault 真主）
// - Phase 1 主要用于测试基础 axios 配置，auth 流程仍走 IPC
//
// 严禁把 refresh_token / access_token 写到 localStorage / sessionStorage。

import axios, { type AxiosInstance, type AxiosError } from 'axios'
import { APP_CONFIG } from '@shared/config'

const client: AxiosInstance = axios.create({
  baseURL: APP_CONFIG.backendUrl,
  timeout: 15000,
  headers: {
    Accept: 'application/json',
    'Content-Type': 'application/json'
  }
})

// ---------- 请求拦截器：注入 JWT header ----------
// Phase 2+ 业务模块启用：每次请求通过 IPC 拿 access_token（永远不落 renderer 内存）
// 当前 Phase 1 留接口，不实际调用（auth 仍走 IPC 路径，避免 token 漂移到 renderer 内存）
client.interceptors.request.use(
  async (config) => {
    // 占位：Phase 2+ 实际从 window.api.auth.getAccessToken() 拿
    // const accessToken = await window.api.auth.getAccessToken?.()
    // if (accessToken) config.headers.set('Authorization', `Bearer ${accessToken}`)
    return config
  },
  (error) => Promise.reject(error)
)

// ---------- 响应拦截器：401 占位 ----------
client.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    // 占位：Phase 2+ 接入 refresh 单飞 (复用 web/src/utils/authRefresh.js 逻辑)
    // if (error.response?.status === 401 && !error.config.__isRetry) { ... }
    return Promise.reject(error)
  }
)

export default client
