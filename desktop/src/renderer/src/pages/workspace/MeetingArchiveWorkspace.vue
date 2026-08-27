<template>
  <div class="meeting-archive" data-testid="meeting-archive">
    <header class="meeting-archive__header">
      <h1>会议档案工作区</h1>
      <p class="meeting-archive__hint">
        浏览 / 编辑已导入的会议 Markdown。修改仅保存在桌面端。
      </p>
    </header>

    <div class="meeting-archive__toolbar">
      <label>
        会议
        <select v-model="selectedMeeting" data-testid="meeting-select" @change="loadMeeting">
          <option value="">选择会议…</option>
          <option v-for="m in meetings" :key="m.id" :value="String(m.id)">{{ m.title }}</option>
        </select>
      </label>
      <span v-if="selectedMeetingData" class="meeting-archive__meta">
        {{ formatDate(selectedMeetingData.start_time_epoch) }}
        <span v-if="selectedMeetingData.location"> · {{ selectedMeetingData.location }}</span>
        · {{ statusLabel(selectedMeetingData.status) }}
      </span>
      <button
        data-testid="meeting-save"
        :disabled="!selectedMeeting || !dirty || saving"
        @click="save"
      >
        {{ saving ? '保存中…' : '保存' }}
      </button>
    </div>

    <textarea
      v-if="selectedMeeting"
      v-model="content"
      data-testid="meeting-editor"
      rows="20"
      spellcheck="false"
    />
    <p v-else class="meeting-archive__empty">未选择会议。</p>

    <p v-if="lastSavedAt" class="meeting-archive__saved" data-testid="saved-at">
      已保存于 {{ lastSavedAt }}
    </p>
    <p v-if="lastError" class="meeting-archive__error">{{ lastError }}</p>
  </div>
</template>

<script setup lang="ts">
// [类 20.204] 2026-08-28: MeetingArchiveWorkspace 真实数据接入.
//   之前用 window.workspace.listMeetings() (不存在, 永远空).
//   改为: 直接读 desktop_meetings (21 行真实会议), 用 summary + key_points_json + decisions_json + transcript_web_url
//         拼出 Markdown 内容给 textarea 编辑. 保存时写回 summary (本地桌面, 不回传 web).
import { computed, onMounted, ref, watch } from 'vue'

interface Meeting {
  id: number
  title: string
  status: string
  start_time_epoch: number | null
  location: string | null
  summary: string | null
  key_points_json: string | null
  decisions_json: string | null
  transcript_web_url: string | null
}

const STATUS_LABELS: Record<string, string> = {
  scheduled: '已排期',
  recording: '录音中',
  processing: '处理中',
  completed: '已完成',
  error: '处理失败'
}

function parseJsonArray(raw: string | null): string[] {
  if (!raw) return []
  try {
    const v = JSON.parse(raw)
    return Array.isArray(v) ? v : []
  } catch { return [] }
}

function formatDate(epoch: number | null): string {
  if (!epoch) return ''
  return new Date(epoch).toLocaleString('zh-CN', { hour12: false })
}

function toMarkdown(m: Meeting): string {
  const lines: string[] = []
  lines.push(`# ${m.title}`)
  if (m.start_time_epoch) lines.push(`\n**时间**: ${formatDate(m.start_time_epoch)}`)
  if (m.location) lines.push(`**地点**: ${m.location}`)
  if (m.transcript_web_url) lines.push(`**转录原文**: ${m.transcript_web_url}`)
  lines.push('')
  if (m.summary) {
    lines.push('## 摘要')
    lines.push(m.summary)
    lines.push('')
  }
  const keyPoints = parseJsonArray(m.key_points_json)
  if (keyPoints.length > 0) {
    lines.push('## 关键要点')
    for (const kp of keyPoints) lines.push(`- ${kp}`)
    lines.push('')
  }
  const decisions = parseJsonArray(m.decisions_json)
  if (decisions.length > 0) {
    lines.push('## 决议事项')
    for (const d of decisions) lines.push(`- ${d}`)
    lines.push('')
  }
  return lines.join('\n')
}

const meetings = ref<Meeting[]>([])
const selectedMeeting = ref<string>('')
const content = ref<string>('')
const originalContent = ref<string>('')
const lastSavedAt = ref<string>('')
const lastError = ref<string>('')
const saving = ref(false)
const dirty = ref(false)

const selectedMeetingData = computed(() => meetings.value.find((x) => String(x.id) === selectedMeeting.value))

watch(content, (val) => {
  dirty.value = val !== originalContent.value
})

type Api = { database: { query: <T>(p: { sql: string; params?: unknown[] }) => Promise<{ rows: T[] }>; update: (p: { sql: string; params?: unknown[] }) => Promise<{ changes: number }> } }
const bridge = (): Api | undefined =>
  (globalThis as unknown as { window?: { api?: Api } }).window?.api

async function loadMeetings(): Promise<void> {
  const api = bridge()
  if (!api?.database) { lastError.value = '数据库 API 不可用'; return }
  try {
    const { rows } = await api.database.query<Meeting>({
      sql: `SELECT id, title, status, start_time_epoch, location, summary,
                   key_points_json, decisions_json, transcript_web_url
            FROM desktop_meetings
            ORDER BY start_time_epoch DESC
            LIMIT 100`
    })
    meetings.value = rows
  } catch (err) {
    lastError.value = err instanceof Error ? err.message : String(err)
  }
}

async function loadMeeting(): Promise<void> {
  if (!selectedMeeting.value) return
  const m = meetings.value.find((x) => String(x.id) === selectedMeeting.value)
  if (!m) return
  const md = toMarkdown(m)
  content.value = md
  originalContent.value = md
  dirty.value = false
  lastSavedAt.value = ''
  lastError.value = ''
}

async function save(): Promise<void> {
  if (!selectedMeeting.value) return
  const m = meetings.value.find((x) => String(x.id) === selectedMeeting.value)
  if (!m) return
  saving.value = true
  try {
    const api = bridge()
    if (!api?.database) throw new Error('数据库 API 不可用')
    await api.database.update({
      sql: 'UPDATE desktop_meetings SET summary = ? WHERE id = ?',
      params: [content.value, m.id]
    })
    m.summary = content.value
    originalContent.value = content.value
    dirty.value = false
    lastSavedAt.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
    lastError.value = ''
  } catch (err) {
    lastError.value = err instanceof Error ? err.message : String(err)
  } finally {
    saving.value = false
  }
}

onMounted(loadMeetings)

function statusLabel(s: string): string {
  return STATUS_LABELS[s] ?? s
}
defineExpose({ meetings, loadMeetings })
</script>

<style scoped>
.meeting-archive { padding: 1.5rem; max-width: 1080px; }
.meeting-archive__header h1 { margin: 0 0 0.5rem; font-size: 1.5rem; }
.meeting-archive__hint { color: #555; font-size: 0.9rem; }
.meeting-archive__toolbar { display: flex; align-items: center; gap: 0.75rem; margin: 1rem 0; flex-wrap: wrap; }
.meeting-archive__meta { color: #6b7280; font-size: 0.85rem; }
select { padding: 0.35rem 0.5rem; border: 1px solid #ccc; border-radius: 4px; background: white; }
button[data-testid="meeting-save"] { padding: 0.4rem 1rem; border: 0; border-radius: 4px; background: #2563eb; color: white; cursor: pointer; }
button[data-testid="meeting-save"]:disabled { background: #cbd5e1; cursor: not-allowed; }
textarea { width: 100%; min-height: 320px; padding: 0.75rem; border: 1px solid #ccc; border-radius: 6px; font-family: ui-monospace, monospace; font-size: 0.85rem; resize: vertical; }
.meeting-archive__empty { padding: 1rem; color: #6b7280; }
.meeting-archive__saved { color: #16a34a; font-size: 0.85rem; }
.meeting-archive__error { color: #dc2626; font-size: 0.85rem; }
</style>