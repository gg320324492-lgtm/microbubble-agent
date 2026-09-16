<script setup lang="ts">
// 本地知识库（M2-1）— 列表/中文检索/导入/编辑，断网全功能。
// 导入走渲染层文件选择器读文本后交主进程；检索走 FTS5（应用层 bigram 预切词）。
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { KnowledgeDocFull, KnowledgeDocMeta, KnowledgeSearchHit } from '@shared/types'

const docs = ref<KnowledgeDocMeta[]>([])
const query = ref('')
const hits = ref<KnowledgeSearchHit[] | null>(null) // null = 未在检索态
const searching = ref(false)
const importing = ref(false)
const selected = ref<KnowledgeDocFull | null>(null)
const editText = ref('')
const editTitle = ref('')
const editing = ref(false)
const saving = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

interface KbListItem {
  id: number
  title: string
  tags: string[]
  fileSize: number
  updatedAt: number
  snippet: string
  highlight: KnowledgeSearchHit['highlight']
}

const shown = computed<KbListItem[]>(() => {
  if (hits.value !== null) {
    const metaById = new Map(docs.value.map((d) => [d.id, d]))
    return hits.value.map((h) => ({
      id: h.id,
      title: h.title,
      tags: h.tags,
      fileSize: metaById.get(h.id)?.fileSize ?? 0,
      updatedAt: h.updatedAt,
      snippet: h.snippet,
      highlight: h.highlight
    }))
  }
  return docs.value.map((d) => ({ id: d.id, title: d.title, tags: d.tags, fileSize: d.fileSize, updatedAt: d.updatedAt, snippet: '', highlight: null }))
})
const isSearchMode = computed(() => hits.value !== null && query.value.trim() !== '')

async function refreshList(): Promise<void> {
  docs.value = await window.api.knowledge.list()
}

async function onSearch(): Promise<void> {
  const q = query.value.trim()
  if (!q) {
    hits.value = null
    return
  }
  searching.value = true
  try {
    hits.value = await window.api.knowledge.search(q)
  } finally {
    searching.value = false
  }
}

function onSearchInput(): void {
  if (!query.value.trim()) hits.value = null // 清空即回到列表态
  else void onSearch()
}

function pickFiles(): void {
  fileInput.value?.click()
}

async function onFilesPicked(e: Event): Promise<void> {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  if (files.length === 0) return
  importing.value = true
  try {
    const payload: { name: string; content: string }[] = []
    for (const f of files) {
      payload.push({ name: f.name, content: await f.text() })
    }
    const res = await window.api.knowledge.import(payload)
    if (res.imported.length) ElMessage.success(`已导入 ${res.imported.length} 个文档`)
    for (const s of res.skipped) ElMessage.warning(`${s.name}：${s.reason}`)
    hits.value = null
    query.value = ''
    await refreshList()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '导入失败')
  } finally {
    importing.value = false
    input.value = ''
  }
}

async function openDoc(id: number): Promise<void> {
  const doc = await window.api.knowledge.get(id)
  if (!doc) {
    ElMessage.error('文档不存在')
    return
  }
  selected.value = doc
  editText.value = doc.content
  editTitle.value = doc.title
  editing.value = false
}

function startEdit(): void {
  editing.value = true
}

async function saveEdit(): Promise<void> {
  if (!selected.value) return
  saving.value = true
  try {
    const updated = await window.api.knowledge.update(selected.value.id, {
      title: editTitle.value,
      content: editText.value
    })
    if (updated) {
      selected.value = updated
      editing.value = false
      ElMessage.success('已保存')
      await refreshList()
    }
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '保存失败')
  } finally {
    saving.value = false
  }
}

async function removeDoc(id: number): Promise<void> {
  try {
    await ElMessageBox.confirm('删除后原件副本将移入系统回收站（可恢复）。确定删除？', '删除文档', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }
  await window.api.knowledge.delete(id)
  if (selected.value?.id === id) selected.value = null
  ElMessage.success('已删除')
  hits.value = null
  await refreshList()
}

function backToList(): void {
  selected.value = null
  editing.value = false
}

function fmtTime(ts: number): string {
  return new Date(ts).toLocaleString('zh-CN')
}

function fmtSize(bytes: number): string {
  return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KB`
}

onMounted(async () => {
  try {
    await refreshList()
  } catch {
    /* 主进程异常保持空态 */
  }
})
</script>

<template>
  <div class="kb">
    <h1>知识库</h1>

    <!-- 详情 / 编辑态 -->
    <section v-if="selected" class="card detail">
      <div class="detail-head">
        <button class="back-btn" @click="backToList">← 返回列表</button>
        <template v-if="editing">
          <input v-model="editTitle" class="title-input" />
        </template>
        <h2 v-else class="detail-title">{{ selected.title }}</h2>
        <div class="detail-actions">
          <template v-if="editing">
            <button class="btn-primary" :disabled="saving" @click="saveEdit">{{ saving ? '保存中…' : '保存' }}</button>
            <button class="btn-ghost" @click="editing = false; editText = selected.content; editTitle = selected.title">取消</button>
          </template>
          <template v-else>
            <button class="mini-btn" @click="startEdit">编辑</button>
            <button class="mini-btn danger" @click="removeDoc(selected.id)">删除</button>
          </template>
        </div>
      </div>
      <div class="detail-meta">
        {{ fmtTime(selected.updatedAt) }} · {{ fmtSize(selected.fileSize) }}
        <span v-for="t in selected.tags" :key="t" class="tag">{{ t }}</span>
      </div>
      <textarea v-if="editing" v-model="editText" class="edit-area" rows="20"></textarea>
      <pre v-else class="doc-content">{{ selected.content }}</pre>
    </section>

    <!-- 列表态 -->
    <template v-else>
      <div class="kb-toolbar">
        <input
          v-model="query"
          class="search-input"
          placeholder="全文检索（支持中文，如：臭氧）…"
          data-testid="kb-search"
          @input="onSearchInput"
          @keydown.enter="onSearch"
        />
        <button class="import-btn" data-testid="kb-import" :disabled="importing" @click="pickFiles">
          {{ importing ? '导入中…' : '＋ 导入文档' }}
        </button>
        <input ref="fileInput" type="file" accept=".md,.markdown,.txt" multiple hidden @change="onFilesPicked" />
      </div>

      <!-- 空态引导 -->
      <div v-if="shown.length === 0" class="card empty" data-testid="kb-empty">
        <template v-if="isSearchMode">
          <p class="empty-title">没有找到与「{{ query }}」相关的文档</p>
          <p class="empty-hint">换个关键词试试，或导入更多 Markdown / 文本文档。</p>
        </template>
        <template v-else>
          <p class="empty-title">知识库还是空的</p>
          <p class="empty-hint">点击「＋ 导入文档」把 Markdown / TXT 文档导入本机知识库；导入后即可全文检索、浏览与编辑。数据只存在本机，断网可用。</p>
        </template>
      </div>

      <!-- 列表 / 检索命中 -->
      <div v-else class="doc-list">
        <button v-for="d in shown" :key="d.id" class="doc-item card" @click="openDoc(d.id)">
          <div class="doc-row1">
            <span class="doc-title">{{ d.title }}</span>
            <span class="doc-time">{{ fmtTime(d.updatedAt) }}</span>
          </div>
          <p v-if="d.snippet" class="doc-snippet">
            <template v-if="d.highlight">
              {{ d.snippet.slice(0, d.highlight.start) }}<mark class="hl">{{ d.snippet.slice(d.highlight.start, d.highlight.end) }}</mark>{{ d.snippet.slice(d.highlight.end) }}
            </template>
            <template v-else>{{ d.snippet }}</template>
          </p>
          <div class="doc-meta">
            <span v-for="t in d.tags" :key="t" class="tag">{{ t }}</span>
            <span class="doc-size">{{ fmtSize(d.fileSize) }}</span>
          </div>
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.kb {
  max-width: 760px;
  margin: 0 auto;
}
.kb h1 {
  font-size: 20px;
  font-weight: var(--font-weight-semibold);
  margin-bottom: var(--space-5);
}
.card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
}
.kb-toolbar {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}
.search-input {
  flex: 1;
  height: 38px;
  padding: 0 var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-card);
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
}
.search-input:focus {
  outline: none;
  border-color: var(--color-primary);
}
.import-btn {
  padding: 0 var(--space-4);
  border: none;
  border-radius: var(--radius-md);
  background: var(--color-primary);
  color: #fff;
  font-size: var(--font-size-sm);
  cursor: pointer;
  white-space: nowrap;
}
.import-btn:disabled {
  opacity: 0.6;
}
.empty {
  padding: var(--space-8) var(--space-6);
  text-align: center;
}
.empty-title {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
}
.empty-hint {
  margin-top: var(--space-2);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  line-height: 1.7;
}
.doc-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.doc-item {
  display: block;
  width: 100%;
  padding: var(--space-4);
  text-align: left;
  cursor: pointer;
  transition: border-color var(--duration-fast) var(--ease-out);
}
.doc-item:hover {
  border-color: rgba(var(--color-primary-rgb), 0.5);
}
.doc-row1 {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
}
.doc-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}
.doc-time {
  flex-shrink: 0;
  font-size: 11px;
  color: var(--color-text-placeholder);
}
.doc-snippet {
  margin-top: var(--space-2);
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  line-height: 1.7;
  word-break: break-word;
}
.hl {
  background: rgba(var(--color-primary-rgb), 0.25);
  border-radius: 2px;
  padding: 0 1px;
}
.doc-meta {
  margin-top: var(--space-2);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.tag {
  padding: 1px 8px;
  border-radius: var(--radius-full);
  background: var(--color-bg-secondary);
  color: var(--color-text-secondary);
  font-size: 10px;
}
.doc-size {
  font-size: 10px;
  color: var(--color-text-placeholder);
}
/* 详情 */
.detail {
  padding: var(--space-5);
}
.detail-head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.back-btn {
  border: none;
  background: transparent;
  color: var(--color-primary);
  cursor: pointer;
  font-size: var(--font-size-sm);
  flex-shrink: 0;
}
.detail-title {
  flex: 1;
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.title-input {
  flex: 1;
  height: 34px;
  padding: 0 var(--space-2);
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
}
.detail-actions {
  display: flex;
  gap: var(--space-2);
  flex-shrink: 0;
}
.mini-btn {
  padding: 4px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg-card);
  cursor: pointer;
  font-size: var(--font-size-xs);
}
.mini-btn.danger:hover {
  border-color: var(--color-danger, #d64545);
  color: var(--color-danger, #d64545);
}
.btn-primary {
  padding: 5px 16px;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--color-primary);
  color: #fff;
  cursor: pointer;
  font-size: var(--font-size-xs);
}
.btn-ghost {
  padding: 5px 16px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  font-size: var(--font-size-xs);
}
.detail-meta {
  margin: var(--space-2) 0 var(--space-3);
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.doc-content {
  margin: 0;
  font-family: inherit;
  font-size: var(--font-size-sm);
  line-height: 1.8;
  color: var(--color-text-regular);
  white-space: pre-wrap;
  word-break: break-word;
}
.edit-area {
  width: 100%;
  font-family: inherit;
  font-size: var(--font-size-sm);
  line-height: 1.8;
  padding: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-page);
  color: var(--color-text-primary);
  resize: vertical;
}
</style>
