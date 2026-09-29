// 通用分块文件通道（工单 M2-3c §2 + 补充约束①）— 纯逻辑 + 注入式 IO，零 Electron / 零依赖。
//
// ★ 设计要点：**不写死「网盘文件」语义** —— 聊天附件上传（图片/PDF/文档）将复用同一基建。
//   因此本模块只认「一个文件 + 一个上传会话 + 进度回调」，与用途无关。
//
// 契约来自只读调研（app/api/v1/drive_chunked_uploads.py，router prefix=/drive/chunked-uploads）：
//   POST /api/v1/drive/chunked-uploads/init
//        body {filename, file_size, chunk_size?, parent_id?, checksum?}
//        → 201 {upload_id, filename, file_size, chunk_size, total_chunks, uploaded_chunks: int[], status, expires_at}
//   GET  /api/v1/drive/chunked-uploads/{upload_id}          → 同上（★ 断点续传的权威依据：uploaded_chunks）
//   PUT  /api/v1/drive/chunked-uploads/{upload_id}/chunks/{i}
//   POST /api/v1/drive/chunked-uploads/{upload_id}/complete  body {final_checksum?, visibility?, is_team_shared?}
//   DELETE /api/v1/drive/chunked-uploads/{upload_id}         → 204

import type { CloudApiClient, CloudResult, CloudTokens } from './api-client'

/** 分块默认大小（服务端约束 256KB–32MB；取 4MB 兼顾请求数与内存） */
export const DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024
/** 低于该值走「简化路径」（一次性上传，不建会话） */
export const SMALL_FILE_THRESHOLD = 4 * 1024 * 1024

export interface UploadSession {
  uploadId: string
  filename: string
  fileSize: number
  chunkSize: number
  totalChunks: number
  /** 服务端已收到的分块序号（权威，断点续传据此跳过） */
  uploadedChunks: number[]
  status: string
  expiresAt: string
  /** 创建/续传时间（本地记账用） */
  updatedAt: number
}

export interface TransferProgress {
  /** 已传字节 / 总字节 */
  transferred: number
  total: number
  /** 0–100（整数） */
  percent: number
  /** 本次跳过（已传过）的分块数 */
  skippedChunks?: number
}

/** 分块读盘（注入：生产用 fs，测试用内存） */
export type ChunkReader = (offset: number, length: number) => Promise<Uint8Array>
/** 上传会话持久化（注入：生产落 settings；测试用内存 Map） */
export interface SessionStore {
  get(key: string): UploadSession | null
  set(key: string, session: UploadSession): void
  remove(key: string): void
  /** 列出全部（用于「恢复未完成上传」入口） */
  list(): UploadSession[]
}

/** 内存实现（测试 / 降级用） */
export class MemorySessionStore implements SessionStore {
  private readonly m = new Map<string, UploadSession>()
  get(key: string): UploadSession | null {
    return this.m.get(key) ?? null
  }
  set(key: string, s: UploadSession): void {
    this.m.set(key, s)
  }
  remove(key: string): void {
    this.m.delete(key)
  }
  list(): UploadSession[] {
    return [...this.m.values()]
  }
}

export interface TransferDeps {
  client: CloudApiClient
  tokens: () => CloudTokens | null
  /** 服务器地址提供者（★ 每次请求前取，禁止构造期快照 —— M2-3b 实证缺陷） */
  baseUrl: () => string
  /** 上传会话持久化（断点续传） */
  sessions: SessionStore
  onTokensRefreshed?: (t: CloudTokens) => void
  log?: (message: string) => void
}

export interface UploadRequest {
  filename: string
  fileSize: number
  /** 分块读盘（大文件不整文件进内存） */
  readChunk: ChunkReader
  /** 目标父目录（网盘语义；聊天附件可传 undefined） */
  parentId?: number | null
  /** 可见性（网盘语义；聊天附件可传 undefined → 服务端默认 team） */
  visibility?: 'private' | 'team' | 'public'
  /** 幂等键：同一文件重试时复用会话（默认 filename+size） */
  resumeKey?: string
  onProgress?: (p: TransferProgress) => void
  /** 中止信号 */
  signal?: AbortSignal
}

export interface UploadResult {
  /** 服务端返回的完成体（网盘场景为 DriveFileItem；附件场景由调用方解释） */
  json: unknown
  resumed: boolean
  uploadedChunks: number
}

/** 归一化上传会话（畸形响应 → null，由调用方按失败处理） */
export function normalizeUploadSession(raw: unknown): UploadSession | null {
  if (!raw || typeof raw !== 'object') return null
  const o = raw as Record<string, unknown>
  const uploadId = typeof o.upload_id === 'string' ? o.upload_id : null
  if (!uploadId) return null
  const num = (v: unknown, d = 0): number => (typeof v === 'number' && Number.isFinite(v) ? v : d)
  const chunks = Array.isArray(o.uploaded_chunks) ? o.uploaded_chunks.filter((x): x is number => typeof x === 'number') : []
  return {
    uploadId,
    filename: typeof o.filename === 'string' ? o.filename : '',
    fileSize: num(o.file_size),
    chunkSize: num(o.chunk_size, DEFAULT_CHUNK_SIZE),
    totalChunks: num(o.total_chunks),
    uploadedChunks: chunks,
    status: typeof o.status === 'string' ? o.status : 'unknown',
    expiresAt: typeof o.expires_at === 'string' ? o.expires_at : '',
    updatedAt: Date.now()
  }
}

/**
 * 通用分块上传通道。
 *
 * 断点续传：会话持久化在 `SessionStore`；重传时先 `GET /{uploadId}` 取**服务端**的
 * `uploaded_chunks`（权威），只补缺口 —— 中断后不重头。
 */
export class FileTransferService {
  constructor(private readonly deps: TransferDeps) {}

  private baseUrlProvider(): string {
    return this.deps.baseUrl()
  }

  private async call(
    method: 'GET' | 'POST' | 'PUT' | 'DELETE',
    path: string,
    opts: { body?: unknown; contentType?: string } = {}
  ): Promise<CloudResult<unknown>> {
    const t = this.deps.tokens()
    if (!t) return { ok: false, error: { kind: 'auth', message: '尚未连接云端。' } }
    // ★ 每次请求前刷新地址（提供者模式）
    this.deps.client.setBaseUrl(this.baseUrlProvider())
    const res = await this.deps.client.requestWithAuth(method, path, t, opts)
    if (!res.ok) return res
    if (res.data.refreshed) this.deps.onTokensRefreshed?.(res.data.tokens)
    return { ok: true, data: res.data.json }
  }

  /** 创建上传会话 */
  async initSession(req: {
    filename: string
    fileSize: number
    chunkSize?: number
    parentId?: number | null
    checksum?: string
  }): Promise<CloudResult<UploadSession>> {
    const body: Record<string, unknown> = {
      filename: req.filename,
      file_size: req.fileSize,
      chunk_size: req.chunkSize ?? DEFAULT_CHUNK_SIZE
    }
    if (req.parentId !== undefined && req.parentId !== null) body.parent_id = req.parentId
    if (req.checksum) body.checksum = req.checksum
    const res = await this.call('POST', '/api/v1/drive/chunked-uploads/init', { body })
    if (!res.ok) return res
    const s = normalizeUploadSession(res.data)
    if (!s) return { ok: false, error: { kind: 'malformed', message: '云端返回了无法识别的上传会话。' } }
    return { ok: true, data: s }
  }

  /** 查询会话状态（断点续传的权威依据） */
  async getSession(uploadId: string): Promise<CloudResult<UploadSession>> {
    const res = await this.call('GET', `/api/v1/drive/chunked-uploads/${encodeURIComponent(uploadId)}`)
    if (!res.ok) return res
    const s = normalizeUploadSession(res.data)
    if (!s) return { ok: false, error: { kind: 'malformed', message: '云端返回了无法识别的上传会话。' } }
    return { ok: true, data: s }
  }

  /** 上传单个分块（分块体为二进制；此处以 base64 承载以便注入式测试，生产由适配层直传） */
  async putChunk(uploadId: string, index: number, bytes: Uint8Array): Promise<CloudResult<unknown>> {
    return this.call('PUT', `/api/v1/drive/chunked-uploads/${encodeURIComponent(uploadId)}/chunks/${index}`, {
      body: { chunk_base64: bytesToBase64(bytes), chunk_index: index }
    })
  }

  /** 完成上传 */
  async completeSession(
    uploadId: string,
    opts: { finalChecksum?: string; visibility?: 'private' | 'team' | 'public' } = {}
  ): Promise<CloudResult<unknown>> {
    const body: Record<string, unknown> = {}
    if (opts.finalChecksum) body.final_checksum = opts.finalChecksum
    if (opts.visibility) body.visibility = opts.visibility
    return this.call('POST', `/api/v1/drive/chunked-uploads/${encodeURIComponent(uploadId)}/complete`, { body })
  }

  /** 取消会话（清服务端会话 + 本地持久化） */
  async cancelSession(uploadId: string, resumeKey?: string): Promise<CloudResult<true>> {
    const res = await this.call('DELETE', `/api/v1/drive/chunked-uploads/${encodeURIComponent(uploadId)}`)
    if (resumeKey) this.deps.sessions.remove(resumeKey)
    if (!res.ok && res.error.kind !== 'client') return res
    return { ok: true, data: true }
  }

  /** 列出未完成的上传（UI「继续上传」入口用） */
  pendingSessions(): UploadSession[] {
    return this.deps.sessions.list()
  }

  /**
   * 上传文件（完整流程，含断点续传与进度）。
   * 大文件分块读盘，不整文件进内存；小文件走简化路径（不建会话，一次性上传）。
   */
  async upload(req: UploadRequest): Promise<CloudResult<UploadResult>> {
    const resumeKey = req.resumeKey ?? `${req.filename}::${req.fileSize}`
    const emit = (p: TransferProgress): void => req.onProgress?.(p)

    // ---- 简化路径：小文件 ----
    if (req.fileSize <= SMALL_FILE_THRESHOLD) {
      const bytes = await req.readChunk(0, req.fileSize)
      // 服务端该端点只收 multipart/form-data（web 端 DriveUploadDialog 同款字段）；
      // 旧 JSON {file_base64} 形态 422（恢复演练 2026-09-29 实锤：ZB 零感备份容器上传全废）。
      // 注：is_team_shared 服务端已恒置 True（该字段退役，迁移 133）；备份隐私由服务端
      // 依目标文件夹路径强制 visibility='private'（ZB-1，保留区=backups/ 根子树），与上传参数无关。
      const boundary = '----mnb-form-' + Date.now().toString(36)
      const enc = (s: string): Buffer => Buffer.from(s, 'utf8')
      const safeName = req.filename.replace(/[\r\n"]/g, '_')
      const parts: Buffer[] = [
        enc(`--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="${safeName}"\r\nContent-Type: application/octet-stream\r\n\r\n`),
        Buffer.from(bytes),
        enc(`\r\n--${boundary}\r\nContent-Disposition: form-data; name="filename"\r\n\r\n${safeName}\r\n`),
        enc(`--${boundary}\r\nContent-Disposition: form-data; name="storage_mode"\r\n\r\ndrive\r\n`),
        ...(req.parentId !== undefined && req.parentId !== null
          ? [enc(`--${boundary}\r\nContent-Disposition: form-data; name="folder_id"\r\n\r\n${String(req.parentId)}\r\n`)]
          : []),
        ...(req.visibility ? [enc(`--${boundary}\r\nContent-Disposition: form-data; name="visibility"\r\n\r\n${req.visibility}\r\n`)] : []),
        enc(`--${boundary}--\r\n`)
      ]
      const res = await this.call('POST', '/api/v1/drive/files/upload', {
        body: Buffer.concat(parts),
        contentType: `multipart/form-data; boundary=${boundary}`
      })
      if (!res.ok) return res
      emit({ transferred: req.fileSize, total: req.fileSize, percent: 100 })
      return { ok: true, data: { json: res.data, resumed: false, uploadedChunks: 1 } }
    }

    // ---- 分块路径 ----
    let session = this.deps.sessions.get(resumeKey)
    let resumed = false
    if (session) {
      // ★ 以服务端状态为准（本地只是线索）
      const remote = await this.getSession(session.uploadId)
      if (remote.ok) {
        session = remote.data
        resumed = remote.data.uploadedChunks.length > 0
        this.deps.log?.(`[transfer] 续传会话 ${session.uploadId}：已传 ${session.uploadedChunks.length}/${session.totalChunks} 块`)
      } else {
        this.deps.log?.('[transfer] 会话失效，重新创建')
        this.deps.sessions.remove(resumeKey)
        session = null
      }
    }
    if (!session) {
      const created = await this.initSession({
        filename: req.filename,
        fileSize: req.fileSize,
        parentId: req.parentId ?? null
      })
      if (!created.ok) return created
      session = created.data
      this.deps.sessions.set(resumeKey, session)
    }

    const done = new Set(session.uploadedChunks)
    const skipped = done.size
    let transferred = Math.min(done.size * session.chunkSize, req.fileSize)
    emit({ transferred, total: req.fileSize, percent: Math.floor((transferred / req.fileSize) * 100), skippedChunks: skipped })

    for (let i = 0; i < session.totalChunks; i += 1) {
      if (req.signal?.aborted) {
        return { ok: false, error: { kind: 'timeout', message: '上传已取消。' } }
      }
      if (done.has(i)) continue // ★ 断点续传：已传过的分块不重传
      const offset = i * session.chunkSize
      const length = Math.min(session.chunkSize, req.fileSize - offset)
      const bytes = await req.readChunk(offset, length)
      const put = await this.putChunk(session.uploadId, i, bytes)
      if (!put.ok) return put
      done.add(i)
      session = { ...session, uploadedChunks: [...done], updatedAt: Date.now() }
      this.deps.sessions.set(resumeKey, session)
      transferred += length
      emit({ transferred, total: req.fileSize, percent: Math.floor((transferred / req.fileSize) * 100), skippedChunks: skipped })
    }

    const finished = await this.completeSession(session.uploadId, {
      ...(req.visibility ? { visibility: req.visibility } : {})
    })
    if (!finished.ok) return finished
    this.deps.sessions.remove(resumeKey)
    return { ok: true, data: { json: finished.data, resumed, uploadedChunks: done.size } }
  }
}

// ---------------------------------------------------------------- 工具

/** base64 编解码（注入式分块体承载；生产适配层可直接用二进制流） */
export function bytesToBase64(bytes: Uint8Array): string {
  return Buffer.from(bytes).toString('base64')
}
export function base64ToBytes(b64: string): Uint8Array {
  return new Uint8Array(Buffer.from(b64, 'base64'))
}

/** 计算分块数（与服务端 total_chunks 口径一致：向上取整） */
export function chunkCount(fileSize: number, chunkSize: number = DEFAULT_CHUNK_SIZE): number {
  if (fileSize <= 0) return 0
  return Math.ceil(fileSize / chunkSize)
}
