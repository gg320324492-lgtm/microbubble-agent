<!--
  BatchActionToolbar.vue — 课题组网盘 v2 PR2 多选批量操作 toolbar

  功能:
  - Sticky 在 FileGrid 顶部 (选中文件后显示)
  - 显示已选数量 + 全选/取消
  - 6 个批量动作: 删除/移动/分享/下载/改可见性/收藏
  - 改可见性下拉弹 el-dropdown (team/public; 2026-09 单盘合并移除 private)
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
          <span class="batch-toolbar-label">已选 <span class="drive-batch-count">{{ selectedCount }}</span> 项<span v-if="sizeLabel"> · {{ sizeLabel }}</span></span>
        </el-checkbox>
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
          <!-- 批次⑥ 对齐视觉稿 dock: ZIP/移动到/收藏/删除, 次级动作收进 ⋯ -->
          <!-- 2026-09-05: "入库知识库"按钮移除 — 网盘文件已默认自动入库 RAG, 无需手动操作 -->
          <el-button class="drive-batch-toolbar-btn" :icon="Download" @click="$emit('batch-download')">下载 ZIP</el-button>
          <el-button class="drive-batch-toolbar-btn" :icon="Folder" @click="$emit('batch-move')">移动到</el-button>
          <el-button class="drive-batch-toolbar-btn" :icon="Star" @click="$emit('batch-toggle-star')">收藏</el-button>
          <el-button class="drive-batch-toolbar-btn drive-batch-toolbar-btn-danger" :icon="Delete" @click="$emit('batch-delete')">删除</el-button>
          <el-dropdown trigger="click" @command="onOverflowCmd">
            <el-button class="drive-batch-toolbar-btn drive-batch-toolbar-btn-more" :icon="MoreFilled" title="更多批量动作" />
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="share" :icon="Share">分享链接</el-dropdown-item>
                <el-dropdown-item command="vis-team" :icon="View">设为团队可见</el-dropdown-item>
                <el-dropdown-item command="vis-public" :icon="Share">设为公开</el-dropdown-item>
                <el-dropdown-item command="clear" divided :icon="Close">取消选择</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <span class="drive-batch-note">拖选中行到左栏夹=移动 · Shift 连选 · Ctrl A 全选</span>
        </template>
        <el-dropdown v-if="context === 'trash'" trigger="click" @command="(c) => c === 'clear' && $emit('clear')">
          <el-button class="drive-batch-toolbar-btn drive-batch-toolbar-btn-more" :icon="MoreFilled" title="更多" />
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="clear" :icon="Close">取消选择</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>
  </transition>
</template>

<script setup>
// v2.0 (2026-07-09) Drive 美化: 引入 drive-view.css 让 .drive-batch-toolbar 共享样式生效
import '@/views/drive/drive-view.css'
import { computed } from 'vue'
import {
  Delete, Download, Folder, Share, Star, View, ArrowDown, RefreshLeft, MoreFilled, Close
} from '@element-plus/icons-vue'

const props = defineProps({
  selectedCount: { type: Number, default: 0 },
  totalCount: { type: Number, default: 0 },
  context: { type: String, default: 'files' },  // 'files' | 'trash'
  /** 批次⑥ 视觉稿 dock "已选 N 项 · X MB": 父层传选中文件体积合计 (null/0 不显示) */
  selectedBytes: { type: [Number, null], default: null },
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
const sizeLabel = computed(() => {
  const b = props.selectedBytes || 0
  if (b <= 0) return ''
  return b >= 1048576 ? (b / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(b / 1024)) + ' KB'
})

function handleVisibilityCmd(cmd) {
  emit('batch-update-visibility', cmd)
}
function onOverflowCmd(cmd) {
  if (cmd === 'share') emit('batch-share')
  else if (cmd === 'vis-team') emit('batch-update-visibility', 'team')
  else if (cmd === 'vis-public') emit('batch-update-visibility', 'public')
  else if (cmd === 'clear') emit('clear')
}
</script>

<style scoped>
/*
 * v2.0 (2026-07-09) Drive 美化: 全部视觉走 drive-view.css .drive-batch-toolbar
 * 本 scoped 块保留 transition name & label flex 细节
 */
.batch-toolbar-label {
  color: var(--el-color-white);
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