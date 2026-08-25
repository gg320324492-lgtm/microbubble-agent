import { contextBridge, ipcRenderer } from 'electron'
import { IPC_CHANNELS } from '@shared/ipc-types'
import type {
  DesktopApi,
  DesktopAuthApi,
  DesktopApiGatewayApi,
  DesktopSessionApi,
  DesktopChatStreamApi,
  DesktopModelApi,
  PingRequest,
  PongResponse
} from '@shared/preload-api'
import type { LoginRequest } from '@shared/auth-types'
import type {
  ChatStreamRequest,
  StreamEvent,
  StreamEndPayload,
  StreamErrorPayload,
  StreamContext
} from '@shared/chat-types'
import type { ApiRequestPayload } from '@shared/preload-api'

/**
 * preload 是 Electron 唯一可在 sandbox 环境访问 ipcRenderer 的层。
 * 仅通过 contextBridge 暴露白名单 API 给 renderer。
 *
 * 严格规则（详见 docs/desktop-conversion/security.md §IPC）：
 * 1. contextIsolation: true —— renderer 拿到的 window.api 是被代理的 snapshot
 * 2. nodeIntegration: false —— renderer 完全访问不到 Node API
 * 3. sandbox: true —— preload 之外所有进程沙箱化
 * 4. 不暴露 ipcRenderer 给 renderer 任何形式
 * 5. 不暴露 ipcRenderer.send —— 全部走 ipcRenderer.invoke（request/response）；
 *    例外: ipcRenderer.on 只能用于 main→renderer broadcast
 *    仍不暴露 ipcRenderer 实例，封装为专门 typed event handler onXxx(cb)
 * 6. 所有鉴权业务请求必须经 window.api.api.request (统一 Bearer + refresh)
 *    禁止 renderer 直接 axios 调鉴权 endpoint
 */

const authApi: DesktopAuthApi = {
  login: (payload: LoginRequest) => ipcRenderer.invoke(IPC_CHANNELS.AUTH_LOGIN, payload),
  logout: () => ipcRenderer.invoke(IPC_CHANNELS.AUTH_LOGOUT),
  restore: () => ipcRenderer.invoke(IPC_CHANNELS.AUTH_RESTORE),
  getBackendUrl: () => ipcRenderer.invoke(IPC_CHANNELS.AUTH_GET_BACKEND_URL)
}

const apiGateway: DesktopApiGatewayApi = {
  request: <T = unknown>(payload: ApiRequestPayload) =>
    ipcRenderer.invoke(IPC_CHANNELS.API_REQUEST, payload) as Promise<ApiResultLike<T>>
}

type ApiResultLike<T> =
  | { ok: true; data: T }
  | { ok: false; error: { code: string; message: string; status?: number } }

const sessionApi: DesktopSessionApi = {
  onSessionExpired: (cb: () => void) => {
    const listener = (): void => {
      try { cb() } catch (err) {
        // eslint-disable-next-line no-console
        console.error('[preload] session-expired listener threw:', err)
      }
    }
    ipcRenderer.on(IPC_CHANNELS.AUTH_SESSION_EXPIRED, listener)
  }
}

// ============ Chat SSE Streaming (Phase 3-A: StreamContext carried) ============
const chunkListeners = new Set<(ctx: StreamContext, event: StreamEvent) => void>()
const endListeners = new Set<(ctx: StreamContext, payload: StreamEndPayload) => void>()
const errorListeners = new Set<(ctx: StreamContext, error: StreamErrorPayload) => void>()

function safeNotify<T>(set: Set<(ctx: StreamContext, p: T) => void>, ctx: StreamContext, payload: T): void {
  for (const cb of set) {
    try { cb(ctx, payload) }
    catch (err) {
      // eslint-disable-next-line no-console
      console.error('[preload] stream listener threw:', err)
    }
  }
}

ipcRenderer.on(IPC_CHANNELS.CHAT_STREAM_CHUNK, (_e, ctx: StreamContext, event: StreamEvent) => {
  safeNotify(chunkListeners, ctx, event)
})
ipcRenderer.on(IPC_CHANNELS.CHAT_STREAM_END, (_e, ctx: StreamContext, payload: StreamEndPayload) => {
  safeNotify(endListeners, ctx, payload)
})
ipcRenderer.on(IPC_CHANNELS.CHAT_STREAM_ERROR, (_e, ctx: StreamContext, error: StreamErrorPayload) => {
  safeNotify(errorListeners, ctx, error)
})

function subscribe<T>(set: Set<(ctx: StreamContext, p: T) => void>, cb: (ctx: StreamContext, p: T) => void): () => void {
  set.add(cb)
  return () => set.delete(cb)
}

const chatStreamApi: DesktopChatStreamApi = {
  startStream: (payload: ChatStreamRequest): Promise<string> =>
    ipcRenderer.invoke(IPC_CHANNELS.CHAT_STREAM_START, payload) as Promise<string>,
  cancelStream: (streamId: string) =>
    ipcRenderer.invoke(IPC_CHANNELS.CHAT_STREAM_CANCEL, streamId) as Promise<
      { ok: true } | { ok: false; error: string }
    >,
  onChunk: (cb) => subscribe(chunkListeners, cb),
  onEnd: (cb) => subscribe(endListeners, cb),
  onError: (cb) => subscribe(errorListeners, cb)
}

// ============ Phase 6-A2: Model SecretStore ============
// Renderer ONLY sees provider ids + booleans. Raw API keys NEVER traverse this bridge.
const modelApi: DesktopModelApi = {
  listProviders: () =>
    ipcRenderer.invoke(IPC_CHANNELS.MODEL_LIST_PROVIDERS) as Promise<{
      providerIds: string[]
    }>,
  saveKey: (providerId, apiKey) =>
    ipcRenderer.invoke(
      IPC_CHANNELS.MODEL_SAVE_KEY,
      providerId,
      apiKey
    ) as Promise<{ ok: true; exists: boolean }>,
  deleteKey: (providerId) =>
    ipcRenderer.invoke(
      IPC_CHANNELS.MODEL_DELETE_KEY,
      providerId
    ) as Promise<{ ok: true; exists: boolean }>,
  keyExists: (providerId) =>
    ipcRenderer.invoke(
      IPC_CHANNELS.MODEL_KEY_EXISTS,
      providerId
    ) as Promise<{ exists: boolean }>,
  // ============ Phase 6-A4: non-secret config + connectivity ============
  listConfigs: () =>
    ipcRenderer.invoke(IPC_CHANNELS.MODEL_LIST_CONFIGS) as Promise<{
      configs: Array<{
        providerId: string
        type: 'cloud' | 'local' | 'openai-compatible'
        endpoint?: string
        defaultModel: string
        displayName: string
        capabilities: string[]
        updatedAt: number
      }>
      hasKey: boolean[]
    }>,
  saveConfig: (providerId, config) =>
    ipcRenderer.invoke(
      IPC_CHANNELS.MODEL_SAVE_CONFIG,
      providerId,
      config
    ) as Promise<{ ok: true; exists: boolean }>,
  deleteConfig: (providerId) =>
    ipcRenderer.invoke(
      IPC_CHANNELS.MODEL_DELETE_CONFIG,
      providerId
    ) as Promise<{ ok: true; exists: boolean }>,
  testProvider: (providerId) =>
    ipcRenderer.invoke(
      IPC_CHANNELS.MODEL_TEST_PROVIDER,
      providerId
    ) as Promise<{ ok: boolean; latencyMs?: number; error?: string }>,
  // ============ Phase 6-C3: capability-driven task routing ============
  routeTask: (profile) =>
    ipcRenderer.invoke(
      IPC_CHANNELS.MODEL_ROUTE_TASK,
      profile
    ) as Promise<{
      decision: {
        providerId: string
        model: string
        source: 'capability-match' | 'active-provider' | 'no-match'
        reason: string
        capabilities: Array<'chat' | 'coding' | 'math' | 'matlab' | 'python' | 'cfd' | 'literature' | 'paper-writing' | 'image-analysis' | 'data-analysis'>
      } | null
      route: 'task-routed' | 'active-fallback' | 'no-route'
      reason: string
    }>
}

const api: DesktopApi = {
  ping: (payload?: PingRequest): Promise<PongResponse> =>
    ipcRenderer.invoke(IPC_CHANNELS.PING, payload ?? {}),
  auth: authApi,
  api: apiGateway,
  session: sessionApi,
  chat: chatStreamApi,
  model: modelApi,
  app: {
    getConfig: () => ipcRenderer.invoke('app:get-config') as Promise<unknown>,
    getStatus: () => ipcRenderer.invoke('app:get-status') as Promise<unknown>,
    getInfo: () => ipcRenderer.invoke('app:get-info') as Promise<{
      name: string; version: string; buildNumber: string; commitHash: string
      buildTime: string; channel: 'stable' | 'beta' | 'dev'
      environment: 'production' | 'development'
    }>,
    checkUpdate: () => ipcRenderer.invoke('app:check-update') as Promise<{ available: boolean; currentVersion: string; message?: string; latestVersion?: string }>,
    downloadUpdate: () => ipcRenderer.invoke('app:download-update') as Promise<{ ok: true; progress?: number }>,
    installUpdate: () => ipcRenderer.invoke('app:install-update') as Promise<{ ok: true }>,
    getCurrentVersion: () => ipcRenderer.invoke('app:get-current-version') as Promise<string>,
    restart: () => ipcRenderer.invoke('app:restart') as Promise<{ ok: true }>,
    quit: () => ipcRenderer.invoke('app:quit') as Promise<{ ok: true }>,
    persistenceSave: (namespace: string, key: string, value: unknown) =>
      ipcRenderer.invoke('persistence:save', { namespace, key, value }) as Promise<{ ok: true }>,
    persistenceLoad: (namespace: string, key: string) =>
      ipcRenderer.invoke('persistence:load', { namespace, key }) as Promise<unknown>,
    persistenceRemove: (namespace: string, key: string) =>
      ipcRenderer.invoke('persistence:remove', { namespace, key }) as Promise<{ ok: true }>,
    logWrite: (level: string, module: string, message: string, metadata?: unknown) =>
      ipcRenderer.invoke('logger:write', { level, module, message, metadata }) as Promise<{ ok: true }>,
    logTail: (lines: number = 100) =>
      ipcRenderer.invoke('logger:tail', { lines }) as Promise<Array<{ timestamp: string; level: string; module: string; message: string; metadata?: unknown }>>
  },
  database: {
    status: () => ipcRenderer.invoke('db:status') as Promise<{ open: boolean; path: string; version: number }>,
    query: <T = unknown>(sql: string, params?: unknown[]) =>
      ipcRenderer.invoke('db:query', { sql, params }) as Promise<{ rows: T[]; changes: number }>,
    insert: <T = unknown>(table: string, data: Record<string, unknown>) =>
      ipcRenderer.invoke('db:insert', { table, data }) as Promise<T>,
    update: <T = unknown>(table: string, id: string | number, patch: Record<string, unknown>) =>
      ipcRenderer.invoke('db:update', { table, id, patch }) as Promise<T | null>,
    delete: (table: string, id: string | number) =>
      ipcRenderer.invoke('db:delete', { table, id }) as Promise<{ deleted: boolean }>
  },
  dataEngine: {
    sampleCreate: (sample) => ipcRenderer.invoke('data:sample.create', sample) as Promise<Record<string, unknown>>,
    sampleListByExperiment: (experimentId) => ipcRenderer.invoke('data:sample.list', experimentId) as Promise<Record<string, unknown>[]>,
    sampleDelete: (sampleId) => ipcRenderer.invoke('data:sample.delete', sampleId) as Promise<{ deleted: boolean }>,
    analysisCreate: (result) => ipcRenderer.invoke('data:analysis.create', result) as Promise<Record<string, unknown>>,
    analysisListByExperiment: (experimentId) => ipcRenderer.invoke('data:analysis.list', experimentId) as Promise<Record<string, unknown>[]>,
    analysisAddModelParam: (param) => ipcRenderer.invoke('data:analysis.param', param) as Promise<Record<string, unknown>>,
    analysisListModelParams: (analysisId) => ipcRenderer.invoke('data:analysis.params', analysisId) as Promise<Record<string, unknown>[]>,
    figureCreate: (figure) => ipcRenderer.invoke('data:figure.create', figure) as Promise<Record<string, unknown>>,
    figureListByExperiment: (experimentId) => ipcRenderer.invoke('data:figure.listByExperiment', experimentId) as Promise<Record<string, unknown>[]>,
    figureListByAnalysis: (analysisId) => ipcRenderer.invoke('data:figure.listByAnalysis', analysisId) as Promise<Record<string, unknown>[]>
  },
  analysis: {
    runKinetic: (experimentId, model, metric) => ipcRenderer.invoke('analysis:run.kinetic', { experimentId, model, metric }) as Promise<string>,
    runRegression: (experimentId, xMetric, yMetric, degree) => ipcRenderer.invoke('analysis:run.regression', { experimentId, xMetric, yMetric, degree }) as Promise<string>,
    runCorrelation: (experimentId, xMetric, yMetric) => ipcRenderer.invoke('analysis:run.correlation', { experimentId, xMetric, yMetric }) as Promise<string>,
    runCurve: (experimentId, family, metric) => ipcRenderer.invoke('analysis:run.curve', { experimentId, family, metric }) as Promise<string>,
    listByExperiment: (experimentId) => ipcRenderer.invoke('analysis:list', experimentId) as Promise<Array<{ id: string; runType: string; status: string | null; model: string | null; startedAt: number; finishedAt: number | null; summary: string | null; confidence: number | null; parameters: Array<{ name: string; value: number; unit: string | null; stdError: number | null; pValue: number | null }> }>>,
    statistics: (experimentId, metric) => ipcRenderer.invoke('analysis:statistics', { experimentId, metric }) as Promise<{ summary: { metric: string; count: number; missingRate: number; mean: number | null; std: number | null; median: number | null; min: number | null; max: number | null; p25: number | null; p75: number | null; outliers: number; interpretation: string }; n: number }>
  }
}

try {
  contextBridge.exposeInMainWorld('api', api)
} catch (error) {
  // eslint-disable-next-line no-console
  console.error('[preload] Failed to expose api via contextBridge:', error)
}
