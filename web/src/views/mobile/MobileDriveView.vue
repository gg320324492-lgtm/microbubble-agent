<!--
  MobileDriveView.vue — v2 PR8 M4 移动端独立网盘视图
  2026-07-02

  v3.0 (2026-07-24 W68 Agent 4) PR8 R4 移动端精修:
    - 长按文件 → 直接显示操作菜单 (preview/download/share/delete) 而非进 detail
      (保留进 detail 的入口: 文件名右上角溢出菜单, 见 drive-file-menu 按钮)
    - 双指捏合 → grid 列数 2/3/4 (捏合=缩小列数, 张开=放大列数, 持久到 localStorage)
    - 顶部搜索栏 sticky (始终可见, 不随滚动消失, 命中后过滤当前 tab)
  4 tab (文件/收藏/最近/团队) + 文件夹 chip + 长按 + MobileActionSheet
-->
<template>
  <!-- v2.0 (2026-07-09) Drive 美化: 加 .drive-page 让 fade-slide-up + --color-bg-page 继承 -->
  <div class="mobile-drive-view drive-page">
    <PageHeader title="网盘" :show-back="false">
      <template #right>
        <span v-if="notificationUnreadCount > 0" class="notification-badge" :aria-label="`${notificationUnreadCount} 条未读通知`">
          🔔 <span class="notification-badge-count">{{ notificationUnreadCount > 99 ? '99+' : notificationUnreadCount }}</span>
        </span>
        <button type="button" class="header-btn" aria-label="搜索" @click="showSearch = true">🔍</button>
        <button type="button" class="header-btn" aria-label="命令面板 (Ctrl+K)" @click="showCommandPalette = true">⌘</button>
      </template>
    </PageHeader>

    <!-- v3.0 (W68 Agent 4) PR8 R4: 顶部搜索栏 sticky, 始终可见, 命中后过滤当前 tab -->
    <div class="drive-sticky-search">
      <div class="drive-sticky-search-input-wrap">
        <span class="drive-sticky-search-icon">🔍</span>
        <input
          v-model="quickSearch"
          type="search"
          class="drive-sticky-search-input"
          placeholder="快速过滤当前列表..."
          aria-label="快速过滤当前列表"
        />
        <button
          v-if="quickSearch"
          type="button"
          class="drive-sticky-search-clear"
          aria-label="清空搜索"
          @click="quickSearch = ''"
        >✕</button>
        <button
          type="button"
          class="drive-sticky-search-grid"
          :aria-label="`当前 ${gridColumns} 列, 点切下一档`"
          @click="cycleGridColumns"
        >▦ {{ gridColumns }}</button>
      </div>
    </div>

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

    <div v-else-if="filteredFiles.length === 0" class="drive-empty">
      <p class="empty-icon">🔍</p>
      <p class="empty-text">没有匹配 "{{ quickSearch }}" 的文件</p>
      <p class="empty-hint">试试清除关键词或切换 tab</p>
    </div>

    <div v-else class="drive-grid" :style="{ gridTemplateColumns: `repeat(${gridColumns}, 1fr)` }"
      @touchstart.passive="onTouchStart"
      @touchmove.passive="onTouchMove"
      @touchend.passive="onTouchEnd">
      <LongPressWrapper v-for="file in filteredFiles" :key="file.id" :duration="600" @long-press="onLongPressFile(file)">
        <article class="drive-file-card" :data-type="getFileTypeKey(file)"
          :class="{ 'is-private': file.visibility === 'private', 'is-starred': file.is_starred }"
          @click="onFileClick(file)">
          <button type="button" class="drive-file-menu" aria-label="更多操作"
            @click.stop="onLongPressFile(file)">⋯</button>
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

    <!-- v3.0 (W68 Agent 4) PR8 R4: Drive 专属 FAB (最近上传照片 + 长按 QR 扫描) -->
    <MobileDriveFAB
      ref="driveFabRef"
      :actions="fabActions"
      :latest-backup="latestBackup"
      @recent-click="onRecentBackupClick"
      @qr-scan-result="onQrScanResult"
    />

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
// v2.2 (2026-07-22) Agent 2: 把 dashboard 5 sections 实际灌进 4 tab, 顶栏显示 notification_unread_count
//                       - dashboard 命中时 tab 切换直接消费预拉数据, 不再 fetchFiles()
//                       - dashboard 失败 (try/catch) 时回退 fetchFiles() (4 独立请求)
//                       - 减少 N 次请求 → 1 次, mobile 网络慢场景首屏体验提升
// v3.0 (2026-07-24 W68 Agent 4) PR8 R4 移动端精修: 长按精简 4 动作菜单 + 双指捏合切换 grid 列数 + sticky 搜索过滤
import '@/views/drive/drive-view.css'
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeader from '@/components/mobile/PageHeader.vue'
import LongPressWrapper from '@/components/mobile/LongPressWrapper.vue'
import MobileActionSheet from '@/components/mobile/MobileActionSheet.vue'
import MobileCommandPalette from '@/views/mobile/MobileCommandPalette.vue'
// v3.0 (W68 Agent 4) PR8 R4: 用 MobileDriveFAB 替换通用 MobileFab, 加最近上传照片 + QR 扫描入口
import MobileDriveFAB from '@/components/mobile/MobileDriveFAB.vue'
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
// dashboardData.value === null 表示预拉失败/未完成, dashboard 失败不阻塞主列表
// 主列表仍走 fetchFiles() 兜底
const dashboardData = ref(null)
const dashboardLoading = ref(false)
const notificationUnreadCount = computed(() => dashboardData.value?.notification_unread_count ?? 0)

async function loadDashboard() {
  // 失败隔离: dashboard 失败不阻塞主列表 (主列表用 useDriveFiles 独立拉)
  dashboardLoading.value = true
  try {
    const resp = await axios.get('/api/v1/mobile/dashboard')
    dashboardData.value = resp.data
  } catch (e) {
    console.warn('[MobileDriveView] dashboard 预拉失败 (主流程仍可用):', e?.message)
    dashboardData.value = null
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

// v2 PR8 Agent 2: dashboard 5 sections 灌进 4 tab 的核心映射
// - starred_files → ⭐ 收藏 tab (覆盖 fetchFiles starred_only=true)
// - team_root_files → 🌐 团队 tab (覆盖 fetchFiles visibility=team)
// - my_uploads → 🕐 最近 tab (覆盖 fetchFiles sort_by=updated_at desc, 我自己的最近上传)
// - recent_activities → 暂不直接灌 tab (UI 当前只显示 drive files; 后续 PR9+ 可做活动流 tab)
// - files tab: 仍走 fetchFiles(folder_id) (需要 folder_id 参数化, dashboard 不带)
// 返回 Array<{id, title, file_name, file_type, ...}> 或 null
function dashboardSectionForTab(tabName) {
  const d = dashboardData.value
  if (!d) return null
  if (tabName === 'starred') return d.starred_files || []
  if (tabName === 'team') return d.team_root_files || []
  if (tabName === 'recent') return d.my_uploads || []
  return null  // files tab 不走 dashboard
}

// v3.0 (W68 Agent 4) PR8 R4: 顶部 sticky 搜索关键词
const quickSearch = ref('')
const filteredFiles = computed(() => {
  const kw = quickSearch.value.trim().toLowerCase()
  if (!kw) return driveFiles.value
  return driveFiles.value.filter((f) => {
    const name = (f.title || f.file_name || '').toLowerCase()
    return name.includes(kw)
  })
})

// v3.0 (W68 Agent 4) PR8 R4: grid 列数 2/3/4, 双指捏合缩, 张开放
// 持久到 localStorage (key: mobile-drive-grid-columns)
const GRID_COLS_OPTIONS = [2, 3, 4]
const GRID_COLS_STORAGE_KEY = 'mobile-drive-grid-columns'
function loadGridColumns() {
  try {
    const v = parseInt(localStorage.getItem(GRID_COLS_STORAGE_KEY) || '2', 10)
    return GRID_COLS_OPTIONS.includes(v) ? v : 2
  } catch { return 2 }
}
const gridColumns = ref(loadGridColumns())
function saveGridColumns(v) {
  try { localStorage.setItem(GRID_COLS_STORAGE_KEY, String(v)) } catch {}
}
function cycleGridColumns() {
  const idx = GRID_COLS_OPTIONS.indexOf(gridColumns.value)
  const next = GRID_COLS_OPTIONS[(idx + 1) % GRID_COLS_OPTIONS.length]
  gridColumns.value = next
  saveGridColumns(next)
  if (typeof navigator !== 'undefined' && typeof navigator.vibrate === 'function') navigator.vibrate(10)
}

// v3.0 (W68 Agent 4) PR8 R4: 双指捏合手势检测 (基于 touchstart/touchmove 两指距离变化)
// 阈值: 距离变化 > 40% 触发一次 (避免频繁切换), 单次操作内只切 1 档
let pinchInitialDistance = 0
let pinchLastDistance = 0
let pinchSwappedThisGesture = false
function getTouchDistance(t1, t2) {
  const dx = t1.clientX - t2.clientX
  const dy = t1.clientY - t2.clientY
  return Math.hypot(dx, dy)
}
function onTouchStart(e) {
  if (e.touches.length !== 2) return
  pinchInitialDistance = getTouchDistance(e.touches[0], e.touches[1])
  pinchLastDistance = pinchInitialDistance
  pinchSwappedThisGesture = false
}
function onTouchMove(e) {
  if (e.touches.length !== 2 || pinchInitialDistance === 0) return
  const d = getTouchDistance(e.touches[0], e.touches[1])
  pinchLastDistance = d
}
function onTouchEnd() {
  if (pinchInitialDistance === 0 || pinchSwappedThisGesture) {
    pinchInitialDistance = 0
    return
  }
  const delta = pinchLastDistance - pinchInitialDistance
  const ratio = delta / pinchInitialDistance
  // 张开 (ratio > 0.4) → 列数 +1 (更多细节); 捏合 (ratio < -0.4) → 列数 -1 (更少卡片)
  const idx = GRID_COLS_OPTIONS.indexOf(gridColumns.value)
  let nextIdx = idx
  if (ratio > 0.4 && idx < GRID_COLS_OPTIONS.length - 1) {
    nextIdx = idx + 1
  } else if (ratio < -0.4 && idx > 0) {
    nextIdx = idx - 1
  }
  if (nextIdx !== idx) {
    gridColumns.value = GRID_COLS_OPTIONS[nextIdx]
    saveGridColumns(GRID_COLS_OPTIONS[nextIdx])
    if (typeof navigator !== 'undefined' && typeof navigator.vibrate === 'function') navigator.vibrate(10)
    pinchSwappedThisGesture = true
  }
  pinchInitialDistance = 0
  pinchLastDistance = 0
}

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
  // v2 PR8 Agent 2: 优先用 dashboard 数据 (1 次聚合替代 4 次独立请求)
  // dashboard 未就绪 (null) 或当前 tab 没对应 section 时回退 fetchFiles
  const sectionData = dashboardSectionForTab(activeTab.value)
  if (sectionData !== null) {
    // 灌进 driveFiles (复用现有渲染逻辑), 不走 fetchFiles
    driveFiles.value = sectionData
    total.value = sectionData.length
    loadError.value = null
    return
  }

  // 兜底: files tab 或 dashboard 失败时走原 fetchFiles 路径
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
function onLongPressFile(file) {
  // v3.0 (W68 Agent 4) PR8 R4: 长按文件直接显示操作菜单 (preview/download/share/delete)
  // 触觉反馈 (CLAUDE.md 2026-06-27 教训)
  if (typeof navigator !== 'undefined' && typeof navigator.vibrate === 'function') navigator.vibrate(10)
  selectedFile.value = file
  showActionSheet.value = true
}

const fileActions = computed(() => {
  if (!selectedFile.value) return []
  const f = selectedFile.value
  // W68 路线 F-3: 加 "查看评论" 入口, 长按菜单升级到 5 个核心动作
  // 顺序: 预览 / 评论 / 下载 / 分享 / 删除 (评论提至第 2 位突出协作价值)
  return [
    { name: 'preview',  label: '👁 预览' },
    { name: 'comments', label: '💬 查看评论' },
    { name: 'download', label: '⬇ 下载' },
    { name: 'share',    label: '🔗 分享' },
    { name: 'delete',   label: '🗑 删除', danger: true },
  ]
})

async function onFileAction(action) {
  if (!selectedFile.value) return
  const file = selectedFile.value
  try {
    switch (action.name) {
      case 'preview': router.push(`/drive/preview/${file.id}`); break
      // W68 路线 F-3: "查看评论" → 跳独立评论页
      case 'comments': router.push(`/drive/file/${file.id}/comments`); break
      case 'download': {
        const resp = await axios.get(`/api/v1/drive/files/${file.id}/download`, { responseType: 'blob' })
        const url = window.URL.createObjectURL(new Blob([resp.data]))
        const a = document.createElement('a'); a.href = url; a.download = file.file_name || `file_${file.id}`; a.click()
        window.URL.revokeObjectURL(url)
        ElMessage.success('下载已开始')
        break
      }
      // v3.0 (W68 Agent 4) PR8 R4: 分享 → 复制链接到剪贴板 (移动端 web Share API 不可用兜底)
      case 'share': {
        const shareUrl = `${window.location.origin}/drive/preview/${file.id}`
        try {
          if (navigator.share) {
            await navigator.share({ title: file.title || file.file_name, url: shareUrl })
            break
          }
          await navigator.clipboard.writeText(shareUrl)
          ElMessage.success('链接已复制')
        } catch (e) {
          if (e?.name === 'AbortError') return
          await navigator.clipboard.writeText(shareUrl).catch(() => {})
          ElMessage.success('链接已复制')
        }
        break
      }
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
const fabActions = [
  { name: 'upload', label: 'Upload file', icon: '📁', handler: onUploadClick },
  { name: 'folder', label: 'New folder', icon: '📂', handler: () => ElMessage.info('Use desktop to create folders') },
  { name: 'share', label: 'Share drive', icon: '🔗', handler: () => ElMessage.info('Select a file to share') },
  { name: 'search', label: 'Search files', icon: '🔍', handler: () => { showSearch.value = true } },
]

function onUploadClick() { showUploadMenu.value = true }
function onUploadAction(action) {
  ElMessage.info(`"${action.label}" 即将上线, 临时跳 KB`)
  router.push('/knowledge?action=upload&mode=' + action.name)
}

// v3.0 (W68 Agent 4) PR8 R4: 最近上传照片 (来自 album-auto-backup, 缺省 null 不显示)
// 数据源: /api/v1/drive/files?sort_by=updated_at&sort_order=desc&file_type=image/*
// 父组件从 useDriveFiles 或独立 fetch 注入, 此处给兜底空值
const latestBackup = ref(null)
const driveFabRef = ref(null)
function onRecentBackupClick(file) {
  // 点击最近上传照片 → 直接预览
  if (file?.id) router.push(`/drive/preview/${file.id}`)
}
function onQrScanResult(text) {
  // QR 扫描结果: 如果是 /drive/preview/<id> 链接, 直接跳转
  if (!text) return
  const m = text.match(/\/drive\/preview\/(\d+)/)
  if (m) {
    router.push(`/drive/preview/${m[1]}`)
    driveFabRef.value?.closeQrScan?.()
  }
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
.drive-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; padding: 12px; touch-action: pan-y; }
.drive-file-card { position: relative; display: flex; flex-direction: column; align-items: center; padding: 16px 8px; background: var(--color-bg-card); border: 1px solid var(--color-border-light); border-radius: 8px; cursor: pointer; transition: transform 0.2s ease; }
.drive-file-card:active { transform: scale(0.97); }
.drive-file-card.is-starred { border-color: var(--color-warning); }
.drive-file-card.is-private { opacity: 0.75; }
.drive-file-menu {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 24px;
  height: 24px;
  padding: 0;
  background: transparent;
  border: none;
  border-radius: 50%;
  color: var(--color-text-secondary);
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.drive-file-menu:active { background: var(--color-bg-hover); }
.drive-file-icon { width: 48px; height: 48px; display: flex; align-items: center; justify-content: center; color: var(--color-primary); margin-bottom: 8px; }
.drive-file-info { width: 100%; text-align: center; }
.drive-file-name { font-size: 13px; color: var(--color-text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.drive-file-meta { display: flex; align-items: center; justify-content: center; gap: 6px; margin-top: 4px; font-size: 11px; color: var(--color-text-secondary); }
.drive-error, .drive-empty, .drive-loading { text-align: center; padding: 60px 20px; color: var(--color-text-secondary); }
.empty-icon { font-size: 48px; margin-bottom: 12px; }
.empty-text { font-size: 15px; margin-bottom: 4px; color: var(--color-text-primary); }
.header-btn { width: 36px; height: 36px; background: transparent; border: none; font-size: 18px; color: var(--color-text-regular); cursor: pointer; border-radius: 6px; }
.notification-badge { display: inline-flex; align-items: center; gap: 4px; padding: 4px 8px; background: var(--color-warning); color: var(--el-color-white); border-radius: 12px; font-size: 11px; font-weight: 600; }
.notification-badge-count { font-variant-numeric: tabular-nums; }

/* v3.0 (W68 Agent 4) PR8 R4: sticky 搜索栏 (始终可见, 不随滚动消失) */
.drive-sticky-search {
  position: sticky;
  top: 0;
  z-index: 90;
  padding: 8px 12px;
  background: var(--color-bg-card);
  border-bottom: 1px solid var(--color-border-light);
}
.drive-sticky-search-input-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--color-bg-page);
  border-radius: var(--radius-md, 8px);
  padding: 8px 10px;
}
.drive-sticky-search-icon { font-size: 14px; color: var(--color-text-secondary); }
.drive-sticky-search-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 14px;
  color: var(--color-text-primary);
  outline: none;
  font-family: inherit;
  min-width: 0;
}
.drive-sticky-search-input::placeholder { color: var(--color-text-placeholder); }
.drive-sticky-search-clear {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--color-border);
  border: none;
  font-size: 11px;
  color: var(--color-text-regular);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  -webkit-tap-highlight-color: transparent;
}
.drive-sticky-search-grid {
  flex-shrink: 0;
  padding: 4px 8px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm, 4px);
  font-size: 12px;
  color: var(--color-text-regular);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.drive-sticky-search-grid:active { background: var(--color-bg-hover); }
</style>

<!-- v77 P2.6-B dark 覆盖 (v60-v67 教训: 非 scoped) -->
<style>
[data-theme="dark"] .drive-file-card { background: var(--color-bg-card); border-color: var(--color-border); }
[data-theme="dark"] .folder-chip { background: var(--color-bg-page); color: var(--color-text-regular); }
[data-theme="dark"] .folder-chip.active { background: var(--color-primary); color: var(--el-color-white); }
[data-theme="dark"] .drive-sticky-search { background: var(--color-bg-card); border-color: var(--color-border); }
[data-theme="dark"] .drive-sticky-search-input-wrap { background: var(--color-bg-page); }
[data-theme="dark"] .drive-sticky-search-grid { background: var(--color-bg-card); border-color: var(--color-border); color: var(--color-text-regular); }
[data-theme="dark"] .drive-file-menu { color: var(--color-text-secondary); }
</style>