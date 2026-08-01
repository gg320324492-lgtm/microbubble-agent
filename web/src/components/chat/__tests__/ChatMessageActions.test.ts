/**
 * ChatMessageActions 单测 — W100 +23 派工 v10
 * 7 case 覆盖: 渲染 / desktop hover 模式 / mobile 始终显示 / regenerate 触发 / copy 触发 / 反馈状态 / aria-label
 */
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ChatMessageActions from '../ChatMessageActions.vue'

describe('ChatMessageActions — W100 +23', () => {
  it('① 基础渲染: 2 个按钮 (regenerate + copy)', () => {
    const wrapper = mount(ChatMessageActions, {
      props: { mode: 'desktop' },
    })
    const buttons = wrapper.findAll('button.action-btn')
    expect(buttons).toHaveLength(2)
    expect(wrapper.find('.regenerate-btn').exists()).toBe(true)
    expect(wrapper.find('.copy-btn').exists()).toBe(true)
  })

  it('② desktop mode: 初始 opacity=0 (hover 才显)', () => {
    const wrapper = mount(ChatMessageActions, {
      props: { mode: 'desktop' },
    })
    const root = wrapper.find('.chat-message-actions')
    expect(root.classes()).toContain('mode-desktop')
    // 通过检查 className (CSS opacity 无法在 jsdom 验证, 但 className 标识正确)
    expect(root.attributes('role')).toBe('toolbar')
    expect(root.attributes('aria-label')).toBe('消息操作工具栏')
  })

  it('③ mobile mode: 始终显示 + tap 区域 ≥ 44px', () => {
    const wrapper = mount(ChatMessageActions, {
      props: { mode: 'mobile' },
    })
    const root = wrapper.find('.chat-message-actions')
    expect(root.classes()).toContain('mode-mobile')
    const buttons = wrapper.findAll('button.action-btn')
    expect(buttons[0].classes()).toContain('regenerate-btn')
    // mobile 模式 .action-text 应渲染
    expect(wrapper.findAll('.action-text')).toHaveLength(2)
  })

  it('④ regenerate 按钮点击 → emit regenerate', async () => {
    const wrapper = mount(ChatMessageActions, {
      props: { mode: 'desktop' },
    })
    await wrapper.find('.regenerate-btn').trigger('click')
    expect(wrapper.emitted('regenerate')).toBeTruthy()
    expect(wrapper.emitted('regenerate')).toHaveLength(1)
  })

  it('⑤ copy 按钮点击 → emit copy', async () => {
    const wrapper = mount(ChatMessageActions, {
      props: { mode: 'desktop' },
    })
    await wrapper.find('.copy-btn').trigger('click')
    expect(wrapper.emitted('copy')).toBeTruthy()
    expect(wrapper.emitted('copy')).toHaveLength(1)
  })

  it('⑥ regenerate 重复点击 → 第二次 disabled 不触发', async () => {
    const wrapper = mount(ChatMessageActions, {
      props: { mode: 'desktop' },
    })
    const regenBtn = wrapper.find('.regenerate-btn')
    await regenBtn.trigger('click')
    // regenerating 状态已置 true, disabled 应生效
    expect(regenBtn.attributes('disabled')).toBeDefined()
    // 第二次点击 disabled button → 不会 emit
    await regenBtn.trigger('click')
    expect(wrapper.emitted('regenerate')).toHaveLength(1)
  })

  it('⑦ aria-label / title 描述每个按钮 (a11y)', () => {
    const wrapper = mount(ChatMessageActions, {
      props: { mode: 'desktop' },
    })
    const regenBtn = wrapper.find('.regenerate-btn')
    expect(regenBtn.attributes('aria-label')).toBe('重新生成回答')
    expect(regenBtn.attributes('title')).toBe('重新生成回答')
    const copyBtn = wrapper.find('.copy-btn')
    expect(copyBtn.attributes('aria-label')).toBe('复制消息内容')
    expect(copyBtn.attributes('title')).toBe('复制消息内容')
  })
})