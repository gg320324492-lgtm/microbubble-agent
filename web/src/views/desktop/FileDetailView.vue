<!--
  FileDetailView.vue — v2 PR6 文件详情页 (桌面端)

  路由: /drive/file/:id

  布局 (左右 2 栏):
  - 左侧: 文件信息 (header + meta + 操作按钮 + 预览链接)
  - 右侧: CommentThread (评论列表 + 发布)

  数据:
  - GET /api/v1/drive/files/{id} 拿 file info
  - current_user / is_file_owner 从 userStore 推断
-->
<template>
  <div class="page-container file-detail-view">
    <!-- 顶部 -->
    <div class="page-header file-detail-header">
      <el-button link @click="goBack" class="back-btn">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
      <h2 class="file-title">{{ file?.file_name || file?.title || '加载中...' }}</h2>
    </div>

    <!-- 加载态 -->
    <div v-if="loading" class="file-detail-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <p>加载文件信息中...</p>
    </div>

    <!-- 错误态 -->
    <el-alert
      v-else-if="loadError"
      :title="loadError"
      type="error"
      :closable="false"
      show-icon
      class="file-detail-error"
    >
      <template #default>
        <div>
          <p>{{ loadError }}</p>
          <el-button type="primary" @click="fetchFile">重试</el-button>
        </div>
      </template>
    </el-alert>

    <!-- 数据态 -->
    <div v-else-if="file" class="file-detail-body">
      <!-- 左侧: 文件信息 -->
      <el-card class="file-info-card" shadow="never">
        <template #header>
          <div class="file-info-header">
            <el-icon :size="32" class="file-type-icon" :class="`is-${file.file_type}`">
              <component :is="fileTypeIcon(file.file_type)" />
            </el-icon>
            <div class="file-info-header-text">
              <h3>{{ file.file_name || file.title }}</h3>
              <el-tag
                :type="visibilityTagType(file.visibility)"
                size="small"
                effect="plain"
              >
                {{ visibilityLabel(file.visibility) }}
              </el-tag>
              <el-tag v-if="file.is_starred" size="small" type="warning" effect="plain">
                ⭐ 已收藏
              </el-tag>
            </div>
          </div>
        </template>

        <el-descriptions :column="1" border class="file-info-descriptions">
          <el-descriptions-item label="类型">
            {{ file.file_type || '未知' }}
          </el-descriptions-item>
          <el-descriptions-item label="大小">
            {{ formatBytes(file.file_size) }}
          </el-descriptions-item>
          <el-descriptions-item label="上传者">
            {{ file.created_by || '未知' }}
          </el-descriptions-item>
          <el-descriptions-item label="上传时间">
            {{ formatDateTime(file.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item v-if="file.updated_at && file.updated_at !== file.created_at" label="修改时间">
            {{ formatDateTime(file.updated_at) }}
          </el-descriptions-item>
          <el-descriptions-item v-if="file.folder_id" label="所属文件夹">
            文件夹 #{{ file.folder_id }}
          </el-descriptions-item>
          <el-descriptions-item v-if="file.version_number" label="版本">
            v{{ file.version_number }}
          </el-descriptions-item>
          <el-descriptions-item v-if="file.download_count" label="下载次数">
            {{ file.download_count }}
          </el-descriptions-item>
          <el-descriptions-item v-if="file.file_hash" label="文件 Hash">
            <code class="hash-code">{{ file.file_hash.slice(0, 16) }}…</code>
          </el-descriptions-item>
        </el-descriptions>

        <!-- 操作按钮 -->
        <div class="file-info-actions">
          <el-button type="primary" :icon="View" @click="openPreview">
            在线预览
          </el-button>
          <el-button :icon="Download" @click="downloadFile">
            下载
          </el-button>
          <el-button
            :type="file.is_starred ? 'warning' : 'default'"
            :icon="Star"
            @click="toggleStar"
          >
            {{ file.is_starred ? '取消收藏' : '收藏' }}
          </el-button>
        </div>
      </el-card>

      <!-- 右侧: 评论 -->
      <el-card class="file-comments-card" shadow="never">
        <CommentThread
          :file-id="Number(file.id)"
          :current-user-id="currentUserId"
          :is-file-owner="isFileOwner"
        />
      </el-card>
    </div>

    <!-- 预览对话框 (懒加载) -->
    <FilePreviewDialog v-model="showPreview" :file="file" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft, Loading, View, Download, Star,
  Document, Picture, VideoCamera, Headset, Files,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import CommentThread from '@/components/drive/CommentThread.vue'
import FilePreviewDialog from '@/components/drive/FilePreviewDialog.vue'
import { useUserStore } from '@/stores/useUserStore'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const file = ref(null)
const loading = ref(false)
const loadError = ref(null)
const showPreview = ref(false)

const fileId = computed(() => Number(route.params.id))

const currentUserId = computed(() => {
  return userStore.userInfo?.id || null
})

const isFileOwner = computed(() => {
  if (!file.value || !currentUserId.value) return false
  return file.value.created_by === currentUserId.value
})

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

function visibilityTagType(visibility) {
  return {
    private: 'info',
    team: 'success',
    public: 'warning',
  }[visibility] || ''
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

function goBack() {
  // 优先返回到 /drive, 失败则首页
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
  const url = `/api/v1/drive/files/${file.value.id}/download`
  // 走 axios 拉 blob + 触发下载 (JWT 鉴权)
  axios.get(url, {
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
  }).catch((err) => {
    ElMessage.error(err.response?.data?.detail || '下载失败')
  })
}

async function toggleStar() {
  if (!file.value) return
  try {
    const resp = await axios.post(
      `/api/v1/drive/files/${file.value.id}/toggle-star`,
      {},
      { headers: { Authorization: `Bearer ${localStorage.getItem('access_token') || ''}` } }
    )
    file.value = { ...file.value, is_starred: resp.data.is_starred }
    ElMessage.success(resp.data.is_starred ? '已收藏' : '已取消收藏')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

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
.page-container.file-detail-view {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.file-detail-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.back-btn {
  font-size: 14px;
}

.file-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary, #303133);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-detail-loading,
.file-detail-error {
  padding: 64px 16px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.file-detail-error {
  text-align: left;
}

.file-detail-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr);
  gap: 20px;
}

@media (max-width: 900px) {
  .file-detail-body {
    grid-template-columns: 1fr;
  }
}

.file-info-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.file-info-header-text {
  flex: 1;
  min-width: 0;
}

.file-info-header-text h3 {
  margin: 0 0 4px;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary, #303133);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-type-icon {
  flex-shrink: 0;
  color: var(--color-primary, #FF7A5C);
}

.file-type-icon.is-image { color: var(--color-success, #67c23a); }
.file-type-icon.is-video { color: var(--color-info, #909399); }
.file-type-icon.is-audio { color: var(--color-warning, #e6a23c); }

.file-info-descriptions {
  margin-bottom: 16px;
}

.hash-code {
  font-family: monospace;
  font-size: 12px;
  background: var(--color-bg-page, #f5f7fa);
  padding: 1px 4px;
  border-radius: 3px;
}

.file-info-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border-light, #ebeef5);
}

.file-comments-card {
  align-self: start;
  position: sticky;
  top: 80px;
  max-height: calc(100vh - 100px);
  overflow-y: auto;
}

/* Dark mode 非 scoped 块 (v60-v67 教训) */
[data-theme="dark"] .file-info-actions {
  border-top-color: var(--color-border-dark, rgba(255, 255, 255, 0.08));
}

[data-theme="dark"] .hash-code {
  background: var(--color-bg-page, #2a2d35);
}
</style>
</content>
</invoke>