// 暴露给渲染进程的桌面 API 类型契约。
//
// 单一源：preload 和 renderer 都从这里 import，避免 tsconfig 跨项目。
//
// 主进程在 src/preload/index.ts 实际注册 handler，类型层面在本文件统一冻结。

export interface PingRequest {
  message?: string
}

export interface PongResponse {
  success: boolean
  message: 'pong'
  timestamp: number
  echo?: string
}

/**
 * Renderer 通过 window.api 拿到的全部方法。
 * 任何 channel 新增 / 重命名 / 删除，必须同步修改：
 *   - src/preload/index.ts  (实际实现 + contextBridge 暴露)
 *   - src/main/ipc.ts       (ipcMain.handle 注册)
 *   - 本文件                  (类型形状)
 */
export interface DesktopApi {
  ping: (payload?: PingRequest) => Promise<PongResponse>
  // Phase 1+ expand here, e.g.:
  // auth: { login(...): Promise<LoginResponse>, logout(): Promise<void>, ... }
}
