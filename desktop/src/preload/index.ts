import { contextBridge, ipcRenderer } from 'electron'
import { IPC_CHANNELS } from '@shared/ipc-types'
import type {
  DesktopApi,
  DesktopAuthApi,
  DesktopApiGatewayApi,
  DesktopSessionApi,
  PingRequest,
  PongResponse
} from '@shared/preload-api'
import type { LoginRequest } from '@shared/auth-types'
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
 *    例外: ipcRenderer.on 只能用于 main→renderer broadcast (Phase 2-Impl-1+ session:expired)
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
  // 仅监听 session:expired 唯一 broadcast channel，不暴露任何通用 on(event)
  onSessionExpired: (cb: () => void) => {
    const listener = (): void => {
      try {
        cb()
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error('[preload] session-expired listener threw:', err)
      }
    }
    ipcRenderer.on(IPC_CHANNELS.AUTH_SESSION_EXPIRED, listener)
  }
}

const api: DesktopApi = {
  ping: (payload?: PingRequest): Promise<PongResponse> =>
    ipcRenderer.invoke(IPC_CHANNELS.PING, payload ?? {}),
  auth: authApi,
  api: apiGateway,
  session: sessionApi
}

try {
  contextBridge.exposeInMainWorld('api', api)
} catch (error) {
  // eslint-disable-next-line no-console
  console.error('[preload] Failed to expose api via contextBridge:', error)
}
