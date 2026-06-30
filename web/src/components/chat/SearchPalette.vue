<!--
  SearchPalette.vue — #043 Phase 6 全局搜索命令面板

  镜像 Linear / Notion 命令面板（Teleport 到 body，顶部搜索框，跨会话搜索结果）
  - ⌘K / Ctrl+K 全局快捷键触发
  - 输入关键词（最少 2 字符）debounce 300ms 后调 searchSessions
  - 上下方向键切换 / Enter 跳到对应 session
  - Esc 关闭
-->
<template>
  <Teleport to="body">
    <Transition name="palette-fade">
      <div
        v-if="modelValue"
        class="palette-mask"
        role="dialog"
        aria-modal="true"
        aria-label="搜索会话"
        @click.self="close"
      >
        <div class="palette-panel">
          <!-- 搜索输入框 -->
          <div class="palette-search">
            <el-input
              ref="searchInputRef"
              v-model="keyword"
              name="chat-search-palette"
              placeholder="搜索所有会话（按消息内容）..."
              size="large"
              clearable
              @keydown.esc.stop="close"
              @keydown.down.prevent="moveSelection(1)"
              @keydown.up.prevent="moveSelection(-1)"
              @keydown.enter.prevent="onEnter"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
          </div>

          <!-- 结果列表 -->
          <div v-loading="loading" class="palette-results">
            <div
              v-for="(item, idx) in results"
              :key="`${item.session_id}-${item.message_id}-${idx}`"
              class="result-item"
              :class="{ active: idx === selectedIdx }"
              @click="selectResult(item)"
              @mouseenter="selectedIdx = idx"
            >
              <div class="result-meta">
                <el-icon><ChatLineRound /></el-icon>
                <span class="result-session">{{ item.session_title }}</span>
                <span class="result-role">{{ item.role === 'user' ? '🙋' : '🤖' }}</span>
                <span class="result-time">{{ formatTime(item.created_at) }}</span>
              </div>
              <div class="result-snippet">{{ item.snippet }}</div>
            </div>

            <div v-if="!loading && results.length === 0 && keyword.trim().length >= 2" class="empty">
              没有找到包含「{{ keyword }}」的会话
            </div>
            <div v-if="!keyword" class="hint">
              输入关键词搜索（最少 2 字） · ⌘K 触发 · Esc 关闭
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, watch, nextTick, computed, onBeforeUnmount } from 'vue'
import { Search, ChatLineRound } from '@element-plus/icons-vue'
import { useChatHistoryStore } from '@/stores/chatHistory'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'select'])

const chatHistoryStore = useChatHistoryStore()

const keyword = ref('')
const loading = ref(false)
const selectedIdx = ref(0)
const searchInputRef = ref(null)
let debounceTimer = null

// 从 store 取结果（store action 已更新 searchResults.value）
const results = computed(() => chatHistoryStore.searchResults.items || [])

// 打开时聚焦输入框 + 清空 keyword
watch(() => props.modelValue, async (open) => {
  if (open) {
    keyword.value = ''
    selectedIdx.value = 0
    await nextTick()
    // el-input 内部 input 元素需要 focus
    const input = searchInputRef.value?.$el?.querySelector('input')
    if (input) input.focus()
  }
})

// 监听 keyword 变化（debounce 300ms 调 searchSessions）
watch(keyword, (val) => {
  if (debounceTimer) clearTimeout(debounceTimer)
  if (!val || val.trim().length < 2) {
    // 不到 2 字符清空结果
    chatHistoryStore.searchResults = { items: [], total: 0, page: 1 }
    return
  }
  debounceTimer = setTimeout(async () => {
    loading.value = true
    try {
      await chatHistoryStore.searchSessions(val.trim())
      selectedIdx.value = 0
    } finally {
      loading.value = false
    }
  }, 300)
})

onBeforeUnmount(() => {
  if (debounceTimer) clearTimeout(debounceTimer)
})

function close() {
  emit('update:modelValue', false)
}

function moveSelection(delta) {
  if (!results.value.length) return
  const next = (selectedIdx.value + delta + results.value.length) % results.value.length
  selectedIdx.value = next
}

function onEnter() {
  if (!results.value.length) return
  const item = results.value[selectedIdx.value]
  if (item) selectResult(item)
}

function selectResult(item) {
  emit('select', { sessionId: item.session_id, messageId: item.message_id })
  close()
}

function formatTime(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch { return '' }
}
</script>

<style scoped>
.palette-mask {
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex; align-items: flex-start; justify-content: center;
  padding-top: 12vh;
  z-index: 2000;
}
.palette-panel {
  width: min(640px, 92vw);
  max-height: 70vh;
  display: flex; flex-direction: column;
  background: var(--color-bg-card);
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
  overflow: hidden;
}
.palette-search { padding: 12px; border-bottom: 1px solid var(--color-border-light, #f0f1f3); }
.palette-results { flex: 1; overflow-y: auto; padding: 8px 0; }
.result-item {
  padding: 10px 16px;
  cursor: pointer;
  transition: background 0.15s;
}
.result-item:hover, .result-item.active {
  background: var(--color-primary-bg);
}
.result-meta {
  display: flex; align-items: center; gap: 8px;
  font-size: 12px; color: var(--color-text-secondary);
  margin-bottom: 4px;
}
.result-session {
  font-weight: 500; color: var(--color-text-primary);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  max-width: 320px;
}
.result-role { font-size: 11px; }
.result-time { margin-left: auto; }
.result-snippet {
  font-size: 13px; line-height: 1.5;
  color: var(--color-text-primary);
  white-space: pre-wrap; overflow-wrap: anywhere;
}
.empty, .hint {
  padding: 24px 16px; text-align: center;
  color: var(--color-text-secondary); font-size: 13px;
}

.palette-fade-enter-active, .palette-fade-leave-active { transition: opacity 0.15s; }
.palette-fade-enter-from, .palette-fade-leave-to { opacity: 0; }
</style>

<!-- v77 P2.6 / v69 P1b: dark 覆盖（v60-v67 教训：必须非 scoped） -->
<style>
[data-theme="dark"] .palette-panel { background: var(--color-bg-card); }
[data-theme="dark"] .palette-search { border-bottom-color: var(--color-border-light); }
[data-theme="dark"] .result-item:hover, [data-theme="dark"] .result-item.active { background: var(--color-primary-bg); }
[data-theme="dark"] .result-session, [data-theme="dark"] .result-snippet { color: var(--color-text-primary); }
[data-theme="dark"] .result-meta { color: var(--color-text-secondary); }
[data-theme="dark"] .empty, [data-theme="dark"] .hint { color: var(--color-text-secondary); }
</style>
