<script setup lang="ts">
// M2-3c 远程网盘（最小可用实现）
//
// 说明：引导态文案**全部来自主进程集中状态机**（cloudGuidance），本组件不硬编码「绑定」措辞
// —— 后续统一登录把语义切为「未登录」时，只改状态机即可。
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

interface DriveItem {
  id: number
  title: string
  fileName: string
  fileType: string
  fileSize: number
  folderId: number | null
  visibility: string | null
  ownerName: string | null
}

interface DriveState {
  state: 'ready' | 'unbound' | 'offline' | 'expired'
  title: string
  hint: string
  canOpenSettings: boolean
  actionLabel: string
  baseUrl?: string
  username?: string | null
}

const gate = ref<DriveState | null>(null)
const items = ref<DriveItem[]>([])
const loading = ref(false)
const uploading = ref(false)
const progress = ref<{ percent: number; transferred: number; total: number } | null>(null)
const pending = ref<{ uploadId: string; filename: string; uploadedChunks: number[]; totalChunks: number }[]>([])
const blocked = computed(() => (gate.value?.state ?? 'ready') !== 'ready')

function fmtSize(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`
}

async function loadState(): Promise<void> {
  try {
    gate.value = (await window.api.drive.state()) as DriveState
  } catch {
    gate.value = { state: 'ready', title: '', hint: '', canOpenSettings: false, actionLabel: '' }
  }
}

async function loadList(): Promise<void> {
  if (blocked.value) return
  loading.value = true
  try {
    const page = (await window.api.drive.list(null)) as { items?: DriveItem[] }
    items.value = Array.isArray(page?.items) ? page.items : []
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadPending(): Promise<void> {
  try {
    pending.value = ((await window.api.drive.pendingUploads()) as typeof pending.value) ?? []
  } catch {
    pending.value = []
  }
}

/** 上传（选择本地文件 → 主进程分块/续传；进度经事件推送） */
async function pickAndUpload(): Promise<void> {
  const input = document.createElement('input')
  input.type = 'file'
  input.onchange = async () => {
    const f = input.files?.[0]
    if (!f) return
    // Electron 下 File 带 path（webUtils）；无则用 name 兜底提示
    const filePath = (f as File & { path?: string }).path ?? ''
    if (!filePath) {
      ElMessage.warning('无法读取本地路径，请改用桌面端文件选择入口')
      return
    }
    uploading.value = true
    progress.value = { percent: 0, transferred: 0, total: f.size }
    try {
      await window.api.drive.upload({ filePath, parentId: null })
      ElMessage.success('上传完成')
      await loadList()
      await loadPending()
    } catch (e) {
      ElMessage.error(e instanceof Error ? e.message : '上传失败')
      await loadPending() // 中断留痕：可在「未完成上传」继续
    } finally {
      uploading.value = false
      progress.value = null
    }
  }
  input.click()
}

async function rename(item: DriveItem): Promise<void> {
  try {
    const { value } = await ElMessageBox.prompt('新名称', '重命名', { inputValue: item.title })
    if (!value) return
    await window.api.drive.rename(item.id, value)
    await loadList()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e instanceof Error ? e.message : '重命名失败')
  }
}

async function remove(item: DriveItem): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定删除「${item.title}」？`, '删除确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await window.api.drive.remove(item.id)
    await loadList()
    ElMessage.success('已删除')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '删除失败')
  }
}

function openSettings(): void {
  location.hash = '/app/settings'
}

onMounted(async () => {
  // 上传进度事件（主进程 → 渲染层）
  window.api.drive.onProgress((p) => {
    progress.value = p as { percent: number; transferred: number; total: number }
  })
  await loadState()
  if (blocked.value) return
  await loadList()
  await loadPending()
})
</script>

<template>
  <div class="drive">
    <!-- M2-3c：数据源引导态（文案来自主进程集中状态机，组件不硬编码措辞） -->
    <div v-if="blocked" class="drive-gate" data-testid="drive-source-gate">
      <h1>{{ gate?.title }}</h1>
      <p>{{ gate?.hint }}</p>
      <button v-if="gate?.canOpenSettings" class="ghost-btn" data-testid="drive-open-settings" @click="openSettings">
        {{ gate?.actionLabel }}
      </button>
    </div>

    <template v-else>
      <header class="drive-head">
        <h1>网盘</h1>
        <div class="drive-actions">
          <button class="btn-primary" data-testid="drive-upload" :disabled="uploading" @click="pickAndUpload">
            {{ uploading ? '上传中…' : '上传文件' }}
          </button>
          <button class="ghost-btn" data-testid="drive-refresh" @click="loadList">刷新</button>
        </div>
      </header>

      <!-- 上传进度（大文件可见） -->
      <div v-if="progress" class="drive-progress" data-testid="drive-progress">
        <div class="bar"><i :style="{ width: progress.percent + '%' }"></i></div>
        <span>{{ progress.percent }}%（{{ fmtSize(progress.transferred) }} / {{ fmtSize(progress.total) }}）</span>
      </div>

      <!-- 未完成上传（断点续传入口） -->
      <div v-if="pending.length" class="drive-pending" data-testid="drive-pending">
        <p>有 {{ pending.length }} 个未完成的上传，重新上传同一文件会自动续传。</p>
        <ul>
          <li v-for="p in pending" :key="p.uploadId">
            {{ p.filename }}（已传 {{ p.uploadedChunks.length }}/{{ p.totalChunks }} 块）
          </li>
        </ul>
      </div>

      <p v-if="loading" class="drive-hint">加载中…</p>
      <p v-else-if="items.length === 0" class="drive-hint" data-testid="drive-empty">网盘里还没有文件。</p>
      <ul v-else class="drive-list" data-testid="drive-list">
        <li v-for="it in items" :key="it.id" class="drive-item" :data-testid="`drive-item-${it.id}`">
          <span class="drive-name" :title="it.fileName">{{ it.fileName }}</span>
          <span class="drive-size">{{ fmtSize(it.fileSize) }}</span>
          <span v-if="it.visibility" class="drive-vis">{{ it.visibility }}</span>
          <button class="mini-btn" @click="rename(it)">重命名</button>
          <button class="mini-btn danger" @click="remove(it)">删除</button>
        </li>
      </ul>
    </template>
  </div>
</template>

<style scoped>
.drive {
  padding: var(--space-4);
}
.drive-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}
.drive-actions {
  display: flex;
  gap: var(--space-2);
}
.drive-gate {
  max-width: 520px;
  margin: 12vh auto 0;
  text-align: center;
}
.drive-hint {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}
.drive-list {
  list-style: none;
  margin: var(--space-3) 0 0;
  padding: 0;
}
.drive-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--color-border);
  font-size: var(--font-size-sm);
}
.drive-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.drive-size,
.drive-vis {
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
}
.drive-progress .bar {
  height: 6px;
  background: var(--color-border);
  border-radius: var(--radius-full);
  overflow: hidden;
  margin-bottom: var(--space-1);
}
.drive-progress .bar i {
  display: block;
  height: 100%;
  background: var(--color-primary);
}
.drive-pending {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
</style>
