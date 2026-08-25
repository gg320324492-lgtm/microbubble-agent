<template>
  <div class="conversation-archive" data-testid="conversation-archive">
    <header class="conversation-archive__header">
      <h1>对话归档工作区</h1>
      <p class="conversation-archive__hint">
        对所有导入的对话按关键词搜索（不区分大小写）。
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
        {{ query ? results.length + ' 条结果' : allMessages.length + ' 条消息' }}
      </span>
    </div>

    <ul data-testid="search-results">
      <li v-for="m in results" :key="m.id" class="conversation-archive__row">
        <strong class="conversation-archive__role">{{ m.role }}:</strong>
        <span class="conversation-archive__content">{{ m.content }}</span>
      </li>
      <li v-if="query && !results.length" class="conversation-archive__empty">
        未找到结果。
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

interface ConversationMessage {
  id: string
  role: string
  content: string
}

interface Conversation {
  id: string
  messages?: ConversationMessage[]
}

interface WindowWorkspace {
  listConversations?: () => Promise<Conversation[]>
}

interface Bridge {
  workspace?: WindowWorkspace
}

const query = ref<string>('')
const results = ref<ConversationMessage[]>([])
const allMessages = ref<ConversationMessage[]>([])

async function loadAll(): Promise<void> {
  const w = (globalThis as unknown as Bridge).window?.workspace
  if (!w?.listConversations) return
  try {
    const convs = await w.listConversations()
    const list: ConversationMessage[] = []
    for (const c of convs) {
      if (Array.isArray(c.messages)) list.push(...c.messages)
    }
    allMessages.value = list
  } catch (err) {
    console.error('[conversation-archive] failed to load conversations', err)
  }
}

function search(): void {
  const q = query.value.trim().toLowerCase()
  if (!q) {
    results.value = []
    return
  }
  results.value = allMessages.value.filter((m) =>
    String(m.content).toLowerCase().includes(q),
  )
}

onMounted(loadAll)

defineExpose({ query, results, allMessages, search, loadAll })
</script>

<style scoped>
.conversation-archive { padding: 1.5rem; max-width: 880px; }
.conversation-archive__header h1 { margin: 0 0 0.5rem; font-size: 1.5rem; }
.conversation-archive__hint { color: #555; font-size: 0.9rem; }
.conversation-archive__toolbar { display: flex; align-items: center; gap: 0.75rem; margin: 1rem 0; }
input[type="search"] { flex: 1; padding: 0.5rem 0.75rem; border: 1px solid #ccc; border-radius: 4px; }
.conversation-archive__count { padding: 0.2rem 0.6rem; background: #eef2ff; color: #4338ca; border-radius: 999px; font-size: 0.8rem; }
ul { list-style: none; padding: 0; margin: 0; border: 1px solid #e5e7eb; border-radius: 8px; background: #fff; }
.conversation-archive__row { padding: 0.6rem 0.9rem; border-bottom: 1px solid #e5e7eb; }
.conversation-archive__row:last-child { border-bottom: 0; }
.conversation-archive__role { color: #2563eb; margin-right: 0.4rem; }
.conversation-archive__content { color: #1f2937; }
.conversation-archive__empty { padding: 1rem; color: #6b7280; }
</style>
