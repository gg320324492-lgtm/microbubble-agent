<template>
  <div class="mobile-agent-traces">
    <PageHeader title="Agent Trace 监控" show-back @back="$router.back()">
      <template #right>
        <button
          type="button"
          class="header-action"
          aria-label="刷新"
          title="刷新"
          @click="fetchTraces"
        >🔄</button>
      </template>
    </PageHeader>

    <main
      class="traces-main"
      :style="{ paddingBottom: 'calc(var(--tabbar-height, 56px) + var(--sab, 0px))' }"
    >
      <!-- 类型筛选 -->
      <div class="filter-chips">
        <button
          v-for="t in typeFilters"
          :key="t.value"
          type="button"
          class="filter-chip"
          :class="{ active: activeType === t.value }"
          @click="setType(t.value)"
        >{{ t.label }}</button>
      </div>

      <!-- 列表 -->
      <div v-if="loading && traces.length === 0" class="loading">
        <div v-for="i in 3" :key="i" class="skeleton-card">
          <div class="skeleton-line w-40" />
          <div class="skeleton-line w-90" />
        </div>
      </div>

      <div v-else-if="traces.length === 0" class="empty-state">
        <div class="empty-icon">📊</div>
        <div class="empty-title">暂无 Trace 记录</div>
        <div class="empty-hint">Agent 调用追踪会自动保存到这里</div>
      </div>

      <div v-else class="trace-list">
        <button
          v-for="t in traces"
          :key="t.id"
          type="button"
          class="trace-card"
          @click="viewDetail(t)"
        >
          <div class="trace-header">
            <span class="trace-type-tag" :class="`type-${t.trace_type || 'unknown'}`">
              {{ t.trace_type || 'unknown' }}
            </span>
            <span class="trace-time">{{ formatTime(t.created_at) }}</span>
          </div>

          <div class="trace-name">{{ t.tool_name || t.action || 'Agent 调用' }}</div>

          <div v-if="t.session_id" class="trace-session">
            🆔 {{ t.session_id.slice(0, 12) }}...
          </div>

          <div class="trace-meta">
            <span v-if="t.duration_ms">⏱ {{ t.duration_ms }}ms</span>
            <span v-if="t.status" class="trace-status" :class="`status-${t.status}`">
              {{ t.status }}
            </span>
          </div>
        </button>
      </div>
    </main>

    <!-- 详情 Sheet -->
    <Teleport to="body">
      <Transition name="detail-sheet">
        <div v-if="showDetail" class="sheet-overlay" @click.self="showDetail = false">
          <div class="sheet-panel" :style="{ paddingBottom: 'calc(16px + var(--sab, 0px) + var(--tabbar-height, 56px))' }">
            <div class="sheet-handle" />
            <h3 class="sheet-title">Trace 详情</h3>
            <pre class="json-content">{{ formatJson(selectedTrace) }}</pre>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
/**
 * MobileAgentTracesView.vue — 移动端 Agent Trace 监控
 *
 * PR #8b: 简化版（无 10 列 el-table）
 * - 卡片化列表（按类型筛选）
 * - 详情 Sheet（JSON 展示）
 */

import { ref, onMounted } from 'vue'
import axios from 'axios'
import dayjs from 'dayjs'
import PageHeader from '@/components/mobile/PageHeader.vue'

const traces = ref([])
const loading = ref(false)
const activeType = ref('')
const showDetail = ref(false)
const selectedTrace = ref(null)

const typeFilters = [
  { label: '全部', value: '' },
  { label: '工具调用', value: 'tool_call' },
  { label: 'LLM', value: 'llm' },
  { label: '错误', value: 'error' },
]

async function fetchTraces() {
  loading.value = true
  try {
    const params = { page: 1, page_size: 50 }
    if (activeType.value) params.type = activeType.value
    const res = await axios.get('/api/v1/admin/agent-traces', { params })
    traces.value = res.data?.items || res.data || []
  } catch (e) {
    console.error('[MobileAgentTracesView] load failed:', e)
    traces.value = []
  } finally {
    loading.value = false
  }
}

function setType(v) {
  activeType.value = v
  fetchTraces()
}

function formatTime(t) {
  if (!t) return ''
  return dayjs(t).format('MM-DD HH:mm:ss')
}

function viewDetail(trace) {
  selectedTrace.value = trace
  showDetail.value = true
}

function formatJson(obj) {
  if (!obj) return ''
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
}

onMounted(() => {
  fetchTraces()
})
</script>

<style scoped>
.mobile-agent-traces {
  min-height: 100vh;
  background: var(--color-bg-page);
}

.traces-main {
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
}

/* 筛选 */
.filter-chips {
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.filter-chips::-webkit-scrollbar { display: none; }
.filter-chip {
  flex-shrink: 0;
  padding: 6px 12px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  font-size: 13px;
  color: var(--color-text-regular);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.filter-chip.active {
  background: var(--color-primary);
  /* stylelint-disable-next-line color-named */
  color: white;
  border-color: var(--color-primary);
}

/* 列表 */
.trace-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.trace-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  text-align: left;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.trace-card:active { background: var(--color-bg-hover); }
[data-theme="dark"] .trace-card { border-color: var(--color-border-base); }

.trace-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.trace-type-tag {
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: var(--font-weight-medium, 500);
  background: var(--color-primary-bg);
  color: var(--color-primary);
}
.trace-type-tag.type-error { background: var(--color-danger-bg); color: var(--color-danger, #F56C6C); }
.trace-type-tag.type-llm { background: var(--color-info-bg); color: var(--color-info, #909399); }
.trace-time {
  font-size: 11px;
  color: var(--color-text-secondary);
  font-variant-numeric: tabular-nums;
}
.trace-name {
  font-size: 14px;
  font-weight: var(--font-weight-medium, 500);
  color: var(--color-text-primary);
  word-break: break-all;
}
.trace-session {
  font-size: 11px;
  color: var(--color-text-secondary);
  font-family: monospace;
}
.trace-meta {
  display: flex;
  gap: 8px;
  font-size: 11px;
  color: var(--color-text-secondary);
}
.trace-status {
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  background: var(--color-bg-page);
}
.trace-status.status-success { background: var(--color-success-bg); color: var(--color-success, #67C23A); }
.trace-status.status-error { background: var(--color-danger-bg); color: var(--color-danger, #F56C6C); }

/* Header */
.header-action {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 18px;
  color: var(--color-text-regular);
  cursor: pointer;
}
.header-action:active { background: var(--color-primary-bg); }

/* 加载 / 空 */
.loading, .empty-state {
  padding: 20px 0;
}
.empty-state {
  text-align: center;
  padding: 60px 20px;
}
.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}
.empty-title {
  font-size: 15px;
  color: var(--color-text-regular);
  margin-bottom: 4px;
}
.empty-hint {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.skeleton-card {
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
  padding: 16px;
  margin-bottom: 8px;
}
.skeleton-line {
  height: 12px;
  background: var(--color-border);
  border-radius: var(--radius-sm);
  margin-bottom: 8px;
}
.skeleton-line.w-40 { width: 40%; }
.skeleton-line.w-90 { width: 90%; }

/* 详情 Sheet */
.sheet-overlay {
  position: fixed;
  inset: 0;
  z-index: 4500;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: flex-end;
}
.sheet-panel {
  width: 100%;
  max-height: 80vh;
  background: var(--color-bg-card);
  border-radius: var(--sheet-radius, 16px) var(--sheet-radius, 16px) 0 0;
  padding: 8px 20px;
  overflow-y: auto;
}
[data-theme="dark"] .sheet-panel { background: var(--color-bg-card); }
.sheet-handle {
  width: var(--sheet-handle-w, 36px);
  height: var(--sheet-handle-h, 4px);
  background: var(--color-border);
  border-radius: 2px;
  margin: 0 auto 12px;
}
.sheet-title {
  margin: 0 0 12px;
  font-size: 16px;
  font-weight: var(--font-weight-semibold, 600);
}
.json-content {
  margin: 0;
  padding: 12px;
  background: var(--color-bg-page);
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-family: monospace;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 60vh;
  overflow: auto;
}

.detail-sheet-enter-active, .detail-sheet-leave-active {
  transition: opacity 0.25s ease;
}
.detail-sheet-enter-active .sheet-panel, .detail-sheet-leave-active .sheet-panel {
  transition: transform 0.3s var(--ease-sheet);
}
.detail-sheet-enter-from, .detail-sheet-leave-to { opacity: 0; }
.detail-sheet-enter-from .sheet-panel, .detail-sheet-leave-to .sheet-panel {
  transform: translateY(100%);
}
</style>