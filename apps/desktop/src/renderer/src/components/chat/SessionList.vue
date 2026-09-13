<script setup lang="ts">
// 会话列表 — 新建/搜索/重命名/删除，当前项高亮
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { ChatSession } from '@shared/types'
import { useChatStore } from '../../stores/chat'

const store = useChatStore()
const keyword = ref('')

const filtered = computed<ChatSession[]>(() => {
  const k = keyword.value.trim().toLowerCase()
  if (!k) return store.sessions
  return store.sessions.filter((s: ChatSession) => s.title.toLowerCase().includes(k))
})

function fmtTime(ts: number): string {
  const d = new Date(ts)
  const today = new Date()
  const sameDay = d.toDateString() === today.toDateString()
  return sameDay
    ? d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    : d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
}

async function onNew(): Promise<void> {
  await store.create()
}

async function onRename(id: string, current: string): Promise<void> {
  try {
    const { value } = await ElMessageBox.prompt('新的会话名称', '重命名会话', {
      inputValue: current,
      inputPattern: /\S+/,
      inputErrorMessage: '名称不能为空',
      confirmButtonText: '重命名',
      cancelButtonText: '取消'
    })
    await store.rename(id, value)
  } catch {
    /* 用户取消 */
  }
}

async function onDelete(id: string, title: string): Promise<void> {
  try {
    await ElMessageBox.confirm(`删除会话「${title}」？其全部消息将一并清除。`, '删除会话', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
    await store.remove(id)
    ElMessage.success('已删除')
  } catch {
    /* 用户取消 */
  }
}

onMounted(() => {
  void store.refreshSessions()
})
</script>

<template>
  <aside class="sessions">
    <button class="sessions-new" @click="onNew">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>
      新建会话
    </button>
    <input v-model="keyword" class="sessions-search" type="search" placeholder="搜索会话…" aria-label="搜索会话" />
    <div class="sessions-list" role="list">
      <div
        v-for="s in filtered"
        :key="s.id"
        class="session-item"
        :class="{ 'is-active': s.id === store.activeId }"
        role="listitem"
        @click="store.select(s.id)"
      >
        <div class="session-main">
          <span class="session-title" :title="s.title">{{ s.title }}</span>
          <span class="session-time">{{ fmtTime(s.updatedAt) }}</span>
        </div>
        <div class="session-actions" @click.stop>
          <button class="session-btn" title="重命名" aria-label="重命名会话" @click="onRename(s.id, s.title)">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 3a2.8 2.8 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>
          </button>
          <button class="session-btn session-btn-danger" title="删除" aria-label="删除会话" @click="onDelete(s.id, s.title)">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/></svg>
          </button>
        </div>
      </div>
      <div v-if="filtered.length === 0" class="sessions-empty">
        {{ keyword ? '没有匹配的会话' : '还没有会话，点上方「新建会话」开始' }}
      </div>
    </div>
  </aside>
</template>

<style scoped>
.sessions {
  width: 248px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--color-border);
  background: var(--color-bg-card);
  overflow: hidden;
}
.sessions-new {
  margin: var(--space-3);
  padding: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px dashed rgba(var(--color-primary-rgb), 0.4);
  border-radius: var(--radius-md);
  background: var(--color-primary-bg);
  color: var(--color-primary-dark);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}
.sessions-new:hover {
  background: rgba(var(--color-primary-rgb), 0.14);
}
.sessions-search {
  margin: 0 var(--space-3) var(--space-2);
  height: 32px;
  padding: 0 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-page);
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
}
.sessions-search:focus {
  outline: none;
  border-color: var(--color-primary);
}
.sessions-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 var(--space-2) var(--space-2);
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.session-item {
  position: relative;
  padding: 8px 10px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out);
}
.session-item:hover {
  background: var(--color-bg-warm);
}
.session-item.is-active {
  background: var(--color-primary-bg);
}
.session-main {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  min-width: 0;
}
.session-title {
  flex: 1;
  min-width: 0;
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.session-item.is-active .session-title {
  color: var(--color-primary-dark);
  font-weight: var(--font-weight-medium);
}
.session-time {
  flex-shrink: 0;
  font-size: 11px;
  color: var(--color-text-secondary);
}
.session-actions {
  position: absolute;
  top: 6px;
  right: 8px;
  display: none;
  gap: 2px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 1px;
}
.session-item:hover .session-actions {
  display: flex;
}
.session-btn {
  width: 24px;
  height: 22px;
  display: grid;
  place-items: center;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  border-radius: var(--radius-sm);
  cursor: pointer;
}
.session-btn:hover {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}
.session-btn-danger:hover {
  background: var(--color-danger-bg);
  color: var(--color-danger);
}
.sessions-empty {
  padding: var(--space-6) var(--space-3);
  text-align: center;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  line-height: 1.7;
}
</style>
