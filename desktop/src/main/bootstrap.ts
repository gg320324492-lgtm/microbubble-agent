// Main Process Bootstrap —— 应用启动时序。
//
// 职责:
// 1. 初始化 storage service (electron-store 落盘)
// 2. 尝试异步恢复 session (vault 中有 refresh_token 则 /auth/refresh + /auth/me)
// 3. 返回 bootstrap 状态供 main/index 决定渲染初始 route 等
//
// 设计原则:
// - 不阻塞主进程启动 (storage 是同步 IO, 在 Electron 启动期由 store 构造时一次性完成)
// - restore 是 async 但不阻塞窗口创建 —— 窗口内 AuthGuard.beforeEach 会等 restore
// - 任何初始化异常都吞掉 + 记 console.error, 不阻塞启动
//
// 调用方: main/index.ts → await bootstrap() → createWindow → registerIpcHandlers

import { getStorePath } from './services/storage.service'
import { authService } from './services/auth.service'
import { isVaultAvailable } from './services/token-vault'

export interface BootstrapResult {
  storePath: string
  vaultAvailable: boolean
  sessionRestored: boolean
  startedAt: string
}

/**
 * 主进程启动初始化。
 * 返回 store path + vault 状态 + session 是否成功恢复。
 */
export async function bootstrap(): Promise<BootstrapResult> {
  const startedAt = new Date().toISOString()
  const storePath = getStorePath()
  const vaultAvailable = isVaultAvailable()

  // 尝试恢复 session —— 不阻塞 (auth guard 在 renderer 端另起一次会等)
  let sessionRestored = false
  if (vaultAvailable) {
    try {
      const r = await authService.restore()
      sessionRestored = r !== null
    } catch (err) {
      // 主进程 init 阶段吞错 —— 启动不应被 restore 失败阻塞
      // eslint-disable-next-line no-console
      console.warn('[bootstrap] auth.restore failed during init:', err)
      sessionRestored = false
    }
  }

  // eslint-disable-next-line no-console
  console.info(
    `[bootstrap] started at ${startedAt}, store=${storePath}, vault=${vaultAvailable}, session=${sessionRestored}`
  )

  return {
    storePath,
    vaultAvailable,
    sessionRestored,
    startedAt
  }
}
