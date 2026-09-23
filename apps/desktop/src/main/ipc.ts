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
import { DailyBackupService } from './services/backup/daily-backup.service'
import { localDateKey, type DailyBackupResult } from './services/backup/daily-backup'
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
import { classifyLlmError, parseRetryAfterMs, withCommitBoundaryRetry } from './agent/llm-retry'
import { normalizePruneConfig, type PruneConfig } from './agent/context/prune'
import type { RememberChoice } from './agent/permissions/policy'
import {
  TOOL_CATEGORIES,
  normalizeStore,
  resolvePermission,
  ruleFromChoice,
  type PermissionStore,
  type PermissionValue,
  type ToolCategory
} from './agent/permissions/policy'
import type { PermissionPort } from './agent/agent-loop.service'
import { RemoteDriveService, driveErrorMessage } from './services/cloud/drive'
import { CloudBackupService, probeFromSettings } from './services/backup/cloud-backup.service'
import { planAutoProvision } from './services/backup/auto-provision'
import { cloudGuidance, cloudUsableStateFromAuth, type CloudAuthSnapshot } from './services/cloud/guidance'
import type { SessionStore, UploadSession } from './services/cloud/transfer'
import {
  RemoteKnowledgeService,
  knowledgeErrorMessage,
  toDocFull,
  toDocMeta,
  toSearchHit
} from './services/cloud/knowledge'
import {
  CloudApiClient,
  DEFAULT_CLOUD_BASE_URL,
  cloudStatusLabel,
  initialBindingState,
  normalizeBaseUrl,
  type CloudBindingState,
  type CloudHttpFn,
  type CloudTokens
} from './services/cloud/api-client'
import type { StreamTurnFn, StreamTurnResult } from '@shared/types'
import { listDirTool } from './agent/tools/list-dir'
import { readFileTool } from './agent/tools/read-file'
import { createTodoWriteTool, TodoStore } from './agent/tools/todowrite'
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
  const auth = new AuthService(db, makeFilePersistence(join(dbPath, '..', 'session-token.enc')),
    // M2-3a+ 安全网：首次认领（re-point 用户真实数据）前落一份数据库备份，出岔子可回滚
    () => {
      try {
        const { copyFileSync, existsSync } = require('node:fs') as typeof import('node:fs')
        if (!existsSync(dbPath)) return
        const stamp = new Date().toISOString().replace(/[:.]/g, '-')
        const dest = `${dbPath}.pre-claim-${stamp}.bak`
        copyFileSync(dbPath, dest)
        console.log(`[auth] 已备份数据库（认领前）：${dest}`)
        // 只保留最近 3 份认领备份，避免长期累积占空间
        try {
          const { readdirSync, unlinkSync } = require('node:fs') as typeof import('node:fs')
          const { dirname, basename, join } = require('node:path') as typeof import('node:path')
          const dir = dirname(dbPath)
          const prefix = `${basename(dbPath)}.pre-claim-`
          const olds = readdirSync(dir)
            .filter((f) => f.startsWith(prefix) && f.endsWith('.bak'))
            .sort()
            .slice(0, -3) // 时间戳可排序，留下最新 3 份
          for (const f of olds) unlinkSync(join(dir, f))
          if (olds.length) console.log(`[auth] 已清理 ${olds.length} 份过期认领备份`)
        } catch (e) {
          console.log(`[auth] 清理过期备份失败（不影响登录）：${e instanceof Error ? e.message : String(e)}`)
        }
      } catch (e) {
        console.log(`[auth] 备份数据库失败（不阻塞登录）：${e instanceof Error ? e.message : String(e)}`)
      }
    })
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
  // M8-3 §7：todowrite（第 10 个工具）——会话级清单，注入共享 store
  // ---- M8-3 §2 权限三层存储装配 ----
  //   会话级：内存 Map（本次会话有效，进程退出即清）
  //   工作区级：工作区 store 目录下的 permissions.json（换工作区即换规则）
  //   全局级：settings 键（跨工作区生效）
  const GLOBAL_PERMS_KEY = 'agent.permissions.global'
  const sessionPerms = new Map<string, Partial<Record<ToolCategory, PermissionValue>>>()
  const workspacePermsFile = join(workspace.getRoot() ?? dbPath, '..', 'permissions.json')
  const readJsonPerms = (file: string): Partial<Record<ToolCategory, PermissionValue>> => {
    try {
      return normalizeStore({ workspace: JSON.parse(readFileSync(file, 'utf8')) }).workspace
    } catch {
      return {}
    }
  }
  const writeJsonPerms = (file: string, layer: Partial<Record<ToolCategory, PermissionValue>>): void => {
    try {
      writeFileSync(file, JSON.stringify(layer, null, 2), 'utf8')
    } catch (e) {
      console.log(`[permissions] 工作区规则写入失败：${e instanceof Error ? e.message : String(e)}`)
    }
  }
  const readPermissionStore = (sessionId: string): PermissionStore =>
    normalizeStore({
      session: sessionPerms.get(sessionId) ?? {},
      workspace: readJsonPerms(workspacePermsFile),
      global: settings.get(GLOBAL_PERMS_KEY, currentUserId() ?? undefined)
    })
  const permissionPort: PermissionPort = {
    resolve: (category, sessionId) => resolvePermission(readPermissionStore(sessionId), category),
    remember: (category, value, choice, sessionId) => {
      const rule = ruleFromChoice(category, value, choice)
      if (!rule) return // 「仅本次」不落库
      if (rule.scope === 'session') {
        sessionPerms.set(sessionId, { ...(sessionPerms.get(sessionId) ?? {}), [category]: value })
      } else if (rule.scope === 'workspace') {
        writeJsonPerms(workspacePermsFile, { ...readJsonPerms(workspacePermsFile), [category]: value })
      } else {
        const next = normalizeStore({ global: { ...(settings.get(GLOBAL_PERMS_KEY, currentUserId() ?? undefined) as object ?? {}), [category]: value } }).global
        settings.set(GLOBAL_PERMS_KEY, next, currentUserId() ?? undefined)
      }
      console.log(`[permissions] 已记住：${category}=${value} @ ${rule.scope}`)
    }
  }

  // ---- M2-3a 云端连接（父级账号绑定）----
  //   令牌：safeStorage 加密后落 settings（同 backup.exitPassword / apiKey 模式）；
  //        解密失败或跨实例不可解 → 视为未绑定（不阻塞启动）。
  //   账号密码只经 UI 输入，绝不落日志/审计。
  const CLOUD_TOKENS_KEY = 'cloud.tokens'
  const CLOUD_STATE_KEY = 'cloud.binding'

  /** 生产 HTTP：注入式接口的 fetch 实现（超时 + 不跟随重定向以外的花活） */
  const cloudHttp: CloudHttpFn = async (req) => {
    const res = await fetch(req.url, {
      method: req.method,
      headers: req.headers,
      ...(req.body === undefined ? {} : { body: req.body }),
      signal: AbortSignal.timeout(req.timeoutMs)
    })
    const headers: Record<string, string> = {}
    res.headers.forEach((v, k) => (headers[k.toLowerCase()] = v))
    return { status: res.status, headers, text: await res.text() }
  }

  /**
   * DL-1 修复：数据源状态**以认证态为唯一事实源**推导，不再维护第二份「绑定状态」。
   * 每次调用现取（提供者模式），杜绝构造期/写入期快照导致的断层。
   */
  const cloudAuthSnapshot = (): CloudAuthSnapshot => {
    let loggedIn = false
    try {
      auth.requireUser()
      loggedIn = true
    } catch {
      loggedIn = false
    }
    const cloudUsername = loggedIn ? auth.cloudIdentityOfCurrentUser() : null
    return {
      loggedIn,
      isCloudIdentity: cloudUsername !== null,
      hasCloudTokens: readCloudTokens() !== null
    }
  }

  /** 服务器地址：机器级元数据（不按用户隔离），仅作配置来源，**不作为状态** */
  const readCloudBaseUrl = (): string => {
    const raw = settings.get('cloud.baseUrl') as string | undefined
    return normalizeBaseUrl(raw ?? DEFAULT_CLOUD_BASE_URL)
  }
  const writeCloudBaseUrl = (url: string): void => {
    settings.set('cloud.baseUrl', normalizeBaseUrl(url))
  }

  const readCloudState = (): CloudBindingState => {
    const raw = settings.get(CLOUD_STATE_KEY, currentUserId() ?? undefined) as Partial<CloudBindingState> | undefined
    const base = initialBindingState(raw?.baseUrl ?? DEFAULT_CLOUD_BASE_URL)
    const status = raw?.status
    return {
      ...base,
      status: status === 'bound' || status === 'expired' || status === 'offline' ? status : 'unbound',
      ...(typeof raw?.username === 'string' ? { username: raw.username } : {}),
      ...(typeof raw?.lastError === 'string' ? { lastError: raw.lastError } : {}),
      updatedAt: typeof raw?.updatedAt === 'number' ? raw.updatedAt : 0
    }
  }

  /** 读取令牌（解密失败 → null，视为未绑定） */
  const readCloudTokens = (): CloudTokens | null => {
    const enc = settings.get(CLOUD_TOKENS_KEY, currentUserId() ?? undefined) as string | undefined
    if (!enc) return null
    const plain = cipher.decrypt(enc)
    if (!plain) {
      console.log('[cloud] 令牌解密失败（跨实例或系统凭据变更）→ 视为未绑定')
      return null
    }
    try {
      const j = JSON.parse(plain) as Partial<CloudTokens>
      return typeof j.accessToken === 'string' && typeof j.refreshToken === 'string' ? (j as CloudTokens) : null
    } catch {
      return null
    }
  }
  const writeCloudTokens = (tokens: CloudTokens | null): void => {
    if (!tokens) {
      settings.set(CLOUD_TOKENS_KEY, '', currentUserId() ?? undefined)
      return
    }
    const enc = cipher.encrypt(JSON.stringify(tokens))
    settings.set(CLOUD_TOKENS_KEY, enc, currentUserId() ?? undefined)
  }

  const makeCloudClient = (baseUrl: string): CloudApiClient =>
    new CloudApiClient({ http: cloudHttp, baseUrl, log: (m) => console.log(m) })

  const todoStore = new TodoStore()
  registry.register(createTodoWriteTool({ store: todoStore }))
  registry.register(globTool)
  registry.register(grepTool)
  registry.register(writeFileTool)
  registry.register(mkdirTool)
  registry.register(createDeleteFileTool({ trashItem: (abs) => shell.trashItem(abs) }))
  // M8-1 §2 装配：提交边界重试包在**网关 SSE 请求外层** —— agent-loop 完全无感（仍是 StreamTurnFn）。
  // 首个可见 delta 之前失败（429/5xx/网络/空响应）→ 静默重试；之后失败 → 不重试，交给循环并入文。
  const streamTurnWithRetry: StreamTurnFn = (userId, sessionId, req) =>
    withCommitBoundaryRetry<StreamTurnResult>({
      now: () => Date.now(),
      sleep: (ms) => new Promise<void>((r) => setTimeout(r, ms)),
      onRetry: ({ attempt, delayMs, kind }) =>
        console.log(`[agent][retry] 第 ${attempt} 次重试（${kind}），等待 ${delayMs}ms`),
      attempt: (visible) =>
        gateway.streamAgentTurn(userId, sessionId, {
          ...req,
          // 桥接「首个可见 delta」：一旦有正文/思考流出即视为已提交，此后不再重试
          onEvent: (e) => {
            visible(e.kind === 'text' ? 'text' : 'thinking')
            req.onEvent(e)
          }
        }),
      toFailure: (err) => {
        const e = err as Error & { status?: number; code?: string; headers?: Record<string, string> }
        const retryAfterMs = parseRetryAfterMs(e?.headers, Date.now())
        return {
          kind: classifyLlmError({
            ...(e?.status === undefined ? {} : { status: e.status }),
            ...(e?.code === undefined ? {} : { code: e.code }),
            message: e?.message ?? String(err)
          }),
          ...(retryAfterMs === undefined ? {} : { retryAfterMs })
        }
      }
    })

  const agentLoop = new AgentLoopService(streamTurnWithRetry, registry, workspace, audit)

  // M8-2 §2 配置化：上下文预算（windowTokens / triggerRatio / targetRatio …）走既有 settings 机制。
  // 默认值即现行为 → 未配置时零行为变更；非法值经 normalizePruneConfig 回退默认。
  const CONTEXT_CONFIG_KEY = 'agent.context.config'
  // 注意：此处**只声明**，调用必须晚于 currentUserId 的声明（见每日定时备份区块之后），
  // 否则会触发 TDZ「Cannot access 'currentUserId' before initialization」导致启动即崩
  // —— 类型检查与单测都抓不到，是 M8-2 真机验证发现的。
  const readContextConfig = (): PruneConfig =>
    normalizePruneConfig(settings.get(CONTEXT_CONFIG_KEY, currentUserId() ?? undefined))

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
                  const payload: ChatStreamEvent | null =
                    evt.kind === 'text'
                      ? { type: 'delta', ...base, delta: evt.delta }
                      : evt.kind === 'thinking'
                        ? { type: 'thinking', ...base, delta: evt.delta }
                        : evt.kind === 'round'
                          ? { type: 'round', ...base, round: evt.round, label: evt.label }
                          : evt.kind === 'tool'
                            ? { type: 'tool', ...base, call: evt.call }
                            : null
                  // M8-2 context 事件不进对话流（避免干扰用户），只落日志供排查；
                  // 当前估算与最近裁切通过 agent:context-get 供设置页调试区读取
                  if (payload) win?.webContents.send(IPC.CHAT_STREAM_EVENT, payload)
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
      // M8-3：透传「记住」选择（仅本次 / 此工作区 / 全局）
      const found = agentLoop.resolveConfirm(
        String(p?.sessionId ?? ''),
        String(p?.callId ?? ''),
        p?.approve === true,
        (p?.remember as RememberChoice | undefined) ?? undefined
      )
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

  // ---------- 远程网盘（M2-3c）----------
  // 实例在下方（currentUserId 就绪后）赋值，此处仅前置声明，避免 TDZ（M8-2/M2-3b 双实证）。
  let remoteDrive: RemoteDriveService
  /** 工单 ZB：零感托管备份执行器（装配在 currentUserId 就绪后） */
  let cloudBackup: CloudBackupService

  ipcMain.handle(IPC.DRIVE_STATE, (): IpcResult<unknown> =>
    tryRun(() => {
      auth.requireUser()
      // DL-1：以认证态为唯一事实源推导
      const snap = cloudAuthSnapshot()
      const state = cloudUsableStateFromAuth(snap)
      const g = cloudGuidance(state, '网盘')
      return {
        state,
        title: g.title,
        hint: g.hint,
        canOpenSettings: g.canOpenSettings,
        actionLabel: g.actionLabel,
        baseUrl: readCloudBaseUrl(),
        username: snap.isCloudIdentity ? auth.cloudIdentityOfCurrentUser() : null
      }
    })
  )

  ipcMain.handle(IPC.DRIVE_LIST, async (_e, p): Promise<IpcResult<unknown>> => {
    auth.requireUser()
    const r = await remoteDrive.list({ parentId: p?.parentId ?? null })
    if (!r.ok) return fail(`DRIVE_${r.error.kind.toUpperCase().replace('-', '_')}`, driveErrorMessage(r.error))
    return ok(r.data)
  })

  ipcMain.handle(IPC.DRIVE_RENAME, async (_e, p): Promise<IpcResult<unknown>> => {
    auth.requireUser()
    const r = await remoteDrive.rename(Number(p?.id), { title: String(p?.title ?? '') })
    if (!r.ok) return fail(`DRIVE_${r.error.kind.toUpperCase().replace('-', '_')}`, driveErrorMessage(r.error))
    return ok(r.data)
  })

  ipcMain.handle(IPC.DRIVE_DELETE, async (_e, p): Promise<IpcResult<boolean>> => {
    auth.requireUser()
    const r = await remoteDrive.remove(Number(p?.id))
    if (!r.ok) return fail(`DRIVE_${r.error.kind.toUpperCase().replace('-', '_')}`, driveErrorMessage(r.error))
    return ok(true)
  })

  ipcMain.handle(IPC.DRIVE_FOLDERS, async (_e, p): Promise<IpcResult<unknown>> => {
    auth.requireUser()
    const r = await remoteDrive.listFolders(p?.parentId ?? null)
    if (!r.ok) return fail(`DRIVE_${r.error.kind.toUpperCase().replace('-', '_')}`, driveErrorMessage(r.error))
    return ok(r.data)
  })

  ipcMain.handle(IPC.DRIVE_CREATE_FOLDER, async (_e, p): Promise<IpcResult<unknown>> => {
    auth.requireUser()
    const name = String(p?.name ?? '').trim()
    if (!name) return fail('INVALID_INPUT', '请填写文件夹名称')
    const r = await remoteDrive.createFolder(name, p?.parentId ?? null)
    if (!r.ok) return fail(`DRIVE_${r.error.kind.toUpperCase().replace('-', '_')}`, driveErrorMessage(r.error))
    return ok(r.data)
  })

  ipcMain.handle(IPC.DRIVE_PENDING_UPLOADS, (): IpcResult<unknown> =>
    tryRun(() => {
      auth.requireUser()
      return remoteDrive.pendingUploads()
    })
  )

  // 下载：弹保存对话框 → 分片落盘（进度经 DRIVE_DOWNLOAD 事件推送）
  ipcMain.handle(IPC.DRIVE_DOWNLOAD, async (e, p): Promise<IpcResult<unknown>> => {
    auth.requireUser()
    const id = Number(p?.id)
    if (!Number.isFinite(id)) return fail('INVALID_INPUT', '缺少文件标识')
    try {
      const { dialog } = await import('electron')
      const win = BrowserWindow.getAllWindows()[0]
      const meta = await remoteDrive.get(id)
      const suggested = meta.ok ? meta.data.fileName : `云端文件-${id}`
      const picked = win
        ? await dialog.showSaveDialog(win, { defaultPath: suggested })
        : await dialog.showSaveDialog({ defaultPath: suggested })
      if (picked.canceled || !picked.filePath) {
        return fail('CANCELLED', '已取消下载')
      }
      const { createWriteStream } = await import('node:fs')
      const ws = createWriteStream(picked.filePath)
      const r = await remoteDrive.download(id, {
        write: async (bytes) => {
          await new Promise<void>((resolve, reject) => {
            ws.write(Buffer.from(bytes), (err) => (err ? reject(err) : resolve()))
          })
        },
        onProgress: (prog) => {
          if (!e.sender.isDestroyed()) e.sender.send(IPC.DRIVE_DOWNLOAD, { kind: 'progress', ...prog })
        }
      })
      await new Promise<void>((resolve) => ws.end(() => resolve()))
      if (!r.ok) return fail(`DRIVE_${r.error.kind.toUpperCase().replace('-', '_')}`, driveErrorMessage(r.error))
      console.log(`[drive] 下载完成：${r.data.bytes} 字节 → ${picked.filePath}`)
      return ok({ bytes: r.data.bytes, path: picked.filePath })
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      console.log(`[drive] 下载异常：${msg}`)
      return fail('DRIVE_DOWNLOAD_FAILED', '下载失败，请稍后重试。')
    }
  })

  // 上传：分块读盘（不整文件进内存）+ 进度事件推给渲染层
  ipcMain.handle(IPC.DRIVE_UPLOAD, async (e, p): Promise<IpcResult<unknown>> => {
    auth.requireUser()
    const filePath = String(p?.filePath ?? '')
    if (!filePath) return fail('INVALID_INPUT', '请选择要上传的文件')
    const parentId = p?.parentId === undefined || p?.parentId === null ? null : Number(p.parentId)
    try {
      const { statSync, openSync, readSync, closeSync } = await import('node:fs')
      const st = statSync(filePath)
      if (!st.isFile()) return fail('INVALID_INPUT', '只能上传文件')
      const fd = openSync(filePath, 'r')
      const readChunk = async (offset: number, length: number): Promise<Uint8Array> => {
        const buf = Buffer.allocUnsafe(length)
        readSync(fd, buf, 0, length, offset)
        return new Uint8Array(buf)
      }
      try {
        const r = await remoteDrive.upload({
          filename: filePath.split(/[\\/]/).pop() ?? '未命名',
          fileSize: st.size,
          readChunk,
          parentId,
          onProgress: (prog) => {
            // 进度事件：大文件上传时渲染层据此画进度条
            if (!e.sender.isDestroyed()) e.sender.send(IPC.DRIVE_UPLOAD, { kind: 'progress', ...prog })
          }
        })
        if (!r.ok) return fail(`DRIVE_${r.error.kind.toUpperCase().replace('-', '_')}`, driveErrorMessage(r.error))
        return ok(r.data)
      } finally {
        closeSync(fd)
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      console.log(`[drive] 上传异常：${msg}`)
      return fail('DRIVE_UPLOAD_FAILED', '上传失败，请检查文件是否可读或稍后重试。')
    }
  })

  // ---------- 远程知识库（M2-3b：数据源切父级服务器） ----------
  // 注意：实例在下方（currentUserId 就绪后）才赋值，此处仅前置声明，避免 TDZ。
  let remoteKnowledge: RemoteKnowledgeService
  //
  // 说明：**渲染层调用面与返回形状保持不变**（list/get/search/update/delete），只换数据源，
  // 因此知识库页面无需重写。本地遗留表（knowledge_documents 等）本单**不迁移、不删除、不显示**，
  // 原样保留在库中（工单 §4 硬边界）；「本地→云端迁移工具」待总指挥/用户拍板。

  /** 远程知识库服务：令牌从 settings 取（M2-3a 加密存储），续期后回写 */
  /** 知识库数据源状态（渲染层据此显示引导态） */
  ipcMain.handle(IPC.KNOWLEDGE_SOURCE_STATE, async (): Promise<IpcResult<unknown>> => {
    try {
      return ok(await (async () => {
      auth.requireUser()
      // DL-1：以认证态为唯一事实源推导（不再读独立的绑定状态存储）
      const snap = cloudAuthSnapshot()
      const state = cloudUsableStateFromAuth(snap)
      // DL-1/UI1-3：统一走集中状态机（与网盘同一套文案；不再用 M2-3b 的旧文案函数）
      const g = cloudGuidance(state, '知识库')
      // 附带服务端返回的条目总数（DL-1 #3 决定性诊断：用户一眼可见 total 是 9 还是 856）。
      // 只在可用态下取，避免未登录/离线时多发一次请求。
      let total: number | null = null
      if (state === 'ready') {
        const r = await remoteKnowledge.list({ page: 1, pageSize: 1 })
        if (r.ok) total = r.data.total
      }
      return {
        state,
        title: g.title,
        hint: g.hint,
        canOpenSettings: g.canOpenSettings,
        baseUrl: readCloudBaseUrl(),
        username: snap.isCloudIdentity ? auth.cloudIdentityOfCurrentUser() : null,
        total
      }
      })())
    } catch (e) {
      const err = e as Error & { code?: string }
      return fail(err.code ?? 'ERROR', err.message)
    }
  })

  // UI1-3：知识库统计（分类/实体/假设计数）—— 对齐父级 health-summary
  ipcMain.handle(IPC.KNOWLEDGE_STATS, async (): Promise<IpcResult<unknown>> => {
    auth.requireUser()
    const r = await remoteKnowledge.stats()
    if (!r.ok) return fail(`KNOWLEDGE_${r.error.kind.toUpperCase().replace('-', '_')}`, knowledgeErrorMessage(r.error))
    return ok(r.data)
  })

  ipcMain.handle(IPC.KNOWLEDGE_LIST, async (): Promise<IpcResult<KnowledgeDocMeta[]>> => {
    auth.requireUser()
    // ★ 拉全所有分页（逻辑在服务层 listAll，避免「测试副本 ≠ 真实实现」）
    const r = await remoteKnowledge.listAll({ pageSize: 100 })
    if (!r.ok) return fail(`KNOWLEDGE_${r.error.kind.toUpperCase().replace('-', '_')}`, knowledgeErrorMessage(r.error))
    return ok(r.data.items.map(toDocMeta) as unknown as KnowledgeDocMeta[])
  })

  ipcMain.handle(IPC.KNOWLEDGE_GET, async (_e, p): Promise<IpcResult<KnowledgeDocFull | null>> => {
    auth.requireUser()
    const r = await remoteKnowledge.get(Number(p?.id))
    if (!r.ok) return fail(`KNOWLEDGE_${r.error.kind.toUpperCase().replace('-', '_')}`, knowledgeErrorMessage(r.error))
    return ok(toDocFull(r.data) as unknown as KnowledgeDocFull)
  })

  ipcMain.handle(IPC.KNOWLEDGE_IMPORT, async (_e, p): Promise<IpcResult<KnowledgeImportResult>> => {
    auth.requireUser()
    // 远程模式：逐条新建；失败项进 skipped（不中断其余）
    const files = Array.isArray(p?.files) ? (p.files as { name?: unknown; content?: unknown }[]) : []
    const imported: unknown[] = []
    const skipped: { name: string; reason: string }[] = []
    for (const f of files) {
      const name = String(f?.name ?? '未命名')
      const r = await remoteKnowledge.create({ title: name, content: String(f?.content ?? '') })
      if (r.ok) imported.push(toDocMeta(r.data))
      else skipped.push({ name, reason: knowledgeErrorMessage(r.error) })
    }
    return ok({ imported, skipped } as unknown as KnowledgeImportResult)
  })

  ipcMain.handle(IPC.KNOWLEDGE_UPDATE, async (_e, p): Promise<IpcResult<KnowledgeDocFull | null>> => {
    auth.requireUser()
    const r = await remoteKnowledge.update(Number(p?.id), {
      ...(p?.title !== undefined ? { title: String(p.title) } : {}),
      ...(p?.content !== undefined ? { content: String(p.content) } : {}),
      ...(Array.isArray(p?.tags) ? { tags: (p.tags as unknown[]).map(String) } : {})
    })
    if (!r.ok) return fail(`KNOWLEDGE_${r.error.kind.toUpperCase().replace('-', '_')}`, knowledgeErrorMessage(r.error))
    return ok(toDocFull(r.data) as unknown as KnowledgeDocFull)
  })

  ipcMain.handle(IPC.KNOWLEDGE_DELETE, async (_e, p): Promise<IpcResult<boolean>> => {
    auth.requireUser()
    const r = await remoteKnowledge.remove(Number(p?.id))
    if (!r.ok) return fail(`KNOWLEDGE_${r.error.kind.toUpperCase().replace('-', '_')}`, knowledgeErrorMessage(r.error))
    return ok(true)
  })

  ipcMain.handle(IPC.KNOWLEDGE_SEARCH, async (_e, p): Promise<IpcResult<KnowledgeSearchHit[]>> => {
    auth.requireUser()
    // ★ 远程模式一律走**服务端检索端点**：本地 CJK bigram 只适用于本地模式
    const r = await remoteKnowledge.search(String(p?.query ?? ''))
    if (!r.ok) return fail(`KNOWLEDGE_${r.error.kind.toUpperCase().replace('-', '_')}`, knowledgeErrorMessage(r.error))
    return ok(r.data.map(toSearchHit) as unknown as KnowledgeSearchHit[])
  })

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

  // M8-2 可观测性：上下文估算与最近裁切（设置页调试区）
  ipcMain.handle(IPC.AGENT_CONTEXT_GET, (): IpcResult<unknown> =>
    tryRun(() => {
      auth.requireUser()
      return agentLoop.contextSnapshot()
    })
  )

  // M8-3 §2/§4：权限查看与写入（设置页「工具权限」区块）
  ipcMain.handle(IPC.AGENT_PERMISSIONS_GET, (): IpcResult<unknown> =>
    tryRun(() => {
      auth.requireUser()
      const sessionId = ''
      return {
        categories: TOOL_CATEGORIES.map((c) => {
          const r = resolvePermission(readPermissionStore(sessionId), c)
          return { category: c, value: r.value, scope: r.scope, isDefault: r.isDefault }
        }),
        global: normalizeStore({ global: settings.get(GLOBAL_PERMS_KEY, currentUserId() ?? undefined) }).global,
        workspace: readJsonPerms(workspacePermsFile)
      }
    })
  )
  ipcMain.handle(IPC.AGENT_PERMISSIONS_SET, (_e, p): IpcResult<unknown> =>
    tryRun(() => {
      auth.requireUser()
      const patch = (p ?? {}) as { category?: string; value?: string; scope?: string }
      const category = String(patch.category ?? '') as ToolCategory
      const value = String(patch.value ?? '') as PermissionValue
      const scope = String(patch.scope ?? 'global') as 'workspace' | 'global'
      if (!TOOL_CATEGORIES.includes(category)) throw new Error(`未知工具类别: ${category}`)
      if (value !== 'allow' && value !== 'ask' && value !== 'deny') throw new Error(`未知权限值: ${value}`)
      if (scope === 'workspace') {
        writeJsonPerms(workspacePermsFile, { ...readJsonPerms(workspacePermsFile), [category]: value })
      } else {
        const cur = (settings.get(GLOBAL_PERMS_KEY, currentUserId() ?? undefined) as Record<string, unknown>) ?? {}
        settings.set(GLOBAL_PERMS_KEY, normalizeStore({ global: { ...cur, [category]: value } }).global, currentUserId() ?? undefined)
      }
      console.log(`[permissions] 设置页写入：${category}=${value} @ ${scope}`)
      return { ok: true }
    })
  )

  // M2-3a §3/§4：云端连接状态（设置页「云端连接」区块 + 可观测性）
  ipcMain.handle(IPC.CLOUD_STATUS_GET, (): IpcResult<unknown> =>
    tryRun(() => {
      auth.requireUser()
      // DL-1：以认证态为唯一事实源推导（不再读独立的绑定状态存储）
      const snap = cloudAuthSnapshot()
      const state = cloudUsableStateFromAuth(snap)
      return {
        status: state,
        statusLabel: cloudStatusLabel(state),
        baseUrl: readCloudBaseUrl(),
        ...(snap.isCloudIdentity ? { username: auth.cloudIdentityOfCurrentUser() } : {}),
        hasTokens: snap.hasCloudTokens
      }
    })
  )

  // 退出登录（原「解绑」，M2-3a+ §5 语义调整）：清云端令牌 + 结束本地会话。
  // 状态无需另存 —— 认证态变「未登录」后，数据源状态自动回 unbound（DL-1 提供者模式）。
  // **本地业务数据一律保留**（同账号下次登录自动认领回来）。
  ipcMain.handle(IPC.CLOUD_UNBIND, (): IpcResult<unknown> =>
    tryRun(() => {
      auth.requireUser()
      writeCloudTokens(null)
      auth.logout()
      console.log('[account] 已退出登录（云端令牌已清；本地数据未动）')
      const state = cloudUsableStateFromAuth(cloudAuthSnapshot())
      return { status: state, statusLabel: cloudStatusLabel(state), baseUrl: readCloudBaseUrl(), hasTokens: false }
    })
  )

  // M2-3a+：外链（仅 http/https，白名单协议，避免被滥用打开本地文件）
  ipcMain.handle(IPC.APP_OPEN_EXTERNAL, async (_e, p): Promise<IpcResult<null>> => {
    const url = String((p as { url?: string })?.url ?? '')
    if (!/^https?:\/\//i.test(url)) return fail('INVALID_INPUT', '仅支持打开 http/https 链接')
    try {
      await shell.openExternal(url)
      return ok(null)
    } catch (err) {
      console.log(`[app] 打开外链失败：${err instanceof Error ? err.message : String(err)}`)
      return fail('OPEN_EXTERNAL_FAILED', '无法打开浏览器，请手动访问 mnb-lab.cn')
    }
  })

  // M8-3 §5：steering —— 任务进行中用户补充要求（轮边界注入）
  ipcMain.handle(IPC.AGENT_STEER, (_e, p): IpcResult<null> =>
    tryRun(() => {
      auth.requireUser()
      const sessionId = String((p as { sessionId?: string })?.sessionId ?? '')
      const text = String((p as { text?: string })?.text ?? '')
      if (sessionId && text.trim()) agentLoop.steer(sessionId, text)
      return null
    })
  )

  // M8-2 §2 配置化：写入上下文预算（部分更新；范围校验后持久化并立即生效）
  ipcMain.handle(IPC.AGENT_CONTEXT_SET, (_e, p): IpcResult<unknown> =>
    tryRun(() => {
      const uid = auth.requireUser().id
      const merged = normalizePruneConfig({ ...readContextConfig(), ...((p ?? {}) as Record<string, unknown>) })
      settings.set(CONTEXT_CONFIG_KEY, merged, uid)
      agentLoop.setContextConfig(merged)
      console.log(
        `[context] 预算配置已更新：window=${merged.windowTokens} 触发=${merged.triggerRatio} 目标=${merged.targetRatio} 近端=${merged.keepRecentRounds} 轮`
      )
      return merged
    })
  )

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

  // ---------- 每日定时备份（R-9 B）----------
  // 端口全部由既有能力注入：密码复用「退出自动备份」的 safeStorage 链路，打包/清理复用
  // BackupService，通知复用 M4 的 desktopNotify。节拍与体积闸在 daily-backup.ts（纯函数）。
  const DAILY_KEY_CONFIG = 'backup.daily.config'
  const DAILY_KEY_LAST = 'backup.daily.last'
  const DAILY_KEY_TARGET = 'backup.daily.targetDir'
  const currentUserId = (): string | null => {
    try {
      return auth.requireUser().id
    } catch {
      return null // 未登录时不触发定时备份
    }
  }
  const dailyBackup = new DailyBackupService({
    readConfig: () => settings.get(DAILY_KEY_CONFIG, currentUserId() ?? undefined),
    writeConfig: (cfg) => settings.set(DAILY_KEY_CONFIG, cfg, currentUserId() ?? undefined),
    // 日期键由 last.at 用**本地时区**推导（与 daily-backup 的 localDateKey 同口径，
    // 不能用 toISOString —— 那是 UTC，跨时区会错一天）
    readLastRunDate: () => {
      const r = settings.get(DAILY_KEY_LAST, currentUserId() ?? undefined) as DailyBackupResult | null
      return r && typeof r.at === 'number' ? localDateKey(r.at) : null
    },
    // 日期键不单独落库：它就是 last.at 的本地日期投影，避免两个键互相漂移
    writeLastRunDate: () => undefined,
    readLastResult: () => (settings.get(DAILY_KEY_LAST, currentUserId() ?? undefined) as DailyBackupResult | null) ?? null,
    writeLastResult: (r) => settings.set(DAILY_KEY_LAST, r, currentUserId() ?? undefined),
    getPassword: () => {
      const uid = currentUserId()
      return uid ? readExitPassword(uid) : null
    },
    getTargetDir: () => String(settings.get(DAILY_KEY_TARGET, currentUserId() ?? undefined) ?? '').trim() || backupDir,
    createBackup: (o) => backup.createBackup(o),
    applyRetention: (dir, o) => backup.applyRetention(dir, o),
    measureFilesBytes: () => backup.measureFilesBytes(),
    notify: (title, body) => desktopNotify(title, body, () => undefined),
    log: (m) => console.log(`[daily-backup] ${m}`)
  })
  dailyBackup.start()

  // M8-2 预算配置：在 currentUserId 就绪后读取并应用（未配置 → 默认值 = 现行为，零变更）
  agentLoop.setContextConfig(readContextConfig())
  // M8-3：注入权限端口（三层 store）；未配置任何规则时判定结果 = 现行为
  agentLoop.setPermissionPort(permissionPort)

  // M2-3a+ 统一登录：父级账号登录 → 云端身份关联 + 首次认领本机历史数据
  ipcMain.handle(IPC.AUTH_CLOUD_LOGIN, async (_e, p): Promise<IpcResult<unknown>> => {
    const payload = (p ?? {}) as { baseUrl?: string; username?: string; password?: string }
    const username = String(payload.username ?? '').trim()
    const password = String(payload.password ?? '')
    if (!username || !password) {
      return fail('INVALID_INPUT', '请填写账号与密码')
    }
    try {
      const baseUrl = normalizeBaseUrl(payload.baseUrl ?? readCloudState().baseUrl)
      const client = makeCloudClient(baseUrl)
      const loginRes = await client.login(username, password)
      if (!loginRes.ok) {
        console.log(`[auth] 云端登录失败（${loginRes.error.kind}）：${loginRes.error.detail ?? ''}`)
        return fail(`CLOUD_${loginRes.error.kind.toUpperCase().replace('-', '_')}`, loginRes.error.message)
      }
      // 取父级身份（用于认领映射与展示）
      const meRes = await client.me(loginRes.data.accessToken)
      if (!meRes.ok) {
        return fail(`CLOUD_${meRes.error.kind.toUpperCase().replace('-', '_')}`, meRes.error.message)
      }
      // ★ 顺序铁律（DL-1 根因修复）：必须先建立本地会话，再写**按用户隔离**的令牌。
      //   旧顺序先写令牌/状态（用旧或空用户 id 作键），而读取时用新身份 → 键不匹配
      //   → 登录成功却永远读不到 → 知识库/网盘误显「未绑定」。
      const cloudLogin = auth.loginWithCloud({ cloudUserId: String(meRes.data.id), cloudUsername: meRes.data.name })
      writeCloudTokens(loginRes.data)
      writeCloudBaseUrl(baseUrl)
      console.log(`[auth] 云端登录成功：${meRes.data.name}（首次接入=${cloudLogin.firstClaim}）`)
      // ★ 工单 ZB：零感托管备份 —— 登录即生效（既有手工配置零覆盖；离线顺延）
      try {
        const probe = probeFromSettings((k) => settings.get(k, auth.requireUser().id))
        const plan = planAutoProvision({ probe, cloudUsername: meRes.data.name })
        if (plan.provision && plan.config) {
          settings.set('backup.daily.config', plan.config, auth.requireUser().id)
          console.log('[backup] 已自动启用零感托管备份（每日 + 保留 7 份；云端 backups/ 目录）')
          // 首次登录立刻跑一次（零操作：用户什么都不用做）；失败不影响登录
          void cloudBackup.runOnce({ enabled: true, keep: plan.config.keep }).catch(() => undefined)
        } else {
          console.log(`[backup] 跳过自动配置（${plan.reason}）`)
        }
      } catch (e) {
        console.log(`[backup] 自动配置异常（不影响登录）：${e instanceof Error ? e.message : String(e)}`)
      }
      return ok({
        user: cloudLogin.session.user,
        expiresAt: cloudLogin.session.expiresAt,
        firstClaim: cloudLogin.firstClaim,
        claimedCounts: cloudLogin.claimedCounts,
        summary: cloudLogin.summary,
        cloudUsername: meRes.data.name
      })
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      console.log(`[auth] 云端登录异常：${msg}`)
      return fail('CLOUD_NETWORK', '无法连接云端服务器，请检查网络或服务器地址。')
    }
  })

  // M2-3b：远程知识库服务 —— **必须晚于 currentUserId 声明**（readCloudState 内部依赖它，
  // 否则触发 TDZ「Cannot access 'currentUserId' before initialization」导致启动即崩；
  // M8-2 已在同位置踩过同一个坑，真机首启再次抓到）。
  // 本地知识库服务实例保留但不接线 —— 本地遗留数据不迁移、不删除（工单 §4 硬边界）。
  void knowledge
  // M2-3c：远程网盘 —— 同样必须晚于 currentUserId 声明（TDZ 教训）
  // 上传会话持久化到 settings（断点续传跨重启可用）
  // 内存索引 + settings 持久化：settings 提供 get/set，没有「按前缀列出」，
  // 故用内存 Map 记账（进程内可列），settings 负责跨重启恢复。
  const driveSessionIndex = new Map<string, UploadSession>()
  const driveSessionStore: SessionStore = {
    get: (key) => {
      const raw = settings.get(`drive.upload.${key}`, currentUserId() ?? undefined) as UploadSession | null | undefined
      const s = raw && typeof raw.uploadId === 'string' ? raw : null
      if (s) driveSessionIndex.set(key, s)
      return s
    },
    set: (key, session) => {
      driveSessionIndex.set(key, session)
      settings.set(`drive.upload.${key}`, session, currentUserId() ?? undefined)
    },
    remove: (key) => {
      driveSessionIndex.delete(key)
      settings.set(`drive.upload.${key}`, null, currentUserId() ?? undefined)
    },
    list: () => [...driveSessionIndex.values()]
  }
  remoteDrive = new RemoteDriveService({
    client: makeCloudClient(readCloudState().baseUrl),
    tokens: () => readCloudTokens(),
    // DL-1：数据源取机器级地址元数据（旧状态存储已废除，读它会回落到默认主机 → 请求打错服务器）
    baseUrl: () => readCloudBaseUrl(),
    sessions: driveSessionStore,
    onTokensRefreshed: (t) => writeCloudTokens(t),
    log: (m) => console.log(m)
  })

  // 工单 ZB：零感托管备份执行器（复用 M2-3c 云端通道；密钥走 safeStorage）
  cloudBackup = new CloudBackupService({
    getCloudUsername: () => auth.cloudIdentityOfCurrentUser(),
    getProtectionKey: () => {
      const enc = settings.get('backup.cloud.key', currentUserId() ?? undefined) as string | undefined
      if (!enc) return null
      try {
        return cipher.decrypt(enc) || null
      } catch {
        return null
      }
    },
    setProtectionKey: (key) => {
      const enc = cipher.encrypt(key)
      if (enc) settings.set('backup.cloud.key', enc, currentUserId() ?? undefined)
    },
    packContainer: async () => {
      // 复用既有容器打包（数据库 + 附件清单）；此处只打数据库主文件，附件走既有 measureFilesBytes 闸
      const { readFileSync } = await import('node:fs')
      const bytes = readFileSync(dbPath)
      const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 16).replace('T', '-')
      return { fileName: `workbench-${stamp.replace(/-/g, '').slice(0, 13)}-1.mnbbak`, bytes: new Uint8Array(bytes) }
    },
    uploadFile: async (remotePath, bytes) => {
      // 复用 M2-3c 分块通道：小文件走简化路径，大文件分块
      const parts = remotePath.split('/')
      const name = parts.pop() ?? 'backup.mnbbak'
      const r = await remoteDrive.upload({
        filename: name,
        fileSize: bytes.length,
        readChunk: async (offset, length) => bytes.subarray(offset, offset + length)
      })
      if (!r.ok) return { ok: false, error: driveErrorMessage(r.error) }
      return { ok: true }
    },
    listRemote: async (remoteDir) => {
      const r = await remoteDrive.list({ keyword: remoteDir.split('/').pop() ?? '' })
      if (!r.ok) return { ok: false, error: driveErrorMessage(r.error) }
      return {
        ok: true,
        entries: r.data.items.map((i) => ({ name: i.fileName, createdAt: Date.parse(i.updatedAt ?? '') || 0 }))
      }
    },
    deleteRemote: async (remotePath) => {
      const r = await remoteDrive.list({ keyword: remotePath.split('/').pop() ?? '' })
      if (!r.ok) return { ok: false, error: driveErrorMessage(r.error) }
      const hit = r.data.items.find((i) => i.fileName === remotePath.split('/').pop())
      if (!hit) return { ok: false, error: '未找到远端文件' }
      const del = await remoteDrive.remove(hit.id)
      return del.ok ? { ok: true } : { ok: false, error: driveErrorMessage(del.error) }
    },
    isOnline: () => true, // 实际在线判定由上传失败驱动（离线时上传即失败 → 顺延）
    notify: (title, body) => {
      try {
        const { Notification } = require('electron') as typeof import('electron')
        if (Notification.isSupported()) new Notification({ title, body }).show()
      } catch {
        /* 通知不可用不影响备份 */
      }
    },
    log: (m) => console.log(m)
  })

  remoteKnowledge = new RemoteKnowledgeService({
    client: makeCloudClient(readCloudState().baseUrl),
    tokens: () => readCloudTokens(),
    // 每次请求前按当前绑定刷新地址（用户可能中途改服务器）
    // DL-1：数据源取机器级地址元数据（旧状态存储已废除，读它会回落到默认主机 → 请求打错服务器）
    baseUrl: () => readCloudBaseUrl(),
    onTokensRefreshed: (t) => writeCloudTokens(t),
    log: (m) => console.log(m)
  })

  ipcMain.handle(IPC.BACKUP_DAILY_GET, (): IpcResult<unknown> => tryRun(() => dailyBackup.snapshot()))
  ipcMain.handle(IPC.BACKUP_DAILY_SET, (_e, p): IpcResult<unknown> =>
    tryRun(() => {
      const patch = (p ?? {}) as Record<string, unknown>
      if (typeof patch.targetDir === 'string') {
        settings.set(DAILY_KEY_TARGET, patch.targetDir.trim(), currentUserId() ?? undefined)
      }
      return dailyBackup.updateConfig(patch)
    })
  )
  // 注意：tryRun 是**同步**的（ok(fn())），传 async 回调仍会把 Promise 包进返回值，
  // 被 Electron 结构化克隆拒绝（实测报 "An object could not be cloned"）。异步 handler
  // 必须像 BACKUP_CREATE 那样显式 await（沿用同一模式）。
  ipcMain.handle(IPC.BACKUP_DAILY_RUN, async (): Promise<IpcResult<unknown>> => {
    try {
      return ok(await dailyBackup.runNow('manual'))
    } catch (err) {
      const e = err as Error & { code?: string }
      return fail(e.code ?? 'ERROR', e.message)
    }
  })

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
