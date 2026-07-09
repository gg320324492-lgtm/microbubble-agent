<!--
  BatchActionToolbar.vue — 课题组网盘 v2 PR2 多选批量操作 toolbar

  功能:
  - Sticky 在 FileGrid 顶部 (选中文件后显示)
  - 显示已选数量 + 全选/取消
  - 6 个批量动作: 删除/移动/分享/下载/改可见性/收藏
  - 改可见性下拉弹 el-dropdown (private/team/public)
  - dark mode: 末尾非 scoped <style> 块 (v60-v67 教训)

  Props:
  - selectedCount: 已选数量
  - totalCount: 当前页总数
  - context: 'files' | 'trash' (trash 模式只显示恢复/删除)

  Events:
  - @select-all, @clear
  - @batch-delete, @batch-move, @batch-share, @batch-download
  - @batch-update-visibility(visibility)
  - @batch-restore (trash only)
  - @batch-permanent-delete (trash only)
-->
<template>
  <!-- v2.0 (2026-07-09) Drive 美化: .drive-batch-toolbar 走共享 CSS (橙渐变 + 数字徽章 + 按钮玻璃) -->
  <transition name="drive-batch-toolbar-fade">
    <div v-if="selectedCount > 0" class="drive-batch-toolbar">
      <div class="drive-batch-toolbar-left">
        <el-checkbox
          :model-value="allSelected"
          :indeterminate="indeterminate"
          @change="$emit('select-all')"
        >
          <span class="batch-toolbar-label">已选 <span class="drive-batch-count">{{ selectedCount }}</span> 项</span>
        </el-checkbox>
        <el-button class="drive-batch-toolbar-btn" size="small" @click="$emit('clear')">取消选择</el-button>
      </div>

      <div class="drive-batch-toolbar-right">
        <template v-if="context === 'trash'">
          <el-button class="drive-batch-toolbar-btn" :icon="RefreshLeft" @click="$emit('batch-restore')">
            批量恢复
          </el-button>
          <el-button class="drive-batch-toolbar-btn drive-batch-toolbar-btn-danger" :icon="Delete" @click="$emit('batch-permanent-delete')">
            彻底删除
          </el-button>
        </template>
        <template v-else>
          <el-button class="drive-batch-toolbar-btn" :icon="Folder" @click="$emit('batch-move')">
            移动
          </el-button>
          <el-dropdown @command="handleVisibilityCmd" trigger="click">
            <el-button class="drive-batch-toolbar-btn" :icon="View">
              可见性
              <el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="private">🔒 仅自己</el-dropdown-item>
                <el-dropdown-item command="team">👥 团队成员</el-dropdown-item>
                <el-dropdown-item command="public">🌐 公开</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button class="drive-batch-toolbar-btn" :icon="Star" @click="$emit('batch-toggle-star')">
            收藏
          </el-button>
          <el-button class="drive-batch-toolbar-btn" :icon="Share" @click="$emit('batch-share')">分享</el-button>
          <el-button class="drive-batch-toolbar-btn" :icon="Download" @click="$emit('batch-download')">下载</el-button>
          <el-button class="drive-batch-toolbar-btn drive-batch-toolbar-btn-danger" :icon="Delete" @click="$emit('batch-delete')">
            删除
          </el-button>
        </template>
      </div>
    </div>
  </transition>
</template>

<script setup>
// v2.0 (2026-07-09) Drive 美化: 引入 drive-view.css 让 .drive-batch-toolbar 共享样式生效
import '@/views/drive/drive-view.css'
import { computed } from 'vue'
import {
  Delete, Download, Folder, Share, Star, View, ArrowDown, RefreshLeft
} from '@element-plus/icons-vue'

const props = defineProps({
  selectedCount: { type: Number, default: 0 },
  totalCount: { type: Number, default: 0 },
  context: { type: String, default: 'files' }  // 'files' | 'trash'
})

const emit = defineEmits([
  'select-all', 'clear',
  'batch-delete', 'batch-move', 'batch-share', 'batch-download',
  'batch-update-visibility', 'batch-toggle-star',
  'batch-restore', 'batch-permanent-delete'
])

const allSelected = computed(() =>
  props.selectedCount > 0 && props.selectedCount === props.totalCount
)
const indeterminate = computed(() =>
  props.selectedCount > 0 && props.selectedCount < props.totalCount
)

function handleVisibilityCmd(cmd) {
  emit('batch-update-visibility', cmd)
}
</script>

<style scoped>
/*
 * v2.0 (2026-07-09) Drive 美化: 全部视觉走 drive-view.css .drive-batch-toolbar
 * 本 scoped 块保留 transition name & label flex 细节
 */
.batch-toolbar-label {
  color: #fff;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  margin-left: var(--space-2);
}

.drive-batch-toolbar-fade-enter-active,
.drive-batch-toolbar-fade-leave-active {
  transition: opacity var(--duration-normal) var(--ease-out),
              transform var(--duration-normal) var(--ease-out);
}
.drive-batch-toolbar-fade-enter-from,
.drive-batch-toolbar-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  本组件已用 var(--color-*) token 跟随 6 主题, dark 块由 variables.css 全局接管
-->