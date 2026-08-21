import { contextBridge, ipcRenderer } from 'electron'
import { IPC_CHANNELS } from '@shared/ipc-types'
import type {
  DesktopApi,
  DesktopAuthApi,
  DesktopApiGatewayApi,
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
 * 5. 不暴露 ipcRenderer.send —— 全部走 ipcRenderer.invoke（request/response）
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

// Local helper type: api.service 返回 ApiResult<T>, 跨 IPC 同样形状
type ApiResultLike<T> =
  | { ok: true; data: T }
  | { ok: false; error: { code: string; message: string; status?: number } }

const api: DesktopApi = {
  ping: (payload?: PingRequest): Promise<PongResponse> =>
    ipcRenderer.invoke(IPC_CHANNELS.PING, payload ?? {}),
  auth: authApi,
  api: apiGateway
}

try {
  contextBridge.exposeInMainWorld('api', api)
} catch (error) {
  // eslint-disable-next-line no-console
  console.error('[preload] Failed to expose api via contextBridge:', error)
}
