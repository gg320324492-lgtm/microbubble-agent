<!--
  FileCard.vue — 课题组网盘 PR3.3 单文件卡片
  2026-07-01

  卡片元素:
  - 大图标 (按 file_type 分类: PDF / Word / PPT / Excel / 图片 / 音频 / 视频 / 其他)
  - 文件名 (单行省略)
  - 大小 + 日期 + visibility 徽章
  - hover 显示操作栏 (下载/预览/重命名/移动/改可见性/删除)
  - 多选 checkbox (左上角)

  权限边界:
  - private 文件: 仅 owner 可见 (后端硬过滤, 前端不显示额外指示)
  - 当前用户对文件的所有权: 通过 file.created_by === currentUserId 判断

  数据:
  - props.file: Knowledge 单条记录
  - props.selected: 是否多选选中
  - props.selectable: 是否可多选
  - props.viewMode: 'grid' | 'list'
-->
<template>
  <div
    class="file-card"
    :class="['file-card--' + viewMode, { 'is-selected': selected, 'is-private': file.visibility === 'private' }]"
    @click="$emit('click', file)"
    @contextmenu.prevent="$emit('contextmenu', file, $event)"
  >
    <!-- 多选 checkbox -->
    <div v-if="selectable" class="file-card-checkbox" @click.stop="$emit('toggle-select', file.id)">
      <el-checkbox :model-value="selected" @change="$emit('toggle-select', file.id)" />
    </div>

    <!-- 大图标 -->
    <div class="file-card-icon">
      <el-icon :size="viewMode === 'grid' ? 56 : 32">
        <component :is="iconComponent" />
      </el-icon>
    </div>

    <!-- 文件名 -->
    <div class="file-card-name" :title="file.title || file.file_name">
      {{ file.title || file.file_name }}
    </div>

    <!-- 网格视图: 大小 + 日期 + 徽章 -->
    <div v-if="viewMode === 'grid'" class="file-card-meta">
      <span class="file-card-size">{{ formatSize(file.file_size) }}</span>
      <el-tag
        :type="visibilityTagType(file.visibility)"
        size="small"
        effect="plain"
        class="file-card-visibility"
      >
        {{ visibilityLabel(file.visibility) }}
      </el-tag>
    </div>

    <!-- hover 操作栏 (仅网格视图) -->
    <div v-if="viewMode === 'grid'" class="file-card-actions">
      <el-tooltip content="下载" placement="top">
        <el-button
          size="small"
          :icon="Download"
          circle
          @click.stop="handleDownload"
        />
      </el-tooltip>
      <el-tooltip content="预览" placement="top">
        <el-button
          size="small"
          :icon="View"
          circle
          @click.stop="$emit('preview', file)"
        />
      </el-tooltip>
      <el-tooltip content="更多" placement="top">
        <el-dropdown trigger="click" @command="(cmd) => $emit(cmd, file)">
          <el-button size="small" :icon="MoreFilled" circle @click.stop />
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="rename">重命名</el-dropdown-item>
              <el-dropdown-item command="move">移动</el-dropdown-item>
              <el-dropdown-item command="update-visibility">修改可见性</el-dropdown-item>
              <el-dropdown-item v-if="file.storage_mode === 'drive'" command="extract-to-kb">
                📚 加入公共知识库
              </el-dropdown-item>
              <el-dropdown-item v-if="file.storage_mode === 'drive'" command="share-link">
                🔗 生成分享链接
              </el-dropdown-item>
              <el-dropdown-item divided command="delete">
                <span style="color: var(--color-danger);">删除</span>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-tooltip>
    </div>

    <!-- 列表视图: 右侧操作栏 -->
    <div v-if="viewMode === 'list'" class="file-card-list-actions">
      <el-button size="small" :icon="Download" circle @click.stop="handleDownload" />
      <el-button size="small" :icon="View" circle @click.stop="$emit('preview', file)" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Document, Picture, VideoCamera, Headset, Download, View, MoreFilled,
  Tickets, DataAnalysis  // PPT/Excel 占位
} from '@element-plus/icons-vue'

const props = defineProps({
  file: { type: Object, required: true },
  selected: { type: Boolean, default: false },
  selectable: { type: Boolean, default: false },
  viewMode: { type: String, default: 'grid' }  // grid | list
})

defineEmits(['click', 'contextmenu', 'toggle-select', 'preview', 'rename', 'move', 'update-visibility', 'extract-to-kb', 'share-link', 'delete'])

// === 图标按 file_type 分类 ===
const iconComponent = computed(() => {
  const ext = (props.file.file_type || '').toLowerCase()
  if (['.pdf'].includes(ext)) return Document
  if (['.doc', '.docx'].includes(ext)) return Document
  if (['.ppt', '.pptx'].includes(ext)) return Tickets
  if (['.xls', '.xlsx'].includes(ext)) return DataAnalysis
  if (['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg'].includes(ext)) return Picture
  if (['.mp4', '.mov', '.avi', '.mkv', '.webm'].includes(ext)) return VideoCamera
  if (['.mp3', '.wav', '.ogg', '.flac', '.m4a'].includes(ext)) return Headset
  if (['.txt', '.md'].includes(ext)) return Document
  return Document
})

// === 工具函数 ===
function formatSize(bytes) {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
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

function handleDownload() {
  // 触发浏览器原生下载 (PR2.6 已实现 /api/v1/drive/files/{id}/download)
  const url = `/api/v1/drive/files/${props.file.id}/download?disposition=attachment`
  window.open(url, '_blank')
}
</script>

<style scoped>
.file-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 12px;
  border: 1px solid var(--color-border-light, #ebeef5);
  border-radius: 8px;
  background: var(--color-bg-card, #fff);
  cursor: pointer;
  transition: all 0.2s;
  min-height: 160px;
}

.file-card:hover {
  border-color: var(--color-primary, #409eff);
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.15);
  transform: translateY(-2px);
}

.file-card.is-selected {
  border-color: var(--color-primary, #409eff);
  background: var(--color-primary-light-9, #ecf5ff);
}

.file-card.is-private {
  border-left: 3px solid var(--color-danger, #f56c6c);
}

/* 列表视图 */
.file-card--list {
  flex-direction: row;
  gap: 12px;
  min-height: auto;
  padding: 10px 12px;
}

.file-card--list .file-card-icon {
  flex-shrink: 0;
}

.file-card--list .file-card-name {
  flex: 1;
  text-align: left;
}

/* checkbox */
.file-card-checkbox {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 1;
}

/* icon */
.file-card-icon {
  color: var(--color-primary, #409eff);
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.file-card.is-private .file-card-icon {
  color: var(--color-danger, #f56c6c);
}

/* name */
.file-card-name {
  width: 100%;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary, #303133);
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 8px;
}

/* meta */
.file-card-meta {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--color-text-secondary, #606266);
}

.file-card-size {
  font-weight: 500;
}

.file-card-visibility {
  margin-top: 2px;
}

/* actions (hover 显示) */
.file-card-actions {
  position: absolute;
  bottom: 8px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
  background: var(--color-bg-card, #fff);
  padding: 4px;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.file-card:hover .file-card-actions {
  opacity: 1;
}

.file-card-list-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  本组件 PR3.7 统一审计时再加 dark 块
-->