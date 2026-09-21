// 远程知识库数据源（工单 M2-3b）— 纯逻辑 + 注入式 HTTP，零 Electron / 零依赖。
//
// 数据源从本地 SQLite 切到父级服务器：数据集中住服务器，组员联网即用。
// 契约来自只读调研（app/api/v1/knowledge.py + app/schemas/knowledge.py + app/services/knowledge_service.py）：
//   GET    /api/v1/knowledge?page=&page_size=&category=&keyword=  → {items: KnowledgeListItem[], total}
//   GET    /api/v1/knowledge/{id}                                 → KnowledgeResponse（含 content）
//   POST   /api/v1/knowledge           body KnowledgeCreate        → 201 KnowledgeResponse
//   PUT    /api/v1/knowledge/{id}      body KnowledgeUpdate        → KnowledgeResponse
//   DELETE /api/v1/knowledge/{id}                                 → 204
//   GET    /api/v1/knowledge/search/semantic?q=&top_k=             → KnowledgeSearchResult[]
//
// ★ 可见性硬要求（工单 §2）：服务端以 `visibility IN ('team','public')` 做**硬过滤**
//   （knowledge_service.py 多处），且私有行 `visibility='private'`。
//   客户端**不自造权限、不预判、不做本地过滤绕过** —— 服务端返回什么就是什么；
//   403/不可见一律按中性文案处理。`visibility` 字段仅**透传**给 UI 展示。

import type { CloudApiClient, CloudError, CloudResult, CloudTokens } from './api-client'

/** 列表项（与父级 KnowledgeListItem 对齐，仅取桌面端需要的字段） */
export interface RemoteKnowledgeItem {
  id: number
  title: string
  category?: string | null
  tags?: string[] | null
  summary?: string | null
  /** content 前 200 字符（服务端给的卡片预览） */
  snippet?: string | null
  /** 'private' | 'team' | 'public' —— 仅透传展示，不参与任何本地判定 */
  visibility?: string | null
  createdAt?: string | null
  updatedAt?: string | null
  /** 是否有上传文件（file_type 非空时服务端会给） */
  fileType?: string | null
  /** 来源类型（用于列表分组展示） */
  sourceTypeHint?: string | null
}

export interface RemoteKnowledgeDetail extends RemoteKnowledgeItem {
  content?: string | null
  formattedContent?: string | null
  source?: string | null
  sourceType?: string | null
  keyConcepts?: string[] | null
}

export interface KnowledgeListPage {
  items: RemoteKnowledgeItem[]
  total: number
  page: number
  pageSize: number
}

export interface CreateKnowledgeInput {
  title: string
  content: string
  category?: string
  tags?: string[]
  sourceType?: string
}

export interface UpdateKnowledgeInput {
  title?: string
  content?: string
  category?: string
  tags?: string[]
}

/** 数据源可用状态（驱动渲染层的引导态） */
export type KnowledgeSourceState = 'ready' | 'unbound' | 'offline' | 'expired'

/** 令牌提供者：返回 null 表示未绑定 */
export type TokensProvider = () => CloudTokens | null

export interface RemoteKnowledgeDeps {
  client: CloudApiClient
  tokens: TokensProvider
  /**
   * 当前绑定的服务器地址提供者（**每次请求前刷新**）。
   * 必要性：客户端在构造时捕获 baseUrl，若用户之后绑定到别的服务器（如自建/局域网），
   * 不刷新就会继续打旧地址 → 401。模拟 E2E 实测抓到过这个缺陷。
   */
  baseUrl?: () => string
  /** 续期成功后回调（装配层据此把新 access 落回加密存储） */
  onTokensRefreshed?: (tokens: CloudTokens) => void
  log?: (message: string) => void
}

// ---------------------------------------------------------------- 归一化（防御畸形响应）

function asString(v: unknown): string | null {
  return typeof v === 'string' ? v : null
}
function asStringArray(v: unknown): string[] | null {
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : null
}

/** 归一化列表项；缺 id/title 视为无效项（丢弃而不是让 UI 崩） */
export function normalizeKnowledgeItem(raw: unknown): RemoteKnowledgeItem | null {
  if (!raw || typeof raw !== 'object') return null
  const o = raw as Record<string, unknown>
  const id = typeof o.id === 'number' ? o.id : typeof o.id === 'string' && /^\d+$/.test(o.id) ? Number(o.id) : null
  const title = asString(o.title)
  if (id === null || title === null) return null
  return {
    id,
    title,
    category: asString(o.category),
    tags: asStringArray(o.tags),
    summary: asString(o.summary),
    snippet: asString(o.snippet),
    visibility: asString(o.visibility),
    createdAt: asString(o.created_at) ?? asString(o.createdAt),
    updatedAt: asString(o.updated_at) ?? asString(o.updatedAt),
    fileType: asString(o.file_type) ?? asString(o.fileType)
  }
}

/** 归一化详情（在列表项基础上补正文等字段） */
export function normalizeKnowledgeDetail(raw: unknown): RemoteKnowledgeDetail | null {
  const base = normalizeKnowledgeItem(raw)
  if (!base) return null
  const o = raw as Record<string, unknown>
  return {
    ...base,
    content: asString(o.content),
    formattedContent: asString(o.formatted_content) ?? asString(o.formattedContent),
    source: asString(o.source),
    sourceType: asString(o.source_type) ?? asString(o.sourceType),
    keyConcepts: asStringArray(o.key_concepts) ?? asStringArray(o.keyConcepts)
  }
}

/** 归一化列表封装：`{items,total}`；容忍服务端直接返回数组（旧版形状） */
export function normalizeKnowledgePage(raw: unknown, page: number, pageSize: number): KnowledgeListPage {
  const o = (raw ?? {}) as Record<string, unknown>
  const rawItems = Array.isArray(raw) ? raw : Array.isArray(o.items) ? o.items : []
  const items = rawItems.map(normalizeKnowledgeItem).filter((x): x is RemoteKnowledgeItem => x !== null)
  const total = typeof o.total === 'number' ? o.total : items.length
  return { items, total, page, pageSize }
}

/** 归一化检索结果数组 */
export function normalizeSearchResults(raw: unknown): RemoteKnowledgeItem[] {
  const arr = Array.isArray(raw) ? raw : Array.isArray((raw as { items?: unknown })?.items) ? (raw as { items: unknown[] }).items : []
  return arr.map(normalizeKnowledgeItem).filter((x): x is RemoteKnowledgeItem => x !== null)
}

// ---------------------------------------------------------------- 状态与引导文案

/** 由绑定状态 + 最近错误推断数据源状态（纯函数） */
export function knowledgeSourceState(binding: { status: string }, error?: CloudError): KnowledgeSourceState {
  if (binding.status === 'unbound') return 'unbound'
  if (binding.status === 'expired') return 'expired'
  if (error && (error.kind === 'network' || error.kind === 'timeout')) return 'offline'
  return 'ready'
}

/** 引导态中性文案（未绑定/离线/失效时展示；不暴露技术细节） */
export function knowledgeGuidance(state: KnowledgeSourceState): { title: string; hint: string; canOpenSettings: boolean } {
  switch (state) {
    case 'unbound':
      return {
        title: '需连接云端才能使用知识库',
        hint: '知识库数据保存在课题组服务器上。请到「设置 · 云端连接」绑定你的课题组账号。',
        canOpenSettings: true
      }
    case 'expired':
      return {
        title: '云端登录状态已失效',
        hint: '请到「设置 · 云端连接」重新绑定账号。',
        canOpenSettings: true
      }
    case 'offline':
      return {
        title: '当前离线',
        hint: '知识库需要联网访问。请检查网络后重试。',
        canOpenSettings: false
      }
    case 'ready':
      return { title: '', hint: '', canOpenSettings: false }
  }
}

/** 不可见/无权限的中性处理（工单 §2：不本地过滤、不预判，403 走中性文案） */
export function inaccessibleMessage(): string {
  return '这条内容你没有查看权限。如需访问，请联系课题组管理员。'
}

// ---------------------------------------------------------------- 远程知识库服务

export class RemoteKnowledgeService {
  private readonly client: CloudApiClient
  private readonly tokens: TokensProvider
  private readonly baseUrlProvider: (() => string) | null
  private readonly onTokensRefreshed: (tokens: CloudTokens) => void
  private readonly log: (m: string) => void

  constructor(deps: RemoteKnowledgeDeps) {
    this.client = deps.client
    this.tokens = deps.tokens
    this.baseUrlProvider = deps.baseUrl ?? null
    this.onTokensRefreshed = deps.onTokensRefreshed ?? ((): void => undefined)
    this.log = deps.log ?? ((): void => undefined)
  }

  /** 未绑定 → 直接返回 unbound 错误（不发起请求） */
  private requireTokens(): CloudResult<CloudTokens> {
    const t = this.tokens()
    if (!t) {
      return { ok: false, error: { kind: 'auth', message: '尚未绑定云端账号。' } }
    }
    return { ok: true, data: t }
  }

  /** 统一出口：401 自动续期一次由 M2-3a 客户端负责；续期成功回写令牌 */
  private async call(
    method: 'GET' | 'POST' | 'PUT' | 'DELETE',
    path: string,
    opts: { body?: unknown } = {}
  ): Promise<CloudResult<unknown>> {
    const tok = this.requireTokens()
    if (!tok.ok) return tok
    // ★ 每次请求前按当前绑定刷新地址（用户可能中途换了服务器）
    if (this.baseUrlProvider) this.client.setBaseUrl(this.baseUrlProvider())
    const res = await this.client.requestWithAuth(method, path, tok.data, opts)
    if (!res.ok) return res
    if (res.data.refreshed) {
      this.log('[cloud] 知识库请求触发续期，已回写新 access')
      this.onTokensRefreshed(res.data.tokens)
    }
    return { ok: true, data: res.data.json }
  }

  /** 列表（分页/分类/关键词） */
  async list(opts: { page?: number; pageSize?: number; category?: string; keyword?: string } = {}): Promise<CloudResult<KnowledgeListPage>> {
    const page = Math.max(1, opts.page ?? 1)
    const pageSize = Math.min(100, Math.max(1, opts.pageSize ?? 20))
    const qs = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
    if (opts.category) qs.set('category', opts.category)
    if (opts.keyword) qs.set('keyword', opts.keyword)
    const res = await this.call('GET', `/api/v1/knowledge?${qs.toString()}`)
    if (!res.ok) return res
    return { ok: true, data: normalizeKnowledgePage(res.data, page, pageSize) }
  }

  /**
   * 检索 —— **走服务端检索端点**。
   * 本地 CJK bigram 逻辑只适用于本地模式，远程模式一律交给服务端（工单 §1 明确）。
   */
  async search(query: string, topK = 10): Promise<CloudResult<RemoteKnowledgeItem[]>> {
    const q = query.trim()
    if (!q) return { ok: true, data: [] }
    const qs = new URLSearchParams({ q, top_k: String(Math.min(20, Math.max(1, topK))) })
    const res = await this.call('GET', `/api/v1/knowledge/search/semantic?${qs.toString()}`)
    if (!res.ok) return res
    return { ok: true, data: normalizeSearchResults(res.data) }
  }

  /** 详情（含正文） */
  async get(id: number): Promise<CloudResult<RemoteKnowledgeDetail>> {
    const res = await this.call('GET', `/api/v1/knowledge/${encodeURIComponent(String(id))}`)
    if (!res.ok) return res
    const detail = normalizeKnowledgeDetail(res.data)
    if (!detail) {
      return { ok: false, error: { kind: 'malformed', message: '云端返回了无法识别的知识条目。' } }
    }
    return { ok: true, data: detail }
  }

  /** 新建 */
  async create(input: CreateKnowledgeInput): Promise<CloudResult<RemoteKnowledgeDetail>> {
    const body: Record<string, unknown> = { title: input.title, content: input.content }
    if (input.category) body.category = input.category
    if (input.tags) body.tags = input.tags
    if (input.sourceType) body.source_type = input.sourceType
    const res = await this.call('POST', '/api/v1/knowledge', { body })
    if (!res.ok) return res
    const detail = normalizeKnowledgeDetail(res.data)
    if (!detail) return { ok: false, error: { kind: 'malformed', message: '云端返回了无法识别的知识条目。' } }
    return { ok: true, data: detail }
  }

  /** 编辑 */
  async update(id: number, input: UpdateKnowledgeInput): Promise<CloudResult<RemoteKnowledgeDetail>> {
    const body: Record<string, unknown> = {}
    if (input.title !== undefined) body.title = input.title
    if (input.content !== undefined) body.content = input.content
    if (input.category !== undefined) body.category = input.category
    if (input.tags !== undefined) body.tags = input.tags
    const res = await this.call('PUT', `/api/v1/knowledge/${encodeURIComponent(String(id))}`, { body })
    if (!res.ok) return res
    const detail = normalizeKnowledgeDetail(res.data)
    if (!detail) return { ok: false, error: { kind: 'malformed', message: '云端返回了无法识别的知识条目。' } }
    return { ok: true, data: detail }
  }

  /** 删除（服务端返回 204 空体） */
  async remove(id: number): Promise<CloudResult<true>> {
    const res = await this.call('DELETE', `/api/v1/knowledge/${encodeURIComponent(String(id))}`)
    if (!res.ok) return res
    return { ok: true, data: true }
  }
}

/** 统一把服务端错误转成用户可见文案（403 走不可见中性文案，其余沿用 M2-3a 归一化） */
export function knowledgeErrorMessage(error: CloudError): string {
  if (error.kind === 'client' && /403|forbidden/i.test(error.detail ?? '')) return inaccessibleMessage()
  return error.message
}

// ---------------------------------------------------------------- 渲染层形状映射
//
// 目标：**保持渲染层既有调用面不变**（`knowledge.list/get/search/...` 的返回形状），
// 只把数据源从本地 SQLite 换成父级服务器 —— 这样 M2-3b 不需要重写知识库页面。

function toMillis(v: string | null | undefined): number {
  if (!v) return 0
  const t = Date.parse(v)
  return Number.isFinite(t) ? t : 0
}

export interface KnowledgeDocMetaLike {
  id: number
  title: string
  tags: string[]
  fileName: string | null
  fileSize: number
  source: string
  createdAt: number
  updatedAt: number
}

export function toDocMeta(item: RemoteKnowledgeItem): KnowledgeDocMetaLike {
  return {
    id: item.id,
    title: item.title,
    tags: item.tags ?? [],
    fileName: item.fileType ? `remote.${item.fileType}` : null,
    fileSize: 0,
    source: item.category ?? item.sourceTypeHint ?? 'cloud',
    createdAt: toMillis(item.createdAt),
    updatedAt: toMillis(item.updatedAt)
  }
}

export function toDocFull(detail: RemoteKnowledgeDetail): KnowledgeDocMetaLike & { content: string } {
  return { ...toDocMeta(detail), content: detail.content ?? detail.formattedContent ?? '' }
}

export function toSearchHit(item: RemoteKnowledgeItem): {
  id: number
  title: string
  tags: string[]
  snippet: string
  highlight: { start: number; end: number } | null
  updatedAt: number
} {
  return {
    id: item.id,
    title: item.title,
    tags: item.tags ?? [],
    snippet: item.snippet ?? item.summary ?? '',
    highlight: null, // 服务端检索不返回高亮区间；渲染层已容忍 null
    updatedAt: toMillis(item.updatedAt)
  }
}
