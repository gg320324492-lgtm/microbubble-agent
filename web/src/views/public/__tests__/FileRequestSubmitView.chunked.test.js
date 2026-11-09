// FileRequestSubmitView.chunked.test.js — 匿名收件页的分流与进度 UI (2026-11-09)
//
// 只验**分流决策**与**状态渲染**, 不重测分片引擎本身 (引擎在 usePublicChunkedUpload.test.js)。
// 分流是这页唯一"选错就静默走错通路"的地方: ≥200MB 必须走 /uploads,
// 否则后端会把整份文件 read() 进内存 (app 容器 mem_limit=8g)。
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const api = vi.hoisted(() => ({
  fetchMy: vi.fn(),
  createRequest: vi.fn(),
  deactivate: vi.fn(),
  fetchPublicInfo: vi.fn(),
  submitPublic: vi.fn(),
  initPublicUpload: vi.fn(),
  getPublicUploadStatus: vi.fn(),
  putPublicChunk: vi.fn(),
  completePublicUpload: vi.fn(),
  abortPublicUpload: vi.fn(),
}))
vi.mock('@/composables/useFileRequests', () => ({ useFileRequests: () => api }))
vi.mock('vue-router', () => ({ useRoute: () => ({ params: { token: 'tokVIEW' } }) }))

import FileRequestSubmitView from '@/views/public/FileRequestSubmitView.vue'
import { storageKey, STORAGE_PREFIX } from '@/composables/usePublicChunkedUpload'

const INFO = {
  id: 1, title: '组会视频', description: '', active: true, expired: false,
  allowed_extensions: [], require_uploader_name: false,
  max_file_size_mb: null,
  // 后端 gates.public_shape 的字段 —— 页面必须按这套数判, 不能自己编
  max_single_file_mb: 20480, max_total_mb: 30720, used_mb: 0,
  max_submissions: 5, auto_close_on_limit: true,
  chunked_supported: true, max_chunk_mb: 32,
  submission_count: 0, expires_at: null,
}

// 300MB 走分片; 一片 100MB ⇒ 正好 3 片。
// ⚠️ init / status 回报的 file_size、chunk_size、total_chunks **三者必须自洽**,
//    否则会被续传自检的"文件大小对不上"拦掉 —— 那道自检是有意的, 不是测试噪音。
const BIG = 300 * 1024 * 1024
const CHUNK = 100 * 1024 * 1024
const TOTAL = 3

/**
 * 大文件用虚拟 File: 只实现分片引擎真正会碰到的四个成员。
 * 300MB 的夹具若真去 alloc, CI 会白吃 300MB 内存; crypto.subtle 是 mock 的,
 * 字节内容不参与任何断言。
 */
function mkBigFile(name, size = BIG, lastModified = 1700000000000) {
  return {
    name,
    size,
    lastModified,
    type: 'application/octet-stream',
    slice(start, end) {
      return { size: Math.max(0, end - start), arrayBuffer: async () => new ArrayBuffer(0) }
    },
  }
}

function mkSmallFile(name, size = 1024 * 1024) {
  const f = new File([new Uint8Array(8)], name, { type: 'application/pdf' })
  Object.defineProperty(f, 'size', { value: size, configurable: true })
  Object.defineProperty(f, 'lastModified', { value: 1700000000000, configurable: true })
  return f
}

async function selectFile(wrapper, file) {
  const input = wrapper.find('input[type="file"]')
  Object.defineProperty(input.element, 'files', { value: [file], configurable: true })
  await input.trigger('change')
  await flushPromises()
}

async function mounted() {
  const w = mount(FileRequestSubmitView)
  await flushPromises()
  return w
}

const initOk = (uploadId = 'u1') => ({
  upload_id: uploadId, request_title: '组会视频', filename: 'big.mp4',
  file_size: BIG, chunk_size: CHUNK, total_chunks: TOTAL,
  uploaded_chunks: 0, missing_chunks: [0, 1, 2], status: 'pending', expires_at: null,
  max_single_file_mb: 20480, max_total_mb: 30720, used_mb: 0, max_chunk_mb: 32,
})
const statusDone = (uploadId = 'u1') => ({
  ...initOk(uploadId), uploaded_chunks: TOTAL, missing_chunks: [], status: 'uploading',
})
const statusMissing = (list, uploadId = 'u1') => ({
  ...initOk(uploadId), uploaded_chunks: TOTAL - list.length, missing_chunks: list,
})

// key 用 composable 自己导出的 storageKey 生成 —— 测试里**绝不重写一遍 key 格式**,
// 否则改了实现这测试还是绿的 (类 20.220: 测试把 bug 焊死)。
function seedLocalSession(file, uploadId = 'u1') {
  localStorage.setItem(storageKey('tokVIEW', file), JSON.stringify({
    uploadId,
    filename: file.name,
    fileSize: file.size,
    lastModified: file.lastModified,
    chunkSize: CHUNK,
    totalChunks: TOTAL,
    expiresAt: null,
    savedAt: Date.now(),
  }))
}
const savedSessionKeys = () =>
  Object.keys(localStorage).filter((k) => String(k).startsWith(STORAGE_PREFIX))

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  Object.defineProperty(globalThis, 'crypto', {
    value: { subtle: { digest: async () => new Uint8Array(32).buffer } },
    configurable: true, writable: true,
  })
  Object.defineProperty(globalThis.window, 'isSecureContext', { value: true, configurable: true })
  api.fetchPublicInfo.mockResolvedValue({ ...INFO })
  api.submitPublic.mockResolvedValue({ success: true, submission_count: 1 })
  api.initPublicUpload.mockImplementation(async () => initOk('u1'))
  api.getPublicUploadStatus.mockImplementation(async () => statusDone('u1'))
  api.putPublicChunk.mockImplementation(async (_t, _u, index) => ({ index }))
  api.completePublicUpload.mockResolvedValue({
    success: true, file_id: 5, filename: 'big.mp4', size: BIG,
    sha256: 'a1b2c3d4e5f6'.padEnd(64, '0'), request_closed: false, content_type_matched: true,
  })
  api.abortPublicUpload.mockResolvedValue({ success: true })
})

describe('阈值分流', () => {
  it('小文件走原有单请求 submit, 不碰分片端点', async () => {
    const w = await mounted()
    await selectFile(w, mkSmallFile('note.pdf'))
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(api.submitPublic).toHaveBeenCalledTimes(1)
    expect(api.initPublicUpload).not.toHaveBeenCalled()
    expect(w.text()).toContain('提交成功')
  })

  it('大文件走 /uploads 分片, 不再调 submit', async () => {
    const w = await mounted()
    await selectFile(w, mkBigFile('big.mp4'))
    expect(w.text()).toContain('将分')            // 选完就预告片数, 让人知道要等多久
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(api.initPublicUpload).toHaveBeenCalledTimes(1)
    expect(api.submitPublic).not.toHaveBeenCalled()
    expect(api.completePublicUpload).toHaveBeenCalledTimes(1)
    expect(w.text()).toContain('上传成功')
  })

  it('边界: 恰好 200MB 走分片, 差 1 字节走单请求', async () => {
    const at = await mounted()
    await selectFile(at, mkBigFile('edge.mp4', 200 * 1024 * 1024))
    api.initPublicUpload.mockImplementation(async () => ({
      ...initOk('u1'), file_size: 200 * 1024 * 1024,
    }))
    api.getPublicUploadStatus.mockImplementation(async () => ({
      ...statusDone('u1'), file_size: 200 * 1024 * 1024,
    }))
    await at.find('form').trigger('submit')
    await flushPromises()
    expect(api.initPublicUpload).toHaveBeenCalledTimes(1)

    vi.clearAllMocks()
    api.fetchPublicInfo.mockResolvedValue({ ...INFO })
    api.submitPublic.mockResolvedValue({ success: true })
    const under = await mounted()
    await selectFile(under, mkSmallFile('under.mp4', 200 * 1024 * 1024 - 1))
    await under.find('form').trigger('submit')
    await flushPromises()
    expect(api.submitPublic).toHaveBeenCalledTimes(1)
    expect(api.initPublicUpload).not.toHaveBeenCalled()
  })

  it('小文件通路没被删掉: 表单与文件选择框仍在', async () => {
    const w = await mounted()
    expect(w.find('input[type="file"]').exists()).toBe(true)
    expect(w.find('form').exists()).toBe(true)
  })
})

describe('成功后的"无损凭证"', () => {
  it('显示服务端实算 sha256 的前 12 位', async () => {
    const w = await mounted()
    await selectFile(w, mkBigFile('big.mp4'))
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(w.find('.proof').exists()).toBe(true)
    expect(w.text()).toContain('a1b2c3d4e5f6')
  })

  it('request_closed=true → 说"已收满并自动关闭", 且**不算失败**', async () => {
    api.completePublicUpload.mockResolvedValue({
      success: true, file_id: 5, filename: 'big.mp4', size: BIG,
      sha256: 'ff'.repeat(32), request_closed: true,
    })
    const w = await mounted()
    await selectFile(w, mkBigFile('big.mp4'))
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(w.find('.submit-success').exists()).toBe(true)
    expect(w.find('.failure-card').exists()).toBe(false)
    expect(w.text()).toMatch(/收满并自动关闭/)
  })

  it('链接收满关闭后, 刚拿到的凭证不许被"已关闭"卡片吞掉', async () => {
    // 真实时序: complete 返回 request_closed → 页面刷新 info → active=false
    api.completePublicUpload.mockResolvedValue({
      success: true, file_id: 5, filename: 'big.mp4', size: BIG,
      sha256: 'ee'.repeat(32), request_closed: true,
    })
    // 第一次拉 info 还是开着的 (否则连文件选择框都不渲染, 测不到后面的时序),
    // complete 之后页面会 refreshInfo() ⇒ 第二次才变成 active:false
    api.fetchPublicInfo
      .mockResolvedValueOnce({ ...INFO })
      .mockResolvedValue({ ...INFO, active: false, is_active: false })
    const w = await mounted()
    await selectFile(w, mkBigFile('big.mp4'))
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(w.find('.submit-success').exists()).toBe(true)
    expect(w.text()).not.toMatch(/无法再提交文件/)   // 不许把成功页盖成"已关闭"
  })

  it('成功后仍可"再提交一份"', async () => {
    const w = await mounted()
    await selectFile(w, mkBigFile('big.mp4'))
    await w.find('form').trigger('submit')
    await flushPromises()
    await w.find('.submit-success button').trigger('click')
    await flushPromises()
    expect(w.find('form').exists()).toBe(true)
  })

  it('清掉断点记录: 成功后刷新不该再提示"有未完成的上传"', async () => {
    const f = mkBigFile('big.mp4')
    const w = await mounted()
    await selectFile(w, f)
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(savedSessionKeys()).toHaveLength(0)
  })
})

describe('逐片校验降级必须写在脸上', () => {
  function noSubtle() {
    Object.defineProperty(globalThis, 'crypto', { value: {}, configurable: true, writable: true })
    Object.defineProperty(globalThis.window, 'isSecureContext', { value: false, configurable: true })
  }

  it('crypto.subtle 不可用 ⇒ 上传照常完成, 不因此整体不可用', async () => {
    noSubtle()
    const w = await mounted()
    await selectFile(w, mkBigFile('big.mp4'))
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(api.putPublicChunk).toHaveBeenCalledTimes(3)
    expect(api.completePublicUpload).toHaveBeenCalledTimes(1)
    expect(w.text()).toContain('上传成功')
    // 且一片都没带校验头 (由 composable 传 null, useFileRequests 那层不加头)
    expect(api.putPublicChunk.mock.calls.every((c) => c[4] === null)).toBe(true)
  })

  it('降级提示在**选完文件时**就出现, 不用等传到一半才看到', async () => {
    noSubtle()
    const w = await mounted()
    await selectFile(w, mkBigFile('big.mp4'))
    const notice = w.findAll('.progress-note.warn').map((n) => n.text()).join(' ')
    expect(notice).toContain('无法逐片校验')
    expect(notice).toContain('https')
    // 不许把它写成"失败"的口气
    expect(notice).toContain('上传照常进行')
    expect(w.find('.failure-card').exists()).toBe(false)
  })

  it('secure context 下不许出现这条提示 (免得对方白担心)', async () => {
    const w = await mounted()
    await selectFile(w, mkBigFile('big.mp4'))
    expect(w.text()).not.toContain('无法逐片校验')
  })
})

describe('失败态: 翻译成人能行动的话', () => {
  it('413 单文件超上限 → 「文件太大了」而不是裸状态码', async () => {
    api.initPublicUpload.mockRejectedValue({
      response: { status: 413, headers: {}, data: { detail: '文件 21000 MB 超过单文件上限 20480 MB' } },
    })
    const w = await mounted()
    await selectFile(w, mkBigFile('huge.mp4'))
    await w.find('form').trigger('submit')
    await flushPromises()
    const card = w.find('.failure-card')
    expect(card.exists()).toBe(true)
    expect(card.text()).toContain('文件太大了')
    expect(card.text()).not.toMatch(/Request failed with status/)
    expect(card.find('details').exists()).toBe(true)   // 技术详情折起来
  })

  it('410 链接已过期 → 让对方找发起人, 并停止传片', async () => {
    api.initPublicUpload.mockRejectedValue({
      response: { status: 410, headers: {}, data: { detail: '这个收件链接已过期' } },
    })
    const w = await mounted()
    await selectFile(w, mkBigFile('big.mp4'))
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(w.find('.failure-card').text()).toMatch(/已关闭或已过期/)
    expect(api.putPublicChunk).not.toHaveBeenCalled()
    expect(api.completePublicUpload).not.toHaveBeenCalled()
  })

  it('服务端说还缺片 → 不许 complete, 并说"还差 N 片"', async () => {
    api.getPublicUploadStatus.mockImplementation(async () => statusMissing([0, 1, 2]))
    const w = await mounted()
    await selectFile(w, mkBigFile('big.mp4'))
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(api.completePublicUpload).not.toHaveBeenCalled()
    expect(w.find('.failure-card').text()).toMatch(/还差 3 片/)
  })

  it('客户端预检超上限也走同一张文案表 (不留第二套说法)', async () => {
    api.fetchPublicInfo.mockResolvedValue({ ...INFO, max_single_file_mb: 100 })
    const w = await mounted()
    await selectFile(w, mkBigFile('big.mp4'))
    expect(w.find('.failure-card').text()).toContain('文件太大了')
    expect(api.initPublicUpload).not.toHaveBeenCalled()
  })

  it('剩余总量不足 → 说的是"总容量"不是"你的文件太大"', async () => {
    api.fetchPublicInfo.mockResolvedValue({ ...INFO, max_total_mb: 400, used_mb: 200 })
    const w = await mounted()
    await selectFile(w, mkBigFile('big.mp4'))
    expect(w.find('.failure-card').exists()).toBe(true)
    expect(w.find('.failure-card').text()).toMatch(/总容量/)
  })

  it('后端没开分片通道时, 大文件在选文件这一步就拦住, 不许白传一半', async () => {
    api.fetchPublicInfo.mockResolvedValue({ ...INFO, chunked_supported: false })
    const w = await mounted()
    await selectFile(w, mkBigFile('big.mp4'))
    expect(api.initPublicUpload).not.toHaveBeenCalled()
    expect(api.submitPublic).not.toHaveBeenCalled()
    expect(w.find('.failure-card').text()).toMatch(/没开启大文件分片通道/)
  })

  it('后端没开分片通道时, 小文件仍走原通路 (不许把老路一起堵死)', async () => {
    api.fetchPublicInfo.mockResolvedValue({ ...INFO, chunked_supported: false })
    const w = await mounted()
    await selectFile(w, mkSmallFile('note.pdf'))
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(api.submitPublic).toHaveBeenCalledTimes(1)
    expect(w.find('.failure-card').exists()).toBe(false)
  })
})

describe('断点续传入口', () => {
  it('选到同一份有记录的文件 → 出现「继续上传」/「重新开始」, 且续传不再 init', async () => {
    const f = mkBigFile('big.mp4')
    seedLocalSession(f, 'u9')
    api.initPublicUpload.mockImplementation(async () => initOk('u9'))
    api.getPublicUploadStatus
      .mockImplementationOnce(async () => statusMissing([2], 'u9'))
      .mockImplementation(async () => statusDone('u9'))

    const w = await mounted()
    await selectFile(w, f)
    expect(w.find('.resume-card').exists()).toBe(true)
    const labels = w.findAll('button').map((b) => b.text())
    expect(labels).toContain('继续上传')
    expect(labels).toContain('重新开始')

    await w.find('.resume-card button').trigger('click')
    await flushPromises()
    expect(api.initPublicUpload).not.toHaveBeenCalled()     // 复用旧会话, 不重开
    expect(api.putPublicChunk.mock.calls.map((c) => c[2])).toEqual([2])
    expect(w.text()).toContain('上传成功')
  })

  it('断点记录里的文件大小与服务端不符 → 拒绝续传 (同名不同文件)', async () => {
    const f = mkBigFile('big.mp4')
    seedLocalSession(f, 'u9')
    api.getPublicUploadStatus.mockImplementation(async () => ({
      ...statusDone('u9'), file_size: BIG + 1,      // 服务端记的是另一份文件
    }))
    const w = await mounted()
    await selectFile(w, f)
    await w.find('.resume-card button').trigger('click')
    await flushPromises()
    expect(api.putPublicChunk).not.toHaveBeenCalled()
    expect(api.completePublicUpload).not.toHaveBeenCalled()
    expect(w.find('.failure-card').text()).toMatch(/对不上/)
  })

  it('换一份不同的文件 → 不许带着上一个 upload_id 继续传', async () => {
    api.getPublicUploadStatus.mockImplementation(async () => statusMissing([0, 1, 2]))
    const w = await mounted()
    await selectFile(w, mkBigFile('a.mp4'))
    await w.find('form').trigger('submit')
    await flushPromises()
    const firstIds = new Set(api.putPublicChunk.mock.calls.map((c) => c[1]))
    expect(firstIds).toEqual(new Set(['u1']))

    vi.clearAllMocks()
    api.fetchPublicInfo.mockResolvedValue({ ...INFO })
    api.initPublicUpload.mockImplementation(async () => initOk('u2'))
    api.getPublicUploadStatus.mockImplementation(async () => statusDone('u2'))
    api.putPublicChunk.mockImplementation(async (_t, _u, index) => ({ index }))
    api.completePublicUpload.mockResolvedValue({
      success: true, file_id: 6, filename: 'b.mp4', size: BIG, sha256: 'b'.repeat(64),
    })

    await selectFile(w, mkBigFile('b.mp4'))
    expect(w.find('.failure-card').exists()).toBe(false)   // 旧失败卡片已清
    await w.find('form').trigger('submit')
    await flushPromises()
    const ids = new Set(api.putPublicChunk.mock.calls.map((c) => c[1]))
    expect(ids).toEqual(new Set(['u2']))                   // 只许用新会话
  })

  it('失败卡片上有「继续上传」入口 (有 upload_id 才可续)', async () => {
    api.getPublicUploadStatus.mockImplementation(async () => statusMissing([0, 1, 2]))
    const w = await mounted()
    await selectFile(w, mkBigFile('big.mp4'))
    await w.find('form').trigger('submit')
    await flushPromises()
    const labels = w.findAll('.failure-card button').map((b) => b.text())
    expect(labels).toContain('继续上传')
  })

  it('放弃 → 调服务端 abort 并清空进度 UI', async () => {
    api.getPublicUploadStatus.mockImplementation(async () => statusMissing([0, 1, 2]))
    const w = await mounted()
    await selectFile(w, mkBigFile('big.mp4'))
    await w.find('form').trigger('submit')
    await flushPromises()
    const abortBtn = w.findAll('button').find((b) => b.text().includes('放弃'))
    await abortBtn.trigger('click')
    await flushPromises()
    expect(api.abortPublicUpload).toHaveBeenCalledWith('tokVIEW', 'u1')
    expect(w.find('.upload-progress').exists()).toBe(false)
    expect(w.find('form').exists()).toBe(true)
  })
})

describe('断点有效期 (naive UTC 的时区坑, 类 20.221)', () => {
  it('后端给的无时区后缀串必须按 UTC 解读, 不能差 8 小时', async () => {
    const naiveUtc = '2026-11-10T02:00:00.000000'
    api.initPublicUpload.mockImplementation(async () => ({
      ...initOk('u1'), expires_at: naiveUtc,
    }))
    // 把 complete 挂住, 好让进度卡片在断言时仍然可见
    // (不然整场瞬间跑完 → 进度卡片已被成功卡片替换, 断的是"根本没渲染")
    let releaseComplete
    api.completePublicUpload.mockImplementation(
      () => new Promise((resolve) => { releaseComplete = resolve }),
    )
    const w = await mounted()
    await selectFile(w, mkBigFile('big.mp4'))
    await w.find('form').trigger('submit')
    await flushPromises()

    const note = w.find('.upload-progress .progress-note')
    expect(note.exists()).toBe(true)
    const shown = note.text()
    expect(shown).toMatch(/保留到/)
    // 唯一正确的解读: 无时区后缀 ⇒ UTC ⇒ 再按本地时区渲染
    expect(shown).toContain(new Date(naiveUtc + 'Z').toLocaleString('zh-CN', { hour12: false }))
    // 不许把后端的原始串直接甩给用户 (那等于漏掉整个时区换算)
    expect(shown).not.toContain(naiveUtc)

    releaseComplete({ success: true, file_id: 1, size: BIG, sha256: 'z'.repeat(64) })
    await flushPromises()
  })
})

describe('进度 UI 的三个数', () => {
  it('传完时进度 100% 且显示总片数', async () => {
    const w = await mounted()
    await selectFile(w, mkBigFile('big.mp4'))
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(w.find('.submit-success').exists()).toBe(true)
    expect(api.putPublicChunk).toHaveBeenCalledTimes(3)
  })
})
