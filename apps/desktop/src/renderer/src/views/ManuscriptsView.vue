<script setup lang="ts">
// 本地稿件库（M3-2）— 状态筛选/检索/新建/详情（期刊·字数·Markdown 正文·附件）。
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { ManuscriptFull, ManuscriptStatus } from '@shared/types'

const STATUS_LABEL: Record<ManuscriptStatus, string> = {
  draft: '草稿',
  revising: '修改中',
  submitted: '已投稿',
  published: '已发表'
}
const STATUS_ORDER: ManuscriptStatus[] = ['draft', 'revising', 'submitted', 'published']

const all = ref<ManuscriptFull[]>([])
const statusFilter = ref<ManuscriptStatus | 'all'>('all')
const query = ref('')
const hits = ref<import('@shared/types').ManuscriptSearchHit[] | null>(null)
const selected = ref<ManuscriptFull | null>(null)

interface ManuscriptMetaShape {
  id: number
  title: string
  status: ManuscriptStatus
  targetJournal: string
  tags: string[]
  updatedAt: number
}

interface MsListItem extends ManuscriptMetaShape {
  cjkChars: number
  words: number
  snippet: string
  highlight: { start: number; end: number } | null
}

const shown = computed<MsListItem[]>(() => {
  const sorted = [...all.value]
    .filter((m) => statusFilter.value === 'all' || m.status === statusFilter.value)
    .sort((a, b) => b.updatedAt - a.updatedAt)
  if (hits.value !== null) {
    const metaById = new Map(all.value.map((m) => [m.id, m]))
    return hits.value.map((h) => ({
      id: h.id,
      title: h.title,
      status: h.status,
      targetJournal: h.targetJournal,
      tags: metaById.get(h.id)?.tags ?? [],
      updatedAt: h.updatedAt,
      cjkChars: 0,
      words: 0,
      snippet: h.snippet,
      highlight: h.highlight
    }))
  }
  return sorted.map((m) => ({
    id: m.id,
    title: m.title,
    status: m.status,
    targetJournal: m.targetJournal,
    tags: m.tags,
    updatedAt: m.updatedAt,
    cjkChars: 0,
    words: 0,
    snippet: m.content.slice(0, 120),
    highlight: null
  }))
})
const isSearchMode = computed(() => hits.value !== null && query.value.trim() !== '')

const creating = ref(false)
const form = ref({ title: '', status: 'draft' as ManuscriptStatus, journal: '', tags: '', content: '' })
const saving = ref(false)
const editing = ref(false)
const editTitle = ref('')
const editContent = ref('')
const attachInput = ref<HTMLInputElement | null>(null)

// 详情页字数（响应式跟随编辑内容）
const liveStats = computed(() => {
  const text = editing.value ? editContent.value : selected.value?.content ?? ''
  const cjk = (text.match(/[\u4e00-\u9fff]/g) ?? []).length
  const latin = (text.match(/[A-Za-z0-9]+/g) ?? []).length
  return { cjkChars: cjk, words: cjk + latin }
})

async function refresh(): Promise<void> {
  all.value = await window.api.manuscripts.list()
}

function applyFilter(s: ManuscriptStatus | 'all'): void {
  statusFilter.value = s
  void refresh()
}

async function onSearch(): Promise<void> {
  const q = query.value.trim()
  if (!q) {
    hits.value = null
    return
  }
  const raw = await window.api.manuscripts.search(q)
  const metaById = new Map(all.value.map((m) => [m.id, m]))
  hits.value = raw.map((h) => ({
    id: h.id,
    title: h.title,
    status: h.status,
    targetJournal: h.targetJournal,
    tags: metaById.get(h.id)?.tags ?? [],
    updatedAt: h.updatedAt,
    cjkChars: 0,
    words: 0,
    snippet: h.snippet,
    highlight: h.highlight
  }))
}

function onSearchInput(): void {
  if (!query.value.trim()) hits.value = null
  else void onSearch()
}

async function onCreate(): Promise<void> {
  if (!form.value.title.trim()) {
    ElMessage.warning('请填写稿件标题')
    return
  }
  saving.value = true
  try {
    const { id } = await window.api.manuscripts.create({
      title: form.value.title.trim(),
      status: form.value.status,
      targetJournal: form.value.journal,
      tags: form.value.tags ? form.value.tags.split(/[,，、]/).map((t) => t.trim()).filter(Boolean) : [],
      content: form.value.content
    })
    creating.value = false
    form.value = { title: '', status: 'draft', journal: '', tags: '', content: '' }
    ElMessage.success('稿件已创建')
    hits.value = null
    query.value = ''
    statusFilter.value = 'all'
    await refresh()
    await openDoc(id)
  } finally {
    saving.value = false
  }
}

async function openDoc(id: number): Promise<void> {
  const doc = await window.api.manuscripts.get(id)
  if (!doc) {
    ElMessage.error('稿件不存在')
    return
  }
  selected.value = doc
  editing.value = false
}

async function setStatus(s: ManuscriptStatus): Promise<void> {
  if (!selected.value || selected.value.status === s) return
  await window.api.manuscripts.update(selected.value.id, { status: s })
  selected.value = (await window.api.manuscripts.get(selected.value.id))!
  ElMessage.success(`状态已切换为「${STATUS_LABEL[s]}」`)
  hits.value = null
  await refresh()
}

function startEdit(): void {
  editTitle.value = selected.value!.title
  editContent.value = selected.value!.content
  editing.value = true
}

async function saveEdit(): Promise<void> {
  if (!selected.value) return
  saving.value = true
  try {
    await window.api.manuscripts.update(selected.value.id, { title: editTitle.value, content: editContent.value })
    selected.value = (await window.api.manuscripts.get(selected.value.id))!
    editing.value = false
    ElMessage.success('已保存')
    hits.value = null
    await refresh()
  } finally {
    saving.value = false
  }
}

async function removeDoc(): Promise<void> {
  if (!selected.value) return
  try {
    await ElMessageBox.confirm('删除稿件将同时删除正文与附件记录，附件文件移入系统回收站（可恢复）。确定删除？', '删除稿件', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }
  await window.api.manuscripts.delete(selected.value.id)
  selected.value = null
  ElMessage.success('稿件已删除')
  hits.value = null
  await refresh()
}

function pickAttachment(): void {
  attachInput.value?.click()
}

async function onAttachmentPicked(e: Event): Promise<void> {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !selected.value) return
  try {
    const data = new Uint8Array(await file.arrayBuffer())
    await window.api.manuscripts.addFile(selected.value.id, { name: file.name, data })
    selected.value = (await window.api.manuscripts.get(selected.value.id))!
    ElMessage.success('附件已添加')
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '附件添加失败')
  } finally {
    input.value = ''
  }
}

async function openAttachment(fileId: number): Promise<void> {
  if (!selected.value) return
  try {
    await window.api.manuscripts.openFile(selected.value.id, fileId)
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '打开失败')
  }
}

async function removeAttachment(fileId: number): Promise<void> {
  if (!selected.value) return
  try {
    await ElMessageBox.confirm('附件文件将移入系统回收站（可恢复）。确定删除？', '删除附件', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }
  await window.api.manuscripts.removeFile(selected.value.id, fileId)
  selected.value = (await window.api.manuscripts.get(selected.value.id))!
  ElMessage.success('附件已删除')
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
    await refresh()
  } catch {
    /* 主进程异常保持空态 */
  }
})
</script>

<template>
  <div class="ms">
    <h1>稿件</h1>

    <!-- 详情 -->
    <section v-if="selected" class="card detail">
      <div class="detail-head">
        <button class="back-btn" @click="backToList">← 返回列表</button>
        <button class="mini-btn danger" @click="removeDoc">删除</button>
      </div>
      <h2 class="detail-title">{{ selected.title }}</h2>
      <div class="status-row">
        <span
          v-for="s in STATUS_ORDER"
          :key="s"
          class="status-chip"
          :class="{ active: selected.status === s }"
          @click="setStatus(s)"
        >
          {{ STATUS_LABEL[s] }}
        </span>
      </div>
      <div class="detail-meta" data-testid="ms-meta">
        <template v-if="selected.targetJournal">目标期刊：{{ selected.targetJournal }} · </template>
        字数：{{ liveStats.cjkChars }} 字 / {{ liveStats.words }} 词 · 更新于 {{ fmtTime(selected.updatedAt) }}
        <span v-for="t in selected.tags" :key="t" class="tag">{{ t }}</span>
      </div>

      <div class="section">
        <div class="section-head">
          <h3>正文</h3>
          <button v-if="!editing" class="mini-btn" @click="startEdit">编辑</button>
          <template v-else>
            <button class="mini-btn" :disabled="saving" @click="saveEdit">保存</button>
            <button class="mini-btn" @click="editing = false">取消</button>
          </template>
        </div>
        <textarea v-if="editing" v-model="editContent" class="edit-area" rows="18" placeholder="稿件正文（Markdown）…"></textarea>
        <pre v-else class="doc-content" data-testid="ms-content">{{ selected.content || '（暂无正文，点「编辑」写入）' }}</pre>
      </div>

      <div class="section">
        <div class="section-head">
          <h3>附件</h3>
          <button class="mini-btn" @click="pickAttachment">＋ 添加附件</button>
          <input ref="attachInput" type="file" hidden @change="onAttachmentPicked" />
        </div>
        <div v-if="selected.files.length === 0" class="section-empty">暂无附件</div>
        <div v-for="f in selected.files" :key="f.id" class="attach-row">
          <button class="attach-name" @click="openAttachment(f.id)" :title="'打开 ' + f.fileName">{{ f.fileName }}</button>
          <span class="attach-size">{{ fmtSize(f.fileSize) }}</span>
          <button class="mini-btn danger" @click="removeAttachment(f.id)">删除</button>
        </div>
      </div>
    </section>

    <!-- 列表态 -->
    <template v-else>
      <div class="ms-toolbar">
        <input
          v-model="query"
          class="search-input"
          placeholder="全文检索（标题 / 正文，支持中文）…"
          data-testid="ms-search"
          @input="onSearchInput"
          @keydown.enter="onSearch"
        />
        <button class="new-btn" data-testid="ms-new" @click="creating = true">＋ 新建稿件</button>
      </div>

      <div class="chips" v-if="!isSearchMode">
        <button class="chip" :class="{ active: statusFilter === 'all' }" @click="applyFilter('all')">全部</button>
        <button
          v-for="s in STATUS_ORDER"
          :key="s"
          class="chip"
          :class="{ active: statusFilter === s }"
          @click="applyFilter(s)"
        >
          {{ STATUS_LABEL[s] }}
        </button>
      </div>

      <!-- 新建表单 -->
      <div v-if="creating" class="card new-form" data-testid="ms-new-form">
        <div class="form-row"><label>标题</label><input v-model="form.title" placeholder="稿件标题（必填）" /></div>
        <div class="form-row"><label>状态</label>
          <select v-model="form.status">
            <option v-for="s in STATUS_ORDER" :key="s" :value="s">{{ STATUS_LABEL[s] }}</option>
          </select>
        </div>
        <div class="form-row"><label>目标期刊</label><input v-model="form.journal" placeholder="目标期刊（可选）" /></div>
        <div class="form-row"><label>标签</label><input v-model="form.tags" placeholder="逗号分隔（可选）" /></div>
        <div class="form-actions">
          <button class="primary-btn" @click="onCreate">创建并打开</button>
          <button class="ghost-btn" @click="creating = false">取消</button>
        </div>
      </div>

      <!-- 空态 -->
      <div v-if="shown.length === 0" class="card empty" data-testid="ms-empty">
        <template v-if="isSearchMode">
          <p class="empty-title">没有找到与「{{ query }}」相关的稿件</p>
          <p class="empty-hint">换个关键词试试——检索覆盖标题与正文。</p>
        </template>
        <template v-else>
          <p class="empty-title">稿件库还是空的</p>
          <p class="empty-hint">点击「＋ 新建稿件」开始写作：四态流转、目标期刊、字数统计、附件挂载。全部数据保存在本机，断网可用。</p>
        </template>
      </div>

      <!-- 列表 / 命中 -->
      <div v-else class="ms-list">
        <button v-for="m in shown" :key="m.id" class="ms-item card" @click="openDoc(m.id)">
          <div class="ms-row1">
            <span class="ms-title">{{ m.title }}</span>
            <span class="status-chip small">{{ STATUS_LABEL[m.status] }}</span>
          </div>
          <div class="ms-row2">
            <span v-if="m.targetJournal" class="ms-journal">{{ m.targetJournal }}</span>
            <span class="ms-time">{{ fmtTime(m.updatedAt) }}</span>
          </div>
          <p v-if="m.snippet" class="ms-snippet">
            <template v-if="m.highlight">
              {{ m.snippet.slice(0, m.highlight.start) }}<mark class="hl">{{ m.snippet.slice(m.highlight.start, m.highlight.end) }}</mark>{{ m.snippet.slice(m.highlight.end) }}
            </template>
            <template v-else>{{ m.snippet }}</template>
          </p>
          <div class="ms-tags">
            <span v-for="t in m.tags" :key="t" class="tag">{{ t }}</span>
          </div>
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.ms {
  max-width: 760px;
  margin: 0 auto;
}
.ms h1 {
  font-size: 20px;
  font-weight: var(--font-weight-semibold);
  margin-bottom: var(--space-5);
}
.card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
}
.ms-toolbar {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
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
.new-btn {
  padding: 0 var(--space-4);
  border: none;
  border-radius: var(--radius-md);
  background: var(--color-primary);
  color: #fff;
  font-size: var(--font-size-sm);
  cursor: pointer;
  white-space: nowrap;
}
.chips {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}
.chip {
  padding: 4px 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  background: var(--color-bg-card);
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  cursor: pointer;
}
.chip.active {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: #fff;
}
.new-form {
  padding: var(--space-4);
  margin-bottom: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.form-row {
  display: grid;
  grid-template-columns: 72px 1fr;
  align-items: center;
  gap: var(--space-3);
}
.form-row label {
  font-size: var(--font-size-sm);
  color: var(--color-text-regular);
}
.form-row input,
.form-row select {
  height: 34px;
  padding: 0 var(--space-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-page);
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
}
.form-actions {
  display: flex;
  gap: var(--space-3);
}
.primary-btn {
  padding: 6px 18px;
  border: none;
  border-radius: var(--radius-md);
  background: var(--color-primary);
  color: #fff;
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.ghost-btn {
  padding: 6px 18px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  cursor: pointer;
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
.ms-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.ms-item {
  display: block;
  width: 100%;
  padding: var(--space-4);
  text-align: left;
  cursor: pointer;
  transition: border-color var(--duration-fast) var(--ease-out);
}
.ms-item:hover {
  border-color: rgba(var(--color-primary-rgb), 0.5);
}
.ms-row1 {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}
.ms-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}
.status-chip.small {
  padding: 1px 8px;
  border-radius: var(--radius-full);
  background: var(--color-bg-secondary);
  color: var(--color-text-secondary);
  font-size: 10px;
}
.ms-row2 {
  margin-top: var(--space-1);
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
}
.ms-journal {
  font-size: 10px;
  color: var(--color-text-secondary);
}
.ms-time {
  font-size: 11px;
  color: var(--color-text-placeholder);
}
.ms-snippet {
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
.ms-tags {
  margin-top: var(--space-2);
  display: flex;
  gap: var(--space-2);
}
.tag {
  padding: 1px 8px;
  border-radius: var(--radius-full);
  background: var(--color-bg-secondary);
  color: var(--color-text-secondary);
  font-size: 10px;
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
.mini-btn {
  padding: 4px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg-card);
  cursor: pointer;
  font-size: var(--font-size-xs);
  color: var(--color-text-regular);
}
.mini-btn.danger:hover {
  border-color: var(--color-danger, #d64545);
  color: var(--color-danger, #d64545);
}
.detail-title {
  margin-top: var(--space-3);
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
}
.status-row {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-2);
}
.status-chip {
  padding: 3px 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  background: var(--color-bg-card);
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  cursor: pointer;
}
.status-chip.active {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: #fff;
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
.section {
  margin-top: var(--space-5);
}
.section-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}
.section-head h3 {
  flex: 1;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-regular);
}
.section-empty {
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
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
.attach-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) 0;
  border-bottom: 1px dashed var(--color-border-light);
}
.attach-name {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--color-primary);
  cursor: pointer;
  text-align: left;
  font-size: var(--font-size-sm);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.attach-size {
  flex-shrink: 0;
  font-size: 10px;
  color: var(--color-text-placeholder);
}
</style>
