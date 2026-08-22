import { ipcMain } from 'electron'
import { IPC_CHANNELS } from '@shared/ipc-types'
import type { PingRequest, PongResponse } from '@shared/preload-api'
import type { LoginRequest } from '@shared/auth-types'
import type { ApiRequestPayload, ApiResult } from '@shared/preload-api'
import type { ChatStreamRequest } from '@shared/chat-types'
import { authService } from './services/auth.service'
import { apiService } from './services/api/api.service'
import {
  startChatStream,
  cancelChatStream
} from './services/chat/chat-stream.service'
import { registerModelIpcHandlers, setProviderPingFn } from './services/model-provider/model-ipc'
import { getProvider } from './services/model-provider/registry'

/**
 * 主进程 IPC 注册入口。
 *
 * 严格规则（详见 docs/desktop-conversion/security.md §IPC）：
 * 1. 只通过 ipcMain.handle 注册 channel
 * 2. preload 通过 contextBridge 暴露的 invoke/on 是唯一 IPC 入口
 * 3. 不在 main 进程加载任何用户态数据（token 等）到全局变量
 *    (Phase 1 引入 auth 服务后允许 inline token, 但只在 main 进程内访问)
 */
export function registerIpcHandlers(): void {
  // ---------- Phase 0 ----------
  ipcMain.handle(
    IPC_CHANNELS.PING,
    async (_event, payload: PingRequest): Promise<PongResponse> => {
      return {
        success: true,
        message: 'pong',
        timestamp: Date.now(),
        ...(payload?.message ? { echo: payload.message } : {})
      }
    }
  )

  // ---------- Phase 1-Impl-1: auth lifecycle ----------
  ipcMain.handle(
    IPC_CHANNELS.AUTH_LOGIN,
    async (_event, payload: LoginRequest) => {
      return authService.login(payload)
    }
  )

  ipcMain.handle(IPC_CHANNELS.AUTH_LOGOUT, async () => {
    return authService.logout()
  })

  ipcMain.handle(IPC_CHANNELS.AUTH_RESTORE, async () => {
    return authService.restore()
  })

  ipcMain.handle(IPC_CHANNELS.AUTH_GET_BACKEND_URL, async () => {
    return authService.getBackendUrl()
  })

  // ---------- Phase 1-Impl-2: API gateway ----------
  // 业务模块调用后端鉴权 endpoint 的统一入口。
  // main: api.service 自动注入 Bearer + 单飞 refresh。
  // renderer: window.api.api.request({ method, path, body? })
  ipcMain.handle(
    IPC_CHANNELS.API_REQUEST,
    async (_event, payload: ApiRequestPayload): Promise<ApiResult<unknown>> => {
      return apiService.request(payload)
    }
  )

  // ---------- Phase 2-Impl-3B: Chat SSE Streaming ----------
  // Renderer 启动一次流: 立刻拿到 streamId, 后续 chunk/end/error 通过
  // webContents.send broadcast.
  ipcMain.handle(
    IPC_CHANNELS.CHAT_STREAM_START,
    async (_event, payload: ChatStreamRequest): Promise<string> => {
      return startChatStream(payload)
    }
  )

  ipcMain.handle(
    IPC_CHANNELS.CHAT_STREAM_CANCEL,
    async (_event, streamId: string) => cancelChatStream(streamId)
  )

  // ---------- Phase 6-A2: Model SecretStore IPC ----------
  // Returns ONLY provider ids / booleans — raw API keys NEVER leave main process.
  // Phase 6-A4: also wires non-secret config + connectivity test.
  setProviderPingFn(async (providerId, cfg) => {
    // Phase 6-A4: ping uses a fake apiKey (test endpoint reachability, NOT key validity).
    // Phase 6-A5 wiring will swap to SecretStore.get(providerId).
    const provider = getProvider(providerId, cfg)
    if (!provider) return { ok: false, error: `no factory registered for providerId '${providerId}' (Phase 6-A4)` }
    return provider.ping(cfg)
  })
  registerModelIpcHandlers()
}
