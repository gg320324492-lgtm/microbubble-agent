// FileRequestFilesView.test.js — 文件请求详情: 已收文件 + 上传中进度 (2026-11-10)
//
// 判据:
//   ① 已收文件按接口返回渲染 (文件名/大小/上传者), 不另造一套列表 (复用 DriveFileTable)
//   ② 进行中会话显示**百分比与片数**; 轮询只在有会话时开, 会话清空即停
//   ③ 接口失败如实显示错误, 不伪装成"没有文件" (类 20.220)
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const httpGet = vi.hoisted(() => vi.fn())
vi.mock('axios', () => ({ default: { get: httpGet } }))

import FileRequestFilesView from '@/components/drive/FileRequestFilesView.vue'

const stubs = {
  DriveFileTable: {
    props: ['files', 'folders', 'total', 'loading'],
    template: `<div class="dft-stub" :data-loading="loading ? '1' : '0'">
      <span v-for="f in files" :key="f.id" class="dft-file">{{ f.file_name }}|{{ f.owner_name }}</span>
    </div>`,
  },
  FilePreviewDialog: { template: '<div />', props: ['modelValue', 'file'] },
  'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
}

const FILES = [
  { id: 1, file_name: 'a.mp4', file_size: 1024, owner_name: '张三', created_at: '2026-11-10T00:00:00' },
  { id: 2, file_name: 'b.pdf', file_size: 2048, owner_name: '李四', created_at: '2026-11-10T00:01:00' },
]
const UPLOADING = [{
  upload_id: 'u1', filename: 'huge.mov', file_size: 64 * 1024 * 1024,
  uploader_name: '王五', uploaded_chunks: 1, total_chunks: 4, percent: 25,
  status: 'uploading',
}]

function mountView(request = { id: 33, title: '111' }) {
  return mount(FileRequestFilesView, {
    props: { request },
    global: { stubs },
  })
}

beforeEach(() => {
  vi.useFakeTimers()
  httpGet.mockReset()
})
afterEach(() => {
  vi.useRealTimers()
})

describe('已收文件', () => {
  it('渲染文件列表并在标题处给出数量', async () => {
    httpGet.mockResolvedValue({ data: { files: FILES, uploading: [] } })
    const w = mountView()
    await flushPromises()
    expect(w.text()).toContain('已收到 2 个文件')
    expect(w.findAll('.dft-file').map(n => n.text())).toEqual(['a.mp4|张三', 'b.pdf|李四'])
    expect(httpGet).toHaveBeenCalledWith('/api/v1/file-requests/33/files')
  })

  it('接口失败时显示错误而不是"还没有收到文件"', async () => {
    httpGet.mockRejectedValue({ response: { status: 404, data: { detail: '文件请求不存在' } } })
    const w = mountView()
    await flushPromises()
    expect(w.text()).toContain('文件请求不存在')
    expect(w.text()).not.toContain('还没有收到文件')
  })
})

describe('正在上传的进度', () => {
  it('显示百分比 / 片数 / 上传者', async () => {
    httpGet.mockResolvedValue({ data: { files: FILES, uploading: UPLOADING } })
    const w = mountView()
    await flushPromises()
    expect(w.text()).toContain('正在上传（1）')
    expect(w.text()).toContain('huge.mov')
    expect(w.text()).toContain('25%')
    expect(w.text()).toContain('1 / 4 片')
    expect(w.text()).toContain('王五')
    // 进度条宽度跟着 percent 走
    expect(w.find('.frf-up-fill').attributes('style')).toContain('width: 25%')
  })

  it('有进行中会话 ⇒ 每 3s 轮询; 会话清空后停止', async () => {
    httpGet
      .mockResolvedValueOnce({ data: { files: FILES, uploading: UPLOADING } })
      .mockResolvedValue({ data: { files: FILES, uploading: [] } })
    const w = mountView()
    await flushPromises()
    expect(httpGet).toHaveBeenCalledTimes(1)
    expect(w.find('.dft-stub').attributes('data-loading')).toBe('0')

    await vi.advanceTimersByTimeAsync(3000)
    await flushPromises()
    expect(httpGet).toHaveBeenCalledTimes(2)
    // ⚠️ 主指挥 2026-11-10 反馈「一会儿一没」: 轮询必须是静默的 ——
    //    每次轮询把 loading 置 true 会让表格每 3s 闪一次骨架屏。
    expect(w.find('.dft-stub').attributes('data-loading')).toBe('0')
    expect(w.text()).not.toContain('正在上传')

    // 已无进行中会话 ⇒ 不再轮询
    await vi.advanceTimersByTimeAsync(9000)
    await flushPromises()
    expect(httpGet).toHaveBeenCalledTimes(2)
  })

  it('没有进行中会话时不轮询', async () => {
    httpGet.mockResolvedValue({ data: { files: FILES, uploading: [] } })
    mountView()
    await flushPromises()
    await vi.advanceTimersByTimeAsync(6000)
    expect(httpGet).toHaveBeenCalledTimes(1)
  })

  it('「返回」按钮向父层抛事件', async () => {
    httpGet.mockResolvedValue({ data: { files: [], uploading: [] } })
    const w = mountView()
    await flushPromises()
    const back = w.findAll('button').find(b => b.text().includes('返回'))
    await back.trigger('click')
    expect(w.emitted('back')).toBeTruthy()
  })
})
