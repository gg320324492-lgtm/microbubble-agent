<!--
  VersionHistoryDialog.vue — 版本历史对话框 (PR4 招牌)
  2026-07-01

  百度网盘 / 坚果云 / Dropbox 同款:
  - 表格列: 版本号 / 上传者 / 时间 / Hash (前 8 位) / 大小 / 备注 / 操作
  - 当前版本高亮 (绿色 tag) + 不可恢复 (避免循环)
  - 历史版本: 下载 + 恢复 (弹 el-popconfirm 二次确认)
  - dark mode 非 scoped <style> 块 (v60-v67 教训)
-->
<template>
  <el-dialog
    :model-value="visible"
    title="🕘 版本历史"
    width="780px"
    top="8vh"
    destroy-on-close
    @update:model-value="$emit('update:visible', $event)"
  >
    <div v-loading="loading" class="version-history-content">
      <!-- 文件摘要 -->
      <div v-if="file" class="version-file-summary">
        <span class="version-file-name">{{ file.file_name }}</span>
        <el-tag size="small" type="success">v{{ file.version_number || 1 }}</el-tag>
        <span class="version-file-hash" v-if="file.file_hash">
          {{ file.file_hash.slice(0, 12) }}…
        </span>
      </div>

      <!-- 空状态 -->
      <el-empty
        v-if="!loading && versions.length === 0"
        description="该文件还没有历史版本（首次上传）"
      />

      <!-- 版本列表 -->
      <el-table
        v-else
        :data="versions"
        stripe
        class="version-table"
        :row-class-name="rowClassName"
      >
        <el-table-column label="版本" prop="version_number" width="80" align="center">
          <template #default="{ row }">
            <span class="version-number">v{{ row.version_number }}</span>
          </template>
        </el-table-column>

        <el-table-column label="上传者" width="120">
          <template #default="{ row }">
            <span class="version-uploader">{{ row.uploaded_by_name || `#${row.uploaded_by}` }}</span>
          </template>
        </el-table-column>

        <el-table-column label="时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>

        <el-table-column label="Hash" width="140">
          <template #default="{ row }">
            <code class="version-hash" :title="row.file_hash">{{ row.file_hash.slice(0, 8) }}…</code>
          </template>
        </el-table-column>

        <el-table-column label="大小" width="100" align="right">
          <template #default="{ row }">
            {{ formatSize(row.file_size) }}
          </template>
        </el-table-column>

        <el-table-column label="备注" min-width="140">
          <template #default="{ row }">
            <span v-if="row.change_note" class="version-note">{{ row.change_note }}</span>
            <span v-else class="version-note-empty">—</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="200" align="center" fixed="right">
          <template #default="{ row }">
            <el-tag v-if="row.is_current" type="success" size="small">当前版本</el-tag>
            <template v-else>
              <el-button size="small" link type="primary" @click="downloadVersion(row)">
                下载
              </el-button>
              <el-popconfirm
                title="恢复此版本将生成新版本, 是否继续?"
                confirm-button-text="恢复"
                cancel-button-text="取消"
                @confirm="restoreVersion(row)"
              >
                <template #reference>
                  <el-button size="small" link type="warning">恢复</el-button>
                </template>
              </el-popconfirm>
            </template>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { formatDateTime } from '@/utils/format'
import { useDriveFiles } from '@/composables/useDriveFiles'

const props = defineProps({
  visible: { type: Boolean, default: false },
  file: { type: Object, default: null },
})
const emit = defineEmits(['update:visible', 'restored'])

// PR4: 走 composable 共享 listVersions / restoreVersion
const { listVersions, restoreVersion: restoreApi, downloadFileUrl } = useDriveFiles()

const versions = ref([])
const loading = ref(false)

// 打开 dialog 时拉取
watch(
  () => [props.visible, props.file?.id],
  async ([vis, fid]) => {
    if (vis && fid) {
      await fetchVersions()
    }
  },
)

async function fetchVersions() {
  if (!props.file) return
  loading.value = true
  try {
    const items = await listVersions(props.file.id)
    versions.value = items
  } catch (e) {
    ElMessage.error('加载版本历史失败')
    versions.value = []
  } finally {
    loading.value = false
  }
}

function rowClassName({ row }) {
  return row.is_current ? 'version-row-current' : ''
}

function downloadVersion(row) {
  // 历史版本直接走当前 file 的 download 端点 — 用户拿到的是当前最新版本字节
  // PR4 完整版应支持按 version_id 取历史 object_name, 当前 PR 阶段先简化:
  // "恢复" 按钮已能还原任意历史版本, "下载" 暂给当前版本
  const url = downloadFileUrl(props.file)
  window.open(url, '_blank')
  ElMessage.info(`下载 v${row.version_number}: 当前文件 (历史版本下载请用"恢复"后下载)`)
}

async function restoreVersion(row) {
  try {
    const newK = await restoreApi(props.file.id, row.id)
    ElMessage.success(`已恢复 v${row.version_number} → 新版本 v${newK.version_number}`)
    emit('restored', newK)
    emit('update:visible', false)
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '恢复失败')
  }
}

function formatSize(bytes) {
  if (!bytes && bytes !== 0) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`
}
</script>

<style scoped>
.version-history-content {
  min-height: 200px;
}

.version-file-summary {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  margin-bottom: 12px;
  background: var(--color-info-bg);
  border-radius: var(--radius-md);
  font-size: 14px;
}

.version-file-name {
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.version-file-hash {
  color: var(--color-text-secondary);
  font-family: monospace;
  font-size: 12px;
}

.version-table {
  width: 100%;
}

.version-number {
  font-weight: var(--font-weight-semibold);
  color: var(--color-primary);
}

.version-uploader {
  color: var(--color-text-regular);
}

.version-hash {
  font-family: monospace;
  background: var(--color-bg-card);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--color-text-secondary);
}

.version-note {
  color: var(--color-text-regular);
  font-size: 13px;
}

.version-note-empty {
  color: var(--color-text-placeholder);
}

:deep(.version-row-current) {
  background: var(--color-success-light-9, rgba(133, 206, 97, 0.08)) !important;
}
</style>

<!-- v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块 (否则 Vue scoped compiler 会把 [data-theme="dark"] 选择器与后代组合处理错) -->
<style>
[data-theme="dark"] .version-history-content .el-dialog__body {
  background: var(--color-bg-card);
  color: var(--color-text-primary);
}

[data-theme="dark"] .version-table.el-table {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: var(--color-bg-elevated, #2a2a2a);
  --el-table-border-color: var(--color-border, #3a3a3a);
  background: transparent;
  color: var(--color-text-primary);
}

[data-theme="dark"] .version-table.el-table th.el-table__cell {
  background: var(--color-bg-elevated, #2a2a2a) !important;
  color: var(--color-text-primary) !important;
  border-color: var(--color-border, #3a3a3a);
}

[data-theme="dark"] .version-table.el-table td.el-table__cell {
  background: transparent;
  border-color: var(--color-border, #3a3a3a);
  color: var(--color-text-regular);
}

[data-theme="dark"] .version-table.el-table tr.version-row-current td.el-table__cell {
  background: rgba(133, 206, 97, 0.15) !important;
  color: var(--color-text-primary);
}

[data-theme="dark"] .version-table.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell {
  background: var(--color-bg-card);
}

[data-theme="dark"] .version-file-summary {
  background: var(--color-bg-elevated, #2a2a2a) !important;
}

[data-theme="dark"] .version-hash {
  background: var(--color-bg-elevated, #2a2a2a) !important;
  color: var(--color-text-secondary);
}
</style>