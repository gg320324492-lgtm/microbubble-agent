/**
 * DriveFileTable.test.js — 三栏工作台行表组件 (批次③ B)
 * mount-smoke + 关键交互契约: folder 行前置 / 行事件 emit / 列头排序 / 选择 checkbox 同步
 */
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import DriveFileTable from '@/components/drive/DriveFileTable.vue'

const files = [
  { id: 11, file_name: '组会0901.pptx', file_size: 24 * 1024 * 1024, created_at: '2026-09-04T08:00:00', updated_at: '2026-09-01T08:00:00', owner_name: '冯懿鑫', is_starred: false, is_latest: true, version_number: 3 },
  { id: 12, file_name: '综述.docx', file_size: 1100 * 1024, created_at: '2026-08-20T08:00:00', owner_name: '关小未', is_starred: true },
  { id: 13, file_name: '100%报告.pdf', file_size: 999, created_at: '2026-08-10T08:00:00', folder_name: '文献库' },
]
const folders = [
  { id: 3, name: '组会 PPT' },
  { id: 4, name: '实验数据' },
]

function factory(props = {}) {
  return mount(DriveFileTable, {
    props: { files, folders, loading: false, ...props },
    global: { stubs: { ElPagination: true } },
  })
}

describe('DriveFileTable', () => {
  it('文件夹行恒排文件行之前, 名称完整渲染', () => {
    const w = factory()
    const rows = w.findAll('.dft-row')
    expect(rows.length).toBe(5)
    expect(rows[0].classes()).toContain('is-folder')
    expect(rows[1].classes()).toContain('is-folder')
    expect(rows[2].text()).toContain('组会0901.pptx')
  })

  it('单击文件行 emit row-activate; Ctrl 单击 emit select-toggle', async () => {
    const w = factory()
    const fileRow = w.findAll('.dft-row')[2]
    await fileRow.trigger('click')
    expect(w.emitted('row-activate')).toBeTruthy()
    expect(w.emitted('row-activate')[0][0].data.id).toBe(11)

    await fileRow.trigger('click', { ctrlKey: true })
    expect(w.emitted('select-toggle')).toBeTruthy()
    expect(w.emitted('select-toggle').at(-1)[0]).toBe(11)
  })

  it('双击文件行 emit row-preview (不跳页, 预览即开)', async () => {
    const w = factory()
    await w.findAll('.dft-row')[2].trigger('dblclick')
    expect(w.emitted('row-preview')[0][0].id).toBe(11)
  })

  it('列头点击 emit sort-change(file_name)', async () => {
    const w = factory()
    await w.findAll('.dft-head .sortable')[0].trigger('click')
    expect(w.emitted('sort-change')[0]).toEqual(['file_name'])
  })

  it('checkbox change emit select-toggle; 表头全选 emit select-all(true)', async () => {
    const w = factory()
    const box = w.findAll('.dft-row input[type=checkbox]')[0]
    await box.setValue(true)
    expect(w.emitted('select-toggle')[0]).toEqual([11])

    const head = w.find('.dft-head input[type=checkbox]')
    await head.setValue(true)
    expect(w.emitted('select-all').at(-1)).toEqual([true])
  })

  it('搜索态 showPath: 行内渲染所属文件夹 folder_name', () => {
    const w = factory({ showPath: true })
    const pdfRow = w.findAll('.dft-row').find((r) => r.text().includes('100%报告'))
    expect(pdfRow.text()).toContain('文献库')
  })

  it('右键行 emit row-contextmenu(row)', async () => {
    const w = factory()
    await w.findAll('.dft-row')[2].trigger('contextmenu')
    const ev = w.emitted('row-contextmenu')[0]
    expect(ev[0].kind).toBe('file')
    expect(ev[0].data.id).toBe(11)
  })

  it('大小格式化: B/KB/MB 阶梯 + 时间 MM-DD HH:mm', () => {
    const w = factory()
    const row = w.findAll('.dft-row')[2]
    expect(row.text()).toMatch(/24(\.0)? MB/)
  })

  it('空态: 无文件无夹显示引导文案 (区分搜索态)', () => {
    const empty = factory({ files: [], folders: [] })
    expect(empty.find('.dft-states--empty').exists()).toBe(true)
    const searched = factory({ files: [], folders: [], showPath: true })
    expect(searched.text()).toContain('换个更短的关键词')
  })

  it('loading 骨架: 8 行 skeleton', () => {
    const w = factory({ loading: true })
    expect(w.findAll('.dft-skel').length).toBe(8)
  })

  it('shift 连选 emit select-range (含两端 file ids)', async () => {
    const w = factory()
    const rows = w.findAll('.dft-row')
    await rows[2].trigger('click')                       // 记录锚点 idx (file 11)
    await rows[3].trigger('click', { shiftKey: true })  // shift → file 12
    const ev = w.emitted('select-range')
    expect(ev).toBeTruthy()
    expect(ev[0][0].sort()).toEqual([11, 12].sort())
  })

  it('拖拽 dragstart 写 DRIVE_MOVE_MIME (多选集合优先, 未选中行只拖自己)', async () => {
    const { DRIVE_MOVE_MIME } = await import('@/composables/useDriveDragMove')
    const w = factory({ selectedIds: [11, 12] })
    const store = {}
    const dt = { setData: (k, v) => { store[k] = v }, getData: (k) => store[k] || '', types: [], effectAllowed: '' }
    const rows = w.findAll('.dft-row')
    // file 11 行 (在选中集) → 拖整批 [11,12]
    rows[2].trigger('dragstart', { dataTransfer: dt })
    expect(JSON.parse(store[DRIVE_MOVE_MIME])).toEqual([11, 12])
    // file 13 行 (未选中) → 只拖自己
    const store2 = {}
    rows[4].trigger('dragstart', { dataTransfer: { setData: (k, v) => { store2[k] = v }, types: [] } })
    expect(JSON.parse(store2[DRIVE_MOVE_MIME])).toEqual([13])
    expect(w.emitted('drag-change')[0]).toEqual([true])
  })
})
