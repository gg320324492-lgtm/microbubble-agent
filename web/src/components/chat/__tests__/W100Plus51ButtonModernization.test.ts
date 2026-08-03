/**
 * W100 +51 按钮现代化测试
 *
 * 覆盖:
 * - ChatMessageActions: 桌面端用 Refresh + CopyDocument icon 替换 emoji ✅
 * - ChatMessageActions: 复制中状态显示 Check icon ✅
 * - ChatMessageActions: 重新生成中状态显示 Loading icon ✅
 * - ChatMessageActions: 桌面端 hover-only 模式不变 ✅
 * - ChatMessageActions: 移动端文字标签持续渲染 ✅
 * - ProEntries: 3 按钮 icon 化 (Share / DataAnalysis / Aim) ✅
 * - ProEntries: 智能显示逻辑不变 (forceAll 仍 3 个按钮) ✅
 */

import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'

// 用 stub 替换 Element Plus icons + el-icon: jsdom 不解析 SVG
// 保留以 'data-icon' 标记, 方便测试断言 icon 类别
const stubs = {
  'el-icon': defineComponent({
    name: 'ElIconStub',
    template: '<i class="el-icon-stub"><slot /></i>',
  }),
  Refresh: defineComponent({ name: 'RefreshStub', template: '<i class="ep-refresh" data-icon="Refresh" />' }),
  CopyDocument: defineComponent({ name: 'CopyDocumentStub', template: '<i class="ep-copy-document" data-icon="CopyDocument" />' }),
  Check: defineComponent({ name: 'CheckStub', template: '<i class="ep-check" data-icon="Check" />' }),
  Loading: defineComponent({ name: 'LoadingStub', template: '<i class="ep-loading" data-icon="Loading" />' }),
  Share: defineComponent({ name: 'ShareStub', template: '<i class="ep-share" data-icon="Share" />' }),
  DataAnalysis: defineComponent({ name: 'DataAnalysisStub', template: '<i class="ep-data-analysis" data-icon="DataAnalysis" />' }),
  Aim: defineComponent({ name: 'AimStub', template: '<i class="ep-aim" data-icon="Aim" />' }),
}

import ChatMessageActions from '../ChatMessageActions.vue'
import ProEntries from '../ProEntries.vue'

describe('W100 +51 ChatMessageActions icon 现代化', () => {
  it('① 桌面端基础状态: 用 Refresh + CopyDocument icon (替换 emoji)', () => {
    const wrapper = mount(ChatMessageActions, {
      props: { mode: 'desktop' },
      global: { stubs },
    })
    const icons = wrapper.findAll('[data-icon]')
    const refreshIcon = wrapper.find('[data-icon="Refresh"]')
    const copyIcon = wrapper.find('[data-icon="CopyDocument"]')
    expect(refreshIcon.exists()).toBe(true)
    expect(copyIcon.exists()).toBe(true)
    expect(icons.length).toBe(2)
  })

  it('② 桌面端 hover-only 模式保持不变', () => {
    const wrapper = mount(ChatMessageActions, {
      props: { mode: 'desktop' },
      global: { stubs },
    })
    const root = wrapper.find('.chat-message-actions')
    expect(root.classes()).toContain('mode-desktop')
    expect(root.attributes('role')).toBe('toolbar')
    expect(root.attributes('aria-label')).toBe('消息操作工具栏')
  })

  it('③ 桌面端 aria-label / title 描述保留', () => {
    const wrapper = mount(ChatMessageActions, {
      props: { mode: 'desktop' },
      global: { stubs },
    })
    const regenBtn = wrapper.find('.regenerate-btn')
    expect(regenBtn.attributes('aria-label')).toBe('重新生成回答')
    expect(regenBtn.attributes('title')).toBe('重新生成回答')
    const copyBtn = wrapper.find('.copy-btn')
    expect(copyBtn.attributes('aria-label')).toBe('复制消息内容')
    expect(copyBtn.attributes('title')).toBe('复制消息内容')
  })

  it('④ 移动端文字标签 + icon 同时渲染', () => {
    const wrapper = mount(ChatMessageActions, {
      props: { mode: 'mobile' },
      global: { stubs },
    })
    // 2 个按钮 + 2 个文字标签
    expect(wrapper.findAll('.action-text')).toHaveLength(2)
    expect(wrapper.find('[data-icon="Refresh"]').exists()).toBe(true)
    expect(wrapper.find('[data-icon="CopyDocument"]').exists()).toBe(true)
  })

  it('⑤ 复制中: CopyDocument 替换为 Check icon', async () => {
    const wrapper = mount(ChatMessageActions, {
      props: { mode: 'desktop' },
      global: { stubs },
    })
    // 点击 copy
    await wrapper.find('.copy-btn').trigger('click')
    // 复制中状态 → Check icon
    expect(wrapper.find('[data-icon="Check"]').exists()).toBe(true)
    expect(wrapper.find('[data-icon="CopyDocument"]').exists()).toBe(false)
  })
})

describe('W100 +51 ProEntries icon 现代化', () => {
  it('⑥ 3 按钮全部使用 Element Plus icon (替换 emoji)', () => {
    const wrapper = mount(ProEntries, {
      props: { mode: 'desktop', forceAll: true },
      global: { stubs },
    })
    expect(wrapper.find('[data-icon="Share"]').exists()).toBe(true)
    expect(wrapper.find('[data-icon="DataAnalysis"]').exists()).toBe(true)
    expect(wrapper.find('[data-icon="Aim"]').exists()).toBe(true)
  })

  it('⑦ 桌面端 hover-only 模式保持不变', () => {
    const wrapper = mount(ProEntries, {
      props: { mode: 'desktop', forceAll: true },
      global: { stubs },
    })
    const root = wrapper.find('.pro-entries')
    expect(root.classes()).toContain('mode-desktop')
    expect(root.attributes('role')).toBe('toolbar')
  })

  it('⑧ 3 entry-click emit 仍正常', async () => {
    const wrapper = mount(ProEntries, {
      props: { mode: 'desktop', forceAll: true },
      global: { stubs },
    })
    await wrapper.find('.graph-btn').trigger('click')
    await wrapper.find('.formula-btn').trigger('click')
    await wrapper.find('.hypothesis-btn').trigger('click')
    const events = wrapper.emitted('entry-click')
    expect(events).toBeTruthy()
    expect(events!.length).toBe(3)
  })

  it('⑨ 智能显示逻辑不变: 无信号 + forceAll=true → 3 按钮都显示', () => {
    const wrapper = mount(ProEntries, {
      props: { mode: 'desktop', intent: null, content: '', toolTrace: [], forceAll: true },
      global: { stubs },
    })
    const buttons = wrapper.findAll('button.entry-btn')
    expect(buttons).toHaveLength(3)
  })

  it('⑩ 智能显示: LaTeX 检测仍控制 formula 按钮显示', () => {
    const wrapper = mount(ProEntries, {
      props: { mode: 'desktop', content: '微泡半径公式: $r = \\sqrt{\\frac{2\\sigma}{\\Delta P}}$' },
      global: { stubs },
    })
    expect(wrapper.find('.formula-btn').exists()).toBe(true)
    expect(wrapper.find('.graph-btn').exists()).toBe(false)
    expect(wrapper.find('.hypothesis-btn').exists()).toBe(false)
  })
})
