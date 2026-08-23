// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import ResearchIcon from '@/components/icons/ResearchIcon.vue'

const ICON_NAMES = [
  'home',
  'assistant',
  'project',
  'literature',
  'experiment',
  'data',
  'manuscript',
  'graph',
  'agent',
  'settings',
  'notification',
  'user',
  'collapse',
  'expand',
  'search',
  'upload',
  'check',
  'warning',
  'error',
  'idle',
  'running',
  'sparkles',
  'tool',
  'evidence',
  'citation',
  'model',
  'clock',
  'progress',
  'folder',
  'document'
] as const

function mountIcon(props: Record<string, unknown>): VueWrapper {
  return mount(ResearchIcon, { props })
}

describe('ResearchIcon 的 30 个定制科研图标', () => {
  it.each(ICON_NAMES)('%s 渲染统一原生 SVG 契约', (name) => {
    const wrapper = mountIcon({ name })
    const svg = wrapper.get('svg')
    expect(svg.classes()).toContain(`research-icon--${name}`)
    expect(svg.attributes('viewBox')).toBe('0 0 24 24')
    expect(svg.attributes('fill')).toBe('none')
    expect(svg.attributes('stroke')).toBe('currentColor')
    expect(svg.findAll('path').length).toBeGreaterThan(0)
  })
})

describe('ResearchIcon 可访问性', () => {
  it.each([
    ['home', '科研首页'],
    ['assistant', '科研助手'],
    ['experiment', '实验设计'],
    ['graph', '知识图谱'],
    ['agent', '智能体状态']
  ] as const)('%s 有标签时作为可读图像暴露“%s”', (name, label) => {
    const svg = mountIcon({ name, label }).get('svg')
    expect(svg.attributes('role')).toBe('img')
    expect(svg.attributes('aria-label')).toBe(label)
    expect(svg.attributes('aria-hidden')).toBeUndefined()
  })
})

describe('ResearchIcon 尺寸', () => {
  it.each([12, 16, 24, 32])('数值尺寸 %d 同步设置宽高', (size) => {
    const svg = mountIcon({ name: 'model', size }).get('svg')
    expect(svg.attributes('width')).toBe(String(size))
    expect(svg.attributes('height')).toBe(String(size))
  })
})

describe('ResearchIcon 色彩继承', () => {
  it.each([
    ['currentColor', 'currentColor'],
    ['var(--research-primary-500)', 'var(--research-primary-500)'],
    ['inherit', 'inherit']
  ] as const)('显式颜色 %s 通过 color 样式传递', (color, expected) => {
    const svg = mountIcon({ name: 'data', color }).get('svg')
    expect(svg.attributes('style').toLowerCase()).toContain(`color: ${expected}`.toLowerCase())
    expect(svg.attributes('stroke')).toBe('currentColor')
  })
})

describe('ResearchIcon 未知名称降级', () => {
  it.each(['unknown', '', 'HOME'])('运行时名称“%s”安全降级到 document', (name) => {
    const svg = mountIcon({ name }).get('svg')
    expect(svg.classes()).toContain('research-icon--document')
    expect(svg.findAll('path').length).toBeGreaterThan(0)
  })
})

describe('ResearchIcon 装饰性与路径细节', () => {
  it('默认装饰图标同时对读屏隐藏且不可聚焦', () => {
    const svg = mountIcon({ name: 'home' }).get('svg')
    expect(svg.attributes('aria-hidden')).toBe('true')
    expect(svg.attributes('focusable')).toBe('false')
  })

  it('assistant 由多段手工路径组成以表达对话结构', () => {
    expect(mountIcon({ name: 'assistant' }).findAll('path').length).toBeGreaterThan(1)
  })

  it('literature 由多段手工路径组成以表达双页结构', () => {
    expect(mountIcon({ name: 'literature' }).findAll('path').length).toBeGreaterThan(1)
  })
})
