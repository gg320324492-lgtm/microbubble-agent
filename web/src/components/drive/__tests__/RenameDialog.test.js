/**
 * RenameDialog.test.js — 批次⑩.83 重命名预填修复
 *
 * 背景: syncFromTarget 之前只是 defineExpose, 父层从未调用 → 弹窗打开时输入框永远为空
 * (左栏树右键「重命名」事件甚至无人监听)。修复后 modelValue 变 true 自动预填。
 *
 * 覆盖 (3 case):
 * - 打开时预填文件夹当前名称 (folder target.name)
 * - 打开时预填文件当前名称 (file target.title / file_name)
 * - 确认时 emit rename {id, type, oldName, newName}
 */
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import RenameDialog from '../RenameDialog.vue'

const elDialogStub = {
  props: ['modelValue', 'title'],
  emits: ['update:modelValue', 'closed'],
  template: `<div v-if="modelValue" class="el-dialog-stub"><slot /><slot name="footer" /></div>`,
}

const elFormStub = {
  template: '<form><slot /></form>',
  methods: { validate: () => Promise.resolve(true), clearValidate: () => {} },
}

function mountDialog(props = {}) {
  return mount(RenameDialog, {
    props: { modelValue: false, target: null, targetType: 'folder', ...props },
    global: {
      stubs: {
        'el-dialog': elDialogStub,
        'el-form': elFormStub,
        'el-form-item': { template: '<div><slot /></div>' },
        'el-input': { props: ['modelValue', 'maxlength'], emits: ['update:modelValue'],
          template: `<input :value="modelValue" @input="$emit('update:modelValue', $event.target.value)" />` },
        'el-button': { template: '<button><slot /></button>' },
      },
    },
  })
}

describe('RenameDialog 批次⑩.83 预填修复', () => {
  it('打开时预填文件夹当前名称', async () => {
    const w = mountDialog({ target: { id: 336, name: '组会PPT' }, targetType: 'folder' })
    await w.setProps({ modelValue: true })
    expect(w.find('input').element.value).toBe('组会PPT')
  })

  it('打开时预填文件当前名称 (title 优先, file_name 兜底)', async () => {
    const w = mountDialog({ target: { id: 1, title: '开题报告.pdf', file_name: '开题报告.pdf' }, targetType: 'file' })
    await w.setProps({ modelValue: true })
    expect(w.find('input').element.value).toBe('开题报告.pdf')
  })

  it('确认时 emit rename {id, type, oldName, newName}', async () => {
    const w = mountDialog({ target: { id: 356, name: '陈天祥' }, targetType: 'folder', modelValue: true })
    await w.find('input').setValue('陈天祥-新')
    await w.findAll('button').find(b => b.text() === '确认').trigger('click')
    const evt = w.emitted('rename')
    expect(evt).toHaveLength(1)
    expect(evt[0][0]).toMatchObject({ id: 356, type: 'folder', oldName: '陈天祥', newName: '陈天祥-新' })
  })
})
