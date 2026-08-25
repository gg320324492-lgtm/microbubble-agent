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
          <option v-for="m in meetings" :key="m.id" :value="m.id">{{ m.title }}</option>
        </select>
      </label>
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
import { onMounted, ref, watch } from 'vue'

interface Meeting {
  id: string
  title: string
}

interface WindowWorkspace {
  listMeetings?: () => Promise<Meeting[]>
  readMeeting?: (id: string) => Promise<string>
  saveMeeting?: (id: string, content: string) => Promise<{ ok: boolean }>
}

const meetings = ref<Meeting[]>([])
const selectedMeeting = ref<string>('')
const content = ref<string>('')
const originalContent = ref<string>('')
const lastSavedAt = ref<string>('')
const lastError = ref<string>('')
const saving = ref(false)

const dirty = ref(false)

watch(content, (val) => {
  dirty.value = val !== originalContent.value
})

const bridge = (): WindowWorkspace | undefined =>
  (globalThis as unknown as { window?: { workspace?: WindowWorkspace } }).window?.workspace

async function loadMeetings(): Promise<void> {
  const w = bridge()
  if (!w?.listMeetings) return
  meetings.value = await w.listMeetings()
}

async function loadMeeting(): Promise<void> {
  const w = bridge()
  if (!selectedMeeting.value || !w?.readMeeting) return
  try {
    const md = await w.readMeeting(selectedMeeting.value)
    content.value = md
    originalContent.value = md
    dirty.value = false
    lastSavedAt.value = ''
    lastError.value = ''
  } catch (err) {
    lastError.value = err instanceof Error ? err.message : String(err)
  }
}

async function save(): Promise<void> {
  const w = bridge()
  if (!selectedMeeting.value || !w?.saveMeeting) return
  saving.value = true
  try {
    await w.saveMeeting(selectedMeeting.value, content.value)
    originalContent.value = content.value
    dirty.value = false
    lastSavedAt.value = new Date().toISOString()
    lastError.value = ''
  } catch (err) {
    lastError.value = err instanceof Error ? err.message : String(err)
  } finally {
    saving.value = false
  }
}

onMounted(loadMeetings)

defineExpose({ meetings, selectedMeeting, content, dirty, loadMeeting, loadMeetings, save })
</script>

<style scoped>
.meeting-archive { padding: 1.5rem; max-width: 1080px; }
.meeting-archive__header h1 { margin: 0 0 0.5rem; font-size: 1.5rem; }
.meeting-archive__hint { color: #555; font-size: 0.9rem; }
.meeting-archive__toolbar { display: flex; align-items: center; gap: 0.75rem; margin: 1rem 0; }
select { padding: 0.35rem 0.5rem; border: 1px solid #ccc; border-radius: 4px; background: white; }
button[data-testid="meeting-save"] { padding: 0.4rem 1rem; border: 0; border-radius: 4px; background: #2563eb; color: white; cursor: pointer; }
button[data-testid="meeting-save"]:disabled { background: #cbd5e1; cursor: not-allowed; }
textarea { width: 100%; min-height: 320px; padding: 0.75rem; border: 1px solid #ccc; border-radius: 6px; font-family: ui-monospace, monospace; font-size: 0.85rem; resize: vertical; }
.meeting-archive__empty { padding: 1rem; color: #6b7280; }
.meeting-archive__saved { color: #16a34a; font-size: 0.85rem; }
.meeting-archive__error { color: #dc2626; font-size: 0.85rem; }
</style>
