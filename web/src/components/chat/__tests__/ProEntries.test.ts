/**
 * ProEntries 单测 — W100 +24 派工 v10
 * 7 case 覆盖: 渲染 / 智能显示 / desktop hover 模式 / mobile 始终显示 / 3 entry-click 触发 / aria-label / fallback forceAll
 */
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ProEntries from '../ProEntries.vue'

describe('ProEntries — W100 +24', () => {
  it('① 基础渲染: 3 个按钮 (graph + formula + hypothesis)', () => {
    const wrapper = mount(ProEntries, {
      props: { mode: 'desktop', forceAll: true },
    })
    const buttons = wrapper.findAll('button.entry-btn')
    expect(buttons).toHaveLength(3)
    expect(wrapper.find('.graph-btn').exists()).toBe(true)
    expect(wrapper.find('.formula-btn').exists()).toBe(true)
    expect(wrapper.find('.hypothesis-btn').exists()).toBe(true)
  })

  it('② desktop mode: 初始 opacity=0 (hover 才显)', () => {
    const wrapper = mount(ProEntries, {
      props: { mode: 'desktop', forceAll: true },
    })
    const root = wrapper.find('.pro-entries')
    expect(root.classes()).toContain('mode-desktop')
    expect(root.attributes('role')).toBe('toolbar')
    expect(root.attributes('aria-label')).toBe('专业模块入口工具栏')
  })

  it('③ 智能显示: 有 keywords 时 graph 按钮显示', () => {
    const wrapper = mount(ProEntries, {
      props: {
        mode: 'desktop',
        intent: { category: 'search_knowledge', confidence: 0.9, keywords: ['微泡', '表面张力'] },
      },
    })
    expect(wrapper.find('.graph-btn').exists()).toBe(true)
    // 无 LaTeX 公式 + 未调 list_formulas → formula 按钮不显示
    expect(wrapper.find('.formula-btn').exists()).toBe(false)
    // 未调 list_hypotheses → hypothesis 按钮不显示
    expect(wrapper.find('.hypothesis-btn').exists()).toBe(false)
  })

  it('④ 智能显示: 内容含 LaTeX 时 formula 按钮显示', () => {
    const wrapper = mount(ProEntries, {
      props: {
        mode: 'desktop',
        content: '微泡半径公式: $r = \\sqrt{\\frac{2\\sigma}{\\Delta P}}$',
      },
    })
    expect(wrapper.find('.formula-btn').exists()).toBe(true)
    expect(wrapper.find('.graph-btn').exists()).toBe(false)
    expect(wrapper.find('.hypothesis-btn').exists()).toBe(false)
  })

  it('⑤ 智能显示: toolTrace 含 list_hypotheses 时 hypothesis 按钮显示', () => {
    const wrapper = mount(ProEntries, {
      props: {
        mode: 'desktop',
        toolTrace: [{ name: 'list_hypotheses' }, { name: 'search_knowledge' }],
      },
    })
    expect(wrapper.find('.hypothesis-btn').exists()).toBe(true)
    // 未识别 keywords + 未调 explore_knowledge_graph → graph 不显示
    expect(wrapper.find('.graph-btn').exists()).toBe(false)
    expect(wrapper.find('.formula-btn').exists()).toBe(false)
  })

  it('⑥ entry-click emit: 3 种 entry kind 都能正确触发', async () => {
    const wrapper = mount(ProEntries, {
      props: { mode: 'desktop', forceAll: true },
    })
    await wrapper.find('.graph-btn').trigger('click')
    await wrapper.find('.formula-btn').trigger('click')
    await wrapper.find('.hypothesis-btn').trigger('click')
    const events = wrapper.emitted('entry-click')
    expect(events).toBeTruthy()
    expect(events!.length).toBe(3)
    expect(events![0]).toEqual(['graph'])
    expect(events![1]).toEqual(['formula'])
    expect(events![2]).toEqual(['hypothesis'])
  })

  it('⑦ forceAll fallback: 无任何信号时 3 个按钮都显示', () => {
    const wrapper = mount(ProEntries, {
      props: {
        mode: 'desktop',
        intent: null,
        content: '',
        toolTrace: [],
        forceAll: true,
      },
    })
    const buttons = wrapper.findAll('button.entry-btn')
    expect(buttons).toHaveLength(3)
  })
})