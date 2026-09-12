<!--
  DriveTrashPanel.vue — 回收站 inline Panel (2026-07-02)

  设计:
  - 从 DriveTrashView 抽取 body 内容 (BatchActionToolbar + FileGrid)
  - 不含 page-container / page-header / 返回网盘按钮 (由 DesktopDriveView 的 breadcrumb 提供)
  - 当 DesktopDriveView 的 specialView === 'trash' 时 inline 渲染
  - URL 直跳 /drive/trash 仍走 DriveTrashView 全屏版 (保留 mobile + URL 兼容性)

  Props: 无 (self-contained, 通过 composable 取数)

  Dark mode: 用 var(--color-*) token 跟随 6 主题
-->
<template>
  <!-- 批次⑩.74: 静默档案条替代旧红橙 hero — 标题 + 30 天清除 chip + 共 N 项 -->
  <div class="drive-trash-panel">
    <div class="trash-strip">
      <span class="trash-strip-title">🗑️ 回收站</span>
      <span class="trash-strip-chip">已删除文件 30 天后自动清除</span>
      <span class="trash-strip-count">共 {{ total }} 项</span>
    </div>
    <BatchActionToolbar
      :selected-count="selectedFileIds.length"
      :total-count="driveFiles.length"
      context="trash"
      @select-all="selectAll"
      @clear="clearSelection"
      @batch-restore="handleBatchRestore"
      @batch-permanent-delete="handleBatchPermanentDelete"
    />

    <div class="trash-content">
      <FileGrid
        :files="driveFiles"
        :total="total"
        :current-page="currentPage"
        :page-size="pageSize"
        :selected-file-ids="selectedFileIds"
        :loading="loading"
        :load-error="loadError"
        :view-mode="viewMode"
        :is-top-level="true"
        :trash-context="true"
        @retry="fetchTrash"
        @file-click="handleFileClick"
        @file-restore="handleRestoreSingle"
        @file-delete="handlePermanentDeleteSingle"
        @page-change="handlePageChange"
      />
    </div>
  </div>
</template>

<script setup>
// v2.0 (2026-07-09) Drive 美化: 引入 drive-view.css 让 .drive-panel 玻璃态生效
import '@/views/drive/drive-view.css'
import { ref, onMounted } from 'vue'
// 不需要 useRouter (没有 goBack; DesktopDriveView breadcrumb 是返回入口)
// 不需要 ArrowLeft icon
import { ElMessage, ElMessageBox } from 'element-plus'

import { useDriveFiles } from '@/composables/useDriveFiles'
import BatchActionToolbar from '@/components/drive/BatchActionToolbar.vue'
import FileGrid from '@/components/drive/FileGrid.vue'

// 复用 PR3.3 composable, fetchTrash 已在 useDriveFiles.js:216 保留
const {
  driveFiles, total, currentPage, pageSize, loading, loadError,
  selectedFileIds,
  fetchTrash, batchRestore, permanentDeleteBatch,
  toggleSelect, clearSelection, selectAll
} = useDriveFiles()

const viewMode = ref('list')  // 回收站默认 list 模式 (表格更清晰)

// 批次⑩.86: 恢复/彻底删除后通知父层刷新侧栏计数 (trash/starred 计数变化,
// 此前面板内部自管数据, 父层无法感知)
const emit = defineEmits(['changed'])

async function reload() {
  currentPage.value = 1
  await fetchTrash()
}

async function handlePageChange(p) {
  currentPage.value = p
  await fetchTrash({ page: p })
}

async function handleBatchRestore() {
  if (selectedFileIds.value.length === 0) return
  try {
    await ElMessageBox.confirm(
      `确定要恢复 ${selectedFileIds.value.length} 个文件吗?`,
      '批量恢复',
      { type: 'success' }
    )
    const resp = await batchRestore(selectedFileIds.value)
    if (resp.skipped_ids?.length) {
      ElMessage.warning(`已恢复 ${resp.succeeded_count} 个, 跳过 ${resp.skipped_ids.length} 个`)
    } else {
      ElMessage.success(`已恢复 ${resp.succeeded_count} 个文件`)
    }
    await reload()
    emit('changed')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '恢复失败')
  }
}

async function handleBatchPermanentDelete() {
  if (selectedFileIds.value.length === 0) return
  try {
    await ElMessageBox.confirm(
      `确定要彻底删除 ${selectedFileIds.value.length} 个文件吗? 此操作不可撤销!`,
      '彻底删除',
      { type: 'error', confirmButtonText: '彻底删除', cancelButtonText: '取消' }
    )
    const resp = await permanentDeleteBatch(selectedFileIds.value)
    ElMessage.success(`已彻底删除 ${resp.succeeded_count} 个文件`)
    await reload()
    emit('changed')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

async function handlePermanentDeleteSingle(file) {
  try {
    await ElMessageBox.confirm(
      `确定要彻底删除 "${file.file_name}" 吗? 此操作不可撤销!`,
      '彻底删除',
      { type: 'error', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    await permanentDeleteBatch([file.id])
    ElMessage.success('已删除')
    await reload()
    emit('changed')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

// 批次⑩.74: 单文件恢复 (FileGrid trash 上下文「↩ 恢复」ghost 钮) — 非破坏性操作免确认
async function handleRestoreSingle(file) {
  try {
    const resp = await batchRestore([file.id])
    if (resp.skipped_ids?.length) {
      ElMessage.warning(`恢复被跳过: ${file.file_name}`)
    } else {
      ElMessage.success(`已恢复 "${file.file_name}"`)
    }
    await reload()
    emit('changed')
  } catch (e) {
    ElMessage.error(e.message || '恢复失败')
  }
}

function handleFileClick(file) {
  // 回收站无 preview/download (避免永久链接泄露)
  ElMessage.info('回收站文件无法预览, 请先恢复')
}

onMounted(() => {
  reload()
})
</script>

<style scoped>
.trash-content {
  min-height: 300px;
}

/* 批次⑩.74: 静默档案条 (替代旧红橙 hero) — 标题 + chip + mono 计数 */
.trash-strip {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--color-border-light);
  margin-bottom: 4px;
}
.trash-strip-title {
  font-size: 14px;
  font-weight: 650;
  color: var(--color-text-primary);
}
.trash-strip-chip {
  font-family: Consolas, 'SFMono-Regular', monospace;
  font-size: 10px;
  letter-spacing: 0.05em;
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border-light);
  border-radius: 5px;
  padding: 2px 8px;
  background: var(--color-bg-warm);
}
.trash-strip-count {
  margin-left: auto;
  font-family: Consolas, 'SFMono-Regular', monospace;
  font-size: 10px;
  letter-spacing: 0.06em;
  color: var(--color-text-secondary);
}

[data-theme='dark'] .trash-strip {
  border-bottom-color: var(--color-border-light);
}
[data-theme='dark'] .trash-strip-chip {
  background: rgba(255, 255, 255, 0.03);
  border-color: rgba(226, 236, 234, 0.14);
  color: var(--color-text-secondary);
}
</style>
