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
    class="file-card drive-file-card"
    :class="[
      'file-card--' + viewMode,
      'drive-file-card-' + viewMode,
      { 'is-selected': selected, 'is-private': file.visibility === 'private' }
    ]"
    :data-type="fileTypeKey"
    @click="$emit('click', file, $event)"
    @contextmenu.prevent="$emit('contextmenu', file, $event)"
  >
    <!-- 多选 checkbox (修复: 仅 el-checkbox @change 触发, 外层只 .stop 防止冒泡到 card 导航) -->
    <div v-if="selectable" class="file-card-checkbox" @click.stop>
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

    <!--
      v2.1 (2026-07-09) Drive 美化: hover 操作栏 — 从 3 个无标签 circle 按钮
      改为 [icon+文本] 水平胶囊. 每个按钮直接显示文字 (下载/预览/更多),
      无需依赖 tooltip 才能辨识, 触摸用户也能看懂. 胶囊背景走白色 + 阴影,
      避免主色橙 (drive-upload-btn) 误读为"上传"CTA. 配色:
      下载 = 主色调 (最常用操作), 预览 = 信息蓝 (中性), 更多 = 默认灰.
    -->
    <div v-if="viewMode === 'grid'" class="file-card-actions">
      <button
        type="button"
        class="file-card-action file-card-action--download"
        :aria-label="`下载 ${file.title || file.file_name}`"
        @click.stop="handleDownload"
      >
        <el-icon :size="14"><Download /></el-icon>
        <span class="file-card-action-label">下载</span>
      </button>
      <button
        type="button"
        class="file-card-action file-card-action--preview"
        :aria-label="`预览 ${file.title || file.file_name}`"
        @click.stop="$emit('preview', file)"
      >
        <el-icon :size="14"><View /></el-icon>
        <span class="file-card-action-label">预览</span>
      </button>
      <el-dropdown trigger="click" @command="(cmd) => $emit(cmd, file)">
        <button
          type="button"
          class="file-card-action file-card-action--more"
          aria-label="更多操作"
          @click.stop
        >
          <el-icon :size="14"><MoreFilled /></el-icon>
          <span class="file-card-action-label">更多</span>
        </button>
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
            <el-dropdown-item v-if="file.storage_mode === 'drive'" command="version-history">
              🕘 版本历史
            </el-dropdown-item>
            <el-dropdown-item divided command="delete">
              <span style="color: var(--color-danger);">删除</span>
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
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

// === v2.0 (2026-07-09) Drive 美化: 按 file_type 提取 type key 用于 data-type ===
// 与 drive-view.css 中的 .drive-file-card[data-type="pdf|doc|ppt|excel|image|video|audio|text"] 配套
const EXTENSION_TYPE_MAP = {
  '.pdf': 'pdf',
  '.doc': 'doc', '.docx': 'doc',
  '.ppt': 'ppt', '.pptx': 'ppt',
  '.xls': 'excel', '.xlsx': 'excel',
  '.jpg': 'image', '.jpeg': 'image', '.png': 'image', '.gif': 'image',
  '.bmp': 'image', '.webp': 'image', '.svg': 'image',
  '.mp4': 'video', '.mov': 'video', '.avi': 'video', '.mkv': 'video', '.webm': 'video',
  '.mp3': 'audio', '.wav': 'audio', '.ogg': 'audio', '.flac': 'audio', '.m4a': 'audio',
  '.txt': 'text', '.md': 'text'
}

const fileTypeKey = computed(() => {
  const ext = (props.file.file_type || '').toLowerCase()
  return EXTENSION_TYPE_MAP[ext] || 'text'
})

// === 图标按 file_type 分类 ===
const iconComponent = computed(() => {
  const type = fileTypeKey.value
  if (type === 'pdf' || type === 'doc' || type === 'text') return Document
  if (type === 'ppt') return Tickets
  if (type === 'excel') return DataAnalysis
  if (type === 'image') return Picture
  if (type === 'video') return VideoCamera
  if (type === 'audio') return Headset
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
/*
 * v2.0 (2026-07-09) Drive 美化: 大部分视觉样式已迁移到 drive-view.css (.drive-file-card 等)
 * 本 scoped 块只保留 layout-flex 细节 (列表视图对齐 / 操作栏位置等)
 *
 * v2.0 已 token 化, 移除硬编码 EP 默认蓝色与色值 fallback
 */

.file-card {
  /* 颜色 / 边框 / 阴影 / hover lift 全部走 .drive-file-card (共享 CSS) */
  /* 本块只留 layout-flex 细节 */
  font-family: inherit;
}

/* 列表视图 layout (drive-file-card-list 在共享 CSS 内已有, 此处补充细节对齐) */
.file-card--list {
  flex-direction: row;
  gap: var(--space-3);
  min-height: auto;
  padding: var(--space-3);
  align-items: center;
}

.file-card--list .file-card-icon {
  flex-shrink: 0;
}

.file-card--list .file-card-name {
  flex: 1;
  text-align: left;
}

/* 列表视图右侧操作按钮组 */
.file-card-list-actions {
  display: flex;
  gap: var(--space-1);
  flex-shrink: 0;
  opacity: 1;
}

/* 操作按钮 hover 显示在 grid 视图 — 列表视图常驻可见 (保留原 UX) */
.file-card--list .file-card-actions {
  position: static;
  transform: none;
  opacity: 1;
  box-shadow: none;
  background: transparent;
}
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  本组件 PR3.7 统一审计时再加 dark 块
-->