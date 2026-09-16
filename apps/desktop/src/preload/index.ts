// Preload — contextBridge 唯一通道（铁律 2）。sandbox 模式下只能 import electron。
// 所有方法白名单化，绝不暴露 ipcRenderer 本体。
import { contextBridge, ipcRenderer } from 'electron'
import { IPC } from '@shared/ipc-channels'
import type { AppInfo, AuthSession, ChatMessage, ChatSession, IpcResult, WorkspaceAuditEntry } from '@shared/types'

async function invoke<T>(channel: string, payload?: unknown): Promise<T> {
  const res = (await ipcRenderer.invoke(channel, payload)) as IpcResult<T>
  if (res && res.ok === false) throw new Error(res.error?.message ?? '调用失败')
  return res.data
}

const api = {
  app: {
    info: (): Promise<AppInfo> => invoke(IPC.APP_INFO)
  },
  auth: {
    status: (): Promise<{ userCount: number }> => invoke(IPC.AUTH_STATUS),
    registerAdmin: (p: { username: string; displayName?: string; password: string }): Promise<AuthSession> =>
      invoke(IPC.AUTH_REGISTER_ADMIN, p),
    login: (p: { username: string; password: string }): Promise<AuthSession> => invoke(IPC.AUTH_LOGIN, p),
    restore: (): Promise<AuthSession | null> => invoke(IPC.AUTH_RESTORE),
    logout: (): Promise<void> => invoke(IPC.AUTH_LOGOUT)
  },
  chat: {
    sessionsList: (): Promise<ChatSession[]> => invoke(IPC.CHAT_SESSIONS_LIST),
    sessionCreate: (title?: string): Promise<ChatSession> => invoke(IPC.CHAT_SESSION_CREATE, { title }),
    sessionRename: (id: string, title: string): Promise<void> => invoke(IPC.CHAT_SESSION_RENAME, { id, title }),
    sessionDelete: (id: string): Promise<void> => invoke(IPC.CHAT_SESSION_DELETE, { id }),
    messagesList: (sessionId: string): Promise<ChatMessage[]> => invoke(IPC.CHAT_MESSAGES_LIST, { sessionId }),
    send: (sessionId: string, content: string): Promise<{ userMessage: ChatMessage; assistantMessage: ChatMessage }> =>
      invoke(IPC.CHAT_SEND, { sessionId, content }),
    abort: (sessionId: string): Promise<void> => invoke(IPC.CHAT_ABORT, { sessionId }),
    confirmResolve: (sessionId: string, callId: string, approve: boolean): Promise<void> =>
      invoke(IPC.CHAT_CONFIRM_RESOLVE, { sessionId, callId, approve }),
    rollbackWrite: (sessionId: string, messageId: string, callId: string): Promise<{ path: string }> =>
      invoke(IPC.CHAT_ROLLBACK_WRITE, { sessionId, messageId, callId }),
    onStreamEvent: (cb: (e: unknown) => void): (() => void) => {
      const listener = (_e: unknown, payload: unknown): void => cb(payload as never)
      ipcRenderer.on(IPC.CHAT_STREAM_EVENT, listener as never)
      return () => ipcRenderer.removeListener(IPC.CHAT_STREAM_EVENT, listener as never)
    }
  },
  model: {
    list: () => invoke(IPC.MODEL_LIST),
    save: (p: unknown) => invoke(IPC.MODEL_SAVE, p),
    remove: (id: string) => invoke(IPC.MODEL_DELETE, { id }),
    setDefault: (id: string) => invoke(IPC.MODEL_SET_DEFAULT, { id }),
    test: (p: unknown) => invoke(IPC.MODEL_TEST, p)
  },
  settings: {
    get: (key: string): Promise<unknown> => invoke(IPC.SETTINGS_GET, { key }),
    set: (key: string, value: unknown): Promise<void> => invoke(IPC.SETTINGS_SET, { key, value })
  },
  workspace: {
    get: (): Promise<{ root: string | null }> => invoke(IPC.WORKSPACE_GET),
    set: (): Promise<string | null> => invoke(IPC.WORKSPACE_SET),
    clear: (): Promise<void> => invoke(IPC.WORKSPACE_CLEAR),
    auditList: (limit?: number): Promise<WorkspaceAuditEntry[]> => invoke(IPC.WORKSPACE_AUDIT_LIST, { limit })
  },
  window: {
    minimize: (): Promise<void> => invoke(IPC.WINDOW_MINIMIZE),
    toggleMaximize: (): Promise<void> => invoke(IPC.WINDOW_TOGGLE_MAXIMIZE),
    close: (): Promise<void> => invoke(IPC.WINDOW_CLOSE),
    isMaximized: (): Promise<boolean> => invoke(IPC.WINDOW_IS_MAXIMIZED),
    onStateChange: (cb: (maximized: boolean) => void): (() => void) => {
      const listener = (_e: unknown, value: unknown): void => cb(Boolean(value))
      ipcRenderer.on(IPC.WINDOW_STATE_EVENT, listener as never)
      return () => ipcRenderer.removeListener(IPC.WINDOW_STATE_EVENT, listener as never)
    }
  }
} as const

contextBridge.exposeInMainWorld('api', api)
