import { contextBridge, ipcRenderer } from 'electron'
import { IPC_CHANNELS } from '@shared/ipc-types'
import type { DesktopApi, PingRequest, PongResponse } from '@shared/preload-api'

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
 */
const api: DesktopApi = {
  ping: (payload?: PingRequest): Promise<PongResponse> =>
    ipcRenderer.invoke(IPC_CHANNELS.PING, payload ?? {})
}

try {
  contextBridge.exposeInMainWorld('api', api)
} catch (error) {
  // eslint-disable-next-line no-console
  console.error('[preload] Failed to expose api via contextBridge:', error)
}
