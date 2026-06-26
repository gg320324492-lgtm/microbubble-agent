<template>
  <figure class="figure-card" :class="{ 'figure-card-compact': compact }">
    <!-- 图片区域（v28 step 15: PDF 风格直视图，按容器宽度 100% 撑满） -->
    <div class="figure-image-wrapper" @click="handlePreview">
      <img
        :src="figure.src || figure.imageUrl"
        :alt="`图片 ${figureNo || figure.id}`"
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

    <!-- v28 step 20: figcaption 结构改为 "Fig. N + caption 标题" 一体化展示 -->
    <figcaption class="figure-caption">
      <!-- 第一行：Fig. N 标题 + caption 描述（标题化效果） -->
      <div v-if="figureNo" class="figure-caption-title">
        <span class="figure-no">{{ figureNo }}</span>
        <span v-if="captionText" class="figure-caption-text">.{{ captionText }}</span>
      </div>

      <!-- 状态（OCR 失败/pending）—— 不展示页码，PDF 阅读体验 -->
      <div v-if="figure.ocrStatus && figure.ocrStatus !== 'done'" class="figure-status-row">
        <span class="figure-status" :class="`status-${figure.ocrStatus}`">
          {{ statusLabel(figure.ocrStatus) }}
        </span>
      </div>

      <!-- 描述（vision model 自动识别）—— v28 step 19: 默认折叠，避免与原文 caption 混淆 -->
      <details v-if="descriptionText" class="figure-description">
        <summary>AI 自动识别描述</summary>
        <p>{{ descriptionText }}</p>
      </details>

      <!-- 图中文字（默认折叠） -->
      <details v-if="hasRecognizedText" class="figure-ocr">
        <summary>查看图中文字（OCR 识别）</summary>
        <pre>{{ figure.ocrText }}</pre>
      </details>

      <!-- 无图注占位 -->
      <div v-if="!captionText && !descriptionText && !figure.ocrText" class="figure-caption-empty">
        暂无图注
      </div>
    </figcaption>

    <!-- 预览 dialog（全屏放大） -->
    <el-dialog
      v-model="previewVisible"
      :title="figureNo || `图片 #${figure.id}`"
      width="92%"
      top="3vh"
      align-center
      :show-close="true"
      :modal="true"
      class="figure-preview-dialog"
    >
      <div class="preview-image-full">
        <img :src="figure.src || figure.imageUrl" :alt="`图片 ${figureNo || figure.id}`" class="preview-image" />
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
// v28 step 19: captionText 完整展示（不截断不折叠）
// descriptionText (vision model 识别) 默认折叠到 <details> 里

/**
 * v28 step 19: 原文 caption（来自 extractions.data.caption 或 figure.caption）
 * 优先 props.caption（PaperSectionRenderer 传 _captionText）
 * 否则 figure.caption
 *
 * v28 step 109.11: 去掉 caption 开头的 figure no 前缀
 *   vision OCR 经常输出 "Fig. 4. Fig. 4. Effects..." 这种重复
 *   既然 badge 已经显示 figureNo，caption 文本就不该再带前缀
 */
const captionText = computed(() => {
  const raw = props.caption || props.figure.caption || ''
  if (!raw) return ''
  const no = (props.figureNo || '').trim()
  if (!no) return raw
  // 匹配 "Fig. 4." / "Fig. 4 " / "Fig 4." / "Fig 4 " / "Fig.4." 等前缀
  // 也处理 vision OCR 重复: "Fig. 4.Fig. 4. Effects..." → "Effects..."
  const escNo = no.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  // 模式：前缀 + 可选第二个重复 + 实际标题
  const stripPatterns = [
    new RegExp(`^${escNo}\\.?\\s*`, 'i'),                    // "Fig. 4. Effects..." → "Effects..."
    new RegExp(`^${escNo}\\.?\\s*${escNo}\\.?\\s*`, 'i'),  // "Fig. 4.Fig. 4. Effects..." → "Effects..."
  ]
  let result = raw
  for (const pat of stripPatterns) {
    result = result.replace(pat, '')
  }
  return result
})

/**
 * v28 step 19: AI 识别描述（来自 extractions.data.description 或 vision model output）
 * 默认折叠，让用户主动点开看
 */
const descriptionText = computed(() => {
  return props.figure.description || props.figure.visualSummary || ''
})

/**
 * 是否显示"查看图中文字"折叠区
 *
 * 显示条件：
 * 1. figure.ocrText 存在
 * 2. 与 caption 不重复
 * 3. 长度 > 5（避免显示过短内容）
 * 4. 字母比例 > 30%（避免显示纯乱码/控制字符）
 */
const hasRecognizedText = computed(() => {
  const ocr = props.figure.ocrText
  if (!ocr || ocr === captionText.value) return false
  if (ocr.length < 5) return false
  // 字母字符（含中英文）占比 > 30%
  const letterCount = (ocr.match(/[\w一-鿿]/g) || []).length
  const letterRatio = letterCount / ocr.length
  return letterRatio > 0.3
})

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
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: 12px;
  overflow: hidden;
  margin: 0 0 20px;
  transition: box-shadow 0.2s, border-color 0.2s;
}

.figure-card:hover {
  box-shadow: var(--shadow-md);
  border-color: rgba(255, 122, 92, 0.2);
}

/* v28 step 15: PDF 风格直视图 —— 图片按容器宽度 100% 撑满，不限 max-height
   （之前 max-height: 620px 强制压缩长图，点 dialog 才能看全）
   现在 inline 模式下图片 1:1 渲染（保留 aspect-ratio），用户一眼看全 */
.figure-image-wrapper {
  position: relative;
  background: var(--color-bg-warm);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
  cursor: zoom-in;
  overflow: hidden;
}

.figure-image {
  width: 100%;
  height: auto;
  max-width: 100%;
  object-fit: contain;
  border-radius: 4px;
  display: block;
  background: var(--color-bg-card);
}

.figure-skeleton {
  position: absolute;
  inset: 8px;
  background: linear-gradient(90deg, #f3f4f6 25%, #e5e7eb 50%, #f3f4f6 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite;
  border-radius: 4px;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.figure-zoom-hint {
  position: absolute;
  top: 12px;
  right: 12px;
  background: rgba(31, 41, 55, 0.78);
  color: #fff;
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
  pointer-events: none;
  backdrop-filter: blur(2px);
}

.figure-card:hover .figure-zoom-hint {
  opacity: 1;
}

.figure-caption {
  padding: 12px 20px;
  border-top: 1px solid var(--color-border-light);
  background: var(--color-bg-card);
}

/* v28 step 20: figcaption 一体化标题（Fig. N + caption 标题） */
.figure-caption-title {
  font-size: 14px;
  line-height: 1.55;
  color: var(--color-text-primary);
  margin-bottom: 6px;
  word-break: break-word;
}

.figure-caption-title .figure-no {
  font-weight: 700;
  color: var(--color-primary);
  font-size: 14.5px;
  margin-right: 4px;
}

.figure-caption-title .figure-caption-text {
  color: var(--color-text-regular);
  font-weight: 400;
}

.figure-caption-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  flex-wrap: wrap;
}

.figure-no {
  font-weight: 600;
  color: var(--color-primary);
  font-size: 13px;
  background: var(--color-primary-bg);
  padding: 2px 8px;
  border-radius: 4px;
}

.figure-status-row {
  margin-bottom: 6px;
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
  font-size: 13.5px;
  line-height: 1.65;
  color: var(--color-text-regular);
  word-break: break-word;
}

.figure-caption-empty {
  font-size: 12px;
  color: var(--color-text-placeholder);
  font-style: italic;
}

/* v28 step 19: AI 自动识别描述 (默认折叠，避免与原文 caption 混淆) */
.figure-description {
  margin-top: 8px;
  padding: 8px 12px;
  background: #F9FAFB;
  border-radius: 6px;
  font-size: 12.5px;
  color: #4B5563;
}

.figure-description summary {
  cursor: pointer;
  font-weight: 500;
  color: var(--color-text-secondary);
  user-select: none;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 4px;
}

.figure-description summary::-webkit-details-marker {
  display: none;
}

.figure-description summary::before {
  content: '▸';
  font-size: 10px;
  transition: transform 0.15s;
}

.figure-description[open] summary::before {
  transform: rotate(90deg);
}

.figure-description summary:hover {
  color: var(--color-primary);
}

.figure-description p {
  margin: 6px 0 0;
  line-height: 1.6;
  word-break: break-word;
}

.figure-ocr {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--color-border-light);
  font-size: 12px;
  color: var(--color-text-secondary);
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
  margin: 6px 0 0;
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

/* v28 step 15: 全屏预览 dialog —— 92vw × 94vh，原图按 viewport 完整渲染 */
.preview-image-full {
  background: var(--color-bg-warm);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  max-height: 88vh;
  min-height: 60vh;
}

.preview-image {
  width: 100%;
  height: auto;
  max-height: 88vh;
  object-fit: contain;
  display: block;
}

/* compact 模式：内嵌图 — 仍 100% 撑满容器宽度，但 figure-card 周围 padding 减少 */
.figure-card-compact .figure-image-wrapper {
  padding: 6px;
}

.figure-card-compact .figure-caption {
  padding: 10px 16px;
}
</style>
