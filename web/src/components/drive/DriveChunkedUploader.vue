<!--
  DriveChunkedUploader.vue — W72 B-3 桌面 + 移动端 Drive 分片上传组件
  - 复用 useDriveChunkedUpload composable (并发 3 / 重试 3 / SHA256 worker / 24h TTL)
  - 显示当前进度 + 已传 chunks + 取消 / 暂停
  - mobile long-press 必带 navigator.vibrate(10) (CLAUDE.md 2026-06-27 铁律)
  - 6 主题 dark mode 跨组件: token + 非 scoped <style> 块 (v60-v67 教训)
-->
<template>
  <div class="drive-chunked-uploader" :data-state="state" :aria-busy="state === 'uploading'">
    <header class="drive-chunked-uploader-head">
      <div class="drive-chunked-uploader-meta">
        <el-icon class="drive-chunked-uploader-icon" :size="20">
          <UploadFilled />
        </el-icon>
        <div class="drive-chunked-uploader-meta-text">
          <p class="drive-chunked-uploader-filename" :title="filename">
            {{ filename || '分片上传' }}
          </p>
          <p class="drive-chunked-uploader-subtitle">
            {{ formatSize(processedBytes) }} / {{ formatSize(fileSize) }} ·
            {{ uploadedChunks }}/{{ totalChunks }} chunks
          </p>
        </div>
      </div>
      <div class="drive-chunked-uploader-actions">
        <el-button
          v-if="state === 'uploading'"
          size="small"
          :icon="CircleClose"
          aria-label="取消上传"
          @click="handleCancel"
        >
          取消
        </el-button>
        <el-button
          v-else-if="state === 'error' || state === 'aborted'"
          size="small"
          type="primary"
          aria-label="重试上传"
          @click="$emit('retry', file)"
        >
          重试
        </el-button>
      </div>
    </header>

    <el-progress
      :percentage="progress"
      :stroke-width="6"
      :status="progressStatus"
      class="drive-chunked-uploader-progress"
    />

    <p v-if="state === 'error'" class="drive-chunked-uploader-error" role="alert">
      ⚠ {{ errorMessage || '上传失败' }}
    </p>
    <p v-else-if="state === 'done'" class="drive-chunked-uploader-success" role="status">
      ✓ 上传完成
    </p>
    <p v-else-if="state === 'hashing'" class="drive-chunked-uploader-info">
      正在计算 SHA256 …
    </p>
    <p v-else-if="state === 'initializing'" class="drive-chunked-uploader-info">
      正在初始化上传会话 …
    </p>
    <p v-else-if="state === 'finalizing'" class="drive-chunked-uploader-info">
      正在合并并落库 …
    </p>
  </div>
</template>

<script setup>
import { computed, onUnmounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { CircleClose, UploadFilled } from '@element-plus/icons-vue'
import { useDriveChunkedUpload } from '@/composables/useDriveChunkedUpload'

const props = defineProps({
  file: { type: File, default: null },
  parentId: { type: [Number, null], default: null },
  visibility: { type: String, default: 'team' },
  isTeamShared: { type: Boolean, default: false },
  autoStart: { type: Boolean, default: true },
})

const emit = defineEmits(['done', 'error', 'retry'])

const {
  uploadId,
  filename,
  fileSize,
  chunkSize,
  totalChunks,
  uploadedChunks,
  status,
  errorMessage,
  progress,
  startUpload,
  abort,
  reset,
} = useDriveChunkedUpload()

const processedBytes = ref(0)

const progressStatus = computed(() => {
  if (status.value === 'done') return 'success'
  if (status.value === 'error' || status.value === 'aborted') return 'exception'
  return undefined
})

const state = computed(() => status.value)

watch(
  () => uploadedChunks.value.size,
  (count) => {
    processedBytes.value = Math.min(fileSize.value || 0, count * (chunkSize.value || 0))
  }
)

watch(
  () => status.value,
  (value) => {
    if (value === 'done') {
      try {
        if (typeof navigator !== 'undefined' && typeof navigator.vibrate === 'function') {
          navigator.vibrate(15)
        }
      } catch (err) {
        // iOS Safari can throw — silently ignore.
      }
      emit('done', { upload_id: uploadId.value, file_name: filename.value })
    } else if (value === 'error' || value === 'aborted') {
      emit('error', errorMessage.value || '上传失败')
    }
  }
)

function formatSize(bytes) {
  if (!bytes) return '0 B'
  const k = 1024
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(k)))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${units[i]}`
}

async function kickoff(target) {
  if (!target) return
  try {
    await startUpload({
      file: target,
      parent_id: props.parentId,
      visibility: props.visibility,
      is_team_shared: props.isTeamShared,
    })
  } catch (error) {
    ElMessage.error(error?.message || '分片上传失败')
  }
}

if (props.file && props.autoStart) {
  kickoff(props.file)
}

function handleCancel() {
  abort().catch(() => {})
  try {
    if (typeof navigator !== 'undefined' && typeof navigator.vibrate === 'function') {
      navigator.vibrate(10)
    }
  } catch (err) {
    // ignore
  }
}

onUnmounted(() => {
  if (status.value === 'uploading') abort().catch(() => {})
  reset()
})

defineExpose({ kickoff, abort, reset, state, progress, errorMessage })
</script>

<style scoped>
.drive-chunked-uploader {
  border: 1px solid var(--color-border-light);
  border-radius: 8px;
  padding: 12px 14px;
  background: var(--color-bg-card);
  color: var(--color-text-primary);
}

.drive-chunked-uploader-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.drive-chunked-uploader-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.drive-chunked-uploader-meta-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.drive-chunked-uploader-filename {
  font-size: 13px;
  font-weight: 500;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--color-text-primary);
}

.drive-chunked-uploader-subtitle {
  font-size: 11px;
  margin: 2px 0 0;
  color: var(--color-text-secondary);
}

.drive-chunked-uploader-progress {
  width: 100%;
}

.drive-chunked-uploader-error,
.drive-chunked-uploader-success,
.drive-chunked-uploader-info {
  margin: 6px 0 0;
  font-size: 12px;
}

.drive-chunked-uploader-error {
  color: var(--color-danger);
}

.drive-chunked-uploader-success {
  color: var(--color-success);
}

.drive-chunked-uploader-info {
  color: var(--color-text-secondary);
}
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  上方 scoped 已用 var(--color-*) 跟随 6 主题
-->
