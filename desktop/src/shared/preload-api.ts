import type {
  LoginRequest,
  UserInfo,
  AuthRestoreResult,
  AuthErrorPayload
} from './auth-types'
import type { PingRequest, PongResponse } from './common-types'

// Re-export for renderer convenience
export type { PingRequest, PongResponse }
export type {
  LoginRequest,
  UserInfo,
  AuthRestoreResult,
  AuthErrorPayload
}

/**
 * 暴露给渲染进程的桌面 API 类型契约（单一源）。
 *
 * 任何 channel 新增 / 重命名 / 删除，必须同步修改：
 *   - src/preload/index.ts  (实际实现 + contextBridge 暴露)
 *   - src/main/ipc.ts       (ipcMain.handle 注册)
 *   - src/shared/ipc-types.ts (channel 名)
 *   - 本文件                  (类型形状)
 */
export interface DesktopPingApi {
  ping: (payload?: PingRequest) => Promise<PongResponse>
}

export interface DesktopAuthApi {
  /**
   * 用户名/邮箱 + 密码登录。
   * 成功：返回 { expiresAt, user }，access_token 进主进程内存，refresh_token 进 safeStorage。
   *   - 注意：refresh_token 永不出主进程；expiresAt 来自 JWT exp claim
   * 失败：返回 AuthErrorPayload（不抛）。
   */
  login: (payload: LoginRequest) => Promise<
    { success: true; data: { expiresAt: number; user: UserInfo } } | { success: false; error: AuthErrorPayload }
  >

  /**
   * 登出（清内存 access_token + safeStorage 中密文 + electron-store 中 user）。
   * 永远返回 success（幂等）。
   */
  logout: () => Promise<{ success: true }>

  /**
   * 应用启动时尝试恢复 session：
   *   - 从 electron-store 取密文 → safeStorage.decryptString 还原 refresh_token
   *   - 调后端 /auth/refresh 拿新 access_token
   *   - 调后端 /auth/me 拉最新 user
   *   - 成功：返回 expiresAt + user；失败：返回 null
   * 任何异常都返回 null，renderer 清空 Pinia state。
   */
  restore: () => Promise<AuthRestoreResult | null>

  /**
   * 方便前端展示"当前连哪个后端"——主要是开发/调试用。
   */
  getBackendUrl: () => Promise<string>
}

/**
 * IPC API Gateway —— 所有需要鉴权的业务请求都走这条。
 *
 * 任何 renderer 想调后端的鉴权 endpoint（如 /api/v1/tasks）都必须经此：
 *   window.api.api.request({ method, path, body, query })
 *
 * 主进程:
 *   1. 注入 Bearer access_token (主进程内存里)
 *   2. 调后端
 *   3. 收到 401 → 单飞 refresh → 用新 token 重试一次
 *      - refresh 失败 → 整个 session 强制 re-login (renderer 跳 /login)
 *   4. 响应归一化为 { ok, data, error }
 */
export interface ApiRequestPayload {
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  /** 后端 endpoint 路径，例如 "/tasks"。不含 baseURL，baseURL 由 main 决定。 */
  path: string
  /** JSON body (POST/PUT/PATCH) 或 undefined (GET/DELETE). */
  body?: unknown
  /** query string 对象（GET 常用）。 */
  query?: Record<string, string | number | boolean>
  /** request timeout ms. 默认 15000. */
  timeoutMs?: number
}

export interface ApiError {
  code: 'INVALID_INPUT' | 'UNAUTHORIZED' | 'TOKEN_EXPIRED' | 'USER_DISABLED' | 'FORBIDDEN' | 'NOT_FOUND' | 'RATE_LIMITED' | 'SERVER_ERROR' | 'NETWORK_ERROR' | 'INVALID_RESPONSE' | 'UNKNOWN_ERROR' | 'NO_ACTIVE_SESSION' | string
  message: string
  status?: number
}

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: ApiError }

export interface DesktopApiGatewayApi {
  request: <T = unknown>(payload: ApiRequestPayload) => Promise<ApiResult<T>>
}

/**
 * Session 失效广播 (Phase 2-Impl-1)。
 * main 进程在以下情况向所有 renderer 广播:
 *   - 单飞 refresh 全部失败 → 强制清场 → 推 auth:session-expired
 *   - 用户禁用 / token 主动 revoke
 *
 * renderer 通过 window.api.onSessionExpired(cb) 订阅。
 * cb 内典型操作: authStore.onSessionExpired() + router.push('/login')
 */
export interface DesktopSessionApi {
  onSessionExpired: (cb: () => void) => void
}

/**
 * Chat SSE Streaming API (Phase 2-Impl-3B + Phase 3-A reliability).
 *
 * 流程:
 *   renderer.startStream({ message, session_id }) → streamId
 *   main → renderer: push chunk / end / error 携带 StreamContext (streamId + sessionId)
 *   renderer 监听 onChunk / onEnd / onError
 *
 * Phase 3-A: StreamContext 用于 renderer 端校验 session 隔离
 *   (用户切换 session 时, stale stream 的 chunk 被 ignore)
 *
 * 安全:
 *   - 不暴露 ipcRenderer 实例
 *   - 不暴露 channel 名 (renderer 只能走白名单方法)
 *   - onChunk / onEnd / onError 返回 unsubscribe 闭包
 */
export interface DesktopChatStreamApi {
  startStream: (payload: import('./chat-types').ChatStreamRequest) => Promise<string>
  cancelStream: (streamId: string) => Promise<{ ok: true } | { ok: false; error: string }>
  onChunk: (
    cb: (
      ctx: import('./chat-types').StreamContext,
      event: import('./chat-types').StreamEvent
    ) => void
  ) => () => void
  onEnd: (
    cb: (
      ctx: import('./chat-types').StreamContext,
      payload: import('./chat-types').StreamEndPayload
    ) => void
  ) => () => void
  onError: (
    cb: (
      ctx: import('./chat-types').StreamContext,
      error: import('./chat-types').StreamErrorPayload
    ) => void
  ) => () => void
}

/**
 * Phase 6-A2: Model Provider SecretStore API.
 *
 * Renderer ONLY sees provider ids and booleans — raw API keys NEVER leave the main process.
 * Renderer never sees ciphertext either (Phase 6-A2: ciphertext only inside main).
 *
 * Workflow (Phase 6-A4 Settings UI):
 *   1. user enters API key in Settings panel
 *   2. renderer calls saveKey(providerId, key)  → key dispatched to main via IPC
 *   3. main: safeStorage.encryptString(key) + electron-store.set(prefix + id, cipherB64)
 *   4. renderer asks keyExists(providerId) to decide whether to render "configured"
 *   5. renderer asks listProviders() to populate provider list dropdown
 */
export interface ModelListProvidersResult {
  providerIds: string[]
}

export interface ModelSaveKeyResult {
  ok: true
  exists: boolean
}

export interface ModelDeleteKeyResult {
  ok: true
  exists: boolean
}

export interface ModelKeyExistsResult {
  exists: boolean
}

/**
 * Phase 6-A4: non-secret provider config (endpoint, defaultModel, displayName).
 * Renderer NEVER sees API keys via these channels.
 */
/**
 * Phase 6-C1: research capability tags attached to a model profile.
 * Mirrors ModelResearchProfile in './model/research-capability'.
 */
export type ResearchCapability =
  | 'chat'
  | 'coding'
  | 'math'
  | 'matlab'
  | 'python'
  | 'cfd'
  | 'literature'
  | 'paper-writing'
  | 'image-analysis'
  | 'data-analysis'

export interface ModelResearchProfile {
  providerId: string
  model: string
  capabilities: ResearchCapability[]
  maxContext?: number
  strengths?: string[]
  limitations?: string[]
}

export interface ModelProviderConfig {
  providerId: string
  type: 'cloud' | 'local' | 'openai-compatible'
  endpoint?: string
  defaultModel: string
  displayName: string
  capabilities: string[]
  updatedAt: number
  /**
   * Phase 6-C1: optional research capability profile.
   * Renderer reads it for capability chips / task matching.
   */
  researchProfile?: ModelResearchProfile
}

export interface ModelListConfigsResult {
  configs: ModelProviderConfig[]
  /**
   * Parallel array aligned with configs[i].providerId — true iff the
   * providerId has an API key stored in SecretStore. Renderer uses this
   * to render "needs key" / "configured" UI state.
   */
  hasKey: boolean[]
}

export interface ModelSaveConfigResult {
  ok: true
  exists: boolean
}

export interface ModelDeleteConfigResult {
  ok: true
  exists: boolean
}

export interface ModelTestProviderResult {
  ok: boolean
  latencyMs?: number
  error?: string
}

/**
 * Phase 6-C3: capability-driven task routing result.
 * Renderer-visible (NEVER contains apiKey).
 */
export type ResearchCapabilityString =
  | 'chat'
  | 'coding'
  | 'math'
  | 'matlab'
  | 'python'
  | 'cfd'
  | 'literature'
  | 'paper-writing'
  | 'image-analysis'
  | 'data-analysis'

export interface ModelRouteTaskDecision {
  providerId: string
  model: string
  source: 'capability-match' | 'active-provider' | 'no-match'
  reason: string
  capabilities: ResearchCapabilityString[]
}

export interface ModelRouteTaskResult {
  decision: ModelRouteTaskDecision | null
  route: 'task-routed' | 'active-fallback' | 'no-route'
  reason: string
}

export interface DesktopModelApi {
  /**
   * List providerIds that have a key stored. Returns IDs only — never keys.
   * Returns array of strings (empty if none configured).
   */
  listProviders: () => Promise<ModelListProvidersResult>

  /**
   * Save / overwrite API key for a providerId.
   * Renderer passes the plaintext key once; main encrypts via safeStorage and persists.
   * Returns { ok: true, exists: true } on success — the key itself is NEVER echoed back.
   * @throws Error if providerId invalid, key empty, or safeStorage unavailable.
   */
  saveKey: (providerId: string, apiKey: string) => Promise<ModelSaveKeyResult>

  /**
   * Delete a stored key. Idempotent — missing keys return { ok: true, exists: false }.
   * @throws Error if providerId invalid.
   */
  deleteKey: (providerId: string) => Promise<ModelDeleteKeyResult>

  /**
   * Existence check — returns boolean. NEVER returns the key itself.
   */
  keyExists: (providerId: string) => Promise<ModelKeyExistsResult>

  /**
   * Phase 6-A4: list all provider configs (non-secret metadata).
   * `hasKey[i]` tells whether provider configs[i].providerId has a key.
   */
  listConfigs: () => Promise<ModelListConfigsResult>

  /**
   * Phase 6-A4: save non-secret provider config (endpoint, defaultModel,
   * displayName, capabilities, type). Does NOT touch the API key.
   * @throws Error if providerId invalid or config shape invalid.
   */
  saveConfig: (
    providerId: string,
    config: Omit<ModelProviderConfig, 'providerId' | 'updatedAt'>
  ) => Promise<ModelSaveConfigResult>

  /**
   * Phase 6-A4: delete a provider config (idempotent).
   * Does NOT delete the API key — call deleteKey separately if needed.
   */
  deleteConfig: (providerId: string) => Promise<ModelDeleteConfigResult>

  /**
   * Phase 6-A4: test provider connectivity (Phase 6-A3 ping via registry).
   * Tests endpoint reachability, NOT key validity (Phase 6-A4 strict:
   * ping does not require a real key; Phase 6-A5 wiring swaps in real key).
   */
  testProvider: (providerId: string) => Promise<ModelTestProviderResult>

  /**
   * Phase 6-C3: capability-driven task routing.
   * Main process runs capability-router (Phase 6-C2) and returns a
   * non-secret decision (providerId / model / reason / capabilities).
   * NO apiKey is included in any field.
   */
  routeTask: (profile: {
    taskType: string
    requiredCapabilities: string[]
    optionalCapabilities?: string[]
    priority?: number
  } | null) => Promise<ModelRouteTaskResult>
}

export interface ApplicationInfo {
  name: string
  version: string
  buildNumber: string
  commitHash: string
  buildTime: string
  channel: 'stable' | 'beta' | 'dev'
  environment: 'production' | 'development'
}

export interface UpdateCheckResult {
  available: boolean
  currentVersion: string
  message?: string
  latestVersion?: string
}

export interface DesktopAppApi {
  getConfig: () => Promise<unknown>
  getStatus: () => Promise<unknown>
  getInfo: () => Promise<ApplicationInfo>
  checkUpdate: () => Promise<UpdateCheckResult>
  downloadUpdate: () => Promise<{ ok: true; progress?: number }>
  installUpdate: () => Promise<{ ok: true }>
  getCurrentVersion: () => Promise<string>
  restart: () => Promise<{ ok: true }>
  quit: () => Promise<{ ok: true }>
  persistenceSave: (namespace: string, key: string, value: unknown) => Promise<{ ok: true }>
  persistenceLoad: (namespace: string, key: string) => Promise<unknown>
  persistenceRemove: (namespace: string, key: string) => Promise<{ ok: true }>
  logWrite: (level: string, module: string, message: string, metadata?: unknown) => Promise<{ ok: true }>
  logTail: (lines?: number) => Promise<Array<{ timestamp: string; level: string; module: string; message: string; metadata?: unknown }>>
}

export interface DatabaseQueryResult<T = unknown> {
  rows: T[]
  changes: number
}

export interface DesktopDatabaseApi {
  status: () => Promise<{ open: boolean; path: string; version: number }>
  query: <T = unknown>(sql: string, params?: unknown[]) => Promise<DatabaseQueryResult<T>>
  insert: <T = unknown>(table: string, data: Record<string, unknown>) => Promise<T>
  update: <T = unknown>(table: string, id: string | number, patch: Record<string, unknown>) => Promise<T | null>
  delete: (table: string, id: string | number) => Promise<{ deleted: boolean }>
}

export interface DesktopDataEngineApi {
  sampleCreate: (sample: Record<string, unknown>) => Promise<Record<string, unknown>>
  sampleListByExperiment: (experimentId: string) => Promise<Record<string, unknown>[]>
  sampleDelete: (sampleId: string) => Promise<{ deleted: boolean }>
  analysisCreate: (result: Record<string, unknown>) => Promise<Record<string, unknown>>
  analysisListByExperiment: (experimentId: string) => Promise<Record<string, unknown>[]>
  analysisAddModelParam: (param: Record<string, unknown>) => Promise<Record<string, unknown>>
  analysisListModelParams: (analysisId: string) => Promise<Record<string, unknown>[]>
  figureCreate: (figure: Record<string, unknown>) => Promise<Record<string, unknown>>
  figureListByExperiment: (experimentId: string) => Promise<Record<string, unknown>[]>
  figureListByAnalysis: (analysisId: string) => Promise<Record<string, unknown>[]>
}

export interface DesktopAnalysisApi {
  runKinetic: (experimentId: string, model: 'first-order' | 'zero-order' | 'pseudo-second-order', metric: string) => Promise<string>
  runRegression: (experimentId: string, xMetric: string, yMetric: string, degree: 1 | 2 | 3 | 4) => Promise<string>
  runCorrelation: (experimentId: string, xMetric: string, yMetric: string) => Promise<string>
  runCurve: (experimentId: string, family: 'exponential-decay' | 'logarithmic' | 'power-law' | 'gaussian', metric: string) => Promise<string>
  listByExperiment: (experimentId: string) => Promise<Array<{
    id: string; runType: string; status: string | null; model: string | null
    startedAt: number; finishedAt: number | null; summary: string | null; confidence: number | null
    parameters: Array<{ name: string; value: number; unit: string | null; stdError: number | null; pValue: number | null }>
  }>>
  statistics: (experimentId: string, metric: string) => Promise<{
    summary: { metric: string; count: number; missingRate: number; mean: number | null; std: number | null; median: number | null; min: number | null; max: number | null; p25: number | null; p75: number | null; outliers: number; interpretation: string }
    n: number
  }>
}

export interface DesktopApi extends DesktopPingApi {
  auth: DesktopAuthApi
  api: DesktopApiGatewayApi
  session: DesktopSessionApi
  chat: DesktopChatStreamApi
  model: DesktopModelApi
  app: DesktopAppApi
  database: DesktopDatabaseApi
  dataEngine: DesktopDataEngineApi
  analysis: DesktopAnalysisApi
  // Phase 2+ expand here (task / knowledge / meeting / ...)
}

// Marker module — runtime unused; only for namespace clarity.
export const PRELOAD_API_NAMESPACE = 'microbubble-desktop' as const
