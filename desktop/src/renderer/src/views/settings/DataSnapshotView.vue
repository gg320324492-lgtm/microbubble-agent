<script setup lang="ts">
// Data Snapshot View — Phase 11
// 设置页: 显示最近一次 PG snapshot 时间 + 触发重新拉取 + 进度条.

import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const history = ref<Array<{ snapshot_id: string; started_at: string; ended_at: string | null; rows_total: number; tables_done: number; tables_total: number; status: string; error_message: string | null }>>([])
const running = ref(false)
const lastResult = ref<{ ok: boolean; snapshotId?: string; tasksTotal?: number; rowsTotal?: number; errors?: string[] } | null>(null)
const error = ref<string | null>(null)

async function refreshHistory() {
  try {
    history.value = await window.api.pgSnapshot.history(20)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

async function runPreflight() {
  error.value = null
  try {
    const r = await window.api.pgSnapshot.preflight()
    if (!r.ok) {
      error.value = `预检查失败: ${r.message ?? '未知'}`
      return false
    }
    return true
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
    return false
  }
}

async function triggerSnapshot() {
  if (running.value) return
  running.value = true
  error.value = null
  const ok = await runPreflight()
  if (!ok) {
    running.value = false
    return
  }
  try {
    lastResult.value = await window.api.pgSnapshot.run()
    await refreshHistory()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    running.value = false
  }
}

function formatTime(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('zh-CN')
}

onMounted(() => {
  refreshHistory()
})
</script>

<template>
  <div class="snapshot-view">
    <header class="snapshot-header">
      <h1>数据快照</h1>
      <p class="snapshot-sub">单向同步: 网页端 PG → 桌面端 SQLite. 本地离线可用, 不同步回写.</p>
    </header>

    <section class="snapshot-card">
      <h2>当前状态</h2>
      <div v-if="history.length > 0" class="snapshot-meta">
        <div class="meta-row">
          <span class="meta-label">最近一次拉取</span>
          <span class="meta-value">{{ formatTime(history[0]?.ended_at) }}</span>
        </div>
        <div class="meta-row">
          <span class="meta-label">状态</span>
          <span :class="['meta-value', 'status-' + history[0]?.status]">
            {{ history[0]?.status ?? '—' }}
          </span>
        </div>
        <div class="meta-row">
          <span class="meta-label">累计行数</span>
          <span class="meta-value">{{ history[0]?.rows_total ?? 0 }}</span>
        </div>
        <div class="meta-row">
          <span class="meta-label">完成表数</span>
          <span class="meta-value">{{ history[0]?.tables_done ?? 0 }} / {{ history[0]?.tables_total ?? 0 }}</span>
        </div>
      </div>
      <div v-else class="snapshot-meta">
        <p>暂无 snapshot 历史. 首次拉取将初始化数据库表 pg_snapshot_meta.</p>
      </div>
    </section>

    <section class="snapshot-card">
      <h2>操作</h2>
      <div class="snapshot-actions">
        <button
          class="snapshot-button primary"
          :disabled="running"
          @click="triggerSnapshot"
        >
          {{ running ? '正在拉取...' : '重新拉取 snapshot' }}
        </button>
        <button
          class="snapshot-button"
          :disabled="running"
          @click="refreshHistory"
        >
          刷新历史
        </button>
        <button
          class="snapshot-button"
          @click="router.push('/web-history')"
        >
          查看 Web 历史
        </button>
      </div>
      <p v-if="error" class="snapshot-error">{{ error }}</p>
      <div v-if="lastResult" class="snapshot-result">
        <h3>本次拉取结果</h3>
        <p>状态: <b :class="lastResult.ok ? 'ok' : 'err'">{{ lastResult.ok ? '成功' : '失败' }}</b></p>
        <p v-if="lastResult.snapshotId">Snapshot ID: <code>{{ lastResult.snapshotId }}</code></p>
        <p v-if="lastResult.tasksTotal !== undefined">任务数: {{ lastResult.tasksTotal }}</p>
        <p v-if="lastResult.rowsTotal !== undefined">累计行数: {{ lastResult.rowsTotal }}</p>
        <pre v-if="lastResult.errors && lastResult.errors.length" class="snapshot-errors">{{ lastResult.errors.join('\n') }}</pre>
      </div>
    </section>

    <section class="snapshot-card">
      <h2>历史 ({{ history.length }})</h2>
      <table v-if="history.length > 0" class="snapshot-table">
        <thead>
          <tr>
            <th>Snapshot ID</th>
            <th>开始</th>
            <th>结束</th>
            <th>状态</th>
            <th>行数</th>
            <th>表数</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="h in history" :key="h.snapshot_id">
            <td><code>{{ h.snapshot_id.slice(-12) }}</code></td>
            <td>{{ formatTime(h.started_at) }}</td>
            <td>{{ formatTime(h.ended_at) }}</td>
            <td :class="['status-' + h.status]">{{ h.status }}</td>
            <td>{{ h.rows_total }}</td>
            <td>{{ h.tables_done }} / {{ h.tables_total }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<style scoped>
.snapshot-view {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px;
}
.snapshot-header h1 {
  font-size: 28px;
  margin: 0 0 4px;
}
.snapshot-sub {
  color: var(--research-text-secondary, #6b7280);
  margin: 0 0 24px;
}
.snapshot-card {
  background: var(--research-surface, #fff);
  border: 1px solid var(--research-border, #e5e7eb);
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 16px;
}
.snapshot-card h2 {
  font-size: 18px;
  margin: 0 0 12px;
}
.snapshot-meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.meta-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid var(--research-border-light, #f3f4f6);
}
.meta-label { color: var(--research-text-secondary, #6b7280); }
.meta-value { font-weight: 500; }
.status-completed { color: #10b981; }
.status-running { color: #f59e0b; }
.status-failed { color: #ef4444; }
.snapshot-actions {
  display: flex;
  gap: 12px;
}
.snapshot-button {
  padding: 8px 16px;
  border: 1px solid var(--research-border, #e5e7eb);
  border-radius: 6px;
  background: var(--research-surface, #fff);
  cursor: pointer;
}
.snapshot-button.primary {
  background: var(--research-primary, #FF7A5C);
  color: #fff;
  border-color: var(--research-primary, #FF7A5C);
}
.snapshot-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.snapshot-error {
  color: #ef4444;
  margin-top: 12px;
}
.snapshot-result {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--research-border-light, #f3f4f6);
}
.snapshot-result .ok { color: #10b981; }
.snapshot-result .err { color: #ef4444; }
.snapshot-errors {
  background: #fef2f2;
  padding: 8px;
  border-radius: 4px;
  font-size: 12px;
  overflow: auto;
}
.snapshot-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.snapshot-table th, .snapshot-table td {
  text-align: left;
  padding: 8px 12px;
  border-bottom: 1px solid var(--research-border-light, #f3f4f6);
}
.snapshot-table code {
  font-family: monospace;
  font-size: 12px;
}
</style>