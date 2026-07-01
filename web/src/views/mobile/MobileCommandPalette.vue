<!--
  MobileCommandPalette.vue — v2 PR8.3 全局命令面板 (Ctrl+K / swipe down)
  2026-07-02
-->
<template>
  <Teleport to="body">
    <div class="command-palette-overlay" @click.self="onClose">
      <div class="command-palette-modal" role="dialog" aria-label="命令面板">
        <div class="cmd-header">
          <span class="cmd-icon">⌘</span>
          <input ref="inputRef" v-model="searchQuery" type="text" class="cmd-input"
            placeholder="搜索文件 / 动作 (Ctrl+K)" aria-label="命令搜索"
            @keydown.escape="onClose" @keydown.enter="onExecuteHighlighted" />
          <button type="button" class="cmd-close" aria-label="关闭" @click="onClose">✕</button>
        </div>
        <ul v-if="results.length" class="cmd-list" role="listbox">
          <li v-for="(r, idx) in results" :key="r.id"
            :class="{ highlighted: idx === highlightedIdx }"
            class="cmd-item" role="option" :aria-selected="idx === highlightedIdx"
            @click="onExecute(r)" @mouseenter="highlightedIdx = idx">
            <span class="cmd-item-icon">{{ r.icon }}</span>
            <div class="cmd-item-info">
              <div class="cmd-item-title">{{ r.title }}</div>
              <div v-if="r.subtitle" class="cmd-item-subtitle">{{ r.subtitle }}</div>
            </div>
            <span class="cmd-item-kind">{{ r.kind }}</span>
          </li>
        </ul>
        <div v-else class="cmd-empty">
          <p v-if="searchQuery">没有匹配 "{{ searchQuery }}" 的结果</p>
          <p v-else>开始输入搜索...</p>
        </div>
        <div class="cmd-footer">
          <span>↑↓ 选择</span><span>Enter 执行</span><span>Esc 关闭</span>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const emit = defineEmits(['close'])
const router = useRouter()

const searchQuery = ref('')
const highlightedIdx = ref(0)
const inputRef = ref(null)
const recentFiles = ref([])

const staticActions = [
  { id: 'a1', icon: '📁', title: '新建文件夹', subtitle: '在当前目录创建', kind: '动作', action: () => router.push('/drive?action=new-folder') },
  { id: 'a2', icon: '📤', title: '上传文件', subtitle: '从相册/相机选择', kind: '动作', action: () => router.push('/drive?action=upload') },
  { id: 'a3', icon: '🗑', title: '回收站', subtitle: '查看已删除文件', kind: '导航', action: () => router.push('/drive/trash') },
  { id: 'a4', icon: '📢', title: '文件请求', subtitle: '查看收作业链接', kind: '导航', action: () => router.push('/drive/requests') },
  { id: 'a5', icon: '🔔', title: '活动动态', subtitle: '团队最近动态', kind: '导航', action: () => router.push('/drive/activity') },
  { id: 'a6', icon: '⭐', title: '我的收藏', subtitle: '查看收藏文件', kind: '导航', action: () => router.push('/drive?tab=starred') },
]

const fileResults = computed(() => {
  if (!searchQuery.value) return []
  const q = searchQuery.value.toLowerCase()
  return recentFiles.value
    .filter(f => (f.file_name || f.title || '').toLowerCase().includes(q))
    .slice(0, 10)
    .map(f => ({
      id: 'f' + f.id, icon: '📄',
      title: f.file_name || f.title || '未命名',
      subtitle: f.visibility === 'private' ? '私有' : '团队可见',
      kind: '文件', action: () => router.push(`/drive/file/${f.id}`),
    }))
})

const actionResults = computed(() => {
  if (!searchQuery.value) return staticActions.slice(0, 6)
  const q = searchQuery.value.toLowerCase()
  return staticActions.filter(a => a.title.toLowerCase().includes(q) || (a.subtitle && a.subtitle.toLowerCase().includes(q)))
})

const results = computed(() => [...fileResults.value, ...actionResults.value])

function onClose() { emit('close') }
function onExecute(item) {
  if (item?.action) item.action()
  onClose()
}
function onExecuteHighlighted() {
  if (results.value.length > 0) onExecute(results.value[highlightedIdx.value])
}
function onKeydown(e) {
  if (e.key === 'ArrowDown') { e.preventDefault(); highlightedIdx.value = Math.min(highlightedIdx.value + 1, results.value.length - 1) }
  else if (e.key === 'ArrowUp') { e.preventDefault(); highlightedIdx.value = Math.max(highlightedIdx.value - 1, 0) }
}

async function loadRecentFiles() {
  try {
    const resp = await axios.get('/api/v1/drive/files', { params: { sort_by: 'updated_at', sort_order: 'desc', page_size: 30 } })
    recentFiles.value = resp.data.items || []
  } catch (e) { recentFiles.value = [] }
}

onMounted(async () => {
  await nextTick()
  inputRef.value?.focus()
  loadRecentFiles()
  document.addEventListener('keydown', onKeydown)
})
onBeforeUnmount(() => { document.removeEventListener('keydown', onKeydown) })
</script>

<style scoped>
.command-palette-overlay { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.5); display: flex; align-items: flex-start; justify-content: center; padding-top: 12vh; z-index: 3000; }
.command-palette-modal { width: 90%; max-width: 600px; max-height: 70vh; background: var(--color-bg-card); border-radius: 12px; box-shadow: var(--shadow-lg); display: flex; flex-direction: column; overflow: hidden; }
.cmd-header { display: flex; align-items: center; gap: 8px; padding: 12px 16px; border-bottom: 1px solid var(--color-border); }
.cmd-icon { font-size: 18px; color: var(--color-text-secondary); }
.cmd-input { flex: 1; border: none; outline: none; background: transparent; font-size: 16px; color: var(--color-text-primary); }
.cmd-close { width: 28px; height: 28px; background: transparent; border: none; font-size: 14px; color: var(--color-text-secondary); cursor: pointer; border-radius: 4px; }
.cmd-close:hover { background: var(--color-bg-page); }
.cmd-list { flex: 1; overflow-y: auto; list-style: none; margin: 0; padding: 4px 0; }
.cmd-item { display: flex; align-items: center; gap: 12px; padding: 10px 16px; cursor: pointer; transition: background 0.15s ease; }
.cmd-item.highlighted { background: var(--color-primary-bg); }
.cmd-item-icon { font-size: 20px; flex-shrink: 0; }
.cmd-item-info { flex: 1; min-width: 0; }
.cmd-item-title { font-size: 14px; color: var(--color-text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cmd-item-subtitle { font-size: 11px; color: var(--color-text-secondary); margin-top: 2px; }
.cmd-item-kind { font-size: 10px; color: var(--color-text-secondary); background: var(--color-bg-page); padding: 2px 8px; border-radius: 4px; flex-shrink: 0; }
.cmd-empty { text-align: center; padding: 40px 20px; color: var(--color-text-secondary); font-size: 13px; }
.cmd-footer { display: flex; justify-content: center; gap: 16px; padding: 8px 16px; border-top: 1px solid var(--color-border-light); font-size: 11px; color: var(--color-text-secondary); }
</style>

<style>
[data-theme="dark"] .command-palette-modal { background: var(--color-bg-card); border: 1px solid var(--color-border); }
[data-theme="dark"] .cmd-item.highlighted { background: rgba(var(--color-primary-rgb), 0.15); }
</style>