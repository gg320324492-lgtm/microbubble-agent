<!--
  DesktopFileVersionsView.vue — 桌面端文件版本历史视图 (W68 第 4 批)

  桌面端独立路由 /drive/file/:id/versions 的全屏视图 (跟移动端 MobileFileCommentsView 风格对等).
  与 VersionHistoryDialog.vue 复用同一 useDriveFiles.listVersions API, 但 layout 走全屏时间线.

  设计:
  - 顶部: 文件摘要 (文件名 + 当前版本 tag + hash 前 8 位)
  - 时间线: 每个版本一行 (大圆点 + 竖线 + 信息块), 按 version_number desc 排序
    - 当前版本: 绿色高亮 + "当前" badge
    - 历史版本: 可点 "下载 / 恢复此版本"
  - 上传新版本: 顶部右侧 "上传新版本" 按钮 → 弹 el-upload 组件
  - 响应式: 桌面端 800px 容器居中, max-width 980px
  - dark mode: 走 .desktop-* class + var() token

  数据流:
  - onMounted: listVersions(fileId) → versions.value = items (含 file_name)
  - 上传新版本: POST multipart → refresh list
  - 恢复版本: 弹 el-popconfirm → restoreVersion → refresh list

  0 production code 改动铁律维持:
  - 仅 desktop/views + desktop/e2e + memory (不动 production code 后端/服务层)
-->
<template>
  <div class="desktop-file-versions-view drive-page">
    <!-- 顶部导航条 (含返回 + 文件名 + 当前版本 tag) -->
    <div class="drive-toolbar">
      <div class="drive-toolbar-left">
        <el-button
          class="drive-toolbar-btn"
          :icon="ArrowLeft"
          @click="goBack"
        >
          返回网盘
        </el-button>
        <h2 class="drive-title">
          <span class="drive-title-icon">🕘</span>
          文件版本历史
        </h2>
      </div>
      <div class="drive-toolbar-actions">
        <el-button
          v-if="versions.length >= 2"
          class="drive-compare-btn"
          :icon="DocumentCopy"
          data-testid="open-version-diff"
          @click="diffDialogVisible = true"
        >
          版本对比
        </el-button>
        <!-- 上传新版本按钮 (走 el-upload 隐式触发) -->
        <el-upload
          v-if="fileInfo"
          :http-request="handleUploadNewVersion"
          :show-file-list="false"
          :before-upload="beforeNewVersionUpload"
          accept="*/*"
        >
          <el-button
            class="drive-upload-btn"
            type="primary"
            :icon="UploadFilled"
            :loading="uploading"
          >
            上传新版本
          </el-button>
        </el-upload>
      </div>
    </div>

    <!-- 文件摘要卡 -->
    <div v-if="fileInfo" class="version-file-summary-card">
      <span class="version-file-name">{{ fileInfo.file_name }}</span>
      <el-tag size="small" type="success" effect="dark">
        当前 v{{ fileInfo.version_number || 1 }}
      </el-tag>
      <span v-if="fileInfo.file_hash" class="version-file-hash">
        {{ fileInfo.file_hash.slice(0, 12) }}…
      </span>
    </div>

    <!-- 主区域: loading / error / empty / timeline 四态 -->
    <div class="version-content">
      <!-- loading -->
      <div v-if="loading" v-loading="true" class="version-loading">
        <p class="version-loading-text">加载版本历史…</p>
      </div>

      <!-- error -->
      <div v-else-if="loadError" class="version-error">
        <el-icon :size="48"><WarningFilled /></el-icon>
        <p class="version-error-title">{{ loadError }}</p>
        <el-button type="primary" @click="fetchVersions">重试</el-button>
      </div>

      <!-- empty -->
      <el-empty
        v-else-if="versions.length === 0"
        description="该文件还没有历史版本（首次上传）"
      />

      <!-- timeline -->
      <div v-else class="version-timeline">
        <div
          v-for="(v, idx) in versions"
          :key="v.id"
          class="version-timeline-item"
          :class="{ 'is-current': v.is_current }"
        >
          <!-- 时间线圆点 + 竖线 -->
          <div class="version-timeline-marker">
            <div class="version-timeline-dot" :class="{ 'is-current': v.is_current }"></div>
            <div v-if="idx < versions.length - 1" class="version-timeline-line"></div>
          </div>

          <!-- 信息块 -->
          <div class="version-timeline-card">
            <div class="version-timeline-header">
              <span class="version-number">v{{ v.version_number }}</span>
              <el-tag v-if="v.is_current" size="small" type="success" effect="dark">当前版本</el-tag>
              <span class="version-uploader">
                {{ v.uploader_name || `用户 #${v.uploader_id}` }}
              </span>
              <span class="version-time">{{ formatDateTime(v.created_at) }}</span>
            </div>

            <div class="version-timeline-meta">
              <span class="version-size">{{ formatSize(v.size) }}</span>
              <code v-if="v.minio_object_key" class="version-hash" :title="v.minio_object_key">
                {{ v.minio_object_key.slice(-12) }}
              </code>
              <span v-if="v.comment" class="version-comment">📝 {{ v.comment }}</span>
              <span v-else class="version-comment-empty">—</span>
            </div>

            <!-- 操作按钮 (仅历史版本可下载/恢复) -->
            <div v-if="!v.is_current" class="version-timeline-actions">
              <el-button size="small" :icon="Download" @click="downloadVersion(v)">
                下载此版本
              </el-button>
              <el-popconfirm
                :title="`确认恢复 v${v.version_number}? 恢复后会生成新版本号 v${(fileInfo?.version_number || 1) + 1}`"
                confirm-button-text="恢复"
                cancel-button-text="取消"
                @confirm="restoreVersion(v)"
              >
                <template #reference>
                  <el-button size="small" type="primary" :icon="Refresh">
                    恢复此版本
                  </el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
        </div>
      </div>
    </div>

    <DesktopVersionDiffDialog
      v-model="diffDialogVisible"
      :file-id="fileId"
      :file-name="fileInfo?.file_name || ''"
      :versions="versions"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft, UploadFilled, WarningFilled, Download, Refresh, DocumentCopy
} from '@element-plus/icons-vue'
import { useDriveFiles } from '@/composables/useDriveFiles'
import DesktopVersionDiffDialog from '@/components/desktop/DesktopVersionDiffDialog.vue'
import { formatDateTime } from '@/utils/format'

// 引入 drive-view.css 共享样式 (跟 FileGrid/DriveTrashView 一致)
import '@/views/drive/drive-view.css'

const route = useRoute()
const router = useRouter()

const fileId = computed(() => Number(route.params.id))

const { listVersions, restoreVersion: restoreApi } = useDriveFiles()

// === 数据 ===
const versions = ref([])
const fileInfo = ref(null)  // { file_name, version_number, file_hash }
const loading = ref(false)
const loadError = ref(null)
const uploading = ref(false)
const diffDialogVisible = ref(false)

async function fetchVersions() {
  loading.value = true
  loadError.value = null
  try {
    const resp = await listVersions(fileId.value)
    // 兼容两种 API 返回:
    //   - 新 API (v2 PR9): { file_id, file_name, count, items }
    //   - 老 API: 直接 items 数组
    if (Array.isArray(resp)) {
      versions.value = resp
    } else if (resp && Array.isArray(resp.items)) {
      versions.value = resp.items
      fileInfo.value = {
        file_name: resp.file_name,
        version_number: versions.value.find(v => v.is_current)?.version_number || 1,
        file_hash: versions.value[0]?.minio_object_key || '',
      }
    } else {
      versions.value = []
    }
    // 文件名优先从 listVersions 响应拿; 拿不到则用占位符
    if (!fileInfo.value) {
      fileInfo.value = {
        file_name: `文件 #${fileId.value}`,
        version_number: versions.value.find(v => v.is_current)?.version_number || 1,
        file_hash: versions.value[0]?.minio_object_key || '',
      }
    }
  } catch (e) {
    loadError.value = e?.response?.data?.detail || e?.message || '加载版本历史失败'
    versions.value = []
  } finally {
    loading.value = false
  }
}

async function downloadVersion(v) {
  // 历史版本: 走 file 下载端点 (DriveVersionService 当前实现: 历史版直接返当前版字节,
  // 完整实现需另起 GET /versions/{vid}/download 端点 — 待 PR9 后续)
  const url = `/api/v1/drive/versions/versions/${v.id}/download`
  window.open(url, '_blank')
  ElMessage.info(`下载 v${v.version_number}: 当前实现仅供查阅 (历史版独立下载端点待后续 PR)`)
}

async function restoreVersion(v) {
  try {
    const newK = await restoreApi(fileId.value, v.id)
    ElMessage.success(`已恢复 v${v.version_number} → 新版本 v${newK.version_number || '?'}`)
    await fetchVersions()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '恢复失败')
  }
}

async function beforeNewVersionUpload(file) {
  // 限制单文件 <= 200MB (跟 DriveUploadDialog 一致)
  const MAX = 200 * 1024 * 1024
  if (file.size > MAX) {
    ElMessage.error(`文件大小 ${formatSize(file.size)} 超过 200MB 上限`)
    return false
  }
  return true
}

async function handleUploadNewVersion({ file, data }) {
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    // data.comment 可选 (本视图暂不暴露 comment input)
    const resp = await fetch(`/api/v1/drive/versions/files/${fileId.value}/versions`, {
      method: 'POST',
      body: fd,
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('access_token') || ''}`,
      },
    })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      throw new Error(err.detail || `HTTP ${resp.status}`)
    }
    const result = await resp.json()
    ElMessage.success(`已上传新版本 v${result.new_version_number}`)
    await fetchVersions()
  } catch (e) {
    ElMessage.error(e.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

function goBack() {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/drive')
  }
}

function formatSize(bytes) {
  if (!bytes && bytes !== 0) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`
}

onMounted(() => {
  fetchVersions()
})
</script>

<style scoped>
/*
 * v2.0 (2026-07-09) Drive 美化 — 复用 .drive-page / .drive-toolbar / .drive-title / .drive-toolbar-btn
 * 本视图额外新增 .version-* 时间线样式
 */
.desktop-file-versions-view {
  display: flex;
  flex-direction: column;
  min-height: 100%;
  background: var(--color-bg-page, #fafbfc);
}

.drive-toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.drive-toolbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.drive-compare-btn {
  color: var(--color-primary-dark);
  border-color: var(--color-primary-border);
  background: var(--color-primary-bg);
}

/* 文件摘要卡 */
.version-file-summary-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 24px;
  margin: 16px 24px 0;
  background: var(--color-info-bg, rgba(64, 158, 255, 0.06));
  border-radius: var(--radius-md, 8px);
  border: 1px solid var(--color-border-light, #ebeef5);
}
.version-file-name {
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary, #303133);
  font-size: 15px;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.version-file-hash {
  font-family: monospace;
  font-size: 12px;
  color: var(--color-text-secondary, #606266);
  background: var(--color-bg-card, #fff);
  padding: 2px 8px;
  border-radius: var(--radius-sm, 4px);
}

/* 内容区 */
.version-content {
  flex: 1;
  padding: 16px 24px 32px;
  max-width: 980px;
  width: 100%;
  margin: 0 auto;
  box-sizing: border-box;
}
.version-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 320px;
  gap: 12px;
}
.version-loading-text {
  color: var(--color-text-secondary);
  font-size: 14px;
}
.version-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 320px;
  gap: 12px;
  color: var(--color-text-secondary);
}
.version-error-title {
  font-size: 14px;
  margin: 0;
}

/* 时间线 */
.version-timeline {
  display: flex;
  flex-direction: column;
  padding: 16px 0;
}
.version-timeline-item {
  display: flex;
  gap: 16px;
  position: relative;
}
.version-timeline-item.is-current .version-timeline-card {
  background: var(--color-success-light-9, rgba(133, 206, 97, 0.08));
  border-color: rgba(133, 206, 97, 0.3);
}
.version-timeline-marker {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 12px;
  flex-shrink: 0;
  width: 20px;
}
.version-timeline-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--color-primary, #ff7a5c);
  border: 3px solid var(--color-bg-card, #fff);
  box-shadow: 0 0 0 2px var(--color-primary, #ff7a5c);
}
.version-timeline-dot.is-current {
  background: var(--color-success, #67c23a);
  box-shadow: 0 0 0 2px var(--color-success, #67c23a);
}
.version-timeline-line {
  flex: 1;
  width: 2px;
  background: var(--color-border-light, #ebeef5);
  margin-top: 4px;
}
.version-timeline-card {
  flex: 1;
  margin-bottom: 16px;
  padding: 14px 16px;
  background: var(--color-bg-card, #fff);
  border: 1px solid var(--color-border-light, #ebeef5);
  border-radius: var(--radius-md, 8px);
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--duration-fast) var(--ease-out);
}
.version-timeline-card:hover {
  box-shadow: var(--shadow-md);
}
.version-timeline-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.version-number {
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-primary, #ff7a5c);
  font-size: 15px;
}
.version-uploader {
  font-size: 13px;
  color: var(--color-text-regular, #606266);
}
.version-time {
  margin-left: auto;
  font-size: 12px;
  color: var(--color-text-secondary, #909399);
}
.version-timeline-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: var(--color-text-secondary, #909399);
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.version-size {
  background: var(--color-info-bg);
  padding: 2px 8px;
  border-radius: var(--radius-sm, 4px);
  font-weight: var(--font-weight-medium, 500);
}
.version-hash {
  font-family: monospace;
  background: var(--color-bg-page, #fafbfc);
  padding: 2px 6px;
  border-radius: var(--radius-sm, 4px);
  font-size: 11px;
}
.version-comment {
  color: var(--color-text-regular, #606266);
}
.version-comment-empty {
  color: var(--color-text-placeholder, #c0c4cc);
}
.version-timeline-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

/* dark mode (CLAUDE.md v60-v67 第 5 次强化: 跨组件 dark 必须放非 scoped <style> 块) */
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  本视图主要用 var() token, dark 自动跟随; 仅极少场景需要非 scoped 块覆盖 (预留位)
-->