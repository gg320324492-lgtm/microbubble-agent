/**
 * DriveDetailRail.test.js — 三栏工作台右栏 (批次③ B) 冒烟
 * mock: axios(thumbnail) / useDriveFiles(versions) / userStore / CommentThread stub
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'

vi.mock('axios', () => ({
  default: { get: vi.fn().mockRejectedValue(new Error('no net')), post: vi.fn() },
}))
vi.mock('@/composables/useDriveFiles', () => ({
  useDriveFiles: () => ({
    listVersions: vi.fn().mockResolvedValue([
      { id: 91, version_number: 3, created_at: '2026-09-04T16:22:00', uploaded_by_name: '冯懿鑫' },
      { id: 90, version_number: 2, created_at: '2026-09-01T10:00:00', uploaded_by_name: '冯懿鑫' },
    ]),
    restoreVersion: vi.fn().mockResolvedValue({}),
  }),
}))

import DriveDetailRail from '@/components/drive/DriveDetailRail.vue'
import CommentThread from '@/components/drive/CommentThread.vue'

const file = {
  id: 11, file_name: '组会0901.pptx', title: '组会', file_type: '.pptx',
  file_size: 24 * 1024 * 1024, created_by: 2, owner_name: '冯懿鑫',
  folder_id: 3, folder_name: '2026 秋', created_at: '2026-09-04T16:22:00',
  updated_at: '2026-09-01T21:40:00', is_starred: false, share_token: null,
  download_count: 3, version_number: 3, thumbnail_status: 'none',
}

function factory(props = {}) {
  return mount(DriveDetailRail, {
    props: { file, ...props },
    global: {
      plugins: [createPinia()],
      stubs: { CommentThread },
    },
  })
}

describe('DriveDetailRail', () => {
  it('空态: file=null 显示引导文案', () => {
    const w = factory({ file: null })
    expect(w.find('.rail-empty').exists()).toBe(true)
  })

  it('渲染文件名 / 位置 (可点跳) / 大小 / 上传者', () => {
    const w = factory()
    expect(w.find('.rail-name').text()).toBe('组会0901.pptx')
    expect(w.text()).toContain('2026 秋')
    expect(w.text()).toContain('24.0 MB')
    expect(w.text()).toContain('冯懿鑫')
  })

  it('动作按钮 emit 真实事件 (ppt/docx/pdf: 首排翻页三键 + 二排 下载/分享/收藏 + 三排 重命名/移动/删除)', async () => {
    const w = factory()   // file_name=组会0901.pptx → previewKind='ppt', 走内嵌预览
    const rows = w.findAll('.rail-actions')
    expect(rows.length).toBe(3)

    // 首排 = 上一页 / 全屏放映 / 下一页。批次⑩.37 选型 B 起内嵌预览, 原「预览」按钮已退役
    const pager = rows[0].findAll('.rail-act')
    expect(pager.length).toBe(3)
    expect(pager[0].classes()).toContain('pv')
    expect(pager[1].classes()).toContain('pri')
    expect(pager[2].classes()).toContain('nx')
    expect(pager[0].attributes('disabled')).toBeDefined()   // 停在第 1 页, 不能往前翻
    expect(w.emitted('preview')).toBeFalsy()                 // 内嵌预览, 不再从动作键 emit preview

    const second = rows[1].findAll('.rail-act')              // 下载 / 分享 / 收藏
    expect(second.length).toBe(3)
    await second[0].trigger('click')
    expect(w.emitted('download')[0][0].id).toBe(11)
    await second[1].trigger('click')
    expect(w.emitted('share')[0][0].id).toBe(11)
    await second[2].trigger('click')
    expect(w.emitted('toggle-star')[0][0].id).toBe(11)

    const third = rows[2].findAll('.rail-act')               // 重命名 / 移动 / 删除
    expect(third.length).toBe(3)
    expect(third[0].text()).toContain('重命名')
    expect(third[1].text()).toContain('移动')
    expect(third[2].text()).toContain('删除')
    await third[0].trigger('click')
    expect(w.emitted('rename')).toBeTruthy()
    await third[1].trigger('click')
    expect(w.emitted('move')).toBeTruthy()
    await third[2].trigger('click')
    expect(w.emitted('delete')).toBeTruthy()
  })

  it('动作按钮 emit 真实事件 (其余类型: 首排 全屏放映/下载/分享/收藏, 不渲染翻页二排)', async () => {
    const w = factory({ file: { ...file, id: 12, file_name: '周报.md', file_type: '.md' } })
    const rows = w.findAll('.rail-actions')
    expect(rows.length).toBe(2)
    const first = rows[0].findAll('.rail-act')
    expect(first.length).toBe(4)
    expect(first[0].classes()).toContain('pri')              // 全屏放映
    expect(first[1].text()).toContain('下载')
    expect(first[2].text()).toContain('分享')
    await first[1].trigger('click')
    expect(w.emitted('download')[0][0].id).toBe(12)
    await first[2].trigger('click')
    expect(w.emitted('share')[0][0].id).toBe(12)
    await first[3].trigger('click')
    expect(w.emitted('toggle-star')[0][0].id).toBe(12)

    // 2026-09-05: "加入知识库"按钮已移除 (网盘文件默认自动入库 RAG), 剩 重命名/移动/删除
    const second = rows[1].findAll('.rail-act')
    expect(second.length).toBe(3)
    expect(second[0].text()).toContain('重命名')
    expect(second[1].text()).toContain('移动')
    expect(second[2].text()).toContain('删除')
  })

  it('评论 tab 挂 CommentThread 且 fileId 正确', () => {
    const w = factory()
    const ct = w.findComponent(CommentThread)
    expect(ct.exists()).toBe(true)
    expect(ct.props('fileId')).toBe(11)
  })

  it('版本 tab: 拉取版本列表 + 恢复/对比入口', async () => {
    const w = factory()
    const tabs = w.findAll('.rail-tab')
    await tabs[1].trigger('click')
    // listVersions 异步
    await new Promise((r) => setTimeout(r, 0))
    const vers = w.findAll('.rail-ver')
    expect(vers.length).toBe(2)
    expect(w.text()).toContain('v2')
    // 当前版 (v3) 无恢复按钮, v2 有
    expect(vers[0].find('.restore').exists()).toBe(false)
    expect(vers[1].find('.restore').exists()).toBe(true)
    // 对比入口 → 冒泡开 dialog
    await w.find('.rail-diff-btn').trigger('click')
    expect(w.emitted('open-versions-dialog')).toBeTruthy()
  })

  it('位置链接 emit goto-folder', async () => {
    const w = factory()
    await w.find('.dl .rail-link, dd .rail-link').trigger('click')
    expect(w.emitted('goto-folder')[0]).toEqual([3])
  })
})

describe('DriveDetailRail 未选中兜底 (复刻视觉稿右栏常驻)', () => {
  it('file=null + recent 列表 → 显示「最近上传」条目, 点击 emit pick-file', async () => {
    const w = factory({ file: null, recent: [file, { ...file, id: 12, file_name: '综述.docx' }] })
    expect(w.find('.rail-recent-cap').text()).toContain('最近上传')
    const items = w.findAll('.rail-recent-item')
    expect(items.length).toBe(2)
    expect(items[0].text()).toContain('组会0901.pptx')
    await items[1].trigger('click')
    expect(w.emitted('pick-file')[0][0].id).toBe(12)
  })
  it('file=null 且无 recent → 回落原引导空态', () => {
    const w = factory({ file: null, recent: [] })
    expect(w.find('.rail-recent-item').exists()).toBe(false)
    expect(w.find('.rail-empty-ico').exists()).toBe(true)
  })
})
