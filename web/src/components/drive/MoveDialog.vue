<!--
  MoveDialog.vue — 课题组网盘 PR3.4 移动到目标文件夹对话框
  2026-07-01

  设计:
  - 文件夹树 picker (el-tree 显示层级, 单选目标)
  - 顶级选项: "📁 顶级目录 (我的网盘)"
  - 当前文件夹 + 选中文件夹自动展开
  - 选中后 confirm 触发 emit('move', { id, target_folder_id })

  隐私边界:
  - 目标文件夹 visibility 是 file 的"硬上限"
  - 移动时 service 层自动升级 file.visibility (PR2.4 folder_service 实现)
-->
<template>
  <el-dialog
    v-model="visible"
    title="移动到"
    width="480px"
    :close-on-click-modal="false"
  >
    <div class="move-dialog-hint">
      选择目标文件夹。如果目标文件夹可见性更公开，文件可见性将自动升级。
    </div>

    <div class="move-dialog-tree-wrapper">
      <!-- 顶级选项 -->
      <div
        class="move-dialog-root-option"
        :class="{ active: selectedFolderId === null }"
        @click="selectedFolderId = null"
      >
        <el-icon><Folder /></el-icon>
        <span>📁 顶级目录 (我的网盘)</span>
      </div>

      <!-- 文件夹树 -->
      <FolderTree
        :folder-tree="folderTree"
        :selected-folder-id="selectedFolderId"
        :expanded-folder-ids="expandedFolderIds"
        @update:selected-folder-id="selectedFolderId = $event"
        @toggle-expanded="toggleExpanded"
      />
    </div>

    <!-- 选中信息 -->
    <div v-if="targetFolderInfo" class="move-dialog-target-info">
      已选择: <strong>{{ targetFolderInfo }}</strong>
      <el-tag
        v-if="targetVisibility"
        :type="visibilityTagType(targetVisibility)"
        size="small"
        effect="plain"
        class="move-dialog-target-visibility"
      >
        {{ visibilityLabel(targetVisibility) }}
      </el-tag>
    </div>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="onSubmit">移动到此</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Folder } from '@element-plus/icons-vue'
import FolderTree from './FolderTree.vue'
import { useFolderTree } from '@/composables/useFolderTree'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  currentFolderId: { type: [Number, null], default: null },  // 当前文件所在 folder (不能选自己)
  fileId: { type: Number, default: null }
})

const emit = defineEmits(['update:modelValue', 'move'])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

const {
  folderTree,
  expandedFolderIds,
  fetchTree,
  toggleExpanded
} = useFolderTree()

const selectedFolderId = ref(null)
const submitting = ref(false)

// 打开 dialog 时重新拉树 + 默认选中顶级
watch(visible, async (newVal) => {
  if (newVal) {
    await fetchTree()
    selectedFolderId.value = null
  }
})

// 找选中的文件夹对象
const targetFolderInfo = computed(() => {
  if (selectedFolderId.value === null) return '顶级目录 (我的网盘)'
  return findFolderName(folderTree.value, selectedFolderId.value)
})

const targetVisibility = computed(() => {
  if (selectedFolderId.value === null) return 'team'
  return findFolderVisibility(folderTree.value, selectedFolderId.value)
})

function findFolderName(nodes, targetId) {
  for (const n of nodes) {
    if (n.id === targetId) return n.name
    if (n.children?.length) {
      const found = findFolderName(n.children, targetId)
      if (found) return found
    }
  }
  return null
}

function findFolderVisibility(nodes, targetId) {
  for (const n of nodes) {
    if (n.id === targetId) return n.visibility
    if (n.children?.length) {
      const found = findFolderVisibility(n.children, targetId)
      if (found) return found
    }
  }
  return null
}

function visibilityTagType(v) {
  if (v === 'private') return 'danger'
  if (v === 'team') return 'success'
  if (v === 'public') return 'warning'
  return 'info'
}

function visibilityLabel(v) {
  if (v === 'private') return '🔒 私有'
  if (v === 'team') return '👥 团队'
  if (v === 'public') return '🌐 公开'
  return v
}

function onSubmit() {
  submitting.value = true
  emit('move', {
    fileId: props.fileId,
    targetFolderId: selectedFolderId.value
  })
}
</script>

<style scoped>
.move-dialog-hint {
  font-size: 12px;
  color: var(--color-text-secondary, #606266);
  margin-bottom: 12px;
}

.move-dialog-tree-wrapper {
  max-height: 360px;
  overflow-y: auto;
  border: 1px solid var(--color-border-lighter, #f0f0f0);
  border-radius: 4px;
  padding: 8px 0;
}

.move-dialog-root-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.15s;
}

.move-dialog-root-option:hover {
  background: var(--color-bg-hover, #f5f7fa);
}

.move-dialog-root-option.active {
  background: var(--color-primary-light-9, #ecf5ff);
  color: var(--color-primary, #409eff);
  font-weight: 500;
}

.move-dialog-target-info {
  margin-top: 12px;
  padding: 8px 12px;
  background: var(--color-bg-light, #f5f7fa);
  border-radius: 4px;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.move-dialog-target-visibility {
  margin-left: auto;
}
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
-->