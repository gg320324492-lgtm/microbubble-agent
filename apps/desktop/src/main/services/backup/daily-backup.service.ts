// 每日定时备份调度（R-9 B）— 零 Electron import；备份/通知/设置全部以原语注入，离线可测。
//
// 职责边界：本服务只做「什么时候跑 + 跑完怎么记账/通知」；真正的打包与清理在 BackupService。
// 节拍判定与体积闸是纯函数（daily-backup.ts），本文件只负责接线与副作用。
import {
  BACKUP_MAX_FILES_BYTES,
  DEFAULT_DAILY_BACKUP_CONFIG,
  assertFilesSizeWithinLimit,
  decideDailyBackup,
  localDateKey,
  normalizeDailyBackupConfig,
  type DailyBackupConfig,
  type DailyBackupResult
} from './daily-backup'
import { BACKUP_DEFAULT_PREFIX } from '@shared/backup-naming'

/** 心跳间隔：60s 足够（最小节拍粒度是分钟） */
export const DAILY_BACKUP_TICK_MS = 60_000

export interface DailyBackupPorts {
  /** 读取持久化配置（原始值，由本服务归一化） */
  readConfig: () => unknown
  writeConfig: (cfg: DailyBackupConfig) => void
  /** 读取上次执行的本地日期键 */
  readLastRunDate: () => string | null
  writeLastRunDate: (dateKey: string) => void
  /** 读取最近一次结果（设置页展示） */
  readLastResult: () => DailyBackupResult | null
  writeLastResult: (r: DailyBackupResult) => void
  /** 备份密码（未配置则返回 null → 定时备份不生效） */
  getPassword: () => string | null
  /** 目标目录（本地/UNC/映射盘均可） */
  getTargetDir: () => string
  /** 执行一次打包，返回产物文件名与大小 */
  createBackup: (opts: { password: string; targetDir: string }) => Promise<{ fileName: string; size: number }>
  /** 保留清理，返回删除的文件名 */
  applyRetention: (targetDir: string, opts: { prefix?: string; keep: number }) => { deleted: string[] }
  /** 测量附件体积（整内存打包前的硬闸） */
  measureFilesBytes: () => number
  /** 系统通知（失败可感知） */
  notify: (title: string, body: string) => void
  log?: (message: string) => void
}

export class DailyBackupService {
  private timer: ReturnType<typeof setInterval> | null = null
  private readonly sessionStartedAt = Date.now()
  private running = false

  constructor(private readonly ports: DailyBackupPorts) {}

  /** 启动心跳（幂等）。仅在应用运行期跑，进程退出即随之中止。 */
  start(): void {
    if (this.timer) return
    this.timer = setInterval(() => void this.tick(), DAILY_BACKUP_TICK_MS)
    this.timer.unref?.()
    this.log('每日定时备份调度已启动（心跳 60s）')
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer)
    this.timer = null
  }

  /** 供设置页读取：配置 + 最近结果 + 目标目录 + 密码是否已配置 */
  snapshot(): {
    config: DailyBackupConfig
    last: DailyBackupResult | null
    targetDir: string
    passwordConfigured: boolean
    lastRunDate: string | null
    /** 下次自动备份时刻（供设置页状态行展示）；无计划时为 null */
    nextRunAt: number | null
  } {
    const config = normalizeDailyBackupConfig(this.ports.readConfig())
    const lastRunDate = this.ports.readLastRunDate()
    // 「下次自动」= 今日判定里的 dueAt；已跑过今天则算明日（仅用于展示，不参与调度）
    const decision = decideDailyBackup({ config, sessionStartedAt: this.sessionStartedAt, lastRunDate, now: Date.now() })
    const nextRunAt = decision.dueAt === null ? null : lastRunDate === localDateKey(Date.now()) ? decision.dueAt + 24 * 60 * 60 * 1000 : decision.dueAt
    return {
      config,
      last: this.ports.readLastResult(),
      targetDir: this.ports.getTargetDir(),
      passwordConfigured: this.ports.getPassword() !== null,
      lastRunDate,
      nextRunAt
    }
  }

  /** 供设置页写入：部分更新并归一化 */
  updateConfig(patch: unknown): DailyBackupConfig {
    const merged = normalizeDailyBackupConfig({ ...(normalizeDailyBackupConfig(this.ports.readConfig()) as object), ...(patch as object) })
    this.ports.writeConfig(merged)
    return merged
  }

  /** 心跳：每分钟判定一次 */
  private async tick(): Promise<void> {
    if (this.running) return
    const config = normalizeDailyBackupConfig(this.ports.readConfig())
    const decision = decideDailyBackup({
      config,
      sessionStartedAt: this.sessionStartedAt,
      lastRunDate: this.ports.readLastRunDate(),
      now: Date.now()
    })
    if (!decision.due) return
    this.log(`定时备份触发（${decision.reason}）`)
    await this.runNow(decision.reason)
  }

  /**
   * 立即执行一轮（心跳触发或设置页「立即备份一次」）。
   * 无论成功失败都写 lastRunDate —— 「当天最多一次」以**尝试**为准，避免失败后每分钟重试打爆。
   */
  async runNow(reason: string): Promise<DailyBackupResult> {
    if (this.running) return this.ports.readLastResult() ?? { at: Date.now(), ok: false, error: '已有备份在进行中' }
    this.running = true
    const at = Date.now()
    const today = localDateKey(at)
    const config = normalizeDailyBackupConfig(this.ports.readConfig())
    try {
      const password = this.ports.getPassword()
      if (!password) {
        // 「未配置密码」不是一次备份尝试：**不占用当天名额**，也不写 last 结果。
        // 否则用户当天补配密码后要等到第二天才会跑（实测踩到）。
        return { at, ok: false, error: '未配置备份密码，定时备份不生效' }
      }

      // 体积硬闸：当前容器为整内存打包，超限明确报错并跳过（不静默失败）
      const bytes = this.ports.measureFilesBytes()
      const sizeOk = assertFilesSizeWithinLimit(bytes, BACKUP_MAX_FILES_BYTES)
      if (!sizeOk.ok) {
        const r: DailyBackupResult = { at, ok: false, error: sizeOk.reason }
        this.finish(r, today)
        this.ports.notify('定时备份已跳过', String(sizeOk.reason))
        return r
      }

      const targetDir = this.ports.getTargetDir()
      const { fileName, size } = await this.ports.createBackup({ password, targetDir })
      const { deleted } = this.ports.applyRetention(targetDir, { prefix: BACKUP_DEFAULT_PREFIX, keep: config.keep })
      const r: DailyBackupResult = { at, ok: true, fileName, size, deleted: deleted.length }
      this.finish(r, today)
      this.log(`定时备份完成：${fileName}（${size} bytes，清理 ${deleted.length} 份，触发=${reason}）`)
      return r
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e)
      const r: DailyBackupResult = { at, ok: false, error: message }
      this.finish(r, today)
      // 失败可感知：系统通知 + 设置页展示（工单硬要求）
      this.ports.notify('定时备份失败', message)
      this.log(`定时备份失败：${message}`)
      return r
    } finally {
      this.running = false
    }
  }

  private finish(r: DailyBackupResult, dateKey: string): void {
    this.ports.writeLastResult(r)
    this.ports.writeLastRunDate(dateKey)
  }

  private log(message: string): void {
    ;(this.ports.log ?? ((m: string) => console.log(`[daily-backup] ${m}`)))(message)
  }
}

export { DEFAULT_DAILY_BACKUP_CONFIG }
