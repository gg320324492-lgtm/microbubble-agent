// 备份服务（M5-1）— 创建加密备份 / 从备份恢复（含安全网）/ 列出本地快照。
// createBackup 通过 VACUUM INTO 做全量 SQLite 快照，收集附件目录打容器。
// restoreBackup 在覆盖前自动保留当前数据快照（pre-restore-*.mnbbak）。
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { basename, join, relative } from 'node:path'
import type { SqlDatabase } from '../../db/adapters'
import { packContainer, unpackContainer } from './container'
import type { OssConfig } from './oss.client'
import { OssClient } from './oss.client'

export interface LocalBackupInfo {
  fileName: string
  size: number
  appVersion: string
  createdAt: number
  path: string
}

const BACKUP_EXT = '.mnbbak'
const FILES_SUBDIRS = ['knowledge', 'meetings', 'experiments']

export class BackupService {
  constructor(
    private readonly db: SqlDatabase,
    private readonly dbPath: string,
    private readonly filesRoot: string,
    private readonly appVersion: string
  ) {}

  /** VACUUM INTO 生成 SQLite 全量快照到指定路径 */
  vacuumInto(targetPath: string): void {
    try { rmSync(targetPath, { force: true }) } catch { /* 忽略 */ }
    this.db.exec(`VACUUM INTO '${targetPath.replace(/\\/g, '/')}'`)
  }

  /** 收集 files/ 目录下全部附件（含子目录与中文路径）为段列表 */
  collectFileSegments(): { name: string; data: Buffer }[] {
    const segments: { name: string; data: Buffer }[] = []
    if (!existsSync(this.filesRoot)) return segments
    for (const sub of FILES_SUBDIRS) {
      const subDir = join(this.filesRoot, sub)
      if (!existsSync(subDir)) continue
      collectRecursive(subDir, (rel, abs) => {
        segments.push({ name: `files/${rel}`, data: readFileSync(abs) })
      })
    }
    return segments
  }

  /** 收集 SQLite 快照段（VACUUM INTO + 读取 + 清理临时文件） */
  collectSqliteSegment(): { name: string; data: Buffer } {
    const tmpPath = join(this.dbPath, '..', '.backup-snapshot.db')
    this.vacuumInto(tmpPath)
    const data = readFileSync(tmpPath)
    try { rmSync(tmpPath, { force: true }) } catch { /* 忽略 */ }
    return { name: 'workbench.db', data }
  }

  /** 打包当前数据为 .mnbbak 加密容器；prefix 可覆盖默认命名前缀（安全网用 pre-restore-） */
  async createBackup(opts: { password: string; targetDir: string; prefix?: string }): Promise<{ fileName: string; size: number }> {
    const { password, targetDir, prefix: namePrefix } = opts
    if (!password || !password.trim()) throw new Error('备份密码不能为空')
    mkdirSync(targetDir, { recursive: true })

    const segments: { name: string; data: Buffer }[] = [this.collectSqliteSegment(), ...this.collectFileSegments()]
    const now = new Date()
    const ts = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}-${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}${String(now.getSeconds()).padStart(2, '0')}`
    const baseName = namePrefix ? `${namePrefix}-${ts}` : `workbench-${ts}`
    let fileName = `${baseName}.mnbbak`
    let seq = 2
    while (existsSync(join(targetDir, fileName))) {
      fileName = `${baseName} (${seq}).mnbbak`
      seq++
    }
    const filePath = join(targetDir, fileName)

    const data = packContainer(segments, { app_version: this.appVersion }, password)
    writeFileSync(filePath, data)
    return { fileName, size: data.length }
  }

  /**
   * 从备份容器恢复：解密验签 → 安全网（保留当前数据快照）→ 覆盖库与文件。
   * 返回 needRestart: true — 调用方提示重启应用重载数据。
   */
  async restoreBackup(opts: { password: string; backupFile: string }): Promise<{ needRestart: boolean }> {
    const { password, backupFile } = opts
    if (!existsSync(backupFile)) throw new Error('备份文件不存在')
    const data = readFileSync(backupFile)
    const { segments } = unpackContainer(data, password)

    // 安全网：先把当前数据打包为 pre-restore 快照（与被恢复文件同目录）
    const backupDir = join(backupFile, '..')
    mkdirSync(backupDir, { recursive: true })
    await this.createBackup({ password, targetDir: backupDir, prefix: 'pre-restore' })

    // 覆盖 SQLite 库（含 WAL 清理）
    const dbData = segments.get('workbench.db')
    if (!dbData) throw new Error('备份容器中缺少 SQLite 数据段')
    writeFileSync(this.dbPath, dbData)
    for (const suffix of ['-wal', '-shm']) {
      try { rmSync(this.dbPath + suffix, { force: true }) } catch { /* 忽略 */ }
    }

    // 清空并重铺附件文件
    for (const sub of FILES_SUBDIRS) {
      const subDir = join(this.filesRoot, sub)
      if (existsSync(subDir)) rmSync(subDir, { recursive: true, force: true })
    }
    for (const [name, segData] of segments) {
      if (!name.startsWith('files/')) continue
      const rel = name.slice('files/'.length)
      const abs = join(this.filesRoot, rel)
      mkdirSync(abs.replace(/[/\\][^/\\]*$/, ''), { recursive: true })
      writeFileSync(abs, segData)
    }

    return { needRestart: true }
  }

  /** 列出目标目录下的 .mnbbak 快照摘要（按时间倒序） */
  listLocalBackups(targetDir: string): LocalBackupInfo[] {
    if (!existsSync(targetDir)) return []
    const results: LocalBackupInfo[] = []
    try {
      for (const f of readdirSync(targetDir)) {
        if (!f.endsWith(BACKUP_EXT)) continue
        const abs = join(targetDir, f)
        const st = statSync(abs)
        results.push({ fileName: f, size: st.size, appVersion: '—', createdAt: st.mtimeMs, path: abs })
      }
    } catch { return [] }
    return results.sort((a, b) => b.createdAt - a.createdAt)
  }

  /** 删除本地快照 — 只接受目录内直接命中的 .mnbbak 文件名，防路径穿越 */
  deleteLocalBackup(targetDir: string, fileName: string): boolean {
    if (!fileName.endsWith(BACKUP_EXT) || fileName.includes('/') || fileName.includes('\\') || fileName.includes('..')) return false
    const abs = join(targetDir, fileName)
    if (!existsSync(abs)) return false
    rmSync(abs, { force: true })
    return true
  }

  // ---------- OSS 远端操作（M5-2） ----------

  /** 上传备份文件到 OSS（key = prefix/<文件名>） */
  async uploadBackup(config: OssConfig, filePath: string): Promise<{ key: string; size: number }> {
    if (!existsSync(filePath)) throw new Error('备份文件不存在')
    const client = new OssClient(config, async (req) => {
      // 注入式 HTTP — 生产环境用 Node http/https，测试注入假
      const { default: https } = await import('node:https')
      return new Promise((resolve, reject) => {
        const url = new URL(req.url)
        const reqOpts = { hostname: url.hostname, port: url.port || 443, path: url.pathname + url.search, method: req.method, headers: req.headers }
        const httpReq = https.request(reqOpts, (res) => {
          const chunks: Buffer[] = []
          res.on('data', (c: Buffer) => chunks.push(c))
          res.on('end', () => resolve({ status: res.statusCode ?? 500, body: Buffer.concat(chunks) }))
        })
        httpReq.on('error', reject)
        if (req.body) httpReq.write(req.body)
        httpReq.end()
      })
    })
    const key = `${config.prefix}${basename(filePath)}`
    const data = readFileSync(filePath)
    await client.putObject(key, data)
    return { key, size: data.length }
  }

  /** 从 OSS 下载备份到本地目录（返回本地路径，后续走 restoreBackup） */
  async downloadBackup(config: OssConfig, remoteKey: string, targetDir: string): Promise<{ localPath: string }> {
    const client = new OssClient(config, async (req) => {
      const { default: https } = await import('node:https')
      return new Promise((resolve, reject) => {
        const url = new URL(req.url)
        const reqOpts = { hostname: url.hostname, port: url.port || 443, path: url.pathname + url.search, method: req.method, headers: req.headers }
        const httpReq = https.request(reqOpts, (res) => {
          const chunks: Buffer[] = []
          res.on('data', (c: Buffer) => chunks.push(c))
          res.on('end', () => resolve({ status: res.statusCode ?? 500, body: Buffer.concat(chunks) }))
        })
        httpReq.on('error', reject)
        httpReq.end()
      })
    })
    const data = await client.getObject(remoteKey)
    mkdirSync(targetDir, { recursive: true })
    const localPath = join(targetDir, basename(remoteKey))
    writeFileSync(localPath, data)
    return { localPath }
  }

  /** 列出 OSS 远端备份摘要 */
  async listRemoteBackups(config: OssConfig): Promise<{ key: string; size: number; lastModified: string }[]> {
    const client = new OssClient(config, async (req) => {
      const { default: https } = await import('node:https')
      return new Promise((resolve, reject) => {
        const url = new URL(req.url)
        const reqOpts = { hostname: url.hostname, port: url.port || 443, path: url.pathname + url.search, method: req.method, headers: req.headers }
        const httpReq = https.request(reqOpts, (res) => {
          const chunks: Buffer[] = []
          res.on('data', (c: Buffer) => chunks.push(c))
          res.on('end', () => resolve({ status: res.statusCode ?? 500, body: Buffer.concat(chunks) }))
        })
        httpReq.on('error', reject)
        httpReq.end()
      })
    })
    return client.listObjects(config.prefix)
  }

  /** 删除 OSS 远端备份 */
  async deleteRemoteBackup(config: OssConfig, remoteKey: string): Promise<void> {
    const client = new OssClient(config, async (req) => {
      const { default: https } = await import('node:https')
      return new Promise((resolve, reject) => {
        const url = new URL(req.url)
        const reqOpts = { hostname: url.hostname, port: url.port || 443, path: url.pathname + url.search, method: req.method, headers: req.headers }
        const httpReq = https.request(reqOpts, (res) => {
          const chunks: Buffer[] = []
          res.on('data', (c: Buffer) => chunks.push(c))
          res.on('end', () => resolve({ status: res.statusCode ?? 500, body: Buffer.concat(chunks) }))
        })
        httpReq.on('error', reject)
        httpReq.end()
      })
    })
    await client.deleteObject(remoteKey)
  }

  /**
   * 退出时自动备份（M5-2）— 创建本地备份（+上传 OSS 如已配置）。
   * 10s 超时保护；失败不阻塞退出。返回 null = 未触发（开关关）或超时。
   */
  async exitAutoBackup(opts: {
    password: string
    autoOnExit: boolean
    ossConfig?: OssConfig | null
  }): Promise<{ fileName: string; uploaded: boolean } | null> {
    if (!opts.autoOnExit) return null
    const targetDir = join(this.filesRoot, '..', 'backups')
    const timeout = new Promise<never>((_, reject) => {
      const timer = setTimeout(() => reject(new Error('退出备份超时')), 10_000)
      timer.unref?.() // 超时保护不阻塞进程退出
    })
    const doBackup = async () => {
      const res = await this.createBackup({ password: opts.password, targetDir })
      let uploaded = false
      if (opts.ossConfig) {
        try {
          await this.uploadBackup(opts.ossConfig, join(targetDir, res.fileName))
          uploaded = true
        } catch { /* 上传失败不阻塞退出 */ }
      }
      return { fileName: res.fileName, uploaded }
    }
    return Promise.race([doBackup(), timeout])
  }
}

/** 递归收集目录下全部文件，回调参数为相对路径（正斜杠）与绝对路径 */
function collectRecursive(base: string, cb: (rel: string, abs: string) => void): void {
  let entries: string[]
  try { entries = readdirSync(base) } catch { return }
  for (const e of entries) {
    const abs = join(base, e)
    let isDir = false
    try { isDir = statSync(abs).isDirectory() } catch { continue }
    if (isDir) collectRecursive(abs, cb)
    else cb(relative(base, abs).replaceAll('\\', '/'), abs)
  }
}
