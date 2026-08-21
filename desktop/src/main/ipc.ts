import { ipcMain } from 'electron'
import { IPC_CHANNELS } from '@shared/ipc-types'
import type { PingRequest, PongResponse } from '@shared/preload-api'

/**
 * 主进程 IPC 注册入口。
 *
 * 严格规则（详见 docs/desktop-conversion/security.md §IPC）：
 * 1. 只通过 ipcMain.handle 注册 channel
 * 2. preload 通过 contextBridge 暴露的 invoke/on 是唯一 IPC 入口
 * 3. 不在 main 进程加载任何用户态数据（token 等）到全局变量
 */
export function registerIpcHandlers(): void {
  ipcMain.handle(
    IPC_CHANNELS.PING,
    async (_event, payload: PingRequest): Promise<PongResponse> => {
      // Phase 0 demo: 仅返回时间戳 + echo，证明三进程通道通
      return {
        success: true,
        message: 'pong',
        timestamp: Date.now(),
        ...(payload?.message ? { echo: payload.message } : {})
      }
    }
  )
}
