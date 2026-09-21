// M2-3c 网盘页 —— 真挂载 DOM 断言
//
// 为什么必须有：M8-2/M2-3b 双实证——**SFC 模板结构性错误 typecheck 抓不到**
// （漏闭合 → 动态 import 失败 → 页面白屏，而 typecheck 0 错）。故新页面必须真挂载验证。
import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import DriveView from '@renderer/views/DriveView.vue'

/** 桩 window.api.drive（各用例按需覆盖 state/list） */
function stubDriveApi(opts: {
  state?: unknown
  list?: unknown
  pending?: unknown
  listRejects?: string
}): void {
  const onProgress = vi.fn(() => () => undefined)
  ;(globalThis as unknown as { window: { api: unknown } }).window.api = {
    drive: {
      state: async () => opts.state ?? { state: 'ready', title: '', hint: '', canOpenSettings: false, actionLabel: '' },
      list: async () => {
        if (opts.listRejects) throw new Error(opts.listRejects)
        return opts.list ?? { items: [], total: 0 }
      },
      pendingUploads: async () => opts.pending ?? [],
      rename: vi.fn(),
      remove: vi.fn(),
      upload: vi.fn(),
      onProgress
    }
  }
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('网盘页 — 真挂载', () => {
  it('未绑定：渲染引导态（标题/提示/设置入口），不渲染文件列表', async () => {
    stubDriveApi({
      state: {
        state: 'unbound',
        title: '需连接云端才能使用网盘',
        hint: '网盘数据保存在课题组服务器上。',
        canOpenSettings: true,
        actionLabel: '前往设置 · 云端连接'
      }
    })
    const w = mount(DriveView, { global: { stubs: { transition: false } } })
    await flushPromises()
    expect(w.find('[data-testid="drive-source-gate"]').exists()).toBe(true)
    expect(w.text()).toContain('需连接云端才能使用网盘')
    expect(w.find('[data-testid="drive-open-settings"]').exists()).toBe(true)
    expect(w.find('[data-testid="drive-list"]').exists()).toBe(false)
  })

  it('离线：不给出设置入口（文案由状态机决定，组件不硬编码）', async () => {
    stubDriveApi({
      state: { state: 'offline', title: '当前离线', hint: '网盘需要联网访问。', canOpenSettings: false, actionLabel: '' }
    })
    const w = mount(DriveView, { global: { stubs: { transition: false } } })
    await flushPromises()
    expect(w.find('[data-testid="drive-source-gate"]').exists()).toBe(true)
    expect(w.find('[data-testid="drive-open-settings"]').exists()).toBe(false)
  })

  it('可用且空：渲染工具栏与空态', async () => {
    stubDriveApi({ state: { state: 'ready', title: '', hint: '', canOpenSettings: false, actionLabel: '' } })
    const w = mount(DriveView, { global: { stubs: { transition: false } } })
    await flushPromises()
    expect(w.find('[data-testid="drive-source-gate"]').exists()).toBe(false)
    expect(w.find('[data-testid="drive-upload"]').exists()).toBe(true)
    expect(w.find('[data-testid="drive-empty"]').exists()).toBe(true)
  })

  it('有文件：列表渲染文件名/体积/可见性，且 visibility 原样展示（不本地过滤）', async () => {
    stubDriveApi({
      state: { state: 'ready', title: '', hint: '', canOpenSettings: false, actionLabel: '' },
      list: {
        items: [
          { id: 1, title: 'a.txt', fileName: 'a.txt', fileType: 'txt', fileSize: 2048, folderId: null, visibility: 'team', ownerName: '演示' },
          { id: 2, title: 'b.bin', fileName: 'b.bin', fileType: 'bin', fileSize: 5 * 1024 * 1024, folderId: null, visibility: 'private', ownerName: '演示' }
        ],
        total: 2
      }
    })
    const w = mount(DriveView, { global: { stubs: { transition: false } } })
    await flushPromises()
    const list = w.find('[data-testid="drive-list"]')
    expect(list.exists()).toBe(true)
    expect(list.findAll('li')).toHaveLength(2)
    expect(w.text()).toContain('a.txt')
    expect(w.text()).toContain('2.0 KB')
    expect(w.text()).toContain('5.0 MB')
    // ★ private 条目必须照实展示（服务端已做可见性过滤，客户端不二次过滤）
    expect(w.find('[data-testid="drive-item-2"]').exists()).toBe(true)
    expect(w.text()).toContain('private')
  })

  it('未完成上传：展示续传入口与已传块数', async () => {
    stubDriveApi({
      state: { state: 'ready', title: '', hint: '', canOpenSettings: false, actionLabel: '' },
      pending: [{ uploadId: 'u1', filename: 'big.bin', uploadedChunks: [0, 1], totalChunks: 5 }]
    })
    const w = mount(DriveView, { global: { stubs: { transition: false } } })
    await flushPromises()
    expect(w.find('[data-testid="drive-pending"]').exists()).toBe(true)
    expect(w.text()).toContain('已传 2/5 块')
  })

  it('列表接口报错：页面不崩（错误提示由消息组件承载）', async () => {
    stubDriveApi({
      state: { state: 'ready', title: '', hint: '', canOpenSettings: false, actionLabel: '' },
      listRejects: '云端服务暂时不可用，请稍后重试。'
    })
    const w = mount(DriveView, { global: { stubs: { transition: false } } })
    await flushPromises()
    // 结构性断言：容器仍在，未抛异常
    expect(w.find('.drive').exists()).toBe(true)
  })
})
