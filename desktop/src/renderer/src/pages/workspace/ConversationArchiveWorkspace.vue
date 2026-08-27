<template>
  <div class="conversation-archive" data-testid="conversation-archive">
    <header class="conversation-archive__header">
      <h1>对话归档工作区</h1>
      <p class="conversation-archive__hint">
        按关键词搜索已同步的对话会话（标题或预览）。本地副本，不会回传到网页。
      </p>
    </header>

    <div class="conversation-archive__toolbar">
      <input
        v-model="query"
        data-testid="search-input"
        type="search"
        placeholder="输入关键词…"
        @input="search"
      />
      <span data-testid="result-count" class="conversation-archive__count">
        {{ query ? results.length + ' 条结果' : allSessions.length + ' 条对话' }}
      </span>
    </div>

    <ul data-testid="search-results">
      <li v-for="s in results" :key="s.id" class="conversation-archive__row">
        <strong class="conversation-archive__title">{{ s.title }}</strong>
        <span class="conversation-archive__meta">
          {{ s.owner_username || '匿名' }}
          · {{ s.message_count }} 条消息
          <span v-if="s.last_message_at_epoch"> · {{ formatDate(s.last_message_at_epoch) }}</span>
        </span>
        <p v-if="s.preview" class="conversation-archive__preview">{{ s.preview }}</p>
      </li>
      <li v-if="query && !results.length" class="conversation-archive__empty">
        未找到结果。
      </li>
      <li v-if="!query && !allSessions.length" class="conversation-archive__empty">
        暂无对话。
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
// [类 20.206] 2026-08-28: ConversationArchiveWorkspace 真实数据接入.
//   之前用 window.workspace.listConversations() (不存在, 永远空).
//   改为: 直接读 desktop_chat_sessions (225 行真实会话), 按 title/preview/owner 搜索.
import { onMounted, ref } from 'vue'

interface Session {
  id: string
  title: string
  preview: string
  owner_username: string | null
  message_count: number
  last_message_at_epoch: number | null
}

const query = ref<string>('')
const results = ref<Session[]>([])
const allSessions = ref<Session[]>([])

function formatDate(epoch: number): string {
  return new Date(epoch).toLocaleString('zh-CN', { hour12: false })
}

type Api = { database: { query: <T>(p: { sql: string; params?: unknown[] }) => Promise<{ rows: T[] }> } }
const bridge = (): Api | undefined =>
  (globalThis as unknown as { window?: { api?: Api } }).window?.api

async function loadAll(): Promise<void> {
  const api = bridge()
  if (!api?.database) return
  try {
    const { rows } = await api.database.query<Session>({
      sql: `SELECT id, title, preview, owner_username, message_count, last_message_at_epoch
            FROM desktop_chat_sessions
            WHERE deleted_at_epoch IS NULL
            ORDER BY last_message_at_epoch DESC NULLS LAST
            LIMIT 500`
    })
    allSessions.value = rows
  } catch (err) {
    console.error('[conversation-archive] load failed', err)
  }
}

function search(): void {
  const q = query.value.trim().toLowerCase()
  if (!q) {
    results.value = []
    return
  }
  results.value = allSessions.value.filter((s) =>
    s.title.toLowerCase().includes(q) ||
    s.preview.toLowerCase().includes(q) ||
    (s.owner_username ?? '').toLowerCase().includes(q)
  )
}

onMounted(loadAll)
defineExpose({ query, results, allSessions, search, loadAll })
</script>

<style scoped>
.conversation-archive { padding: 1.5rem; max-width: 880px; }
.conversation-archive__header h1 { margin: 0 0 0.5rem; font-size: 1.5rem; }
.conversation-archive__hint { color: #555; font-size: 0.9rem; }
.conversation-archive__toolbar { display: flex; align-items: center; gap: 0.75rem; margin: 1rem 0; }
input[type="search"] { flex: 1; padding: 0.5rem 0.75rem; border: 1px solid #ccc; border-radius: 4px; }
.conversation-archive__count { padding: 0.2rem 0.6rem; background: #eef2ff; color: #4338ca; border-radius: 999px; font-size: 0.8rem; }
ul { list-style: none; padding: 0; margin: 0; border: 1px solid #e5e7eb; border-radius: 8px; background: #fff; }
.conversation-archive__row { padding: 0.6rem 0.9rem; border-bottom: 1px solid #e5e7eb; display: flex; flex-direction: column; gap: 0.2rem; }
.conversation-archive__row:last-child { border-bottom: 0; }
.conversation-archive__title { color: #111827; }
.conversation-archive__meta { color: #6b7280; font-size: 0.8rem; }
.conversation-archive__preview { color: #4b5563; font-size: 0.85rem; margin: 0.2rem 0 0; }
.conversation-archive__empty { padding: 1rem; color: #6b7280; }
</style>