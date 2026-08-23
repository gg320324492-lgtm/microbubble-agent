<script setup lang="ts">
import { LineChart } from 'echarts/charts'
import { AriaComponent, GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import type { EChartsType } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsOption } from 'echarts'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { resolveResearchChartTheme, type ResearchChartTheme } from '../../utils/scientific-chart'

echarts.use([
  LineChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  AriaComponent,
  CanvasRenderer
])

const props = withDefaults(defineProps<{
  option: EChartsOption
  ariaLabel: string
  empty?: boolean
}>(), {
  empty: false
})

const host = ref<HTMLDivElement | null>(null)
let chart: EChartsType | null = null
let observer: ResizeObserver | null = null

type OptionRecord = Record<string, unknown>

function asRecord(value: unknown): OptionRecord {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as OptionRecord
    : {}
}

function themeAxis(axis: unknown, theme: ResearchChartTheme): unknown {
  const apply = (value: unknown): OptionRecord => {
    const current = asRecord(value)
    const axisLine = asRecord(current.axisLine)
    const splitLine = asRecord(current.splitLine)
    return {
      ...current,
      axisLine: {
        ...axisLine,
        lineStyle: { ...asRecord(axisLine.lineStyle), color: theme.strongBorder }
      },
      axisLabel: { ...asRecord(current.axisLabel), color: theme.text },
      splitLine: {
        ...splitLine,
        lineStyle: { ...asRecord(splitLine.lineStyle), color: theme.border }
      }
    }
  }
  return Array.isArray(axis) ? axis.map(apply) : apply(axis)
}

function themeSeries(series: unknown, theme: ResearchChartTheme): unknown {
  if (!Array.isArray(series)) return series
  return series.map(value => {
    const current = asRecord(value)
    if (current.name === '模型预测曲线') {
      return {
        ...current,
        lineStyle: { ...asRecord(current.lineStyle), color: theme.primary }
      }
    }
    if (current.name === '残差范围') {
      return {
        ...current,
        areaStyle: { ...asRecord(current.areaStyle), color: theme.ai }
      }
    }
    return current
  })
}

function themedOption(option: EChartsOption): EChartsOption {
  const style = host.value && typeof window.getComputedStyle === 'function'
    ? window.getComputedStyle(host.value)
    : null
  const theme = resolveResearchChartTheme(style)
  const current = option as OptionRecord
  const tooltip = asRecord(current.tooltip)
  const legend = asRecord(current.legend)
  let reducedMotion = false
  try {
    reducedMotion = typeof window.matchMedia === 'function'
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  } catch {
    reducedMotion = false
  }
  return {
    ...current,
    ...(reducedMotion ? { animation: false, animationDuration: 0 } : {}),
    color: [theme.primary, theme.ai, theme.success],
    textStyle: { ...asRecord(current.textStyle), color: theme.text, fontFamily: theme.fontFamily },
    tooltip: {
      ...tooltip,
      backgroundColor: theme.surface,
      borderColor: theme.strongBorder,
      textStyle: { ...asRecord(tooltip.textStyle), color: theme.strongText, fontFamily: theme.fontFamily }
    },
    legend: {
      ...legend,
      textStyle: { ...asRecord(legend.textStyle), color: theme.text, fontFamily: theme.fontFamily }
    },
    xAxis: themeAxis(current.xAxis, theme),
    yAxis: themeAxis(current.yAxis, theme),
    series: themeSeries(current.series, theme)
  } as EChartsOption
}

function releaseChart(): void {
  observer?.disconnect()
  observer = null
  chart?.dispose()
  chart = null
}

async function initializeChart(): Promise<void> {
  if (typeof window === 'undefined' || props.empty || chart) return
  if (!host.value) await nextTick()
  if (!host.value || props.empty || chart) return
  chart = echarts.init(host.value)
  chart.setOption(themedOption(props.option))

  if (typeof ResizeObserver !== 'undefined') {
    observer = new ResizeObserver(() => chart?.resize())
    observer.observe(host.value)
  }
}

onMounted(() => {
  void initializeChart()
})

watch(
  () => props.option,
  option => {
    if (!props.empty) chart?.setOption(themedOption(option), { notMerge: true })
  },
  { deep: true }
)

watch(
  () => props.empty,
  empty => {
    if (empty) releaseChart()
    else void initializeChart()
  },
  { flush: 'post' }
)

onBeforeUnmount(releaseChart)
</script>

<template>
  <div class="scientific-chart-frame">
    <div
      v-if="empty"
      class="scientific-chart-frame__empty"
      data-testid="scientific-chart-empty"
      role="status"
      :aria-label="ariaLabel"
    >
      暂无可绘制的科学数据
    </div>
    <div
      v-else
      ref="host"
      class="scientific-chart"
      data-testid="scientific-chart"
      role="img"
      :aria-label="ariaLabel"
    />
  </div>
</template>

<style scoped>
.scientific-chart-frame {
  display: grid;
  width: 100%;
  min-width: 0;
  min-height: 300px;
}

.scientific-chart {
  width: 100%;
  min-width: 0;
  min-height: 300px;
}

.scientific-chart-frame__empty {
  display: grid;
  min-height: 300px;
  place-items: center;
  border: 1px dashed var(--research-border-strong);
  border-radius: var(--research-radius-panel);
  background: var(--research-bg-panel);
  color: var(--research-text-secondary);
  font-size: var(--research-text-sm);
}
</style>
