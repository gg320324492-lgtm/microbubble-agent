// @vitest-environment happy-dom
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import ScientificChart from '@/components/research/ScientificChart.vue'
import type { ModelFitResult } from '@/services/research/data-analysis.service'
import { buildKineticFitOption } from '@/utils/scientific-chart'

const echartsMocks = vi.hoisted(() => ({
  init: vi.fn(),
  use: vi.fn()
}))

vi.mock('echarts/core', () => ({
  init: echartsMocks.init,
  use: echartsMocks.use
}))
vi.mock('echarts/charts', () => ({ LineChart: { name: 'LineChart' } }))
vi.mock('echarts/components', () => ({
  GridComponent: { name: 'GridComponent' },
  LegendComponent: { name: 'LegendComponent' },
  TooltipComponent: { name: 'TooltipComponent' },
  AriaComponent: { name: 'AriaComponent' }
}))
vi.mock('echarts/renderers', () => ({ CanvasRenderer: { name: 'CanvasRenderer' } }))

const validModel: ModelFitResult = {
  model: 'first-order',
  parameters: { k: 0.0243 },
  rSquared: 0.9887,
  residualError: 0.0211
}

async function build(model: ModelFitResult) {
  return buildKineticFitOption(model)
}

function seriesOf(option: Awaited<ReturnType<typeof build>>) {
  return option.series as Array<{ name: string; data: Array<[number, number]> }>
}

describe('科学图表配置构建器（20）', () => {
  it('一级动力学模型名翻译为中文', async () => {
    expect(JSON.stringify(await build(validModel))).toContain('一级动力学')
  })

  it('零级动力学模型名翻译为中文且不伪造一级曲线', async () => {
    const option = await build({ ...validModel, model: 'zero-order' })
    expect(JSON.stringify(option)).toContain('零级动力学')
    expect(seriesOf(option)).toHaveLength(0)
    expect(JSON.stringify(option)).toContain('不支持该模型绘图')
    expect(JSON.stringify(option)).not.toContain('缺少有效的一级动力学参数 k')
  })

  it('未知模型以中文未知标签保留原模型标识', async () => {
    expect(JSON.stringify(await build({ ...validModel, model: 'langmuir' }))).toContain('未知模型（langmuir）')
  })

  it('有效 k 只生成模型预测曲线和残差上下界', async () => {
    expect(seriesOf(await build(validModel)).map(item => item.name)).toEqual([
      '残差范围下界',
      '残差范围',
      '模型预测曲线'
    ])
  })

  it('预测曲线从时间零和归一化浓度一开始', async () => {
    expect(seriesOf(await build(validModel))[2].data[0]).toEqual([0, 1])
  })

  it('预测曲线提供覆盖零到一百二十分钟的二十五个点', async () => {
    const data = seriesOf(await build(validModel))[2].data
    expect(data).toHaveLength(25)
    expect(data.at(-1)?.[0]).toBe(120)
  })

  it('预测时间点严格递增', async () => {
    const times = seriesOf(await build(validModel))[2].data.map(([time]) => time)
    expect(times.every((time, index) => index === 0 || time > times[index - 1])).toBe(true)
  })

  it('一级动力学预测浓度严格单调下降', async () => {
    const values = seriesOf(await build(validModel))[2].data.map(([, value]) => value)
    expect(values.every((value, index) => index === 0 || value < values[index - 1])).toBe(true)
  })

  it('预测值严格来自 C/C₀ 等于 exp(-kt)', async () => {
    const point = seriesOf(await build(validModel))[2].data.find(([time]) => time === 60)
    expect(point?.[1]).toBeCloseTo(Math.exp(-0.0243 * 60), 6)
  })

  it('残差范围上界不会超过归一化浓度一', async () => {
    const series = seriesOf(await build(validModel))
    expect(series[1].data.every(([, width], index) => series[0].data[index][1] + width <= 1)).toBe(true)
  })

  it('残差范围下界不会低于零', async () => {
    const lower = seriesOf(await build(validModel))[0].data
    expect(lower.every(([, value]) => value >= 0)).toBe(true)
  })

  it('残差上下界由真实 residualError 对称推导', async () => {
    const option = await build(validModel)
    const series = seriesOf(option)
    const prediction = series[2].data[12][1]
    expect(series[0].data[12][1]).toBeCloseTo(prediction - validModel.residualError, 6)
    expect(series[0].data[12][1] + series[1].data[12][1]).toBeCloseTo(prediction + validModel.residualError, 6)
  })

  it('图例把误差区域明确标记为残差范围', async () => {
    expect(JSON.stringify(await build(validModel))).toContain('残差范围')
  })

  it('配置绝不把残差范围称为置信区间', async () => {
    expect(JSON.stringify(await build(validModel))).not.toContain('置信区间')
  })

  it('ARIA 摘要包含三位小数拟合可信度', async () => {
    const option = await build(validModel)
    expect((option.aria as { description: string }).description).toContain('拟合可信度 0.989')
  })

  it('非法 R² 不输出 NaN 或 Infinity', async () => {
    const option = await build({ ...validModel, rSquared: Number.NaN })
    expect(JSON.stringify(option)).not.toMatch(/NaN|Infinity/)
    expect((option.aria as { description: string }).description).toContain('拟合可信度待评估')
  })

  it('缺少 k 时返回空序列和中文原因', async () => {
    const option = await build({ ...validModel, parameters: {} })
    expect(seriesOf(option)).toHaveLength(0)
    expect(JSON.stringify(option)).toContain('缺少有效的一级动力学参数 k')
  })

  it('非正 k 被视为非法且不生成伪曲线', async () => {
    for (const k of [0, -0.1]) {
      expect(seriesOf(await build({ ...validModel, parameters: { k } }))).toHaveLength(0)
    }
  })

  it('非有限 k 与负值或非有限残差被防御性过滤', async () => {
    expect(seriesOf(await build({ ...validModel, parameters: { k: Number.POSITIVE_INFINITY } }))).toHaveLength(0)
    for (const residualError of [-0.085, Number.NaN, Number.POSITIVE_INFINITY]) {
      const option = await build({ ...validModel, residualError })
      expect(seriesOf(option).map(item => item.name)).toEqual(['模型预测曲线'])
      expect((option.aria as { description: string }).description).toContain('残差范围待评估')
      expect(JSON.stringify(option.legend)).not.toContain('残差范围')
      expect(JSON.stringify(option)).not.toMatch(/NaN|Infinity|±0\.085/)
    }
  })

  it('构建器保留中文坐标与提示但不复制视觉主题颜色', async () => {
    const option = await build(validModel)
    expect(option.color).toBeUndefined()
    expect((option.xAxis as { name: string }).name).toBe('时间（分钟）')
    expect((option.yAxis as { name: string }).name).toBe('归一化浓度 C/C₀')
    const formatter = (option.tooltip as { formatter: (params: unknown) => string }).formatter
    const y = Math.exp(-0.0243 * 60)
    const tooltip = formatter([{ seriesName: '模型预测曲线', value: [60, y] }])
    expect(tooltip).toContain('时间：60 分钟')
    expect(tooltip).toContain('归一化浓度 C/C₀')
    expect(tooltip).toContain(y.toFixed(3))
  })
})

const chart = {
  setOption: vi.fn(),
  resize: vi.fn(),
  dispose: vi.fn()
}

let observerCallback: ResizeObserverCallback | undefined
const observer = {
  observe: vi.fn(),
  disconnect: vi.fn()
}

async function mountChart(props: Record<string, unknown>): Promise<VueWrapper> {
  return mount(ScientificChart, { attachTo: document.body, props })
}

describe('ScientificChart 图表生命周期（14）', () => {
  beforeEach(() => {
    echartsMocks.init.mockReset().mockReturnValue(chart)
    chart.setOption.mockReset()
    chart.resize.mockReset()
    chart.dispose.mockReset()
    observer.observe.mockReset()
    observer.disconnect.mockReset()
    observerCallback = undefined
    vi.stubGlobal('ResizeObserver', class {
      constructor(callback: ResizeObserverCallback) { observerCallback = callback }
      observe = observer.observe
      disconnect = observer.disconnect
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('挂载有数据图表时初始化唯一 ECharts 实例', async () => {
    const wrapper = await mountChart({ option: { series: [] }, ariaLabel: '动力学图' })
    expect(echartsMocks.init).toHaveBeenCalledOnce()
    wrapper.unmount()
  })

  it('初始化后向真实实例传入首个配置', async () => {
    const tokenValues: Record<string, string> = {
      '--research-primary-500': 'rgb(10 20 30)',
      '--research-ai-500': 'rgb(40 50 60)',
      '--research-success-500': 'rgb(70 80 90)',
      '--research-text-secondary': 'rgb(100 110 120)',
      '--research-text-primary': 'rgb(15 25 35)',
      '--research-border-subtle': 'rgb(130 140 150)',
      '--research-border-strong': 'rgb(120 130 140)',
      '--research-bg-card': 'rgb(250 251 252)',
      '--research-font-sans': '科研测试字体'
    }
    const styleSpy = vi.spyOn(window, 'getComputedStyle').mockReturnValue({
      getPropertyValue: (name: string) => tokenValues[name] ?? ''
    } as CSSStyleDeclaration)
    const option = {
      title: { text: '真实配置' },
      animationDuration: 420,
      xAxis: { type: 'value' },
      yAxis: { type: 'value' },
      series: [{ name: '模型预测曲线', type: 'line', data: [] }]
    }
    const wrapper = await mountChart({ option, ariaLabel: '动力学图' })
    expect(chart.setOption).toHaveBeenCalledWith(expect.objectContaining({
      title: option.title,
      animationDuration: 420,
      color: ['rgb(10 20 30)', 'rgb(40 50 60)', 'rgb(70 80 90)'],
      textStyle: expect.objectContaining({ color: 'rgb(100 110 120)', fontFamily: '科研测试字体' }),
      xAxis: expect.objectContaining({
        axisLabel: { color: 'rgb(100 110 120)' },
        axisLine: { lineStyle: { color: 'rgb(120 130 140)' } },
        splitLine: { lineStyle: { color: 'rgb(130 140 150)' } }
      }),
      tooltip: expect.objectContaining({
        backgroundColor: 'rgb(250 251 252)',
        borderColor: 'rgb(120 130 140)',
        textStyle: expect.objectContaining({ color: 'rgb(15 25 35)' })
      }),
      legend: expect.objectContaining({
        textStyle: expect.objectContaining({ color: 'rgb(100 110 120)' })
      }),
      series: [expect.objectContaining({ lineStyle: expect.objectContaining({ color: 'rgb(10 20 30)' }) })]
    }))
    styleSpy.mockRestore()
    wrapper.unmount()
  })

  it('图表宿主具备中文图片角色与可读标签', async () => {
    const option = await build(validModel)
    const description = (option.aria as { description: string }).description
    const wrapper = await mountChart({ option, ariaLabel: description })
    const label = wrapper.get('[role="img"]').attributes('aria-label')
    expect(label).toContain('一级动力学')
    expect(label).toContain('时间')
    expect(label).toContain('归一化浓度 C/C₀')
    expect(label).toContain('拟合可信度 0.989')
    expect(label).toContain('残差范围 ±0.021')
    wrapper.unmount()
  })

  it('有 ResizeObserver 时观察图表宿主', async () => {
    const wrapper = await mountChart({ option: {}, ariaLabel: '动力学图' })
    expect(observer.observe).toHaveBeenCalledWith(wrapper.get('[data-testid="scientific-chart"]').element)
    wrapper.unmount()
  })

  it('尺寸观察回调触发真实图表 resize', async () => {
    const wrapper = await mountChart({ option: {}, ariaLabel: '动力学图' })
    observerCallback?.([], {} as ResizeObserver)
    expect(chart.resize).toHaveBeenCalledOnce()
    wrapper.unmount()
  })

  it('配置更新以 notMerge 方式完整替换', async () => {
    let primary = 'rgb(20 30 40)'
    const styleSpy = vi.spyOn(window, 'getComputedStyle').mockReturnValue({
      getPropertyValue: (name: string) => name === '--research-primary-500' ? primary : ''
    } as CSSStyleDeclaration)
    const wrapper = await mountChart({ option: { series: [{ data: [1] }] }, ariaLabel: '动力学图' })
    chart.setOption.mockClear()
    primary = 'rgb(50 60 70)'
    await wrapper.setProps({ option: { series: [{ data: [2] }] } })
    expect(chart.setOption).toHaveBeenCalledWith(
      expect.objectContaining({
        color: expect.arrayContaining(['rgb(50 60 70)']),
        series: [expect.objectContaining({ data: [2] })]
      }),
      { notMerge: true }
    )
    styleSpy.mockRestore()
    wrapper.unmount()
  })

  it('初始空态不初始化图表并显示中文说明', async () => {
    const wrapper = await mountChart({ option: {}, ariaLabel: '缺少有效的一级动力学参数 k，暂无可绘制曲线', empty: true })
    expect(echartsMocks.init).not.toHaveBeenCalled()
    const empty = wrapper.get('[data-testid="scientific-chart-empty"]')
    expect(empty.text()).toContain('暂无可绘制的科学数据')
    expect(empty.attributes('aria-label')).toContain('缺少有效的一级动力学参数 k')
    wrapper.unmount()
  })

  it('从空态切换到有数据会延迟初始化', async () => {
    const wrapper = await mountChart({ option: {}, ariaLabel: '动力学图', empty: true })
    await wrapper.setProps({ empty: false })
    await flushPromises()
    expect(echartsMocks.init).toHaveBeenCalledOnce()
    wrapper.unmount()
  })

  it('从有数据切换到空态释放当前实例', async () => {
    const wrapper = await mountChart({ option: {}, ariaLabel: '动力学图' })
    await wrapper.setProps({ empty: true })
    expect(chart.dispose).toHaveBeenCalledOnce()
    wrapper.unmount()
  })

  it('空态恢复后创建全新观察关系', async () => {
    const wrapper = await mountChart({ option: {}, ariaLabel: '动力学图' })
    await wrapper.setProps({ empty: true })
    await wrapper.setProps({ empty: false })
    await flushPromises()
    expect(echartsMocks.init).toHaveBeenCalledTimes(2)
    expect(observer.observe).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('卸载时释放 ECharts 实例', async () => {
    const wrapper = await mountChart({ option: {}, ariaLabel: '动力学图' })
    wrapper.unmount()
    expect(chart.dispose).toHaveBeenCalledOnce()
  })

  it('卸载时断开 ResizeObserver', async () => {
    const wrapper = await mountChart({ option: {}, ariaLabel: '动力学图' })
    wrapper.unmount()
    expect(observer.disconnect).toHaveBeenCalledOnce()
  })

  it('环境缺少 ResizeObserver 且偏好减少动效时安全禁用动画', async () => {
    vi.stubGlobal('ResizeObserver', undefined)
    vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: true }))
    const wrapper = await mountChart({ option: { animationDuration: 420 }, ariaLabel: '动力学图' })
    expect(echartsMocks.init).toHaveBeenCalledOnce()
    expect(chart.setOption).toHaveBeenCalledWith(expect.objectContaining({ animation: false, animationDuration: 0 }))
    expect(() => wrapper.unmount()).not.toThrow()
  })

  it('空态期间配置变化不会向已释放实例写入', async () => {
    const wrapper = await mountChart({ option: { series: [] }, ariaLabel: '动力学图' })
    await wrapper.setProps({ empty: true })
    chart.setOption.mockClear()
    await wrapper.setProps({ option: { series: [{ data: [3] }] } })
    expect(chart.setOption).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
