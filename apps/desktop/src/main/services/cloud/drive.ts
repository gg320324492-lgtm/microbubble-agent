// 远程网盘数据源（工单 M2-3c §1/§3）— 纯逻辑 + 注入式 HTTP，零 Electron / 零依赖。
//
// 契约来自只读调研：
//   drive_files.py   router prefix=/drive     → /api/v1/drive/files ...
//   drive_folders.py router prefix=/folders   → /api/v1/folders ...
//   drive_chunked_uploads.py prefix=/drive/chunked-uploads → 分块上传（见 transfer.ts）
//   GET  /api/v1/drive/files?parent_id=&keyword=   → DriveFileListResponse
//   GET  /api/v1/drive/files/{id}                  → DriveFileItem
//   PUT  /api/v1/drive/files/{id}                  → DriveFileItem（重命名/移动）
//   POST /api/v1/drive/files/upload                → 201 DriveFileItem（小文件简化路径）
//   GET  /api/v1/drive/by-path?path=               → 按路径取文件
//   DELETE /api/v1/drive/files/{id}                → 删除
//
// ★ 可见性硬要求：沿用服务端 `_can_see_file` + visibility 继承校验，
//   客户端**不自造权限、不预判、不本地过滤绕过**；`visibility` 仅透传展示。
// ★ 外部状态一律「提供者」模式（baseUrl / 当前文件夹 / 上传会话），禁止构造期快照。

import type { CloudApiClient, CloudError, CloudResult, CloudTokens } from './api-client'
import { featureErrorMessage } from './guidance'
import { FileTransferService, MemorySessionStore, type ChunkReader, type SessionStore, type TransferProgress, type UploadSession } from './transfer'

/** 网盘条目（与父级 DriveFileItem 对齐，仅取桌面端需要的字段） */
export interface RemoteDriveItem {
  id: number
  title: string
  fileName: string
  fileType: string
  fileSize: number
  /** 父目录（null = 根） */
  folderId: number | null
  /** 'private' | 'team' | 'public' —— 仅透传展示，不参与本地判定 */
  visibility: string | null
  ownerName: string | null
  createdAt: string | null
  updatedAt: string | null
}

export interface DriveListPage {
  items: RemoteDriveItem[]
  total: number
}

export interface DriveUploadResult {
  item: RemoteDriveItem | null
  resumed: boolean
  uploadedChunks: number
}

export interface RemoteDriveDeps {
  client: CloudApiClient
  tokens: () => CloudTokens | null
  /** 服务器地址提供者（每次请求前取） */
  baseUrl: () => string
  /** 上传会话持久化（默认内存；生产装配层传 settings 实现） */
  sessions?: SessionStore
  onTokensRefreshed?: (t: CloudTokens) => void
  log?: (message: string) => void
}

// ---------------------------------------------------------------- 归一化

function asString(v: unknown): string | null {
  return typeof v === 'string' ? v : null
}
function asNumber(v: unknown): number | null {
  if (typeof v === 'number' && Number.isFinite(v)) return v
  if (typeof v === 'string' && /^\d+$/.test(v)) return Number(v)
  return null
}

/** 归一化条目；缺 id 或文件名视为无效（丢弃而非让 UI 崩） */
export function normalizeDriveItem(raw: unknown): RemoteDriveItem | null {
  if (!raw || typeof raw !== 'object') return null
  const o = raw as Record<string, unknown>
  const id = asNumber(o.id)
  if (id === null) return null
  const fileName = asString(o.file_name) ?? asString(o.title)
  if (!fileName) return null
  return {
    id,
    title: asString(o.title) ?? fileName,
    fileName,
    fileType: asString(o.file_type) ?? '',
    fileSize: asNumber(o.file_size) ?? 0,
    folderId: asNumber(o.folder_id),
    visibility: asString(o.visibility),
    ownerName: asString(o.owner_name),
    createdAt: asString(o.created_at),
    updatedAt: asString(o.updated_at)
  }
}

/** 归一化列表：容忍裸数组与 `{items,total}` 两种形状 */
export function normalizeDrivePage(raw: unknown): DriveListPage {
  const o = (raw ?? {}) as Record<string, unknown>
  const arr = Array.isArray(raw) ? raw : Array.isArray(o.items) ? o.items : Array.isArray(o.files) ? o.files : []
  const items = arr.map(normalizeDriveItem).filter((x): x is RemoteDriveItem => x !== null)
  const total = asNumber(o.total) ?? items.length
  return { items, total }
}

// ---------------------------------------------------------------- 服务

export class RemoteDriveService {
  private readonly client: CloudApiClient
  private readonly tokens: () => CloudTokens | null
  private readonly baseUrlProvider: () => string
  private readonly transfer: FileTransferService
  private readonly log: (m: string) => void

  constructor(deps: RemoteDriveDeps) {
    this.client = deps.client
    this.tokens = deps.tokens
    this.baseUrlProvider = deps.baseUrl
    this.log = deps.log ?? ((): void => undefined)
    this.transfer = new FileTransferService({
      client: deps.client,
      tokens: deps.tokens,
      baseUrl: deps.baseUrl,
      sessions: deps.sessions ?? new MemorySessionStore(),
      ...(deps.onTokensRefreshed ? { onTokensRefreshed: deps.onTokensRefreshed } : {}),
      log: this.log
    })
  }

  private async call(
    method: 'GET' | 'POST' | 'PUT' | 'DELETE',
    path: string,
    opts: { body?: unknown } = {}
  ): Promise<CloudResult<unknown>> {
    const t = this.tokens()
    if (!t) return { ok: false, error: { kind: 'auth', message: '尚未连接云端。' } }
    // ★ 每次请求前刷新地址（提供者模式，禁构造期快照）
    this.client.setBaseUrl(this.baseUrlProvider())
    const res = await this.client.requestWithAuth(method, path, t, opts)
    if (!res.ok) return res
    return { ok: true, data: res.data.json }
  }

  /** 目录/文件列表（parentId 为空 = 根；keyword 为服务端搜索） */
  async list(opts: { parentId?: number | null; keyword?: string } = {}): Promise<CloudResult<DriveListPage>> {
    const qs = new URLSearchParams()
    if (opts.parentId !== undefined && opts.parentId !== null) qs.set('parent_id', String(opts.parentId))
    if (opts.keyword) qs.set('keyword', opts.keyword)
    const suffix = qs.toString() ? `?${qs.toString()}` : ''
    const res = await this.call('GET', `/api/v1/drive/files${suffix}`)
    if (!res.ok) return res
    return { ok: true, data: normalizeDrivePage(res.data) }
  }

  /** 按路径取（服务端 `GET /by-path`） */
  async byPath(path: string): Promise<CloudResult<RemoteDriveItem>> {
    const res = await this.call('GET', `/api/v1/drive/by-path?path=${encodeURIComponent(path)}`)
    if (!res.ok) return res
    const item = normalizeDriveItem(res.data)
    if (!item) return { ok: false, error: { kind: 'malformed', message: '云端返回了无法识别的文件信息。' } }
    return { ok: true, data: item }
  }

  /** 详情 */
  async get(id: number): Promise<CloudResult<RemoteDriveItem>> {
    const res = await this.call('GET', `/api/v1/drive/files/${encodeURIComponent(String(id))}`)
    if (!res.ok) return res
    const item = normalizeDriveItem(res.data)
    if (!item) return { ok: false, error: { kind: 'malformed', message: '云端返回了无法识别的文件信息。' } }
    return { ok: true, data: item }
  }

  /** 重命名 / 移动（只下发传入字段） */
  async rename(id: number, patch: { title?: string; folderId?: number | null }): Promise<CloudResult<RemoteDriveItem>> {
    const body: Record<string, unknown> = {}
    if (patch.title !== undefined) body.title = patch.title
    if (patch.folderId !== undefined) body.folder_id = patch.folderId
    const res = await this.call('PUT', `/api/v1/drive/files/${encodeURIComponent(String(id))}`, { body })
    if (!res.ok) return res
    const item = normalizeDriveItem(res.data)
    if (!item) return { ok: false, error: { kind: 'malformed', message: '云端返回了无法识别的文件信息。' } }
    return { ok: true, data: item }
  }

  /** 删除 */
  async remove(id: number): Promise<CloudResult<true>> {
    const res = await this.call('DELETE', `/api/v1/drive/files/${encodeURIComponent(String(id))}`)
    if (!res.ok) return res
    return { ok: true, data: true }
  }

  /**
   * 上传文件（分块/小文件由 transfer 决定；支持断点续传与进度）。
   * 本方法是**网盘语义的薄适配**——基建在 transfer.ts，聊天附件将复用同一通道。
   */
  async upload(req: {
    filename: string
    fileSize: number
    readChunk: ChunkReader
    parentId?: number | null
    visibility?: 'private' | 'team' | 'public'
    resumeKey?: string
    onProgress?: (p: TransferProgress) => void
    signal?: AbortSignal
  }): Promise<CloudResult<DriveUploadResult>> {
    const res = await this.transfer.upload({
      filename: req.filename,
      fileSize: req.fileSize,
      readChunk: req.readChunk,
      parentId: req.parentId ?? null,
      ...(req.visibility ? { visibility: req.visibility } : {}),
      ...(req.resumeKey ? { resumeKey: req.resumeKey } : {}),
      ...(req.onProgress ? { onProgress: req.onProgress } : {}),
      ...(req.signal ? { signal: req.signal } : {})
    })
    if (!res.ok) return res
    return {
      ok: true,
      data: {
        item: normalizeDriveItem(res.data.json),
        resumed: res.data.resumed,
        uploadedChunks: res.data.uploadedChunks
      }
    }
  }

  /** 未完成上传列表（UI「继续上传」入口） */
  pendingUploads(): UploadSession[] {
    return this.transfer.pendingSessions()
  }

  /** 取消上传会话 */
  async cancelUpload(uploadId: string, resumeKey?: string): Promise<CloudResult<true>> {
    return this.transfer.cancelSession(uploadId, resumeKey)
  }
}

/** 统一错误文案（403 → 不可见中性文案；其余沿用归一化文案） */
export function driveErrorMessage(error: CloudError): string {
  return featureErrorMessage(error)
}
