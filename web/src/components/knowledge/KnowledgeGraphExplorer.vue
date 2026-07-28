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
    legend: categories?.length > 1 ? {
      data: categories.map(c => c.name),
      orient: 'vertical',
      right: 10,
      top: 'middle',
    } : undefined,
    animationDurationUpdate: 600,
    animationEasingUpdate: 'cubicInOut',
    series: [{
      type: 'graph',
      layout: 'force',
      roam: true,
      draggable: true,
      force: {
        repulsion: 200,
        edgeLength: [80, 240],
        gravity: 0.05,
      },
      data: nodes,
      links: links,
      categories: categories,
      label: {
        show: true,
        position: 'right',
        fontSize: 11,
        formatter: '{b}',
      },
      lineStyle: {
        color: '#bbb',
        curveness: 0.15,
        width: 1,
      },
      emphasis: {
        focus: 'adjacency',
        lineStyle: { width: 2 },
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
  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(chartRef.value)
  chartInstance.setOption(buildOption())

  // 节点点击事件 → emit 上抛 (KnowledgeGraphView 监听)
  chartInstance.on('click', (params) => {
    if (params.dataType === 'node') {
      emit('node-click', params.data)
    }
  })
}

const handleResize = () => {
  if (chartInstance) chartInstance.resize()
}

// 监听 nodes/edges 变化 → 重渲染
watch(() => [props.nodes, props.edges], () => {
  nextTick(() => renderChart())
}, { deep: true })

onMounted(() => {
  renderChart()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
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