import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import MobileFormSheet from '../MobileFormSheet.vue'

describe('MobileFormSheet', () => {
  const fields = [
    { key: 'title', label: '标题', type: 'input', required: true, placeholder: '输入标题' },
    { key: 'priority', label: '优先级', type: 'radio', options: [
      { value: 'high', label: '高' },
      { value: 'low', label: '低' },
    ]},
    { key: 'agree', label: '同意条款', type: 'switch' },
  ]

  const factory = (props = {}) => mount(MobileFormSheet, {
    props: {
      modelValue: true,
      title: '测试表单',
      fields,
      form: { title: '', priority: 'high', agree: false },
      ...props,
    },
    global: {
      stubs: {
        Teleport: true, // Stub Teleport 简化测试
      },
    },
  })

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('modelValue=true 时渲染 sheet', () => {
    const wrapper = factory()
    expect(wrapper.find('.sheet-title').exists()).toBe(true)
    expect(wrapper.text()).toContain('测试表单')
  })

  it('modelValue=false 时不渲染', () => {
    const wrapper = factory({ modelValue: false })
    expect(wrapper.find('.sheet-overlay').exists()).toBe(false)
  })

  it('渲染所有字段', () => {
    const wrapper = factory()
    const inputs = wrapper.findAll('.form-field')
    expect(inputs.length).toBe(3)
  })

  it('required 字段显示星号', () => {
    const wrapper = factory()
    expect(wrapper.find('.required-mark').exists()).toBe(true)
    expect(wrapper.text()).toContain('*')
  })

  it('input 字段双向绑定到 form', async () => {
    const wrapper = factory({ form: { title: '', priority: 'high', agree: false } })
    const input = wrapper.find('input.field-input')
    await input.setValue('测试标题')
    expect(wrapper.emitted('update:form')).toBeTruthy()
    const update = wrapper.emitted('update:form')[0][0]
    expect(update.title).toBe('测试标题')
  })

  it('radio 字段点击切换值', async () => {
    const wrapper = factory({ form: { title: '', priority: 'high', agree: false } })
    const lowBtn = wrapper.findAll('.opt-chip').find((b) => b.text() === '低')
    await lowBtn.trigger('click')
    expect(wrapper.emitted('update:form')).toBeTruthy()
    const update = wrapper.emitted('update:form')[0][0]
    expect(update.priority).toBe('low')
  })

  it('switch 字段点击切换 boolean', async () => {
    const wrapper = factory({ form: { title: '', priority: 'high', agree: false } })
    const switchBtn = wrapper.find('.field-switch')
    await switchBtn.trigger('click')
    expect(wrapper.emitted('update:form')).toBeTruthy()
    expect(wrapper.emitted('update:form')[0][0].agree).toBe(true)
  })

  it('空 required 字段提交时显示错误', async () => {
    const wrapper = factory({ form: { title: '', priority: 'high', agree: false } })
    const submitBtn = wrapper.find('.btn-primary')
    await submitBtn.trigger('click')
    expect(wrapper.find('.field-error').exists()).toBe(true)
    expect(wrapper.text()).toContain('标题不能为空')
  })

  it('valid 字段提交触发 submit 事件', async () => {
    const wrapper = factory({ form: { title: '有效', priority: 'high', agree: false } })
    const submitBtn = wrapper.find('.btn-primary')
    await submitBtn.trigger('click')
    expect(wrapper.emitted('submit')).toBeTruthy()
    expect(wrapper.emitted('submit')[0][0]).toEqual({
      title: '有效',
      priority: 'high',
      agree: false,
    })
  })

  it('取消按钮触发 cancel 和 update:modelValue(false)', async () => {
    const wrapper = factory()
    const cancelBtn = wrapper.find('.btn-secondary')
    await cancelBtn.trigger('click')
    expect(wrapper.emitted('cancel')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')[0][0]).toBe(false)
  })

  it('遮罩点击关闭', async () => {
    const wrapper = factory()
    const overlay = wrapper.find('.sheet-overlay')
    await overlay.trigger('click')
    expect(wrapper.emitted('update:modelValue')[0][0]).toBe(false)
  })
})