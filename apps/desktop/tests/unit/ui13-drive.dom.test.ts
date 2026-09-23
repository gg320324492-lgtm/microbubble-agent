// UI1-3 网盘页原生还原 —— 纯逻辑 + 结构断言
//
// 拖拽与面包屑的判定抽成了纯函数（useDriveNav），这里直接测逻辑 + 挂载测结构。
import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import DriveView from '@renderer/views/DriveView.vue'
import {
  ROOT_CRUMB,
  crumbPath,
  currentFolderId,
  enterFolder,
  extractLocalPaths,
  filterItems,
  goToCrumb,
  hasDraggedFiles,
  isDragActive,
  nextDragDepth,
  type Crumb
} from '@renderer/composables/useDriveNav'

function stubDrive(opts: { items?: unknown[]; folders?: unknown[]; gate?: unknown } = {}): void {
  ;(globalThis as unknown as { window: Record<string, unknown> }).window = {
    api: {
      drive: {
        state: async () => opts.gate ?? { state: 'ready', title: '', hint: '', canOpenSettings: false, actionLabel: '' },
        list: async () => ({ items: opts.items ?? [], total: (opts.items ?? []).length }),
        folders: async () => opts.folders ?? [],
        createFolder: vi.fn(),
        pendingUploads: async () => [],
        upload: vi.fn(),
        rename: vi.fn(),
        remove: vi.fn(),
        download: vi.fn(),
        onProgress: () => () => undefined
      }
    },
    addEventListener: () => undefined,
    removeEventListener: () => undefined
  }
}

afterEach(() => {
  vi.restoreAllMocks()
})

// ---------------------------------------------------------------- 拖拽（纯逻辑）

describe('UI1-3 网盘 — 拖拽上传（纯逻辑）', () => {
  it('★ 拖拽判定：带 Files 类型或有 file 项才算文件拖入', () => {
    expect(hasDraggedFiles({ types: ['Files'] })).toBe(true)
    expect(hasDraggedFiles({ items: [{ kind: 'file' }] })).toBe(true)
    expect(hasDraggedFiles({ types: ['text/plain'] })).toBe(false)
    expect(hasDraggedFiles({ items: [{ kind: 'string' }] })).toBe(false)
    expect(hasDraggedFiles(null)).toBe(false)
    expect(hasDraggedFiles(undefined)).toBe(false)
  })

  it('★ 高亮计数：enter/leave 成对不闪烁；drop 归零', () => {
    let d = 0
    expect(isDragActive(d)).toBe(false)
    d = nextDragDepth(d, 'enter')
    expect(d).toBe(1)
    expect(isDragActive(d)).toBe(true)
    // 子元素 enter/leave 嵌套：先 enter 再 leave → 仍在拖拽态
    d = nextDragDepth(d, 'enter')
    expect(d).toBe(2)
    d = nextDragDepth(d, 'leave')
    expect(d).toBe(1)
    expect(isDragActive(d)).toBe(true)
    // 全部离开 → 高亮消失
    d = nextDragDepth(d, 'leave')
    expect(isDragActive(d)).toBe(false)
    // leave 多于 enter 不会变负数
    expect(nextDragDepth(0, 'leave')).toBe(0)
    // drop 直接归零
    expect(nextDragDepth(3, 'drop')).toBe(0)
  })

  it('★ 本地路径提取：无 path（非 Electron 场景）被过滤，不产生空上传', () => {
    const out = extractLocalPaths([
      { path: 'C:/a.txt', name: 'a.txt' },
      { name: 'b.txt' }, // 无 path
      { path: '', name: 'c.txt' }
    ])
    expect(out).toEqual([{ path: 'C:/a.txt', name: 'a.txt' }])
  })
})

// ---------------------------------------------------------------- 文件夹导航（纯逻辑）

describe('UI1-3 网盘 — 文件夹导航（状态机）', () => {
  it('★ 进入子目录追加面包屑；点面包屑回退到该级', () => {
    let c: Crumb[] = [ROOT_CRUMB]
    expect(currentFolderId(c)).toBeNull()
    c = enterFolder(c, { id: 10, name: '实验数据' })
    expect(currentFolderId(c)).toBe(10)
    expect(crumbPath(c)).toBe('网盘 / 实验数据')
    c = enterFolder(c, { id: 11, name: '2026' })
    expect(currentFolderId(c)).toBe(11)
    expect(crumbPath(c)).toBe('网盘 / 实验数据 / 2026')
    // 回退到第 1 级（实验数据）
    c = goToCrumb(c, 1)
    expect(currentFolderId(c)).toBe(10)
    // 回退到根
    c = goToCrumb(c, 0)
    expect(currentFolderId(c)).toBeNull()
    // 越界回退 → 根
    expect(goToCrumb(c, -5)).toEqual([ROOT_CRUMB])
  })

  it('★ 搜索过滤：按文件名/标题本地过滤，空关键词返回全部', () => {
    const items = [{ fileName: '报告.txt', title: '报告' }, { fileName: 'data.csv', title: '数据' }]
    expect(filterItems(items, '')).toHaveLength(2)
    expect(filterItems(items, '报告')).toHaveLength(1)
    expect(filterItems(items, 'DATA')).toHaveLength(1) // 大小写不敏感
    expect(filterItems(items, 'zzz')).toHaveLength(0)
  })
})

// ---------------------------------------------------------------- 页面结构（挂载）

describe('UI1-3 网盘 — 工作台结构（挂载）', () => {
  it('★ 顶栏含搜索/新建文件夹/上传/刷新，且有面包屑与拖拽区', async () => {
    stubDrive()
    const w = mount(DriveView, { global: { stubs: { transition: false } } })
    await flushPromises()
    expect(w.find('[data-testid="drive-search"]').exists()).toBe(true)
    expect(w.find('[data-testid="drive-new-folder"]').exists()).toBe(true)
    expect(w.find('[data-testid="drive-upload"]').exists()).toBe(true)
    expect(w.find('[data-testid="drive-refresh"]').exists()).toBe(true)
    expect(w.find('[data-testid="drive-crumbs"]').exists()).toBe(true)
    expect(w.find('[data-testid="drive-dropzone"]').exists()).toBe(true)
    expect(w.get('[data-testid="drive-crumb-path"]').text()).toBe('网盘')
  })

  it('★ 文件夹与文件同页渲染；空目录给空态', async () => {
    stubDrive({
      folders: [{ id: 10, name: '实验数据', parentId: null }],
      items: [{ id: 1, title: '占位.txt', fileName: '占位.txt', fileType: 'txt', fileSize: 2048, folderId: null, visibility: 'team', ownerName: '演示' }]
    })
    const w = mount(DriveView, { global: { stubs: { transition: false } } })
    await flushPromises()
    expect(w.find('[data-testid="drive-folder-10"]').exists()).toBe(true)
    expect(w.get('[data-testid="drive-folder-10"]').text()).toContain('实验数据')
    expect(w.find('[data-testid="drive-item-1"]').exists()).toBe(true)
    expect(w.get('[data-testid="drive-item-1"]').text()).toContain('2.0 KB')
    expect(w.find('[data-testid="drive-empty"]').exists()).toBe(false)
  })

  it('★ 空目录：显示空态提示，不渲染列表', async () => {
    stubDrive()
    const w = mount(DriveView, { global: { stubs: { transition: false } } })
    await flushPromises()
    expect(w.get('[data-testid="drive-empty"]').text()).toContain('这个目录还没有内容')
    expect(w.find('[data-testid="drive-list"]').exists()).toBe(false)
  })

  it('★ 引导态：未登录时只渲染引导，不渲染工作台', async () => {
    stubDrive({
      gate: { state: 'unbound', title: '需登录课题组账号才能使用网盘', hint: '请到「设置 · 账号」登录。', canOpenSettings: true, actionLabel: '前往设置 · 账号' }
    })
    const w = mount(DriveView, { global: { stubs: { transition: false } } })
    await flushPromises()
    expect(w.find('[data-testid="drive-source-gate"]').exists()).toBe(true)
    expect(w.find('[data-testid="drive-dropzone"]').exists()).toBe(false)
    expect(w.text()).not.toContain('绑定')
  })
})
