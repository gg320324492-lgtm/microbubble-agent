// IPC 注册 — 白名单 channel 与 shared/ipc-channels.ts 一一对应，测试有一致性校验。
// 会话 token 持久化走 safeStorage（Win DPAPI 绑定本机），解密失败即清除重来，不阻塞（E-3 铁律）。
import { app, ipcMain, BrowserWindow, safeStorage } from 'electron'
import { existsSync, readFileSync, unlinkSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { IPC } from '@shared/ipc-channels'
import { APP_NAME, APP_VERSION } from '@shared/constants'
import type { AppInfo, AuthSession, IpcResult } from '@shared/types'
import type { SqlDatabase } from './db/adapters'
import { AuthService } from './services/auth.service'
import { SettingsService } from './services/settings.service'

const ok = <T>(data: T): IpcResult<T> => ({ ok: true, data })
const fail = (code: string, message: string): IpcResult<never> => ({ ok: false, error: { code, message } })

function tryRun<T>(fn: () => T): IpcResult<T> {
  try {
    return ok(fn())
  } catch (err) {
    const e = err as Error & { code?: string }
    return fail(e.code ?? 'ERROR', e.message)
  }
}

/** safeStorage 加密的会话 token 文件 */
function makeFilePersistence(file: string) {
  return {
    persist(token: string): void {
      if (!safeStorage.isEncryptionAvailable()) return // 加密不可用则放弃跨重启恢复，重启后重新登录
      writeFileSync(file, safeStorage.encryptString(token).toString('base64'), 'utf8')
    },
    load(): string | null {
      try {
        if (!existsSync(file) || !safeStorage.isEncryptionAvailable()) return null
        return safeStorage.decryptString(Buffer.from(readFileSync(file, 'utf8'), 'base64'))
      } catch {
        try {
          unlinkSync(file)
        } catch {
          /* 忽略 */
        }
        return null
      }
    },
    clear(): void {
      try {
        if (existsSync(file)) unlinkSync(file)
      } catch {
        /* 忽略 */
      }
    }
  }
}

export function registerIpc(db: SqlDatabase, dbPath: string, getWindow: () => BrowserWindow | null): void {
  const auth = new AuthService(db, makeFilePersistence(join(dbPath, '..', 'session-token.enc')))
  const settings = new SettingsService(db)

  // 启动即尝试恢复上次会话（有持久化 token 且未过期则免登录）
  auth.restore()

  ipcMain.handle(IPC.APP_INFO, (): IpcResult<AppInfo> =>
    tryRun(() => ({ version: APP_VERSION, platform: process.platform, dbPath, appName: APP_NAME }))
  )

  ipcMain.handle(IPC.AUTH_STATUS, (): IpcResult<{ userCount: number }> => tryRun(() => ({ userCount: auth.getUserCount() })))

  ipcMain.handle(IPC.AUTH_REGISTER_ADMIN, (_e, p): IpcResult<AuthSession> =>
    tryRun(() =>
      auth.registerFirstAdmin({
        username: String(p?.username ?? ''),
        displayName: p?.displayName ? String(p.displayName) : undefined,
        password: String(p?.password ?? '')
      })
    )
  )

  ipcMain.handle(IPC.AUTH_LOGIN, (_e, p): IpcResult<AuthSession> =>
    tryRun(() => auth.login(String(p?.username ?? ''), String(p?.password ?? '')))
  )

  ipcMain.handle(IPC.AUTH_RESTORE, (): IpcResult<AuthSession | null> => tryRun(() => auth.restore()))

  ipcMain.handle(IPC.AUTH_LOGOUT, (): IpcResult<boolean> => tryRun(() => auth.logout()))

  ipcMain.handle(IPC.SETTINGS_GET, (_e, p): IpcResult<unknown> =>
    tryRun(() => {
      const user = auth.requireUser()
      return settings.get(String(p?.key ?? ''), user.id)
    })
  )

  ipcMain.handle(IPC.SETTINGS_SET, (_e, p): IpcResult<null> =>
    tryRun(() => {
      const user = auth.requireUser()
      settings.set(String(p?.key ?? ''), p?.value ?? null, user.id)
      return null
    })
  )

  ipcMain.handle(IPC.WINDOW_MINIMIZE, (): IpcResult<null> => {
    getWindow()?.minimize()
    return ok(null)
  })
  ipcMain.handle(IPC.WINDOW_TOGGLE_MAXIMIZE, (): IpcResult<null> => {
    const win = getWindow()
    if (win) {
      if (win.isMaximized()) win.unmaximize()
      else win.maximize()
    }
    return ok(null)
  })
  ipcMain.handle(IPC.WINDOW_CLOSE, (): IpcResult<null> => {
    getWindow()?.close()
    return ok(null)
  })

  void app // 本模块暂未直接使用 app，显式置空引用保持 import 语义清晰
}
