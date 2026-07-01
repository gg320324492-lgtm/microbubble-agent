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
  <transition name="batch-toolbar-fade">
    <div v-if="selectedCount > 0" class="batch-toolbar">
      <div class="batch-toolbar-inner">
        <div class="batch-toolbar-left">
          <el-checkbox
            :model-value="allSelected"
            :indeterminate="indeterminate"
            @change="$emit('select-all')"
          >
            <span class="batch-toolbar-count">已选 {{ selectedCount }} 项</span>
          </el-checkbox>
          <el-button text size="small" @click="$emit('clear')">取消选择</el-button>
        </div>

        <div class="batch-toolbar-right">
          <template v-if="context === 'trash'">
            <el-button type="success" :icon="RefreshLeft" @click="$emit('batch-restore')">
              批量恢复
            </el-button>
            <el-button type="danger" :icon="Delete" @click="$emit('batch-permanent-delete')">
              彻底删除
            </el-button>
          </template>
          <template v-else>
            <el-button :icon="Folder" @click="$emit('batch-move')">
              移动
            </el-button>
            <el-dropdown @command="handleVisibilityCmd">
              <el-button :icon="View">
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
            <el-button :icon="Star" @click="$emit('batch-toggle-star')">
              收藏
            </el-button>
            <el-button :icon="Share" @click="$emit('batch-share')">分享</el-button>
            <el-button :icon="Download" @click="$emit('batch-download')">下载</el-button>
            <el-button type="danger" :icon="Delete" @click="$emit('batch-delete')">
              删除
            </el-button>
          </template>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
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
.batch-toolbar {
  position: sticky;
  top: 0;
  z-index: 100;
  background: var(--color-bg-card, #ffffff);
  border: 1px solid var(--color-primary-light-7, #fde2dc);
  border-radius: 6px;
  padding: 8px 12px;
  margin-bottom: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.batch-toolbar-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.batch-toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.batch-toolbar-count {
  font-weight: 600;
  color: var(--color-primary, #ff7a5c);
  margin-left: 8px;
}

.batch-toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.batch-toolbar-fade-enter-active,
.batch-toolbar-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.batch-toolbar-fade-enter-from,
.batch-toolbar-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  本组件已用 var(--color-*) token 跟随 6 主题, dark 块由 variables.css 全局接管
-->