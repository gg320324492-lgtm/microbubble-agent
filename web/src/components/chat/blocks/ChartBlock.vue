<script setup>
/**
 * ChartBlock.vue — 图表块（ECharts 占位）
 *
 * 接收 block.data = {type: 'line'|'bar'|'pie', title, x_data, series, options}
 *
 * 当前为简化版：折线图 + 柱状图 + 饼图三种基本图表。
 * 完整 ECharts 集成可在后续接入。
 */
import { ref, onMounted, watch, onUnmounted } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart, BarChart, PieChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, BarChart, PieChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent, CanvasRenderer])

const props = defineProps({ block: { type: Object, required: true } })
const chartRef = ref(null)
let chartInstance = null

const data = ref(props.block.data || {})

const renderChart = () => {
  if (!chartRef.value) return
  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(chartRef.value)

  const type = data.value.type || 'bar'
  const title = data.value.title || props.block.title || '数据图表'
  const xData = data.value.x_data || data.value.labels || []
  const series = data.value.series || []

  let option
  if (type === 'pie') {
    option = {
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
    option = {
      title: { text: title, left: 'center' },
      tooltip: { trigger: 'axis' },
      grid: { left: 50, right: 20, top: 50, bottom: 40 },
      xAxis: { type: 'category', data: xData },
      yAxis: { type: 'value' },
      series: [{ type: 'line', data: series, smooth: true, areaStyle: {} }],
    }
  } else {
    option = {
      title: { text: title, left: 'center' },
      tooltip: { trigger: 'axis' },
      grid: { left: 50, right: 20, top: 50, bottom: 40 },
      xAxis: { type: 'category', data: xData },
      yAxis: { type: 'value' },
      series: [{ type: 'bar', data: series, itemStyle: { color: 'var(--color-primary)' } }],
    }
  }
  chartInstance.setOption(option)
}

onMounted(renderChart)
onUnmounted(() => { if (chartInstance) chartInstance.dispose() })

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
.rich-card { background: var(--color-bg-card); border: 1px solid #e8eaed; border-radius: 10px; padding: 12px 14px; margin: 8px 0; box-shadow: var(--shadow-xs); }
.chart-canvas { width: 100%; height: 300px; }
.empty { text-align: center; color: var(--color-text-secondary); padding: 40px 0; }
.empty p { margin: 4px 0; }
.empty .hint { font-size: 12px; color: var(--color-border-light); font-family: monospace; }
</style>
