<!--
  AuditLogView.vue — v2 PR7 审计日志视图 (admin only)

  路由: /admin/audit
  功能:
  - 时间倒序审计列表
  - filter: user_id, action, ip, 时间段
  - 分页 (50/页)
  - 统计摘要卡片 (按 action 聚合)
  - dark mode 非 scoped 块
-->
<template>
  <div class="page-container audit-log-view">
    <div class="page-header">
      <h2>🔒 审计日志</h2>
      <p class="page-subtitle">查看所有 API 调用 (谁在什么时间做了什么)</p>
    </div>

    <div v-if="summary" class="audit-summary">
      <div class="summary-card">
        <div class="summary-label">总记录</div>
        <div class="summary-value">{{ summary.total }}</div>
      </div>
      <div class="summary-card" v-for="(count, action) in topActions" :key="action">
        <div class="summary-label">{{ action }}</div>
        <div class="summary-value">{{ count }}</div>
      </div>
    </div>

    <div class="audit-filters">
      <el-form :inline="true" :model="filters" @submit.prevent="onSearch">
        <el-form-item label="用户ID">
          <el-input v-model.number="filters.user_id" type="number" placeholder="user_id" style="width: 120px" clearable />
        </el-form-item>
        <el-form-item label="动作">
          <el-select v-model="filters.action" placeholder="全部" clearable style="width: 140px">
            <el-option v-for="a in COMMON_ACTIONS" :key="a" :label="a" :value="a" />
          </el-select>
        </el-form-item>
        <el-form-item label="起始时间">
          <el-date-picker v-model="filters.from_dt" type="datetime" placeholder="起始" style="width: 180px" />
        </el-form-item>
        <el-form-item label="截止时间">
          <el-date-picker v-model="filters.to_dt" type="datetime" placeholder="截止" style="width: 180px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="onSearch">查询</el-button>
          <el-button @click="onReset">重置</el-button>
          <el-button @click="onRefresh">刷新</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div v-if="loading && entries.length === 0" class="audit-loading">加载中...</div>

    <div v-else-if="entries.length === 0" class="audit-empty">
      <el-empty description="暂无审计记录" />
    </div>

    <el-table v-else :data="entries" stripe class="audit-table">
      <el-table-column prop="created_at" label="时间" width="170">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column prop="user_id" label="用户" width="80">
        <template #default="{ row }">{{ row.user_id || '匿名' }}</template>
      </el-table-column>
      <el-table-column prop="method" label="方法" width="80" />
      <el-table-column prop="action" label="动作" width="100">
        <template #default="{ row }">
          <el-tag size="small">{{ row.action }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="path" label="路径" min-width="240">
        <template #default="{ row }">
          <code class="path-code">{{ row.path }}</code>
        </template>
      </el-table-column>
      <el-table-column prop="status_code" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="statusTag(row.status_code)" size="small">{{ row.status_code }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="ip_address" label="IP" width="130">
        <template #default="{ row }">{{ row.ip_address || '—' }}</template>
      </el-table-column>
      <el-table-column prop="duration_ms" label="耗时" width="80">
        <template #default="{ row }">{{ row.duration_ms || 0 }}ms</template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="filters.page"
      v-model:page-size="filters.page_size"
      :total="total"
      :page-sizes="[20, 50, 100, 200]"
      layout="total, sizes, prev, pager, next, jumper"
      @current-change="onPageChange"
      @size-change="onSizeChange"
      class="audit-pagination"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const COMMON_ACTIONS = [
  'read', 'write', 'delete',
  'login', 'logout',
  'upload', 'download', 'share', 'unshare',
  'share_token_create', 'share_token_revoke',
  'visibility_change',
  'file_request_create', 'file_request_submit', 'file_request_deactivate',
  'ws_connect', 'ws_disconnect',
  'admin_action',
]

const entries = ref([])
const summary = ref(null)
const loading = ref(false)
const total = ref(0)

const filters = ref({
  user_id: null,
  action: null,
  from_dt: null,
  to_dt: null,
  page: 1,
  page_size: 50,
})

const topActions = computed(() => {
  if (!summary.value?.by_action) return {}
  return Object.fromEntries(
    Object.entries(summary.value.by_action).slice(0, 6)
  )
})

function statusTag(code) {
  if (code >= 500) return 'danger'
  if (code >= 400) return 'warning'
  if (code >= 200 && code < 300) return 'success'
  return 'info'
}

function formatTime(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString('zh-CN', { hour12: false })
  } catch { return iso }
}

function buildQueryParams() {
  const p = { page: filters.value.page, page_size: filters.value.page_size }
  if (filters.value.user_id) p.user_id = filters.value.user_id
  if (filters.value.action) p.action = filters.value.action
  if (filters.value.from_dt) p.from_dt = new Date(filters.value.from_dt).toISOString()
  if (filters.value.to_dt) p.to_dt = new Date(filters.value.to_dt).toISOString()
  return p
}

async function fetchEntries() {
  loading.value = true
  try {
    const resp = await axios.get('/api/v1/admin/audit', { params: buildQueryParams() })
    entries.value = resp.data.items || []
    total.value = resp.data.total || 0
  } catch (e) {
    ElMessage.error(e?.response?.data?.error?.message || '加载失败')
    entries.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function fetchSummary() {
  try {
    const resp = await axios.get('/api/v1/admin/audit/summary')
    summary.value = resp.data
  } catch (e) {
    summary.value = null
  }
}

async function onSearch() {
  filters.value.page = 1
  await fetchEntries()
}

function onReset() {
  filters.value = {
    user_id: null,
    action: null,
    from_dt: null,
    to_dt: null,
    page: 1,
    page_size: 50,
  }
  fetchEntries()
}

function onRefresh() {
  fetchEntries()
  fetchSummary()
}

function onPageChange(p) {
  filters.value.page = p
  fetchEntries()
}

function onSizeChange(s) {
  filters.value.page_size = s
  filters.value.page = 1
  fetchEntries()
}

onMounted(() => {
  fetchEntries()
  fetchSummary()
})
</script>

<style scoped>
.page-container.audit-log-view {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}
.page-header h2 {
  margin: 0 0 4px 0;
  font-size: 22px;
  font-weight: 600;
}
.page-subtitle {
  margin: 0 0 20px 0;
  color: var(--color-text-secondary);
  font-size: 13px;
}
.audit-summary {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.summary-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 12px 18px;
  min-width: 120px;
}
.summary-label {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-bottom: 4px;
}
.summary-value {
  font-size: 22px;
  font-weight: 600;
  color: var(--color-primary);
}
.audit-filters {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 12px 16px;
  margin-bottom: 16px;
}
.audit-loading, .audit-empty {
  padding: 40px;
  text-align: center;
  color: var(--color-text-secondary);
}
.audit-table {
  border-radius: var(--radius-md);
  overflow: hidden;
}
.path-code {
  font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
  font-size: 12px;
  background: var(--color-bg-page);
  padding: 2px 6px;
  border-radius: 4px;
  word-break: break-all;
}
.audit-pagination {
  margin-top: 16px;
  justify-content: flex-end;
  display: flex;
}
</style>

<!-- v60-v67 教训: dark mode 跨组件覆盖必须非 scoped 块 -->
<style>
[data-theme="dark"] .audit-log-view .summary-card {
  background: var(--color-bg-card);
  border-color: var(--color-border);
}
[data-theme="dark"] .audit-log-view .audit-filters {
  background: var(--color-bg-card);
  border-color: var(--color-border);
}
[data-theme="dark"] .audit-log-view .path-code {
  background: var(--color-bg-page);
  color: var(--color-text-primary);
}
</style>
