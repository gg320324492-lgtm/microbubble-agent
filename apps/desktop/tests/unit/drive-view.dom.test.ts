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
  folders?: unknown
}): { listCalls: Array<number | null> } {
  const listCalls: Array<number | null> = []
  const onProgress = vi.fn(() => () => undefined)
  ;(globalThis as unknown as { window: { api: unknown } }).window.api = {
    drive: {
      state: async () => opts.state ?? { state: 'ready', title: '', hint: '', canOpenSettings: false, actionLabel: '' },
      list: async (folderId?: number | null) => {
        listCalls.push(folderId ?? null)
        if (opts.listRejects) throw new Error(opts.listRejects)
        return opts.list ?? { items: [], total: 0 }
      },
      pendingUploads: async () => opts.pending ?? [],
      // UI1-3：网盘页新增文件夹导航
      folders: async () => opts.folders ?? [],
      rename: vi.fn(),
      remove: vi.fn(),
      upload: vi.fn(),
      onProgress
    }
  }
  return { listCalls }
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

// ---------------------------------------------------------------- DL-3 目录视图契约

describe('DL-3 当前目录视图 — 子文件夹与文件混合渲染', () => {
  it('★ 根视图：子文件夹可见（团队盘根只有文件夹），不出「空目录」误导文案', async () => {
    stubDriveApi({
      folders: [
        { id: 10, name: '组会PPT', parentId: null },
        { id: 20, name: '实验数据', parentId: null }
      ],
      list: { items: [], total: 0 }
    })
    const w = mount(DriveView, { global: { stubs: { transition: false } } })
    await flushPromises()
    expect(w.find('[data-testid="drive-folders"]').exists()).toBe(true)
    expect(w.find('[data-testid="drive-folder-10"]').text()).toContain('组会PPT')
    expect(w.find('[data-testid="drive-folder-20"]').exists()).toBe(true)
    // 根视图文件为空是正常的 → 不渲染文件列表；但子文件夹在场 → 空态文案不得出现
    expect(w.find('[data-testid="drive-list"]').exists()).toBe(false)
    expect(w.find('[data-testid="drive-empty"]').exists()).toBe(false)
  })

  it('★ 混合视图：当前目录的子文件夹与文件同时渲染（DL-2 空白页病根回归防线）', async () => {
    stubDriveApi({
      folders: [{ id: 336, name: '艾琳琳', parentId: null }],
      list: {
        items: [
          { id: 1, title: 'a.pptx', fileName: 'a.pptx', fileType: 'pptx', fileSize: 1024, folderId: 10, visibility: 'team', ownerName: '演示' }
        ],
        total: 1
      }
    })
    const w = mount(DriveView, { global: { stubs: { transition: false } } })
    await flushPromises()
    expect(w.find('[data-testid="drive-folder-336"]').exists()).toBe(true)
    const list = w.find('[data-testid="drive-list"]')
    expect(list.exists()).toBe(true)
    expect(list.findAll('li')).toHaveLength(1)
    expect(w.text()).toContain('a.pptx')
  })

  it('进入子文件夹：面包屑推进、只渲染直接子文件夹、按 folder_id 拉文件列表', async () => {
    const { listCalls } = stubDriveApi({
      folders: [
        { id: 10, name: '组会PPT', parentId: null },
        { id: 336, name: '艾琳琳', parentId: 10 },
        { id: 337, name: '深层目录', parentId: 336 }
      ]
    })
    const w = mount(DriveView, { global: { stubs: { transition: false } } })
    await flushPromises()
    expect(listCalls[0]).toBeNull() // 根视图不带 folder_id
    await w.get('[data-testid="drive-folder-10"] .drive-folder-btn').trigger('click')
    await flushPromises()
    // 面包屑推进到 组会PPT；文件列表按 folder_id=10 拉取
    expect(w.find('[data-testid="drive-crumbs"]').text()).toContain('组会PPT')
    expect(listCalls[1]).toBe(10)
    // 只显示当前目录的直接子文件夹（艾琳琳），隔代（深层目录）不出现
    expect(w.find('[data-testid="drive-folder-336"]').exists()).toBe(true)
    expect(w.find('[data-testid="drive-folder-337"]').exists()).toBe(false)
  })
})
