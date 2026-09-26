<script setup lang="ts">
// 网盘页（UI1-3 原生还原）— 数据来自父级服务器（M2-3c），本页只做呈现。
//
// 布局对齐父级 web/src/views/DesktopDriveView.vue（工作台形态）：
//   顶栏（搜索 / 新建文件夹 / 上传） → 面包屑（文件夹层级导航） → 拖拽区 + 文件列表/网格
// 能力：拖拽上传（复用 M2-3c 分块通道，含进度）、文件夹进入与返回、下载、重命名、删除。
//
// 引导态文案全部来自主进程集中状态机（guidance.ts），本组件零硬编码措辞。
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ROOT_CRUMB,
  crumbPath,
  currentFolderId,
  enterFolder,
  extractLocalPaths,
  filterItems,
  goToCrumb,
  hasDraggedFiles,
  isDragActive,
  nextDragDepth,
  type Crumb
} from '../composables/useDriveNav'

interface DriveItem {
  id: number
  title: string
  fileName: string
  fileType: string
  fileSize: number
  folderId: number | null
  visibility: string | null
  ownerName: string | null
  /** DL-2：列表列需要上传时间（web 列：名称/大小/上传者/时间） */
  createdAt?: string
  updatedAt?: string
}

interface DriveFolder {
  id: number
  name: string
  parentId: number | null
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

// 导航与搜索
const crumbs = ref<Crumb[]>([ROOT_CRUMB])
const keyword = ref('')
const currentId = computed(() => currentFolderId(crumbs.value))
const breadcrumbText = computed(() => crumbPath(crumbs.value))
const shownItems = computed(() => filterItems(items.value, keyword.value))

// 拖拽（深度计数避免子元素 enter/leave 闪烁）
const dragDepth = ref(0)
const dragActive = computed(() => isDragActive(dragDepth.value))

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

/** 全量文件夹树（DL-3：来自 /folders/tree?scope=team，只拉一次） */
const tree = ref<DriveFolder[]>([])

async function loadTree(): Promise<void> {
  if (blocked.value) return
  try {
    const t = (await window.api.drive.folders()) as DriveFolder[]
    tree.value = Array.isArray(t) ? t : []
  } catch {
    tree.value = []
  }
}

/** 当前目录的子文件夹（从树里按 parentId 筛，避免逐目录请求） */
const subFolders = computed<DriveFolder[]>(() =>
  tree.value.filter((f) => (f.parentId ?? null) === currentId.value)
)

async function loadList(): Promise<void> {
  if (blocked.value) return
  loading.value = true
  try {
    // DL-2：契约参数为 folder_id（根视图不传）；view=team + 排序由服务层统一带上
    const page = (await window.api.drive.list(currentId.value)) as { items?: DriveItem[] }
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

/** 上传一组本地路径（拖拽或文件选择共用） */
async function uploadPaths(paths: { path: string; name: string }[]): Promise<void> {
  if (!paths.length) return
  uploading.value = true
  try {
    for (const f of paths) {
      progress.value = { percent: 0, transferred: 0, total: 0 }
      try {
        await window.api.drive.upload({ filePath: f.path, parentId: currentId.value })
      } catch (e) {
        ElMessage.error(`${f.name}：${e instanceof Error ? e.message : '上传失败'}`)
      }
    }
    ElMessage.success(`已上传 ${paths.length} 个文件`)
    await loadList()
    await loadPending()
  } finally {
    uploading.value = false
    progress.value = null
  }
}

/** 选择本地文件（工具栏上传按钮） */
function pickAndUpload(): void {
  const input = document.createElement('input')
  input.type = 'file'
  input.multiple = true
  input.onchange = () => {
    const files = Array.from(input.files ?? []) as (File & { path?: string })[]
    void uploadPaths(extractLocalPaths(files))
  }
  input.click()
}

/** 新建文件夹 */
async function createFolder(): Promise<void> {
  try {
    const { value } = await ElMessageBox.prompt('文件夹名称', '新建文件夹', { inputValue: '新建文件夹' })
    const name = (value ?? '').trim()
    if (!name) return
    await window.api.drive.createFolder(name, currentId.value)
    await loadList()
    ElMessage.success('已创建')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e instanceof Error ? e.message : '创建失败')
  }
}

function openFolder(f: DriveFolder): void {
  crumbs.value = enterFolder(crumbs.value, { id: f.id, name: f.name })
  keyword.value = ''
  void loadList()
}

function backTo(index: number): void {
  crumbs.value = goToCrumb(crumbs.value, index)
  keyword.value = ''
  void loadList()
}

async function download(item: DriveItem): Promise<void> {
  try {
    const r = (await window.api.drive.download(item.id)) as { bytes?: number }
    ElMessage.success(`已下载（${fmtSize(r?.bytes ?? 0)}）`)
  } catch (e) {
    const msg = e instanceof Error ? e.message : '下载失败'
    if (!msg.includes('取消')) ElMessage.error(msg)
  }
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

// ---- 拖拽上传 ----
function onDragEnter(e: DragEvent): void {
  if (!hasDraggedFiles(e.dataTransfer)) return
  e.preventDefault()
  dragDepth.value = nextDragDepth(dragDepth.value, 'enter')
}
function onDragOver(e: DragEvent): void {
  if (!hasDraggedFiles(e.dataTransfer)) return
  e.preventDefault() // 必须阻止默认，否则浏览器会打开文件
}
function onDragLeave(e: DragEvent): void {
  if (!hasDraggedFiles(e.dataTransfer)) return
  dragDepth.value = nextDragDepth(dragDepth.value, 'leave')
}
function onDrop(e: DragEvent): void {
  if (!hasDraggedFiles(e.dataTransfer)) return
  e.preventDefault()
  dragDepth.value = nextDragDepth(dragDepth.value, 'drop')
  const files = Array.from(e.dataTransfer?.files ?? []) as (File & { path?: string })[]
  const paths = extractLocalPaths(files)
  if (!paths.length) {
    ElMessage.warning('未能读取本地路径，请改用「上传」按钮选择文件')
    return
  }
  void uploadPaths(paths)
}

function openSettings(): void {
  location.hash = '/app/settings'
}

let offProgress: (() => void) | null = null

onMounted(async () => {
  offProgress = window.api.drive.onProgress((p) => {
    progress.value = p as { percent: number; transferred: number; total: number }
  })
  await loadState()
  if (blocked.value) return
  await loadTree()
  await loadList()
  await loadPending()
})

onUnmounted(() => {
  offProgress?.()
})
</script>

<template>
  <div class="drive">
    <!-- 引导态（文案来自主进程集中状态机，组件不硬编码措辞） -->
    <div v-if="blocked" class="drive-gate" data-testid="drive-source-gate">
      <h1>{{ gate?.title }}</h1>
      <p>{{ gate?.hint }}</p>
      <button v-if="gate?.canOpenSettings" class="ghost-btn" data-testid="drive-open-settings" @click="openSettings">
        {{ gate?.actionLabel }}
      </button>
    </div>

    <template v-else>
      <!-- 顶栏：搜索 / 新建文件夹 / 上传 -->
      <header class="drive-head">
        <h1 class="drive-title">网盘</h1>
        <div class="drive-actions">
          <input v-model="keyword" class="drive-search" data-testid="drive-search" placeholder="搜索当前目录" />
          <button class="ghost-btn" data-testid="drive-new-folder" @click="createFolder">新建文件夹</button>
          <button class="btn-primary" data-testid="drive-upload" :disabled="uploading" @click="pickAndUpload">
            {{ uploading ? '上传中…' : '上传' }}
          </button>
          <button class="ghost-btn" data-testid="drive-refresh" @click="loadList">刷新</button>
        </div>
      </header>

      <!-- 面包屑（文件夹层级导航） -->
      <nav class="drive-crumbs" data-testid="drive-crumbs" aria-label="目录路径">
        <template v-for="(c, i) in crumbs" :key="`${i}-${c.id ?? 'root'}`">
          <button class="crumb" :data-testid="`drive-crumb-${i}`" :disabled="i === crumbs.length - 1" @click="backTo(i)">
            {{ c.name }}
          </button>
          <span v-if="i < crumbs.length - 1" class="crumb-sep" aria-hidden="true">/</span>
        </template>
        <span class="drive-crumb-path" data-testid="drive-crumb-path">{{ breadcrumbText }}</span>
      </nav>

      <!-- 拖拽区（拖入高亮 → 松手触发分块上传） -->
      <div
        class="drive-drop"
        :class="{ 'is-active': dragActive }"
        data-testid="drive-dropzone"
        @dragenter="onDragEnter"
        @dragover="onDragOver"
        @dragleave="onDragLeave"
        @drop="onDrop"
      >
        <span class="drive-drop-hint">{{ dragActive ? '松开即上传到当前目录' : '把文件拖到这里上传' }}</span>
      </div>

      <!-- 上传进度 -->
      <div v-if="progress" class="drive-progress" data-testid="drive-progress">
        <div class="bar"><i :style="{ width: progress.percent + '%' }"></i></div>
        <span>{{ progress.percent }}%（{{ fmtSize(progress.transferred) }} / {{ fmtSize(progress.total) }}）</span>
      </div>

      <!-- 未完成上传（断点续传入口） -->
      <div v-if="pending.length" class="drive-pending" data-testid="drive-pending">
        <p>有 {{ pending.length }} 个未完成的上传，重新上传同一文件会自动续传。</p>
        <ul>
          <li v-for="p in pending" :key="p.uploadId">{{ p.filename }}（已传 {{ p.uploadedChunks.length }}/{{ p.totalChunks }} 块）</li>
        </ul>
      </div>

      <p v-if="loading" class="drive-hint">加载中…</p>

      <template v-else>
        <p v-if="!subFolders.length && !shownItems.length" class="drive-hint" data-testid="drive-empty">
          <template v-if="keyword">没有匹配「{{ keyword }}」的文件。</template>
          <template v-else>这个目录还没有内容，拖文件进来或点「上传」。</template>
        </p>

        <!-- 文件夹 -->
        <ul v-if="subFolders.length" class="drive-list" data-testid="drive-folders">
          <li v-for="f in subFolders" :key="`f-${f.id}`" class="drive-item" :data-testid="`drive-folder-${f.id}`">
            <button class="drive-folder-btn" @click="openFolder(f)">📁 {{ f.name }}</button>
          </li>
        </ul>

        <!-- 文件 -->
        <ul v-if="shownItems.length" class="drive-list" data-testid="drive-list">
          <li v-for="it in shownItems" :key="it.id" class="drive-item" :data-testid="`drive-item-${it.id}`">
            <span class="drive-name" :title="it.fileName" data-testid="drive-item-name">{{ it.fileName }}</span>
            <span class="drive-size" data-testid="drive-item-size">{{ fmtSize(it.fileSize) }}</span>
            <span class="drive-owner" data-testid="drive-item-owner">{{ it.ownerName ?? '—' }}</span>
            <span class="drive-time" data-testid="drive-item-time">{{ (it.createdAt ?? '').slice(0, 10) }}</span>
            <span v-if="it.visibility" class="drive-vis">{{ it.visibility }}</span>
            <button class="mini-btn" data-testid="drive-download" @click="download(it)">下载</button>
            <button class="mini-btn" @click="rename(it)">重命名</button>
            <button class="mini-btn danger" @click="remove(it)">删除</button>
          </li>
        </ul>
      </template>
    </template>
  </div>
</template>

<style scoped>
.drive {
  padding: var(--space-4);
  height: 100%;
  overflow-y: auto;
}
.drive-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}
.drive-title {
  margin: 0;
  font-size: var(--font-size-xl);
}
.drive-actions {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}
.drive-search {
  min-width: 180px;
}
.drive-crumbs {
  display: flex;
  align-items: center;
  gap: 4px;
  margin: var(--space-2) 0;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
.crumb {
  background: transparent;
  border: none;
  color: var(--color-primary);
  cursor: pointer;
  font-size: var(--font-size-xs);
  padding: 0 2px;
}
.crumb:disabled {
  color: var(--color-text-primary);
  cursor: default;
}
.crumb-sep {
  color: var(--color-text-secondary);
}
.drive-crumb-path {
  margin-left: auto;
  opacity: 0.6;
}
.drive-drop {
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  text-align: center;
  margin-bottom: var(--space-3);
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  transition: border-color 0.15s, background 0.15s;
}
.drive-drop.is-active {
  border-color: var(--color-primary);
  background: color-mix(in srgb, var(--color-primary) 8%, transparent);
  color: var(--color-primary);
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
.drive-folder-btn {
  background: transparent;
  border: none;
  color: var(--color-text-primary);
  cursor: pointer;
  font-size: var(--font-size-sm);
  padding: 0;
}
.drive-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.drive-size,
.drive-owner,
.drive-time,
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
