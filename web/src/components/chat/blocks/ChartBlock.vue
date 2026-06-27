<script setup>
/**
 * ChartBlock.vue — 图表块（ECharts 占位）
 *
 * 接收 block.data = {type: 'line'|'bar'|'pie', title, x_data, series, options}
 *
 * 当前为简化版：折线图 + 柱状图 + 饼图三种基本图表。
 * 完整 ECharts 集成可在后续接入。
 *
 * v77 P2.5.3: ECharts theme 适配（MutationObserver 监听 <html data-theme> → 重渲）
 * ECharts 不感知 CSS theme，必须在 setOption 时注入主题色，主题切换时重渲。
 */
import { ref, onMounted, watch, onUnmounted } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart, BarChart, PieChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, BarChart, PieChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent, CanvasRenderer])

const props = defineProps({ block: { type: Object, required: true } })
const chartRef = ref(null)
const data = ref(props.block.data || {})
let chartInstance = null
let themeObserver = null

// v77 P2.6-A: ECharts theme 调色板改用 getComputedStyle 读 token（与 v77 P2.5.3 MeetingCard statusColor 同模式）
// 8 个裸 hex → 6 个 token，dark/light/accent 3 轴自动适配，6 主题一致
const getPalette = (isDark) => {
  const root = document.documentElement
  const get = (token) => getComputedStyle(root).getPropertyValue(token).trim()
  return isDark
    ? {
        text: get('--color-text-regular'),
        textDim: get('--color-text-secondary'),
        gridLine: get('--color-border-base'),
        tooltipBg: get('--color-bg-card'),
        tooltipBorder: get('--color-border-base'),
      }
    : {
        text: get('--color-text-primary'),
        textDim: get('--color-text-secondary'),
        gridLine: get('--color-border-light'),
        tooltipBg: get('--color-bg-card'),
        tooltipBorder: get('--color-border-light'),
      }
}

const isDarkTheme = () => document.documentElement.dataset.theme === 'dark'

// 注入主题色到所有 textStyle / axisLabel / tooltip
const applyTheme = (option, palette) => {
  if (option.title) option.title.textStyle = { color: palette.text }
  if (option.legend) option.legend.textStyle = { color: palette.text }
  if (option.xAxis) option.xAxis.axisLabel = { color: palette.textDim }
  if (option.yAxis) option.yAxis.axisLabel = { color: palette.textDim }
  if (option.tooltip) {
    option.tooltip.backgroundColor = palette.tooltipBg
    option.tooltip.borderColor = palette.tooltipBorder
    option.tooltip.textStyle = { color: palette.text }
  }
  return option
}

const renderChart = () => {
  if (!chartRef.value) return
  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(chartRef.value)

  const type = data.value.type || 'bar'
  const title = data.value.title || props.block.title || '数据图表'
  const xData = data.value.x_data || data.value.labels || []
  const series = data.value.series || []

  let baseOption
  if (type === 'pie') {
    baseOption = {
      title: { text: title, left: 'center' },
      tooltip: { trigger: 'item' },
      legend: { orient: 'vertical', left: 'left' },
      series: [{
        type: 'pie',
        radius: '50%',
        data: xData.map((label, i) => ({ name: label, value: series[i] || 0 })),
      }],
    }
  } else if (type === 'line') {
    baseOption = {
      title: { text: title, left: 'center' },
      tooltip: { trigger: 'axis' },
      grid: { left: 50, right: 20, top: 50, bottom: 40 },
      xAxis: { type: 'category', data: xData },
      yAxis: { type: 'value' },
      series: [{ type: 'line', data: series, smooth: true, areaStyle: {} }],
    }
  } else {
    baseOption = {
      title: { text: title, left: 'center' },
      tooltip: { trigger: 'axis' },
      grid: { left: 50, right: 20, top: 50, bottom: 40 },
      xAxis: { type: 'category', data: xData },
      yAxis: { type: 'value' },
      series: [{ type: 'bar', data: series }],
    }
  }

  chartInstance.setOption(applyTheme(baseOption, getPalette(isDarkTheme())))
}

onMounted(() => {
  renderChart()
  // v77 P2.5.3: 监听 <html data-theme> 变化 → 重渲 ECharts
  themeObserver = new MutationObserver(() => {
    if (chartInstance) renderChart()
  })
  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme'],
  })
})

onUnmounted(() => {
  if (chartInstance) chartInstance.dispose()
  if (themeObserver) themeObserver.disconnect()
})

watch(() => props.block.data, (v) => { data.value = v; renderChart() })
</script>

<template>
  <div class="chart-block rich-card">
    <div v-if="!data.x_data && !data.labels" class="empty">
      <p>📊 图表数据为空</p>
      <p class="hint">期望格式: {type, title, x_data, series}</p>
    </div>
    <div v-else ref="chartRef" class="chart-canvas"></div>
  </div>
</template>

<style scoped>
.rich-card { background: var(--color-bg-card); border: 1px solid var(--color-border-light); border-radius: 10px; padding: 12px 14px; margin: 8px 0; box-shadow: var(--shadow-xs); }
.chart-canvas { width: 100%; height: 300px; }
.empty { text-align: center; color: var(--color-text-secondary); padding: 40px 0; }
.empty p { margin: 4px 0; }
.empty .hint { font-size: 12px; color: var(--color-border-light); font-family: monospace; }
</style>
