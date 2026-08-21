import { contextBridge, ipcRenderer } from 'electron'
import { IPC_CHANNELS } from '@shared/ipc-types'
import type {
  DesktopApi,
  DesktopAuthApi,
  DesktopApiGatewayApi,
  DesktopSessionApi,
  DesktopChatStreamApi,
  PingRequest,
  PongResponse
} from '@shared/preload-api'
import type { LoginRequest } from '@shared/auth-types'
import type {
  ChatStreamRequest,
  StreamEvent,
  StreamEndPayload,
  StreamErrorPayload
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
 *    例外: ipcRenderer.on 只能用于 main→renderer broadcast (Phase 2-Impl-1+ session:expired, Phase 2-Impl-3B+ chat:stream-chunk/end/error)
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

// ============ Chat SSE Streaming (Phase 2-Impl-3B) ============
// 内部 listener 注册 (load 时一次性注册)
const chunkListeners = new Set<(streamId: string, event: StreamEvent) => void>()
const endListeners = new Set<(streamId: string, payload: StreamEndPayload) => void>()
const errorListeners = new Set<(streamId: string, error: StreamErrorPayload) => void>()

function safeNotify<T>(set: Set<(streamId: string, p: T) => void>, args: [string, T]): void {
  for (const cb of set) {
    try {
      cb(args[0], args[1])
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('[preload] stream listener threw:', err)
    }
  }
}

ipcRenderer.on(IPC_CHANNELS.CHAT_STREAM_CHUNK, (_e, streamId: string, event: StreamEvent) => {
  safeNotify(chunkListeners, [streamId, event])
})
ipcRenderer.on(IPC_CHANNELS.CHAT_STREAM_END, (_e, streamId: string, payload: StreamEndPayload) => {
  safeNotify(endListeners, [streamId, payload])
})
ipcRenderer.on(IPC_CHANNELS.CHAT_STREAM_ERROR, (_e, streamId: string, error: StreamErrorPayload) => {
  safeNotify(errorListeners, [streamId, error])
})

function subscribe<T>(set: Set<(streamId: string, p: T) => void>, cb: (streamId: string, p: T) => void): () => void {
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

const api: DesktopApi = {
  ping: (payload?: PingRequest): Promise<PongResponse> =>
    ipcRenderer.invoke(IPC_CHANNELS.PING, payload ?? {}),
  auth: authApi,
  api: apiGateway,
  session: sessionApi,
  chat: chatStreamApi
}

try {
  contextBridge.exposeInMainWorld('api', api)
} catch (error) {
  // eslint-disable-next-line no-console
  console.error('[preload] Failed to expose api via contextBridge:', error)
}
