<script setup lang="ts">
// Web History View — Phase 11
// 浏览从 web PG 同步过来的数据 (只读, desktop 端离线编辑不回写).
// 显示 desktop_tasks / meetings / reminders / chat_sessions / knowledge / search_logs / audit_log.

import { onMounted, ref } from 'vue'

type TableKey = 'tasks' | 'meetings' | 'reminders' | 'chat_sessions' | 'knowledge' | 'search_logs' | 'audit_log'

const activeTable = ref<TableKey>('tasks')
const loading = ref(false)
const error = ref<string | null>(null)
const rows = ref<Array<Record<string, unknown>>>([])
const total = ref(0)

interface TableSpec {
  key: TableKey
  label: string
  columns: Array<{ key: string; label: string }>
}

const TABLES: TableSpec[] = [
  {
    key: 'tasks',
    label: '任务 (95)',
    columns: [
      { key: 'web_id', label: 'ID' },
      { key: 'title', label: '标题' },
      { key: 'status', label: '状态' },
      { key: 'priority', label: '优先级' },
      { key: 'assignee_username', label: '负责人' },
      { key: 'due_date_epoch', label: '截止' }
    ]
  },
  {
    key: 'meetings',
    label: '会议 (21)',
    columns: [
      { key: 'web_id', label: 'ID' },
      { key: 'title', label: '标题' },
      { key: 'start_time_epoch', label: '开始' },
      { key: 'status', label: '状态' },
      { key: 'creator_username', label: '创建人' }
    ]
  },
  {
    key: 'reminders',
    label: '提醒 (78)',
    columns: [
      { key: 'web_id', label: 'ID' },
      { key: 'remind_at_epoch', label: '提醒时间' },
      { key: 'remind_type', label: '类型' },
      { key: 'status', label: '状态' },
      { key: 'target_type', label: '目标' }
    ]
  },
  {
    key: 'chat_sessions',
    label: '聊天会话 (225)',
    columns: [
      { key: 'id', label: 'ID' },
      { key: 'title', label: '标题' },
      { key: 'owner_username', label: '用户' },
      { key: 'message_count', label: '消息数' },
      { key: 'last_message_at_epoch', label: '最后消息' }
    ]
  },
  {
    key: 'knowledge',
    label: '知识库 (530)',
    columns: [
      { key: 'web_id', label: 'ID' },
      { key: 'title', label: '标题' },
      { key: 'category', label: '分类' },
      { key: 'knowledge_type', label: '类型' },
      { key: 'quality_score', label: '质量' }
    ]
  },
  {
    key: 'search_logs',
    label: '搜索日志 (6902)',
    columns: [
      { key: 'web_id', label: 'ID' },
      { key: 'owner_username', label: '用户' },
      { key: 'query', label: '查询' },
      { key: 'search_type', label: '类型' },
      { key: 'response_time_ms', label: '响应' }
    ]
  },
  {
    key: 'audit_log',
    label: '审计日志 (1000, 30天, 脱敏)',
    columns: [
      { key: 'web_id', label: 'ID' },
      { key: 'user_id', label: '用户ID' },
      { key: 'ip_hash', label: 'IP hash' },
      { key: 'method', label: '方法' },
      { key: 'path', label: '路径' },
      { key: 'action', label: '操作' }
    ]
  }
]

async function loadTable(key: TableKey) {
  loading.value = true
  error.value = null
  try {
    const r = await window.api.database.query(
      `SELECT * FROM desktop_${key} ORDER BY web_id DESC LIMIT 100`,
      []
    )
    rows.value = r.rows as Array<Record<string, unknown>>
    const countRes = await window.api.database.query(
      `SELECT COUNT(*) AS total FROM desktop_${key}`,
      []
    )
    const totalRow = countRes.rows[0] as { total?: number } | undefined
    total.value = Number(totalRow?.total ?? 0)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

function switchTable(key: TableKey) {
  activeTable.value = key
  loadTable(key)
}

function formatCell(value: unknown): string {
  if (value == null) return ''
  if (typeof value === 'number' && value > 1e12) {
    // epoch ms
    return new Date(value).toLocaleString('zh-CN')
  }
  if (typeof value === 'object') return JSON.stringify(value).slice(0, 60)
  const s = String(value)
  return s.length > 80 ? s.slice(0, 80) + '…' : s
}

onMounted(() => {
  loadTable('tasks')
})
</script>

<template>
  <div class="web-history">
    <header class="history-header">
      <h1>Web 历史</h1>
      <p class="history-sub">从网页端 PG 数据库单向同步的本地镜像. 仅本地可读, 编辑不同步回 web.</p>
    </header>

    <nav class="history-tabs">
      <button
        v-for="t in TABLES"
        :key="t.key"
        :class="['tab-button', { active: activeTable === t.key }]"
        @click="switchTable(t.key)"
      >
        {{ t.label }}
      </button>
    </nav>

    <section v-if="loading" class="history-loading">加载中…</section>
    <section v-else-if="error" class="history-error">{{ error }}</section>
    <section v-else class="history-content">
      <div class="history-meta">
        <span>共 {{ total }} 条</span>
        <span>显示前 100 条</span>
      </div>
      <div class="history-table-wrapper">
        <table class="history-table">
          <thead>
            <tr>
              <th v-for="c in TABLES.find(t => t.key === activeTable)!.columns" :key="c.key">{{ c.label }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, i) in rows" :key="i">
              <td v-for="c in TABLES.find(t => t.key === activeTable)!.columns" :key="c.key">
                {{ formatCell(r[c.key]) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.web-history {
  max-width: 1280px;
  margin: 0 auto;
  padding: 24px;
}
.history-header h1 { font-size: 28px; margin: 0 0 4px; }
.history-sub { color: var(--research-text-secondary, #6b7280); margin: 0 0 24px; }
.history-tabs { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
.tab-button {
  padding: 8px 16px;
  border: 1px solid var(--research-border, #e5e7eb);
  border-radius: 6px;
  background: var(--research-surface, #fff);
  cursor: pointer;
  font-size: 13px;
}
.tab-button.active {
  background: var(--research-primary, #FF7A5C);
  color: #fff;
  border-color: var(--research-primary, #FF7A5C);
}
.history-loading,
.history-error { padding: 32px; text-align: center; color: var(--research-text-secondary, #6b7280); }
.history-error { color: #ef4444; }
.history-meta { display: flex; gap: 16px; margin-bottom: 12px; color: var(--research-text-secondary, #6b7280); font-size: 13px; }
.history-table-wrapper { overflow-x: auto; background: var(--research-surface, #fff); border: 1px solid var(--research-border, #e5e7eb); border-radius: 8px; }
.history-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.history-table th, .history-table td {
  text-align: left;
  padding: 8px 12px;
  border-bottom: 1px solid var(--research-border-light, #f3f4f6);
  white-space: nowrap;
  max-width: 360px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.history-table th { background: var(--research-surface-alt, #f9fafb); font-weight: 600; }
</style>