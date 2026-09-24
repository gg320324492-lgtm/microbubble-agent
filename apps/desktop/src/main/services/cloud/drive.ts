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

/**
 * 归一化文件夹树（DL-2）：递归展开 children，输出**扁平列表**（带 parentId 便于建树/面包屑）。
 * 容忍形状：裸数组 / `{items}` / `{tree}` / `{nodes}` / 节点含 `children|nodes|subfolders`。
 */
export function normalizeTree(raw: unknown): RemoteFolder[] {
  const out: RemoteFolder[] = []
  const pick = (v: unknown): unknown[] => {
    if (Array.isArray(v)) return v
    const o = (v ?? {}) as Record<string, unknown>
    for (const k of ['items', 'tree', 'nodes', 'folders', 'data']) {
      if (Array.isArray(o[k])) return o[k] as unknown[]
    }
    return []
  }
  const walk = (nodes: unknown[], parentId: number | null): void => {
    for (const n of nodes) {
      const f = normalizeFolder(n)
      if (!f) continue
      const o = n as Record<string, unknown>
      out.push({ ...f, parentId: f.parentId ?? parentId })
      const kids = pick(o['children'] ?? o['nodes'] ?? o['subfolders'])
      if (kids.length) walk(kids, f.id)
    }
  }
  walk(pick(raw), null)
  return out
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

  /**
   * 文件列表（DL-2 修复：按网页端 F12 实测契约）。
   *
   * ★ 契约（2026-09-24 用户实测）：
   *   GET /api/v1/drive/files?page=1&page_size=20&sort_by=created_at&sort_order=desc
   *                          &starred_only=false&view=team[&folder_id=336]
   *   · **进入子目录 = 追加 `folder_id`**；根视图**不带** folder_id
   *   · 旧实现用 `parent_id` → 服务端不识别 → 始终返回根视图 → **文件夹内文件不显示**（DL-2 病根）
   */
  async list(
    opts: { folderId?: number | null; keyword?: string; page?: number; pageSize?: number; view?: string } = {}
  ): Promise<CloudResult<DriveListPage>> {
    const qs = new URLSearchParams()
    qs.set('page', String(opts.page ?? 1))
    qs.set('page_size', String(opts.pageSize ?? 100))
    qs.set('sort_by', 'created_at')
    qs.set('sort_order', 'desc')
    qs.set('starred_only', 'false')
    qs.set('view', opts.view ?? 'team')
    // 根视图不带 folder_id（实测契约）
    if (opts.folderId !== undefined && opts.folderId !== null) qs.set('folder_id', String(opts.folderId))
    if (opts.keyword) qs.set('keyword', opts.keyword)
    const res = await this.call('GET', `/api/v1/drive/files?${qs.toString()}`)
    if (!res.ok) return res
    return { ok: true, data: normalizeDrivePage(res.data) }
  }

  /**
   * 文件夹树（DL-2 修复：接实测契约，废弃 /folders 自造树）。
   *   GET /api/v1/drive/tree?scope=team → 侧栏树（组会PPT/实验数据/项目资料…）
   */
  async tree(scope = 'team'): Promise<CloudResult<RemoteFolder[]>> {
    const res = await this.call('GET', `/api/v1/drive/tree?scope=${encodeURIComponent(scope)}`)
    if (!res.ok) return res
    return { ok: true, data: normalizeTree(res.data) }
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

  /** 文件夹列表（父级 /folders，UI1-3 文件夹导航） */
  async listFolders(parentId: number | null = null): Promise<CloudResult<RemoteFolder[]>> {
    const qs = parentId === null ? '' : `?parent_id=${encodeURIComponent(String(parentId))}`
    const res = await this.call('GET', `/api/v1/folders${qs}`)
    if (!res.ok) return res
    return { ok: true, data: normalizeFolderPage(res.data) }
  }

  /** 新建文件夹（父级 POST /folders） */
  async createFolder(name: string, parentId: number | null = null): Promise<CloudResult<RemoteFolder>> {
    const body: Record<string, unknown> = { name }
    if (parentId !== null) body.parent_id = parentId
    const res = await this.call('POST', '/api/v1/folders', { body })
    if (!res.ok) return res
    const f = normalizeFolder(res.data)
    if (!f) return { ok: false, error: { kind: 'malformed', message: '云端返回了无法识别的文件夹信息。' } }
    return { ok: true, data: f }
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

  /**
   * 下载文件（服务端自带 `_check_download_visibility` 可见性校验 → 403 走中性文案）。
   *
   * 说明：当前注入式 HTTP 接口一次返回整个响应体，故实现为「整取后分片落盘 + 分片进度」。
   * 真正的流式下载需要把 http 接口扩展为异步迭代体 —— 已列入遗留项（接口形态不变时不做）。
   */
  async download(
    id: number,
    opts: { write: ChunkWriter; onProgress?: (p: TransferProgress) => void; signal?: AbortSignal }
  ): Promise<CloudResult<DownloadResult>> {
    const t = this.tokens()
    if (!t) return { ok: false, error: { kind: 'auth', message: '尚未连接云端。' } }
    // ★ 每次请求前刷新地址（提供者模式，禁构造期快照）
    this.client.setBaseUrl(this.baseUrlProvider())
    const res = await this.client.requestBinaryWithAuth(`/api/v1/drive/files/${id}/download`, t)
    if (!res.ok) return res
    if (res.data.refreshed) this.log('[drive] 下载触发续期，已回写新 access')

    const bytes = res.data.bytes
    const slices = sliceBytes(bytes)
    let written = 0
    for (const sl of slices) {
      if (opts.signal?.aborted) return { ok: false, error: { kind: 'timeout', message: '下载已取消。' } }
      await opts.write(sl)
      written += sl.length
      opts.onProgress?.({
        transferred: written,
        total: bytes.length,
        percent: bytes.length === 0 ? 100 : Math.floor((written / bytes.length) * 100)
      })
    }
    if (bytes.length === 0) opts.onProgress?.({ transferred: 0, total: 0, percent: 100 })
    return {
      ok: true,
      data: { bytes: written, serverFileName: parseContentDisposition(res.data.headers), slices: slices.length }
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

// ---------------------------------------------------------------- 下载辅助（纯函数）

/** 落盘写入器（注入：生产用 fs 流式写；测试用内存收集） */
export type ChunkWriter = (bytes: Uint8Array) => Promise<void>

export interface DownloadResult {
  /** 实际写入字节数 */
  bytes: number
  /** 服务端给出的文件名（Content-Disposition；无则 null） */
  serverFileName: string | null
  /** 分片数（进度用） */
  slices: number
}

/** 从 Content-Disposition 提取文件名（RFC 5987 的 filename* 优先） */
export function parseContentDisposition(headers: Record<string, string>): string | null {
  const cd = headers['content-disposition'] ?? ''
  if (!cd) return null
  const star = /filename\*=UTF-8''([^;]+)/i.exec(cd)
  if (star?.[1]) {
    try {
      return decodeURIComponent(star[1].trim())
    } catch {
      return star[1].trim()
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(cd)
  return plain?.[1]?.trim() ?? null
}

/** 把字节切成分片（默认 1MB），供分片落盘与进度回调 */
export function sliceBytes(bytes: Uint8Array, sliceSize = 1024 * 1024): Uint8Array[] {
  if (bytes.length === 0) return []
  const out: Uint8Array[] = []
  for (let off = 0; off < bytes.length; off += sliceSize) {
    out.push(bytes.subarray(off, Math.min(off + sliceSize, bytes.length)))
  }
  return out
}

// ---------------------------------------------------------------- 文件夹

/** 网盘文件夹（与父级 FolderItem 对齐） */
export interface RemoteFolder {
  id: number
  name: string
  parentId: number | null
  visibility: string | null
  path: string | null
}

/** 归一化文件夹；缺 id/name 视为无效 */
export function normalizeFolder(raw: unknown): RemoteFolder | null {
  if (!raw || typeof raw !== 'object') return null
  const o = raw as Record<string, unknown>
  const id = asNumber(o.id)
  const name = asString(o.name)
  if (id === null || !name) return null
  return { id, name, parentId: asNumber(o.parent_id), visibility: asString(o.visibility), path: asString(o.path) }
}

/** 归一化文件夹列表（容忍裸数组与 {items,total}） */
export function normalizeFolderPage(raw: unknown): RemoteFolder[] {
  const o = (raw ?? {}) as Record<string, unknown>
  const arr = Array.isArray(raw) ? raw : Array.isArray(o.items) ? o.items : []
  return arr.map(normalizeFolder).filter((x): x is RemoteFolder => x !== null)
}

/** 统一错误文案（403 → 不可见中性文案；其余沿用归一化文案） */
export function driveErrorMessage(error: CloudError): string {
  return featureErrorMessage(error)
}
