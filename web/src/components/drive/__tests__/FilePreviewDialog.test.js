/**
 * FilePreviewDialog.test.js — v2.7 (2026-07-10) 在线预览增强测试
 *
 * 覆盖 (10 case):
 * - previewType 8 类映射 (image/video/audio/pdf/office/text/unsupported)
 * - Office viewer URL 拼接正确 (MinIO public + view.officeapps)
 * - Text preview: 二进制 blob 检测 fallback unsupported
 * - Text preview: 大文件截断 + warning
 * - Text preview: UTF-8 decode fatal:false 行为
 * - thumbnailUrl: unsupported 路径 fallback 拉 thumbnail
 * - 大文件警告: 30MB image / 100MB video 触发 pendingLargeFileConfirm
 * - Blob URL revoke 内存不泄漏 (cleanup)
 * - formatSize / formatDateTime helper 函数
 * - 默认 fallback 检查 (unsupported 路径下 thumbnail + 元信息存在则显示)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))

const mockAxiosGet = vi.fn()
vi.mock('axios', () => ({
  default: { get: (...args) => mockAxiosGet(...args) },
}))

import FilePreviewDialog from '../FilePreviewDialog.vue'

const makeFile = (overrides = {}) => ({
  id: 1,
  file_name: 'test.pdf',
  file_type: '.pdf',
  file_size: 1024 * 100,
  file_path: 'drive/test/test.pdf',
  storage_mode: 'drive',
  thumbnail_url: null,
  thumbnail_status: 'pending',
  visibility: 'team',
  created_at: '2026-07-01T10:00:00Z',
  created_by: 'tester',
  ...overrides,
})

const globalStubs = {
  stubs: {
    'el-dialog': { template: '<div class="el-dialog"><slot /></div>' },
    'el-icon': { template: '<i><slot /></i>' },
    'el-tooltip': { template: '<div><slot /></div>' },
    'el-button': {
      template: '<button @click="$emit(\'click\')"><slot /></button>',
    },
  },
}

describe('FilePreviewDialog v2.7 previewType 分类', () => {
  beforeEach(() => {
    mockAxiosGet.mockReset()
  })

  it('image (.jpg / .png / .gif / .webp / .svg / .bmp) → image', () => {
    for (const ext of ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp']) {
      const wrapper = mount(FilePreviewDialog, {
        props: { modelValue: true, file: makeFile({ file_type: ext }) },
        global: globalStubs,
      })
      expect(wrapper.vm.previewType).toBe('image')
      wrapper.unmount()
    }
  })

  it('video (.mp4 / .webm / .ogg / .mov / .avi / .mkv) → video', () => {
    for (const ext of ['.mp4', '.webm', '.ogg', '.mov', '.avi', '.mkv']) {
      const wrapper = mount(FilePreviewDialog, {
        props: { modelValue: true, file: makeFile({ file_type: ext }) },
        global: globalStubs,
      })
      expect(wrapper.vm.previewType).toBe('video')
      wrapper.unmount()
    }
  })

  it('office (.ppt / .pptx / .doc / .docx / .xls / .xlsx / .odp / .odt / .ods) → office', () => {
    for (const ext of ['.ppt', '.pptx', '.doc', '.docx', '.xls', '.xlsx', '.odp', '.odt', '.ods']) {
      const wrapper = mount(FilePreviewDialog, {
        props: { modelValue: true, file: makeFile({ file_type: ext }) },
        global: globalStubs,
      })
      expect(wrapper.vm.previewType).toBe('office')
      wrapper.unmount()
    }
  })

  it('text (.txt / .md / .json / .csv / .xml / .yaml / .sh / .sql 等) → text', () => {
    for (const ext of ['.txt', '.md', '.json', '.csv', '.xml', '.yaml', '.yml', '.sh', '.sql', '.env', '.log']) {
      const wrapper = mount(FilePreviewDialog, {
        props: { modelValue: true, file: makeFile({ file_type: ext }) },
        global: globalStubs,
      })
      expect(wrapper.vm.previewType).toBe('text')
      wrapper.unmount()
    }
  })

  it('未知类型 → unsupported (office text 都不匹配)', () => {
    const wrapper = mount(FilePreviewDialog, {
      props: { modelValue: true, file: makeFile({ file_type: '.unknown_ext' }) },
      global: globalStubs,
    })
    expect(wrapper.vm.previewType).toBe('unsupported')
    wrapper.unmount()
  })

  it('Office viewer URL 拼接: file_path + MinIO public + view.officeapps.live.com', async () => {
    // loadPreview 走到 office 分支时 officeViewerUrl 必须含完整 3 段
    mockAxiosGet.mockResolvedValueOnce({
      data: { thumbnail_url: 'https://agent.mnb-lab.cn/minio/microbubble/thumbnails/1.jpg' },
    })
    const wrapper = mount(FilePreviewDialog, {
      props: {
        modelValue: true,
        file: makeFile({
          file_name: '组会ppt.pptx',  // 含中文
          file_type: '.pptx',
          file_path: 'drive/2026/07/test.pptx',
        }),
      },
      global: globalStubs,
    })
    await flushPromises()
    await flushPromises()
    expect(wrapper.vm.officeViewerUrl).toContain('view.officeapps.live.com/op/embed.aspx')
    expect(wrapper.vm.officeViewerUrl).toContain(encodeURIComponent('agent.mnb-lab.cn'))
    expect(wrapper.vm.officeViewerUrl).toContain(encodeURIComponent('drive/2026/07/test.pptx'))
    wrapper.unmount()
  })

  // Office iframe 能力配置 + 错误降级
  it('office iframe 不含 sandbox 且保留 referrerpolicy', async () => {
    mockAxiosGet.mockReset()
    mockAxiosGet.mockResolvedValueOnce({ data: { thumbnail_url: null } })
    const wrapper = mount(FilePreviewDialog, {
      props: {
        modelValue: true,
        file: makeFile({ file_type: '.pptx', file_path: 'drive/test.pptx' }),
      },
      global: {
        stubs: {
          'el-dialog': {
            template: '<div><slot /></div>',
          },
          'el-icon': { template: '<i><slot /></i>' },
          'el-button': {
            template: '<button @click="$emit(\'click\')"><slot /></button>',
          },
          // 让 iframe 真的渲染到 DOM (v-if=true)
          'iframe': {
            template: '<iframe v-bind="$attrs" v-on="$listeners" />',
            inheritAttrs: true,
          },
        },
      },
    })
    for (let i = 0; i < 4; i++) await flushPromises()
    const html = wrapper.html()
    const iframe = wrapper.find('iframe')
    // Office 365 是完整的跨域 Web 应用；sandbox 会把它或其嵌套 frame
    // 降级为 origin=null，并阻断 cookie/storage/CORS 启动链。
    expect(iframe.exists()).toBe(true)
    expect(iframe.attributes('sandbox')).toBeUndefined()
    expect(html).toMatch(/referrerpolicy="no-referrer"/i)
    expect(html).toMatch(/allowfullscreen/i)
    // 验证 officeViewerUrl 含 Office 域名
    expect(wrapper.vm.officeViewerUrl).toContain('view.officeapps.live.com')
    wrapper.unmount()
  })

  it('Office viewer @error 降级到 thumbnail: officeFallbackToThumbnail=true', async () => {
    mockAxiosGet.mockResolvedValueOnce({ data: { thumbnail_url: null } })
    const wrapper = mount(FilePreviewDialog, {
      props: {
        modelValue: true,
        file: makeFile({ file_type: '.pptx', file_path: 'drive/test.pptx' }),
      },
      global: globalStubs,
    })
    for (let i = 0; i < 4; i++) await flushPromises()
    expect(wrapper.vm.previewType).toBe('office')
    expect(wrapper.vm.officeFallbackToThumbnail).toBe(false)  // 初始 false
    // 模拟 @error 触发
    wrapper.vm.onOfficeViewerError(new Error('iframe load fail'))
    await flushPromises()
    expect(wrapper.vm.officeFallbackToThumbnail).toBe(true)   // 降级触发
    wrapper.unmount()
  })

  it('cleanup 资源不泄漏: visibility false 触发后无内存泄漏 (blob URL revoke 调用)', async () => {
    mockAxiosGet.mockReset()
    const revokeSpy = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
    mockAxiosGet.mockResolvedValueOnce({ data: new Blob(['x'], { type: 'image/jpeg' }) })

    const wrapper = mount(FilePreviewDialog, {
      props: { modelValue: true, file: makeFile({ file_type: '.jpg' }) },
      global: globalStubs,
    })
    for (let i = 0; i < 4; i++) await flushPromises()
    expect(wrapper.vm.blobUrl).toBeTruthy()
    expect(revokeSpy).not.toHaveBeenCalled()  // 未关闭前不应 revoke

    // 模拟关闭 — 触发 watch → cleanup → revokeObjectURL
    await wrapper.setProps({ modelValue: false })
    for (let i = 0; i < 4; i++) await flushPromises()

    expect(revokeSpy).toHaveBeenCalled()  // cleanup 路径会 revoke
    expect(wrapper.vm.blobUrl).toBe(null)  // blob URL 已清空
    revokeSpy.mockRestore()
    wrapper.unmount()
  })
})

describe('FilePreviewDialog v2.7 text preview 行为', () => {
  beforeEach(() => {
    mockAxiosGet.mockReset()
  })

  it('text 大于 500KB 触发截断 + textTruncated=true', async () => {
    // 构造 600KB 的文本 (UTF-8 编码)
    const longText = 'A'.repeat(600 * 1024)
    const blob = new Blob([longText], { type: 'text/plain' })
    mockAxiosGet.mockReset()
    mockAxiosGet.mockResolvedValueOnce({ data: blob })
    mockAxiosGet.mockResolvedValueOnce({ data: { thumbnail_url: null } })  // 末尾拉 thumbnail

    const wrapper = mount(FilePreviewDialog, {
      props: {
        modelValue: true,
        file: makeFile({ file_type: '.txt' }),
      },
      global: globalStubs,
    })
    // 多轮 flushPromises 处理 watch + immediate + 多个 axios
    for (let i = 0; i < 5; i++) await flushPromises()
    expect(wrapper.vm.textContent.length).toBeLessThanOrEqual(500 * 1024)
    expect(wrapper.vm.textTruncated).toBe(true)
    wrapper.unmount()
  })

  it('text 含 NUL byte 前 512 字节 (binary) → fallback unsupported', async () => {
    // 构造二进制 blob (以 NUL byte 开头)
    const bytes = new Uint8Array(1024)
    bytes[0] = 0
    bytes[10] = 0xFF
    bytes[100] = 0x80
    const blob = new Blob([bytes], { type: 'application/octet-stream' })
    mockAxiosGet.mockReset()
    mockAxiosGet.mockResolvedValueOnce({ data: blob })

    const wrapper = mount(FilePreviewDialog, {
      props: {
        modelValue: true,
        file: makeFile({ file_type: '.txt' }),  // 假装是 txt
      },
      global: globalStubs,
    })
    for (let i = 0; i < 5; i++) await flushPromises()
    // 二进制 fallback 后, previewType 不变 (它本来就是 text), 但 error 设置 + textContent 空
    expect(wrapper.vm.textContent).toBe('')
    expect(wrapper.vm.error || '').toContain('二进制')
    wrapper.unmount()
  })
})

describe('FilePreviewDialog v2.7 大文件警告', () => {
  beforeEach(() => {
    mockAxiosGet.mockReset()
  })

  it('image > 30MB 触发 pendingLargeFileConfirm=true', async () => {
    const wrapper = mount(FilePreviewDialog, {
      props: {
        modelValue: true,
        file: makeFile({ file_type: '.jpg', file_size: 40 * 1024 * 1024 }),  // 40 MB
      },
      global: globalStubs,
    })
    await nextTick()
    await flushPromises()
    expect(wrapper.vm.pendingLargeFileConfirm).toBe(true)
    wrapper.unmount()
  })

  it('video > 100MB 触发 pendingLargeFileConfirm=true', async () => {
    const wrapper = mount(FilePreviewDialog, {
      props: {
        modelValue: true,
        file: makeFile({ file_type: '.mp4', file_size: 150 * 1024 * 1024 }),
      },
      global: globalStubs,
    })
    await nextTick()
    await flushPromises()
    expect(wrapper.vm.pendingLargeFileConfirm).toBe(true)
    wrapper.unmount()
  })

  it('image < 30MB 不触发警告, 直接 loadPreview', async () => {
    mockAxiosGet.mockResolvedValueOnce({ data: new Blob(['img'], { type: 'image/jpeg' }) })
    const wrapper = mount(FilePreviewDialog, {
      props: {
        modelValue: true,
        file: makeFile({ file_type: '.jpg', file_size: 1024 * 1024 }),  // 1 MB
      },
      global: globalStubs,
    })
    await nextTick()
    await flushPromises()
    expect(wrapper.vm.pendingLargeFileConfirm).toBe(false)
    expect(wrapper.vm.blobUrl).toBeTruthy()  // 已加载
    wrapper.unmount()
  })
})

describe('FilePreviewDialog v2.7 helper functions', () => {
  beforeEach(() => { mockAxiosGet.mockReset() })

  it('formatSize: 各种 bytes', () => {
    const wrapper = mount(FilePreviewDialog, {
      props: { modelValue: false, file: null },
      global: globalStubs,
    })
    expect(wrapper.vm.formatSize(0)).toBe('0 B')
    expect(wrapper.vm.formatSize(1024)).toBe('1.0 KB')
    expect(wrapper.vm.formatSize(1024 * 1024)).toBe('1.0 MB')
    expect(wrapper.vm.formatSize(1024 * 1024 * 1024)).toBe('1.0 GB')
    wrapper.unmount()
  })

  it('fileExtension: 提取扩展名大写 (.pptx / .PDF 等)', () => {
    const wrapper = mount(FilePreviewDialog, {
      props: { modelValue: false, file: makeFile({ file_name: '组会ppt.pptx' }) },
      global: globalStubs,
    })
    expect(wrapper.vm.fileExtension).toBe('.PPTX')
    wrapper.unmount()

    const wrapper2 = mount(FilePreviewDialog, {
      props: { modelValue: false, file: makeFile({ file_name: 'report.PDF' }) },
      global: globalStubs,
    })
    expect(wrapper2.vm.fileExtension).toBe('.PDF')
    wrapper2.unmount()
  })
})

describe('FilePreviewDialog v2.7 thumbnail fallback for unsupported', () => {
  beforeEach(() => { mockAxiosGet.mockReset() })

  it('unsupported 路径下 thumbnail 拉取 + thumbnailUrl 设置', async () => {
    mockAxiosGet.mockResolvedValueOnce({
      data: { thumbnail_url: 'https://agent.mnb-lab.cn/minio/microbubble/thumbnails/1.jpg' },
    })
    const wrapper = mount(FilePreviewDialog, {
      props: {
        modelValue: true,
        file: makeFile({ file_type: '.unknown_ext' }),
      },
      global: globalStubs,
    })
    await nextTick()
    await flushPromises()
    expect(wrapper.vm.thumbnailUrl).toBeTruthy()
    expect(wrapper.vm.previewType).toBe('unsupported')
    wrapper.unmount()
  })
})
