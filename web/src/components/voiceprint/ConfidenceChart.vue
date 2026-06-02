<template>
  <div ref="chartEl" class="confidence-chart" style="height: 200px;"></div>
</template>

<script setup>
import { ref, onMounted, watch, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  history: { type: Array, default: () => [] },
})

const chartEl = ref(null)
let chartInstance = null

onMounted(() => {
  nextTick(() => render())
})

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})

watch(() => props.history, () => render(), { deep: true })

function render() {
  if (!chartEl.value) return
  if (!chartInstance) {
    chartInstance = echarts.init(chartEl.value)
  }
  const data = props.history.map((h) => [h.recorded_at, h.confidence])
  chartInstance.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'time' },
    yAxis: { type: 'value', min: 0, max: 1, name: '置信度' },
    series: [{
      type: 'line',
      data,
      smooth: true,
      lineStyle: { color: '#ff7a5c', width: 2 },
      markLine: {
        data: [{ yAxis: 0.55, label: { formatter: '阈值 0.55' } }],
        lineStyle: { color: '#f56c6c', type: 'dashed' },
      },
    }],
  })
}
</script>
