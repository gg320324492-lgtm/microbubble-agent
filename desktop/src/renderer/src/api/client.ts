// renderer axios 客户端（Phase 2+ 业务模块直连后端非鉴权 endpoint 使用）。
//
// Phase 1-Impl-2 设计（详见 docs/desktop-conversion/security.md §API Gateway）：
// - renderer 永不在 axios 客户端持有 token（access 或 refresh 都无）
// - 所有鉴权 endpoint 必须经 window.api.api.request 走主进程 API Gateway
// - 本 client 仅供 renderer 调非鉴权 endpoint（如公开元数据、健康检查）
//
// 严禁：
// - ❌ 在任何拦截器注入 Authorization header
// - ❌ 直接调需要鉴权的后端 endpoint
// - ❌ 同步 access_token / refresh_token 到 renderer 任何层

import axios, { type AxiosInstance } from 'axios'
import { APP_CONFIG } from '@shared/config'

const client: AxiosInstance = axios.create({
  baseURL: APP_CONFIG.backendUrl,
  timeout: 15000,
  headers: {
    Accept: 'application/json',
    'Content-Type': 'application/json'
  }
})

// 不加任何 token 注入拦截器。
// 401 → 归一化为 HttpError（api.service 仍在主进程处理 refresh）。

export default client
