// IPC 注册 — 白名单 channel 与 shared/ipc-channels.ts 一一对应，测试有一致性校验。
// 会话 token 持久化走 safeStorage（Win DPAPI 绑定本机），解密失败即清除重来，不阻塞（E-3 铁律）。
import { app, dialog, ipcMain, BrowserWindow, safeStorage, shell, Tray, Menu, globalShortcut, Notification } from 'electron'
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
  KnowledgeDocFull,
  KnowledgeDocMeta,
  KnowledgeImportResult,
  KnowledgeSearchHit,
  ModelProvider,
  ExperimentStatus,
  ManuscriptStatus,
  ModelProtocol,
  UpdateState,
  WorkspaceAuditEntry
} from '@shared/types'
import type { SqlDatabase } from './db/adapters'
import { AuthService } from './services/auth.service'
import { ChatService, parseMessageMeta } from './services/chat.service'
import { ModelGatewayService, type ProviderRecord } from './services/model-gateway.service'
import { SettingsService } from './services/settings.service'
import { WorkspaceService } from './services/workspace/workspace.service'
import { AuditService } from './services/workspace/audit.service'
import { KnowledgeService } from './services/knowledge/knowledge.service'
import { MeetingService } from './services/meeting/meeting.service'
import { ExperimentService, EXPERIMENT_STATUSES } from './services/experiment/experiment.service'
import { DesktopIntegrationService } from './services/desktop/desktop-integration.service'
import { UpdateService, type UpdaterPort } from './services/update/update.service'
import { isUpdateChannelAvailable } from './services/update/feed-config'
import { BackupService } from './services/backup/backup.service'
import {
  EXIT_PASSWORD_ENC_KEY,
  EXIT_PASSWORD_KEY,
  maskSecret,
  planExitPasswordMigration,
  planExitPasswordWrite,
  resolveExitPassword
} from './services/backup/exit-password'
import { OssClient } from './services/backup/oss.client'
import { normalizeEndpoint } from './services/backup/oss-sig'
import { ManuscriptService, MANUSCRIPT_STATUSES, manuscriptStats } from './services/manuscript/manuscript.service'
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

// 桌面集成原语（M4）— main/index.ts 启动时安装真实 Electron 绑定；测试环境不触碰
let trayRef: Tray | null = null
let desktopTrayCreate: (iconPath: string) => void = () => undefined
let desktopTraySetToolTip: (tip: string) => void = () => undefined
let desktopTraySetContextMenu: (items: { label: string; action: () => void }[]) => void = () => undefined
let desktopTrayOnLeftClick: (cb: () => void) => void = () => undefined
let desktopTrayDestroy: () => void = () => undefined
let desktopNotify: (title: string, body: string, onClick: () => void) => void = () => undefined
let desktopRegisterShortcut: (acc: string, cb: () => void) => boolean = () => false
let desktopUnregisterShortcut: (acc: string) => void = () => undefined

/** main/index.ts 启动时安装 Electron 真实绑定（托盘/通知/globalShortcut） */
export function installDesktopPrimitives(getWindow: () => BrowserWindow | null): void {
  desktopTrayCreate = (iconPath) => {
    trayRef = new Tray(iconPath)
  }
  desktopTraySetToolTip = (tip) => trayRef?.setToolTip(tip)
  desktopTraySetContextMenu = (items) => {
    trayRef?.setContextMenu(
      Menu.buildFromTemplate(items.map((i) => ({ label: i.label, click: () => i.action() })))
    )
  }
  desktopTrayOnLeftClick = (cb) => trayRef?.on('click', () => cb())
  desktopTrayDestroy = () => {
    trayRef?.destroy()
    trayRef = null
  }
  desktopNotify = (title, body, onClick) => {
    const n = new Notification({ title, body })
    n.on('click', () => onClick())
    n.show()
  }
  desktopRegisterShortcut = (acc, cb) => globalShortcut.register(acc, cb)
  desktopUnregisterShortcut = (acc) => globalShortcut.unregister(acc)
  void getWindow
}

// 更新端口（M6-1）— main/index.ts 用适配层装配真实 electron-updater；未装配时用空端口，
// 保证服务可构造、状态机与 IPC 在无 Electron 运行时也成立。
let updaterPort: UpdaterPort | null = null

/** main/index.ts 启动时装配真实 updater（适配层是全仓库唯一 import electron-updater 处） */
export function installUpdaterPort(port: UpdaterPort): void {
  updaterPort = port
}

function resolveUpdaterPort(): UpdaterPort {
  return (
    updaterPort ?? {
      // 未装配适配层时不能声称"已是最新"：如实上报跳过（M6-1 打回项 2）
      checkForUpdates: async () => ({ skipped: true }),
      downloadUpdate: async () => undefined,
      quitAndInstall: () => undefined,
      onProgress: () => undefined,
      onDownloaded: () => undefined
    }
  )
}

export function registerIpc(db: SqlDatabase, dbPath: string, getWindow: () => BrowserWindow | null): {
  desktop: DesktopIntegrationService
  update: UpdateService
  runExitBackup: () => Promise<{ fileName: string; uploaded: boolean } | null>
} {
  const auth = new AuthService(db, makeFilePersistence(join(dbPath, '..', 'session-token.enc')))
  const settings = new SettingsService(db)
  const chat = new ChatService(db)
  const cipher = makeCipher()
  const gateway = new ModelGatewayService(db, cipher)
  const workspace = new WorkspaceService(join(dbPath, '..', 'workspace'))
  const audit = new AuditService(db)
  // 本地知识库（M2-1）— 原件副本目录 + 回收站注入（与 C-3 delete_file 同模式）
  const knowledge = new KnowledgeService(
    db,
    join(dbPath, '..', 'files'),
    { trashItem: (abs) => shell.trashItem(abs) }
  )
  // 本地会议档案（M2-2）— 附件删除走回收站、打开走 openPath，均注入装配
  const meetings = new MeetingService(
    db,
    join(dbPath, '..', 'files'),
    {
      trashItem: (abs) => shell.trashItem(abs),
      openPath: (abs) => shell.openPath(abs)
    }
  )
  // 本地实验记录本（M3-1）— 同注入装配
  const experiments = new ExperimentService(
    db,
    join(dbPath, '..', 'files'),
    {
      trashItem: (abs) => shell.trashItem(abs),
      openPath: (abs) => shell.openPath(abs)
    }
  )
  // 本地稿件库（M3-2）— 同注入装配
  const manuscripts = new ManuscriptService(
    db,
    join(dbPath, '..', 'files'),
    {
      trashItem: (abs) => shell.trashItem(abs),
      openPath: (abs) => shell.openPath(abs)
    }
  )

  // 桌面集成（M4）— 托盘/通知/全局快捷键，Electron 能力注入装配
  // 备份服务（M5-1）— VACUUM INTO + 附件目录打包
  const backup = new BackupService(db, dbPath, join(dbPath, '..', 'files'), APP_VERSION)
  /** 默认备份目录 — 空 targetDir 时兜底；与 exitAutoBackup 产物目录一致 */
  const backupDir = join(dbPath, '..', 'backups')

  const desktop = new DesktopIntegrationService({
    isWindowVisible: () => getWindow()?.isVisible() ?? false,
    focusWindow: () => {
      const w = getWindow()
      if (w) {
        if (w.isMinimized()) w.restore()
        w.show()
        w.focus()
      }
    },
    hideWindow: () => getWindow()?.hide(),
    trayCreate: (iconPath) => {
      desktopTrayCreate(iconPath)
    },
    traySetToolTip: (tip) => desktopTraySetToolTip(tip),
    traySetContextMenu: (items) => desktopTraySetContextMenu(items),
    trayOnLeftClick: (cb) => desktopTrayOnLeftClick(cb),
    trayDestroy: () => desktopTrayDestroy(),
    notify: (title, body, onClick) => desktopNotify(title, body, onClick),
    registerGlobalShortcut: (acc, cb) => desktopRegisterShortcut(acc, cb),
    unregisterGlobalShortcut: (acc) => desktopUnregisterShortcut(acc),
    getSetting: (key) => {
      try {
        return settings.get(key, auth.requireUser().id)
      } catch {
        return undefined
      }
    },
    setSetting: (key, value) => {
      try {
        settings.set(key, value, auth.requireUser().id)
      } catch {
        /* 未登录时写失败 */
      }
    },
    quit: () => {
      app.quit()
    }
  })

  // 自动更新（M6-1）— 提示式：启动后台检查 + 设置页手动检查；绝不自动下载/自动安装。
  // 非打包环境 electron-updater 会拒绝运行，故默认禁用；联调时用 feed 覆盖放行。
  const update = new UpdateService({
    currentVersion: APP_VERSION,
    // 与服务层/适配层共用同一事实来源（feed-config），避免"一侧放行、一侧闸门关闭"的接线断裂
    envSupported: isUpdateChannelAvailable({ env: process.env, isPackaged: app.isPackaged }),
    port: resolveUpdaterPort(),
    getSetting: (key) => {
      try {
        return settings.get(key, auth.requireUser().id)
      } catch {
        return undefined
      }
    },
    isWindowVisible: () => getWindow()?.isVisible() ?? false,
    // 复用 M4 通知注入（desktopNotify）
    notify: (title, body, onClick) => desktopNotify(title, body, onClick),
    onOpenSettings: () => {
      const w = getWindow()
      if (w) {
        if (w.isMinimized()) w.restore()
        w.show()
        w.focus()
        w.webContents.send(IPC.UPDATE_OPEN_SETTINGS, true)
      }
    },
    onStateChange: (state) => {
      getWindow()?.webContents.send(IPC.UPDATE_STATE_EVENT, state)
    },
    log: (message) => {
      // 打包后无控制台，重定向 stdout 启动时仍可取证；不进任何用户可见界面
      console.log(message)
    }
  })

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
      const key = String(p?.key ?? '')
      // 敏感设置一律不回显明文/密文（M6-2 清账③）
      if (key === EXIT_PASSWORD_KEY) return maskSecret(readExitPassword(user.id) !== null)
      return settings.get(key, user.id)
    })
  )

  ipcMain.handle(IPC.SETTINGS_SET, (_e, p): IpcResult<null> =>
    tryRun(() => {
      const user = auth.requireUser()
      const key = String(p?.key ?? '')
      // 敏感设置在写入路径即转 safeStorage 加密，明文不落盘
      if (key === EXIT_PASSWORD_KEY) {
        const plan = planExitPasswordWrite(p?.value ?? null, cipher)
        settings.set(EXIT_PASSWORD_ENC_KEY, plan.encrypted, user.id)
        settings.set(EXIT_PASSWORD_KEY, null, user.id)
        return null
      }
      settings.set(key, p?.value ?? null, user.id)
      return null
    })
  )

  ipcMain.handle(IPC.CHAT_SESSIONS_LIST, (): IpcResult<ChatSession[]> =>
    tryRun(() => {
      const user = auth.requireUser()
      return chat.listSessions(user.id).map((r) => ({
        id: r.id,
        title: r.title,
        createdAt: r.created_at,
        updatedAt: r.updated_at,
        tokensIn: r.tokens_in ?? 0,
        tokensOut: r.tokens_out ?? 0
      }))
    })
  )

  ipcMain.handle(IPC.CHAT_SESSION_CREATE, (_e, p): IpcResult<ChatSession> =>
    tryRun(() => {
      const user = auth.requireUser()
      const r = chat.createSession(user.id, p?.title ? String(p.title) : undefined)
      return {
        id: r.id,
        title: r.title,
        createdAt: r.created_at,
        updatedAt: r.updated_at,
        tokensIn: r.tokens_in ?? 0,
        tokensOut: r.tokens_out ?? 0
      }
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
              // V1 用量记账：本会话累计（迁移 010 两列；每轮 agent 完成即累加）
              chat.addSessionUsage(sessionId, run.usage)
              return { content: run.content, meta: run.meta }
            }
          : undefined,
        (messageId, delta) => {
          const evt: ChatStreamEvent = { type: 'delta', sessionId, messageId, delta }
          win?.webContents.send(IPC.CHAT_STREAM_EVENT, evt)
        }
      )
      if (hasProvider) {
        const sessionTitle = chat.listSessions(user.id).find((x) => x.id === sessionId)?.title ?? 'AI 助手'
        desktop.onAgentTurnComplete(sessionTitle, assistantMessage.content)
      }
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

  const toProviderDto = (
    r: ProviderRecord & { keyState?: 'ok' | 'invalid' }
  ): ModelProvider => ({
    id: r.id,
    name: r.name,
    protocol: r.protocol,
    baseUrl: r.baseUrl,
    model: r.model,
    apiKeyMasked: r.apiKeyEncrypted ? '••••••••' : null,
    isDefault: r.isDefault,
    keyState: r.keyState ?? 'ok'
  })

  ipcMain.handle(IPC.MODEL_LIST, (): IpcResult<ModelProvider[]> =>
    tryRun(() => {
      const user = auth.requireUser()
      return gateway.listWithKeyState(user.id).map(toProviderDto)
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

  // ---------- 备份与恢复（M5-1） ----------

  ipcMain.handle(IPC.BACKUP_CREATE, async (_e, p): Promise<IpcResult<{ fileName: string; size: number }>> => {
    try {
      auth.requireUser() // 登录守卫
      return ok(await backup.createBackup({ password: String(p?.password ?? ''), targetDir: String(p?.targetDir ?? '') || backupDir }))
    } catch (err) {
      const e = err as Error & { code?: string }
      return fail(e.code ?? 'ERROR', e.message)
    }
  })

  ipcMain.handle(IPC.BACKUP_RESTORE, async (_e, p): Promise<IpcResult<{ needRestart: boolean }>> => {
    try {
      auth.requireUser() // 登录守卫
      return ok(await backup.restoreBackup({ password: String(p?.password ?? ''), backupFile: String(p?.backupFile ?? '') }))
    } catch (err) {
      const e = err as Error & { code?: string }
      return fail(e.code ?? 'ERROR', e.message)
    }
  })

  ipcMain.handle(IPC.BACKUP_LIST, (_e, p): IpcResult<unknown[]> => tryRun(() => {
    return backup.listLocalBackups(String(p?.targetDir ?? '') || backupDir)
  }))

  // ---------- OSS 通道（M5-2） ----------

  /** 读 settings 中的 OSS 配置，Secret safeStorage 解密；未配置返回 null */
  function readOssConfig(): { bucket: string; endpoint: string; prefix: string; accessKeyId: string; accessKeySecret: string } | null {
    try {
      const bucket = settings.get('backup.oss.bucket', auth.requireUser().id) as string | undefined
      if (!bucket) return null
      const enc = settings.get('backup.oss.accessKeySecretEnc', auth.requireUser().id) as string | undefined
      if (!enc) return null
      return {
        bucket,
        endpoint: normalizeEndpoint((settings.get('backup.oss.endpoint', auth.requireUser().id) as string) ?? ''),
        prefix: (settings.get('backup.oss.prefix', auth.requireUser().id) as string) ?? 'desktop-backup/',
        accessKeyId: (settings.get('backup.oss.accessKeyId', auth.requireUser().id) as string) ?? '',
        accessKeySecret: safeStorage.decryptString(Buffer.from(enc, 'base64'))
      }
    } catch {
      return null
    }
  }

  ipcMain.handle(IPC.BACKUP_OSS_SAVE_CONFIG, (_e, p): IpcResult<null> => tryRun(() => {
    const user = auth.requireUser()
    const secret = String(p?.accessKeySecret ?? '')
    if (secret) {
      const enc = safeStorage.encryptString(secret).toString('base64')
      settings.set('backup.oss.accessKeySecretEnc', enc, user.id)
    }
    settings.set('backup.oss.bucket', String(p?.bucket ?? ''), user.id)
    settings.set('backup.oss.endpoint', normalizeEndpoint(String(p?.endpoint ?? '')), user.id)
    settings.set('backup.oss.prefix', String(p?.prefix ?? 'desktop-backup/'), user.id)
    settings.set('backup.oss.accessKeyId', String(p?.accessKeyId ?? ''), user.id)
    return null
  }))

  ipcMain.handle(IPC.BACKUP_OSS_TEST, async (_e): Promise<IpcResult<{ ok: boolean; error?: string }>> => {
    try {
      auth.requireUser()
      const cfg = readOssConfig()
      if (!cfg) return fail('NO_CONFIG', 'OSS 配置不完整')
      const client = new OssClient(cfg, async (req: { method: string; url: string; headers: Record<string, string>; body?: Buffer }) => {
        const { default: https } = await import('node:https')
        return new Promise((resolve, reject) => {
          const url = new URL(req.url)
          const opts = { hostname: url.hostname, port: url.port || 443, path: url.pathname + url.search, method: req.method, headers: req.headers }
          const httpReq = https.request(opts, (res) => {
            const chunks: Buffer[] = []
            res.on('data', (c: Buffer) => chunks.push(c))
            res.on('end', () => resolve({ status: res.statusCode ?? 500, body: Buffer.concat(chunks) }))
          })
          httpReq.on('error', reject)
          httpReq.end()
        })
      })
      return ok(await client.testConnection())
    } catch (err) {
      const e = err as Error & { code?: string }
      return fail(e.code ?? 'ERROR', e.message)
    }
  })

  ipcMain.handle(IPC.BACKUP_OSS_UPLOAD, async (_e, p): Promise<IpcResult<{ key: string; size: number }>> => {
    try {
      auth.requireUser()
      const cfg = readOssConfig()
      if (!cfg) return fail('NO_CONFIG', 'OSS 配置不完整')
      return ok(await backup.uploadBackup(cfg, String(p?.filePath ?? '')))
    } catch (err) {
      const e = err as Error & { code?: string }
      return fail(e.code ?? 'ERROR', e.message)
    }
  })

  ipcMain.handle(IPC.BACKUP_OSS_LIST_REMOTE, async (_e): Promise<IpcResult<unknown[]>> => {
    try {
      auth.requireUser()
      const cfg = readOssConfig()
      if (!cfg) return fail('NO_CONFIG', 'OSS 配置不完整')
      return ok(await backup.listRemoteBackups(cfg))
    } catch (err) {
      const e = err as Error & { code?: string }
      return fail(e.code ?? 'ERROR', e.message)
    }
  })

  ipcMain.handle(IPC.BACKUP_OSS_DOWNLOAD, async (_e, p): Promise<IpcResult<{ localPath: string }>> => {
    try {
      auth.requireUser()
      const cfg = readOssConfig()
      if (!cfg) return fail('NO_CONFIG', 'OSS 配置不完整')
      return ok(await backup.downloadBackup(cfg, String(p?.remoteKey ?? ''), join(dbPath, '..', 'backups')))
    } catch (err) {
      const e = err as Error & { code?: string }
      return fail(e.code ?? 'ERROR', e.message)
    }
  })

  ipcMain.handle(IPC.BACKUP_OSS_DELETE_REMOTE, async (_e, p): Promise<IpcResult<boolean>> => {
    try {
      auth.requireUser()
      const cfg = readOssConfig()
      if (!cfg) return fail('NO_CONFIG', 'OSS 配置不完整')
      await backup.deleteRemoteBackup(cfg, String(p?.remoteKey ?? ''))
      return ok(true)
    } catch (err) {
      const e = err as Error & { code?: string }
      return fail(e.code ?? 'ERROR', e.message)
    }
  })

  // 删除本地快照（合并列表「删除」操作）— 仅限默认备份目录内的 .mnbbak
  ipcMain.handle(IPC.BACKUP_DELETE_LOCAL, (_e, p): IpcResult<boolean> => tryRun(() => {
    auth.requireUser()
    return backup.deleteLocalBackup(backupDir, String(p?.fileName ?? ''))
  }))

  // ---------- 桌面集成（M4） ----------

  ipcMain.handle(IPC.DESKTOP_APPLY_SHORTCUT, (_e, p): IpcResult<{ ok: boolean; accelerator: string; error?: string; suggestion?: string }> =>
    tryRun(() => {
      const r = desktop.applyGlobalShortcut(String(p?.accelerator ?? ''))
      if (!r.ok) {
        const suggestion = desktop.findAvailableAlternative(String(p?.accelerator ?? ''))
        return { ...r, suggestion: suggestion ?? undefined }
      }
      return r
    })
  )

  ipcMain.handle(IPC.APP_QUIT, (): IpcResult<null> => {
    app.quit()
    return ok(null)
  })

  // ---------- 本地知识库（M2-1） ----------

  ipcMain.handle(IPC.KNOWLEDGE_LIST, (): IpcResult<KnowledgeDocMeta[]> => tryRun(() => {
    const user = auth.requireUser()
    return knowledge.list(user.id)
  }))

  ipcMain.handle(IPC.KNOWLEDGE_GET, (_e, p): IpcResult<KnowledgeDocFull | null> => tryRun(() => {
    const user = auth.requireUser()
    return knowledge.get(user.id, Number(p?.id))
  }))

  ipcMain.handle(IPC.KNOWLEDGE_IMPORT, (_e, p): IpcResult<KnowledgeImportResult> => tryRun(() => {
    const user = auth.requireUser()
    return knowledge.importFromFiles(user.id, Array.isArray(p?.files) ? p.files : [])
  }))

  ipcMain.handle(IPC.KNOWLEDGE_UPDATE, (_e, p): IpcResult<KnowledgeDocFull | null> => tryRun(() => {
    const user = auth.requireUser()
    return knowledge.update(user.id, Number(p?.id), {
      ...(p?.title !== undefined ? { title: String(p.title) } : {}),
      ...(p?.content !== undefined ? { content: String(p.content) } : {}),
      ...(Array.isArray(p?.tags) ? { tags: p.tags.map(String) } : {})
    })
  }))

  ipcMain.handle(IPC.KNOWLEDGE_DELETE, async (_e, p): Promise<IpcResult<boolean>> => {
    try {
      const user = auth.requireUser()
      return ok(await knowledge.delete(user.id, Number(p?.id)))
    } catch (err) {
      const e = err as Error & { code?: string }
      return fail(e.code ?? 'ERROR', e.message)
    }
  })

  ipcMain.handle(IPC.KNOWLEDGE_SEARCH, (_e, p): IpcResult<KnowledgeSearchHit[]> => tryRun(() => {
    const user = auth.requireUser()
    return knowledge.search(user.id, String(p?.query ?? ''))
  }))

  // ---------- 本地会议档案（M2-2） ----------

  const meetingToDto = (m: {
    id: number
    title: string
    meeting_date: number | null
    location: string
    attendees: string
    minutes: string
    created_at: number
    updated_at: number
  }) => {
    let attendees: string[] = []
    try {
      const v = JSON.parse(m.attendees)
      attendees = Array.isArray(v) ? v.map(String) : []
    } catch {
      attendees = []
    }
    return {
      id: m.id,
      title: m.title,
      meetingDate: m.meeting_date,
      location: m.location,
      attendees,
      minutes: m.minutes,
      createdAt: m.created_at,
      updatedAt: m.updated_at
    }
  }
  const toTranscriptDto = (t: { id: number; meeting_id: number; content: string; source: string; created_at: number; updated_at: number }) => ({
    id: t.id,
    meetingId: t.meeting_id,
    content: t.content,
    source: t.source as 'paste' | 'txt' | 'srt',
    createdAt: t.created_at,
    updatedAt: t.updated_at
  })
  const toFileDto = (f: { id: number; meeting_id: number; file_name: string; file_size: number; created_at: number }) => ({
    id: f.id,
    meetingId: f.meeting_id,
    fileName: f.file_name,
    fileSize: f.file_size,
    createdAt: f.created_at
  })

  ipcMain.handle(IPC.MEETINGS_LIST, (): IpcResult<unknown[]> => tryRun(() => {
    const user = auth.requireUser()
    return meetings.list(user.id).map(meetingToDto)
  }))

  ipcMain.handle(IPC.MEETINGS_GET, (_e, p): IpcResult<unknown> => tryRun(() => {
    const user = auth.requireUser()
    const detail = meetings.get(user.id, Number(p?.id))
    if (!detail) return null
    return {
      meeting: meetingToDto(detail.meeting),
      transcripts: detail.transcripts.map(toTranscriptDto),
      files: detail.files.map(toFileDto)
    }
  }))

  ipcMain.handle(IPC.MEETINGS_CREATE, (_e, p): IpcResult<{ id: number }> => tryRun(() => {
    const user = auth.requireUser()
    const id = meetings.create(user.id, {
      title: String(p?.title ?? ''),
      meetingDate: p?.meetingDate === null || p?.meetingDate === undefined ? null : Number(p.meetingDate),
      location: p?.location !== undefined ? String(p.location) : undefined,
      attendees: Array.isArray(p?.attendees) ? p.attendees.map(String) : undefined,
      minutes: p?.minutes !== undefined ? String(p.minutes) : undefined
    })
    return { id }
  }))

  ipcMain.handle(IPC.MEETINGS_UPDATE, (_e, p): IpcResult<boolean> => tryRun(() => {
    const user = auth.requireUser()
    return meetings.update(user.id, Number(p?.id), {
      ...(p?.title !== undefined ? { title: String(p.title) } : {}),
      ...(p?.meetingDate !== undefined ? { meetingDate: p.meetingDate === null ? null : Number(p.meetingDate) } : {}),
      ...(p?.location !== undefined ? { location: String(p.location) } : {}),
      ...(Array.isArray(p?.attendees) ? { attendees: p.attendees.map(String) } : {}),
      ...(p?.minutes !== undefined ? { minutes: String(p.minutes) } : {})
    })
  }))

  ipcMain.handle(IPC.MEETINGS_DELETE, async (_e, p): Promise<IpcResult<boolean>> => {
    try {
      const user = auth.requireUser()
      return ok(await meetings.delete(user.id, Number(p?.id)))
    } catch (err) {
      const e = err as Error & { code?: string }
      return fail(e.code ?? 'ERROR', e.message)
    }
  })

  ipcMain.handle(IPC.MEETINGS_TRANSCRIPT_IMPORT, (_e, p): IpcResult<unknown> => tryRun(() => {
    const user = auth.requireUser()
    const t = meetings.importTranscript(user.id, Number(p?.meetingId), {
      content: String(p?.content ?? ''),
      source: p?.source === 'txt' || p?.source === 'srt' ? p.source : 'paste'
    })
    return t ? toTranscriptDto(t) : null
  }))

  ipcMain.handle(IPC.MEETINGS_TRANSCRIPT_UPDATE, (_e, p): IpcResult<unknown> => tryRun(() => {
    const user = auth.requireUser()
    const t = meetings.updateTranscript(user.id, Number(p?.meetingId), Number(p?.transcriptId), String(p?.content ?? ''))
    return t ? toTranscriptDto(t) : null
  }))

  ipcMain.handle(IPC.MEETINGS_FILE_ADD, (_e, p): IpcResult<unknown> => tryRun(() => {
    const user = auth.requireUser()
    const f = meetings.addFile(user.id, Number(p?.meetingId), {
      name: String(p?.name ?? ''),
      data: new Uint8Array(p?.data ?? [])
    })
    return f
  }))

  ipcMain.handle(IPC.MEETINGS_FILE_REMOVE, async (_e, p): Promise<IpcResult<boolean>> => {
    try {
      const user = auth.requireUser()
      return ok(await meetings.removeFile(user.id, Number(p?.meetingId), Number(p?.fileId)))
    } catch (err) {
      const e = err as Error & { code?: string }
      return fail(e.code ?? 'ERROR', e.message)
    }
  })

  ipcMain.handle(IPC.MEETINGS_FILE_OPEN, (_e, p): IpcResult<{ path: string } | null> => tryRun(() => {
    const user = auth.requireUser()
    const path = meetings.openFile(user.id, Number(p?.meetingId), Number(p?.fileId))
    return path ? { path } : null
  }))

  ipcMain.handle(IPC.MEETINGS_SEARCH, (_e, p): IpcResult<unknown[]> => tryRun(() => {
    const user = auth.requireUser()
    return meetings.search(user.id, String(p?.query ?? ''))
  }))

  // ---------- 本地实验记录本（M3-1） ----------

  const toExperimentMeta = (r: { id: number; title: string; code: string; status: string; tags: string; created_at: number; updated_at: number }) => {
    let tags: string[] = []
    try {
      const v = JSON.parse(r.tags)
      tags = Array.isArray(v) ? v.map(String) : []
    } catch {
      tags = []
    }
    return { id: r.id, title: r.title, code: r.code, status: r.status as ExperimentStatus, tags, createdAt: r.created_at, updatedAt: r.updated_at }
  }
  const toExperimentFile = (f: { id: number; experiment_id: number; file_name: string; file_size: number; created_at: number }) => ({
    id: f.id,
    experimentId: f.experiment_id,
    fileName: f.file_name,
    fileSize: f.file_size,
    createdAt: f.created_at
  })

  ipcMain.handle(IPC.EXPERIMENTS_LIST, (_e, p): IpcResult<unknown[]> => tryRun(() => {
    const user = auth.requireUser()
    const status = typeof p?.status === 'string' && (EXPERIMENT_STATUSES as readonly string[]).includes(p.status) ? (p.status as ExperimentStatus) : undefined
    return experiments.list(user.id, status).map((r) => ({ ...toExperimentMeta(r), content: r.content }))
  }))

  ipcMain.handle(IPC.EXPERIMENTS_GET, (_e, p): IpcResult<unknown> => tryRun(() => {
    const user = auth.requireUser()
    const detail = experiments.get(user.id, Number(p?.id))
    if (!detail) return null
    return { ...toExperimentMeta(detail.experiment), content: detail.experiment.content, files: detail.files.map(toExperimentFile) }
  }))

  ipcMain.handle(IPC.EXPERIMENTS_CREATE, (_e, p): IpcResult<{ id: number; code: string }> => tryRun(() => {
    const user = auth.requireUser()
    const id = experiments.create(user.id, {
      title: String(p?.title ?? ''),
      ...(p?.code !== undefined && String(p.code).trim() !== '' ? { code: String(p.code) } : {}),
      ...(p?.status !== undefined ? { status: p.status as ExperimentStatus } : {}),
      ...(Array.isArray(p?.tags) ? { tags: p.tags.map(String) } : {}),
      ...(p?.content !== undefined ? { content: String(p.content) } : {})
    })
    const row = experiments.get(user.id, id)!.experiment
    return { id, code: row.code }
  }))

  ipcMain.handle(IPC.EXPERIMENTS_UPDATE, (_e, p): IpcResult<boolean> => tryRun(() => {
    const user = auth.requireUser()
    return experiments.update(user.id, Number(p?.id), {
      ...(p?.title !== undefined ? { title: String(p.title) } : {}),
      ...(p?.code !== undefined ? { code: String(p.code) } : {}),
      ...(p?.status !== undefined ? { status: p.status as ExperimentStatus } : {}),
      ...(Array.isArray(p?.tags) ? { tags: p.tags.map(String) } : {}),
      ...(p?.content !== undefined ? { content: String(p.content) } : {})
    })
  }))

  ipcMain.handle(IPC.EXPERIMENTS_DELETE, async (_e, p): Promise<IpcResult<boolean>> => {
    try {
      const user = auth.requireUser()
      return ok(await experiments.delete(user.id, Number(p?.id)))
    } catch (err) {
      const e = err as Error & { code?: string }
      return fail(e.code ?? 'ERROR', e.message)
    }
  })

  ipcMain.handle(IPC.EXPERIMENTS_FILE_ADD, (_e, p): IpcResult<unknown> => tryRun(() => {
    const user = auth.requireUser()
    const f = experiments.addFile(user.id, Number(p?.experimentId), {
      name: String(p?.name ?? ''),
      data: new Uint8Array(p?.data ?? [])
    })
    return f ? toExperimentFile(f) : null
  }))

  ipcMain.handle(IPC.EXPERIMENTS_FILE_REMOVE, async (_e, p): Promise<IpcResult<boolean>> => {
    try {
      const user = auth.requireUser()
      return ok(await experiments.removeFile(user.id, Number(p?.experimentId), Number(p?.fileId)))
    } catch (err) {
      const e = err as Error & { code?: string }
      return fail(e.code ?? 'ERROR', e.message)
    }
  })

  ipcMain.handle(IPC.EXPERIMENTS_FILE_OPEN, (_e, p): IpcResult<{ path: string } | null> => tryRun(() => {
    const user = auth.requireUser()
    const path = experiments.openFile(user.id, Number(p?.experimentId), Number(p?.fileId))
    return path ? { path } : null
  }))

  ipcMain.handle(IPC.EXPERIMENTS_SEARCH, (_e, p): IpcResult<unknown[]> => tryRun(() => {
    const user = auth.requireUser()
    return experiments.search(user.id, String(p?.query ?? ''))
  }))

  // ---------- 本地稿件库（M3-2） ----------

  ipcMain.handle(IPC.MANUSCRIPTS_LIST, (_e, p): IpcResult<unknown[]> => tryRun(() => {
    const user = auth.requireUser()
    const status = typeof p?.status === 'string' && (MANUSCRIPT_STATUSES as readonly string[]).includes(p.status) ? (p.status as ManuscriptStatus) : undefined
    return manuscripts.list(user.id, status).map((r) => ({
      id: r.id,
      title: r.title,
      status: r.status as ManuscriptStatus,
      targetJournal: r.target_journal,
      tags: (() => {
        try {
          const v = JSON.parse(r.tags)
          return Array.isArray(v) ? v.map(String) : []
        } catch {
          return []
        }
      })(),
      createdAt: r.created_at,
      updatedAt: r.updated_at,
      content: r.content,
      files: [] as unknown[],
      wordStats: manuscriptStats(r.content)
    }))
  }))

  ipcMain.handle(IPC.MANUSCRIPTS_GET, (_e, p): IpcResult<unknown> => tryRun(() => {
    const user = auth.requireUser()
    const detail = manuscripts.get(user.id, Number(p?.id))
    if (!detail) return null
    const m = detail.manuscript
    let tags: string[] = []
    try {
      const v = JSON.parse(m.tags)
      tags = Array.isArray(v) ? v.map(String) : []
    } catch {
      tags = []
    }
    return {
      id: m.id,
      title: m.title,
      status: m.status as ManuscriptStatus,
      targetJournal: m.target_journal,
      tags,
      content: m.content,
      createdAt: m.created_at,
      updatedAt: m.updated_at,
      files: detail.files.map((f) => ({
        id: f.id,
        manuscriptId: f.manuscript_id,
        fileName: f.file_name,
        fileSize: f.file_size,
        createdAt: f.created_at
      })),
      wordStats: manuscriptStats(m.content)
    }
  }))

  ipcMain.handle(IPC.MANUSCRIPTS_CREATE, (_e, p): IpcResult<{ id: number }> => tryRun(() => {
    const user = auth.requireUser()
    const id = manuscripts.create(user.id, {
      title: String(p?.title ?? ''),
      ...(p?.status !== undefined ? { status: p.status as ManuscriptStatus } : {}),
      ...(p?.targetJournal !== undefined ? { targetJournal: String(p.targetJournal) } : {}),
      ...(Array.isArray(p?.tags) ? { tags: p.tags.map(String) } : {}),
      ...(p?.content !== undefined ? { content: String(p.content) } : {})
    })
    return { id }
  }))

  ipcMain.handle(IPC.MANUSCRIPTS_UPDATE, (_e, p): IpcResult<boolean> => tryRun(() => {
    const user = auth.requireUser()
    return manuscripts.update(user.id, Number(p?.id), {
      ...(p?.title !== undefined ? { title: String(p.title) } : {}),
      ...(p?.status !== undefined ? { status: p.status as ManuscriptStatus } : {}),
      ...(p?.targetJournal !== undefined ? { targetJournal: String(p.targetJournal) } : {}),
      ...(Array.isArray(p?.tags) ? { tags: p.tags.map(String) } : {}),
      ...(p?.content !== undefined ? { content: String(p.content) } : {})
    })
  }))

  ipcMain.handle(IPC.MANUSCRIPTS_DELETE, async (_e, p): Promise<IpcResult<boolean>> => {
    try {
      const user = auth.requireUser()
      return ok(await manuscripts.delete(user.id, Number(p?.id)))
    } catch (err) {
      const e = err as Error & { code?: string }
      return fail(e.code ?? 'ERROR', e.message)
    }
  })

  ipcMain.handle(IPC.MANUSCRIPTS_FILE_ADD, (_e, p): IpcResult<unknown> => tryRun(() => {
    const user = auth.requireUser()
    const f = manuscripts.addFile(user.id, Number(p?.manuscriptId), {
      name: String(p?.name ?? ''),
      data: new Uint8Array(p?.data ?? [])
    })
    return f ? { id: f.id, manuscriptId: f.manuscript_id, fileName: f.file_name, fileSize: f.file_size, createdAt: f.created_at } : null
  }))

  ipcMain.handle(IPC.MANUSCRIPTS_FILE_REMOVE, async (_e, p): Promise<IpcResult<boolean>> => {
    try {
      const user = auth.requireUser()
      return ok(await manuscripts.removeFile(user.id, Number(p?.manuscriptId), Number(p?.fileId)))
    } catch (err) {
      const e = err as Error & { code?: string }
      return fail(e.code ?? 'ERROR', e.message)
    }
  })

  ipcMain.handle(IPC.MANUSCRIPTS_FILE_OPEN, (_e, p): IpcResult<{ path: string } | null> => tryRun(() => {
    const user = auth.requireUser()
    const path = manuscripts.openFile(user.id, Number(p?.manuscriptId), Number(p?.fileId))
    return path ? { path } : null
  }))

  ipcMain.handle(IPC.MANUSCRIPTS_SEARCH, (_e, p): IpcResult<unknown[]> => tryRun(() => {
    const user = auth.requireUser()
    return manuscripts.search(user.id, String(p?.query ?? ''))
  }))

  ipcMain.handle(IPC.MANUSCRIPTS_STATS, (_e, p): IpcResult<unknown> => tryRun(() => {
    return manuscriptStats(String(p?.content ?? ''))
  }))

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

  ipcMain.handle(IPC.WORKSPACE_CLEAR, (): IpcResult<null> =>
    tryRun(() => {
      workspace.clearRoot()
      return null
    })
  )

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
  ipcMain.handle(IPC.WINDOW_SHOW, (): IpcResult<null> => {
    const w = getWindow()
    if (w) { w.show() }
    return ok(null)
  })
  ipcMain.handle(IPC.WINDOW_FOCUS, (): IpcResult<null> => {
    const w = getWindow()
    if (w) { w.show(); w.focus() }
    return ok(null)
  })
  ipcMain.handle(IPC.WINDOW_CLOSE, (): IpcResult<null> => {
    getWindow()?.close()
    return ok(null)
  })

  desktop.restoreGlobalShortcut()

  /**
   * 读取退出备份密码（M6-2 清账③）— 优先解密 safeStorage 密文；
   * 命中旧明文时顺带完成一次性迁移（加密覆盖 → 清明文），无旧值则不做任何写入。
   */
  function readExitPassword(userId: string): string | null {
    const legacy = settings.get(EXIT_PASSWORD_KEY, userId)
    const encrypted = settings.get(EXIT_PASSWORD_ENC_KEY, userId)
    const resolved = resolveExitPassword({ legacyPlaintext: legacy, encrypted, cipher })
    if (resolved.needsMigration) {
      const plan = planExitPasswordMigration({ legacyPlaintext: legacy, encrypted, cipher })
      if (plan.encrypted) settings.set(EXIT_PASSWORD_ENC_KEY, plan.encrypted, userId)
      if (plan.clearPlaintext) settings.set(EXIT_PASSWORD_KEY, null, userId)
      console.log('[backup] exitPassword 已迁移至 safeStorage 加密存储')
    }
    return resolved.password
  }

  // ---------- 自动更新（M6-1）----------
  ipcMain.handle(IPC.UPDATE_STATE_GET, (): IpcResult<UpdateState> => tryRun(() => update.snapshot()))

  ipcMain.handle(IPC.UPDATE_CHECK, async (): Promise<IpcResult<UpdateState>> => {
    try {
      return ok(await update.check('manual'))
    } catch (err) {
      const e = err as Error & { code?: string }
      return fail(e.code ?? 'UPDATE_CHECK_FAILED', e.message)
    }
  })

  ipcMain.handle(IPC.UPDATE_DOWNLOAD, async (): Promise<IpcResult<UpdateState>> => {
    try {
      return ok(await update.download())
    } catch (err) {
      const e = err as Error & { code?: string }
      return fail(e.code ?? 'UPDATE_DOWNLOAD_FAILED', e.message)
    }
  })

  ipcMain.handle(IPC.UPDATE_INSTALL, (): IpcResult<boolean> => tryRun(() => update.installAndRestart()))

  const runExitBackup = async (): Promise<{ fileName: string; uploaded: boolean } | null> => {
    try {
      const autoOnExit = settings.get('backup.autoOnExit', auth.requireUser().id) === true
      if (!autoOnExit) return null
      const password = readExitPassword(auth.requireUser().id)
      if (!password) return null
      const cfg = readOssConfig()
      return backup.exitAutoBackup({ password, autoOnExit: true, ossConfig: cfg })
    } catch {
      return null // 退出备份失败不阻塞退出
    }
  }

  return { desktop, update, runExitBackup }
}

void app
