<template>
  <figure class="figure-card" :class="{ 'figure-card-compact': compact }">
    <!-- 图片区域 -->
    <div class="figure-image-wrapper" @click="handlePreview">
      <img
        :src="figure.src || figure.imageUrl"
        :alt="`图片 ${figure.id}`"
        :loading="lazy ? 'lazy' : 'eager'"
        class="figure-image"
        @load="onImgLoad"
        @error="onImgError"
      />
      <div v-if="!loaded" class="figure-skeleton"></div>
      <div class="figure-zoom-hint">
        <el-icon><ZoomIn /></el-icon>
        <span>点击放大</span>
      </div>
    </div>

    <!-- 元信息条 -->
    <figcaption class="figure-caption">
      <div class="figure-caption-header">
        <span v-if="figureNo" class="figure-no">{{ figureNo }}</span>
        <span v-if="figure.page" class="figure-page">P{{ figure.page }}</span>
        <span v-if="figure.ocrStatus && figure.ocrStatus !== 'done'" class="figure-status" :class="`status-${figure.ocrStatus}`">
          {{ statusLabel(figure.ocrStatus) }}
        </span>
      </div>

      <!-- 图注文字（长支持展开） -->
      <div v-if="captionText" class="figure-caption-text" :class="{ 'is-collapsed': captionCollapsed && isLongCaption }">
        {{ captionText }}
      </div>
      <button v-if="isLongCaption" class="figure-caption-toggle" @click="captionCollapsed = !captionCollapsed">
        {{ captionCollapsed ? '展开 ▾' : '收起 ▴' }}
      </button>

      <!-- OCR 文本（默认折叠） -->
      <details v-if="figure.ocrText && figure.ocrText !== captionText" class="figure-ocr">
        <summary>OCR 文本</summary>
        <pre>{{ figure.ocrText }}</pre>
      </details>

      <!-- 无图注占位 -->
      <div v-if="!captionText && !figure.ocrText" class="figure-caption-empty">
        暂无图注
        <span v-if="figure.page">· 第 {{ figure.page }} 页</span>
      </div>
    </figcaption>

    <!-- 预览 dialog -->
    <el-dialog
      v-model="previewVisible"
      :title="`图片详情 #${figure.id}`"
      width="85%"
      top="5vh"
      align-center
    >
      <div class="preview-content">
        <div class="preview-image-wrap">
          <img :src="figure.src || figure.imageUrl" :alt="`图片 ${figure.id}`" class="preview-image" />
        </div>
        <div class="preview-info">
          <div class="preview-info-row" v-if="figure.page">
            <span class="preview-info-label">页码</span>
            <span>第 {{ figure.page }} 页</span>
          </div>
          <div class="preview-info-row" v-if="figure.width && figure.height">
            <span class="preview-info-label">尺寸</span>
            <span>{{ figure.width }} × {{ figure.height }}</span>
          </div>
          <div v-if="figure.ocrText" class="preview-ocr">
            <div class="preview-info-label">OCR 文本</div>
            <pre>{{ figure.ocrText }}</pre>
          </div>
        </div>
      </div>
    </el-dialog>
  </figure>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ZoomIn } from '@element-plus/icons-vue'

const props = defineProps({
  figure: { type: Object, required: true },
  figureNo: { type: String, default: '' },
  caption: { type: String, default: '' },
  compact: { type: Boolean, default: false },
  lazy: { type: Boolean, default: true },
})

const loaded = ref(false)
const previewVisible = ref(false)
const captionCollapsed = ref(true)

const captionText = computed(() => {
  return props.caption || props.figure.caption || ''
})

const isLongCaption = computed(() => captionText.value.length > 200)

const onImgLoad = () => { loaded.value = true }
const onImgError = (e) => {
  loaded.value = true
  e.target.style.opacity = '0.3'
}

const handlePreview = () => {
  previewVisible.value = true
}

const statusLabel = (s) => ({
  pending: '处理中',
  failed: '失败',
  skipped: '跳过',
}[s] || s)
</script>

<style scoped>
.figure-card {
  background: #fff;
  border: 1px solid var(--color-border-light);
  border-radius: 12px;
  overflow: hidden;
  margin: 0 0 20px;
  transition: box-shadow 0.2s, border-color 0.2s;
}

.figure-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
  border-color: rgba(255, 122, 92, 0.2);
}

.figure-image-wrapper {
  position: relative;
  background: #fafbfc;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  min-height: 200px;
  max-height: 620px;
  cursor: zoom-in;
  overflow: hidden;
}

.figure-image {
  max-width: 100%;
  max-height: 580px;
  object-fit: contain;
  border-radius: 4px;
  display: block;
}

.figure-skeleton {
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, #f3f4f6 25%, #e5e7eb 50%, #f3f4f6 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.figure-zoom-hint {
  position: absolute;
  bottom: 12px;
  right: 12px;
  background: rgba(31, 41, 55, 0.75);
  color: #fff;
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
  pointer-events: none;
}

.figure-card:hover .figure-zoom-hint {
  opacity: 1;
}

.figure-caption {
  padding: 14px 20px;
  border-top: 1px solid var(--color-border-light);
  background: #fff;
}

.figure-caption-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.figure-no {
  font-weight: 600;
  color: var(--color-primary);
  font-size: 14px;
  background: var(--color-primary-bg);
  padding: 2px 8px;
  border-radius: 4px;
}

.figure-page {
  font-size: 11px;
  color: #9CA3AF;
  background: #F3F4F6;
  padding: 2px 8px;
  border-radius: 8px;
}

.figure-status {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 8px;
}

.figure-status.status-failed {
  background: var(--color-danger-bg);
  color: var(--color-danger);
}

.figure-status.status-pending {
  background: var(--color-warning-bg);
  color: var(--color-warning);
}

.figure-caption-text {
  font-size: 14px;
  line-height: 1.7;
  color: #374151;
  word-break: break-word;
}

.figure-caption-text.is-collapsed {
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.figure-caption-toggle {
  margin-top: 6px;
  background: none;
  border: none;
  color: var(--color-primary);
  font-size: 12px;
  cursor: pointer;
  padding: 0;
}

.figure-caption-toggle:hover {
  text-decoration: underline;
}

.figure-caption-empty {
  font-size: 12px;
  color: #9CA3AF;
  font-style: italic;
}

.figure-ocr {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--color-border-light);
  font-size: 12px;
  color: #6B7280;
}

.figure-ocr summary {
  cursor: pointer;
  font-weight: 500;
  color: #4B5563;
  user-select: none;
}

.figure-ocr summary:hover {
  color: var(--color-primary);
}

.figure-ocr pre {
  margin: 8px 0 0;
  padding: 10px;
  background: #F9FAFB;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'SF Mono', Consolas, monospace;
  font-size: 12px;
  line-height: 1.6;
  max-height: 200px;
  overflow-y: auto;
}

/* 预览 */
.preview-content {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 20px;
  max-height: 75vh;
}

@media (max-width: 768px) {
  .preview-content {
    grid-template-columns: 1fr;
  }
}

.preview-image-wrap {
  background: #fafbfc;
  border-radius: 8px;
  padding: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  max-height: 75vh;
}

.preview-image {
  max-width: 100%;
  max-height: 70vh;
  object-fit: contain;
}

.preview-info {
  overflow-y: auto;
  max-height: 75vh;
  padding-right: 8px;
}

.preview-info-row {
  display: flex;
  gap: 10px;
  margin-bottom: 8px;
  font-size: 13px;
}

.preview-info-label {
  color: #6B7280;
  font-weight: 500;
  min-width: 60px;
}

.preview-ocr {
  margin-top: 12px;
}

.preview-ocr pre {
  background: #F9FAFB;
  padding: 12px;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.6;
  max-height: 300px;
  overflow-y: auto;
  margin: 6px 0 0;
  white-space: pre-wrap;
  word-break: break-word;
}

/* compact 模式 */
.figure-card-compact .figure-image-wrapper {
  padding: 12px;
  min-height: 120px;
  max-height: 240px;
}

.figure-card-compact .figure-image {
  max-height: 220px;
}
</style>
