<!--
  DriveUploadDialog.vue — 课题组网盘 PR3.6 上传对话框 (drive 模式)
  2026-07-01

  字段:
  - storage_mode: 固定 'drive' (本组件仅 drive, KB 模式走 KnowledgeUploadDialog)
  - folder_id: TreeSelect 选目标文件夹 (顶级 null)
  - visibility: private / team / public
  - files[]: 待上传文件 (相对路径 + 大小)

  功能:
  - 文件夹拖拽接收 (useFolderDropZone, 支持 webkitGetAsEntry)
  - 进度条 per 文件 (PR2.8 multipart API)
  - 多文件批量顺序上传
  - 大于 50MB 走 multipart, 小于走 single endpoint

  数据流:
  1. 拖拽/选择文件 → fileList 累加
  2. 用户选 folder_id + visibility
  3. 点"开始上传" → 顺序上传每个文件 (Promise 链)
  4. emit('uploaded', { count, folderId })
-->
<template>
  <el-dialog
    v-model="visible"
    class="drive-dialog"
    :title="props.isTeamShared ? '上传到团队共享盘' : '上传到网盘'"
    width="640px"
    :close-on-click-modal="false"
    :close-on-press-escape="!uploading"
    @closed="resetForm"
  >
    <!-- v2 PR6-P19: 团队共享盘上传横幅 -->
    <div
      v-if="props.isTeamShared"
      class="drive-upload-team-banner"
    >
      <el-icon><Share /></el-icon>
      <span>此文件将上传到「团队共享盘」, <strong>不会显示在您的个人网盘</strong>。如需个人可见, 请先切换回「我的网盘」再上传。</span>
    </div>
    <!-- 文件接收区 -->
    <div
      class="drive-upload-drop-zone"
      :class="{ 'is-drag-over': isDragging }"
      ref="dropZoneRef"
      @click="triggerFileInput"
    >
      <el-icon :size="48" class="drive-upload-drop-icon"><UploadFilled /></el-icon>
      <p class="drive-upload-drop-title">点击或拖拽文件到此处</p>
      <p class="drive-upload-drop-hint">
        支持文件夹拖拽 (Chrome/Edge/Safari), Firefox 仅单文件
      </p>
      <input
        ref="fileInputRef"
        type="file"
        multiple
        :webkitdirectory="webkitDirectorySupported"
        style="display: none;"
        @change="onFileInputChange"
      />
    </div>

    <!-- 文件列表 + 进度 -->
    <div v-if="fileItems.length > 0" class="drive-upload-file-list">
      <div class="drive-upload-file-list-header">
        <span>待上传文件 ({{ fileItems.length }})</span>
        <el-button v-if="!uploading" size="small" text @click="clearFiles">清空</el-button>
      </div>
      <div
        v-for="(item, idx) in fileItems"
        :key="idx"
        class="drive-upload-file-item"
      >
        <el-icon class="drive-upload-file-icon">
          <Document />
        </el-icon>
        <div class="drive-upload-file-info">
          <div class="drive-upload-file-name" :title="item.relativePath">
            {{ item.relativePath }}
          </div>
          <div class="drive-upload-file-meta">
            {{ formatSize(item.file.size) }}
            <el-tag v-if="item.status === 'done'" type="success" size="small">✓ 完成</el-tag>
            <el-tag v-else-if="item.status === 'error'" type="danger" size="small">✗ 失败</el-tag>
            <el-tag v-else-if="item.status === 'uploading'" type="warning" size="small">上传中</el-tag>
          </div>
        </div>
        <el-progress
          v-if="item.status === 'uploading'"
          :percentage="item.progress"
          :stroke-width="6"
          class="drive-upload-file-progress"
        />
      </div>
    </div>

    <!-- 配置区 -->
    <el-form :model="form" label-width="100px" :disabled="uploading" class="drive-upload-form">
      <el-form-item label="目标文件夹">
        <el-select v-model="form.folderId" placeholder="选择目标文件夹 (留空=顶级)" clearable filterable>
          <el-option label="📁 顶级目录 (我的网盘)" :value="null" />
          <template v-for="f in flatFolderOptions" :key="f.id">
            <el-option :label="f.label" :value="f.id" />
          </template>
        </el-select>
      </el-form-item>
      <el-form-item label="可见性">
        <el-radio-group v-model="form.visibility">
          <el-radio value="private">🔒 私有</el-radio>
          <el-radio value="team">👥 团队</el-radio>
          <el-radio value="public">🌐 公开</el-radio>
        </el-radio-group>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false" :disabled="uploading">取消</el-button>
      <el-button
        type="primary"
        :loading="uploading"
        :disabled="fileItems.length === 0"
        @click="onSubmit"
      >
        {{ uploading ? `上传中 (${uploadedCount}/${fileItems.length})` : '开始上传' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
// v2.0 (2026-07-09) Drive 美化: 引入 drive-view.css 让 .drive-dialog 玻璃态生效
import '@/views/drive/drive-view.css'
import { ref, reactive, computed, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, Document, Share } from '@element-plus/icons-vue'
import { useFolderDropZone } from '@/composables/useFolderDropZone'
import { useFolderTree } from '@/composables/useFolderTree'
import { useFileHash } from '@/composables/useFileHash'   // PR4
import { useDriveFiles } from '@/composables/useDriveFiles' // PR4

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  defaultFolderId: { type: [Number, null], default: null },
  // v2 PR6-P19: 团队共享盘标识 (DesktopDriveView 切到 team 视图时上传传 true)
  isTeamShared: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'uploaded'])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

// === 状态 ===
const dropZoneRef = ref(null)
const fileInputRef = ref(null)
const fileItems = ref([])  // [{ file, relativePath, status, progress }]
const uploading = ref(false)
const uploadedCount = ref(0)

// PR4: useFileHash (复用同一个 worker 实例避免重复创建) + useDriveFiles (instantUpload)
const { calc: calcHash } = useFileHash()
const { instantUpload } = useDriveFiles()

const form = reactive({
  folderId: props.defaultFolderId,
  visibility: 'team'
})

// === 文件夹列表 (供 TreeSelect) ===
const { folderTree, fetchTree } = useFolderTree()
const flatFolderOptions = computed(() => {
  const opts = []
  function walk(nodes, depth = 0) {
    for (const n of nodes) {
      opts.push({ id: n.id, label: `${'─'.repeat(depth)} ${n.name}` })
      if (n.children?.length) walk(n.children, depth + 1)
    }
  }
  walk(folderTree.value || [])
  return opts
})

// === 检测 webkitdirectory 支持 ===
const webkitDirectorySupported = computed(() => {
  // Chrome / Edge / Safari 支持, Firefox 不支持
  return 'webkitdirectory' in document.createElement('input')
})

// === 文件夹拖拽 ===
const { isDragging, bind: bindDropZone, unbind: unbindDropZone } = useFolderDropZone({
  onFilesDropped: ({ entries }) => {
    addFiles(entries)
  }
})

watch(visible, async (newVal) => {
  if (newVal) {
    await nextTick()
    if (dropZoneRef.value) bindDropZone(dropZoneRef.value)
    await fetchTree()
  } else {
    unbindDropZone()
  }
})

// === 文件接收 ===
function triggerFileInput() {
  fileInputRef.value?.click()
}

function onFileInputChange(e) {
  const files = Array.from(e.target.files || [])
  const entries = files.map(f => ({
    file: f,
    relativePath: f.webkitRelativePath || f.name
  }))
  addFiles(entries)
  // 重置 input value (允许重复选同一文件)
  e.target.value = ''
}

function addFiles(entries) {
  const newItems = entries.map(({ file, relativePath }) => ({
    file,
    relativePath,
    status: 'pending',
    progress: 0
  }))
  fileItems.value = [...fileItems.value, ...newItems]
  ElMessage.success(`已添加 ${newItems.length} 个文件`)
}

function clearFiles() {
  fileItems.value = []
  uploadedCount.value = 0
}

function formatSize(bytes) {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
}

function resetForm() {
  fileItems.value = []
  uploadedCount.value = 0
  form.folderId = props.defaultFolderId
  form.visibility = 'team'
}

// === 上传逻辑 ===
async function onSubmit() {
  if (fileItems.value.length === 0) return
  uploading.value = true
  uploadedCount.value = 0
  try {
    // 顺序上传 (Promise 链)
    for (let i = 0; i < fileItems.value.length; i++) {
      const item = fileItems.value[i]
      if (item.status === 'done') continue
      try {
        await uploadOne(item)
        item.status = 'done'
        item.progress = 100
      } catch (e) {
        item.status = 'error'
        console.error(`上传失败: ${item.relativePath}`, e)
      }
      uploadedCount.value = i + 1
    }
    const successCount = fileItems.value.filter(i => i.status === 'done').length
    if (successCount > 0) {
      ElMessage.success(`上传完成: ${successCount}/${fileItems.value.length}`)
      emit('uploaded', { count: successCount, folderId: form.folderId })
      // 短暂延迟后关闭 dialog
      setTimeout(() => {
        visible.value = false
      }, 1000)
    } else {
      ElMessage.error('所有文件上传失败')
    }
  } finally {
    uploading.value = false
  }
}

async function uploadOne(item) {
  // v2 PR4: 秒传先查 hash, 命中走零带宽 dedup (仅小文件)
  // 大文件 multipart 暂不秒传 (PR5 范围)
  const SMALL_FILE_THRESHOLD = 50 * 1024 * 1024  // 50MB

  // PR4 step 1: 算 hash (仅小文件, 大文件 multipart 不秒传)
  if (item.file.size < SMALL_FILE_THRESHOLD && item.file.size < 100 * 1024 * 1024) {
    item.status = 'hashing'
    item.progress = 0
    try {
      const fileHash = await calcHash(item.file)
      item.fileHash = fileHash

      // PR4 step 2: 查 instant-upload
      item.status = 'checking-instant'
      const instant = await instantUpload({
        fileHash,
        fileName: item.file.name,
        fileSize: item.file.size,
        folderId: form.folderId || null,
        visibility: form.visibility,
        isTeamShared: !!props.isTeamShared,  // v2 PR6-P19
      })

      if (instant.instant) {
        // PR4 step 3a: 命中秒传 → 跳过文件上传
        item.status = 'done-instant'
        item.dedupSavedBytes = instant.dedup_saved_bytes
        item.fileId = instant.file_id
        item.progress = 100
        return  // 秒传完成, 不走 multipart
      }
      // instant=false → 走老路径
    } catch (e) {
      // hash 失败 / instant-upload 报错 → 不阻塞, 降级到普通上传
      console.warn('[PR4] hash/instant-upload 失败, 降级普通上传:', e)
    }
  }

  item.status = 'uploading'
  item.progress = 0

  if (item.file.size < SMALL_FILE_THRESHOLD) {
    // 小文件: 单端点上传
    const formData = new FormData()
    formData.append('file', item.file)
    formData.append('folder_id', form.folderId || '')
    formData.append('visibility', form.visibility)
    formData.append('storage_mode', 'drive')

    await axios.post('/api/v1/drive/files/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (e.total) {
          item.progress = Math.round((e.loaded / e.total) * 100)
        }
      }
    })
  } else {
    // 大文件: multipart 3 阶段 (init + complete + abort on error)
    // ⚠️ 后端 schema (MultipartInitRequest) 用 `filename` + `total_size`, 区别于
    //    PR4 `/drive/files/instant-upload` 的 `file_name` + `file_size` 命名约定.
    //    见 app/api/v1/upload_multipart.py:5 docstring 的 canonical wire format.
    const initResp = await axios.post('/api/v1/upload/multipart/init', {
      filename: item.file.name,
      total_size: item.file.size,
      content_type: item.file.type || 'application/octet-stream'
    })
    const uploadId = initResp.data.upload_id

    try {
      const completeForm = new FormData()
      completeForm.append('upload_id', uploadId)
      completeForm.append('folder_id', form.folderId || '')
      completeForm.append('visibility', form.visibility)
      completeForm.append('storage_mode', 'drive')
      completeForm.append('data', item.file)

      await axios.post('/api/v1/upload/multipart/complete', completeForm, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
          if (e.total) {
            item.progress = Math.round((e.loaded / e.total) * 100)
          }
        }
      })
    } catch (e) {
      // 失败回滚: 通知后端清理 MinIO
      await axios.post('/api/v1/upload/multipart/abort', { upload_id: uploadId }).catch(() => {})
      throw e
    }
  }
}
</script>

<script>
import axios from 'axios'
export default { name: 'DriveUploadDialog' }
</script>

<style scoped>
.drive-upload-drop-zone {
  border: 2px dashed var(--color-border-light, #dcdfe6);
  border-radius: 8px;
  padding: 32px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--color-bg-light, #fafbfc);
}

.drive-upload-drop-zone:hover {
  border-color: var(--color-primary, #409eff);
  background: var(--color-primary-light-9, #ecf5ff);
}

.drive-upload-drop-zone.is-drag-over {
  border-color: var(--color-primary, #409eff);
  background: var(--color-primary-light-9, #ecf5ff);
  border-style: solid;
}

.drive-upload-drop-icon {
  color: var(--color-primary, #409eff);
  margin-bottom: 8px;
}

.drive-upload-drop-title {
  font-size: 16px;
  font-weight: 500;
  margin: 0 0 4px 0;
  color: var(--color-text-primary, #303133);
}

.drive-upload-drop-hint {
  font-size: 12px;
  margin: 0;
  color: var(--color-text-placeholder, #909399);
}

.drive-upload-file-list {
  margin-top: 16px;
  border: 1px solid var(--color-border-lighter, #f0f0f0);
  border-radius: 4px;
  padding: 12px;
  max-height: 240px;
  overflow-y: auto;
}

.drive-upload-file-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary, #303133);
}

.drive-upload-file-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px solid var(--color-border-lighter, #f5f7fa);
}

.drive-upload-file-item:last-child {
  border-bottom: none;
}

.drive-upload-file-icon {
  color: var(--color-primary, #409eff);
  flex-shrink: 0;
}

.drive-upload-file-info {
  flex: 1;
  min-width: 0;
}

.drive-upload-file-name {
  font-size: 13px;
  color: var(--color-text-primary, #303133);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.drive-upload-file-meta {
  font-size: 11px;
  color: var(--color-text-secondary, #909399);
  margin-top: 2px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.drive-upload-file-progress {
  width: 120px;
  flex-shrink: 0;
}

.drive-upload-form {
  margin-top: 20px;
}

/* v2 PR6-P19: 团队共享盘上传横幅 (橙黄高亮) */
.drive-upload-team-banner {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  margin-bottom: var(--space-3);
  background: linear-gradient(135deg, rgba(255, 179, 71, 0.12), rgba(255, 122, 92, 0.08));
  border: 1px solid var(--color-accent);
  border-radius: var(--radius-md);
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
  line-height: 1.5;
}

.drive-upload-team-banner :deep(.el-icon) {
  color: var(--color-accent);
  font-size: 18px;
  flex-shrink: 0;
}

.drive-upload-team-banner strong {
  color: var(--color-primary);
  font-weight: var(--weight-semibold, 600);
}
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  本组件 PR3.7 统一审计时再加 dark 块
-->