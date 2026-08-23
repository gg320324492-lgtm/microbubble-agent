// @vitest-environment happy-dom
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import type { Component } from 'vue'

import ResearchPageShell from '@/components/research/ResearchPageShell.vue'
import ResearchPanel from '@/components/research/ResearchPanel.vue'
import ResearchState from '@/components/research/ResearchState.vue'
import Button from '@/components/ui/Button.vue'
import Card from '@/components/ui/Card.vue'
import AgentCard from '@/components/research/AgentCard.vue'
import InsightCard from '@/components/research/InsightCard.vue'
import ScientificMetric from '@/components/research/ScientificMetric.vue'
import StatusBadge from '@/components/research/StatusBadge.vue'
import Timeline from '@/components/research/Timeline.vue'

const componentRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..', 'src', 'renderer', 'src', 'components')
const componentSource = (relativePath: string) => readFileSync(resolve(componentRoot, relativePath), 'utf8')

function mountRequired(component: Component, options: Parameters<typeof mount>[1] = {}): VueWrapper {
  return mount(component, options as never)
}

describe('ResearchPageShell（12）', () => {
  const shell = (props: Record<string, unknown> = {}, slots: Record<string, string> = {}) =>
    mountRequired(ResearchPageShell, {
      props: { title: '臭氧微纳米气泡研究', ...props },
      slots
    })

  it('以一级标题呈现页面标题', () => expect(shell().get('h1').text()).toBe('臭氧微纳米气泡研究'))
  it('呈现眉题以建立科研层级', () => expect(shell({ eyebrow: '当前研究' }).text()).toContain('当前研究'))
  it('呈现页面说明', () => expect(shell({ description: '追踪证据、实验与模型。' }).text()).toContain('追踪证据、实验与模型。'))
  it('呈现状态文案', () => expect(shell({ status: 'AI 在线' }).text()).toContain('AI 在线'))
  it('状态使用可辨识的 status 区域', () => expect(shell({ status: '分析中' }).find('.research-page-shell__status').exists()).toBe(true))
  it('呈现 actions 插槽', () => expect(shell({}, { actions: '<button>导入数据</button>' }).get('button').text()).toBe('导入数据'))
  it('呈现默认内容插槽', () => expect(shell({}, { default: '<article>科研内容</article>' }).get('article').text()).toBe('科研内容'))
  it('无眉题时不渲染空眉题节点', () => expect(shell().find('.research-page-shell__eyebrow').exists()).toBe(false))
  it('无说明时不渲染空说明节点', () => expect(shell().find('.research-page-shell__description').exists()).toBe(false))
  it('根节点提供统一页面类', () => expect(shell().classes()).toContain('research-page-shell'))
  it('内容位于统一 body 容器', () => expect(shell({}, { default: '<span>结果</span>' }).get('.research-page-shell__body').text()).toBe('结果'))
  it('状态更新会同步刷新 DOM', async () => {
    const wrapper = shell({ status: '等待中' })
    await wrapper.setProps({ status: '已完成' })
    expect(wrapper.text()).toContain('已完成')
  })
})

describe('ResearchPanel（12）', () => {
  const panel = (props: Record<string, unknown> = {}, slots: Record<string, string> = {}) =>
    mountRequired(ResearchPanel, {
      props: { title: '证据面板', ...props },
      slots
    })

  it('呈现面板标题', () => expect(panel().text()).toContain('证据面板'))
  it('标题使用面板级标题元素', () => expect(panel().get('h2').text()).toBe('证据面板'))
  it('呈现副标题', () => expect(panel({ subtitle: '共 8 条可靠证据' }).text()).toContain('共 8 条可靠证据'))
  it('无副标题时不产生空节点', () => expect(panel().find('.research-panel__subtitle').exists()).toBe(false))
  it('呈现 actions 插槽', () => expect(panel({}, { actions: '<button>查看全部</button>' }).get('button').text()).toBe('查看全部'))
  it('呈现默认内容插槽', () => expect(panel({}, { default: '<div data-test="evidence">证据 A</div>' }).get('[data-test="evidence"]').text()).toBe('证据 A'))
  it.each(['default', 'primary', 'ai', 'success', 'warning'] as const)('tone=%s 输出对应语义类', (tone) => {
    expect(panel({ tone }).classes()).toContain(`research-panel--${tone}`)
  })
  it('根节点使用 section 语义', () => expect(panel().element.tagName).toBe('SECTION'))
})

describe('ResearchState（18）', () => {
  const state = (value: 'loading' | 'empty' | 'error', props: Record<string, unknown> = {}) =>
    mountRequired(ResearchState, { props: { state: value, ...props } })

  it.each([
    ['loading', 'AI 正在分析...'],
    ['empty', '暂无科研数据'],
    ['error', '分析失败，请重试']
  ] as const)('%s 显示标准中文标题', (value, label) => expect(state(value).text()).toContain(label))

  it.each([
    ['loading', '正在整理科研数据与证据，请稍候。'],
    ['empty', '导入资料或创建研究任务后，这里会显示结果。'],
    ['error', '已有内容不会丢失，可以重新发起本次分析。']
  ] as const)('%s 显示标准辅助说明', (value, description) => expect(state(value).text()).toContain(description))

  it.each(['loading', 'empty', 'error'] as const)('%s 输出状态类', (value) => {
    expect(state(value).classes()).toContain(`research-state--${value}`)
  })

  it.each([
    ['loading', 'sparkles'],
    ['empty', 'document'],
    ['error', 'error']
  ] as const)('%s 使用 %s 定制 SVG 图标', (value, icon) => {
    expect(state(value).get('svg').classes()).toContain(`research-icon--${icon}`)
  })

  it('加载态以礼貌状态区设置完整忙碌宣告', () => {
    const wrapper = state('loading')
    expect(wrapper.attributes()).toMatchObject({
      'aria-busy': 'true',
      'aria-live': 'polite',
      'aria-atomic': 'true',
      role: 'status'
    })
    const loadingSource = componentSource('ui/Loading.vue')
    expect(loadingSource).not.toMatch(/\b(?:800ms|1\.4s)\b/)
    expect(loadingSource).toContain('calc(var(--research-duration-slow)')
  })
  it('非加载态以礼貌状态区宣告且不忙碌', () => {
    expect(state('empty').attributes()).toMatchObject({
      'aria-busy': 'false',
      'aria-live': 'polite',
      'aria-atomic': 'true',
      role: 'status'
    })
  })
  it('错误态以紧急警报显示重新分析操作', () => {
    const wrapper = state('error')
    expect(wrapper.get('button').text()).toBe('重新分析')
    expect(wrapper.attributes()).toMatchObject({
      'aria-live': 'assertive',
      'aria-atomic': 'true',
      role: 'alert'
    })
  })
  it('错误态点击发出 retry', async () => {
    const wrapper = state('error')
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })
  it('允许覆盖标准标题', () => expect(state('empty', { title: '尚未导入实验数据' }).text()).toContain('尚未导入实验数据'))
  it('允许覆盖标准说明', () => expect(state('error', { description: '请检查数据文件格式。' }).text()).toContain('请检查数据文件格式。'))
})

describe('Button 与 Card（12）', () => {
  it('Button 默认使用 primary、medium 与 button 类型', () => {
    const button = mount(Button, { slots: { default: '开始分析' } }).get('button')
    expect(button.classes()).toEqual(expect.arrayContaining(['ui-btn--primary', 'ui-btn--medium']))
    expect(button.attributes('type')).toBe('button')
  })

  it.each(['primary', 'secondary', 'danger', 'ghost'] as const)('Button variant=%s 输出语义类', (variant) => {
    expect(mount(Button, { props: { variant } }).get('button').classes()).toContain(`ui-btn--${variant}`)
  })

  it('Button 加载态禁用并显示无障碍忙碌状态', () => {
    const button = mount(Button, { props: { loading: true } }).get('button')
    expect(button.attributes('disabled')).toBeDefined()
    expect(button.attributes('aria-busy')).toBe('true')
    expect(button.find('svg').exists()).toBe(true)
  })

  it('Button 禁用态阻止 click 事件', async () => {
    const wrapper = mount(Button, { props: { disabled: true } })
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('click')).toBeUndefined()
  })

  it('Button 可用时发出 click 事件', async () => {
    const wrapper = mount(Button)
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('click')).toHaveLength(1)
  })

  it('Card 同时呈现标题与副标题', () => {
    const wrapper = mount(Card, { props: { title: '模型拟合', subtitle: '指数衰减模型' } })
    expect(wrapper.text()).toContain('模型拟合')
    expect(wrapper.text()).toContain('指数衰减模型')
  })

  it('Card 呈现默认内容', () => expect(mount(Card, { slots: { default: '<p>R² = 0.943</p>' } }).text()).toContain('R² = 0.943'))
  it('Card 支持自定义 header', () => expect(mount(Card, { slots: { header: '<h2>自定义科研标题</h2>' } }).get('h2').text()).toBe('自定义科研标题'))
  it('Card 支持 footer', () => expect(mount(Card, { slots: { footer: '<button>导出</button>' } }).get('footer').text()).toBe('导出'))
})

describe('科研卡片、时间线、指标与徽章（20）', () => {
  it.each([
    ['running', '运行中', 'running'],
    ['completed', '已完成', 'check'],
    ['idle', '等待中', 'idle'],
    ['error', '异常', 'error']
  ] as const)('AgentCard %s 显示中文状态与定制图标', (status, label, icon) => {
    const wrapper = mount(AgentCard, { props: { icon: 'agent', name: '规划智能体', status } })
    expect(wrapper.text()).toContain(label)
    expect(wrapper.classes()).toContain(`agent-card--${status}`)
    expect(wrapper.get('.agent-card__status svg').classes()).toContain(`research-icon--${icon}`)
  })

  it('AgentCard 呈现任务与可选耗时', () => {
    const wrapper = mount(AgentCard, { props: { icon: 'agent', name: '知识智能体', status: 'running', task: '检索证据', duration: '1.8 秒' } })
    expect(wrapper.text()).toContain('检索证据')
    expect(wrapper.text()).toContain('1.8 秒')
    const agentSource = componentSource('research/AgentCard.vue')
    expect(agentSource).toMatch(/\.agent-card__task[^}]*var\(--research-text-secondary\)/s)
    expect(agentSource).toMatch(/\.agent-card__duration[^}]*var\(--research-text-secondary\)/s)
    expect(agentSource).not.toMatch(/\.agent-card:hover[^}]*translateY/s)
    expect(componentSource('research/EvidenceCard.vue')).toMatch(/\.evidence-card__label[^}]*var\(--research-text-secondary\)/s)
  })

  it.each([
    ['done', 'check', '已完成'],
    ['current', 'running', '进行中'],
    ['pending', 'idle', '待开始']
  ] as const)('Timeline %s 使用 %s SVG、中文状态且保留标签与时间', (status, icon, statusLabel) => {
    const wrapper = mount(Timeline, { props: { steps: [{ label: '培养反应体系', time: '09:30', status }] } })
    expect(wrapper.text()).toContain('培养反应体系')
    expect(wrapper.text()).toContain('09:30')
    expect(wrapper.get('.timeline__marker svg').classes()).toContain(`research-icon--${icon}`)
    expect(wrapper.get('.timeline__marker').text()).toBe('')
    expect(wrapper.get('.timeline__status-label').text()).toBe(statusLabel)
    const timelineSource = componentSource('research/Timeline.vue')
    expect(timelineSource).toMatch(/\.timeline__time[^}]*var\(--research-text-secondary\)/s)
    expect(timelineSource).toMatch(/\.timeline__marker[^}]*var\(--research-text-secondary\)/s)
  })

  it('ScientificMetric 呈现标签、数值与单位', () => {
    const wrapper = mount(ScientificMetric, { props: { label: '模型拟合', value: '0.943', unit: 'R²' } })
    expect(wrapper.text()).toContain('模型拟合')
    expect(wrapper.text()).toContain('0.943')
    expect(wrapper.text()).toContain('R²')
  })

  it.each([
    ['up', '上升', '-90deg'],
    ['down', '下降', '90deg'],
    ['stable', '稳定', '0deg']
  ] as const)('ScientificMetric %s 趋势使用 progress 图标和方向类', (trend, trendText, rotation) => {
    const wrapper = mount(ScientificMetric, { props: { label: '证据质量', value: '92', trend, trendText } })
    expect(wrapper.text()).toContain(trendText)
    expect(wrapper.get('.metric-card__trend svg').classes()).toContain('research-icon--progress')
    expect(wrapper.get('.metric-card__trend svg').classes()).toContain(`metric-card__trend-icon--${trend}`)
    expect(wrapper.get('.metric-card__trend').classes()).toContain(`metric-card__trend--${trend}`)
    expect(componentSource('research/ScientificMetric.vue')).toMatch(
      new RegExp(`\\.metric-card__trend-icon--${trend}[^}]*rotate\\(${rotation}\\)`, 's')
    )
  })

  it.each([
    ['success', '可信'],
    ['warning', '待确认'],
    ['error', '失败'],
    ['info', '分析中'],
    ['neutral', '等待中']
  ] as const)('StatusBadge %s 同时输出语义类和文案', (status, label) => {
    const wrapper = mount(StatusBadge, { props: { status, label } })
    expect(wrapper.text()).toBe(label)
    expect(wrapper.classes()).toContain(`status-badge--${status}`)
    if (status === 'warning') {
      expect(componentSource('research/StatusBadge.vue')).toMatch(/\.status-badge--warning[^}]*var\(--research-text-primary\)/s)
      const projectSource = componentSource('research/ProjectCard.vue')
      expect(projectSource).toMatch(/\.project-card__status--planning[^}]*var\(--research-text-primary\)/s)
      expect(projectSource).not.toMatch(/\.project-card:hover[^}]*translateY/s)
    }
  })

  it.each([
    ['info', 'sparkles'],
    ['warning', 'warning'],
    ['critical', 'error']
  ] as const)('InsightCard %s 使用 %s 图标并呈现建议', (severity, icon) => {
    const wrapper = mount(InsightCard, { props: { finding: '存在显著非线性趋势', suggestion: '建议增加低浓度梯度。', severity } })
    expect(wrapper.classes()).toContain(`insight-card--${severity}`)
    expect(wrapper.get('svg').classes()).toContain(`research-icon--${icon}`)
    expect(wrapper.text()).toContain('建议增加低浓度梯度。')
  })
})
