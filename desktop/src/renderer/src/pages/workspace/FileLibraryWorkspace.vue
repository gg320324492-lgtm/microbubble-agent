<template>
  <div class="file-library" data-testid="file-library">
    <header class="file-library__header">
      <h1>文件库工作区</h1>
      <p class="file-library__hint">
        浏览 / 编辑已导入的本地文件。修改仅保存在桌面端。
      </p>
    </header>

    <div class="file-library__toolbar">
      <label>
        文件
        <select v-model="selectedFile" data-testid="file-select" @change="loadFile">
          <option value="">选择文件…</option>
          <option v-for="f in files" :key="f.id" :value="String(f.id)">{{ f.name }}</option>
        </select>
      </label>
      <span v-if="selectedFileData" class="file-library__meta">
        {{ formatDate(selectedFileData.created_at_epoch) }}
        <span v-if="selectedFileData.file_type"> · {{ selectedFileData.file_type }}</span>
      </span>
      <button
        data-testid="file-save"
        :disabled="!selectedFile || !dirty || saving"
        @click="save"
      >
        {{ saving ? '保存中…' : '保存' }}
      </button>
    </div>

    <textarea
      v-if="selectedFile"
      v-model="content"
      data-testid="file-editor"
      rows="20"
      spellcheck="false"
    />
    <p v-else class="file-library__empty">未选择文件。</p>

    <p v-if="lastSavedAt" class="file-library__saved" data-testid="saved-at">
      已保存于 {{ lastSavedAt }}
    </p>
    <p v-if="lastError" class="file-library__error">{{ lastError }}</p>
  </div>
</template>

<script setup lang="ts">
// [类 20.205] 2026-08-28: FileLibraryWorkspace 真实数据接入.
//   之前用 window.workspace.listFiles() (不存在, 永远空).
//   改为: 直接读 desktop_knowledge 表 (535 行, file_path/file_name/file_type 字段), 用 content 作可编辑内容.
import { computed, onMounted, ref, watch } from 'vue'

interface KnowledgeFile {
  id: number
  title: string
  content: string
  file_path: string | null
  file_name: string | null
  file_type: string | null
  created_at_epoch: number | null
}

const files = ref<KnowledgeFile[]>([])
const selectedFile = ref<string>('')
const content = ref<string>('')
const originalContent = ref<string>('')
const dirty = ref(false)
const saving = ref(false)
const lastSavedAt = ref<string>('')
const lastError = ref<string>('')

const selectedFileData = computed(() => files.value.find((f) => String(f.id) === selectedFile.value))

watch(content, (val) => {
  dirty.value = val !== originalContent.value
})

function formatDate(epoch: number | null): string {
  if (!epoch) return ''
  return new Date(epoch).toLocaleDateString('zh-CN')
}

type Api = { database: { query: <T>(p: { sql: string; params?: unknown[] }) => Promise<{ rows: T[] }>; update: (p: { sql: string; params?: unknown[] }) => Promise<{ changes: number }> } }
const bridge = (): Api | undefined =>
  (globalThis as unknown as { window?: { api?: Api } }).window?.api

async function loadFiles(): Promise<void> {
  const api = bridge()
  if (!api?.database) { lastError.value = '数据库 API 不可用'; return }
  try {
    const { rows } = await api.database.query<KnowledgeFile>({
      sql: `SELECT id, title, content, file_path, file_name, file_type, created_at_epoch
            FROM desktop_knowledge
            ORDER BY created_at_epoch DESC
            LIMIT 200`
    })
    // 映射成"文件": 用 file_name 优先, 退到 title
    files.value = rows.map((r) => ({ ...r, name: r.file_name && r.file_name !== 'X' ? r.file_name : r.title }))
  } catch (err) {
    lastError.value = err instanceof Error ? err.message : String(err)
  }
}

async function loadFile(): Promise<void> {
  if (!selectedFile.value) return
  const f = files.value.find((x) => String(x.id) === selectedFile.value)
  if (!f) return
  // 拼成 Markdown 头 + 原 content
  const md = `# ${f.title}\n\n${f.content || ''}`
  content.value = md
  originalContent.value = md
  dirty.value = false
  lastSavedAt.value = ''
  lastError.value = ''
}

async function save(): Promise<void> {
  if (!selectedFile.value) return
  const f = files.value.find((x) => String(x.id) === selectedFile.value)
  if (!f) return
  saving.value = true
  try {
    const api = bridge()
    if (!api?.database) throw new Error('数据库 API 不可用')
    // 简化: 把 Markdown 全文存到 content (本地桌面, 不回传 web)
    await api.database.update({
      sql: 'UPDATE desktop_knowledge SET content = ?, updated_at_epoch = ? WHERE id = ?',
      params: [content.value, Math.floor(Date.now() / 1000), f.id]
    })
    f.content = content.value
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

onMounted(loadFiles)
defineExpose({ files, loadFiles })
</script>

<style scoped>
.file-library { padding: 1.5rem; max-width: 1080px; }
.file-library__header h1 { margin: 0 0 0.5rem; font-size: 1.5rem; }
.file-library__hint { color: #555; font-size: 0.9rem; }
.file-library__toolbar { display: flex; align-items: center; gap: 0.75rem; margin: 1rem 0; flex-wrap: wrap; }
.file-library__meta { color: #6b7280; font-size: 0.85rem; }
select { padding: 0.35rem 0.5rem; border: 1px solid #ccc; border-radius: 4px; background: white; }
button[data-testid="file-save"] { padding: 0.4rem 1rem; border: 0; border-radius: 4px; background: #2563eb; color: white; cursor: pointer; }
button[data-testid="file-save"]:disabled { background: #cbd5e1; cursor: not-allowed; }
textarea { width: 100%; min-height: 320px; padding: 0.75rem; border: 1px solid #ccc; border-radius: 6px; font-family: ui-monospace, monospace; font-size: 0.85rem; resize: vertical; }
.file-library__empty { padding: 1rem; color: #6b7280; }
.file-library__saved { color: #16a34a; font-size: 0.85rem; }
.file-library__error { color: #dc2626; font-size: 0.85rem; }
</style>