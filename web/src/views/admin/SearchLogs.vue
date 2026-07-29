<script setup>
/**
 * SearchLogs.vue — RAG PR6 (W92) 检索日志 7 维管理页
 *
 * 路由: /admin/search-logs (admin | leader, 后端 get_current_admin_user 兜底)
 * 数据: useSearchLogs composable → /api/v1/admin/search-logs (+ /summary)
 *
 * 7 维 (量化门禁 a): 时间 / 查询 / 候选数 / 命中 / 点击 / 耗时 / user
 *
 * ⚠️ "耗时" 列语义 = 点击决策耗时 (updated_at - created_at), **非检索耗时**。
 *    search_logs 无检索耗时列, PR6 非 alembic 例外 PR 不得加。真检索耗时留 PR7。
 *    表头带 tooltip 明示, 禁止误标。
 *
 * 与既有 AnalyticsView.vue 的分工:
 *   AnalyticsView = 聚合看板 (ECharts 趋势/模型对比), 本页 = 逐行日志 + 筛选 + 门禁。
 *   两者共用后端 search_logs 表, 互不改动对方代码。
 */
import { onMounted } from 'vue'
import { Refresh, Search } from '@element-plus/icons-vue'
import {
  useSearchLogs,
  GATE_DIMENSIONS,
  RECALL_RATE_TARGET,
  SLOW_QUERY_RATE_TARGET,
} from '@/composables/useSearchLogs'

const {
  rows,
  summary,
  total,
  limit,
  loading,
  error,
  filters,
  currentPage,
  hasAllDimensions,
  recallGatePass,
  slowGatePass,
  slowGateEvaluable,
  refresh,
  applyFilters,
  goToPage,
  setPageSize,
  resetFilters,
} = useSearchLogs()

const fmtPct = (v) => (v == null ? '-' : `${(v * 100).toFixed(1)}%`)
const fmtNum = (v) => (v == null ? '-' : v.toLocaleString())
const fmtMs = (v) => (v == null ? '-' : `${v.toLocaleString()} ms`)
const fmtTime = (iso) => {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return iso
  }
}

const sourceLabel = (s) =>
  ({
    knowledge_search: '知识库搜索',
    knowledge_search_semantic: '知识库语义',
    agent_chat: 'Agent 检索',
    mobile: '移动端',
  }[s] || s || '-')

const onSearch = () => applyFilters({})
const onReset = async () => {
  resetFilters()
  await refresh()
}

onMounted(refresh)
</script>

<template>
  <div class="search-logs-view">
    <div class="page-header">
      <div>
        <h2 class="page-title">检索日志</h2>
        <p class="page-desc">
          逐行检索埋点 · {{ GATE_DIMENSIONS.length }} 维
          <el-tag v-if="hasAllDimensions" type="success" size="small" effect="plain">
            维度齐备
          </el-tag>
          <el-tag v-else type="danger" size="small" effect="plain">维度缺失</el-tag>
        </p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="refresh">刷新</el-button>
    </div>

    <el-alert
      v-if="error"
      :title="error"
      type="error"
      show-icon
      :closable="false"
      class="mb-16"
    />

    <!-- 门禁卡片: 回收率 / 慢查询占比 -->
    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-label">总搜索</div>
        <div class="stat-value">{{ fmtNum(summary?.total_searches) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">总点击</div>
        <div class="stat-value">{{ fmtNum(summary?.total_clicks) }}</div>
      </div>
      <div class="stat-card" :class="recallGatePass ? 'gate-pass' : 'gate-fail'">
        <div class="stat-label">
          回收率
          <span class="stat-target">目标 ≥ {{ fmtPct(RECALL_RATE_TARGET) }}</span>
        </div>
        <div class="stat-value">{{ fmtPct(summary?.recall_rate) }}</div>
      </div>
      <div
        class="stat-card"
        :class="!slowGateEvaluable ? 'gate-unknown' : slowGatePass ? 'gate-pass' : 'gate-fail'"
      >
        <div class="stat-label">
          慢查询占比
          <span class="stat-target">目标 ≤ {{ fmtPct(SLOW_QUERY_RATE_TARGET) }}</span>
        </div>
        <div class="stat-value">{{ fmtPct(summary?.slow_query_rate) }}</div>
        <div v-if="!slowGateEvaluable" class="stat-note">
          基于决策耗时代理值, 门禁不可判定 (真检索耗时留 PR7)
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-label">P95 决策耗时</div>
        <div class="stat-value">{{ fmtMs(summary?.p95_latency_ms) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">活跃用户</div>
        <div class="stat-value">{{ fmtNum(summary?.distinct_users) }}</div>
      </div>
    </div>

    <el-alert
      v-if="summary?.latency_semantics"
      type="info"
      show-icon
      :closable="false"
      class="mb-16"
    >
      <template #title>
        耗时口径: {{ summary.latency_semantics }}
      </template>
    </el-alert>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-input
        v-model="filters.q"
        placeholder="搜索 query 子串"
        clearable
        :prefix-icon="Search"
        class="filter-query"
        @keyup.enter="onSearch"
      />
      <el-select v-model="filters.days" class="filter-days" @change="onSearch">
        <el-option :value="7" label="近 7 天" />
        <el-option :value="30" label="近 30 天" />
        <el-option :value="90" label="近 90 天" />
        <el-option :value="365" label="近 1 年" />
      </el-select>
      <el-select
        v-model="filters.source"
        placeholder="全部来源"
        clearable
        class="filter-source"
        @change="onSearch"
      >
        <el-option value="knowledge_search" label="知识库搜索" />
        <el-option value="knowledge_search_semantic" label="知识库语义" />
        <el-option value="agent_chat" label="Agent 检索" />
        <el-option value="mobile" label="移动端" />
      </el-select>
      <el-checkbox v-model="filters.hitOnly" @change="onSearch">仅命中</el-checkbox>
      <el-checkbox v-model="filters.slowOnly" @change="onSearch">仅慢查询</el-checkbox>
      <el-button type="primary" :icon="Search" @click="onSearch">查询</el-button>
      <el-button @click="onReset">重置</el-button>
    </div>

    <!-- 7 维表格 -->
    <el-table
      v-loading="loading"
      :data="rows"
      stripe
      border
      size="small"
      empty-text="暂无检索日志"
      class="logs-table"
    >
      <el-table-column prop="created_at" label="时间" width="150">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column prop="query" label="查询" min-width="200" show-overflow-tooltip />
      <el-table-column prop="candidate_count" label="候选数" width="88" align="right" />
      <el-table-column label="命中" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="row.hit ? 'success' : 'info'" size="small" effect="plain">
            {{ row.hit ? '是' : '否' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="点击位置" width="96" align="right">
        <template #default="{ row }">
          {{ row.click_position == null ? '-' : `#${row.click_position}` }}
        </template>
      </el-table-column>
      <el-table-column width="120" align="right">
        <template #header>
          <el-tooltip
            content="点击决策耗时 = updated_at - created_at, 非检索耗时 (真检索耗时留 PR7)"
            placement="top"
          >
            <span>耗时 *</span>
          </el-tooltip>
        </template>
        <template #default="{ row }">{{ fmtMs(row.latency_ms) }}</template>
      </el-table-column>
      <el-table-column label="用户" width="120">
        <template #default="{ row }">{{ row.user_name || '匿名用户' }}</template>
      </el-table-column>
      <el-table-column label="来源" width="120">
        <template #default="{ row }">{{ sourceLabel(row.source) }}</template>
      </el-table-column>
      <el-table-column
        prop="embedding_model"
        label="模型"
        min-width="150"
        show-overflow-tooltip
      />
    </el-table>

    <el-pagination
      v-if="total > 0"
      :current-page="currentPage"
      :page-size="limit"
      :page-sizes="[20, 50, 100, 200]"
      :total="total"
      layout="total, sizes, prev, pager, next"
      class="pager"
      @current-change="goToPage"
      @size-change="setPageSize"
    />
  </div>
</template>

<style scoped>
.search-logs-view {
  padding: 20px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 20px;
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.page-desc {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.mb-16 {
  margin-bottom: 16px;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.stat-card {
  padding: 14px 16px;
  background: var(--el-bg-color-overlay);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: var(--radius-lg, 12px);
}

.stat-card.gate-pass {
  border-color: var(--el-color-success);
}

.stat-card.gate-fail {
  border-color: var(--el-color-danger);
}

.stat-card.gate-unknown {
  border-color: var(--el-color-warning);
}

.stat-note {
  margin-top: 6px;
  font-size: 11px;
  line-height: 1.4;
  color: var(--el-color-warning);
}

.stat-label {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: baseline;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.stat-target {
  font-size: 11px;
  color: var(--el-text-color-placeholder);
}

.stat-value {
  margin-top: 6px;
  font-size: 22px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-bottom: 14px;
}

.filter-query {
  width: 240px;
}

.filter-days {
  width: 130px;
}

.filter-source {
  width: 160px;
}

.logs-table {
  width: 100%;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

@media (width <= 768px) {
  .search-logs-view {
    padding: 12px;
  }

  .filter-query,
  .filter-days,
  .filter-source {
    width: 100%;
  }
}
</style>
