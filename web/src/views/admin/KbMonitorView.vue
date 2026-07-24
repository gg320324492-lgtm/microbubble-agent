<script setup>
/**
 * KbMonitorView.vue — KB 自动入库监控 dashboard
 *
 * qa-bench v3.1 决策 D5 (Dashboard KB 监控) — W68 第 7 批 A-4 (2026-07-24)
 * 锚点范式第 78 守恒.
 *
 * 背景: plan `qa-bench-v3.1-decisions.md` D5 一直缺失核心前端, 本页补齐.
 *
 * 4 核心指标卡 + 4 ECharts 子图 + 失败/滞留列表:
 *   - 入库趋势 (逐小时 ingested/done 折线)
 *   - 失败率 (逐小时 failed/ingested 百分比折线)
 *   - 重试次数 (retrying/failed/done 柱状对比)
 *   - 队列堆积 (pending/analyzing 饼图 + eta)
 *
 * 数据源:
 *   - GET /admin/kb-monitor/overview?hours=24  → 聚合 + trend
 *   - GET /admin/kb-monitor/queue-depth        → 队列快照
 *   - GET /admin/kb-monitor/failures           → 失败列表
 *
 * 权限: admin/leader (后端 get_current_admin 兜底, 403 → 提示). write tier 30/min.
 * 主题: 全走 var(--color-*) token, dark mode 自动适配 (跟 AnalyticsView 一致).
 */
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { fetchKbOverview, fetchKbQueueDepth, fetchKbFailures } from '@/api/kbMonitor'

const hours = ref(24)
const loading = ref(false)
const overview = ref(null)
const queue = ref(null)
const failures = ref([])

// ECharts refs (4 子图)
const ingestChartRef = ref(null)
const failRateChartRef = ref(null)
const retryChartRef = ref(null)
const queueChartRef = ref(null)
let ingestChart = null
let failRateChart = null
let retryChart = null
let queueChart = null

const fmtNum = (v) => (v == null ? '-' : v.toLocaleString())
const fmtPct = (v) => (v == null ? '-' : `${(v * 100).toFixed(1)}%`)
const fmtHour = (iso) => {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit' })
  } catch { return iso }
}
const fmtTime = (iso) => {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch { return iso }
}
const statusLabel = (s) => ({
  pending: '等待中', analyzing: '分析中', done: '已完成', failed: '失败',
}[s] || s || '-')
const statusTagType = (s) => ({
  done: 'success', failed: 'danger', analyzing: 'warning', pending: 'info',
}[s] || 'info')

const loadAll = async () => {
  loading.value = true
  try {
    const [ov, q, f] = await Promise.all([
      fetchKbOverview(hours.value),
      fetchKbQueueDepth(),
      fetchKbFailures(50, true),
    ])
    overview.value = ov
    queue.value = q
    failures.value = f.items || []
    await nextTick()
    renderIngestChart()
    renderFailRateChart()
    renderRetryChart()
    renderQueueChart()
  } catch (e) {
    if (e.response?.status === 403) {
      ElMessage.error('需要管理员权限')
    } else {
      ElMessage.error(e.response?.data?.detail || e.response?.data?.error?.message || '加载失败')
    }
  } finally {
    loading.value = false
  }
}

// 复用 AnalyticsView v31.1 fix: init 时显式传 width/height, 避免 hidden 容器 canvas 默认 100x150
const initChart = (refEl) => {
  if (!refEl) return null
  const w = refEl.clientWidth || refEl.getBoundingClientRect().width || 534
  const h = refEl.clientHeight || refEl.getBoundingClientRect().height || 260
  return echarts.init(refEl, null, { width: w, height: h })
}

const renderIngestChart = () => {
  if (!ingestChartRef.value || !overview.value) return
  ingestChart = ingestChart || initChart(ingestChartRef.value)
  const trend = overview.value.trend || []
  ingestChart.setOption({
    grid: { left: 50, right: 30, top: 40, bottom: 30 },
    tooltip: { trigger: 'axis' },
    legend: { top: 5, data: ['入库数', '成功数'] },
    xAxis: { type: 'category', data: trend.map(t => fmtHour(t.hour)), axisLabel: { rotate: 30, fontSize: 10 } },
    yAxis: { type: 'value', name: '条数' },
    series: [
      {
        name: '入库数', type: 'line', smooth: true,
        data: trend.map(t => t.ingested),
        itemStyle: { color: '#409EFF' },
        areaStyle: { color: 'rgba(64,158,255,0.1)' },
        symbol: 'circle', symbolSize: 7, showSymbol: true,
      },
      {
        name: '成功数', type: 'line', smooth: true,
        data: trend.map(t => t.done),
        itemStyle: { color: '#67C23A' },
        symbol: 'circle', symbolSize: 7, showSymbol: true,
      },
    ],
  })
}

const renderFailRateChart = () => {
  if (!failRateChartRef.value || !overview.value) return
  failRateChart = failRateChart || initChart(failRateChartRef.value)
  const trend = overview.value.trend || []
  failRateChart.setOption({
    grid: { left: 50, right: 30, top: 40, bottom: 30 },
    tooltip: { trigger: 'axis', formatter: (ps) => ps.map(p => `${p.seriesName}: ${p.value}%`).join('<br/>') },
    legend: { top: 5, data: ['失败率'] },
    xAxis: { type: 'category', data: trend.map(t => fmtHour(t.hour)), axisLabel: { rotate: 30, fontSize: 10 } },
    yAxis: { type: 'value', name: '失败率 %', min: 0, axisLabel: { formatter: '{value}%' } },
    series: [
      {
        name: '失败率', type: 'line', smooth: true,
        data: trend.map(t => (t.ingested > 0 ? +((t.failed / t.ingested) * 100).toFixed(1) : 0)),
        itemStyle: { color: '#F56C6C' },
        lineStyle: { type: 'dashed' },
        areaStyle: { color: 'rgba(245,108,108,0.08)' },
        symbol: 'circle', symbolSize: 7, showSymbol: true,
      },
    ],
  })
}

const renderRetryChart = () => {
  if (!retryChartRef.value || !overview.value) return
  retryChart = retryChart || initChart(retryChartRef.value)
  const ov = overview.value
  retryChart.setOption({
    grid: { left: 50, right: 30, top: 30, bottom: 40 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: ['成功', '失败', '重试/滞留'] },
    yAxis: { type: 'value', name: '条数' },
    series: [
      {
        name: '数量', type: 'bar', barWidth: '50%',
        data: [
          { value: ov.done, itemStyle: { color: '#67C23A' } },
          { value: ov.failed, itemStyle: { color: '#F56C6C' } },
          { value: ov.retrying, itemStyle: { color: '#E6A23C' } },
        ],
        label: { show: true, position: 'top' },
      },
    ],
  })
}

const renderQueueChart = () => {
  if (!queueChartRef.value || !queue.value) return
  queueChart = queueChart || initChart(queueChartRef.value)
  const q = queue.value
  const data = [
    { name: '等待中', value: q.pending, itemStyle: { color: '#909399' } },
    { name: '分析中', value: q.analyzing, itemStyle: { color: '#E6A23C' } },
  ].filter(d => d.value > 0)
  queueChart.setOption({
    tooltip: { trigger: 'item', formatter: (p) => `${p.name}<br/>${p.value} 条 (${(p.percent || 0).toFixed(1)}%)` },
    legend: { bottom: 5, textStyle: { fontSize: 11 } },
    series: [
      {
        type: 'pie', radius: ['30%', '55%'], center: ['50%', '45%'],
        data: data.length ? data : [{ name: '队列为空', value: 1, itemStyle: { color: '#67C23A' } }],
        label: { formatter: '{b}\n{c}', fontSize: 11 },
      },
    ],
  })
}

const handleResize = () => {
  ingestChart?.resize()
  failRateChart?.resize()
  retryChart?.resize()
  queueChart?.resize()
}

onMounted(() => {
  loadAll()
  window.addEventListener('resize', handleResize)
  nextTick(() => handleResize())
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  ingestChart?.dispose()
  failRateChart?.dispose()
  retryChart?.dispose()
  queueChart?.dispose()
  ingestChart = failRateChart = retryChart = queueChart = null
})
</script>

<template>
  <div class="kb-monitor-view" v-loading="loading">
    <div class="page-header">
      <h2>📥 KB 自动入库监控</h2>
      <p class="desc">知识库后台自动分析入库的健康度：入库趋势 / 失败率 / 重试 / 队列堆积（qa-bench v3.1 D5）</p>
    </div>

    <!-- 时间窗口 + 刷新 -->
    <el-card class="filter-card" shadow="never">
      <el-radio-group v-model="hours" @change="loadAll" size="default">
        <el-radio-button :value="6">最近 6 小时</el-radio-button>
        <el-radio-button :value="24">最近 24 小时</el-radio-button>
        <el-radio-button :value="72">最近 3 天</el-radio-button>
        <el-radio-button :value="168">最近 7 天</el-radio-button>
      </el-radio-group>
      <el-button style="margin-left:16px" :icon="Refresh" @click="loadAll" :loading="loading">刷新</el-button>
      <span v-if="queue" class="meta">
        当前队列深度: <strong :class="{ warn: queue.queue_depth > 50 }">{{ queue.queue_depth }}</strong>
        · 预计清空: <strong>{{ queue.eta_minutes }}</strong> 分钟
        · 轮询间隔: {{ (queue.polling_interval_sec / 60).toFixed(0) }} 分钟
      </span>
    </el-card>

    <!-- 4 核心指标卡 -->
    <div v-if="overview" class="metric-row">
      <el-card class="metric-card" shadow="hover">
        <div class="metric-label">窗口内入库数</div>
        <div class="metric-value">{{ fmtNum(overview.ingested) }}</div>
      </el-card>
      <el-card class="metric-card" shadow="hover">
        <div class="metric-label">成功率</div>
        <div class="metric-value" :class="{ good: overview.success_rate >= 0.9, warn: overview.success_rate != null && overview.success_rate < 0.7 }">
          {{ fmtPct(overview.success_rate) }}
        </div>
        <div class="metric-hint">≥90% 良好 · &lt;70% 需关注</div>
      </el-card>
      <el-card class="metric-card" shadow="hover">
        <div class="metric-label">失败数</div>
        <div class="metric-value" :class="{ danger: overview.failed > 0 }">{{ fmtNum(overview.failed) }}</div>
      </el-card>
      <el-card class="metric-card" shadow="hover">
        <div class="metric-label">重试 / 滞留</div>
        <div class="metric-value" :class="{ warn: overview.retrying > 0 }">{{ fmtNum(overview.retrying) }}</div>
        <div class="metric-hint">超 3 轮仍 pending</div>
      </el-card>
    </div>

    <!-- 4 ECharts 子图 -->
    <div v-if="overview" class="chart-row">
      <el-card class="chart-card" shadow="never">
        <template #header><div class="chart-title">📈 入库趋势（逐小时）</div></template>
        <div ref="ingestChartRef" class="chart-canvas" />
      </el-card>
      <el-card class="chart-card" shadow="never">
        <template #header><div class="chart-title">📉 失败率（逐小时）</div></template>
        <div ref="failRateChartRef" class="chart-canvas" />
      </el-card>
    </div>
    <div v-if="overview" class="chart-row">
      <el-card class="chart-card" shadow="never">
        <template #header><div class="chart-title">🔁 成功 / 失败 / 重试 对比</div></template>
        <div ref="retryChartRef" class="chart-canvas" />
      </el-card>
      <el-card class="chart-card" shadow="never">
        <template #header><div class="chart-title">🧱 队列堆积</div></template>
        <div ref="queueChartRef" class="chart-canvas" />
      </el-card>
    </div>

    <!-- 失败 / 滞留列表 -->
    <el-card class="logs-card" shadow="never">
      <template #header>
        <div class="chart-title">⚠️ 失败 / 滞留列表（{{ failures.length }} 条）</div>
      </template>
      <el-table :data="failures" stripe size="default" max-height="500">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="标题" min-width="240" show-overflow-tooltip />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.analysis_status)" size="small">
              {{ statusLabel(row.analysis_status) }}
            </el-tag>
            <el-tag v-if="row.is_stuck" type="warning" size="small" style="margin-left:4px">滞留</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="质量分" width="100" align="center">
          <template #default="{ row }">
            <span v-if="row.quality_score != null">{{ row.quality_score.toFixed(2) }}</span>
            <span v-else style="color:var(--color-text-placeholder)">—</span>
          </template>
        </el-table-column>
        <el-table-column label="入库时间" width="150">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && failures.length === 0" description="暂无失败或滞留条目 🎉" />
    </el-card>
  </div>
</template>

<style scoped>
.kb-monitor-view {
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
  color: var(--color-info);
  font-size: 13px;
}
.filter-card {
  margin-bottom: 16px;
}
.filter-card .meta {
  margin-left: 16px;
  color: var(--color-text-regular);
  font-size: 13px;
}
.filter-card .meta .warn {
  color: var(--color-warning);
}
.metric-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
.metric-card {
  text-align: center;
  padding: 4px 0;
}
.metric-label {
  font-size: 12px;
  color: var(--color-info);
  margin-bottom: 6px;
}
.metric-value {
  font-size: 26px;
  font-weight: 600;
  color: var(--color-text-primary);
}
.metric-value.good { color: var(--color-success); }
.metric-value.warn { color: var(--color-warning); }
.metric-value.danger { color: var(--color-danger); }
.metric-hint {
  font-size: 11px;
  color: var(--color-text-placeholder);
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
  color: var(--color-text-primary);
}
.chart-canvas {
  width: 100%;
  height: 260px;
}
.logs-card {
  margin-bottom: 16px;
}
</style>
