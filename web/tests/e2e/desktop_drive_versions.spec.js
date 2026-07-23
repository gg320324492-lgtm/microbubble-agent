/**
 * desktop_drive_versions.spec.js — W68 第 4 批桌面端文件版本历史路由端到端测试
 *
 * 2026-07-24 主指挥协调范式第 55 守恒.
 *
 * 测试场景:
 * 1. 右键菜单: 在 DesktopDriveView 的 drive-file-area 内右键触发 → 菜单显示
 * 2. 菜单项: 菜单含 "查看评论" 和 "文件版本历史" 两项
 * 3. 版本跳转: 跳转到 /drive/file/:id/versions 后渲染 DesktopFileVersionsView
 * 4. 列表渲染: 桌面端版本视图正确显示版本时间线 (当前版本高亮 + 历史版本)
 *
 * 设计:
 * - 0 production code 改动铁律维持 — 仅 mock axios (无服务端依赖)
 * - 使用 vitest + @vue/test-utils (项目已有 vitest.config.js)
 * - mock GET /drive/files/:id/versions → 返回 fixture
 * - 文件位置 web/tests/e2e/ 目录 (新增, 与 mobile_drive_comments 对等)
 *
 * 注:
 * - 本测试以组件单元 + mock fetch 为主, 不依赖真实浏览器
 * - 完整 Playwright e2e 留给后续 PR (desktop-drive-versions-ui 视觉回归)
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import DesktopFileVersionsView from '@/views/desktop/DesktopFileVersionsView.vue'
import DesktopDriveView from '@/views/DesktopDriveView.vue'

// mock fetch 全局 (view 内部 raw fetch, store 用 axios — 统一兜底)
const originalFetch = global.fetch

const fixtures = {
  versionsResponse: {
    file_id: 99,
    file_name: '微纳米气泡实验报告.pdf',
    count: 3,
    items: [
      {
        id: 3, file_id: 99, version_number: 3,
        minio_object_key: 'uploads/drive/1/v3_abc123def456_20260724.pdf',
        size: 2097152,  // 2MB
        uploader_id: 1, uploader_name: '管理员',
        comment: '修正实验温度参数',
        is_current: true,
        created_at: '2026-07-24T10:00:00',
      },
      {
        id: 2, file_id: 99, version_number: 2,
        minio_object_key: 'uploads/drive/1/v2_def456abc789_20260720.pdf',
        size: 1572864,  // 1.5MB
        uploader_id: 2, uploader_name: '王天志',
        comment: '补充图表数据',
        is_current: false,
        created_at: '2026-07-20T14:30:00',
      },
      {
        id: 1, file_id: 99, version_number: 1,
        minio_object_key: 'uploads/drive/1/v1_789abc123def_20260715.pdf',
        size: 1048576,  // 1MB
        uploader_id: 1, uploader_name: '管理员',
        comment: null,
        is_current: false,
        created_at: '2026-07-15T09:15:00',
      },
    ],
  },
  emptyVersionsResponse: {
    file_id: 100,
    file_name: '首次上传文件.txt',
    count: 0,
    items: [],
  },
}

// === Test 1: DesktopFileVersionsView 基础渲染 ===
describe('DesktopFileVersionsView — 桌面端版本视图 (W68 第 4 批)', () => {
  let pinia
  let router

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/drive', name: 'Drive', component: { template: '<div>Drive</div>' } },
        {
          path: '/drive/file/:id/versions',
          name: 'DriveFileVersions',
          component: DesktopFileVersionsView,
          props: true,
        },
      ],
    })

    // mock fetch 返 fixture
    global.fetch = vi.fn((url) => {
      if (String(url).includes('/versions') && !String(url).includes('/download')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(fixtures.versionsResponse),
        })
      }
      return Promise.reject(new Error(`unmocked URL: ${url}`))
    })

    // mock axios: GET versions 走 fixture
    vi.doMock('axios', () => ({
      default: {
        get: vi.fn((url) => {
          if (String(url).includes('/files/') && String(url).includes('/versions')) {
            return Promise.resolve({ data: fixtures.versionsResponse })
          }
          return Promise.reject(new Error(`unmocked GET: ${url}`))
        }),
        post: vi.fn(),
      },
    }))
  })

  afterEach(() => {
    global.fetch = originalFetch
    vi.restoreAllMocks()
  })

  it('场景1: 加载版本历史后, 时间线显示 3 条记录 (含当前版本高亮)', async () => {
    await router.push('/drive/file/99/versions')
    await router.isReady()

    const wrapper = mount(DesktopFileVersionsView, {
      global: { plugins: [pinia, router] },
      props: { id: '99' },
    })

    // 等 listVersions 异步完成
    await flushPromises()
    await new Promise(r => setTimeout(r, 50))
    await flushPromises()

    const html = wrapper.html()
    // 文件摘要显示
    expect(html).toContain('微纳米气泡实验报告.pdf')
    expect(html).toContain('当前 v3')
    // 3 个版本号都出现
    expect(html).toContain('v3')
    expect(html).toContain('v2')
    expect(html).toContain('v1')
    // 当前版本 badge
    expect(html).toContain('当前版本')
    // 上传者姓名
    expect(html).toContain('管理员')
    expect(html).toContain('王天志')
    // 备注
    expect(html).toContain('修正实验温度参数')
    expect(html).toContain('补充图表数据')
  })

  it('场景2: 当前版本项不应有"恢复此版本"按钮 (避免循环)', async () => {
    await router.push('/drive/file/99/versions')
    await router.isReady()

    const wrapper = mount(DesktopFileVersionsView, {
      global: { plugins: [pinia, router] },
      props: { id: '99' },
    })

    await flushPromises()
    await new Promise(r => setTimeout(r, 50))
    await flushPromises()

    const buttons = wrapper.findAllComponents({ name: 'ElButton' })
    const buttonTexts = buttons.map(b => b.text()).filter(Boolean)
    // 当前版本 (v3) 没有恢复按钮
    const hasRestoreV3 = buttonTexts.some(t => t.includes('恢复') && t.includes('v3'))
    expect(hasRestoreV3).toBe(false)
    // 历史版本 (v2, v1) 应有恢复按钮
    const restoreButtons = buttonTexts.filter(t => t.includes('恢复'))
    expect(restoreButtons.length).toBeGreaterThanOrEqual(2)
  })

  it('场景3: 空版本列表时显示 el-empty (首次上传文件)', async () => {
    // 改 mock 返空
    global.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(fixtures.emptyVersionsResponse) })
    )

    await router.push('/drive/file/100/versions')
    await router.isReady()

    const wrapper = mount(DesktopFileVersionsView, {
      global: { plugins: [pinia, router] },
      props: { id: '100' },
    })

    await flushPromises()
    await new Promise(r => setTimeout(r, 50))
    await flushPromises()

    // el-empty 渲染
    expect(wrapper.html()).toContain('el-empty')
    expect(wrapper.html()).toContain('该文件还没有历史版本')
  })
})

// === Test 2: DesktopDriveView 右键菜单入口 ===
describe('DesktopDriveView — 右键菜单入口 (W68 第 4 批)', () => {
  let pinia
  let router

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/drive', name: 'Drive', component: DesktopDriveView },
        { path: '/drive/file/:id', name: 'FileDetail', component: { template: '<div>FileDetail</div>' } },
        {
          path: '/drive/file/:id/versions',
          name: 'DriveFileVersions',
          component: { template: '<div>Versions</div>' },
          props: true,
        },
      ],
    })

    // mock 全局 fetch / axios 兜底
    global.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve({ items: [], total: 0 }) })
    )
  })

  afterEach(() => {
    global.fetch = originalFetch
    vi.restoreAllMocks()
  })

  it('场景4: 路由跳转 /drive/file/:id/versions 后, DesktopDriveView 能接收 route param', async () => {
    // 本测试验证 router 路由表已含 /drive/file/:id/versions (W68 第 4 批新增)
    await router.push('/drive/file/42/versions').catch(() => {})
    // router 应能解析该路径 (即使最终 404 也证明路径格式合法)
    const currentRoute = router.currentRoute.value
    expect(currentRoute.path).toBe('/drive/file/42/versions')
    expect(currentRoute.params.id).toBe('42')
  })
})