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
let themeObserver = null

// ECharts 不感知 CSS 主题, 必须用 getComputedStyle 读 CSS 变量
// (v60-v67 教训的姊妹篇, 与 v77 P2.6-A ChartBlock + P2.6-B MobileECharts 同模式)
function readRgbVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

onMounted(() => {
  nextTick(() => render())
  // 监听主题/主色切换 → 重绘 ECharts (因 ECharts option 是 static snapshot, 不会自动跟随 CSS 变量)
  themeObserver = new MutationObserver(() => {
    if (chartInstance) render()
  })
  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme', 'data-accent'],
  })
})

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
  if (themeObserver) {
    themeObserver.disconnect()
    themeObserver = null
  }
})

watch(() => props.history, () => render(), { deep: true })

function render() {
  if (!chartEl.value) return
  if (!chartInstance) {
    chartInstance = echarts.init(chartEl.value)
  }
  // v60-v67: ECharts itemStyle.color 接受 hex / rgb / rgba, 不能直接给 var() 或 '255, 122, 92' 字符串
  // 从 CSS 变量读 RGB 字符串 (variables.css --color-primary-rgb: '255, 122, 92') 后构造 hex
  const primaryRgb = readRgbVar('--color-primary-rgb') || '255, 122, 92'
  const dangerRgb = readRgbVar('--color-danger-rgb') || '245, 108, 108'
  const primaryHex = '#' + primaryRgb.split(',').map((s) => parseInt(s.trim(), 10).toString(16).padStart(2, '0')).join('')
  const dangerHex = '#' + dangerRgb.split(',').map((s) => parseInt(s.trim(), 10).toString(16).padStart(2, '0')).join('')
  const data = props.history.map((h) => [h.recorded_at, h.confidence])
  chartInstance.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'time' },
    yAxis: { type: 'value', min: 0, max: 1, name: '置信度' },
    series: [{
      type: 'line',
      data,
      smooth: true,
      lineStyle: { color: primaryHex, width: 2 },
      markLine: {
        data: [{ yAxis: 0.55, label: { formatter: '阈值 0.55' } }],
        lineStyle: { color: dangerHex, type: 'dashed' },
      },
    }],
  })
}
</script>
