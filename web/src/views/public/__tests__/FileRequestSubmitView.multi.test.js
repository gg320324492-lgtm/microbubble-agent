// FileRequestSubmitView.multi.test.js — 多件上传 + 默认不限格式 (2026-11-10)
//
// 与 chunked.test.js 分工: 那份只验单件的分流/进度/失败, 本份只验**队列**。
// 关键不变量:
//   ① 单件行为不能因引入队列而变 (既有 41 例在 chunked.test.js 里守)
//   ② 默认不渲染 accept 属性 (浏览器对 `*/*` 的过滤口径不一致)
//   ③ 队列串行 —— 同一时刻只有一个 init, 一件失败不阻断后续
//   ④ 失败/跳过如实计数, 不许把未传的件报成成功 (类 20.220)
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const api = vi.hoisted(() => ({
  fetchMy: vi.fn(), createRequest: vi.fn(), deactivate: vi.fn(),
  fetchPublicInfo: vi.fn(), submitPublic: vi.fn(),
  initPublicUpload: vi.fn(), getPublicUploadStatus: vi.fn(),
  putPublicChunk: vi.fn(), completePublicUpload: vi.fn(), abortPublicUpload: vi.fn(),
}))
vi.mock('@/composables/useFileRequests', () => ({ useFileRequests: () => api }))
vi.mock('vue-router', () => ({ useRoute: () => ({ params: { token: 'tokMULTI' } }) }))

import FileRequestSubmitView from '@/views/public/FileRequestSubmitView.vue'

const INFO = {
  id: 1, title: '收件', description: '', active: true, expired: false,
  allowed_extensions: [], require_uploader_name: false,
  max_file_size_mb: null, max_single_file_mb: 20480,
  max_total_mb: 30720, used_mb: 0, max_submissions: 10,
  auto_close_on_limit: true, chunked_supported: true, max_chunk_mb: 32,
  submission_count: 0, expires_at: null,
}

function mkSmall(name, size = 1024) {
  const f = new File([new Uint8Array(8)], name, { type: 'application/octet-stream' })
  Object.defineProperty(f, 'size', { value: size, configurable: true })
  Object.defineProperty(f, 'lastModified', { value: 1700000000000, configurable: true })
  return f
}

async function selectFiles(wrapper, files) {
  const input = wrapper.find('input[type="file"]')
  Object.defineProperty(input.element, 'files', { value: files, configurable: true })
  await input.trigger('change')
  await flushPromises()
}

async function mounted(info = INFO) {
  const w = mount(FileRequestSubmitView)
  await flushPromises()
  return w
}

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
  api.abortPublicUpload.mockResolvedValue({ success: true })
})

describe('默认不限格式', () => {
  it('allowed_extensions 为空 ⇒ input 上没有 accept 属性 (不是 */*)', async () => {
    const w = await mounted()
    const attrs = w.find('input[type="file"]').attributes()
    expect(attrs.accept).toBeUndefined()
    expect(attrs.multiple).toBeDefined()
  })

  it('发起人显式选了格式 ⇒ accept 只列那几种', async () => {
    api.fetchPublicInfo.mockResolvedValue({ ...INFO, allowed_extensions: ['mp4', 'mov'] })
    const w = await mounted()
    expect(w.find('input[type="file"]').attributes('accept')).toBe('.mp4,.mov')
  })

  it('任意奇怪格式都能进队列 (没有扩展名 / 生僻后缀 / 无 MIME)', async () => {
    const w = await mounted()
    await selectFiles(w, [mkSmall('noext'), mkSmall('data.foobar123'), mkSmall('archive.tar.gz')])
    expect(w.findAll('.file-queue li')).toHaveLength(3)
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(api.submitPublic).toHaveBeenCalledTimes(3)
  })
})

describe('多件队列', () => {
  it('选 3 件 → 按钮写明件数, 串行提交 3 次并显示汇总', async () => {
    const w = await mounted()
    await selectFiles(w, [mkSmall('a.bin'), mkSmall('b.bin'), mkSmall('c.bin')])
    expect(w.find('button[type="submit"]').text()).toContain('3 个文件')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(api.submitPublic).toHaveBeenCalledTimes(3)
    expect(w.text()).toContain('成功 3 件')
    expect(w.findAll('.batch-summary .batch-done')).toHaveLength(3)
  })

  it('中间一件失败不阻断后续, 汇总如实报 2 成功 1 失败', async () => {
    api.submitPublic
      .mockResolvedValueOnce({ success: true })
      .mockRejectedValueOnce({ response: { status: 413, data: { detail: '文件太大' } } })
      .mockResolvedValueOnce({ success: true })
    const w = await mounted()
    await selectFiles(w, [mkSmall('a.bin'), mkSmall('b.bin'), mkSmall('c.bin')])
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(api.submitPublic).toHaveBeenCalledTimes(3)
    expect(w.text()).toContain('成功 2 件')
    expect(w.text()).toContain('失败 1 件')
    expect(w.findAll('.batch-summary .batch-failed')).toHaveLength(1)
  })

  it('批量跑到一半链接收满 ⇒ 剩余件如实标「未传」, 不伪装成成功', async () => {
    let n = 0
    api.fetchPublicInfo.mockImplementation(async () => {
      n += 1
      // 第 1 次是 onMounted, 第 2 次是队列第 1 件开始前, 之后一律关闭
      return n <= 2 ? { ...INFO } : { ...INFO, active: false, submission_count: 10 }
    })
    const w = await mounted()
    await selectFiles(w, [mkSmall('a.bin'), mkSmall('b.bin'), mkSmall('c.bin')])
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(api.submitPublic).toHaveBeenCalledTimes(1)
    expect(w.text()).toContain('未传 2 件')
    expect(w.findAll('.batch-summary .batch-skipped')).toHaveLength(2)
  })

  it('配置白名单时, 队列里任何一个文件不合格就整批拦下 (文案带文件名)', async () => {
    api.fetchPublicInfo.mockResolvedValue({ ...INFO, allowed_extensions: ['pdf'] })
    const w = await mounted()
    await selectFiles(w, [mkSmall('a.pdf'), mkSmall('b.exe')])
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(api.submitPublic).not.toHaveBeenCalled()
    expect(w.find('.failure-card').text()).toContain('b.exe')
  })

  it('「再传一批」清空队列, 回到可选文件状态', async () => {
    const w = await mounted()
    await selectFiles(w, [mkSmall('a.bin'), mkSmall('b.bin')])
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(w.text()).toContain('成功 2 件')
    await w.find('.submit-success .submit-btn').trigger('click')
    await flushPromises()
    expect(w.findAll('.file-queue li')).toHaveLength(0)
    expect(w.find('input[type="file"]').exists()).toBe(true)
  })
})
