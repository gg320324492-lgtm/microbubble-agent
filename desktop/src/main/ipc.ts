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

  // ---------- Phase 8-M0-H0: AppConfig / LocalPersistence / Logger ----------
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
}
