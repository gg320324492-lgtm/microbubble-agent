<!--
  MobileFileDetailView.vue — v2 PR6-P3 移动端文件详情页

  路由: /drive/file/:id (复用 desktop 路由, resolveMobileComponent 自动分流)

  布局 (mobile 单列, sticky):
  - 顶部 sticky: 返回按钮 + 文件名 + visibility/starred tag
  - 中部: 文件信息 card (类型/大小/上传者/时间/版本等)
  - 中部: CommentThread (评论列表 + sticky 底部输入栏)
  - 底部浮动: 操作按钮 (预览/下载/收藏) — 移动端用长按触发 ActionSheet 选操作

  数据:
  - GET /api/v1/drive/files/{id} 拿 file info
  - current_user / is_file_owner 从 userStore 推断
  - 复用 desktop 同套 API + 同套 userStore

  设计:
  - 单列布局 (vs desktop 左右 2 栏)
  - sticky 顶部 (返回 + 标题) 始终可见
  - 长按底部操作栏 → ActionSheet 弹出 6 项 (预览/下载/收藏/重命名/移动/删除)
  - 评论区直接复用 desktop CommentThread (PR6-P3 单列适配版 MobileCommentThread)

  Dark mode: 非 scoped 块 (v60-v67 教训)
-->
<template>
  <div class="mobile-file-detail">
    <!-- Sticky 顶部 -->
    <div class="mfd-header">
      <button
        type="button"
        class="mfd-back"
        aria-label="返回"
        title="返回"
        @click="goBack"
      >
        <el-icon :size="20"><ArrowLeft /></el-icon>
      </button>
      <div class="mfd-title-area">
        <h2 class="mfd-title">{{ file?.file_name || file?.title || '加载中...' }}</h2>
        <div v-if="file" class="mfd-tags">
          <span class="mfd-visibility-tag" :class="`is-${file.visibility}`">
            {{ visibilityLabel(file.visibility) }}
          </span>
          <span v-if="file.is_starred" class="mfd-star-tag">⭐ 已收藏</span>
        </div>
      </div>
      <button
        type="button"
        class="mfd-action-trigger"
        :class="{ 'is-active': showActions }"
        aria-label="更多操作"
        title="更多操作"
        @click="showActions = true"
      >
        <el-icon :size="20"><MoreFilled /></el-icon>
      </button>
    </div>

    <!-- 加载态 -->
    <div v-if="loading" class="mfd-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <p>加载文件信息中...</p>
    </div>

    <!-- 错误态 -->
    <div v-else-if="loadError" class="mfd-error">
      <el-icon :size="48" class="mfd-error-icon"><WarningFilled /></el-icon>
      <p>{{ loadError }}</p>
      <button type="button" class="mfd-retry-btn" @click="fetchFile">
        重试
      </button>
    </div>

    <!-- 数据态 -->
    <div v-else-if="file" class="mfd-body">
      <!-- 文件信息 card -->
      <div class="mfd-info-card">
        <div class="mfd-info-header">
          <el-icon :size="48" class="mfd-type-icon">
            <component :is="fileTypeIcon(file.file_type)" />
          </el-icon>
          <div class="mfd-info-summary">
            <div class="mfd-info-name">{{ file.file_name || file.title }}</div>
            <div class="mfd-info-size">{{ formatBytes(file.file_size) }}</div>
          </div>
        </div>

        <ul class="mfd-info-list">
          <li class="mfd-info-row">
            <span class="mfd-info-label">类型</span>
            <span class="mfd-info-value">{{ file.file_type || '未知' }}</span>
          </li>
          <li class="mfd-info-row">
            <span class="mfd-info-label">上传者</span>
            <span class="mfd-info-value">{{ file.created_by || '未知' }}</span>
          </li>
          <li class="mfd-info-row">
            <span class="mfd-info-label">上传时间</span>
            <span class="mfd-info-value">{{ formatDateTime(file.created_at) }}</span>
          </li>
          <li v-if="file.updated_at && file.updated_at !== file.created_at" class="mfd-info-row">
            <span class="mfd-info-label">修改时间</span>
            <span class="mfd-info-value">{{ formatDateTime(file.updated_at) }}</span>
          </li>
          <li v-if="file.folder_id" class="mfd-info-row">
            <span class="mfd-info-label">所属文件夹</span>
            <span class="mfd-info-value">#{{ file.folder_id }}</span>
          </li>
          <li v-if="file.version_number" class="mfd-info-row">
            <span class="mfd-info-label">版本</span>
            <span class="mfd-info-value">v{{ file.version_number }}</span>
          </li>
          <li v-if="file.download_count" class="mfd-info-row">
            <span class="mfd-info-label">下载次数</span>
            <span class="mfd-info-value">{{ file.download_count }}</span>
          </li>
          <li v-if="file.file_hash" class="mfd-info-row">
            <span class="mfd-info-label">文件 Hash</span>
            <span class="mfd-info-value hash-value">{{ file.file_hash.slice(0, 16) }}…</span>
          </li>
        </ul>
      </div>

      <!-- 主操作按钮 (mobile 友好的 3 个核心操作) -->
      <div class="mfd-actions-primary">
        <button
          type="button"
          class="mfd-action-btn is-primary"
          aria-label="在线预览"
          title="在线预览"
          @click="openPreview"
        >
          <el-icon :size="18"><View /></el-icon>
          <span>预览</span>
        </button>
        <button
          type="button"
          class="mfd-action-btn"
          aria-label="下载文件"
          title="下载文件"
          @click="downloadFile"
        >
          <el-icon :size="18"><Download /></el-icon>
          <span>下载</span>
        </button>
        <button
          type="button"
          class="mfd-action-btn"
          :class="{ 'is-warning': file.is_starred }"
          aria-label="切换收藏"
          :title="file.is_starred ? '取消收藏' : '收藏'"
          @click="toggleStar"
        >
          <el-icon :size="18">
            <component :is="file.is_starred ? StarFilled : Star" />
          </el-icon>
          <span>{{ file.is_starred ? '已收藏' : '收藏' }}</span>
        </button>
      </div>

      <!-- 评论 card -->
      <div class="mfd-comments-card">
        <MobileCommentThread
          :file-id="Number(file.id)"
          :current-user-id="currentUserId"
          :is-file-owner="isFileOwner"
        />
      </div>
    </div>

    <!-- 预览对话框 -->
    <FilePreviewDialog v-model="showPreview" :file="file" />

    <!-- 浮动操作 ActionSheet (右上角 ... 触发) -->
    <MobileActionSheet
      v-model:show="showActions"
      :title="file?.file_name || file?.title || '操作'"
      :actions="fileActions"
      @action="onAction"
    />
  </div>
</template>

<script setup>
/**
 * MobileFileDetailView.vue — 移动端文件详情页
 *
 * 关键设计:
 * 1. 复用 desktop FileDetailView 的 API (axios.get /api/v1/drive/files/{id})
 * 2. 复用 desktop useUserStore (currentUserId + isFileOwner 推断)
 * 3. 单列布局 (mobile 屏小, 左右 2 栏挤)
 * 4. sticky 顶部 (返回 + 标题) 让用户随时可返回
 * 5. 复用 desktop FilePreviewDialog (mobile 上也用 el-dialog, isMobile 已适配)
 * 6. 长按/点 ... 触发 MobileActionSheet 6 操作 (预览/下载/收藏/重命名/移动/改可见性/删除)
 * 7. 评论区直接用 MobileCommentThread (PR6-P3 移动端专属版)
 *
 * 与 desktop 镜像:
 * - formatBytes / formatDateTime / fileTypeIcon / visibilityLabel 完全一致
 * - goBack 优先 router.back, 失败 /drive fallback
 * - toggleStar 乐观更新本地 + 后端返回兜底
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft, Loading, View, Download, Star, StarFilled, MoreFilled,
  Document, Picture, VideoCamera, Headset, Files, WarningFilled,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import MobileCommentThread from '@/views/mobile/MobileCommentThread.vue'
import MobileActionSheet from '@/components/mobile/MobileActionSheet.vue'
import FilePreviewDialog from '@/components/drive/FilePreviewDialog.vue'
import { useUserStore } from '@/stores/useUserStore'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const file = ref(null)
const loading = ref(false)
const loadError = ref(null)
const showPreview = ref(false)
const showActions = ref(false)

const fileId = computed(() => Number(route.params.id))

const currentUserId = computed(() => {
  return userStore.userInfo?.id || null
})

const isFileOwner = computed(() => {
  if (!file.value || !currentUserId.value) return false
  return file.value.created_by === currentUserId.value
})

// === helper 函数 (与 desktop FileDetailView 镜像) ===
function fileTypeIcon(fileType) {
  if (!fileType) return Files
  if (fileType.startsWith('image/')) return Picture
  if (fileType.startsWith('video/')) return VideoCamera
  if (fileType.startsWith('audio/')) return Headset
  if (fileType === 'application/pdf') return Document
  return Files
}

function visibilityLabel(visibility) {
  return {
    private: '🔒 仅自己',
    team: '👥 全组',
    public: '🌍 公开',
  }[visibility] || visibility || '未知'
}

function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return '—'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let v = bytes
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i++
  }
  return `${v.toFixed(1)} ${units[i]}`
}

function formatDateTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('zh-CN', { hour12: false })
}

// === 操作 ActionSheet 配置 ===
const fileActions = computed(() => {
  if (!file.value) return []
  const f = file.value
  return [
    { name: 'preview', label: '👁 在线预览' },
    { name: 'download', label: '⬇️ 下载' },
    { name: 'toggle-star', label: f.is_starred ? '⭐ 取消收藏' : '⭐ 收藏' },
    { name: 'rename', label: '✏️ 重命名' },
    { name: 'move', label: '📂 移动' },
    { name: 'update-visibility', label: '🔒 改可见性' },
    { name: 'delete', label: '🗑️ 删除', danger: true },
  ]
})

function onAction(action) {
  showActions.value = false
  if (!file.value || !action?.name) return
  switch (action.name) {
    case 'preview': openPreview(); break
    case 'download': downloadFile(); break
    case 'toggle-star': toggleStar(); break
    case 'rename': onRename(); break
    case 'move': onMove(); break
    case 'update-visibility': onUpdateVisibility(); break
    case 'delete': onDelete(); break
  }
}

// === 操作实现 ===
function goBack() {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/drive')
  }
}

function openPreview() {
  showPreview.value = true
}

function downloadFile() {
  if (!file.value) return
  axios.get(`/api/v1/drive/files/${file.value.id}/download`, {
    responseType: 'blob',
    headers: { Authorization: `Bearer ${localStorage.getItem('access_token') || ''}` },
  }).then((resp) => {
    const blobUrl = URL.createObjectURL(resp.data)
    const a = document.createElement('a')
    a.href = blobUrl
    a.download = file.value.file_name || `file_${file.value.id}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    setTimeout(() => URL.revokeObjectURL(blobUrl), 5000)
  }).catch(() => {
    ElMessage.error('下载失败')
  })
}

async function toggleStar() {
  if (!file.value) return
  try {
    const resp = await axios.post(
      `/api/v1/drive/files/${file.value.id}/toggle-star`,
      {},
      { headers: { Authorization: `Bearer ${localStorage.getItem('access_token') || ''}` } },
    )
    file.value = { ...file.value, is_starred: resp.data.is_starred }
    ElMessage.success(resp.data.is_starred ? '已收藏' : '已取消收藏')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

async function onRename() {
  if (!file.value) return
  try {
    const { value } = await ElMessageBox.prompt('请输入新文件名', '重命名', {
      inputValue: file.value.file_name || file.value.title,
      confirmButtonText: '保存',
      cancelButtonText: '取消',
      inputValidator: (val) => {
        if (!val || !val.trim()) return '文件名不能为空'
        if (val.length > 200) return '文件名过长'
        return true
      },
    })
    const newName = value.trim()
    await axios.put(
      `/api/v1/drive/files/${file.value.id}/rename`,
      { file_name: newName },
      { headers: { Authorization: `Bearer ${localStorage.getItem('access_token') || ''}` } },
    )
    file.value = { ...file.value, file_name: newName }
    ElMessage.success('已重命名')
  } catch (e) {
    if (e === 'cancel') return
    ElMessage.error(e.response?.data?.detail || '重命名失败')
  }
}

function onMove() {
  ElMessage.info('移动操作开发中, 请到桌面端使用 (PR6-P4)')
}

async function onUpdateVisibility() {
  if (!file.value) return
  const options = ['private', 'team', 'public']
  const labels = { private: '🔒 仅自己', team: '👥 全组', public: '🌍 公开' }
  try {
    const result = await ElMessageBox({
      title: '修改可见性',
      message: '请选择新的可见性',
      showCancelButton: true,
      confirmButtonText: '保存',
      cancelButtonText: '取消',
      // 简化版: 用 prompt 选 (mobile 上 select 组件不友好)
      showInput: true,
      inputType: 'select',
      inputOptions: options.reduce((acc, k) => { acc[k] = labels[k]; return acc }, {}),
      inputValue: file.value.visibility || 'team',
    })
    if (!result?.value) return
    await axios.put(
      `/api/v1/drive/files/${file.value.id}/visibility`,
      { visibility: result.value },
      { headers: { Authorization: `Bearer ${localStorage.getItem('access_token') || ''}` } },
    )
    file.value = { ...file.value, visibility: result.value }
    ElMessage.success('已更新')
  } catch (e) {
    if (e === 'cancel') return
    ElMessage.error(e.response?.data?.detail || '更新失败')
  }
}

async function onDelete() {
  if (!file.value) return
  try {
    await ElMessageBox.confirm(
      `确认删除文件 "${file.value.file_name || file.value.title}"？此操作不可撤销。`,
      '删除确认',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }
  try {
    await axios.delete(`/api/v1/drive/files/${file.value.id}`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('access_token') || ''}` },
    })
    ElMessage.success('已删除')
    router.push('/drive')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

// === 数据加载 ===
async function fetchFile() {
  if (!fileId.value) {
    loadError.value = '无效的文件 ID'
    return
  }
  loading.value = true
  loadError.value = null
  try {
    const resp = await axios.get(`/api/v1/drive/files/${fileId.value}`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('access_token') || ''}` },
    })
    file.value = resp.data
  } catch (e) {
    if (e.response?.status === 404) {
      loadError.value = '文件不存在或已被删除'
    } else if (e.response?.status === 403) {
      loadError.value = '没有访问权限 (private 文件仅所有者可见)'
    } else {
      loadError.value = e.response?.data?.detail || e.message || '加载失败'
    }
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchFile()
})

watch(fileId, () => {
  fetchFile()
})
</script>

<style scoped>
.mobile-file-detail {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  padding-bottom: 24px;
}

/* Sticky 顶部 */
.mfd-header {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--color-bg-card, #fff);
  border-bottom: 1px solid var(--color-border-light, #ebeef5);
}

.mfd-back,
.mfd-action-trigger {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  color: var(--color-text-primary, #303133);
}

.mfd-back:active,
.mfd-action-trigger:active,
.mfd-action-trigger.is-active {
  background: var(--color-bg-hover, #f5f7fa);
}

.mfd-title-area {
  flex: 1;
  min-width: 0;
}

.mfd-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary, #303133);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mfd-tags {
  margin-top: 4px;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.mfd-visibility-tag {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 8px;
  background: var(--color-bg-page, #f5f7fa);
  color: var(--color-text-secondary, #606266);
}

.mfd-visibility-tag.is-private {
  background: rgba(245, 108, 108, 0.1);
  color: var(--color-danger, #f56c6c);
}

.mfd-visibility-tag.is-team {
  background: rgba(103, 194, 58, 0.1);
  color: var(--color-success, #67c23a);
}

.mfd-visibility-tag.is-public {
  background: rgba(230, 162, 60, 0.1);
  color: var(--color-warning, #e6a23c);
}

.mfd-star-tag {
  font-size: 11px;
  color: var(--color-warning, #e6a23c);
  font-weight: 500;
}

/* 加载 / 错误 */
.mfd-loading,
.mfd-error {
  padding: 60px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: var(--color-text-secondary, #606266);
}

.mfd-error-icon {
  color: var(--color-danger, #f56c6c);
  opacity: 0.6;
}

.mfd-retry-btn {
  margin-top: 8px;
  padding: 6px 16px;
  background: var(--color-primary, #409eff);
  color: var(--el-color-white);
  border: none;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
}

.is-loading {
  animation: spin 1s linear infinite;
  font-size: 32px;
  color: var(--color-primary, #409eff);
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 数据态 */
.mfd-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
}

.mfd-info-card {
  background: var(--color-bg-card, #fff);
  border-radius: 8px;
  padding: 16px;
  border: 1px solid var(--color-border-light, #ebeef5);
}

.mfd-info-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-border-light, #f5f7fa);
  margin-bottom: 12px;
}

.mfd-type-icon {
  flex-shrink: 0;
  color: var(--color-primary, #409eff);
  background: var(--color-primary-light-9, #ecf5ff);
  border-radius: 12px;
  padding: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.mfd-info-summary {
  flex: 1;
  min-width: 0;
}

.mfd-info-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary, #303133);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mfd-info-size {
  margin-top: 2px;
  font-size: 12px;
  color: var(--color-text-secondary, #909399);
}

.mfd-info-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mfd-info-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
}

.mfd-info-label {
  flex-shrink: 0;
  width: 70px;
  color: var(--color-text-secondary, #909399);
}

.mfd-info-value {
  flex: 1;
  color: var(--color-text-primary, #303133);
  overflow-wrap: anywhere;
  word-break: normal;
}

.hash-value {
  font-family: monospace;
  font-size: 12px;
}

/* 主操作按钮 */
.mfd-actions-primary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  padding: 0 4px;
}

.mfd-action-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 12px 8px;
  background: var(--color-bg-card, #fff);
  border: 1px solid var(--color-border-light, #ebeef5);
  border-radius: 8px;
  cursor: pointer;
  font-size: 12px;
  color: var(--color-text-primary, #303133);
}

.mfd-action-btn:active {
  background: var(--color-bg-hover, #f5f7fa);
}

.mfd-action-btn.is-primary {
  background: var(--color-primary, #409eff);
  color: var(--el-color-white);
  border-color: var(--color-primary, #409eff);
}

.mfd-action-btn.is-warning {
  color: var(--color-warning, #e6a23c);
  border-color: var(--color-warning, #e6a23c);
  background: rgba(230, 162, 60, 0.08);
}

/* 评论 card */
.mfd-comments-card {
  background: var(--color-bg-card, #fff);
  border-radius: 8px;
  border: 1px solid var(--color-border-light, #ebeef5);
  overflow: hidden;
}
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  下方 dark 块覆盖 mobile 专属样式 (sticky 顶部 / 操作按钮 / info 卡片)
-->
<style>
[data-theme="dark"] .mobile-file-detail {
  background: var(--color-bg-page, #1a1d23);
}

[data-theme="dark"] .mfd-header {
  background: var(--color-bg-card, #2a2d35);
  border-bottom-color: var(--color-border-light, #3a3d45);
}

[data-theme="dark"] .mfd-back:active,
[data-theme="dark"] .mfd-action-trigger:active,
[data-theme="dark"] .mfd-action-trigger.is-active {
  background: var(--color-bg-hover, #3a3d45);
}

[data-theme="dark"] .mfd-info-card {
  background: var(--color-bg-card, #2a2d35);
  border-color: var(--color-border-light, #3a3d45);
}

[data-theme="dark"] .mfd-info-header {
  border-bottom-color: var(--color-border-light, #3a3d45);
}

[data-theme="dark"] .mfd-action-btn {
  background: var(--color-bg-card, #2a2d35);
  border-color: var(--color-border-light, #3a3d45);
  color: var(--color-text-primary, #e6e8eb);
}

[data-theme="dark"] .mfd-action-btn:active {
  background: var(--color-bg-hover, #3a3d45);
}

[data-theme="dark"] .mfd-action-btn.is-warning {
  background: rgba(230, 162, 60, 0.15);
}

[data-theme="dark"] .mfd-comments-card {
  background: var(--color-bg-card, #2a2d35);
  border-color: var(--color-border-light, #3a3d45);
}

[data-theme="dark"] .mfd-type-icon {
  background: rgba(64, 158, 255, 0.15);
}
</style>