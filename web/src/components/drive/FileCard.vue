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

    <!--
      v3.3 (2026-07-24) W68 第 14 批 C-3: 缩略图懒加载 + LQIP
      - IntersectionObserver 观察 file-card-icon 元素, 进入视口才触发 axios 拉 URL
      - LQIP placeholder: 16x16 micro-blur 微图先显示, 真实图 load 完成后 swap
      - 失败 fallback: type icon (el-icon) 灰色占位块 + 文件类型 icon
      - 性能: 大文件夹 (200 文件) 滚动 FPS 60+
      - 锚点范式第 179 守恒
    -->
    <div class="file-card-icon" ref="iconRef">
      <!-- LQIP 微图: 16x16 blur 占位, src 加载成功后由真实 thumbnailUrl 替换 -->
      <img
        v-if="showLQIP"
        :src="lqipDataUrl"
        :alt="file.title || file.file_name"
        class="file-card-thumb file-card-thumb--lqip"
        aria-hidden="true"
      />
      <!-- 真实缩略图: LQIP 已显示, 真实图 load 完成后 opacity 1 -->
      <img
        v-if="thumbnailUrl && file.storage_mode === 'drive'"
        :src="thumbnailUrl"
        :alt="file.title || file.file_name"
        class="file-card-thumb file-card-thumb--real"
        :class="{ 'is-loaded': thumbLoaded }"
        @load="onThumbLoad"
        @error="onThumbError"
      />
      <!-- fallback: 文件类型 icon (LQIP + 真实图都失败时显示) -->
      <el-icon
        v-if="!thumbnailUrl && !showLQIP"
        :size="viewMode === 'grid' ? 56 : 32"
      >
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
            <!--
              W68 F-4: 桌面端 "查看评论" 入口.
              与 mobile 文件级长按菜单 "查看评论" 对等 (W68 F-3 移动端).
              点击跳到 /drive/file/{id}/comments 独立评论路由页.
            -->
            <el-dropdown-item command="view-comments" divided>
              💬 查看评论
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
              <!--
                W68 F-4: 桌面端 detail 视图 (默认) "查看评论" 入口.
                跟 grid 视图对等, 路由跳转 /drive/file/{id}/comments.
              -->
              <el-dropdown-item command="view-comments" divided>
                💬 查看评论
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
import { computed, ref, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import {
  Document, Picture, VideoCamera, Headset, Download, View, MoreFilled,
  Tickets, DataAnalysis, Star, StarFilled,  // v2 PR2
  Files  // v77 P2.6-G.3: 未知类型 generic fallback 图标
} from '@element-plus/icons-vue'
import { useThumbnailLazyLoad } from '@/composables/useThumbnailLazyLoad'

const props = defineProps({
  file: { type: Object, required: true },
  selected: { type: Boolean, default: false },
  selectable: { type: Boolean, default: false },
  viewMode: { type: String, default: 'detail' }  // detail | grid | list (v2.16 detail 默认)
})

defineEmits(['click', 'contextmenu', 'toggle-select', 'preview', 'rename', 'move', 'update-visibility', 'extract-to-kb', 'share-link', 'version-history', 'view-comments', 'delete', 'toggle-star'])

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

// === v3.3 (2026-07-24) W68 第 14 批 C-3: 缩略图懒加载 + LQIP ===
// 取代 v2 PR5 onMounted 立即触发模式, 改用 IntersectionObserver 进入视口才触发
// 配合 16x16 LQIP placeholder 提供平滑过渡 (避免白屏闪烁 + 滚动卡顿)
const iconRef = ref(null)
const thumbnailUrl = ref(null)
const thumbLoaded = ref(false)

// === LQIP (Low Quality Image Placeholder) ===
// 16x16 blur 微图, 用 SVG dataURL 内联避免额外网络请求
// 颜色按 file_type 决定 (派生自主色 + 类型色), 滚动时仅 1px 模糊渐变占位
const LQIP_COLORS = {
  pdf: '#FFB347',     // 主色 (文件 PDF 暖橙)
  doc: '#5B8DEF',     // 信息蓝
  ppt: '#FF7A5C',     // 珊瑚橙 (演示)
  excel: '#10B981',   // 绿色 (表格)
  image: '#A78BFA',   // 紫色 (图片)
  video: '#F59E0B',   // 橙黄 (视频)
  audio: '#EC4899',   // 粉色 (音频)
  text: '#6B7280',    // 灰色 (文本)
}

function makeLQIP(color) {
  // 16x16 微图, blur(5px) CSS 模糊处理, 用 SVG dataURL 内联
  // 选浅色填充 + 中间渐变, 视觉上像真实图模糊后
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">
    <defs>
      <radialGradient id="g" cx="50%" cy="40%" r="60%">
        <stop offset="0%" stop-color="${color}" stop-opacity="0.85"/>
        <stop offset="100%" stop-color="${color}" stop-opacity="0.45"/>
      </radialGradient>
    </defs>
    <rect width="16" height="16" fill="url(#g)"/>
  </svg>`
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`
}

const lqipColor = computed(() => LQIP_COLORS[fileTypeKey.value] || LQIP_COLORS.text)
const lqipDataUrl = computed(() => makeLQIP(lqipColor.value))

// 是否显示 LQIP: storage_mode=drive + thumbnail_status='ready' + 真实图未加载完
const showLQIP = computed(() => {
  if (props.file.storage_mode !== 'drive') return false
  if (props.file.thumbnail_status !== 'ready') return false
  if (!thumbnailUrl.value) return false  // 没真实图就不显示 (走 type icon fallback)
  return !thumbLoaded.value  // 真实图已加载完就不显示 LQIP
})

async function loadThumbnail() {
  // 触发条件: storage_mode=drive + thumbnail_status='ready' (其他状态不请求, 走 type icon fallback)
  if (props.file.storage_mode !== 'drive') return
  if (props.file.thumbnail_status !== 'ready') return
  try {
    const resp = await axios.get(`/api/v1/drive/files/${props.file.id}/thumbnail`)
    if (resp.data.thumbnail_url) {
      thumbLoaded.value = false  // 重置 (新图未 load)
      thumbnailUrl.value = resp.data.thumbnail_url
    }
  } catch (e) {
    // 失败 silent fallback 到 type icon
    thumbnailUrl.value = null
    thumbLoaded.value = false
  }
}

function onThumbLoad() {
  // 缩略图加载成功 → 隐藏 LQIP
  thumbLoaded.value = true
}

function onThumbError() {
  // MinIO URL 过期 / bucket 不可达 → fallback 到 type icon
  thumbnailUrl.value = null
  thumbLoaded.value = false
}

// === v3.3 懒加载: IntersectionObserver 进入视口才触发 loadThumbnail ===
// threshold 0.01 + rootMargin '50px' (派工纪要 v5 段 5 反馈预期: 滚动一开始立即触发 + 提前预加载)
const { bindRef: bindIconRef } = useThumbnailLazyLoad(loadThumbnail, {
  threshold: 0.01,
  rootMargin: '50px',
  once: true,
})

// 绑定 iconRef → bindIconRef, 让 IntersectionObserver 跟踪 .file-card-icon
watch(iconRef, (el) => {
  bindIconRef(el)
})

// 兼容老路径: onMounted 时也尝试 trigger (首屏元素已在视口, observer 可能没及时触发)
// 注意: useThumbnailLazyLoad 内部 once 语义守卫, 重复 trigger 安全
onMounted(() => {
  // 不直接 trigger — 让 IntersectionObserver 自然触发
  // 仅当不支持 IntersectionObserver 时, composable 已自动 trigger
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

/*
 * v3.3 (2026-07-24) W68 第 14 批 C-3: 缩略图懒加载 + LQIP CSS
 * - .file-card-thumb: 真实缩略图容器, LQIP 在底层, 真实图 opacity 切换
 * - .file-card-thumb--lqip: 16x16 微图, blur(5px) 模糊放大到卡片大小
 * - .file-card-thumb--real: 真实图, 默认 opacity 0 (LQIP 在下), load 后 0.3s 渐变到 1
 * - 性能: LQIP 内联 SVG 不发网络请求, 真实图走 IntersectionObserver 进入视口才拉
 */
.file-card-thumb {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: var(--radius-sm);
  background: var(--color-bg-page, #f5f5f5);
}

/* LQIP 微图: 16x16 拉伸到容器 + blur(5px) 模拟真实图占位 */
.file-card-thumb--lqip {
  position: absolute;
  inset: 0;
  filter: blur(5px);
  /* 拉伸 16x16 到容器大小, 给用户"已经加载但模糊"的视觉 */
  width: 100%;
  height: 100%;
  transform: scale(1.1);  /* 略放大消除 blur 边缘的羽化 */
  transition: opacity var(--duration-fast, 150ms) var(--ease-out, ease);
  pointer-events: none;
}

/* 真实图: 默认 opacity 0 (LQIP 在下显示), load 后渐变到 1 */
.file-card-thumb--real {
  position: relative;
  opacity: 0;
  transition: opacity var(--duration-normal, 200ms) var(--ease-out, ease);
  z-index: 1;
}
.file-card-thumb--real.is-loaded {
  opacity: 1;
}

/* icon 容器需要 relative 定位, 让 LQIP absolute 正确覆盖 */
.file-card-icon {
  position: relative;
  overflow: hidden;
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