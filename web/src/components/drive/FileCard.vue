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
    @click="$emit('click', file, $event)"
    @contextmenu.prevent="$emit('contextmenu', file, $event)"
  >
    <!-- 多选 checkbox -->
    <div v-if="selectable" class="file-card-checkbox" @click.stop="$emit('toggle-select', file.id)">
      <el-checkbox :model-value="selected" @change="$emit('toggle-select', file.id)" />
    </div>

    <!-- v2 PR2: 收藏按钮 (右上角镜像 checkbox 位置, 始终可见) -->
    <div class="file-card-star" @click.stop="$emit('toggle-star', file)">
      <el-tooltip :content="file.is_starred ? '取消收藏' : '加入收藏'" placement="top">
        <el-icon :size="18" :class="{ 'is-starred': file.is_starred }">
          <component :is="file.is_starred ? StarFilled : Star" />
        </el-icon>
      </el-tooltip>
    </div>

    <!-- 大图标 / 缩略图 (PR5: thumbnail_status='ready' 时显示 <img>) -->
    <div class="file-card-icon">
      <img
        v-if="thumbnailUrl && file.storage_mode === 'drive'"
        :src="thumbnailUrl"
        :alt="file.title || file.file_name"
        class="file-card-thumb"
        @load="onThumbLoad"
        @error="onThumbError"
      />
      <el-icon v-else :size="viewMode === 'grid' ? 56 : 32">
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
              <el-dropdown-item command="toggle-star">
                {{ file.is_starred ? '⭐ 取消收藏' : '⭐ 加入收藏' }}
              </el-dropdown-item>
              <el-dropdown-item divided command="rename">重命名</el-dropdown-item>
              <el-dropdown-item command="move">移动</el-dropdown-item>
              <el-dropdown-item command="update-visibility">修改可见性</el-dropdown-item>
              <el-dropdown-item v-if="file.storage_mode === 'drive'" command="extract-to-kb">
                📚 加入公共知识库
              </el-dropdown-item>
              <el-dropdown-item v-if="file.storage_mode === 'drive'" command="share-link">
                🔗 生成分享链接
              </el-dropdown-item>
              <!-- v2 PR4: 版本历史 (仅 drive 文件, 当前版本始终 ≥1) -->
              <el-dropdown-item v-if="file.storage_mode === 'drive'" command="version-history">
                🕘 版本历史
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
import { computed, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import {
  Document, Picture, VideoCamera, Headset, Download, View, MoreFilled,
  Tickets, DataAnalysis, Star, StarFilled  // v2 PR2
} from '@element-plus/icons-vue'

const props = defineProps({
  file: { type: Object, required: true },
  selected: { type: Boolean, default: false },
  selectable: { type: Boolean, default: false },
  viewMode: { type: String, default: 'grid' }  // grid | list
})

defineEmits(['click', 'contextmenu', 'toggle-select', 'preview', 'rename', 'move', 'update-visibility', 'extract-to-kb', 'share-link', 'version-history', 'delete', 'toggle-star'])

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

// === v2 PR5: 缩略图 (优先用后端给的 thumbnail_url, 懒加载) ===
const thumbnailUrl = ref(null)

async function loadThumbnail() {
  // 触发条件: storage_mode=drive + thumbnail_status='ready' (其他状态不请求, 走 type icon fallback)
  if (props.file.storage_mode !== 'drive') return
  if (props.file.thumbnail_status !== 'ready') return
  try {
    const resp = await axios.get(`/api/v1/drive/files/${props.file.id}/thumbnail`)
    if (resp.data.thumbnail_url) {
      thumbnailUrl.value = resp.data.thumbnail_url
    }
  } catch (e) {
    // 失败 silent fallback 到 type icon
    thumbnailUrl.value = null
  }
}

function onThumbLoad() {
  // 缩略图加载成功 (留作埋点 hook)
}

function onThumbError() {
  // MinIO URL 过期 / bucket 不可达 → fallback 到 type icon
  thumbnailUrl.value = null
}

// PR5: onMounted 触发懒加载 (不要 watch props.file 避免滚动时反复请求)
onMounted(() => {
  loadThumbnail()
})
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

/* v2 PR2: 收藏按钮 (右上角镜像 checkbox) */
.file-card-star {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 1;
  cursor: pointer;
  padding: 2px;
  border-radius: 4px;
  transition: background 0.15s;
}
.file-card-star:hover {
  background: var(--color-bg-hover, #f5f7fa);
}
.file-card-star .el-icon {
  color: var(--color-text-placeholder, #909399);
  transition: color 0.15s;
}
.file-card-star .el-icon.is-starred {
  color: var(--color-warning, #e6a23c);  /* 收藏后金色 */
}

/* icon */
.file-card-icon {
  color: var(--color-primary, #409eff);
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* v2 PR5: 缩略图 (替代 type icon) */
.file-card-thumb {
  max-width: 80px;
  max-height: 80px;
  object-fit: contain;
  border-radius: 4px;
  background: var(--color-bg-light, #fafbfc);
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