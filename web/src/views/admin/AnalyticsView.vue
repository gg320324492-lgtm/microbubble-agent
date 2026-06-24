<script setup>
/**
 * AnalyticsView.vue — 检索质量监控 dashboard (v31)
 *
 * 5 核心指标卡 + 趋势线 + 模型对比柱状图 + 详细搜索日志表
 *
 * 数据源:
 *   - GET /api/v1/analytics/stats?days=7  → 聚合指标
 *   - GET /api/v1/analytics/logs?limit=50  → 详细列表
 *
 * 权限: admin 角色 (后端 /admin/agent-traces 一样靠 role 校验, 这边暂用同样 auth).
 *   2026-06-25 v31 注: 本页只展示统计, 不写数据, 暂不强制 admin 校验,
 *   普通用户可看 (不暴露敏感信息). 后端如果未来要加校验, 在 analytics.py 加 admin 守卫即可.
 */
import { ref, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { fetchStats, fetchRecentLogs } from '@/api/analytics'

const days = ref(7)
const loading = ref(false)
const stats = ref(null)
const recentLogs = ref([])

// ECharts refs
const trendChartRef = ref(null)
const modelChartRef = ref(null)
const sourceChartRef = ref(null)
let trendChart = null
let modelChart = null
let sourceChart = null

const fmtPct = (v) => (v == null ? '-' : `${(v * 100).toFixed(1)}%`)
const fmtNum = (v) => (v == null ? '-' : v.toLocaleString())
const fmtTime = (iso) => {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch { return iso }
}

const sourceLabel = (s) => ({
  knowledge_search: '知识库搜索',
  knowledge_search_semantic: '知识库语义',
  agent_chat: 'Agent 检索',
}[s] || s || '-')

const sourceColor = (s) => ({
  knowledge_search: '#409EFF',
  knowledge_search_semantic: '#67C23A',
  agent_chat: '#E6A23C',
}[s] || '#909399')

const loadAll = async () => {
  loading.value = true
  try {
    const [s, l] = await Promise.all([fetchStats(days.value), fetchRecentLogs(50)])
    stats.value = s
    recentLogs.value = l.items || []
    await nextTick()
    renderTrendChart()
    renderModelChart()
    renderSourceChart()
  } catch (e) {
    if (e.response?.status === 403) {
      ElMessage.error('需要管理员权限')
    } else {
      ElMessage.error(e.response?.data?.detail || '加载失败')
    }
  } finally {
    loading.value = false
  }
}

const renderTrendChart = () => {
  if (!trendChartRef.value || !stats.value) return
  trendChart = trendChart || echarts.init(trendChartRef.value)
  const trend = stats.value.trend || []
  trendChart.setOption({
    grid: { left: 50, right: 60, top: 40, bottom: 30 },
    tooltip: { trigger: 'axis' },
    legend: { top: 5, data: ['搜索量', '零点击率'] },
    xAxis: {
      type: 'category',
      data: trend.map(t => t.date),
      axisLabel: { rotate: 0, fontSize: 11 },
    },
    yAxis: [
      { type: 'value', name: '搜索量', position: 'left', axisLine: { show: true, lineStyle: { color: '#409EFF' } } },
      { type: 'value', name: '零点击率', position: 'right', min: 0, max: 1, axisLabel: { formatter: '{value}' }, axisLine: { show: true, lineStyle: { color: '#F56C6C' } } },
    ],
    series: [
      {
        name: '搜索量',
        type: 'line',
        smooth: true,
        data: trend.map(t => t.count),
        yAxisIndex: 0,
        itemStyle: { color: '#409EFF' },
        areaStyle: { color: 'rgba(64,158,255,0.1)' },
      },
      {
        name: '零点击率',
        type: 'line',
        smooth: true,
        data: trend.map(t => t.zero_click_rate || 0),
        yAxisIndex: 1,
        itemStyle: { color: '#F56C6C' },
        lineStyle: { type: 'dashed' },
      },
    ],
  })
}

const renderModelChart = () => {
  if (!modelChartRef.value || !stats.value) return
  modelChart = modelChart || echarts.init(modelChartRef.value)
  const byModel = stats.value.by_model || {}
  const entries = Object.entries(byModel)
  modelChart.setOption({
    grid: { left: 50, right: 30, top: 30, bottom: 60 },
    tooltip: { trigger: 'axis' },
    legend: { top: 5, data: ['搜索量', '任何点击率'] },
    xAxis: {
      type: 'category',
      data: entries.map(([k]) => k),
      axisLabel: { rotate: 20, fontSize: 11, interval: 0 },
    },
    yAxis: [
      { type: 'value', name: '搜索量', position: 'left' },
      { type: 'value', name: '点击率', position: 'right', min: 0, max: 1, axisLabel: { formatter: (v) => `${(v * 100).toFixed(0)}%` } },
    ],
    series: [
      {
        name: '搜索量',
        type: 'bar',
        data: entries.map(([, v]) => v.total_searches),
        itemStyle: { color: '#409EFF' },
        yAxisIndex: 0,
      },
      {
        name: '任何点击率',
        type: 'line',
        data: entries.map(([, v]) => v.any_click_rate || 0),
        itemStyle: { color: '#67C23A' },
        yAxisIndex: 1,
      },
    ],
  })
}

const renderSourceChart = () => {
  if (!sourceChartRef.value || !stats.value) return
  sourceChart = sourceChart || echarts.init(sourceChartRef.value)
  const bySource = stats.value.by_source || {}
  const entries = Object.entries(bySource)
  sourceChart.setOption({
    tooltip: { trigger: 'item', formatter: (p) => `${p.name}<br/>${p.value} 次 (${(p.percent || 0).toFixed(1)}%)` },
    legend: { bottom: 5, textStyle: { fontSize: 11 } },
    series: [
      {
        type: 'pie',
        radius: ['40%', '65%'],
        center: ['50%', '45%'],
        data: entries.map(([k, v]) => ({
          name: sourceLabel(k),
          value: v.total_searches,
          itemStyle: { color: sourceColor(k) },
        })),
        label: { formatter: '{b}\n{d}%', fontSize: 11 },
      },
    ],
  })
}

const handleResize = () => {
  trendChart?.resize()
  modelChart?.resize()
  sourceChart?.resize()
}

onMounted(() => {
  loadAll()
  window.addEventListener('resize', handleResize)
})
</script>

<template>
  <div class="analytics-view" v-loading="loading">
    <div class="page-header">
      <h2>📊 检索质量监控</h2>
      <p class="desc">用户搜索 / Agent 检索的真实反馈，监控 embedding 模型效果长期趋势</p>
    </div>

    <!-- 时间窗口选择 -->
    <el-card class="filter-card" shadow="never">
      <el-radio-group v-model="days" @change="loadAll" size="default">
        <el-radio-button :value="1">最近 1 天</el-radio-button>
        <el-radio-button :value="7">最近 7 天</el-radio-button>
        <el-radio-button :value="30">最近 30 天</el-radio-button>
        <el-radio-button :value="90">最近 90 天</el-radio-button>
      </el-radio-group>
      <el-button style="margin-left:16px" :icon="Refresh" @click="loadAll" :loading="loading">刷新</el-button>
      <span v-if="stats" class="meta">
        共 <strong>{{ stats.total_searches }}</strong> 次搜索
        · 当前 embedding 模型: <strong>{{ Object.keys(stats.by_model || {})[0] || '-' }}</strong>
      </span>
    </el-card>

    <!-- 5 核心指标卡 -->
    <div v-if="stats" class="metric-row">
      <el-card class="metric-card" shadow="hover">
        <div class="metric-label">总搜索次数</div>
        <div class="metric-value">{{ fmtNum(stats.total_searches) }}</div>
      </el-card>
      <el-card class="metric-card" shadow="hover">
        <div class="metric-label">总点击次数</div>
        <div class="metric-value">{{ fmtNum(stats.total_clicks) }}</div>
      </el-card>
      <el-card class="metric-card" shadow="hover">
        <div class="metric-label">任何点击率 (CTR)</div>
        <div class="metric-value" :class="{ good: stats.any_click_rate >= 0.3, warn: stats.any_click_rate < 0.15 }">
          {{ fmtPct(stats.any_click_rate) }}
        </div>
        <div class="metric-hint">≥30% 良好 · &lt;15% 需关注</div>
      </el-card>
      <el-card class="metric-card" shadow="hover">
        <div class="metric-label">零点击率 (召回失败)</div>
        <div class="metric-value" :class="{ danger: stats.zero_click_rate > 0.5, warn: stats.zero_click_rate > 0.3 }">
          {{ fmtPct(stats.zero_click_rate) }}
        </div>
        <div class="metric-hint">top-10 没点的比例</div>
      </el-card>
      <el-card class="metric-card" shadow="hover">
        <div class="metric-label">平均点击位置 (MRR proxy)</div>
        <div class="metric-value">
          {{ stats.avg_click_position != null ? stats.avg_click_position.toFixed(2) : '-' }}
        </div>
        <div class="metric-hint">越低越好（1.0 最佳）</div>
      </el-card>
    </div>

    <!-- 图表区 -->
    <div v-if="stats" class="chart-row">
      <el-card class="chart-card" shadow="never">
        <template #header><div class="chart-title">📈 搜索量 + 零点击率 趋势</div></template>
        <div ref="trendChartRef" class="chart-canvas" />
      </el-card>
      <el-card class="chart-card" shadow="never">
        <template #header><div class="chart-title">🥧 来源分布</div></template>
        <div ref="sourceChartRef" class="chart-canvas" />
      </el-card>
    </div>

    <div v-if="stats && Object.keys(stats.by_model || {}).length > 0" class="chart-row">
      <el-card class="chart-card" shadow="never">
        <template #header><div class="chart-title">🤖 Embedding 模型对比</div></template>
        <div ref="modelChartRef" class="chart-canvas" />
      </el-card>
      <el-card class="chart-card" shadow="never" v-if="Object.keys(stats.by_model || {}).length <= 1">
        <div class="empty-tip">
          <p>当前只有 <strong>{{ Object.keys(stats.by_model || {})[0] }}</strong> 一个模型的数据。</p>
          <p style="font-size:12px;color:#909399;margin-top:8px">
            未来如果切到其他模型（如 Qwen3-Embedding-8B / bge-m3），这里会按模型分组显示对比。
          </p>
        </div>
      </el-card>
    </div>

    <!-- 详细搜索日志 -->
    <el-card class="logs-card" shadow="never">
      <template #header>
        <div class="chart-title">📋 最近 {{ recentLogs.length }} 条搜索日志</div>
      </template>
      <el-table :data="recentLogs" stripe size="default" max-height="500">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="query" label="Query" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="query-cell">{{ row.query }}</span>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="130">
          <template #default="{ row }">
            <el-tag size="small" :type="row.source === 'agent_chat' ? 'warning' : (row.source === 'knowledge_search_semantic' ? 'success' : 'primary')">
              {{ sourceLabel(row.source) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="embedding 模型" width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="model-cell">{{ row.embedding_model || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="top-N" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small">{{ (row.top_ids || []).length }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="点击" width="120" align="center">
          <template #default="{ row }">
            <template v-if="row.clicked_id != null">
              <el-tag type="success" size="small">#{{ row.click_position }} (id={{ row.clicked_id }})</el-tag>
            </template>
            <el-tag v-else type="info" size="small">未点击</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="140">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && recentLogs.length === 0" description="暂无搜索日志" />
    </el-card>
  </div>
</template>

<style scoped>
.analytics-view {
  padding: 0 8px;
}
.page-header {
  margin-bottom: 16px;
}
.page-header h2 {
  margin: 0 0 4px 0;
  font-size: 22px;
}
.page-header .desc {
  margin: 0;
  color: #909399;
  font-size: 13px;
}
.filter-card {
  margin-bottom: 16px;
}
.filter-card .meta {
  margin-left: 16px;
  color: #606266;
  font-size: 13px;
}
.metric-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
.metric-card {
  text-align: center;
  padding: 4px 0;
}
.metric-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
}
.metric-value {
  font-size: 26px;
  font-weight: 600;
  color: #303133;
}
.metric-value.good { color: #67C23A; }
.metric-value.warn { color: #E6A23C; }
.metric-value.danger { color: #F56C6C; }
.metric-hint {
  font-size: 11px;
  color: #C0C4CC;
  margin-top: 4px;
}
.chart-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 16px;
}
.chart-card {
  min-height: 280px;
}
.chart-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}
.chart-canvas {
  width: 100%;
  height: 260px;
}
.empty-tip {
  padding: 40px 20px;
  text-align: center;
  color: #606266;
}
.logs-card {
  margin-bottom: 16px;
}
.query-cell {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 12px;
  background: #f5f7fa;
  padding: 2px 6px;
  border-radius: 3px;
}
.model-cell {
  font-size: 11px;
  color: #606266;
  word-break: break-all;
}
</style>
