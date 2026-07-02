<!--
  DriveTrashView.vue — 课题组网盘 v2 PR2 回收站视图

  功能:
  - 顶部 PageHeader (面包屑 返回网盘 + 标题 "回收站")
  - BatchActionToolbar (trash context: 恢复/删除)
  - FileGrid (复用, viewMode=list 突出表格)
  - 三态空态: loading / error / 90 天后自动清空提示
  - dark mode: 末尾非 scoped <style> 块 (v60-v67 教训)

  Props: 无 (顶层路由 /drive/trash)
  2026-07-02: 恢复 page-container + 返回网盘按钮 (PR7 nested route 回滚后顶级 sibling 模式)
-->
<template>
  <div class="page-container drive-trash-view">
    <div class="page-header">
      <div class="page-header-left">
        <el-button :icon="ArrowLeft" text @click="goBack">返回网盘</el-button>
        <h2 class="page-title">🗑️ 回收站</h2>
        <el-tag size="small" type="info">3 天后自动清除</el-tag>
      </div>
      <div class="page-header-right">
        <span class="trash-stat">共 {{ total }} 个文件 / 文件夹</span>
      </div>
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
        @retry="fetchTrash"
        @file-click="handleFileClick"
        @file-preview="handleFilePreview"
        @file-delete="handlePermanentDeleteSingle"
        @toggle-select="toggleSelect"
        @page-change="handlePageChange"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
// 2026-07-02: 恢复 ArrowLeft + useRouter + goBack (PR7 nested route 回滚后顶级 sibling 模式)
import { ArrowLeft } from '@element-plus/icons-vue'

import { useDriveFiles } from '@/composables/useDriveFiles'
import BatchActionToolbar from '@/components/drive/BatchActionToolbar.vue'
import FileGrid from '@/components/drive/FileGrid.vue'

// 2026-07-02: 恢复 router 实例 (PR7 删除后回滚)
const router = useRouter()

// 复用 PR3.3 composable, 但覆盖 fetch 用 fetchTrash
const {
  driveFiles, total, currentPage, pageSize, loading, loadError,
  selectedFileIds,
  fetchTrash, batchRestore, permanentDeleteBatch,
  toggleSelect, clearSelection, selectAll
} = useDriveFiles()

const viewMode = ref('list')  // 回收站默认 list 模式 (表格更清晰)

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
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

function handleFileClick(file) {
  // 回收站无 preview/download (避免永久链接泄露)
  ElMessage.info('回收站文件无法预览, 请先恢复')
}

function handleFilePreview(file) {
  handleFileClick(file)
}

// 2026-07-02: 恢复 goBack (PR7 nested route 回滚后顶级 sibling 模式)
function goBack() {
  router.push('/drive')
}

onMounted(() => {
  reload()
})
</script>

<style scoped>
/* 2026-07-02: 恢复 .page-container (PR7 回滚后顶级 sibling 模式, padding 由 view 自身提供) */
.page-container {
  padding: 16px 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  gap: 12px;
}

.page-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary, #303133);
}

.page-header-right {
  color: var(--color-text-secondary, #606266);
  font-size: 13px;
}

.trash-stat {
  font-size: 13px;
  color: var(--color-text-secondary, #606266);
}

.trash-content {
  min-height: 300px;
}
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  本 view 已用 var(--color-*) token 跟随 6 主题, dark 块由 variables.css 全局接管
-->