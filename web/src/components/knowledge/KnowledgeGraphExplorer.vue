<template>
  <!--
    KnowledgeGraphExplorer.vue
    Phase 9 batch 1 (W85 B-1) — 交互式知识图谱 Explorer
    封装 ECharts 力导向图 + 节点点击事件 + 路径高亮 + 子图钻取触发
    复用 web/src/utils/paperAdapter.js normalizeGraphData 适配多种后端格式
  -->
  <div class="kg-explorer">
    <div v-if="loading" class="kg-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>图谱加载中…</span>
    </div>
    <div v-else-if="!normalizedData.nodes.length" class="kg-empty">
      <el-empty description="暂无图谱数据，请先添加知识条目或扩大深度" />
    </div>
    <div v-else ref="chartRef" class="kg-chart"></div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { normalizeGraphData } from '@/utils/paperAdapter'

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  edges: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['node-click'])

const chartRef = ref(null)
let chartInstance = null

const normalizedData = computed(() => {
  // 兼容多种字段名（nodes/links/relations）
  return normalizeGraphData({ nodes: props.nodes, edges: props.edges })
})

const buildOption = () => {
  const { nodes, links, categories } = normalizedData.value
  // 2026-09-13 重做: 力导参数随规模自适应, 防大图 (100 节点) 挤成一团
  const n = nodes?.length || 0
  return {
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        if (params.dataType === 'node') {
          return `<b>${params.name}</b><br/>分类: ${params.data.category || '未分类'}`
        }
        if (params.dataType === 'edge') {
          return `关系: ${params.data.label || params.data.type || '关联'}`
        }
        return ''
      },
    },
    // 图例固定画布右上角横排 (旧版 vertical+middle 悬在关系线中间, 挡图)
    legend: categories?.length > 1 ? {
      data: categories.map(c => c.name),
      orient: 'horizontal',
      right: 10,
      top: 6,
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { fontSize: 10 },
    } : undefined,
    animationDurationUpdate: 600,
    animationEasingUpdate: 'cubicInOut',
    series: [{
      type: 'graph',
      layout: 'force',
      roam: true,
      draggable: true,
      // 画布内缩: 节点标签 (position:right) 不再被容器边缘裁剪
      left: 30,
      top: 40,
      right: 110,
      bottom: 30,
      force: {
        repulsion: n > 70 ? 420 : n > 40 ? 320 : 240,
        edgeLength: [60, 200],
        gravity: 0.12,
      },
      data: nodes,
      links: links,
      categories: categories,
      label: {
        show: true,
        position: 'right',
        fontSize: 10.5,
        color: '#41564f',
        formatter: '{b}',
      },
      lineStyle: {
        color: 'rgba(113, 138, 131, 0.4)',
        curveness: 0.12,
        width: 1.2,
      },
      emphasis: {
        focus: 'adjacency',
        lineStyle: { width: 2.2 },
      },
      edgeLabel: {
        fontSize: 10,
        show: false,
      },
    }],
  }
}

const renderChart = async () => {
  if (!chartRef.value) return
  await nextTick()
  // 容器尚未完成布局 (图谱 tab 未激活 / v-show 隐藏中) 时宽高为 0,
  // echarts.init 会生成 0x0 画布并刷 "Can't get DOM width or height" 警告 —
  // 跳过本次, 等 ResizeObserver / window resize 在容器有尺寸后触发
  // handleResize 补首次渲染
  if (chartRef.value.clientWidth === 0 || chartRef.value.clientHeight === 0) return
  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(chartRef.value)
  chartInstance.setOption(buildOption())

  // W86 mini-5: chartRef 在 v-if/v-else (loading / empty / chart) 之间切换时是**新 DOM 元素**,
  // onMounted 时 observe 的旧元素已卸载 → 必须重新绑定, 否则 ResizeObserver 形同失效.
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver.observe(chartRef.value)
  }

  // 节点点击事件 → emit 上抛 (KnowledgeGraphView 监听)
  chartInstance.on('click', (params) => {
    if (params.dataType === 'node') {
      emit('node-click', params.data)
    }
  })
}

const handleResize = () => {
  if (!chartInstance) {
    // 首次渲染因容器零尺寸被跳过 → 容器出现尺寸时在这里补渲染
    renderChart()
    return
  }
  chartInstance.resize()
}

// W86 mini-5 fix: 父容器高度变化 (grid/flex 重排、tab 切换) 不触发 window resize,
// ECharts canvas 会停留在初始化时的尺寸 → 图谱被裁成"小框显示不全".
// ResizeObserver 直接盯 chartRef 尺寸变化, 补上 window resize 覆盖不到的场景.
let resizeObserver = null

// 监听 nodes/edges 变化 → 重渲染
watch(() => [props.nodes, props.edges], () => {
  nextTick(() => renderChart())
}, { deep: true })

onMounted(() => {
  renderChart()
  window.addEventListener('resize', handleResize)
  // W86 mini-5: jsdom / 老浏览器无 ResizeObserver 时降级为仅 window resize
  if (typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(handleResize)
    if (chartRef.value) resizeObserver.observe(chartRef.value)
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})
</script>

<style scoped>
.kg-explorer {
  width: 100%;
  height: 100%;
  min-height: 480px;
  position: relative;
  display: flex;
  flex-direction: column;
}
.kg-chart {
  flex: 1;
  width: 100%;
  height: 100%;
  min-height: 480px;
}
.kg-loading,
.kg-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 8px;
  color: var(--color-text-secondary, #909399);
  font-size: 13px;
}
</style>