// 零感托管备份 —— 自动配置决策与密钥生成（工单 ZB §1/§2）— 纯函数，零依赖。
//
// 用户裁决：备份对组员**零操作** —— 没有密码输入、没有目录选择、没有「立即备份」按钮依赖。
// 登录成功那一刻应用已知「这个人是谁」（M2-3a+ 云端身份），备份随之全自动生效：
//   · 备份目标 = 该用户自己的云端网盘 `backups/` 目录（复用 M2-3c 分块通道，零服务端改动）
//   · 保护密钥 = 自动生成的强随机密码（safeStorage 保存 + 随容器同目录托管上传 key.json）
//   · 每日定时 + 保留最近 7 份
//
// ★ 既有手工配置的用户（如负责人本人）**零覆盖** —— 检测到既有配置即跳过。

import { DEFAULT_DAILY_BACKUP_CONFIG, type DailyBackupConfig } from './daily-backup'

/** 云端备份根目录（用户网盘内） */
export const CLOUD_BACKUP_ROOT = 'backups'
/** 密钥托管文件后缀 */
export const KEY_FILE_SUFFIX = '.key.json'
/** 保护密钥字节数（32 字节 → base64 ≈ 44 字符，强度足够） */
export const KEY_BYTES = 32

export interface BackupConfigProbe {
  /** 是否已有每日定时配置 */
  hasDailyConfig: boolean
  /** 是否已有手工目标目录 */
  hasManualTargetDir: boolean
  /** 是否已有 OSS 直传配置（旧手工路线） */
  hasOssConfig: boolean
  /** 是否已有备份密码（旧手工路线） */
  hasExitPassword: boolean
}

export interface AutoProvisionInput {
  probe: BackupConfigProbe
  /** 当前云端用户名（null = 非云端身份/未登录） */
  cloudUsername: string | null
}

export type AutoProvisionReason =
  | 'not-cloud-identity' // 未登录或非云端身份 → 不配置
  | 'already-configured' // 既有配置 → **零覆盖**
  | 'provision' // 无任何配置 → 自动配置

export interface AutoProvisionPlan {
  provision: boolean
  reason: AutoProvisionReason
  /** 自动配置内容（仅 reason='provision' 时有值） */
  config?: DailyBackupConfig
  /** 云端备份目录（用户网盘内相对路径） */
  remoteDir?: string
}

/** 是否「未做过任何备份配置」 */
export function isUnconfigured(probe: BackupConfigProbe): boolean {
  return !probe.hasDailyConfig && !probe.hasManualTargetDir && !probe.hasOssConfig && !probe.hasExitPassword
}

/**
 * 自动配置决策（纯函数）。
 *
 * 优先级：未登录/非云端身份 → 不配置；既有任意配置 → **零覆盖**；否则自动配置。
 * 注意：判定为「既有配置」的门槛很低（四个探针任一为真即跳过）——宁可少配，不可覆盖用户手工设置。
 */
export function planAutoProvision(input: AutoProvisionInput): AutoProvisionPlan {
  if (!input.cloudUsername) {
    return { provision: false, reason: 'not-cloud-identity' }
  }
  if (!isUnconfigured(input.probe)) {
    return { provision: false, reason: 'already-configured' }
  }
  return {
    provision: true,
    reason: 'provision',
    config: {
      ...DEFAULT_DAILY_BACKUP_CONFIG,
      enabled: true, // 零感：登录即开启
      keep: 7 // 保留最近 7 份
    },
    remoteDir: cloudBackupDir(input.cloudUsername)
  }
}

/** 用户云端备份目录（网盘内路径；成员互相不可见——各自目录内） */
export function cloudBackupDir(cloudUsername: string): string {
  const safe = cloudUsername.trim().replace(/[^\w\u4e00-\u9fa5.-]/g, '_') || 'user'
  return `${CLOUD_BACKUP_ROOT}/${safe}`
}

/**
 * 生成保护密钥（注入随机源以便测试）。
 * @param rand 形如 crypto.randomBytes 的函数
 */
export function generateProtectionKey(rand: (size: number) => Uint8Array, bytes: number = KEY_BYTES): string {
  return Buffer.from(rand(bytes)).toString('base64')
}

/** 密钥托管文件名：与容器同目录、同名（仅后缀不同），便于成对识别 */
export function keyFileName(containerName: string): string {
  // workbench-20260923-1.mnbbak → workbench-20260923-1.mnbbak.key.json
  return `${containerName}${KEY_FILE_SUFFIX}`
}

/** 由 key 文件名反推容器名（对不上返回 null） */
export function containerNameFromKeyFile(keyName: string): string | null {
  if (!keyName.endsWith(KEY_FILE_SUFFIX)) return null
  return keyName.slice(0, -KEY_FILE_SUFFIX.length)
}

export interface KeyEnvelope {
  version: 1
  /** 保护密钥（base64）—— ★ 绝不写日志/报告 */
  key: string
  createdAt: number
  note: string
}

/** 构造托管信封（供上传为 key.json） */
export function buildKeyEnvelope(key: string, createdAt: number): KeyEnvelope {
  return {
    version: 1,
    key,
    createdAt,
    note: '本文件是「科研工作台」自动备份的保护密钥。恢复数据时需与本目录的备份容器配对使用。请勿删除或公开分享。'
  }
}

/** 解析托管信封（畸形返回 null） */
export function parseKeyEnvelope(raw: unknown): KeyEnvelope | null {
  if (!raw || typeof raw !== 'object') return null
  const o = raw as Record<string, unknown>
  if (o.version !== 1) return null
  if (typeof o.key !== 'string' || !o.key) return null
  return {
    version: 1,
    key: o.key,
    createdAt: typeof o.createdAt === 'number' ? o.createdAt : 0,
    note: typeof o.note === 'string' ? o.note : ''
  }
}

// ---------------------------------------------------------------- 保留策略

/** 保留判定所需的最小文件信息 */
export interface RemoteBackupEntry {
  name: string
  createdAt: number
}

/**
 * 计算应删除的远端备份（保留最近 keep 份）。
 *
 * ★ 安全约束：**只删本应用命名模式的文件**（`.mnbbak` / `pre-restore` 前缀），
 *   用户放进同目录的其它文件一律不动（沿用 shared/backup-naming 的既有约定）。
 * ★ 配对约束：删容器时**连它的 .key.json 一起删**，避免遗留孤儿密钥。
 */
export function planRetention(
  entries: readonly RemoteBackupEntry[],
  keep: number,
  isManaged: (name: string) => boolean
): { keep: string[]; remove: string[] } {
  const containers = entries.filter((e) => isManaged(e.name) && e.name.endsWith('.mnbbak'))
  if (keep <= 0) return { keep: containers.map((c) => c.name), remove: [] }
  const sorted = [...containers].sort((a, b) => b.createdAt - a.createdAt) // 新→旧
  const keepNames = sorted.slice(0, keep).map((c) => c.name)
  const removeNames = sorted.slice(keep).map((c) => c.name)
  // 连密钥文件一起删（成对）
  const removeWithKeys = removeNames.flatMap((n) => [n, keyFileName(n)])
  return { keep: keepNames, remove: removeWithKeys }
}

/** 判断某远端文件名是否属于「本应用管理的备份」 */
export function isManagedBackupName(name: string, prefixes: readonly string[]): boolean {
  if (!name.endsWith('.mnbbak') && !name.endsWith('.mnbbak' + KEY_FILE_SUFFIX)) return false
  return prefixes.some((p) => name.startsWith(p))
}

// ---------------------------------------------------------------- 离线宽容

/** 本次是否应执行（断网顺延到次日，不报错） */
export function shouldRunNow(input: { online: boolean; loggedIn: boolean; dueNow: boolean }): {
  run: boolean
  reason: 'ok' | 'offline-deferred' | 'not-logged-in' | 'not-due'
} {
  if (!input.loggedIn) return { run: false, reason: 'not-logged-in' }
  if (!input.online) return { run: false, reason: 'offline-deferred' } // 顺延，不报错
  if (!input.dueNow) return { run: false, reason: 'not-due' }
  return { run: true, reason: 'ok' }
}
