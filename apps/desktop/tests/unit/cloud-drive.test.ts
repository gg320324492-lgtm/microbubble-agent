// M2-3c 远程网盘 + 通用分块文件通道 —— 全部离线，HTTP 注入式
// 契约来自 app/api/v1/drive_*.py 只读调研（前缀 /drive、/folders、/drive/chunked-uploads）
import { describe, expect, it } from 'vitest'
import { CloudApiClient, type CloudHttpFn, type CloudHttpRequest, type CloudHttpResponse, type CloudTokens } from '@main/services/cloud/api-client'
import { RemoteDriveService, driveErrorMessage, normalizeDriveItem, normalizeDrivePage, parseContentDisposition, sliceBytes } from '@main/services/cloud/drive'
import { DEFAULT_CHUNK_SIZE, MemorySessionStore, chunkCount, type ChunkReader } from '@main/services/cloud/transfer'
import { cloudGuidance, cloudUsableState, featureErrorMessage, inaccessibleMessage } from '@main/services/cloud/guidance'

function res(status: number, json: unknown, headers: Record<string, string> = {}): CloudHttpResponse {
  return { status, headers, text: typeof json === 'string' ? json : JSON.stringify(json) }
}

interface Harness {
  svc: RemoteDriveService
  requests: CloudHttpRequest[]
  sessions: MemorySessionStore
  refreshed: CloudTokens[]
}

function harness(
  script: ((req: CloudHttpRequest) => CloudHttpResponse | Promise<CloudHttpResponse>)[],
  opts: { tokens?: CloudTokens | null; baseUrl?: () => string } = {}
): Harness {
  const requests: CloudHttpRequest[] = []
  let i = 0
  const http: CloudHttpFn = async (req) => {
    requests.push(req)
    const step = script[Math.min(i, script.length - 1)]!
    i += 1
    return step(req)
  }
  const sessions = new MemorySessionStore()
  const refreshed: CloudTokens[] = []
  let current = 'https://agent.mnb-lab.cn'
  const svc = new RemoteDriveService({
    client: new CloudApiClient({ http, baseUrl: current }),
    tokens: () => (opts.tokens === undefined ? { accessToken: 'AT1', refreshToken: 'RT1' } : opts.tokens),
    baseUrl: opts.baseUrl ?? (() => current),
    sessions,
    onTokensRefreshed: (t) => refreshed.push(t)
  })
  void current
  return { svc, requests, sessions, refreshed }
}

// 服务端形状样例（虚构占位）
const fileItem = (id: number, over: Record<string, unknown> = {}): Record<string, unknown> => ({
  id,
  title: `占位文件${id}.txt`,
  file_path: `drive/${id}`,
  file_name: `占位文件${id}.txt`,
  file_type: 'txt',
  file_size: 1234,
  storage_mode: 'drive',
  visibility: 'team',
  folder_id: null,
  owner_name: '演示同学',
  created_at: '2026-09-01T10:00:00',
  updated_at: '2026-09-02T11:00:00',
  ...over
})

const uploadSession = (over: Record<string, unknown> = {}): Record<string, unknown> => ({
  upload_id: 'up-1',
  filename: '占位大文件.bin',
  file_size: 12 * 1024 * 1024,
  chunk_size: DEFAULT_CHUNK_SIZE,
  total_chunks: 3,
  uploaded_chunks: [],
  status: 'pending',
  expires_at: '2026-09-22T00:00:00',
  ...over
})

/** 从内存读分块（测试用，不碰盘） */
function memoryReader(size: number): ChunkReader {
  const buf = new Uint8Array(size)
  for (let i = 0; i < size; i += 1) buf[i] = i % 256
  return async (offset, length) => buf.slice(offset, offset + length)
}

// ---------------------------------------------------------------- 1 适配回放（≥4）

describe('网盘契约适配回放', () => {
  it('★ DL-2 契约：子目录列表用 folder_id（不是 parent_id），带 view=team/排序/分页', async () => {
    const h = harness([() => res(200, { items: [fileItem(1), fileItem(2)], total: 2 })])
    const r = await h.svc.list({ folderId: 336, keyword: '占位' })
    expect(r.ok).toBe(true)
    if (r.ok) {
      expect(r.data.total).toBe(2)
      expect(r.data.items[0]).toMatchObject({ id: 1, fileName: '占位文件1.txt', fileType: 'txt', visibility: 'team' })
    }
    const url = new URL(h.requests[0]!.url)
    expect(url.pathname).toBe('/api/v1/drive/files')
    // ★ 用户 F12 实测契约参数
    expect(url.searchParams.get('folder_id')).toBe('336')
    expect(url.searchParams.get('view')).toBe('team')
    expect(url.searchParams.get('sort_by')).toBe('created_at')
    expect(url.searchParams.get('sort_order')).toBe('desc')
    expect(url.searchParams.get('starred_only')).toBe('false')
    expect(url.searchParams.get('page')).toBe('1')
    expect(url.searchParams.get('page_size')).toBe('100')
    expect(url.searchParams.get('keyword')).toBe('占位')
    // 旧参数必须消失（DL-2 病根：parent_id 服务端不识别 → 永远返回根视图）
    expect(url.searchParams.get('parent_id')).toBeNull()
    expect(h.requests[0]!.headers['authorization']).toBe('Bearer AT1')
  })

  it('★ DL-2 契约：根视图**不带 folder_id**，但带 view=team 与排序分页', async () => {
    const h = harness([() => res(200, { items: [], total: 0 })])
    await h.svc.list()
    const url = new URL(h.requests[0]!.url)
    expect(url.searchParams.get('folder_id')).toBeNull()
    expect(url.searchParams.get('parent_id')).toBeNull()
    expect(url.searchParams.get('view')).toBe('team')
    expect(url.searchParams.get('page_size')).toBe('100')
  })

  it('详情 / 按路径：GET /drive/files/{id} 与 GET /drive/by-path', async () => {
    const h = harness([() => res(200, fileItem(9)), () => res(200, fileItem(10))])
    const a = await h.svc.get(9)
    const b = await h.svc.byPath('sub/dir/占位.txt')
    expect(a.ok && a.data.id).toBe(9)
    expect(b.ok && b.data.id).toBe(10)
    expect(h.requests[0]!.url).toBe('https://agent.mnb-lab.cn/api/v1/drive/files/9')
    expect(h.requests[1]!.url).toContain('/api/v1/drive/by-path?path=')
  })

  it('重命名：PUT /drive/files/{id} 只带传入字段', async () => {
    const h = harness([() => res(200, fileItem(3, { title: '改名后.txt' }))])
    const r = await h.svc.rename(3, { title: '改名后.txt' })
    expect(r.ok).toBe(true)
    expect(h.requests[0]!.method).toBe('PUT')
    expect(JSON.parse(h.requests[0]!.body!)).toEqual({ title: '改名后.txt' })
  })

  it('删除：DELETE，204 空体不报错', async () => {
    const h = harness([() => res(204, '')])
    const r = await h.svc.remove(4)
    expect(r.ok).toBe(true)
    expect(h.requests[0]!.method).toBe('DELETE')
    expect(h.requests[0]!.url).toBe('https://agent.mnb-lab.cn/api/v1/drive/files/4')
  })
})

// ---------------------------------------------------------------- 1b 树端点定论（DL-3）

describe('DL-3 文件夹树端点定论（web 源码只读调研）', () => {
  // 病根回放：M2-3b 实现用 /api/v1/drive/tree —— 该路径服务端不存在（总指挥用用户 F12 令牌实测 404）
  //   → 树恒为空 → 网盘页「空白」。定论依据：web/src/composables/useFolderTree.js
  //   fetchTree() = fetch('/api/v1/folders/tree?scope=…')。
  it('★ tree() 请求 /api/v1/folders/tree?scope=team（旧 404 路径一旦回归立即爆红）', async () => {
    const h = harness([() => res(200, { tree: [{ id: 10, name: '组会PPT', children: [] }], max_depth: 3, scope: 'team' })])
    const r = await h.svc.tree('team')
    expect(r.ok).toBe(true)
    const url = new URL(h.requests[0]!.url)
    expect(url.pathname).toBe('/api/v1/folders/tree')
    expect(url.searchParams.get('scope')).toBe('team')
    expect(url.pathname).not.toBe('/api/v1/drive/tree')
  })

  it('★ 后端真实形状回放：{tree, max_depth, scope}；节点无 parent_id 时按遍历上下文补链', async () => {
    // 形状取自 app/api/v1/drive_folders.py get_folder_tree：节点 {id, name, children} + owner_name/is_starred
    const raw = {
      tree: [
        { id: 10, name: '组会PPT', owner_name: '管理员', is_starred: false, children: [{ id: 336, name: '艾琳琳', owner_name: '艾琳琳' }] },
        { id: 20, name: '实验数据', children: [] }
      ],
      max_depth: 3,
      scope: 'team'
    }
    const h = harness([() => res(200, raw)])
    const r = await h.svc.tree()
    expect(r.ok).toBe(true)
    if (r.ok) {
      expect(r.data.map((f) => f.name)).toEqual(['组会PPT', '艾琳琳', '实验数据'])
      expect(r.data.find((f) => f.id === 10)?.parentId).toBeNull()
      expect(r.data.find((f) => f.id === 336)?.parentId).toBe(10)
    }
  })

  it('树请求失败（如旧路径 404）错误透传：不吞错、不返回半棵树', async () => {
    const h = harness([() => res(404, { error: { code: 'NOT_FOUND', message: 'Not Found' } })])
    const r = await h.svc.tree()
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.error.kind).toBe('client')
  })
})

// ---------------------------------------------------------------- 2 分块上传时序（≥4）

describe('分块上传三件套时序', () => {
  it('大文件：init → chunks(0..2) → complete，顺序与路径正确', async () => {
    const size = 3 * DEFAULT_CHUNK_SIZE // 3 块
    const h = harness([
      () => res(201, uploadSession({ file_size: size, total_chunks: 3 })), // init
      () => res(200, uploadSession({ file_size: size, total_chunks: 3, uploaded_chunks: [0] })),
      () => res(200, uploadSession({ file_size: size, total_chunks: 3, uploaded_chunks: [0, 1] })),
      () => res(200, fileItem(77)) // complete
    ])
    const progress: number[] = []
    const r = await h.svc.upload({
      filename: '占位大文件.bin',
      fileSize: size,
      readChunk: memoryReader(size),
      onProgress: (p) => progress.push(p.percent)
    })
    expect(r.ok).toBe(true)
    if (r.ok) {
      expect(r.data.item?.id).toBe(77)
      expect(r.data.uploadedChunks).toBe(3)
      expect(r.data.resumed).toBe(false)
    }
    const paths = h.requests.map((q) => `${q.method} ${new URL(q.url).pathname}`)
    expect(paths).toEqual([
      'POST /api/v1/drive/chunked-uploads/init',
      'PUT /api/v1/drive/chunked-uploads/up-1/chunks/0',
      'PUT /api/v1/drive/chunked-uploads/up-1/chunks/1',
      'PUT /api/v1/drive/chunked-uploads/up-1/chunks/2',
      'POST /api/v1/drive/chunked-uploads/up-1/complete'
    ])
    expect(progress.at(-1)).toBe(100)
    expect(h.sessions.list()).toHaveLength(0) // 完成后清本地会话
  })

  it('init 请求体：filename/file_size/chunk_size 必填，parent_id 可选', async () => {
    const size = 2 * DEFAULT_CHUNK_SIZE
    const h = harness([() => res(201, uploadSession({ file_size: size, total_chunks: 2 })), () => res(200, uploadSession({ total_chunks: 2, uploaded_chunks: [0, 1] })), () => res(200, uploadSession({ total_chunks: 2, uploaded_chunks: [0, 1] })), () => res(200, fileItem(1))])
    await h.svc.upload({ filename: 'a.bin', fileSize: size, readChunk: memoryReader(size), parentId: 42 })
    const initBody = JSON.parse(h.requests[0]!.body!) as Record<string, unknown>
    expect(initBody.filename).toBe('a.bin')
    expect(initBody.file_size).toBe(size)
    expect(initBody.chunk_size).toBe(DEFAULT_CHUNK_SIZE)
    expect(initBody.parent_id).toBe(42)
  })

  it('小文件走简化路径：POST /drive/files/upload，不建会话', async () => {
    const size = 1024
    const h = harness([() => res(201, fileItem(88))])
    const r = await h.svc.upload({ filename: '小.txt', fileSize: size, readChunk: memoryReader(size) })
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data.uploadedChunks).toBe(1)
    expect(h.requests).toHaveLength(1)
    expect(h.requests[0]!.url).toBe('https://agent.mnb-lab.cn/api/v1/drive/files/upload')
    expect(h.sessions.list()).toHaveLength(0)
  })

  it('chunkCount 口径：向上取整（与服务端 total_chunks 一致）', () => {
    expect(chunkCount(0)).toBe(0)
    expect(chunkCount(1)).toBe(1)
    expect(chunkCount(DEFAULT_CHUNK_SIZE)).toBe(1)
    expect(chunkCount(DEFAULT_CHUNK_SIZE + 1)).toBe(2)
    expect(chunkCount(3 * DEFAULT_CHUNK_SIZE)).toBe(3)
  })
})

// ---------------------------------------------------------------- 3 断点续传（≥3）

describe('断点续传', () => {
  it('中断后重传：以服务端 uploaded_chunks 为准，只补缺口', async () => {
    const size = 4 * DEFAULT_CHUNK_SIZE // 4 块
    // 第一次：传完第 0 块后中断（第 1 块返回错误）
    const h1 = harness([
      () => res(201, uploadSession({ file_size: size, total_chunks: 4 })),
      () => res(200, uploadSession({ file_size: size, total_chunks: 4, uploaded_chunks: [0] })),
      () => res(500, { error: { code: 'BOOM', message: 'x' } }) // 第 1 块失败
    ])
    const first = await h1.svc.upload({ filename: 'big.bin', fileSize: size, readChunk: memoryReader(size), resumeKey: 'k1' })
    expect(first.ok).toBe(false)
    expect(h1.sessions.list()).toHaveLength(1) // ★ 会话已持久化（断点留痕）
    expect(h1.sessions.get('k1')?.uploadedChunks).toEqual([0])

    // 第二次：服务端说已收到 0、1 两块 → 只传 2、3
    const h2 = harness([
      () => res(200, uploadSession({ file_size: size, total_chunks: 4, uploaded_chunks: [0, 1] })), // GET 会话
      () => res(200, uploadSession({ total_chunks: 4, uploaded_chunks: [0, 1, 2] })),
      () => res(200, uploadSession({ total_chunks: 4, uploaded_chunks: [0, 1, 2, 3] })),
      () => res(200, fileItem(99))
    ])
    h2.sessions.set('k1', h1.sessions.get('k1')!) // 复用同一持久化会话
    const progress: { percent: number; skipped?: number }[] = []
    const second = await h2.svc.upload({
      filename: 'big.bin',
      fileSize: size,
      readChunk: memoryReader(size),
      resumeKey: 'k1',
      onProgress: (p) => progress.push({ percent: p.percent, ...(p.skippedChunks === undefined ? {} : { skipped: p.skippedChunks }) })
    })
    expect(second.ok).toBe(true)
    if (second.ok) {
      expect(second.data.resumed).toBe(true)
      expect(second.data.uploadedChunks).toBe(4)
    }
    const putIndexes = h2.requests
      .filter((q) => q.method === 'PUT')
      .map((q) => Number(new URL(q.url).pathname.split('/').pop()))
    expect(putIndexes).toEqual([2, 3]) // ★ 只补缺口，不重头
    expect(progress[0]?.skipped).toBe(2) // 起始即报告跳过 2 块
  })

  it('会话在服务端已失效：本地会话被清并重新创建', async () => {
    const size = 2 * DEFAULT_CHUNK_SIZE
    const h = harness([
      () => res(404, { error: { code: 'NOT_FOUND', message: 'gone' } }), // GET 会话失效
      () => res(201, uploadSession({ file_size: size, total_chunks: 2 })),
      () => res(200, uploadSession({ total_chunks: 2, uploaded_chunks: [0] })),
      () => res(200, uploadSession({ total_chunks: 2, uploaded_chunks: [0, 1] })),
      () => res(200, fileItem(5))
    ])
    h.sessions.set('k2', { uploadId: 'old', filename: 'x', fileSize: size, chunkSize: DEFAULT_CHUNK_SIZE, totalChunks: 2, uploadedChunks: [0], status: 'pending', expiresAt: '', updatedAt: 0 })
    const r = await h.svc.upload({ filename: 'x', fileSize: size, readChunk: memoryReader(size), resumeKey: 'k2' })
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data.resumed).toBe(false)
    expect(h.requests[0]!.method).toBe('GET') // 先查会话
    expect(h.requests[1]!.url).toContain('/init') // 再重建
  })

  it('会话持久化往返：MemorySessionStore 读写一致；pendingUploads 可列出', async () => {
    const store = new MemorySessionStore()
    const s = { uploadId: 'u1', filename: 'f', fileSize: 10, chunkSize: 4, totalChunks: 3, uploadedChunks: [0, 2], status: 'pending', expiresAt: 'x', updatedAt: 1 }
    store.set('k', s)
    expect(store.get('k')).toEqual(s)
    expect(store.list()).toHaveLength(1)
    store.remove('k')
    expect(store.get('k')).toBeNull()
    expect(store.list()).toHaveLength(0)

    const h = harness([() => res(200, { items: [], total: 0 })])
    h.sessions.set('p', s)
    expect(h.svc.pendingUploads()).toHaveLength(1)
  })

  it('取消上传：DELETE 会话并清本地', async () => {
    const h = harness([() => res(204, '')])
    h.sessions.set('k3', { uploadId: 'up-9', filename: 'f', fileSize: 1, chunkSize: 1, totalChunks: 1, uploadedChunks: [], status: 'pending', expiresAt: '', updatedAt: 0 })
    const r = await h.svc.cancelUpload('up-9', 'k3')
    expect(r.ok).toBe(true)
    expect(h.requests[0]!.method).toBe('DELETE')
    expect(h.sessions.list()).toHaveLength(0)
  })
})

// ---------------------------------------------------------------- 4 可见性（≥2）

describe('可见性沿用服务端', () => {
  it('visibility 三值原样透传，一条不剔除（客户端不本地过滤）', async () => {
    const h = harness([() => res(200, { items: [fileItem(1, { visibility: 'private' }), fileItem(2, { visibility: 'team' }), fileItem(3, { visibility: 'public' })], total: 3 })])
    const r = await h.svc.list()
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data.items.map((x) => x.visibility)).toEqual(['private', 'team', 'public'])
  })

  it('403 不可见：中性文案，不暴露服务端原文与 id', async () => {
    const h = harness([() => res(403, { error: { code: 'FORBIDDEN', message: 'no permission on file 88' } })])
    const r = await h.svc.get(88)
    expect(r.ok).toBe(false)
    if (!r.ok) {
      const msg = driveErrorMessage(r.error)
      expect(msg).not.toMatch(/FORBIDDEN|no permission|88/)
      expect(featureErrorMessage({ kind: 'client', message: 'x', detail: '403 forbidden' })).toBe(inaccessibleMessage())
    }
  })
})

// ---------------------------------------------------------------- 5 提供者刷新（≥1）

describe('外部状态「提供者」模式', () => {
  it('改绑定后请求打新地址（禁构造期快照 —— M2-3b 同款回归）', async () => {
    let current = 'https://agent.mnb-lab.cn'
    const h = harness([() => res(200, { items: [], total: 0 })], { baseUrl: () => current })
    await h.svc.list()
    expect(h.requests[0]!.url.startsWith('https://agent.mnb-lab.cn')).toBe(true)
    current = 'http://127.0.0.1:8899'
    await h.svc.list()
    expect(h.requests[1]!.url.startsWith('http://127.0.0.1:8899')).toBe(true)
  })

  it('未绑定：不发请求，直接给出引导（且状态机文案由 guidance 统一给出）', async () => {
    const h = harness([() => res(200, { items: [], total: 0 })], { tokens: null })
    const r = await h.svc.list()
    expect(r.ok).toBe(false)
    expect(h.requests).toHaveLength(0)
    const state = cloudUsableState({ status: 'unbound' })
    const g = cloudGuidance(state, '网盘')
    expect(g.title).toContain('网盘')
    expect(g.canOpenSettings).toBe(true)
    // ★ 组件不得硬编码措辞：文案来自集中状态机
    expect(g.actionLabel).toContain('设置')
    expect(cloudGuidance('offline', '网盘').canOpenSettings).toBe(false)
    expect(cloudGuidance('ready', '网盘').title).toBe('')
  })
})

// ---------------------------------------------------------------- 6 协议健壮（≥1）

describe('畸形响应不崩溃', () => {
  it('列表/详情畸形：丢弃无效项、明确报错，不抛异常', async () => {
    expect(normalizeDrivePage(null).items).toEqual([])
    expect(normalizeDrivePage({ items: 'oops' }).items).toEqual([])
    expect(normalizeDrivePage([fileItem(1)]).items).toHaveLength(1) // 容忍裸数组
    expect(normalizeDriveItem({ file_name: '无 id.txt' })).toBeNull()
    expect(normalizeDriveItem({ id: 1 })).toBeNull()
    expect(normalizeDriveItem('str')).toBeNull()

    const h = harness([() => res(200, '"just a string"')])
    const r = await h.svc.get(1)
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.error.kind).toBe('malformed')
  })
})

// ---------------------------------------------------------------- 7 下载（≥3）

describe('文件下载', () => {
  /** 构造带二进制的响应 */
  const binRes = (bytes: Uint8Array, headers: Record<string, string> = {}): CloudHttpResponse => ({
    status: 200,
    headers,
    text: '',
    bytes
  })

  function downloadHarness(script: ((req: CloudHttpRequest) => CloudHttpResponse | Promise<CloudHttpResponse>)[]): {
    svc: RemoteDriveService
    requests: CloudHttpRequest[]
  } {
    const requests: CloudHttpRequest[] = []
    let i = 0
    const http: CloudHttpFn = async (req) => {
      requests.push(req)
      const step = script[Math.min(i, script.length - 1)]!
      i += 1
      return step(req)
    }
    const svc = new RemoteDriveService({
      client: new CloudApiClient({ http, baseUrl: 'https://agent.mnb-lab.cn' }),
      tokens: () => ({ accessToken: 'AT1', refreshToken: 'RT1' }),
      baseUrl: () => 'https://agent.mnb-lab.cn'
    })
    return { svc, requests }
  }

  it('下载：请求正确端点 + 分片落盘 + 进度到 100% + 字节数一致', async () => {
    const payload = new Uint8Array(2.5 * 1024 * 1024) // 2.5MB → 3 片（1MB 切）
    for (let i = 0; i < payload.length; i += 1) payload[i] = i % 251
    const h = downloadHarness([() => binRes(payload, { 'content-disposition': 'attachment; filename="占位.bin"' })])
    const chunks: Uint8Array[] = []
    const progress: number[] = []
    const r = await h.svc.download(7, {
      write: async (b) => {
        chunks.push(b)
      },
      onProgress: (p) => progress.push(p.percent)
    })
    expect(r.ok).toBe(true)
    if (r.ok) {
      expect(r.data.bytes).toBe(payload.length)
      expect(r.data.slices).toBe(3)
      expect(r.data.serverFileName).toBe('占位.bin')
    }
    // 落盘内容与源字节逐字节一致
    const merged = Buffer.concat(chunks.map((c) => Buffer.from(c)))
    expect(merged.length).toBe(payload.length)
    expect(Buffer.compare(merged, Buffer.from(payload))).toBe(0)
    expect(progress.at(-1)).toBe(100)
    expect(h.requests[0]!.url).toBe('https://agent.mnb-lab.cn/api/v1/drive/files/7/download')
    expect(h.requests[0]!.headers['authorization']).toBe('Bearer AT1')
  })

  it('403 不可见：中性文案（不暴露服务端原文）', async () => {
    const h = downloadHarness([() => ({ status: 403, headers: {}, text: '{"error":{"code":"FORBIDDEN","message":"no permission on file 7"}}' })])
    const r = await h.svc.download(7, { write: async () => undefined })
    expect(r.ok).toBe(false)
    if (!r.ok) {
      const msg = driveErrorMessage(r.error)
      expect(msg).not.toMatch(/FORBIDDEN|no permission|7/)
    }
  })

  it('401 → 续期 → 重放下载（令牌语义与 JSON 请求一致）', async () => {
    const payload = new Uint8Array(10)
    const h = downloadHarness([
      () => ({ status: 401, headers: {}, text: '{}' }),
      () => res(200, { access_token: 'AT2', token_type: 'bearer' }),
      () => binRes(payload)
    ])
    const r = await h.svc.download(3, { write: async () => undefined })
    expect(r.ok).toBe(true)
    expect(h.requests.map((q) => new URL(q.url).pathname)).toEqual([
      '/api/v1/drive/files/3/download',
      '/api/v1/auth/refresh',
      '/api/v1/drive/files/3/download'
    ])
    expect(h.requests[2]!.headers['authorization']).toBe('Bearer AT2')
  })

  it('取消下载：signal 已中止 → 中性取消文案，不继续写盘', async () => {
    const payload = new Uint8Array(2 * 1024 * 1024)
    const h = downloadHarness([() => binRes(payload)])
    const ac = new AbortController()
    ac.abort()
    let wrote = 0
    const r = await h.svc.download(1, {
      write: async () => {
        wrote += 1
      },
      signal: ac.signal
    })
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.error.message).toContain('取消')
    expect(wrote).toBe(0)
  })

  it('空文件：进度直接 100%、字节 0、不写盘', async () => {
    const h = downloadHarness([() => binRes(new Uint8Array(0))])
    let wrote = 0
    const progress: number[] = []
    const r = await h.svc.download(1, {
      write: async () => {
        wrote += 1
      },
      onProgress: (p) => progress.push(p.percent)
    })
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data.bytes).toBe(0)
    expect(wrote).toBe(0)
    expect(progress).toEqual([100])
  })

  it('纯函数：Content-Disposition 解析与分片切分', () => {
    expect(parseContentDisposition({ 'content-disposition': 'attachment; filename="a b.txt"' })).toBe('a b.txt')
    expect(parseContentDisposition({ 'content-disposition': "attachment; filename*=UTF-8''%E5%8D%A0%E4%BD%8D.bin" })).toBe('占位.bin')
    expect(parseContentDisposition({})).toBeNull()
    expect(sliceBytes(new Uint8Array(0))).toEqual([])
    expect(sliceBytes(new Uint8Array(3 * 1024 * 1024)).length).toBe(3)
    expect(sliceBytes(new Uint8Array(1024 * 1024 + 1)).length).toBe(2)
  })
})
