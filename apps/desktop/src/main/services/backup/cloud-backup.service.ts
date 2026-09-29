// 零感托管备份 —— 云端执行器（工单 ZB §1/§2/§3）
//
// 复用 M2-3c 已交付的**云端网盘分块上传通道**（零服务端改动）：
//   1. 本机打包容器（复用既有 packContainer）
//   2. 上传容器到该用户网盘 `backups/<用户>/`
//   3. **随容器同目录上传 `<容器名>.key.json`**（保护密钥托管，笔记本报废也能救）
//   4. 保留最近 7 份（连密钥一起删，且只动本应用命名模式的文件）
//
// ★ 依赖全部注入（上传/删除/列表/随机源/日志），单测零网络零 Electron ABI。

import { randomBytes } from 'node:crypto'
import {
  CLOUD_BACKUP_ROOT,
  buildKeyEnvelope,
  cloudBackupDir,
  generateProtectionKey,
  isManagedBackupName,
  keyFileName,
  planRetention,
  shouldRunNow,
  type BackupConfigProbe,
  type RemoteBackupEntry
} from './auto-provision'
import { MANAGED_BACKUP_PREFIXES } from '@shared/backup-naming'

export interface CloudBackupDeps {
  /** 云端身份（null = 未登录） */
  getCloudUsername: () => string | null
  /** 保护密钥（已配置则返回既有值；未配置返回 null） */
  getProtectionKey: () => string | null
  /** 持久化保护密钥（safeStorage 路线由装配层负责） */
  setProtectionKey: (key: string) => void
  /** 打包容器 → 返回文件名与字节 */
  packContainer: () => Promise<{ fileName: string; bytes: Uint8Array }>
  /** 上传（复用 M2-3c 分块通道）；remotePath 形如 backups/<user>/<file> */
  uploadFile: (remotePath: string, bytes: Uint8Array) => Promise<{ ok: boolean; error?: string }>
  /** 列远端备份目录 */
  listRemote: (remoteDir: string) => Promise<{ ok: boolean; entries?: RemoteBackupEntry[]; error?: string }>
  /** 删除远端文件 */
  deleteRemote: (remotePath: string) => Promise<{ ok: boolean; error?: string }>
  /** 在线判定（离线宽容：断网顺延） */
  isOnline: () => boolean
  /** 随机源（测试注入；生产默认 crypto.randomBytes） */
  random?: (size: number) => Uint8Array
  /** 系统通知（失败可感知） */
  notify?: (title: string, body: string) => void
  log?: (message: string) => void
}

export interface CloudBackupResult {
  ok: boolean
  /** 本次是否实际执行 */
  ran: boolean
  reason: 'ok' | 'offline-deferred' | 'not-logged-in' | 'not-due' | 'error'
  container?: string
  keyFile?: string
  bytes?: number
  /** 本次清理的文件名（含密钥） */
  deleted?: string[]
  error?: string
}

export interface CloudBackupConfig {
  keep: number
  /** 是否开启（零感：自动配置后为 true） */
  enabled: boolean
}

/** 远端路径拼接（统一用正斜杠） */
export function joinRemote(dir: string, name: string): string {
  return `${dir.replace(/\/+$/, '')}/${name}`
}

export class CloudBackupService {
  constructor(private readonly deps: CloudBackupDeps) {}

  private log(m: string): void {
    this.deps.log?.(m)
  }

  private rand(): (size: number) => Uint8Array {
    return this.deps.random ?? ((n: number) => new Uint8Array(randomBytes(n)))
  }

  /** 确保保护密钥存在（不存在则生成并持久化） */
  ensureProtectionKey(): string {
    const existing = this.deps.getProtectionKey()
    if (existing) return existing
    const key = generateProtectionKey(this.rand())
    this.deps.setProtectionKey(key)
    // ★ 只记长度，绝不记内容
    this.log(`[backup] 已生成保护密钥（长度 ${key.length}，内容不入日志）`)
    return key
  }

  /**
   * 执行一次云端备份（零感：调用方无需提供任何参数）。
   *
   * @param dueNow 是否到执行时点（定时器决定；手动触发可传 true）
   */
  async runOnce(cfg: CloudBackupConfig, dueNow = true): Promise<CloudBackupResult> {
    const username = this.deps.getCloudUsername()
    const gate = shouldRunNow({ online: this.deps.isOnline(), loggedIn: !!username, dueNow })
    if (!gate.run) {
      if (gate.reason === 'offline-deferred') {
        this.log('[backup] 当前离线，本次备份顺延到下次（不报错）')
      }
      // 未执行（离线顺延/未登录/未到点）都不是错误 —— 离线宽容：不报错，等下次
      return { ok: true, ran: false, reason: gate.reason }
    }
    if (!cfg.enabled) return { ok: true, ran: false, reason: 'not-due' }

    const remoteDir = cloudBackupDir(username as string)
    try {
      // 1) 打包
      const { fileName, bytes } = await this.deps.packContainer()
      // 2) 上传容器
      const up = await this.deps.uploadFile(joinRemote(remoteDir, fileName), bytes)
      if (!up.ok) {
        this.notifyFail('云端备份失败', up.error ?? '上传失败')
        return { ok: false, ran: true, reason: 'error', error: up.error }
      }
      // 3) 密钥托管（与容器同目录、同名后缀）
      const key = this.ensureProtectionKey()
      const keyName = keyFileName(fileName)
      const envelope = JSON.stringify(buildKeyEnvelope(key, Date.now()), null, 2)
      const keyUp = await this.deps.uploadFile(joinRemote(remoteDir, keyName), Buffer.from(envelope, 'utf8'))
      if (!keyUp.ok) {
        // 容器已上传但密钥托管失败 → 可感知但不视为整体失败（数据本身在）
        this.log(`[backup] 密钥托管上传失败：${keyUp.error ?? '未知'}`)
        this.notifyFail('备份密钥托管失败', '备份已上传，但密钥托管未成功，下次会重试')
      }
      // 4) 保留策略
      const deleted = await this.applyRetention(remoteDir, cfg.keep)
      this.log(
        `[backup] 云端备份完成：${fileName}（${bytes.length} bytes，清理 ${deleted.length} 项，目录 ${remoteDir}）`
      )
      return { ok: true, ran: true, reason: 'ok', container: fileName, keyFile: keyName, bytes: bytes.length, deleted }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      this.log(`[backup] 云端备份异常：${msg}`)
      this.notifyFail('云端备份异常', msg)
      return { ok: false, ran: true, reason: 'error', error: msg }
    }
  }

  /** 保留最近 keep 份（连密钥一起删；只动本应用命名模式） */
  async applyRetention(remoteDir: string, keep: number): Promise<string[]> {
    const listed = await this.deps.listRemote(remoteDir)
    if (!listed.ok || !listed.entries) {
      this.log(`[backup] 列出远端备份失败，跳过清理：${listed.error ?? '未知'}`)
      return []
    }
    const plan = planRetention(listed.entries, keep, (n) => isManagedBackupName(n, MANAGED_BACKUP_PREFIXES))
    const deleted: string[] = []
    for (const name of plan.remove) {
      const r = await this.deps.deleteRemote(joinRemote(remoteDir, name))
      if (r.ok) deleted.push(name)
      else this.log(`[backup] 删除远端文件失败：${name}`)
    }
    return deleted
  }

  private notifyFail(title: string, body: string): void {
    // DL-7 Part C：失败必须落主进程日志（演练 ④：只弹通知零痕迹，排查全靠翻服务器日志）
    this.log(`[backup] ${title}：${body}`)
    this.deps.notify?.(title, body)
  }
}

/** 探测「是否有任何既有备份配置」（供自动配置决策；纯函数便于测试） */
export function probeFromSettings(read: (key: string) => unknown): BackupConfigProbe {
  return {
    hasDailyConfig: read('backup.daily.config') != null,
    hasManualTargetDir: read('backup.daily.targetDir') != null,
    hasOssConfig: read('backup.oss.bucket') != null || read('backup.oss.accessKeyId') != null,
    hasExitPassword: read('backup.exitPassword') != null
  }
}

export { CLOUD_BACKUP_ROOT }
