// usePublicChunkedUpload.test.js — 匿名分片上传的单测 (2026-11-09)
//
// 这个模块最容易错的四件事，每条都有对应断言:
//   ① 必须用**服务端**的 chunk_size 切片 (自己算 ⇒ 非末片长度不等 ⇒ 后端 400)
//   ② missing_chunks 服务端只回前 200 个 ⇒ 截断时必须保守补全 (漏传比多传严重)
//   ③ crypto.subtle 不可用要**降级继续传**, 不能让功能整体不可用
//   ④ 断点记录的 key 要能区分"同名不同文件" (本仓踩过 basename 静默复用错数据)
import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  // 纯函数
  shouldUseChunked,
  chunkRange,
  planPending,
  paceWindow,
  MAX_PUTS_PER_MINUTE,
  RATE_WINDOW_MS,
  isRetryableStatus,
  resolveRetryDelayMs,
  canComputeChunkHash,
  bufToHex,
  fileFingerprint,
  storageKey,
  isSessionCompatible,
  makeLocalFailure,
  // 常量
  CHUNKED_THRESHOLD_BYTES,
  MISSING_CHUNKS_CAP,
  STORAGE_PREFIX,
  MAX_CHUNK_CONCURRENCY,
  // composable
  usePublicChunkedUpload,
} from '@/composables/usePublicChunkedUpload'

// ── 用假 api 层替换掉真 axios: 本测试测的是**编排逻辑**, 不是 axios ──
// ⚠️ 必须 vi.hoisted: vi.mock 的工厂会在**顶部 import 求值时**就被调用,
//    那时普通 const 还在 TDZ 里, 直接引用会得到 undefined → 整个文件加载失败。
const api = vi.hoisted(() => ({
  initPublicUpload: vi.fn(),
  getPublicUploadStatus: vi.fn(),
  putPublicChunk: vi.fn(),
  completePublicUpload: vi.fn(),
  abortPublicUpload: vi.fn(),
}))
vi.mock('@/composables/useFileRequests', () => ({
  useFileRequests: () => api,
}))

const TOKEN = 'tokTEST'

function fakeFile(name, bytes, lastModified = 1700000000000) {
  const f = new File([new Uint8Array(bytes)], name, { type: 'application/octet-stream' })
  // jsdom 的 File 没有可写的 lastModified, 直接定义 —— 本模块只读它
  Object.defineProperty(f, 'lastModified', { value: lastModified, configurable: true })
  return f
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  // 默认给出可用的 subtle: 返回 32 字节全零
  Object.defineProperty(globalThis, 'crypto', {
    value: { subtle: { digest: async () => new Uint8Array(32).buffer } },
    configurable: true,
    writable: true,
  })
})

// ── ① 分流阈值 ───────────────────────────────────────────────────────────────

describe('shouldUseChunked', () => {
  it('阈值 = 200 MB', () => {
    expect(CHUNKED_THRESHOLD_BYTES).toBe(200 * 1024 * 1024)
  })
  it('小于阈值走小文件通路, 等于/大于走分片', () => {
    expect(shouldUseChunked(CHUNKED_THRESHOLD_BYTES - 1)).toBe(false)
    expect(shouldUseChunked(CHUNKED_THRESHOLD_BYTES)).toBe(true)
    expect(shouldUseChunked(10 * 1024 * 1024 * 1024)).toBe(true)
  })
  it('非数字/空值 ⇒ false (不许把 undefined 当 0 去分片)', () => {
    expect(shouldUseChunked(undefined)).toBe(false)
    expect(shouldUseChunked(NaN)).toBe(false)
    expect(shouldUseChunked('abc')).toBe(false)
  })
})

// ── ② 切片区间 ───────────────────────────────────────────────────────────────

describe('chunkRange', () => {
  it('末片短, 其余等长', () => {
    // 10 字节 / 片 4 ⇒ [4,4,2]
    expect(chunkRange(10, 4, 0)).toEqual({ start: 0, end: 4, len: 4 })
    expect(chunkRange(10, 4, 2)).toEqual({ start: 8, end: 10, len: 2 })
    const lens = [0, 1, 2].map((i) => chunkRange(10, 4, i).len)
    expect(lens).toEqual([4, 4, 2])
    expect(lens.reduce((a, b) => a + b, 0)).toBe(10)
  })
  it('整除时末片也是满的', () => {
    expect(chunkRange(8, 4, 1).len).toBe(4)
  })
})

// ── ③ missing_chunks 的 200 截断 ─────────────────────────────────────────────

describe('planPending —— 后端 _missing() 只回前 200 个', () => {
  it('未截断: 原样返回缺失下标', () => {
    expect(planPending(10, [2, 5, 9])).toEqual([2, 5, 9])
    expect(planPending(10, [])).toEqual([])
  })
  it('截断 (刚好 200 个): 必须把最大缺失下标之后的全部补上', () => {
    const listed = Array.from({ length: MISSING_CHUNKS_CAP }, (_, i) => i)  // 0..199
    const out = planPending(320, listed)
    // 320 片全都没传 ⇒ 必须排 320 片, 少一片都会在 complete 时 409
    expect(out.length).toBe(320)
    expect(out).toEqual(Array.from({ length: 320 }, (_, i) => i))
  })
  it('截断且中间有已传的: 未列出的**较小**下标可以证明已传, 较大的必须重传', () => {
    // total=250, 前 50 片已传, 缺失升序 = 50..249, 服务端只给 50..249 的前 200 个
    const listed = Array.from({ length: MISSING_CHUNKS_CAP }, (_, i) => i + 50)
    expect(listed[listed.length - 1]).toBe(249)
    const out = planPending(250, listed)
    expect(out).toEqual(listed)          // 249 之后没有片了
    expect(out).not.toContain(0)         // 0..49 未列出 ⇒ 已传, 不许重传
  })
  it('越界/重复/null 的下标一律丢掉 (Number(null)===0 会被当成 0 号片)', () => {
    // total=5 ⇒ 合法下标 0..4; 5 与 99 越界, -1 越界, 'x' 非数, null 必须先挡掉
    expect(planPending(5, [0, 0, 1, 4, 5, 99, -1, 'x', null, undefined, ''])).toEqual([0, 1, 4])
  })
})

// ── ④ 重试与退避 ─────────────────────────────────────────────────────────────

describe('isRetryableStatus', () => {
  it('422/429/5xx/无响应 可重试', () => {
    for (const s of [422, 429, 500, 502, 503, 0]) expect(isRetryableStatus(s)).toBe(true)
  })
  it('链接/会话级错误不可重试 (重传多少片都没用)', () => {
    for (const s of [404, 409, 410, 413, 415]) expect(isRetryableStatus(s)).toBe(false)
  })
})

describe('resolveRetryDelayMs', () => {
  it('优先听 Retry-After (秒)', () => {
    expect(resolveRetryDelayMs({ response: { headers: { 'retry-after': '3' } } }, 1)).toBe(3000)
  })
  it('Retry-After 超上限时夹到 30s, 不许退避到天荒地老', () => {
    expect(resolveRetryDelayMs({ response: { headers: { 'retry-after': '99999' } } }, 1))
      .toBeLessThanOrEqual(30000)
  })
  it('没有 Retry-After 时指数增长', () => {
    const d0 = resolveRetryDelayMs({}, 0)
    const d3 = resolveRetryDelayMs({}, 3)
    expect(d0).toBeGreaterThanOrEqual(200)
    expect(d3).toBeGreaterThan(d0)
    expect(d3).toBeLessThanOrEqual(30000)
  })
  it('退避不许为负数', () => {
    for (let i = 0; i < 20; i++) expect(resolveRetryDelayMs({}, i % 6)).toBeGreaterThan(0)
  })
})

// ── ⑤ hash 可用性判据与降级 ──────────────────────────────────────────────────

describe('canComputeChunkHash', () => {
  const okCrypto = { subtle: { digest: async () => new Uint8Array(32).buffer } }
  it('有 crypto.subtle ⇒ true', () => {
    expect(canComputeChunkHash({ crypto: okCrypto, window: { isSecureContext: true } })).toBe(true)
  })
  it('非 secure context ⇒ false (http:// 内网 IP 就是这个情况)', () => {
    expect(canComputeChunkHash({ crypto: okCrypto, window: { isSecureContext: false } })).toBe(false)
  })
  it('subtle 缺失/非函数 ⇒ false', () => {
    expect(canComputeChunkHash({ crypto: {}, window: {} })).toBe(false)
    expect(canComputeChunkHash({ crypto: { subtle: {} }, window: {} })).toBe(false)
    expect(canComputeChunkHash({}, {})).toBe(false)
  })
  it('getter 抛异常也必须返回 false, 不许把判定本身炸掉', () => {
    const hostile = { get crypto() { throw new Error('boom') }, window: {} }
    expect(canComputeChunkHash(hostile)).toBe(false)
  })
})

it('bufToHex: 输出 64 位小写十六进制 (后端要求, 否则 400)', () => {
  const hex = bufToHex(new Uint8Array(32).fill(10).buffer)
  expect(hex).toMatch(/^[0-9a-f]{64}$/)
})

// ── ⑥ 断点记录: key 与兼容性判定 ─────────────────────────────────────────────

describe('断点记录 (localStorage)', () => {
  it('key 里带 token + 文件名 + 大小, 且有版本前缀', () => {
    const f = fakeFile('lecture.mp4', [1, 2, 3])
    const k = storageKey(TOKEN, f)
    expect(k.startsWith(STORAGE_PREFIX)).toBe(true)
    expect(k).toContain(TOKEN)
    expect(k).toContain(encodeURIComponent('lecture.mp4'))
    expect(k).toContain(':3:')       // 字节数进了 key
  })
  it('同名不同内容 ⇒ 不同 key (本仓踩过 basename 静默复用错数据, 类 20.242)', () => {
    const a = fakeFile('merged.m4a', [1, 1])
    const b = fakeFile('merged.m4a', [1, 1], 1600000000000)      // 同大小, 改 mtime
    const c = fakeFile('merged.m4a', [1, 1, 1])                  // 不同大小
    expect(storageKey(TOKEN, a)).not.toBe(storageKey(TOKEN, b))
    expect(storageKey(TOKEN, a)).not.toBe(storageKey(TOKEN, c))
    // 同名同大小同 mtime 才可能是同一份, 但指纹仍要一致
    expect(fileFingerprint(a)).toBe(fileFingerprint(fakeFile('merged.m4a', [1, 1], a.lastModified)))
  })
  it('不同 token ⇒ 不同 key (两个收件链接不串会话)', () => {
    const f = fakeFile('a.mp4', [1])
    expect(storageKey('t1', f)).not.toBe(storageKey('t2', f))
  })
  it('isSessionCompatible: 文件名/大小/mtime 任一项不符就拒绝续传', () => {
    const f = fakeFile('a.mp4', [1, 2, 3])
    const good = { filename: 'a.mp4', fileSize: 3, lastModified: f.lastModified, chunkSize: 4, totalChunks: 1 }
    expect(isSessionCompatible(good, f)).toBe(true)
    expect(isSessionCompatible({ ...good, filename: 'b.mp4' }, f)).toBe(false)
    expect(isSessionCompatible({ ...good, fileSize: 999 }, f)).toBe(false)
    expect(isSessionCompatible({ ...good, lastModified: 1 }, f)).toBe(false)
    expect(isSessionCompatible({ ...good, chunkSize: 0 }, f)).toBe(false)
    expect(isSessionCompatible(null, f)).toBe(false)
  })
})

/**
 * 建一份 File 并把"上次没传完"的记录按它自己的 key 写进 localStorage。
 * key 一律用被测模块导出的 storageKey 现算 —— **测试里不重写 key 格式**,
 * 否则实现改了 key 规则, 这条测试还是绿的 (类 20.251 ②: 测试把 bug 焊死)。
 */
function withSavedSession(name, bytes, over = {}) {
  const f = fakeFile(name, bytes)
  localStorage.setItem(storageKey(TOKEN, f), JSON.stringify({
    uploadId: 'up9',
    filename: f.name,
    fileSize: f.size,
    lastModified: f.lastModified,
    chunkSize: 4,
    totalChunks: Math.ceil(f.size / 4),
    expiresAt: null,
    ...over,
  }))
  return f
}

// ── ⑦ 起跑限速 (纯函数, 不动定时器) ──────────────────────────────────────────

describe('paceWindow —— 客户端滚动窗口限速', () => {
  it('窗口没满 ⇒ 不等待, 并把本次时刻记进去', () => {
    const r = paceWindow(1000, [], 3)
    expect(r.waitMs).toBe(0)
    expect(r.stamps).toEqual([1000])
  })
  it('窗口满了 ⇒ 等到最老那次出窗为止', () => {
    // 额度 3, 已经发了 t=0/10/20 三次; 在 t=25 再发就要等
    const r = paceWindow(25, [0, 10, 20], 3, RATE_WINDOW_MS)
    expect(r.waitMs).toBe(RATE_WINDOW_MS - 25)
  })
  it('超过窗口的旧时刻自动失效 (滚动, 不是整分钟清零)', () => {
    const old = 0
    const r = paceWindow(RATE_WINDOW_MS + 5, [old], 1)
    expect(r.stamps).not.toContain(old)
    expect(r.waitMs).toBe(0)
  })
  it('等待之后出窗的那些不许继续占额度 (否则越等越久)', () => {
    const r = paceWindow(0, [0, 0, 0], 3, 100)     // 额度 3, 窗口 100ms
    expect(r.waitMs).toBe(100)
    expect(r.stamps.length).toBe(1)                // 三个旧的都已出窗
  })
  it('默认额度必须**低于**后端的 120/min', () => {
    expect(MAX_PUTS_PER_MINUTE).toBeLessThan(120)
    expect(RATE_WINDOW_MS).toBe(60000)
  })
  it('脏输入不炸 (recent 不是数组 / NaN)', () => {
    expect(paceWindow(NaN, undefined).waitMs).toBe(0)
    expect(paceWindow(0, 'nope', 2).stamps.length).toBe(1)
  })
  it('限速真的被引擎用上了, 不是只写了个纯函数没人调', async () => {
    api.initPublicUpload.mockResolvedValue({
      upload_id: 'upP', chunk_size: 5, total_chunks: 6, file_size: 30,
      uploaded_chunks: 0, missing_chunks: [0, 1, 2, 3, 4, 5],
    })
    api.getPublicUploadStatus.mockResolvedValue({
      upload_id: 'upP', chunk_size: 5, total_chunks: 6, file_size: 30,
      uploaded_chunks: 6, missing_chunks: [],
    })
    const at = []
    api.putPublicChunk.mockImplementation(async (_t, _u, index) => {
      at.push(Date.now())
      return { index }
    })
    // 额度 2 / 窗口 120ms ⇒ 6 片不可能在 120ms 内全发完
    const up = usePublicChunkedUpload(TOKEN, { maxPutsPerMinute: 2, rateWindowMs: 120 })
    const res = await up.upload(fakeFile('p.mp4', new Array(30).fill(1)))
    expect(res.ok).toBe(true)
    expect(at.length).toBe(6)
    expect(at[at.length - 1] - at[0]).toBeGreaterThanOrEqual(120)
  })

  it('限速的等待必须能被「暂停」打断 (裸 sleep 会拖到整个窗口结束)', async () => {
    api.initPublicUpload.mockResolvedValue({
      upload_id: 'upQ', chunk_size: 5, total_chunks: 4, file_size: 20,
      uploaded_chunks: 0, missing_chunks: [0, 1, 2, 3],
    })
    api.putPublicChunk.mockImplementation(async (_t, _u, index) => ({ index }))
    const up = usePublicChunkedUpload(TOKEN, { maxPutsPerMinute: 1, rateWindowMs: 30000 })
    const p = up.upload(fakeFile('q.mp4', new Array(20).fill(1)))
    await new Promise((r) => setTimeout(r, 30))
    const t0 = Date.now()
    up.pause()
    await p
    expect(Date.now() - t0).toBeLessThan(1000)      // 远小于 30s 的窗口 ⇒ 等待真的被打断
    expect(up.lastError.value.title).toBe('上传已暂停')
  })
})

// ── ⑦ 编排流程 ───────────────────────────────────────────────────────────────

describe('usePublicChunkedUpload.upload()', () => {
  /** 10 字节 / 服务端定 4 字节一片 = 3 片 */
  const initResp = {
    upload_id: 'up1', chunk_size: 4, total_chunks: 3, file_size: 10,
    uploaded_chunks: 0, missing_chunks: [0, 1, 2], status: 'pending',
    expires_at: null, request_title: 'T',
  }
  const allDone = {
    ...initResp, uploaded_chunks: 3, missing_chunks: [], status: 'uploading',
  }

  beforeEach(() => {
    api.initPublicUpload.mockResolvedValue(initResp)
    api.getPublicUploadStatus.mockResolvedValue(allDone)
    api.putPublicChunk.mockImplementation(async (_t, _u, index) => ({
      index, uploaded_chunks: 3, total_chunks: 3, missing_chunks: [],
    }))
    api.completePublicUpload.mockResolvedValue({
      success: true, file_id: 9, size: 10, sha256: 'ab'.repeat(32), request_closed: false,
    })
  })

  it('用服务端的 chunk_size 切片: 每片长度必须是 4/4/2', async () => {
    const up = usePublicChunkedUpload(TOKEN)
    const res = await up.upload(fakeFile('v.mp4', [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]))
    expect(res.ok).toBe(true)
    const lens = api.putPublicChunk.mock.calls.map((c) => c[3].size)
    expect(lens).toEqual([4, 4, 2])
    // 传给后端的 index 集合必须覆盖 0..2 各一次
    expect(api.putPublicChunk.mock.calls.map((c) => c[2]).sort()).toEqual([0, 1, 2])
  })

  it('init 请求带上了 filename / file_size', async () => {
    const up = usePublicChunkedUpload(TOKEN)
    await up.upload(fakeFile('v.mp4', [1, 2]))
    expect(api.initPublicUpload).toHaveBeenCalledWith(TOKEN, expect.objectContaining({
      filename: 'v.mp4', fileSize: 2,
    }))
  })

  it('每片都带 X-Chunk-SHA256 (secure context 下不许静默省掉)', async () => {
    const up = usePublicChunkedUpload(TOKEN)
    await up.upload(fakeFile('v.mp4', [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]))
    for (const call of api.putPublicChunk.mock.calls) {
      expect(call[4]).toMatch(/^[0-9a-f]{64}$/)
    }
  })

  it('crypto.subtle 不可用 ⇒ 降级为不带校验头, **但上传照常完成**', async () => {
    Object.defineProperty(globalThis, 'crypto', {
      value: {}, configurable: true, writable: true,          // 模拟 http:// 非安全上下文
    })
    Object.defineProperty(globalThis.window, 'isSecureContext', {
      value: false, configurable: true,
    })
    const up = usePublicChunkedUpload(TOKEN)
    const res = await up.upload(fakeFile('v.mp4', [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]))
    expect(up.hashAvailable.value).toBe(false)                 // UI 据此显示"本环境无法逐片校验"
    expect(res.ok).toBe(true)                                  // 关键: 不能因此不可用
    expect(api.putPublicChunk.mock.calls.every((c) => c[4] === null)).toBe(true)
  })

  it('进度: 完成后 100% 且字节数等于文件大小', async () => {
    const up = usePublicChunkedUpload(TOKEN)
    await up.upload(fakeFile('v.mp4', new Array(10).fill(1)))
    expect(up.uploadedBytes.value).toBe(10)
    expect(up.percent.value).toBe(100)
    expect(up.status.value).toBe('done')
  })

  it('并发**从不超过 2** (限流档 120/min/IP, 猛打会把整场打成 429)', async () => {
    // 用一片很小但片数够多的会话, 才看得见并发度: 1000 字节 / 每片 5 = 200 片。
    // ⚠️ 200 片 > 默认的 100/min 会被限流**正确地**卡住 —— 本条测的是并发度不是限流
    //    (限流另有 paceWindow 那组用例), 所以这里豁免额度, 别当成在掩盖 bug。
    api.initPublicUpload.mockResolvedValue({
      upload_id: 'upC', chunk_size: 5, total_chunks: 200, file_size: 1000,
      uploaded_chunks: 0, missing_chunks: Array.from({ length: 200 }, (_, i) => i),
    })
    api.getPublicUploadStatus.mockResolvedValue({
      upload_id: 'upC', chunk_size: 5, total_chunks: 200, file_size: 1000,
      uploaded_chunks: 200, missing_chunks: [],
    })
    let live = 0
    let peak = 0
    api.putPublicChunk.mockImplementation(async (_t, _u, index) => {
      live += 1
      peak = Math.max(peak, live)
      await new Promise((r) => setTimeout(r, 1))
      live -= 1
      return { index }
    })
    const up = usePublicChunkedUpload(TOKEN, { maxPutsPerMinute: 100000 })
    const res = await up.upload(fakeFile('v.mp4', new Array(1000).fill(1)))
    expect(res.ok).toBe(true)
    expect(peak).toBeGreaterThan(1)                    // 确实是并发, 不是退化成串行而空过
    expect(peak).toBeLessThanOrEqual(MAX_CHUNK_CONCURRENCY)
  })

  it('429 会退避重试而不是立刻放弃', async () => {
    const err429 = { response: { status: 429, headers: { 'retry-after': '0' }, data: { detail: '慢一点' } } }
    api.putPublicChunk
      .mockRejectedValueOnce(err429)
      .mockImplementation(async (_t, _u, index) => ({ index }))
    const up = usePublicChunkedUpload(TOKEN)
    const res = await up.upload(fakeFile('v.mp4', new Array(10).fill(1)))
    expect(res.ok).toBe(true)
    expect(api.putPublicChunk.mock.calls.length).toBe(4)      // 3 片 + 1 次重试
  })

  it('410 (链接关闭) 立即停止整场, 不重传其余片', async () => {
    const err410 = { response: { status: 410, headers: {}, data: { detail: '这个收件链接已过期' } } }
    api.putPublicChunk.mockRejectedValue(err410)
    const up = usePublicChunkedUpload(TOKEN)
    const res = await up.upload(fakeFile('v.mp4', new Array(10).fill(1)))
    expect(res.ok).toBe(false)
    expect(res.error.code).toBe('link_closed')
    expect(api.putPublicChunk.mock.calls.length).toBeLessThanOrEqual(MAX_CHUNK_CONCURRENCY)
    expect(api.completePublicUpload).not.toHaveBeenCalled()
  })

  it('服务端说还缺片时不许 complete (对账), 且提示是"还差几片"而不是"网络断了"', async () => {
    api.getPublicUploadStatus
      .mockResolvedValue({ ...initResp, uploaded_chunks: 0, missing_chunks: [0, 1, 2] })
    const up = usePublicChunkedUpload(TOKEN)
    const res = await up.upload(fakeFile('v.mp4', new Array(10).fill(1)))
    expect(api.completePublicUpload).not.toHaveBeenCalled()
    expect(res.ok).toBe(false)
    expect(res.error.title).toMatch(/还差 3 片/)
    expect(res.error.detail).not.toMatch(/网络断/)
  })

  it('成功后清掉断点记录 (否则下次进来还会提示"有未完成的上传")', async () => {
    const f = fakeFile('v.mp4', new Array(10).fill(1))
    const up = usePublicChunkedUpload(TOKEN)
    await up.upload(f)
    expect(localStorage.getItem(storageKey(TOKEN, f))).toBeNull()
  })

  it('request_closed=true 走成功分支, 不许显示成失败', async () => {
    api.completePublicUpload.mockResolvedValue({
      success: true, file_id: 9, size: 10, sha256: 'cd'.repeat(32), request_closed: true,
    })
    const up = usePublicChunkedUpload(TOKEN)
    const res = await up.upload(fakeFile('v.mp4', new Array(10).fill(1)))
    expect(res.ok).toBe(true)
    expect(up.status.value).toBe('done')
    expect(up.lastError.value).toBeFalsy()
  })
})

describe('断点续传 resume()', () => {
  it('只补缺失的片, 已传的片不重传, 也不再 init', async () => {
    const f = withSavedSession('v.mp4', [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    api.getPublicUploadStatus
      .mockResolvedValueOnce({          // 第一次: 还缺第 2 片
        upload_id: 'up9', chunk_size: 4, total_chunks: 3, file_size: 10,
        uploaded_chunks: 2, missing_chunks: [2],
      })
      .mockResolvedValue({               // 补完之后: 齐了
        upload_id: 'up9', chunk_size: 4, total_chunks: 3, file_size: 10,
        uploaded_chunks: 3, missing_chunks: [],
      })
    api.putPublicChunk.mockImplementation(async (_t, _u, index) => ({ index }))
    api.completePublicUpload.mockResolvedValue({ success: true, size: 10, sha256: 'e'.repeat(64) })

    const up = usePublicChunkedUpload(TOKEN)
    expect(up.findResumable(f)).toBeTruthy()
    const res = await up.resume(f)

    expect(res.ok).toBe(true)
    expect(api.initPublicUpload).not.toHaveBeenCalled()
    expect(api.putPublicChunk.mock.calls.map((c) => c[2])).toEqual([2])
    expect(up.uploadId.value).toBe('up9')
    expect(localStorage.getItem(storageKey(TOKEN, f))).toBeNull()   // 成功即清记录
  })

  it('missing 被截断到 200 时要补全 —— 未列出的较大下标无法证明已传, 必须重排', async () => {
    // 250 字节 / 每片 1 字节 = 250 片; 服务端只肯给前 200 个缺失下标 (契约里的 [:200])
    const f = withSavedSession('big.mp4', new Array(250).fill(1), { chunkSize: 1, totalChunks: 250 })
    api.getPublicUploadStatus
      .mockResolvedValueOnce({
        upload_id: 'up9', chunk_size: 1, total_chunks: 250, file_size: 250,
        uploaded_chunks: 50, missing_chunks: Array.from({ length: 200 }, (_, i) => i),
      })
      .mockResolvedValue({
        upload_id: 'up9', chunk_size: 1, total_chunks: 250, file_size: 250,
        uploaded_chunks: 250, missing_chunks: [],
      })
    api.putPublicChunk.mockImplementation(async (_t, _u, index) => ({ index }))
    api.completePublicUpload.mockResolvedValue({ success: true, size: 250, sha256: 'f'.repeat(64) })
    // 250 片 > 100/min, 同上豁免 (本条测的是 missing 截断的补全逻辑)
    const up = usePublicChunkedUpload(TOKEN, { maxPutsPerMinute: 100000 })
    up.findResumable(f)
    const res = await up.resume(f)
    expect(res.ok).toBe(true)
    const sent = api.putPublicChunk.mock.calls.map((c) => c[2])
    expect(sent.length).toBe(250)                     // 200 列出 + 50 个无法证明已传的
    expect(new Set(sent).size).toBe(250)              // 且不许重复排片
  })

  it('服务端记的文件大小与本地这份不符 ⇒ 拒绝续传 (同名不同文件)', async () => {
    const f = withSavedSession('v.mp4', [1, 2, 3])
    api.getPublicUploadStatus.mockResolvedValue({
      upload_id: 'up9', chunk_size: 4, total_chunks: 2500, file_size: 10000000000,
      uploaded_chunks: 2500, missing_chunks: [],
    })
    const up = usePublicChunkedUpload(TOKEN)
    up.findResumable(f)
    const res = await up.resume(f)
    expect(res.ok).toBe(false)
    expect(api.putPublicChunk).not.toHaveBeenCalled()
    expect(api.completePublicUpload).not.toHaveBeenCalled()   // 绝不能把别人的会话合并到自己文件上
    expect(localStorage.getItem(storageKey(TOKEN, f))).toBeNull()
  })

  it('对账之后按暂停, 提示的片数必须含**服务端基线**, 不许只报本轮增量', async () => {
    // 场景: 250 片, 服务端已收 200。续传先对账(基线 200) 再补 50 片,
    // 补到第 4 片时用户按暂停 —— 提示应当写"已停下 2xx/250 片"。
    // 只用 doneSet.size 计数的话, 对账刚把 doneSet 清空, 会报成"3/250",
    // 让对方以为自己快要从头再来 (类 20.220: 数字看着合理但在骗人)。
    const f = withSavedSession('big.mp4', new Array(250).fill(1), {
      chunkSize: 1, totalChunks: 250,
    })
    api.getPublicUploadStatus.mockResolvedValue({
      upload_id: 'up9', chunk_size: 1, total_chunks: 250, file_size: 250,
      uploaded_chunks: 200, missing_chunks: Array.from({ length: 50 }, (_, i) => i + 200),
    })
    const up = usePublicChunkedUpload(TOKEN)
    let n = 0
    api.putPublicChunk.mockImplementation(async (_t, _u, index) => {
      n += 1
      if (n === 4) up.pause()
      return { index }
    })
    up.findResumable(f)
    const res = await up.resume(f)
    expect(res.ok).toBe(false)
    expect(up.lastError.value.title).toBe('上传已暂停')
    expect(up.uploadedCount.value).toBeGreaterThanOrEqual(200)
    expect(up.lastError.value.detail).toMatch(/2\d\d\/250/)   // 基线 200 + 增量, 绝不是 3/250
  })

  it('记录过期 ⇒ findResumable 返回 null 并清理记录', () => {
    const past = new Date(Date.now() - 3600_000).toISOString()
    const f = withSavedSession('v.mp4', [1, 2], { expiresAt: past })
    const up = usePublicChunkedUpload(TOKEN)
    expect(up.findResumable(f)).toBeNull()
    expect(localStorage.getItem(storageKey(TOKEN, f))).toBeNull()
  })

  it('abort() 会通知服务端删临时片并清掉本地记录', async () => {
    const f = withSavedSession('v.mp4', [1, 2, 3, 4])
    api.abortPublicUpload.mockResolvedValue({ success: true })
    const up = usePublicChunkedUpload(TOKEN)
    up.findResumable(f)
    up.uploadId.value = 'up9'
    await up.abort(f)
    expect(api.abortPublicUpload).toHaveBeenCalledWith(TOKEN, 'up9')
    expect(localStorage.getItem(storageKey(TOKEN, f))).toBeNull()
    expect(up.status.value).toBe('aborted')
  })
})

describe('makeLocalFailure', () => {
  it('形状与后端失败对象一致 (UI 只有一条渲染路径)', () => {
    const f = makeLocalFailure('x', '标题', '说明', 'retry', '技术串')
    expect(f).toEqual({ code: 'x', title: '标题', detail: '说明', action: 'retry', technical: '技术串', status: 0 })
  })
})
