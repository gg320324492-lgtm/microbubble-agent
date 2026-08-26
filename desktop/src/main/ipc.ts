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
import type { AppConfigShape } from '@shared/config'

// 注入 AppConfig (在 bootstrapApp 中通过 resolveAppConfig() 计算)
let appConfigSnapshot: AppConfigShape | null = null

export function setAppConfig(cfg: AppConfigShape): void {
  appConfigSnapshot = cfg
}

export function getAppConfigSnapshot(): AppConfigShape | null {
  return appConfigSnapshot
}

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

  // ---------- Phase 8-M1-B: SQLite Database IPC Bridge ----------
  ipcMain.handle('db:status', async () => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return { open: false, path: '', version: 0 }
    return svc.status()
  })
  ipcMain.handle('db:query', async (_e, payload: { sql: string; params?: unknown[] }) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return { rows: [], changes: 0 }
    try {
      const params = (payload.params ?? []) as Array<string | number | bigint | Buffer | null>
      const rows = svc.db.query<unknown>(payload.sql, params)
      svc.audit.record({ action: 'db.query', module: 'database', metadata: { sql: payload.sql, count: rows.length } })
      return { rows, changes: 0 }
    } catch (err) {
      svc.audit.record({ action: 'db.query.error', module: 'database', metadata: { sql: payload.sql, error: String(err) } })
      return { rows: [], changes: 0 }
    }
  })
  ipcMain.handle('db:insert', async (_e, payload: { table: string; data: Record<string, unknown> }) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return null
    const cols = Object.keys(payload.data)
    const placeholders = cols.map(() => '?').join(', ')
    const values = cols.map((c) => payload.data[c] as string | number | bigint | Buffer | null)
    const sql = `INSERT INTO ${payload.table} (${cols.join(', ')}) VALUES (${placeholders})`
    const result = svc.db.execute(sql, values)
    svc.audit.record({ action: `${payload.table}.create`, module: 'database', metadata: { lastInsertRowid: Number(result.lastInsertRowid) } })
    return { ...payload.data, id: Number(result.lastInsertRowid) }
  })
  ipcMain.handle('db:update', async (_e, payload: { table: string; id: string | number; patch: Record<string, unknown> }) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return null
    const cols = Object.keys(payload.patch)
    const setClause = cols.map((c) => `${c} = ?`).join(', ')
    const values = cols.map((c) => payload.patch[c] as string | number | bigint | Buffer | null)
    values.push(payload.id)
    const sql = `UPDATE ${payload.table} SET ${setClause} WHERE id = ?`
    const result = svc.db.execute(sql, values)
    svc.audit.record({ action: `${payload.table}.update`, module: 'database', metadata: { id: payload.id, changes: result.changes } })
    return result.changes > 0 ? { ...payload.patch, id: payload.id } : null
  })
  ipcMain.handle('db:delete', async (_e, payload: { table: string; id: string | number }) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return { deleted: false }
    const result = svc.db.execute(`DELETE FROM ${payload.table} WHERE id = ?`, [payload.id])
    svc.audit.record({ action: `${payload.table}.delete`, module: 'database', metadata: { id: payload.id, changes: result.changes } })
    return { deleted: result.changes > 0 }
  })

  // ---------- Phase 8-M1-C: Scientific Data Engine IPC Bridge ----------
  ipcMain.handle('data:sample.create', async (_e, sample: Record<string, unknown>) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return null
    const created = svc.samples.create(sample as never)
    svc.audit.record({ action: 'sample.create', module: 'dataEngine', metadata: { id: created.id, experimentId: created.experimentId } })
    return created as unknown as Record<string, unknown>
  })
  ipcMain.handle('data:sample.list', async (_e, experimentId: string) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return []
    return svc.samples.listByExperiment(experimentId) as unknown as Record<string, unknown>[]
  })
  ipcMain.handle('data:sample.delete', async (_e, sampleId: string) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return { deleted: false }
    const result = svc.samples.delete(sampleId)
    svc.audit.record({ action: 'sample.delete', module: 'dataEngine', metadata: { id: sampleId, deleted: result } })
    return { deleted: result }
  })
  ipcMain.handle('data:analysis.create', async (_e, result: Record<string, unknown>) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return null
    const created = svc.analysisResults.create(result as never)
    svc.audit.record({ action: 'analysis.create', module: 'dataEngine', metadata: { id: created.id, runType: created.runType } })
    return created as unknown as Record<string, unknown>
  })
  ipcMain.handle('data:analysis.list', async (_e, experimentId: string) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return []
    return svc.analysisResults.listByExperiment(experimentId) as unknown as Record<string, unknown>[]
  })
  ipcMain.handle('data:analysis.param', async (_e, param: Record<string, unknown>) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return null
    return svc.analysisResults.addModelParam(param as never) as unknown as Record<string, unknown>
  })
  ipcMain.handle('data:analysis.params', async (_e, analysisId: string) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return []
    return svc.analysisResults.listModelParams(analysisId) as unknown as Record<string, unknown>[]
  })
  ipcMain.handle('data:figure.create', async (_e, figure: Record<string, unknown>) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return null
    return svc.figures.create(figure as never) as unknown as Record<string, unknown>
  })
  ipcMain.handle('data:figure.listByExperiment', async (_e, experimentId: string) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return []
    return svc.figures.listByExperiment(experimentId) as unknown as Record<string, unknown>[]
  })
  ipcMain.handle('data:figure.listByAnalysis', async (_e, analysisId: string) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return []
    return svc.figures.listByAnalysis(analysisId) as unknown as Record<string, unknown>[]
  })

  // ---------- Phase 8-M1-D: Scientific Analysis Engine IPC Bridge ----------
  ipcMain.handle('analysis:run.kinetic', async (_e, payload: { experimentId: string; model: 'first-order' | 'zero-order' | 'pseudo-second-order'; metric: string }) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return ''
    const id = svc.analysisEngine.runKinetic(payload.experimentId, payload.model, payload.metric)
    svc.audit.record({ action: 'analysis.kinetic', module: 'analysis', metadata: { id, model: payload.model, metric: payload.metric } })
    return id
  })
  ipcMain.handle('analysis:run.regression', async (_e, payload: { experimentId: string; xMetric: string; yMetric: string; degree: 1 | 2 | 3 | 4 }) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return ''
    return svc.analysisEngine.runRegression(payload.experimentId, payload.xMetric, payload.yMetric, payload.degree)
  })
  ipcMain.handle('analysis:run.correlation', async (_e, payload: { experimentId: string; xMetric: string; yMetric: string }) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return ''
    return svc.analysisEngine.runCorrelation(payload.experimentId, payload.xMetric, payload.yMetric)
  })
  ipcMain.handle('analysis:run.curve', async (_e, payload: { experimentId: string; family: 'exponential-decay' | 'logarithmic' | 'power-law' | 'gaussian'; metric: string }) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return ''
    return svc.analysisEngine.runCurve(payload.experimentId, payload.family, payload.metric)
  })
  ipcMain.handle('analysis:list', async (_e, experimentId: string) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return []
    return svc.analysisEngine.listByExperiment(experimentId)
  })
  ipcMain.handle('analysis:statistics', async (_e, payload: { experimentId: string; metric: string }) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return { summary: { metric: payload.metric, count: 0, missingRate: 1, mean: null, std: null, median: null, min: null, max: null, p25: null, p75: null, outliers: 0, interpretation: 'no data' }, n: 0 }
    return svc.analysisEngine.statistics(payload.experimentId, payload.metric)
  })

  // ---------- Phase 8-M1-E: Agent IPC Bridge ----------
  ipcMain.handle('agent:tool.list', async () => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return []
    return svc.agent.listTools()
  })
  ipcMain.handle('agent:tool.invoke', async (_e, payload: { name: string; params: Record<string, unknown> }) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) throw new Error('数据库未就绪')
    const result = await svc.agent.invokeTool(payload.name, payload.params)
    svc.audit.record({ action: 'tool.invoke', module: 'agent', metadata: { name: payload.name, ok: true } })
    return result
  })
  ipcMain.handle('agent:chat.send', async (_e, payload: { sessionId: string; role: 'user' | 'assistant'; content: string; toolName?: string; toolResult?: string }) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return { ok: false }
    svc.agent.recordMessage(payload.sessionId, payload.role, payload.content, payload.toolName, payload.toolResult)
    return { ok: true }
  })
  ipcMain.handle('agent:chat.history', async (_e, payload: { sessionId: string; limit?: number }) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return []
    return svc.agent.getHistory(payload.sessionId, payload.limit)
  })
  ipcMain.handle('agent:chat.search', async (_e, payload: { query: string; limit?: number }) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return []
    return svc.agent.searchMemory(payload.query, payload.limit)
  })
  ipcMain.handle('agent:chat.clear', async (_e, payload: { sessionId: string }) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return 0
    return svc.agent.clearMemory(payload.sessionId)
  })

  // ---------- Phase 8-M1-F: Device Control IPC Bridge ----------
  ipcMain.handle('device:list', async () => {
    const { getDeviceService } = await import('./services/device/device.service')
    return getDeviceService()?.status() ?? []
  })
  ipcMain.handle('device:connect', async (_e, payload: {
    deviceId: string; deviceType: 'ozone-generator' | 'pump' | 'reactor' | 'sensor' | 'ph-meter' | 'do-meter' | 'orp-meter' | 'flow-meter' | 'power-meter'
    endpoint: string; pollIntervalMs?: number; calibrationAt?: number; alarmLow?: number | null; alarmHigh?: number | null
  }) => {
    const { getDeviceService, bootstrapDeviceService } = await import('./services/device/device.service')
    const { getDatabaseService } = await import('./services/database.service')
    const ds = getDeviceService() ?? bootstrapDeviceService(() => getDatabaseService())
    await ds.connect(payload as never)
    return { ok: true }
  })
  ipcMain.handle('device:disconnect', async (_e, payload: { deviceId: string }) => {
    const { getDeviceService } = await import('./services/device/device.service')
    await getDeviceService()?.disconnect(payload.deviceId)
    return { ok: true }
  })
  ipcMain.handle('device:telemetry', async (_e, payload: { deviceId: string; sinceMs?: number }) => {
    const { getDeviceService } = await import('./services/device/device.service')
    return getDeviceService()?.telemetry(payload.deviceId, payload.sinceMs) ?? []
  })
  ipcMain.handle('device:alarm.list', async (_e, payload: { deviceId?: string }) => {
    const { getDeviceService } = await import('./services/device/device.service')
    return getDeviceService()?.alarms(payload.deviceId) ?? []
  })
  ipcMain.handle('device:command', async (_e, payload: {
    deviceId: string
    deviceType: 'ozone-generator' | 'pump' | 'reactor' | 'sensor' | 'ph-meter' | 'do-meter' | 'orp-meter' | 'flow-meter' | 'power-meter'
    endpoint: string
    kind: 'set-setpoint' | 'start' | 'stop' | 'calibrate' | 'reset-alarm'
    metric?: string; value?: number; reason?: string; operator?: string
  }) => {
    const { getDeviceService } = await import('./services/device/device.service')
    const ds = getDeviceService()
    if (!ds) throw new Error('DeviceService 未启动')
    return ds.command(
      { deviceId: payload.deviceId, deviceType: payload.deviceType, endpoint: payload.endpoint } as never,
      { kind: payload.kind, metric: payload.metric, value: payload.value, reason: payload.reason, operator: payload.operator }
    )
  })
  ipcMain.handle('device:status', async () => {
    const { getDeviceService } = await import('./services/device/device.service')
    return getDeviceService()?.status() ?? []
  })

  // ---------- Phase 8-M1-G: Product IPC (auth / config / backup / export / audit) ----------
  ipcMain.handle('app:user.login', async (_e, payload: { username: string; password: string }) => {
    let { getDatabaseService } = await import('./services/database.service')
    let svc = getDatabaseService()
    // Phase 10.6 hotfix: 如果 DB 未就绪 (e.g. bootstrapDatabase 在 registerIpcHandlers 之后), 尝试同步 bootstrap
    if (!svc) {
      const { bootstrapDatabase } = await import('./services/database.service')
      try {
        svc = bootstrapDatabase()
      } catch (e) {
        return { ok: false, message: `数据库初始化失败: ${e instanceof Error ? e.message : String(e)}` }
      }
    }
    if (!svc) return { ok: false, message: '数据库未就绪' }
    try {
      const result = svc.product.auth.login(payload.username, payload.password)
      return { ok: true, user: result.user, session: result.session, token: result.token }
    } catch (err) {
      return { ok: false, message: err instanceof Error ? err.message : '登录失败' }
    }
  })
  // 注: 'app:auth:login' channel 由 IPC_CHANNELS.AUTH_LOGIN (line 52-57) 注册,
  // 走远端 fetch 路径. 这里不重复注册避免 "Attempted to register a second handler" 错误.
  ipcMain.handle('app:user.logout', async (_e, payload: { token: string }) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return false
    return svc.product.auth.logout(payload.token)
  })
  ipcMain.handle('app:user.list', async () => {
    const { getDatabaseService } = await import('./services/database.service')
    return getDatabaseService()?.product.auth.listUsers() ?? []
  })
  ipcMain.handle('app:user.create', async (_e, payload: { username: string; password: string; displayName?: string; role?: 'admin' | 'researcher' | 'viewer' | 'operator' }) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return null
    try {
      return svc.product.auth.createUser(payload)
    } catch (err) {
      return { error: err instanceof Error ? err.message : '创建失败' }
    }
  })
  ipcMain.handle('app:config.get', async (_e, payload: { scope: 'system' | 'user' | 'project'; key: string }) => {
    const { getDatabaseService } = await import('./services/database.service')
    return getDatabaseService()?.product.config.get(payload.scope, payload.key) ?? null
  })
  ipcMain.handle('app:config.set', async (_e, payload: { scope: 'system' | 'user' | 'project'; key: string; value: unknown; valueType?: 'string' | 'number' | 'boolean' | 'json'; isSensitive?: boolean }) => {
    const { getDatabaseService } = await import('./services/database.service')
    getDatabaseService()?.product.config.set(payload.scope, payload.key, payload.value, {
      valueType: payload.valueType,
      isSensitive: payload.isSensitive
    })
    return { ok: true }
  })
  ipcMain.handle('app:config.list', async (_e, payload: { scope?: 'system' | 'user' | 'project' }) => {
    const { getDatabaseService } = await import('./services/database.service')
    return getDatabaseService()?.product.config.list(payload.scope) ?? []
  })
  ipcMain.handle('backup:create', async (_e, payload: { createdBy?: string; note?: string }) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return null
    try {
      return svc.product.backup.create(payload)
    } catch (err) {
      return { error: err instanceof Error ? err.message : '备份失败' }
    }
  })
  ipcMain.handle('backup:list', async () => {
    const { getDatabaseService } = await import('./services/database.service')
    return getDatabaseService()?.product.backup.list() ?? []
  })
  ipcMain.handle('backup:restore', async (_e, payload: { backupId: string }) => {
    const { getDatabaseService } = await import('./services/database.service')
    return getDatabaseService()?.product.backup.restore(payload.backupId) ?? false
  })
  ipcMain.handle('export:csv', async (_e, payload: { table: string; where?: string; limit?: number; outputPath: string }) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return null
    try {
      return svc.product.exporter.export({ ...payload, format: 'csv' })
    } catch (err) {
      return { error: err instanceof Error ? err.message : '导出失败' }
    }
  })
  ipcMain.handle('export:json', async (_e, payload: { table: string; where?: string; limit?: number; outputPath: string }) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return null
    try {
      return svc.product.exporter.export({ ...payload, format: 'json' })
    } catch (err) {
      return { error: err instanceof Error ? err.message : '导出失败' }
    }
  })
  ipcMain.handle('audit:list', async (_e, payload: { limit?: number }) => {
    const { getDatabaseService } = await import('./services/database.service')
    return getDatabaseService()?.product.audit.list(payload?.limit) ?? []
  })
  ipcMain.handle('audit:verify', async () => {
    const { getDatabaseService } = await import('./services/database.service')
    return getDatabaseService()?.product.audit.verifyChain() ?? { ok: true, firstTamperedId: null, checked: 0 }
  })

  // ---------- Phase 9-A: Data Import IPC Bridge ----------
  ipcMain.handle('data:import.formats', async () => {
    const { SUPPORTED_FORMATS } = await import('./services/import')
    return SUPPORTED_FORMATS
  })
  ipcMain.handle('data:import.parse', async (_e, payload: { filePath: string; format?: 'csv' | 'xlsx' | 'json' }) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return null
    try {
      return await svc.importSvc.engine.parseFile(payload.filePath, payload.format)
    } catch (err) {
      return { error: err instanceof Error ? err.message : '解析失败' }
    }
  })
  ipcMain.handle('data:import.suggest', async (_e, payload: { raw: { columns: string[]; rows: Array<Record<string, string>> } }) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return null
    return svc.importSvc.engine.suggestMapping(payload.raw as never)
  })
  ipcMain.handle('data:import.validate', async (_e, payload: { raw: { columns: string[]; rows: Array<Record<string, string>> }; mapping: Record<string, 'timestamp' | 'metric' | 'value' | 'unit' | 'sample_batch' | 'replicate' | 'operator' | 'notes' | 'ignore'> }) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return null
    return svc.importSvc.engine.validate(payload.raw as never, payload.mapping)
  })
  ipcMain.handle('data:import.commit', async (_e, payload: { projectId: string; experimentName: string; mapping: Record<string, 'timestamp' | 'metric' | 'value' | 'unit' | 'sample_batch' | 'replicate' | 'operator' | 'notes' | 'ignore'>; raw: { columns: string[]; rows: Array<Record<string, string>>; sourceHash: string }; importedBy?: string }) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return null
    try {
      return await svc.importSvc.engine.commit({
        projectId: payload.projectId,
        experimentName: payload.experimentName,
        mapping: payload.mapping,
        raw: payload.raw as never,
        fileHash: payload.raw.sourceHash,
        importedBy: payload.importedBy
      })
    } catch (err) {
      return { error: err instanceof Error ? err.message : '提交失败' }
    }
  })
  ipcMain.handle('data:import.datasets', async (_e, payload: { projectId?: string }) => {
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return []
    return svc.importSvc.engine.listDatasets(payload?.projectId)
  })

  // ---------- Phase 9-B: Workflow IPC Bridge ----------
  ipcMain.handle('workflow:templates.list', async () => {
    const { getWorkflowService, bootstrapWorkflowService } = await import('./services/workflow.service')
    const { getDatabaseService } = await import('./services/database.service')
    const ds = getDatabaseService()
    if (!ds) return []
    return (getWorkflowService() ?? bootstrapWorkflowService(() => ds)).listTemplates()
  })
  ipcMain.handle('workflow:run.start', async (_e, payload: { templateId: string; parameters: Record<string, unknown>; startedBy?: string }) => {
    const { getWorkflowService, bootstrapWorkflowService } = await import('./services/workflow.service')
    const { getDatabaseService } = await import('./services/database.service')
    const ds = getDatabaseService()
    if (!ds) return null
    try {
      const run = await (getWorkflowService() ?? bootstrapWorkflowService(() => ds)).startRun(payload)
      return run
    } catch (err) {
      return { error: err instanceof Error ? err.message : '启动失败' }
    }
  })
  ipcMain.handle('workflow:run.status', async (_e, payload: { runId: string }) => {
    const { getWorkflowService } = await import('./services/workflow.service')
    return getWorkflowService()?.getRun(payload.runId) ?? null
  })
  ipcMain.handle('workflow:run.list', async (_e, payload: { limit?: number }) => {
    const { getWorkflowService, bootstrapWorkflowService } = await import('./services/workflow.service')
    const { getDatabaseService } = await import('./services/database.service')
    const ds = getDatabaseService()
    if (!ds) return []
    return (getWorkflowService() ?? bootstrapWorkflowService(() => ds)).listRuns(payload?.limit)
  })
  ipcMain.handle('workflow:run.cancel', async (_e, payload: { runId: string }) => {
    const { getWorkflowService } = await import('./services/workflow.service')
    return getWorkflowService()?.cancelRun(payload.runId) ?? false
  })
  ipcMain.handle('workflow:run.approve', async (_e, payload: { runId: string; stepId: string; approvedBy: string }) => {
    const { getWorkflowService } = await import('./services/workflow.service')
    return getWorkflowService()?.approveStep(payload.runId, payload.stepId, payload.approvedBy) ?? false
  })

  // ---------- Phase 8-M0-H0: AppConfig / LocalPersistence / Logger ----------
  // Phase 10.6 hotfix: 代理 fetch 远程 avatar URL → 返回 dataURL.
  // 沙箱 Electron renderer <img src=remote> 可能被 webSecurity/CSP 阻止.
  // main 进程 fetch URL 转 base64 dataURL, renderer 直接用.
  ipcMain.handle('app:avatar.fetch', async (_e, payload: { url: string }) => {
    if (!payload?.url || typeof payload.url !== 'string') return { ok: false, dataUrl: null, error: 'invalid url' }
    if (!payload.url.startsWith('https://')) return { ok: false, dataUrl: null, error: 'only https' }
    try {
      const resp = await fetch(payload.url)
      if (!resp.ok) return { ok: false, dataUrl: null, error: `HTTP ${resp.status}` }
      const buf = Buffer.from(await resp.arrayBuffer())
      const ct = resp.headers.get('content-type') ?? 'image/jpeg'
      const dataUrl = `data:${ct};base64,${buf.toString('base64')}`
      return { ok: true, dataUrl }
    } catch (err) {
      return { ok: false, dataUrl: null, error: err instanceof Error ? err.message : String(err) }
    }
  })

  ipcMain.handle('app:get-config', async () => appConfigSnapshot)
  ipcMain.handle('app:get-status', async () => {
    const { getBootstrapResult } = await import('./bootstrap')
    return getBootstrapResult()
  })
  ipcMain.handle('app:get-info', async () => {
    const { resolveApplicationInfo } = await import('./application-info')
    return resolveApplicationInfo()
  })
  ipcMain.handle('app:restart', async () => {
    const { app } = await import('electron')
    app.relaunch()
    app.exit(0)
    return { ok: true }
  })
  ipcMain.handle('app:quit', async () => {
    const { app } = await import('electron')
    app.quit()
    return { ok: true }
  })
  ipcMain.handle('app:check-update', async () => {
    const { updateService } = await import('./services/update-service')
    return updateService.checkUpdate()
  })
  ipcMain.handle('app:download-update', async () => {
    const { updateService } = await import('./services/update-service')
    return updateService.downloadUpdate()
  })
  ipcMain.handle('app:install-update', async () => {
    const { updateService } = await import('./services/update-service')
    return updateService.installUpdate()
  })
  ipcMain.handle('app:get-current-version', async () => {
    const { updateService } = await import('./services/update-service')
    return updateService.getCurrentVersion()
  })
  ipcMain.handle('persistence:save', async (_e, payload: { namespace: string; key: string; value: unknown }) => {
    const { persistence } = await import('./services/storage.service')
    await persistence.save(payload.namespace, payload.key, payload.value)
    return { ok: true }
  })
  ipcMain.handle('persistence:load', async (_e, payload: { namespace: string; key: string }) => {
    const { persistence } = await import('./services/storage.service')
    return persistence.load(payload.namespace, payload.key)
  })
  ipcMain.handle('persistence:remove', async (_e, payload: { namespace: string; key: string }) => {
    const { persistence } = await import('./services/storage.service')
    await persistence.remove(payload.namespace, payload.key)
    return { ok: true }
  })
  ipcMain.handle('logger:write', async (_e, payload: { level: string; module: string; message: string; metadata?: unknown }) => {
    const { logger } = await import('./services/storage.service')
    logger.write(payload.level as 'info' | 'warn' | 'error' | 'debug', payload.module, payload.message, payload.metadata)
    return { ok: true }
  })
  ipcMain.handle('logger:tail', async (_e, payload: { lines?: number }) => {
    const { logger } = await import('./services/storage.service')
    return logger.tail(payload?.lines ?? 100)
  })

  // ---------- R4: Migration (mbrp import into staging workspace) ----------
  // All three handlers defer to the same MbrpImporter instance so we share
  // databasePath / dataDir resolution with the rest of the desktop app.
  // The renderer must NEVER call these without an authenticated user (Phase 1
  // auth gate is applied at the renderer routing layer).
  // Phase 10.6 hotfix: wrap top-level await in IIFE (registerIpcHandlers is non-async).
  void (async () => {
  const { MbrpImporter } = await import('./migration/mbrp-importer')
  const { verifyMbrp } = await import('./migration/index')
  const { app } = await import('electron')
  const migrationImporter = new MbrpImporter({ dataDir: app.getPath('userData') })

  ipcMain.handle('migration:preflight', async (_e, payload: { packagePath: string }) => {
    if (!payload?.packagePath || typeof payload.packagePath !== 'string') {
      return { ok: false, code: 'INVALID_PACKAGE', message: 'packagePath required' }
    }
    return verifyMbrp(payload.packagePath)
  })

  ipcMain.handle('migration:import', async (_e, payload: { packagePath: string; snapshotId: string }) => {
    if (!payload?.packagePath || !payload?.snapshotId) {
      return { ok: false, code: 'INVALID_PACKAGE', message: 'packagePath + snapshotId required' }
    }
    return migrationImporter.importPackage(payload)
  })

  ipcMain.handle('migration:runs', async () => {
    // R4 minimal stub: history listing is wired in a follow-up patch once
    // the renderer needs it. Return [] so the renderer can guard.
    return []
  })
  })()  // end IIFE (Phase 10.6 hotfix: wrap mbrp top-level await)

  // ---------- Phase 11: PG Snapshot (单向 web → desktop 数据迁移) ----------
  // 触发器: 仅由 renderer 通过 IPC trigger, 凭据不暴露.
  ipcMain.handle('pg:snapshot.preflight', async () => {
    const { pgPreflight } = await import('./migration/pg-snapshot/pg-connector')
    return pgPreflight()
  })

  ipcMain.handle('pg:snapshot.history', async (_e, payload: { limit?: number }) => {
    const { listSnapshots } = await import('./migration/pg-snapshot/import-runner')
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return []
    return listSnapshots(svc, payload?.limit ?? 20)
  })

  ipcMain.handle('pg:snapshot.run', async (_e, payload: { tasks?: Array<{ pgTable: string; desktopTable: string; selectSql: string; transformerMap: Record<string, 'pgTimestampToEpochMs' | 'pgJsonToJsonString' | 'pgTextArrayToJsonString' | 'pgUuidString' | 'pgVectorDrop' | 'pgHalfVectorDrop' | 'truncateText' | 'passthrough'> }> }) => {
    // Phase 11 P11-1+: 接受 renderer 传来的 transformer spec, 动态 import transformers.
    const tasks = payload?.tasks ?? []
    if (tasks.length === 0) {
      // Stage 0 占位: 空任务 = sanity check
      const { runSnapshot } = await import('./migration/pg-snapshot/import-runner')
      const { getDatabaseService } = await import('./services/database.service')
      const svc = getDatabaseService()
      if (!svc) return { ok: false, error: '数据库未就绪' }
      return runSnapshot(svc, { tasks: [] })
    }
    // 动态 import transformers/<table>.ts, 解析 string → 函数
    const { runSnapshot } = await import('./migration/pg-snapshot/import-runner')
    const pipeline = await import('./migration/pg-snapshot/transform-pipeline')
    const transformerFns: Record<string, (v: unknown) => unknown> = {
      pgTimestampToEpochMs: pipeline.pgTimestampToEpochMs,
      pgJsonToJsonString: pipeline.pgJsonToJsonString,
      pgTextArrayToJsonString: pipeline.pgTextArrayToJsonString,
      pgUuidString: pipeline.pgUuidString,
      pgVectorDrop: pipeline.pgVectorDrop,
      pgHalfVectorDrop: pipeline.pgHalfVectorDrop,
      truncateText: pipeline.truncateText,
      passthrough: (v: unknown) => v
    }
    const resolvedTasks = tasks.map((t) => ({
      pgTable: t.pgTable,
      desktopTable: t.desktopTable,
      selectSql: t.selectSql,
      transformerMap: Object.fromEntries(
        Object.entries(t.transformerMap).map(([col, fnName]) => [col, transformerFns[fnName] ?? ((v: unknown) => v)])
      )
    }))
    const { getDatabaseService } = await import('./services/database.service')
    const svc = getDatabaseService()
    if (!svc) return { ok: false, error: '数据库未就绪' }
    return runSnapshot(svc, { tasks: resolvedTasks })
  })
}
