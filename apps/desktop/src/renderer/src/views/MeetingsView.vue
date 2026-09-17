<script setup lang="ts">
// 本地会议档案（M2-2）— 列表/检索/新建 + 详情三区（纪要/转录/附件），断网全功能。
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { MeetingDetail, MeetingListItem, MeetingSearchHit, MeetingTranscript } from '@shared/types'
const meetings = ref<MeetingListItem[]>([])
const query = ref('')
const hits = ref<MeetingSearchHit[] | null>(null)
const selected = ref<MeetingDetail | null>(null)

// 新建表单
const creating = ref(false)
const form = ref({ title: '', date: '', location: '', attendees: '', minutes: '' })
const saving = ref(false)

// 纪要编辑 / 转录编辑
const editingMinutes = ref(false)
const minutesText = ref('')
const editingTranscriptId = ref<number | null>(null)
const transcriptText = ref('')
const transcriptImporting = ref(false)
const transcriptFileInput = ref<HTMLInputElement | null>(null)

const shown = computed(() => {
  if (hits.value !== null) {
    const byId = new Map(meetings.value.map((m) => [m.id, m]))
    return hits.value.map((h) => ({ ...h, attendees: byId.get(h.id)?.attendees ?? [] }))
  }
  return meetings.value.map((m) => ({ id: m.id, title: m.title, meetingDate: m.meetingDate, location: m.location, hitSource: '' as const, snippet: m.minutes.slice(0, 120), highlight: null, updatedAt: m.updatedAt, attendees: m.attendees }))
})
const isSearchMode = computed(() => hits.value !== null && query.value.trim() !== '')

async function refreshList(): Promise<void> {
  meetings.value = await window.api.meetings.list()
}

async function onSearch(): Promise<void> {
  const q = query.value.trim()
  if (!q) {
    hits.value = null
    return
  }
  hits.value = await window.api.meetings.search(q)
}

function onSearchInput(): void {
  if (!query.value.trim()) hits.value = null
  else void onSearch()
}

async function openMeeting(id: number): Promise<void> {
  const detail = await window.api.meetings.get(id)
  if (!detail) {
    ElMessage.error('会议不存在')
    return
  }
  selected.value = detail
  editingMinutes.value = false
}

function backToList(): void {
  selected.value = null
  editingMinutes.value = false
  editingTranscriptId.value = null
}

async function onCreate(): Promise<void> {
  if (!form.value.title.trim()) {
    ElMessage.warning('请填写会议标题')
    return
  }
  saving.value = true
  try {
    const ts = form.value.date ? new Date(form.value.date).getTime() : null
    const { id } = await window.api.meetings.create({
      title: form.value.title.trim(),
      meetingDate: ts,
      location: form.value.location,
      attendees: form.value.attendees ? form.value.attendees.split(/[,，、]/).map((a) => a.trim()).filter(Boolean) : [],
      minutes: form.value.minutes
    })
    creating.value = false
    form.value = { title: '', date: '', location: '', attendees: '', minutes: '' }
    ElMessage.success('会议已创建')
    hits.value = null
    await refreshList()
    await openMeeting(id)
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    saving.value = false
  }
}

async function saveMinutes(): Promise<void> {
  if (!selected.value) return
  saving.value = true
  try {
    await window.api.meetings.update(selected.value.meeting.id, { minutes: minutesText.value })
    selected.value = (await window.api.meetings.get(selected.value.meeting.id))!
    editingMinutes.value = false
    ElMessage.success('纪要已保存')
    hits.value = null
    await refreshList()
  } finally {
    saving.value = false
  }
}

function startTranscriptEdit(t: MeetingTranscript): void {
  editingTranscriptId.value = t.id
  transcriptText.value = t.content
}

async function saveTranscript(): Promise<void> {
  if (!selected.value || editingTranscriptId.value === null) return
  await window.api.meetings.updateTranscript(selected.value.meeting.id, editingTranscriptId.value, transcriptText.value)
  selected.value = (await window.api.meetings.get(selected.value.meeting.id))!
  editingTranscriptId.value = null
  ElMessage.success('转录已保存')
}

function pickTranscriptFile(): void {
  transcriptFileInput.value?.click()
}

async function onTranscriptFile(e: Event): Promise<void> {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !selected.value) return
  transcriptImporting.value = true
  try {
    const content = await file.text()
    const ext = file.name.toLowerCase().endsWith('.srt') ? 'srt' : 'txt'
    await window.api.meetings.importTranscript({ meetingId: selected.value.meeting.id, content, source: ext })
    selected.value = (await window.api.meetings.get(selected.value.meeting.id))!
    ElMessage.success('转录已导入')
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '导入失败')
  } finally {
    transcriptImporting.value = false
    input.value = ''
  }
}

/** 粘贴新建转录 — 弹多行输入框，内容落库 source=paste */
async function pasteTranscript(): Promise<void> {
  if (!selected.value) return
  let content: string
  try {
    const { value } = await ElMessageBox.prompt('粘贴转录文本（纯文本或字幕文本）：', '粘贴新建转录', {
      inputType: 'textarea',
      inputPlaceholder: '在此粘贴转录内容…',
      confirmButtonText: '创建',
      cancelButtonText: '取消'
    })
    content = String(value ?? '')
    if (!content.trim()) return
  } catch {
    return // 取消
  }
  try {
    await window.api.meetings.importTranscript({ meetingId: selected.value.meeting.id, content, source: 'paste' })
    selected.value = (await window.api.meetings.get(selected.value.meeting.id))!
    ElMessage.success('转录已创建')
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '创建失败')
  }
}

function pickAttachment(): void {
  ;(document.getElementById('meeting-attach-input') as HTMLInputElement | null)?.click()
}

async function onAttachmentPicked(e: Event): Promise<void> {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !selected.value) return
  try {
    const data = new Uint8Array(await file.arrayBuffer())
    await window.api.meetings.addFile(selected.value.meeting.id, { name: file.name, data })
    selected.value = (await window.api.meetings.get(selected.value.meeting.id))!
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
    await window.api.meetings.openFile(selected.value.meeting.id, fileId)
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
  await window.api.meetings.removeFile(selected.value.meeting.id, fileId)
  selected.value = (await window.api.meetings.get(selected.value.meeting.id))!
  ElMessage.success('附件已删除')
}

async function removeMeeting(): Promise<void> {
  if (!selected.value) return
  try {
    await ElMessageBox.confirm('删除会议将同时删除纪要、转录记录，附件文件移入系统回收站。确定删除？', '删除会议', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }
  await window.api.meetings.delete(selected.value.meeting.id)
  selected.value = null
  ElMessage.success('会议已删除')
  hits.value = null
  await refreshList()
}

function fmtDate(ts: number | null): string {
  return ts ? new Date(ts).toLocaleDateString('zh-CN') : '未定'
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
  <div class="mtg">
    <h1>会议档案</h1>

    <!-- 详情三区 -->
    <section v-if="selected" class="card detail">
      <div class="detail-head">
        <button class="back-btn" @click="backToList">← 返回列表</button>
        <h2 class="detail-title">{{ selected.meeting.title }}</h2>
        <button class="mini-btn danger" @click="removeMeeting">删除会议</button>
      </div>
      <div class="detail-meta">
        {{ fmtDate(selected.meeting.meetingDate) }}<template v-if="selected.meeting.location"> · {{ selected.meeting.location }}</template>
        <template v-if="selected.meeting.attendees.length"> · 参会：{{ selected.meeting.attendees.join('、') }}</template>
      </div>

      <!-- 纪要 -->
      <div class="section">
        <div class="section-head">
          <h3>纪要</h3>
          <button v-if="!editingMinutes" class="mini-btn" @click="editingMinutes = true; minutesText = selected.meeting.minutes">编辑</button>
          <template v-else>
            <button class="mini-btn" :disabled="saving" @click="saveMinutes">保存</button>
            <button class="mini-btn" @click="editingMinutes = false">取消</button>
          </template>
        </div>
        <textarea v-if="editingMinutes" v-model="minutesText" class="edit-area" rows="10" placeholder="会议纪要（Markdown）…"></textarea>
        <pre v-else class="doc-content" data-testid="mtg-minutes">{{ selected.meeting.minutes || '（暂无纪要，点「编辑」写入）' }}</pre>
      </div>

      <!-- 转录 -->
      <div class="section">
        <div class="section-head">
          <h3>转录</h3>
          <div class="section-actions">
            <button class="mini-btn" @click="pasteTranscript">粘贴新建</button>
            <button class="mini-btn" data-testid="mtg-transcript-import" :disabled="transcriptImporting" @click="pickTranscriptFile">
              {{ transcriptImporting ? '导入中…' : '导入 .txt/.srt' }}
            </button>
            <input ref="transcriptFileInput" type="file" accept=".txt,.srt" hidden @change="onTranscriptFile" />
          </div>
        </div>
        <div v-if="selected.transcripts.length === 0" class="section-empty">暂无转录 — 可导入 .txt / .srt 文件</div>
        <div v-for="t in selected.transcripts" :key="t.id" class="transcript-item">
          <div class="section-head">
            <span class="transcript-meta">{{ t.source.toUpperCase() }} · {{ fmtTime(t.updatedAt) }}</span>
            <div class="section-actions">
              <button v-if="editingTranscriptId !== t.id" class="mini-btn" @click="startTranscriptEdit(t)">编辑</button>
              <template v-else>
                <button class="mini-btn" @click="saveTranscript">保存</button>
                <button class="mini-btn" @click="editingTranscriptId = null">取消</button>
              </template>
            </div>
          </div>
          <textarea v-if="editingTranscriptId === t.id" v-model="transcriptText" class="edit-area" rows="8"></textarea>
          <pre v-else class="doc-content small">{{ t.content }}</pre>
        </div>
      </div>

      <!-- 附件 -->
      <div class="section">
        <div class="section-head">
          <h3>附件</h3>
          <button class="mini-btn" @click="pickAttachment">＋ 添加附件</button>
          <input id="meeting-attach-input" type="file" hidden @change="onAttachmentPicked" />
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
      <div class="mtg-toolbar">
        <input
          v-model="query"
          class="search-input"
          placeholder="全文检索（标题 / 纪要 / 转录，支持中文）…"
          data-testid="mtg-search"
          @input="onSearchInput"
          @keydown.enter="onSearch"
        />
        <button class="new-btn" data-testid="mtg-new" @click="creating = true">＋ 新建会议</button>
      </div>

      <!-- 新建表单 -->
      <div v-if="creating" class="card new-form" data-testid="mtg-new-form">
        <div class="form-row"><label>标题</label><input v-model="form.title" placeholder="会议标题（必填）" /></div>
        <div class="form-row"><label>日期</label><input v-model="form.date" type="date" /></div>
        <div class="form-row"><label>地点</label><input v-model="form.location" placeholder="会议地点（可选）" /></div>
        <div class="form-row"><label>参会人</label><input v-model="form.attendees" placeholder="逗号分隔（可选）" /></div>
        <div class="form-actions">
          <button class="primary-btn" @click="onCreate">创建并打开</button>
          <button class="ghost-btn" @click="creating = false">取消</button>
        </div>
      </div>

      <!-- 空态 -->
      <div v-if="shown.length === 0" class="card empty" data-testid="mtg-empty">
        <template v-if="isSearchMode">
          <p class="empty-title">没有找到与「{{ query }}」相关的会议</p>
          <p class="empty-hint">换个关键词试试——检索覆盖标题、纪要与转录。</p>
        </template>
        <template v-else>
          <p class="empty-title">还没有会议档案</p>
          <p class="empty-hint">点击「＋ 新建会议」创建条目：写纪要、导入转录文本（.txt/.srt）、挂附件。全部数据保存在本机，断网可用。</p>
        </template>
      </div>

      <!-- 列表 / 命中 -->
      <div v-else class="mtg-list">
        <button v-for="m in shown" :key="m.id" class="mtg-item card" @click="openMeeting(m.id)">
          <div class="mtg-row1">
            <span class="mtg-title">{{ m.title }}</span>
            <span class="mtg-date">{{ fmtDate(m.meetingDate) }}</span>
          </div>
          <p v-if="m.snippet" class="mtg-snippet">
            <template v-if="m.highlight">
              {{ m.snippet.slice(0, m.highlight.start) }}<mark class="hl">{{ m.snippet.slice(m.highlight.start, m.highlight.end) }}</mark>{{ m.snippet.slice(m.highlight.end) }}
            </template>
            <template v-else>{{ m.snippet }}</template>
          </p>
          <div class="mtg-meta">
            <span v-if="m.location" class="mtg-loc">{{ m.location }}</span>
            <span v-if="isSearchMode" class="mtg-hit">命中：{{ m.hitSource === 'title' ? '标题' : m.hitSource === 'minutes' ? '纪要' : '转录' }}</span>
          </div>
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.mtg {
  max-width: 760px;
  margin: 0 auto;
}
.mtg h1 {
  font-size: 20px;
  font-weight: var(--font-weight-semibold);
  margin-bottom: var(--space-5);
}
.card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
}
.mtg-toolbar {
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
.new-form {
  padding: var(--space-4);
  margin-bottom: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.form-row {
  display: grid;
  grid-template-columns: 64px 1fr;
  align-items: center;
  gap: var(--space-3);
}
.form-row label {
  font-size: var(--font-size-sm);
  color: var(--color-text-regular);
}
.form-row input {
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
.mtg-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.mtg-item {
  display: block;
  width: 100%;
  padding: var(--space-4);
  text-align: left;
  cursor: pointer;
  transition: border-color var(--duration-fast) var(--ease-out);
}
.mtg-item:hover {
  border-color: rgba(var(--color-primary-rgb), 0.5);
}
.mtg-row1 {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: var(--space-3);
}
.mtg-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}
.mtg-date {
  flex-shrink: 0;
  font-size: 11px;
  color: var(--color-text-placeholder);
}
.mtg-snippet {
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
.mtg-meta {
  margin-top: var(--space-2);
  display: flex;
  gap: var(--space-3);
  font-size: 10px;
  color: var(--color-text-placeholder);
}
.mtg-hit {
  color: var(--color-primary);
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
.detail-meta {
  margin: var(--space-2) 0 0;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
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
.section-actions {
  display: flex;
  gap: var(--space-2);
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
.section-empty {
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
}
.transcript-item {
  border: 1px dashed var(--color-border-light);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  margin-bottom: var(--space-2);
}
.transcript-meta {
  flex: 1;
  font-size: 10px;
  color: var(--color-text-placeholder);
  font-family: var(--font-family-mono);
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
.doc-content.small {
  font-size: var(--font-size-xs);
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
