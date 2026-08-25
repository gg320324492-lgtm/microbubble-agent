<template>
  <div class="file-library" data-testid="file-library">
    <header class="file-library__header">
      <h1>文件库工作区</h1>
      <p class="file-library__hint">
        浏览 / 编辑已导入的文件。每次保存会生成一个新版本（v1 → v2 → v3…）。
      </p>
    </header>

    <div class="file-library__toolbar">
      <label>
        文件
        <select v-model="selectedFile" data-testid="file-select" @change="loadFile">
          <option value="">选择文件…</option>
          <option v-for="f in files" :key="f.path" :value="f.path">{{ f.name }}</option>
        </select>
      </label>
      <span v-if="version" data-testid="file-version" class="file-library__version">当前版本 v{{ version }}</span>
      <button
        data-testid="file-save"
        :disabled="!selectedFile || !dirty || saving"
        @click="save"
      >
        {{ saving ? '保存中…' : '保存（生成新版本）' }}
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
      已保存，新版本 v{{ version }}（{{ lastSavedAt }}）
    </p>
    <p v-if="lastError" class="file-library__error">{{ lastError }}</p>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

interface FileEntry {
  path: string
  name: string
}

interface FileReadResult {
  content: string
  version: number
}

interface WindowWorkspace {
  listFiles?: () => Promise<FileEntry[]>
  readFile?: (path: string) => Promise<FileReadResult>
  saveFile?: (path: string, content: string) => Promise<FileReadResult>
}

const files = ref<FileEntry[]>([])
const selectedFile = ref<string>('')
const content = ref<string>('')
const originalContent = ref<string>('')
const version = ref<number>(0)
const dirty = ref(false)
const saving = ref(false)
const lastSavedAt = ref<string>('')
const lastError = ref<string>('')

watch(content, (val) => {
  dirty.value = val !== originalContent.value
})

const bridge = (): WindowWorkspace | undefined =>
  (globalThis as unknown as { window?: { workspace?: WindowWorkspace } }).window?.workspace

async function loadFiles(): Promise<void> {
  const w = bridge()
  if (!w?.listFiles) return
  files.value = await w.listFiles()
}

async function loadFile(): Promise<void> {
  const w = bridge()
  if (!selectedFile.value || !w?.readFile) return
  try {
    const r = await w.readFile(selectedFile.value)
    content.value = r.content
    originalContent.value = r.content
    version.value = r.version
    dirty.value = false
    lastSavedAt.value = ''
    lastError.value = ''
  } catch (err) {
    lastError.value = err instanceof Error ? err.message : String(err)
  }
}

async function save(): Promise<void> {
  const w = bridge()
  if (!selectedFile.value || !w?.saveFile) return
  saving.value = true
  try {
    const r = await w.saveFile(selectedFile.value, content.value)
    version.value = r.version
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

onMounted(loadFiles)

defineExpose({ files, selectedFile, content, version, dirty, loadFile, loadFiles, save })
</script>

<style scoped>
.file-library { padding: 1.5rem; max-width: 1080px; }
.file-library__header h1 { margin: 0 0 0.5rem; font-size: 1.5rem; }
.file-library__hint { color: #555; font-size: 0.9rem; }
.file-library__toolbar { display: flex; align-items: center; gap: 0.75rem; margin: 1rem 0; }
select { padding: 0.35rem 0.5rem; border: 1px solid #ccc; border-radius: 4px; background: white; }
.file-library__version { padding: 0.2rem 0.6rem; background: #eef2ff; color: #4338ca; border-radius: 999px; font-size: 0.8rem; }
button[data-testid="file-save"] { padding: 0.4rem 1rem; border: 0; border-radius: 4px; background: #2563eb; color: white; cursor: pointer; }
button[data-testid="file-save"]:disabled { background: #cbd5e1; cursor: not-allowed; }
textarea { width: 100%; min-height: 320px; padding: 0.75rem; border: 1px solid #ccc; border-radius: 6px; font-family: ui-monospace, monospace; font-size: 0.85rem; resize: vertical; }
.file-library__empty { padding: 1rem; color: #6b7280; }
.file-library__saved { color: #16a34a; font-size: 0.85rem; }
.file-library__error { color: #dc2626; font-size: 0.85rem; }
</style>
