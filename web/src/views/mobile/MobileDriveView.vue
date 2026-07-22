<!--
  MobileDriveView.vue — v2 PR8 M4 移动端独立网盘视图
  2026-07-02

  4 tab (文件/收藏/最近/团队) + 文件夹 chip + 长按 + MobileActionSheet
-->
<template>
  <!-- v2.0 (2026-07-09) Drive 美化: 加 .drive-page 让 fade-slide-up + --color-bg-page 继承 -->
  <div class="mobile-drive-view drive-page">
    <PageHeader title="网盘" :show-back="false">
      <template #actions>
        <button type="button" class="header-btn" aria-label="搜索" @click="showSearch = true">🔍</button>
        <button type="button" class="header-btn" aria-label="命令面板 (Ctrl+K)" @click="showCommandPalette = true">⌘</button>
      </template>
    </PageHeader>

    <nav class="drive-tabs" role="tablist">
      <button v-for="t in tabs" :key="t.name" type="button" role="tab"
        :aria-selected="activeTab === t.name"
        :class="{ active: activeTab === t.name }"
        class="drive-tab-btn" @click="switchTab(t.name)">
        <span class="drive-tab-icon">{{ t.icon }}</span>
        <span class="drive-tab-label">{{ t.label }}</span>
      </button>
    </nav>

    <div v-if="activeTab === 'files'" class="folder-chip-row">
      <button type="button" class="folder-chip" :class="{ active: currentFolderId === null }"
        @click="selectFolder(null)" aria-label="顶级">🏠 我的网盘</button>
      <button v-for="f in folderChips" :key="f.id" type="button" class="folder-chip"
        :class="{ active: currentFolderId === f.id }"
        @click="selectFolder(f.id)" :aria-label="`切换到 ${f.name}`">📁 {{ f.name }}</button>
    </div>

    <div v-if="loadError" class="drive-error"><p>⚠️ 加载失败</p>
      <el-button size="small" @click="refresh">重试</el-button>
    </div>

    <div v-else-if="isEmpty" class="drive-empty">
      <p class="empty-icon">{{ emptyState.icon }}</p>
      <p class="empty-text">{{ emptyState.text }}</p>
      <p class="empty-hint">{{ emptyState.hint }}</p>
    </div>

    <div v-else-if="loading && driveFiles.length === 0" class="drive-loading"><p>加载中...</p></div>

    <div v-else class="drive-grid">
      <LongPressWrapper v-for="file in driveFiles" :key="file.id" :duration="600" @long-press="onLongPressFile(file)">
        <article class="drive-file-card" :data-type="getFileTypeKey(file)"
          :class="{ 'is-private': file.visibility === 'private', 'is-starred': file.is_starred }"
          @click="onFileClick(file)">
          <div class="drive-file-icon">
            <el-icon :size="32"><component :is="getFileIcon(file)" /></el-icon>
          </div>
          <div class="drive-file-info">
            <div class="drive-file-name">{{ file.title || file.file_name || '未命名' }}</div>
            <div class="drive-file-meta">
              <span>{{ formatSize(file.file_size) }}</span>
              <span v-if="file.is_starred">⭐</span>
              <span v-if="file.visibility === 'private'">🔒</span>
            </div>
          </div>
        </article>
      </LongPressWrapper>
    </div>

    <button type="button" class="drive-fab" aria-label="上传文件" @click="onUploadClick">+</button>

    <MobileActionSheet v-model="showActionSheet"
      :title="selectedFile ? (selectedFile.title || selectedFile.file_name) : ''"
      :actions="fileActions" @select="onFileAction" />

    <MobileActionSheet v-model="showUploadMenu" title="上传文件" :actions="uploadActions" @select="onUploadAction" />

    <Teleport to="body">
      <MobileCommandPalette v-if="showCommandPalette" @close="showCommandPalette = false" />
    </Teleport>
  </div>
</template>

<script setup>
// v2.0 (2026-07-09) Drive 美化: 引入 drive-view.css 让 .drive-page fade-slide-up + 文件类型色共享样式生效
// v2.1 (2026-07-22) PR8: onMounted 预拉 /api/v1/mobile/dashboard 一次聚合 (5 sections 1 请求) 替换 N 次独立请求
import '@/views/drive/drive-view.css'
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeader from '@/components/mobile/PageHeader.vue'
import LongPressWrapper from '@/components/mobile/LongPressWrapper.vue'
import MobileActionSheet from '@/components/mobile/MobileActionSheet.vue'
import MobileCommandPalette from '@/views/mobile/MobileCommandPalette.vue'
import { useFolderTree } from '@/composables/useFolderTree'
import { useDriveFiles } from '@/composables/useDriveFiles'
import { formatSize } from '@/utils/format'

const route = useRoute()
const router = useRouter()

const tabs = [
  { name: 'files', icon: '📁', label: '文件' },
  { name: 'starred', icon: '⭐', label: '收藏' },
  { name: 'recent', icon: '🕐', label: '最近' },
  { name: 'team', icon: '🌐', label: '团队' },
]

const activeTab = ref('files')
const currentFolderId = ref(null)
const showCommandPalette = ref(false)
const showSearch = ref(false)
const showUploadMenu = ref(false)
const showActionSheet = ref(false)
const selectedFile = ref(null)

// v2 PR8: 移动端首页聚合 (5 sections 1 请求)
const dashboardData = ref(null)
const dashboardLoading = ref(false)

async function loadDashboard() {
  // 失败隔离: dashboard 失败不阻塞主列表 (主列表用 useDriveFiles 独立拉)
  dashboardLoading.value = true
  try {
    const resp = await axios.get('/api/v1/mobile/dashboard')
    dashboardData.value = resp.data
  } catch (e) {
    console.warn('[MobileDriveView] dashboard 预拉失败 (主流程仍可用):', e?.message)
  } finally {
    dashboardLoading.value = false
  }
}

const { folderTree, fetchTree } = useFolderTree()
const folderChips = computed(() => {
  const flat = []
  function walk(nodes, depth = 0) {
    if (depth > 1) return
    for (const n of (nodes || [])) {
      flat.push({ id: n.id, name: n.name })
      if (n.children && depth < 1) walk(n.children, depth + 1)
    }
  }
  walk(folderTree.value, 0)
  return flat
})

const { driveFiles, total, currentPage, pageSize, loading, loadError, isEmpty, fetchFiles } = useDriveFiles()

function switchTab(name) {
  if (activeTab.value === name) return
  activeTab.value = name
  currentFolderId.value = null
  applyTabQuery()
}

function selectFolder(folderId) {
  currentFolderId.value = folderId
  applyTabQuery()
}

function applyTabQuery() {
  const params = {}
  if (activeTab.value === 'files' && currentFolderId.value !== null) {
    params.folder_id = currentFolderId.value
  } else if (activeTab.value === 'starred') {
    params.starred_only = 'true'
  } else if (activeTab.value === 'recent') {
    params.sort_by = 'updated_at'
    params.sort_order = 'desc'
  } else if (activeTab.value === 'team') {
    params.visibility = 'team'
  }
  fetchFiles(params)
}

function refresh() { applyTabQuery() }

const emptyState = computed(() => {
  switch (activeTab.value) {
    case 'starred': return { icon: '⭐', text: '暂无收藏', hint: '长按文件卡片点 ⭐' }
    case 'recent':  return { icon: '🕐', text: '暂无最近', hint: '' }
    case 'team':    return { icon: '🌐', text: '团队空间暂无文件', hint: '改 visibility 为团队' }
    default:        return { icon: '📂', text: '当前文件夹暂无文件', hint: '点 + 上传' }
  }
})

function onFileClick(file) { router.push(`/drive/preview/${file.id}`) }
function onLongPressFile(file) { selectedFile.value = file; showActionSheet.value = true }

const fileActions = computed(() => {
  if (!selectedFile.value) return []
  const f = selectedFile.value
  return [
    { name: 'preview',  label: '👁 预览' },
    { name: 'download', label: '⬇ 下载' },
    { name: 'rename',   label: '✏ 重命名' },
    { name: 'visibility', label: f.visibility === 'private' ? '🔓 改团队可见' : '🔒 改私有' },
    { name: 'star',     label: f.is_starred ? '☆ 取消收藏' : '⭐ 收藏' },
    { name: 'extract',  label: '📚 提取到知识库' },
    { name: 'delete',   label: '🗑 删除', danger: true },
  ]
})

async function onFileAction(action) {
  if (!selectedFile.value) return
  const file = selectedFile.value
  try {
    switch (action.name) {
      case 'preview': router.push(`/drive/preview/${file.id}`); break
      case 'download': {
        const resp = await axios.get(`/api/v1/drive/files/${file.id}/download`, { responseType: 'blob' })
        const url = window.URL.createObjectURL(new Blob([resp.data]))
        const a = document.createElement('a'); a.href = url; a.download = file.file_name || `file_${file.id}`; a.click()
        window.URL.revokeObjectURL(url)
        ElMessage.success('下载已开始')
        break
      }
      case 'rename': {
        const { value: newName } = await ElMessageBox.prompt('新文件名', '重命名', {
          inputValue: file.file_name || file.title, confirmButtonText: '保存', cancelButtonText: '取消',
        })
        if (newName?.trim()) {
          await axios.put(`/api/v1/drive/files/${file.id}`, { file_name: newName.trim() })
          ElMessage.success('已重命名'); refresh()
        }
        break
      }
      case 'visibility':
        await axios.put(`/api/v1/drive/files/${file.id}`, { visibility: file.visibility === 'private' ? 'team' : 'private' })
        ElMessage.success('可见性已更新'); refresh()
        break
      case 'star':
        await axios.post(`/api/v1/drive/files/${file.id}/toggle-star`)
        ElMessage.success(file.is_starred ? '已取消收藏' : '已收藏'); refresh()
        break
      case 'extract':
        await axios.post(`/api/v1/drive/files/${file.id}/extract-to-kb`, { target_visibility: 'team' })
        ElMessage.success('已提取到知识库'); refresh()
        break
      case 'delete': {
        await ElMessageBox.confirm(`确定删除 "${file.title || file.file_name}"?`, '删除', {
          confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
        })
        await axios.delete(`/api/v1/drive/files/${file.id}`)
        ElMessage.success('已移入回收站'); refresh()
        break
      }
    }
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    ElMessage.error('操作失败: ' + (e.response?.data?.error?.message || e.message))
  }
}

const uploadActions = [
  { name: 'kb', label: '📚 入知识库', subtitle: '上传 + 自动解析' },
  { name: 'drive', label: '📁 入网盘', subtitle: '原始文件归档' },
  { name: 'photo', label: '📷 拍照上传', subtitle: '调用摄像头' },
]
function onUploadClick() { showUploadMenu.value = true }
function onUploadAction(action) {
  ElMessage.info(`"${action.label}" 即将上线, 临时跳 KB`)
  router.push('/knowledge?action=upload&mode=' + action.name)
}

function getFileIcon(file) {
  const name = (file.file_name || file.title || '').toLowerCase()
  const t = file.file_type || ''
  if (t.startsWith('image/') || /\.(jpe?g|png|gif|webp|svg)$/.test(name)) return 'Picture'
  if (t.startsWith('video/') || /\.(mp4|mov|avi|webm)$/.test(name)) return 'VideoPlay'
  if (t.startsWith('audio/') || /\.(mp3|wav|ogg|m4a)$/.test(name)) return 'Headset'
  if (/\.pdf$/.test(name) || t === 'application/pdf') return 'Document'
  if (/\.(docx?|rtf)$/.test(name)) return 'Document'
  if (/\.(xlsx?|csv)$/.test(name)) return 'Grid'
  if (/\.(pptx?|key)$/.test(name)) return 'Present'
  return 'Folder'
}

// v2.0 (2026-07-09) Drive 美化: 文件类型分类 key (与 drive-view.css .drive-file-card[data-type=...] 配套)
const MOBILE_FILE_TYPE_KEYS = {
  'image/': 'image', 'video/': 'video', 'audio/': 'audio',
  'application/pdf': 'pdf',
  '.pdf': 'pdf', '.doc': 'doc', '.docx': 'doc', '.rtf': 'doc',
  '.xls': 'excel', '.xlsx': 'excel', '.csv': 'text',
  '.ppt': 'ppt', '.pptx': 'ppt', '.key': 'ppt',
  '.txt': 'text', '.md': 'text',
  '.jpg': 'image', '.jpeg': 'image', '.png': 'image', '.gif': 'image',
  '.webp': 'image', '.svg': 'image',
  '.mp4': 'video', '.mov': 'video', '.avi': 'video', '.webm': 'video',
  '.mp3': 'audio', '.wav': 'audio', '.ogg': 'audio', '.m4a': 'audio',
}
function getFileTypeKey(file) {
  const name = (file.file_name || file.title || '').toLowerCase()
  const t = file.file_type || ''
  // 先比 MIME 前缀
  for (const [prefix, key] of Object.entries(MOBILE_FILE_TYPE_KEYS)) {
    if (prefix.endsWith('/') && t.startsWith(prefix)) return key
  }
  // 再比扩展名
  for (const ext of Object.keys(MOBILE_FILE_TYPE_KEYS)) {
    if (ext.startsWith('.') && name.endsWith(ext)) return MOBILE_FILE_TYPE_KEYS[ext]
  }
  return 'text'
}

onMounted(() => { fetchTree(); applyTabQuery(); loadDashboard() })
watch(() => route.query.tab, (newTab) => {
  if (newTab && tabs.some(t => t.name === newTab)) switchTab(newTab)
})
</script>

<style scoped>
.mobile-drive-view { padding-top: 0; padding-bottom: 80px; min-height: 100vh; }
.drive-header { position: sticky; top: 0; z-index: 100; }
.drive-tabs { display: flex; gap: 4px; padding: 8px 12px; background: var(--color-bg-card); border-bottom: 1px solid var(--color-border); overflow-x: auto; -webkit-overflow-scrolling: touch; }
.drive-tab-btn { flex: 1; min-width: 64px; padding: 8px 6px; background: transparent; border: none; border-radius: 8px; font-size: 13px; color: var(--color-text-secondary); cursor: pointer; transition: background 0.2s ease, color 0.2s ease; }
.drive-tab-btn.active { background: var(--color-primary-bg); color: var(--color-primary); font-weight: 600; }
.drive-tab-icon { display: block; font-size: 18px; margin-bottom: 2px; }
.folder-chip-row { display: flex; gap: 8px; padding: 8px 12px; overflow-x: auto; background: var(--color-bg-card); border-bottom: 1px solid var(--color-border-light); -webkit-overflow-scrolling: touch; }
.folder-chip { flex-shrink: 0; padding: 6px 12px; background: var(--color-bg-page); border: 1px solid var(--color-border); border-radius: 16px; font-size: 12px; color: var(--color-text-regular); cursor: pointer; white-space: nowrap; }
.folder-chip.active { background: var(--color-primary); color: var(--el-color-white); border-color: var(--color-primary); }
.drive-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; padding: 12px; }
.drive-file-card { display: flex; flex-direction: column; align-items: center; padding: 16px 8px; background: var(--color-bg-card); border: 1px solid var(--color-border-light); border-radius: 8px; cursor: pointer; transition: transform 0.2s ease; }
.drive-file-card:active { transform: scale(0.97); }
.drive-file-card.is-starred { border-color: var(--color-warning); }
.drive-file-card.is-private { opacity: 0.75; }
.drive-file-icon { width: 48px; height: 48px; display: flex; align-items: center; justify-content: center; color: var(--color-primary); margin-bottom: 8px; }
.drive-file-info { width: 100%; text-align: center; }
.drive-file-name { font-size: 13px; color: var(--color-text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.drive-file-meta { display: flex; align-items: center; justify-content: center; gap: 6px; margin-top: 4px; font-size: 11px; color: var(--color-text-secondary); }
.drive-error, .drive-empty, .drive-loading { text-align: center; padding: 60px 20px; color: var(--color-text-secondary); }
.empty-icon { font-size: 48px; margin-bottom: 12px; }
.empty-text { font-size: 15px; margin-bottom: 4px; color: var(--color-text-primary); }
.drive-fab { position: fixed; right: 20px; bottom: 80px; width: 56px; height: 56px; border-radius: 50%; background: var(--color-primary); color: var(--el-color-white); font-size: 28px; border: none; box-shadow: var(--shadow-lg); cursor: pointer; z-index: 200; }
.drive-fab:active { transform: scale(0.95); }
.header-btn { width: 36px; height: 36px; background: transparent; border: none; font-size: 18px; color: var(--color-text-regular); cursor: pointer; border-radius: 6px; }
</style>

<!-- v77 P2.6-B dark 覆盖 (v60-v67 教训: 非 scoped) -->
<style>
[data-theme="dark"] .drive-file-card { background: var(--color-bg-card); border-color: var(--color-border); }
[data-theme="dark"] .folder-chip { background: var(--color-bg-page); color: var(--color-text-regular); }
[data-theme="dark"] .folder-chip.active { background: var(--color-primary); color: var(--el-color-white); }
</style>