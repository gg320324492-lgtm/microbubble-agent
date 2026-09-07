/**
 * FolderDeleteConfirmDialog.test.js — 批次⑩.81 (2026-09-08 选型 A 轻确认卡片)
 *
 * 覆盖 (6 case):
 * - 文件夹主角卡显示名称
 * - 空文件夹 → meta 显示「空文件夹」, 回收站文案走「可随时恢复」分支
 * - 有子项 → meta 显示「N 个子文件夹 · M 个文件」, 回收站文案走「全部移入回收站」分支
 * - adminWarning=true → 红字警告块渲染; false → 不渲染
 * - 点「移入回收站」emit confirm; loading 时按钮文案变「删除中…」且禁用
 * - 回收站说明为 30 天 (对齐后端 DRIVE_RETENTION_DAYS, 不是任务垃圾桶的 3 天)
 */
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))

import FolderDeleteConfirmDialog from '../FolderDeleteConfirmDialog.vue'

const elDialogStub = {
  props: ['modelValue'],
  template: `<div v-if="modelValue" class="el-dialog-stub">
    <slot name="header" /><slot /><slot name="footer" />
  </div>`,
}

function mountDialog(props = {}) {
  return mount(FolderDeleteConfirmDialog, {
    props: { modelValue: true, folderName: '陈天祥-组会PPT', ...props },
    global: { stubs: { 'el-dialog': elDialogStub } },
  })
}

describe('FolderDeleteConfirmDialog 批次⑩.81 选型 A', () => {
  it('主角卡显示文件夹名称', () => {
    const w = mountDialog()
    expect(w.find('.fdc-hero .nm').text()).toBe('陈天祥-组会PPT')
  })

  it('空文件夹: meta=「空文件夹」, 回收站文案=「可随时恢复」分支', () => {
    const w = mountDialog()
    expect(w.find('.fdc-info .meta').text()).toBe('空文件夹')
    expect(w.find('.fdc-recycle').text()).toContain('30 天内可随时恢复')
    expect(w.find('.fdc-recycle').text()).not.toContain('全部移入回收站')
  })

  it('有子项: meta=计数, 回收站文案=「全部移入回收站」分支', () => {
    const w = mountDialog({ folderCount: 5, fileCount: 12 })
    expect(w.find('.fdc-info .meta').text()).toBe('5 个子文件夹 · 12 个文件')
    expect(w.find('.fdc-recycle').text()).toContain('全部移入回收站')
    expect(w.find('.fdc-recycle').text()).toContain('30 天内可整体恢复')
  })

  it('adminWarning 红字警告按 prop 显隐', async () => {
    const w1 = mountDialog({ adminWarning: true })
    expect(w1.find('.fdc-admin-warn').exists()).toBe(true)
    const w2 = mountDialog({ adminWarning: false })
    expect(w2.find('.fdc-admin-warn').exists()).toBe(false)
  })

  it('点「移入回收站」emit confirm; loading 时禁用并显示「删除中…」', async () => {
    const w = mountDialog()
    await w.findAll('.fdc-btn').find(b => b.classes().includes('fdc-primary')).trigger('click')
    expect(w.emitted('confirm')).toHaveLength(1)

    const wl = mountDialog({ loading: true })
    const btn = wl.findAll('.fdc-btn').find(b => b.classes().includes('fdc-primary'))
    expect(btn.text()).toBe('删除中…')
    expect(btn.attributes('disabled')).toBeDefined()
    await btn.trigger('click')
    expect(wl.emitted('confirm')).toBeUndefined()
  })

  it('保留期是 30 天 (DRIVE_RETENTION_DAYS), 不是任务垃圾桶的 3 天', () => {
    const w = mountDialog()
    expect(w.find('.fdc-recycle').text()).not.toContain('3 天内')
  })
})
