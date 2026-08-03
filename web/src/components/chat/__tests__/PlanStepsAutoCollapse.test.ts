/**
 * PlanSteps W100 +52 auto-collapse 测试 — 默认模式全部 done 后自动折叠成单行
 *
 * 5 case 覆盖：
 * ① 默认模式 (collapsedByDefault=false) 全部 done → 折叠成单行 "✓ 计划完成: N 个步骤"
 * ② 折叠模式 (collapsedByDefault=true) 全部 done → 行为保持不变（用户控制 toggle）
 * ③ 默认模式初次加载 step 全 done (oldVal=0) → 不应折叠 (oldVal > 0 守卫)
 * ④ 默认模式 + 步骤从 1→6 (running 变为 all-done) → 触发折叠
 * ⑤ 折叠态点击 toggle 重新展开 → 看到完整 step 列表
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import PlanSteps from '../PlanSteps.vue'

const pendingSample = [
  { step: '查询知识库', tool: 'search_knowledge', status: 'pending' as const },
  { step: '提取公式', tool: 'extract_formulas', status: 'pending' as const },
  { step: '生成回答', status: 'pending' as const },
]

const runningOneSample = [
  { step: '查询知识库', tool: 'search_knowledge', status: 'done' as const },
  { step: '提取公式', tool: 'extract_formulas', status: 'running' as const },
  { step: '生成回答', status: 'pending' as const },
]

const allDoneSample = [
  { step: '查询知识库', tool: 'search_knowledge', status: 'done' as const },
  { step: '提取公式', tool: 'extract_formulas', status: 'done' as const },
  { step: '生成回答', status: 'done' as const },
]

describe('PlanSteps — W100 +52 auto-collapse', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('① 默认模式 + 全部 done → 折叠成单行 "✓ 计划完成: N 个步骤" + 展开 icon', async () => {
    const wrapper = mount(PlanSteps, {
      props: { steps: runningOneSample },
    })
    // 初始: 展开态 → 列表可见
    expect(wrapper.find('[data-testid="plan-steps-list"]').exists()).toBe(true)
    // 步骤从 1→3 (running 变 all-done) → 触发 auto-collapse
    await wrapper.setProps({ steps: allDoneSample })
    await new Promise((r) => setTimeout(r, 250))
    // 列表已隐藏
    expect(wrapper.find('[data-testid="plan-steps-list"]').exists()).toBe(false)
    // 折叠 header 显示, summary = "计划完成: 3 个步骤"
    const header = wrapper.find('[data-testid="plan-steps-toggle-header"]')
    expect(header.exists()).toBe(true)
    expect(header.text()).toContain('计划完成: 3 个步骤')
    // aria-expanded=false, role=button
    expect(header.attributes('aria-expanded')).toBe('false')
    expect(header.attributes('role')).toBe('button')
  })

  it('② 折叠模式 (collapsedByDefault=true) + 全部 done → 行为保持不变（用户控制 toggle）', async () => {
    const wrapper = mount(PlanSteps, {
      props: { steps: pendingSample, collapsedByDefault: true },
    })
    // 折叠模式初始: 列表不可见
    expect(wrapper.find('[data-testid="plan-steps-list"]').exists()).toBe(false)
    // 步骤变 all-done, auto-collapse 不干预 (LLM 显式要求保留折叠 UI)
    await wrapper.setProps({ steps: allDoneSample })
    await new Promise((r) => setTimeout(r, 250))
    // 列表仍不可见 (因 isShown 受 expanded 控制, 而 expanded 初始 false 未变)
    expect(wrapper.find('[data-testid="plan-steps-list"]').exists()).toBe(false)
    // 用户点击 header → 列表出现
    await wrapper.find('[role="button"]').trigger('click')
    await nextTick()
    expect(wrapper.find('[data-testid="plan-steps-list"]').exists()).toBe(true)
  })

  it('③ 默认模式 + 初次加载 step 全 done (oldVal=0) → 不应折叠 (oldVal > 0 守卫)', async () => {
    // 关键: 用户查看历史消息, message 的 plan 数组里 step 全是 done
    // watcher 触发时 oldVal=0 → 跳过 auto-collapse, 列表直接可见
    const wrapper = mount(PlanSteps, {
      props: { steps: allDoneSample },
    })
    await new Promise((r) => setTimeout(r, 250))
    // 列表可见, 折叠 header 不存在
    expect(wrapper.find('[data-testid="plan-steps-list"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="plan-steps-toggle-header"]').exists()).toBe(false)
    // a11y 隐藏的 summary 仍然显示 "计划完成: 3 个步骤"
    expect(wrapper.find('[data-testid="plan-steps-summary-static"]').text()).toBe('计划完成: 3 个步骤')
  })

  it('④ 默认模式 + 步骤从 1→6 触发折叠 (running 变 all-done, oldVal=1)', async () => {
    // 模拟流式: 初始 1 个 done, 5 个 running → 全部变 done
    const partialSample = [
      { step: '步骤 1', status: 'done' as const },
      { step: '步骤 2', status: 'running' as const },
      { step: '步骤 3', status: 'pending' as const },
      { step: '步骤 4', status: 'pending' as const },
      { step: '步骤 5', status: 'pending' as const },
      { step: '步骤 6', status: 'pending' as const },
    ]
    const wrapper = mount(PlanSteps, {
      props: { steps: partialSample },
    })
    // 初始: 展开态, 列表可见
    expect(wrapper.find('[data-testid="plan-steps-list"]').exists()).toBe(true)
    // 全部 done
    const sixDone = Array.from({ length: 6 }, (_, i) => ({
      step: `步骤 ${i + 1}`,
      status: 'done' as const,
    }))
    await wrapper.setProps({ steps: sixDone })
    await new Promise((r) => setTimeout(r, 250))
    // 列表已折叠
    expect(wrapper.find('[data-testid="plan-steps-list"]').exists()).toBe(false)
    // 折叠 header 显示 "计划完成: 6 个步骤"
    const header = wrapper.find('[data-testid="plan-steps-toggle-header"]')
    expect(header.exists()).toBe(true)
    expect(header.text()).toContain('计划完成: 6 个步骤')
  })

  it('⑤ 折叠态点击 toggle → 重新展开 → 看到完整 step 列表', async () => {
    const wrapper = mount(PlanSteps, {
      props: { steps: runningOneSample },
    })
    // 触发 auto-collapse
    await wrapper.setProps({ steps: allDoneSample })
    await new Promise((r) => setTimeout(r, 250))
    expect(wrapper.find('[data-testid="plan-steps-list"]').exists()).toBe(false)
    // 用户点击 header (auto-collapse header 此时显示)
    const autoHeader = wrapper.find('[data-testid="plan-steps-toggle-header"]')
    expect(autoHeader.exists()).toBe(true)
    await autoHeader.trigger('click')
    await nextTick()
    // 列表展开, 3 个 step 全部可见
    expect(wrapper.find('[data-testid="plan-steps-list"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="plan-step-0-name"]').text()).toBe('查询知识库')
    expect(wrapper.find('[data-testid="plan-step-1-name"]').text()).toBe('提取公式')
    expect(wrapper.find('[data-testid="plan-step-2-name"]').text()).toBe('生成回答')
    // 展开后无 toggle header, a11y 隐藏 summary 仍存在
    expect(wrapper.find('[data-testid="plan-steps-summary-static"]').text()).toBe('计划完成: 3 个步骤')
  })
})
