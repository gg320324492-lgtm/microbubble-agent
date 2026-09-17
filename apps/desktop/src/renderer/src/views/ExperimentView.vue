<script setup lang="ts">
// 本地实验记录本（M3-1）— 状态筛选/检索/新建/详情（编号·状态流转·Markdown 记录·附件）。
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { ExperimentFull, ExperimentStatus } from '@shared/types'

const STATUS_LABEL: Record<ExperimentStatus, string> = {
  draft: '草稿',
  ongoing: '进行中',
  completed: '已完成',
  archived: '已归档'
}
const STATUS_ORDER: ExperimentStatus[] = ['draft', 'ongoing', 'completed', 'archived']

const all = ref<ExperimentFull[]>([])
const statusFilter = ref<ExperimentStatus | 'all'>('all')
const query = ref('')
const selected = ref<ExperimentFull | null>(null)

const creating = ref(false)
const form = ref({ title: '', code: '', status: 'ongoing' as ExperimentStatus, tags: '', content: '' })

const editing = ref(false)
const editTitle = ref('')
const editContent = ref('')
const saving = ref(false)
const attachInput = ref<HTMLInputElement | null>(null)

const hits = ref<ElnListItem[] | null>(null)
const isSearchMode = computed(() => hits.value !== null && query.value.trim() !== '')

interface ElnListItem {
  id: number
  title: string
  code: string
  status: ExperimentStatus
  tags: string[]
  snippet: string
  highlight: { start: number; end: number } | null
  updatedAt: number
}

const shown = computed<ElnListItem[]>(() => {
  const sorted = [...all.value].sort((a, b) => b.updatedAt - a.updatedAt)
  if (hits.value !== null) {
    return hits.value.map((h) => ({
      id: h.id,
      title: h.title,
      code: h.code,
      status: h.status,
      tags: h.tags,
      snippet: h.snippet,
      highlight: h.highlight,
      updatedAt: h.updatedAt
    }))
  }
  return sorted.map((d) => ({
    id: d.id,
    title: d.title,
    code: d.code,
    status: d.status,
    tags: d.tags,
    snippet: d.content.slice(0, 120),
    highlight: null,
    updatedAt: d.updatedAt
  }))
})

async function refresh(): Promise<void> {
  all.value = await window.api.experiments.list()
}

function applyFilter(s: ExperimentStatus | 'all'): void {
  statusFilter.value = s
  void refresh()
}

async function onSearch(): Promise<void> {
  const q = query.value.trim()
  if (!q) {
    hits.value = null
    return
  }
  hits.value = await window.api.experiments.search(q)
}

function onSearchInput(): void {
  if (!query.value.trim()) hits.value = null
  else void onSearch()
}

async function onCreate(): Promise<void> {
  if (!form.value.title.trim()) {
    ElMessage.warning('请填写实验标题')
    return
  }
  saving.value = true
  try {
    const { id, code } = await window.api.experiments.create({
      title: form.value.title.trim(),
      ...(form.value.code.trim() ? { code: form.value.code.trim() } : {}),
      status: form.value.status,
      tags: form.value.tags ? form.value.tags.split(/[,，、]/).map((t) => t.trim()).filter(Boolean) : [],
      content: form.value.content
    })
    creating.value = false
    form.value = { title: '', code: '', status: 'ongoing', tags: '', content: '' }
    ElMessage.success(`实验已创建，编号 ${code}`)
    hits.value = null
    query.value = ''
    statusFilter.value = 'all'
    await refresh()
    await openDoc(id)
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '创建失败')
  } finally {
    saving.value = false
  }
}

async function openDoc(id: number): Promise<void> {
  const doc = await window.api.experiments.get(id)
  if (!doc) {
    ElMessage.error('实验不存在')
    return
  }
  selected.value = doc
  editing.value = false
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
    await window.api.experiments.update(selected.value.id, { title: editTitle.value, content: editContent.value })
    selected.value = (await window.api.experiments.get(selected.value.id))!
    editing.value = false
    ElMessage.success('已保存')
    hits.value = null
    await refresh()
  } finally {
    saving.value = false
  }
}

async function setStatus(s: ExperimentStatus): Promise<void> {
  if (!selected.value || selected.value.status === s) return
  await window.api.experiments.update(selected.value.id, { status: s })
  selected.value = (await window.api.experiments.get(selected.value.id))!
  ElMessage.success(`状态已切换为「${STATUS_LABEL[s]}」`)
  hits.value = null
  await refresh()
}

async function removeDoc(): Promise<void> {
  if (!selected.value) return
  try {
    await ElMessageBox.confirm('删除实验将同时删除记录，附件文件移入系统回收站（可恢复）。确定删除？', '删除实验', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }
  await window.api.experiments.delete(selected.value.id)
  selected.value = null
  ElMessage.success('实验已删除')
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
    await window.api.experiments.addFile(selected.value.id, { name: file.name, data })
    selected.value = (await window.api.experiments.get(selected.value.id))!
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
    await window.api.experiments.openFile(selected.value.id, fileId)
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
  await window.api.experiments.removeFile(selected.value.id, fileId)
  selected.value = (await window.api.experiments.get(selected.value.id))!
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
  <div class="eln">
    <h1>实验记录本</h1>

    <!-- 详情 -->
    <section v-if="selected" class="card detail">
      <div class="detail-head">
        <button class="back-btn" @click="backToList">← 返回列表</button>
        <span class="code-badge" data-testid="eln-code">{{ selected.code }}</span>
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
      <div class="detail-meta">
        {{ fmtTime(selected.updatedAt) }}
        <span v-for="t in selected.tags" :key="t" class="tag">{{ t }}</span>
      </div>

      <div class="section">
        <div class="section-head">
          <h3>实验记录</h3>
          <button v-if="!editing" class="mini-btn" @click="startEdit">编辑</button>
          <template v-else>
            <button class="mini-btn" :disabled="saving" @click="saveEdit">保存</button>
            <button class="mini-btn" @click="editing = false">取消</button>
          </template>
        </div>
        <textarea v-if="editing" v-model="editContent" class="edit-area" rows="16" placeholder="实验记录（Markdown）…"></textarea>
        <pre v-else class="doc-content" data-testid="eln-content">{{ selected.content || '（暂无记录，点「编辑」写入）' }}</pre>
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
      <div class="eln-toolbar">
        <input
          v-model="query"
          class="search-input"
          placeholder="全文检索（标题 / 实验记录，支持中文）…"
          data-testid="eln-search"
          @input="onSearchInput"
          @keydown.enter="onSearch"
        />
        <button class="new-btn" data-testid="eln-new" @click="creating = true">＋ 新建实验</button>
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
      <div v-if="creating" class="card new-form" data-testid="eln-new-form">
        <div class="form-row"><label>标题</label><input v-model="form.title" placeholder="实验标题（必填）" /></div>
        <div class="form-row"><label>编号</label><input v-model="form.code" placeholder="留空自动生成（EXP-YYYYMMDD-NN）" /></div>
        <div class="form-row"><label>状态</label>
          <select v-model="form.status">
            <option v-for="s in STATUS_ORDER" :key="s" :value="s">{{ STATUS_LABEL[s] }}</option>
          </select>
        </div>
        <div class="form-row"><label>标签</label><input v-model="form.tags" placeholder="逗号分隔（可选）" /></div>
        <div class="form-actions">
          <button class="primary-btn" @click="onCreate">创建并打开</button>
          <button class="ghost-btn" @click="creating = false">取消</button>
        </div>
      </div>

      <!-- 空态 -->
      <div v-if="shown.length === 0" class="card empty" data-testid="eln-empty">
        <template v-if="isSearchMode">
          <p class="empty-title">没有找到与「{{ query }}」相关的实验</p>
          <p class="empty-hint">换个关键词试试——检索覆盖标题与实验记录。</p>
        </template>
        <template v-else>
          <p class="empty-title">实验记录本还是空的</p>
          <p class="empty-hint">点击「＋ 新建实验」创建条目：编号自动生成（可手改）、四态流转、Markdown 记录、附件挂载。全部数据保存在本机，断网可用。</p>
        </template>
      </div>

      <!-- 列表 / 检索命中 -->
      <div v-else class="exp-list">
        <button v-for="e in shown" :key="e.id" class="exp-item card" @click="openDoc(e.id)">
          <div class="exp-row1">
            <span class="exp-title">{{ e.title }}</span>
            <span class="status-chip small" :class="{ active: true }">{{ STATUS_LABEL[e.status] }}</span>
          </div>
          <div class="exp-row2">
            <span class="exp-code">{{ e.code }}</span>
            <span class="exp-time">{{ fmtTime(e.updatedAt) }}</span>
          </div>
          <p v-if="e.snippet" class="exp-snippet">
            <template v-if="e.highlight">
              {{ e.snippet.slice(0, e.highlight.start) }}<mark class="hl">{{ e.snippet.slice(e.highlight.start, e.highlight.end) }}</mark>{{ e.snippet.slice(e.highlight.end) }}
            </template>
            <template v-else>{{ e.snippet }}</template>
          </p>
          <div class="exp-tags">
            <span v-for="t in e.tags" :key="t" class="tag">{{ t }}</span>
          </div>
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.eln {
  max-width: 760px;
  margin: 0 auto;
}
.eln h1 {
  font-size: 20px;
  font-weight: var(--font-weight-semibold);
  margin-bottom: var(--space-5);
}
.card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
}
.eln-toolbar {
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
  grid-template-columns: 56px 1fr;
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
.exp-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.exp-item {
  display: block;
  width: 100%;
  padding: var(--space-4);
  text-align: left;
  cursor: pointer;
  transition: border-color var(--duration-fast) var(--ease-out);
}
.exp-item:hover {
  border-color: rgba(var(--color-primary-rgb), 0.5);
}
.exp-row1 {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}
.exp-title {
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
.status-chip.small.active {
  background: var(--color-primary);
  color: #fff;
}
.exp-row2 {
  margin-top: var(--space-1);
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
}
.exp-code {
  font-family: var(--font-family-mono);
  font-size: 10px;
  color: var(--color-text-secondary);
}
.exp-time {
  font-size: 11px;
  color: var(--color-text-placeholder);
}
.exp-snippet {
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
.exp-tags {
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
.code-badge {
  flex-shrink: 0;
  padding: 2px 10px;
  border-radius: var(--radius-full);
  background: var(--color-bg-secondary);
  font-family: var(--font-family-mono);
  font-size: 11px;
  color: var(--color-text-secondary);
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
