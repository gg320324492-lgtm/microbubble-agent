<!--
  DriveSharesPanel.vue — 批次⑩.88 (2026-09-08 选型 A) 分享中 inline 面板
  列出当前所有生效的分享链接 (文件 + 文件夹): 路径 / 到期 (<24h 橙色预警) / 复制 / 撤销
  数据: GET /api/v1/drive/shares/active; 撤销后 emit('changed') 通知父层刷计数与树
-->
<template>
  <div class="drive-panel">
    <div class="drive-panel-header is-share">
      <h3 class="drive-panel-title">🔗 分享中 — {{ rows.length }} 个生效链接 · 撤销后立即失效</h3>
    </div>

    <div v-if="loading" class="sp-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>正在加载分享列表…</span>
    </div>
    <div v-else-if="loadError" class="sp-error">
      <p>{{ loadError }}</p>
      <el-button size="small" @click="fetchShares">重试</el-button>
    </div>
    <div v-else-if="rows.length === 0" class="sp-empty">
      <p class="sp-empty-title">当前没有正在分享的内容</p>
      <p class="sp-empty-hint">在文件/文件夹的「分享」中生成链接后，会出现在这里</p>
    </div>
    <div v-else class="sp-list">
      <div v-for="row in rowsWithExp" :key="row.key" class="sp-row">
        <span class="ic">{{ row.kind === 'folder' ? '📁' : '📄' }}</span>
        <div class="nm-wrap">
          <span class="nm" :title="row.name">{{ row.name }}</span>
          <small class="path">{{ row.pathLabel }}</small>
        </div>
        <span class="type-tag">{{ row.kind === 'folder' ? '文件夹' : '文件' }}</span>
        <span class="exp" :class="{ soon: row.expiresSoon }">{{ row.expLabel }}</span>
        <span class="act">
          <button class="sp-btn" :disabled="copiedKey === row.key" @click="copyLink(row)">
            {{ copiedKey === row.key ? '已复制' : '复制链接' }}
          </button>
          <button class="sp-btn danger" :disabled="revokingKey === row.key" @click="revoke(row)">
            {{ revokingKey === row.key ? '撤销中…' : '撤销' }}
          </button>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
// 样式与 DriveTrashPanel 同构 (drive-panel + is-share 色系走 drive-view.css)
import '@/views/drive/drive-view.css'
import { computed, onMounted, ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { useFolderTree } from '@/composables/useFolderTree'

const emit = defineEmits(['changed'])

const { findFolderById } = useFolderTree()

const loading = ref(false)
const loadError = ref(null)
const folders = ref([])
const files = ref([])
const copiedKey = ref(null)
const revokingKey = ref(null)

function pathLabel(folderId, ownName) {
  if (folderId == null) return '团队共享盘 · 顶层'
  const parts = []
  let node = findFolderById(folderId)
  while (node) {
    parts.unshift(node.name)
    node = node.parent_id != null ? findFolderById(node.parent_id) : null
  }
  return parts.length ? parts.join(' / ') : ownName
}

const rows = computed(() => {
  const out = []
  for (const f of folders.value) {
    out.push({
      key: `folder-${f.id}`, kind: 'folder', id: f.id, shareId: f.share_id,
      name: f.name, token: f.token, expiresAt: f.expires_at,
      pathLabel: pathLabel(f.path ? folderIdFromPath(f.path) : null, f.name),
    })
  }
  for (const f of files.value) {
    out.push({
      key: `file-${f.id}`, kind: 'file', id: f.id,
      name: f.name, token: f.token, expiresAt: f.expires_at,
      pathLabel: f.folder_id != null ? pathLabel(f.folder_id, f.name) : '团队共享盘 · 顶层',
    })
  }
  return out.sort((a, b) => {
    if (!a.expiresAt) return 1
    if (!b.expiresAt) return -1
    return a.expiresAt.localeCompare(b.expiresAt)
  })
})

// folders.path 物化格式 '/336/339/' → 直接父 id
function folderIdFromPath(path) {
  const parts = String(path).split('/').filter(Boolean)
  return parts.length ? Number(parts[parts.length - 1]) : null
}

function expInfo(iso) {
  if (!iso) return { label: '永久', soon: false }
  const exp = new Date(iso).getTime()
  const diff = exp - Date.now()
  if (diff <= 0) return { label: '已过期', soon: true }
  if (diff < 24 * 3600 * 1000) {
    const h = Math.floor(diff / 3600000)
    return { label: `${h > 0 ? h + ' 小时' : Math.floor(diff / 60000) + ' 分钟'}后到期`, soon: true }
  }
  const d = new Date(iso)
  return { label: `${d.getMonth() + 1}-${d.getDate()} 到期`, soon: false }
}

// 模板用 row.expLabel / row.expiresSoon: 在 rows 计算尾部统一补充
const rowsWithExp = computed(() =>
  rows.value.map((r) => {
    const info = expInfo(r.expiresAt)
    return { ...r, expLabel: info.label, expiresSoon: info.soon }
  })
)

async function fetchShares() {
  loading.value = true
  loadError.value = null
  try {
    const resp = await axios.get('/api/v1/drive/shares/active')
    folders.value = resp.data?.folders || []
    files.value = resp.data?.files || []
  } catch (e) {
    loadError.value = e.response?.data?.error?.message || e.message || '分享列表加载失败'
  } finally {
    loading.value = false
  }
}

async function copyLink(row) {
  const url = `${window.location.origin}/drive/share/${row.token}`
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(url)
    } else {
      const ta = document.createElement('textarea')
      ta.value = url
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    copiedKey.value = row.key
    ElMessage.success('链接已复制')
    setTimeout(() => (copiedKey.value = null), 2000)
  } catch {
    ElMessage.error('复制失败, 请手动复制: ' + url)
  }
}

async function revoke(row) {
  revokingKey.value = row.key
  try {
    if (row.kind === 'folder') {
      await axios.delete(`/api/v1/folders/${row.id}/share/${row.shareId}`)
    } else {
      await axios.delete(`/api/v1/drive/files/${row.id}/share-link`)
    }
    ElMessage.success(`已撤销「${row.name}」的分享链接`)
    await fetchShares()
    emit('changed')  // 父层刷新侧栏计数 + 树 (文件夹可见性回团队)
  } catch (e) {
    ElMessage.error(e.response?.data?.error?.message || e.response?.data?.detail || e.message || '撤销失败')
  } finally {
    revokingKey.value = null
  }
}

onMounted(fetchShares)
</script>

<script>
export default { name: 'DriveSharesPanel' }
</script>

<style scoped>
/* is-share 头部色系: 与 trash (danger) 同构的 teal 提示条 */
.drive-panel-header.is-share { background: linear-gradient(135deg, #0e766e, #12897c); }
.sp-loading, .sp-error, .sp-empty { display: flex; flex-direction: column; align-items: center;
  gap: 10px; padding: 48px 0; color: var(--color-text-secondary); }
.sp-empty-title { margin: 0; font-size: 14px; color: var(--color-text-regular); }
.sp-empty-hint { margin: 0; font-size: 12px; }
.sp-list { display: flex; flex-direction: column; gap: 8px; padding: 4px 2px 16px; }
.sp-row { display: flex; align-items: center; gap: 10px; padding: 9px 12px;
  border: 1px solid var(--color-border); border-radius: 8px; background: #fafbfa; font-size: 12.5px; }
.sp-row .ic { flex: none; }
.nm-wrap { flex: 1; min-width: 0; }
.sp-row .nm { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  color: var(--color-text-primary); font-weight: 500; }
.sp-row .path { display: block; font-size: 10.5px; color: var(--color-text-placeholder);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.type-tag { flex: none; font-size: 10px; padding: 2px 7px; border-radius: 999px;
  background: #f0f9f7; border: 1px solid #cbe4dc; color: #0b5c43; }
.exp { flex: none; font-family: var(--font-mono, Consolas, monospace); font-size: 10.5px;
  color: var(--color-text-secondary); }
.exp.soon { color: var(--color-warning); font-weight: 700; }
.act { flex: none; display: flex; gap: 6px; }
.sp-btn { font: inherit; font-size: 11.5px; border-radius: 6px; padding: 4px 10px; cursor: pointer;
  border: 1px solid var(--color-border); background: #fff; color: var(--color-text-regular);
  transition: all .15s; }
.sp-btn:disabled { opacity: .55; cursor: default; }
.sp-btn:hover:not(:disabled) { border-color: #b8e0db; color: #0e766e; }
.sp-btn.danger { border-color: #fbc4c4; color: var(--color-danger, #f56c6c); }
.sp-btn.danger:hover:not(:disabled) { background: #fff5f5; }
</style>
