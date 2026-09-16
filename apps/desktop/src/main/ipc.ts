// IPC 注册 — 白名单 channel 与 shared/ipc-channels.ts 一一对应，测试有一致性校验。
// 会话 token 持久化走 safeStorage（Win DPAPI 绑定本机），解密失败即清除重来，不阻塞（E-3 铁律）。
import { app, dialog, ipcMain, BrowserWindow, safeStorage, shell } from 'electron'
import { existsSync, readFileSync, unlinkSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { IPC } from '@shared/ipc-channels'
import { APP_NAME, APP_VERSION } from '@shared/constants'
import type {
  AppInfo,
  AuthSession,
  ChatMessage,
  ChatSession,
  ChatStreamEvent,
  IpcResult,
  ModelProvider,
  ModelProtocol,
  WorkspaceAuditEntry
} from '@shared/types'
import type { SqlDatabase } from './db/adapters'
import { AuthService } from './services/auth.service'
import { ChatService, parseMessageMeta } from './services/chat.service'
import { ModelGatewayService } from './services/model-gateway.service'
import { SettingsService } from './services/settings.service'
import { WorkspaceService } from './services/workspace/workspace.service'
import { AuditService } from './services/workspace/audit.service'
import { ToolRegistry } from './agent/tool-registry'
import { AgentLoopService, buildAgentSystemPrompt } from './agent/agent-loop.service'
import { listDirTool } from './agent/tools/list-dir'
import { readFileTool } from './agent/tools/read-file'
import { globTool } from './agent/tools/glob'
import { grepTool } from './agent/tools/grep'
import { writeFileTool } from './agent/tools/write-file'
import { mkdirTool } from './agent/tools/mkdir'
import { createDeleteFileTool } from './agent/tools/delete-file'
import { restoreFromBackup } from './agent/tools/rollback'

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

/** safeStorage 加密器（apiKey / 会话 token 共用）— 加密不可用时 encrypt 返回空串 */
function makeCipher(): { encrypt(plaintext: string): string; decrypt(ciphertext: string): string | null } {
  return {
    encrypt(plaintext: string): string {
      if (!safeStorage.isEncryptionAvailable()) return ''
      return safeStorage.encryptString(plaintext).toString('base64')
    },
    decrypt(ciphertext: string): string | null {
      try {
        if (!safeStorage.isEncryptionAvailable()) return null
        return safeStorage.decryptString(Buffer.from(ciphertext, 'base64'))
      } catch {
        return null
      }
    }
  }
}

export function registerIpc(db: SqlDatabase, dbPath: string, getWindow: () => BrowserWindow | null): void {
  const auth = new AuthService(db, makeFilePersistence(join(dbPath, '..', 'session-token.enc')))
  const settings = new SettingsService(db)
  const chat = new ChatService(db)
  const gateway = new ModelGatewayService(db, makeCipher())
  const workspace = new WorkspaceService(join(dbPath, '..', 'workspace'))
  const audit = new AuditService(db)
  // Agent 工具循环（C-2/C-3）— 只读工具 auto；写工具 confirm 拦截在循环层；
  // delete_file 的回收站能力在此注入（工具与测试不 import Electron ABI）
  const registry = new ToolRegistry(workspace, audit)
  registry.register(listDirTool)
  registry.register(readFileTool)
  registry.register(globTool)
  registry.register(grepTool)
  registry.register(writeFileTool)
  registry.register(mkdirTool)
  registry.register(createDeleteFileTool({ trashItem: (abs) => shell.trashItem(abs) }))
  const agentLoop = new AgentLoopService(
    (userId, sessionId, req) => gateway.streamAgentTurn(userId, sessionId, req),
    registry,
    workspace,
    audit
  )

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

  ipcMain.handle(IPC.CHAT_SESSIONS_LIST, (): IpcResult<ChatSession[]> =>
    tryRun(() => {
      const user = auth.requireUser()
      return chat.listSessions(user.id).map((r) => ({ id: r.id, title: r.title, createdAt: r.created_at, updatedAt: r.updated_at }))
    })
  )

  ipcMain.handle(IPC.CHAT_SESSION_CREATE, (_e, p): IpcResult<ChatSession> =>
    tryRun(() => {
      const user = auth.requireUser()
      const r = chat.createSession(user.id, p?.title ? String(p.title) : undefined)
      return { id: r.id, title: r.title, createdAt: r.created_at, updatedAt: r.updated_at }
    })
  )

  ipcMain.handle(IPC.CHAT_SESSION_RENAME, (_e, p): IpcResult<null> =>
    tryRun(() => {
      const user = auth.requireUser()
      chat.renameSession(user.id, String(p?.id ?? ''), String(p?.title ?? ''))
      return null
    })
  )

  ipcMain.handle(IPC.CHAT_SESSION_DELETE, (_e, p): IpcResult<null> =>
    tryRun(() => {
      const user = auth.requireUser()
      chat.deleteSession(user.id, String(p?.id ?? ''))
      return null
    })
  )

  ipcMain.handle(IPC.CHAT_MESSAGES_LIST, (_e, p): IpcResult<ChatMessage[]> =>
    tryRun(() => {
      const user = auth.requireUser()
      return chat
        .listMessages(user.id, String(p?.sessionId ?? ''))
        .map((r) => ({ id: r.id, sessionId: r.session_id, role: r.role, content: r.content, meta: parseMessageMeta(r.meta), createdAt: r.created_at }))
    })
  )

  ipcMain.handle(IPC.CHAT_SEND, async (_e, p): Promise<IpcResult<{ userMessage: ChatMessage; assistantMessage: ChatMessage }>> => {
    try {
      const user = auth.requireUser()
      const sessionId = String(p?.sessionId ?? '')
      const content = String(p?.content ?? '')
      const win = getWindow()
      const hasProvider = gateway.getDefault(user.id) !== null

      const { userMessage, assistantMessage } = await chat.send(
        user.id,
        sessionId,
        content,
        hasProvider
          ? async (turns, assistantId) => {
              // Agent 循环（C-2）：多轮 tool_use；assistantId 用于流事件标记消息归属
              const run = await agentLoop.run({
                userId: user.id,
                sessionId,
                baseTurns: turns,
                system: buildAgentSystemPrompt(workspace.getRoot()),
                emit: (evt) => {
                  const base = { sessionId, messageId: assistantId } as const
                  const payload: ChatStreamEvent =
                    evt.kind === 'text'
                      ? { type: 'delta', ...base, delta: evt.delta }
                      : evt.kind === 'thinking'
                        ? { type: 'thinking', ...base, delta: evt.delta }
                        : evt.kind === 'round'
                          ? { type: 'round', ...base, round: evt.round, label: evt.label }
                          : { type: 'tool', ...base, call: evt.call }
                  win?.webContents.send(IPC.CHAT_STREAM_EVENT, payload)
                }
              })
              return { content: run.content, meta: run.meta }
            }
          : undefined,
        (messageId, delta) => {
          const evt: ChatStreamEvent = { type: 'delta', sessionId, messageId, delta }
          win?.webContents.send(IPC.CHAT_STREAM_EVENT, evt)
        }
      )
      const toDto = (r: { id: string; session_id: string; role: string; content: string; meta: string | null; created_at: number }): ChatMessage => ({
        id: r.id,
        sessionId: r.session_id,
        role: r.role as ChatMessage['role'],
        content: r.content,
        meta: parseMessageMeta(r.meta),
        createdAt: r.created_at
      })
      return { ok: true, data: { userMessage: toDto(userMessage), assistantMessage: toDto(assistantMessage) } }
    } catch (err) {
      const e = err as Error & { code?: string }
      return { ok: false, error: { code: e.code ?? 'ERROR', message: e.message } }
    }
  })

  ipcMain.handle(IPC.CHAT_ABORT, (_e, p): IpcResult<null> => {
    const sessionId = String(p?.sessionId ?? '')
    gateway.abort(sessionId) // 杀在途 HTTP 流
    agentLoop.stop(sessionId) // 杀轮间空隙 + 取消未决写确认
    return { ok: true, data: null }
  })

  // 写工具确认结果回传（C-3）— 批准后循环层继续 invoke；拒绝则回喂拒绝语义
  ipcMain.handle(IPC.CHAT_CONFIRM_RESOLVE, (_e, p): IpcResult<boolean> =>
    tryRun(() => {
      const found = agentLoop.resolveConfirm(String(p?.sessionId ?? ''), String(p?.callId ?? ''), p?.approve === true)
      if (!found) throw new Error('确认请求不存在或已过期')
      return true
    })
  )

  // 回滚一次 write_file（C-3）— 从 .agent-backups 恢复原内容，审计留痕并回写卡片状态
  ipcMain.handle(IPC.CHAT_ROLLBACK_WRITE, (_e, p): IpcResult<{ path: string }> =>
    tryRun(() => {
      const user = auth.requireUser()
      const sessionId = String(p?.sessionId ?? '')
      const messageId = String(p?.messageId ?? '')
      const callId = String(p?.callId ?? '')
      const row = chat.getMessage(user.id, sessionId, messageId)
      if (!row) throw new Error('消息不存在')
      const meta = parseMessageMeta(row.meta)
      const call = meta?.tools?.find((t) => t.id === callId)
      if (!call) throw new Error('未找到该写入记录')
      const data = call.data as { path?: string; backupPath?: string; rolledBack?: boolean } | undefined
      if (!data?.backupPath) throw new Error('该写入没有备份（新建文件），无法回滚')
      if (data.rolledBack) throw new Error('该写入已回滚过')
      const targetAbs = workspace.resolveInWorkspace(String(data.path))
      const backupAbs = workspace.resolveInWorkspace(String(data.backupPath))
      restoreFromBackup(targetAbs, backupAbs)
      audit.record(user.id, 'rollback_write', `已回滚 ${data.path}（恢复自 ${data.backupPath}）`, true)
      chat.patchToolCall(user.id, sessionId, messageId, callId, {
        summary: `已回滚：已恢复原内容（备份 ${data.backupPath}）`,
        data: { ...data, rolledBack: true }
      })
      return { path: String(data.path) }
    })
  )

  // ---------- 模型网关 ----------

  const toProviderDto = (r: { id: string; name: string; protocol: ModelProtocol; baseUrl: string; model: string; isDefault: boolean; apiKeyEncrypted: string }): ModelProvider => ({
    id: r.id,
    name: r.name,
    protocol: r.protocol,
    baseUrl: r.baseUrl,
    model: r.model,
    apiKeyMasked: r.apiKeyEncrypted ? '••••••••' : null,
    isDefault: r.isDefault
  })

  ipcMain.handle(IPC.MODEL_LIST, (): IpcResult<ModelProvider[]> =>
    tryRun(() => {
      const user = auth.requireUser()
      return gateway.list(user.id).map(toProviderDto)
    })
  )

  ipcMain.handle(IPC.MODEL_SAVE, (_e, p): IpcResult<null> =>
    tryRun(() => {
      const user = auth.requireUser()
      gateway.save(user.id, {
        id: p?.id ? String(p.id) : undefined,
        name: String(p?.name ?? ''),
        protocol: (p?.protocol === 'anthropic' ? 'anthropic' : 'openai') as ModelProtocol,
        baseUrl: String(p?.baseUrl ?? ''),
        model: String(p?.model ?? ''),
        apiKey: p?.apiKey ? String(p.apiKey) : undefined
      })
      return null
    })
  )

  ipcMain.handle(IPC.MODEL_DELETE, (_e, p): IpcResult<null> =>
    tryRun(() => {
      const user = auth.requireUser()
      gateway.remove(user.id, String(p?.id ?? ''))
      return null
    })
  )

  ipcMain.handle(IPC.MODEL_SET_DEFAULT, (_e, p): IpcResult<null> =>
    tryRun(() => {
      const user = auth.requireUser()
      gateway.setDefault(user.id, String(p?.id ?? ''))
      return null
    })
  )

  ipcMain.handle(IPC.MODEL_TEST, async (_e, p): Promise<IpcResult<{ ok: boolean; message: string }>> => {
    try {
      const user = auth.requireUser()
      if (p?.id) {
        return { ok: true, data: await gateway.testConnection(user.id, String(p.id)) }
      }
      // 表单未保存场景：直接探针
      const probe = await gateway.probe({
        protocol: (p?.protocol === 'anthropic' ? 'anthropic' : 'openai') as ModelProtocol,
        baseUrl: String(p?.baseUrl ?? ''),
        model: String(p?.model ?? ''),
        apiKey: String(p?.apiKey ?? '')
      })
      return { ok: true, data: probe }
    } catch (err) {
      const e = err as Error & { code?: string }
      return { ok: false, error: { code: e.code ?? 'ERROR', message: e.message } }
    }
  })

  // ---------- 工作区（Agent 文件操作地基） ----------

  ipcMain.handle(IPC.WORKSPACE_GET, (): IpcResult<{ root: string | null }> => tryRun(() => ({ root: workspace.getRoot() })))

  ipcMain.handle(IPC.WORKSPACE_SET, async (): Promise<IpcResult<string | null>> => {
    try {
      const win = getWindow()
      const ret = win
        ? await dialog.showOpenDialog(win, { properties: ['openDirectory', 'createDirectory'] })
        : await dialog.showOpenDialog({ properties: ['openDirectory', 'createDirectory'] })
      if (ret.canceled || ret.filePaths.length === 0) return ok(null) // 用户取消
      workspace.setRoot(ret.filePaths[0])
      return ok(workspace.getRoot())
    } catch (err) {
      const e = err as Error & { code?: string }
      return fail(e.code ?? 'ERROR', e.message)
    }
  })

  ipcMain.handle(IPC.WORKSPACE_AUDIT_LIST, (_e, p): IpcResult<WorkspaceAuditEntry[]> =>
    tryRun(() =>
      audit.list(Number(p?.limit) || 20).map((r) => ({
        id: r.id,
        userId: r.user_id,
        tool: r.tool,
        inputSummary: r.input_summary,
        ok: r.ok === 1,
        createdAt: r.created_at
      }))
    )
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
  ipcMain.handle(IPC.WINDOW_IS_MAXIMIZED, (): IpcResult<boolean> => ok(getWindow()?.isMaximized() ?? false))
  ipcMain.handle(IPC.WINDOW_CLOSE, (): IpcResult<null> => {
    getWindow()?.close()
    return ok(null)
  })

  void app // 本模块暂未直接使用 app，显式置空引用保持 import 语义清晰
}
