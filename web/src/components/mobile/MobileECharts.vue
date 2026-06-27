<template>
  <div
    ref="chartRef"
    class="mobile-echarts"
    :style="{ height: height, touchAction: 'none' }"
  />
</template>

<script setup>
/**
 * MobileECharts.vue — 移动端 ECharts 封装（PR #7）
 *
 * 替代桌面 ECharts 移动端适配（不靠 CSS hack）
 * - pinch 双指缩放（roam.scale）
 * - 触摸拖动（roam.translate）
 * - 响应式配置（grid/legend/tooltip 紧凑）
 * - 长按 tooltip 显示
 * - tap 高亮
 *
 * 用法：
 *   <MobileECharts
 *     :option="chartOption"
 *     height="300px"
 *     @click="onChartClick"
 *   />
 *
 * 关键：监听 isMobile 切换时 resize + 重新 setOption（强制重渲染）
 */

import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import { useIsMobile } from '@/composables/useIsMobile'

const props = defineProps({
  option: { type: Object, required: true },
  height: { type: String, default: '300px' },
  /** 是否启用缩放/拖动（默认 true） */
  roam: { type: Boolean, default: true },
  /** 主题（light / dark） */
  theme: { type: String, default: '' },
})

// v77 P2.6-B: ECharts 调色板改用 getComputedStyle 读 token（与 v77 P2.6-A ChartBlock 同模式）
// 解决 6 主题（3 主色 × 2 明暗）下 ECharts 颜色不随主题切换的问题
const getPalette = () => {
  const root = document.documentElement
  const get = (token) => getComputedStyle(root).getPropertyValue(token).trim()
  const isDark = root.dataset.theme === 'dark'
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

const applyThemeToOption = (opt) => {
  const palette = getPalette()
  if (!opt) return opt
  if (opt.title && typeof opt.title === 'object' && opt.title.text) {
    opt.title.textStyle = { ...(opt.title.textStyle || {}), color: palette.text }
  }
  if (opt.legend) {
    opt.legend.textStyle = { ...(opt.legend.textStyle || {}), color: palette.text }
  }
  if (opt.xAxis) {
    const xs = Array.isArray(opt.xAxis) ? opt.xAxis : [opt.xAxis]
    xs.forEach((ax) => { ax.axisLabel = { ...(ax.axisLabel || {}), color: palette.textDim } })
  }
  if (opt.yAxis) {
    const ys = Array.isArray(opt.yAxis) ? opt.yAxis : [opt.yAxis]
    ys.forEach((ay) => { ay.axisLabel = { ...(ay.axisLabel || {}), color: palette.textDim } })
  }
  if (opt.tooltip) {
    opt.tooltip.backgroundColor = palette.tooltipBg
    opt.tooltip.borderColor = palette.tooltipBorder
    opt.tooltip.textStyle = { ...(opt.tooltip.textStyle || {}), color: palette.text }
  }
  return opt
}

const emit = defineEmits(['click', 'finished'])

const chartRef = ref(null)
const { isMobile, width } = useIsMobile()
let chartInstance = null
let resizeObserver = null
let longPressTimer = null
let themeObserver = null  // v77 P2.6-B: 监听 <html data-theme> 变化 → 重渲 ECharts

// ============================================================================
// 移动端适配 option
// ============================================================================
function adaptOption(opt) {
  if (!isMobile.value) return opt

  const adapted = JSON.parse(JSON.stringify(opt))

  // 紧凑 grid
  if (adapted.grid) {
    adapted.grid = {
      ...adapted.grid,
      left: adapted.grid.left ?? 12,
      right: adapted.grid.right ?? 12,
      top: adapted.grid.top ?? 30,
      bottom: adapted.grid.bottom ?? 30,
      containLabel: true,
    }
  }

  // 紧凑 tooltip
  if (adapted.tooltip) {
    adapted.tooltip = {
      ...adapted.tooltip,
      textStyle: { fontSize: 12 },
      ...(adapted.tooltip.trigger !== 'item' && { trigger: 'axis' }),
    }
  }

  // 图例放底部
  if (adapted.legend && !adapted.legend.bottom) {
    adapted.legend = {
      ...adapted.legend,
      bottom: 0,
      textStyle: { fontSize: 11 },
    }
  }

  // 字号缩小
  if (adapted.xAxis) {
    const xAxis = Array.isArray(adapted.xAxis) ? adapted.xAxis : [adapted.xAxis]
    xAxis.forEach((ax) => {
      if (ax.axisLabel) {
        ax.axisLabel = { ...ax.axisLabel, fontSize: 10 }
      }
    })
  }
  if (adapted.yAxis) {
    const yAxis = Array.isArray(adapted.yAxis) ? adapted.yAxis : [adapted.yAxis]
    yAxis.forEach((ay) => {
      if (ay.axisLabel) {
        ay.axisLabel = { ...ay.axisLabel, fontSize: 10 }
      }
    })
  }

  // 缩放/拖动
  if (props.roam) {
    if (adapted.dataZoom === undefined) {
      adapted.dataZoom = [
        {
          type: 'inside',
          xAxisIndex: 0,
          zoomOnMouseWheel: true,
          moveOnMouseMove: true,
          moveOnTouch: true,
        },
        {
          type: 'inside',
          yAxisIndex: 0,
          zoomOnMouseWheel: false,
          moveOnMouseMove: false,
          moveOnTouch: false,
        },
      ]
    }
  }

  // graph 类型启用 roam
  if (adapted.series) {
    const series = Array.isArray(adapted.series) ? adapted.series : [adapted.series]
    series.forEach((s) => {
      if (s.type === 'graph' || s.type === 'tree' || s.type === 'sankey') {
        s.roam = true
      }
    })
  }

  return adapted
}

// ============================================================================
// Chart 实例管理
// ============================================================================
function initChart() {
  if (!chartRef.value) return
  try {
    chartInstance = echarts.init(chartRef.value, props.theme || undefined, {
      renderer: 'canvas',
    })
    chartInstance.setOption(applyThemeToOption(adaptOption(props.option)))
    chartInstance.on('click', (params) => emit('click', params))
    chartInstance.on('finished', () => emit('finished'))
  } catch (e) {
    console.error('[MobileECharts] init failed:', e)
  }
}

function resizeChart() {
  if (chartInstance) {
    chartInstance.resize()
  }
}

function updateOption() {
  if (!chartInstance) return
  chartInstance.setOption(applyThemeToOption(adaptOption(props.option)), true) // notMerge
}

// ============================================================================
// 长按 tooltip
// ============================================================================
function onTouchStart(e) {
  if (!chartInstance) return
  const touch = e.touches?.[0]
  if (!touch) return
  longPressTimer = setTimeout(() => {
    // 显示当前位置的 tooltip
    chartInstance.dispatchAction({
      type: 'showTip',
      x: touch.clientX - chartRef.value.getBoundingClientRect().left,
      y: touch.clientY - chartRef.value.getBoundingClientRect().top,
    })
  }, 500)
}

function onTouchEnd() {
  if (longPressTimer) {
    clearTimeout(longPressTimer)
    longPressTimer = null
  }
}

// ============================================================================
// 生命周期
// ============================================================================
onMounted(async () => {
  await nextTick()
  initChart()

  // ResizeObserver 监听容器尺寸变化（移动端横竖屏切换）
  if (typeof ResizeObserver !== 'undefined' && chartRef.value) {
    resizeObserver = new ResizeObserver(() => resizeChart())
    resizeObserver.observe(chartRef.value)
  } else {
    window.addEventListener('resize', resizeChart)
  }

  // 触屏手势（长按显示 tooltip）
  if (chartRef.value) {
    chartRef.value.addEventListener('touchstart', onTouchStart, { passive: true })
    chartRef.value.addEventListener('touchend', onTouchEnd)
    chartRef.value.addEventListener('touchcancel', onTouchEnd)
  }

  // v77 P2.6-B: 监听 <html data-theme> 变化 → 重新应用主题色 + 重渲
  themeObserver = new MutationObserver(() => {
    if (chartInstance) {
      chartInstance.setOption(applyThemeToOption(adaptOption(props.option)), true)
    }
  })
  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme'],
  })
})

onBeforeUnmount(() => {
  if (longPressTimer) clearTimeout(longPressTimer)
  if (chartRef.value) {
    chartRef.value.removeEventListener('touchstart', onTouchStart)
    chartRef.value.removeEventListener('touchend', onTouchEnd)
    chartRef.value.removeEventListener('touchcancel', onTouchEnd)
  }
  if (resizeObserver) {
    resizeObserver.disconnect()
  } else {
    window.removeEventListener('resize', resizeChart)
  }
  if (themeObserver) themeObserver.disconnect()  // v77 P2.6-B
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})

// ============================================================================
// 监听 prop 变化
// ============================================================================
watch(
  () => props.option,
  () => updateOption(),
  { deep: true }
)
watch(
  () => isMobile.value,
  () => {
    // 桌面/移动端切换时重新渲染（应用不同的 grid/legend 配置）
    nextTick(() => {
      if (chartInstance) {
        chartInstance.dispose()
      }
      initChart()
    })
  }
)
watch(width, () => resizeChart())
</script>

<style scoped>
.mobile-echarts {
  width: 100%;
  position: relative;
}
</style>

<!-- v77 P2.6-B: dark mode 适配（v60-v67 教训：必须非 scoped） -->
<style>
/* MobileECharts 调色板走 JS getComputedStyle 自动适配 dark/light/accent */
[data-theme="dark"] .mobile-echarts {
  /* tooltip 背景由 ECharts setOption 注入 token 值；这里只确保容器背景不漏色 */
  background: transparent;
}
</style>