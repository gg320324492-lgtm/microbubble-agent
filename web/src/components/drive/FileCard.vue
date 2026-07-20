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

    <!--
      v2.16 (2026-07-11) Drive 横向详情行 (类似 macOS Finder 列表视图)
      用户决策: 默认模式改为 detail, 取代 grid — 一行 56px 紧凑, 信息密度高
      169 文件全部可见不用翻页卡, 完整文件名 (单行省略), 大小/日期/owner/可见性/操作
      columns: 32px (checkbox) + 32px (star) + 32px (icon) + flex (name) + 80px (size) + 110px (date) + 80px (owner) + 100px (visibility) + 120px (actions)
    -->
    <template v-if="viewMode === 'detail'">
      <!-- 大小 -->
      <div class="file-row-col file-row-size" :title="formatSize(file.file_size)">
        {{ formatSize(file.file_size) }}
      </div>
      <!-- 上传日期 -->
      <div class="file-row-col file-row-date" :title="formatDate(file.created_at)">
        {{ formatDate(file.created_at) }}
      </div>
      <!-- 拥有者 -->
      <div class="file-row-col file-row-owner" :title="ownerName">
        {{ ownerName }}
      </div>
      <!-- 可见性 tag -->
      <div class="file-row-col file-row-visibility">
        <el-tag
          :type="visibilityTagType(file.visibility)"
          size="small"
          effect="plain"
          class="file-row-vis-tag"
        >
          {{ visibilityLabel(file.visibility) }}
        </el-tag>
      </div>
      <!-- 操作 -->
      <div class="file-row-col file-row-actions">
        <button
          type="button"
          class="file-row-action-btn"
          :aria-label="`预览 ${file.title || file.file_name}`"
          @click.stop="$emit('preview', file)"
        >
          <el-icon :size="16"><View /></el-icon>
        </button>
        <button
          type="button"
          class="file-row-action-btn"
          :aria-label="`下载 ${file.title || file.file_name}`"
          @click.stop="handleDownload"
        >
          <el-icon :size="16"><Download /></el-icon>
        </button>
        <el-dropdown trigger="click" @command="(cmd) => $emit(cmd, file)">
          <button
            type="button"
            class="file-row-action-btn"
            aria-label="更多操作"
            @click.stop
          >
            <el-icon :size="16"><MoreFilled /></el-icon>
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
    </template>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import {
  Document, Picture, VideoCamera, Headset, Download, View, MoreFilled,
  Tickets, DataAnalysis, Star, StarFilled,  // v2 PR2
  Files  // v77 P2.6-G.3: 未知类型 generic fallback 图标
} from '@element-plus/icons-vue'

const props = defineProps({
  file: { type: Object, required: true },
  selected: { type: Boolean, default: false },
  selectable: { type: Boolean, default: false },
  viewMode: { type: String, default: 'detail' }  // detail | grid | list (v2.16 detail 默认)
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

// v77 P2.6-G.3 缩略图常规化: 真文本 (.txt/.md) 用 Document, 其余未知扩展 (无扩展/.zip/.csv 等)
// 走 generic Files 图标, 避免未知类型伪装成文本文档. data-type 仍归 'text' 复用 file-default 色 token.
const KNOWN_TEXT_EXT = new Set(['.txt', '.md'])
const isGenericFile = computed(() => {
  const ext = (props.file.file_type || '').toLowerCase()
  return fileTypeKey.value === 'text' && !KNOWN_TEXT_EXT.has(ext)
})

// === 图标按 file_type 分类 ===
const iconComponent = computed(() => {
  const type = fileTypeKey.value
  if (type === 'pdf' || type === 'doc') return Document
  if (type === 'ppt') return Tickets
  if (type === 'excel') return DataAnalysis
  if (type === 'image') return Picture
  if (type === 'video') return VideoCamera
  if (type === 'audio') return Headset
  // text 组: 真文本 → Document; 未知扩展/无扩展 → generic Files (缩略图 fallback 常规化)
  if (isGenericFile.value) return Files
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

/**
 * 格式化上传日期 (v2.16 detail 模式)
 * 格式: YYYY-MM-DD HH:MM
 * 例: 2026-07-09 14:23
 */
function formatDate(iso) {
  if (!iso) return '-'
  // 兼容 ISO 字符串 / Date 对象 / postgres timestamp-without-tz
  const d = iso instanceof Date ? iso : new Date(iso)
  if (isNaN(d.getTime())) return '-'
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/**
 * detail 模式 owner 列显示
 * v2.16: 后端 list_drive_files 已 join member, 返 owner_name / owner_username
 * 兼容: 老 API 只给 created_by id 时显示 id 而非 name
 */
const ownerName = computed(() => {
  return (
    props.file.owner_name ||
    props.file.owner_username ||
    (props.file.created_by ? `#${props.file.created_by}` : '-')
  )
})

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

/*
 * v2.16 (2026-07-11) detail 模式 (横向表格行)
 * 单行布局: checkbox | star | icon | name | size | date | owner | visibility | actions
 * 默认模式, 取代 grid — 信息密度高, 169 文件全部可见
 *
 * 与 .drive-file-card-detail 共享样式 (drive-view.css) 提供完整列定义
 * 此处保留 grid 内部 alignment 细节
 */
.file-card--detail {
  display: grid;
  /* 列: checkbox(32) + star(32) + icon(36) + name(flex) + size(80) + date(110) + owner(80) + visibility(100) + actions(120) */
  grid-template-columns: 32px 32px 36px minmax(0, 1fr) 80px 110px 80px 100px 120px;
  gap: var(--space-3);
  align-items: center;
  min-height: 52px;
  padding: 0 var(--space-3);
  border-radius: var(--radius-md);
}

.file-card--detail::before {
  /* 左侧 4px 染色条 (与 grid 同) */
  width: 4px;
  height: auto;
  inset: 0 auto 0 0;
}

.file-card--detail .file-card-icon {
  margin-bottom: 0;
  width: 32px;
  height: 32px;
}

.file-card--detail .file-card-name {
  text-align: left;
  width: auto;
  margin: 0;
}

.file-card--detail .file-card-checkbox,
.file-card--detail .file-card-star {
  /* 隐藏原本卡片的绝对定位 - detail 模式下用网格列定位 */
  position: static;
  top: auto;
  left: auto;
}

.file-row-col {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-row-size {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.file-row-date {
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum";
}

.file-row-visibility {
  display: flex;
  align-items: center;
}

.file-row-vis-tag {
  font-size: var(--font-size-xs);
}

.file-row-actions {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  justify-content: flex-end;
  opacity: 0;
  transition: opacity var(--duration-fast) var(--ease-out);
}

.file-card--detail:hover .file-row-actions,
.file-card--detail.is-selected .file-row-actions {
  opacity: 1;
}

.file-row-action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  background: transparent;
  border: none;
  border-radius: var(--radius-md);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.file-row-action-btn:hover {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.file-row-action-btn:active {
  background: var(--color-primary-bg);
  color: var(--color-primary);
  transform: scale(0.92);
}

/* detail 模式下 checkbox + star 显示在 row 内 */
.file-card--detail .file-card-checkbox {
  display: flex;
  align-items: center;
  justify-content: center;
}

.file-card--detail .file-card-star {
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  本组件 PR3.7 统一审计时再加 dark 块
-->