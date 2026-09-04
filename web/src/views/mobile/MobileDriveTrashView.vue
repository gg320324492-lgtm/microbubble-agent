<template>
  <div class="mobile-drive-trash-view mg-page">
    <PageHeader title="网盘回收站" show-back @back="$router.back()">
      <template #right>
        <button
          v-if="hasAnything"
          type="button"
          class="header-action"
          aria-label="清空回收站"
          title="清空回收站"
          @click="emptyTrash"
        >🧹</button>
      </template>
    </PageHeader>

    <main class="trash-main" :style="{ paddingBottom: 'calc(var(--tabbar-height, 56px) + var(--sab, 0px))' }">
      <div class="trash-hint mg-glass mg-rise">
        <span class="hint-icon">ℹ️</span>
        <span>回收站文件 30 天内可恢复；移动端不提供单件永久删除，如需彻底清空请用右上角 🧹（会二次确认）。</span>
      </div>

      <div v-if="error" class="trash-error mg-glass">
        <p>⚠️ {{ error }}</p>
        <button type="button" class="item-btn" @click="reload">重试</button>
      </div>

      <div v-else-if="loading && !hasAnything" class="trash-loading mg-glass"><p>加载中…</p></div>

      <div v-else-if="!hasAnything" class="trash-empty mg-glass">
        <p class="empty-icon">🗑</p>
        <p class="empty-text">回收站是空的</p>
        <p class="empty-hint">删除的文件和文件夹会保留 30 天</p>
      </div>

      <template v-else>
        <!-- 文件区 -->
        <section v-if="files.length" class="trash-section">
          <h3 class="section-title">📄 文件 ({{ fileTotal }})</h3>
          <ul class="trash-list">
            <li v-for="f in files" :key="'f-' + f.id" class="trash-row mg-glass mg-rise">
              <div class="row-main">
                <div class="row-title">{{ f.title || f.file_name || `文件 #${f.id}` }}</div>
                <div class="row-meta">
                  <span>{{ formatSize(f.file_size) }}</span>
                  <span v-if="f.deleted_at">· 删除于 {{ formatDate(f.deleted_at) }}</span>
                </div>
              </div>
              <button type="button" class="item-btn restore" @click="restoreFile(f)">↩️ 恢复</button>
            </li>
          </ul>
        </section>

        <!-- 文件夹区 -->
        <section v-if="folders.length" class="trash-section">
          <h3 class="section-title">📂 文件夹 ({{ folders.length }})</h3>
          <ul class="trash-list">
            <li v-for="d in folders" :key="'d-' + d.id" class="trash-row mg-glass mg-rise">
              <div class="row-main">
                <div class="row-title">{{ d.name }}</div>
                <div class="row-meta">
                  <span v-if="d.deleted_at">删除于 {{ formatDate(d.deleted_at) }}</span>
                  <span v-else>已删除</span>
                </div>
              </div>
              <button type="button" class="item-btn restore" @click="restoreFolder(d)">↩️ 恢复</button>
            </li>
          </ul>
        </section>
      </template>
    </main>
  </div>
</template>

<script setup>
/**
 * MobileDriveTrashView.vue — 移动端网盘回收站 (F1 修复: 批次② 新建)
 *
 * 背景: router /drive/trash 的 mobile 组件名 'MobileDriveTrashView' 自 v2 PR2 起
 * 一直指向不存在的文件 (resolveMobile 警告 + fallback 桌面版, 移动端断链)。
 *
 * 功能 (mg-* 液态毛玻璃范式, 参照 MobileTaskTrash):
 * - 文件回收站: GET /api/v1/drive/trash (useDriveFiles.fetchTrash)
 * - 文件夹回收站: GET /api/v1/drive/folders/trash/list (后端 drive_folders.py 已有)
 * - 每项仅"恢复": 文件 POST /files/batch-restore(单 id), 文件夹 POST /folders/{id}/restore
 * - 移动端不放大件永久删除; 顶栏 🧹 清空回收站 = 对当前回收站全部文件走
 *   permanentDeleteBatch (window.confirm 二次确认; 文件夹无批量永久删端点, 不提供)
 */
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import PageHeader from '@/components/mobile/PageHeader.vue'
import { useDriveFiles } from '@/composables/useDriveFiles'
import { formatSize } from '@/utils/format'

const {
  driveFiles, total, loading, loadError,
  fetchTrash, batchRestore, permanentDeleteBatch,
} = useDriveFiles()

const files = computed(() => driveFiles.value || [])
const fileTotal = computed(() => total.value || 0)
const error = computed(() => loadError.value)

const folders = ref([])
const foldersLoading = ref(false)

const hasAnything = computed(() => files.value.length > 0 || folders.value.length > 0)

function formatDate(s) {
  if (!s) return ''
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return String(s).slice(0, 16)
  return `${d.getMonth() + 1}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

async function fetchFolderTrash() {
  foldersLoading.value = true
  try {
    const resp = await axios.get('/api/v1/drive/folders/trash/list', {
      params: { page: 1, page_size: 100 },
    })
    folders.value = resp.data?.items || []
  } catch (e) {
    // 文件夹回收站失败不阻塞文件回收站展示
    console.warn('[MobileDriveTrashView] folder trash load failed:', e?.message)
    folders.value = []
  } finally {
    foldersLoading.value = false
  }
}

async function restoreFile(f) {
  try {
    await batchRestore([f.id])
    ElMessage.success('已恢复')
    await reload()
  } catch (e) {
    ElMessage.error('恢复失败: ' + (e.message || e))
  }
}

async function restoreFolder(d) {
  try {
    await axios.post(`/api/v1/drive/folders/${d.id}/restore`)
    ElMessage.success('文件夹已恢复')
    await fetchFolderTrash()
  } catch (e) {
    ElMessage.error('恢复失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function emptyTrash() {
  if (!files.value.length) {
    ElMessage.info('回收站没有可清空的文件')
    return
  }
  if (!window.confirm(`确定永久删除回收站全部 ${files.value.length} 个文件? 此操作不可恢复!`)) return
  try {
    const resp = await permanentDeleteBatch(files.value.map(f => f.id))
    ElMessage.success(`已永久删除 ${resp?.succeeded_count ?? files.value.length} 个文件`)
    await reload()
  } catch (e) {
    ElMessage.error('清空失败: ' + (e.message || e))
  }
}

async function reload() {
  await Promise.all([fetchTrash(), fetchFolderTrash()])
}

onMounted(() => { reload() })
</script>

<style scoped>
/* mg 范式 (参照 MobileTaskTrash): 背景/文字色由全局 .mg-page 提供 */
.mobile-drive-trash-view {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.trash-main {
  flex: 1;
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
}

:deep(.mobile-page-header) {
  background: var(--mg-glass-bg);
  -webkit-backdrop-filter: blur(24px);
  backdrop-filter: blur(24px);
  border-bottom: 1px solid var(--mg-glass-border);
}
:deep(.header-title) { color: var(--mg-text-strong); }
:deep(.header-back) { color: var(--mg-text); }

.header-action {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 18px;
  color: var(--mg-text);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.header-action:active { background: var(--mg-gradient-soft); }

.trash-hint {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 14px;
  border-radius: var(--mg-radius-md);
  box-shadow: var(--mg-shadow-sm);
  font-size: 12px;
  color: var(--mg-text);
  margin-bottom: 12px;
}
.hint-icon { flex-shrink: 0; }

.trash-error, .trash-loading, .trash-empty {
  text-align: center;
  padding: 40px 20px;
  border-radius: var(--mg-radius-lg);
  color: var(--mg-text-soft);
}
.empty-icon { font-size: 44px; margin-bottom: 8px; }
.empty-text { font-size: 15px; font-weight: 700; color: var(--mg-text-strong); margin: 0 0 4px; }
.empty-hint { font-size: 12px; color: var(--mg-text-faint); margin: 0; }

.trash-section { margin-bottom: 16px; }
.section-title {
  margin: 4px 2px 8px;
  font-size: 13px;
  font-weight: 700;
  color: var(--mg-text-strong);
}

.trash-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.trash-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 13px 14px;
  border: 1.5px solid var(--mg-glass-border);
  border-radius: var(--mg-radius-md);
  box-shadow: var(--mg-shadow-sm);
}
.row-main { flex: 1; min-width: 0; }
.row-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--mg-text-strong);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.row-meta {
  display: flex;
  gap: 6px;
  margin-top: 3px;
  font-size: 11px;
  color: var(--mg-text-soft);
}

.item-btn {
  flex-shrink: 0;
  min-height: 44px;
  padding: 10px 12px;
  border-radius: 14px;
  border: 1.5px solid var(--mg-glass-border);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  background: var(--mg-glass-bg-strong);
  color: var(--mg-text);
  -webkit-tap-highlight-color: transparent;
  transition: transform 150ms ease, opacity 150ms ease;
}
.item-btn:active { transform: scale(0.97); opacity: 0.85; }
.item-btn.restore {
  background: var(--mg-success-soft);
  color: var(--mg-success);
  border-color: transparent;
}
</style>
