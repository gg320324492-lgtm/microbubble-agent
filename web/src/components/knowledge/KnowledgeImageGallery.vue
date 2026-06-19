<template>
  <div class="knowledge-image-gallery">
    <!-- 状态条 -->
    <div v-if="loading" class="gallery-loading">
      <el-skeleton :rows="2" animated />
    </div>

    <div v-else-if="!images.length" class="gallery-empty">
      <el-empty :description="emptyText" :image-size="60" />
    </div>

    <div v-else>
      <!-- 状态徽章 -->
      <div class="gallery-status">
        <el-tag size="small" type="success" effect="light">
          <el-icon><CircleCheck /></el-icon> OCR 完成 {{ stats.done }}
        </el-tag>
        <el-tag v-if="stats.failed > 0" size="small" type="danger" effect="light">
          <el-icon><CircleClose /></el-icon> 失败 {{ stats.failed }}
        </el-tag>
        <el-tag v-if="stats.pending > 0" size="small" type="warning" effect="light">
          <el-icon><Loading /></el-icon> 处理中 {{ stats.pending }}
        </el-tag>
        <el-button v-if="showTrigger" size="small" type="primary" plain :loading="triggering" @click="handleTrigger">
          <el-icon><Refresh /></el-icon> 重新提取
        </el-button>
      </div>

      <!-- 图片网格 -->
      <div class="gallery-grid">
        <div
          v-for="img in images"
          :key="img.id"
          class="gallery-item"
          @click="openImage(img)"
        >
          <div class="gallery-item-img">
            <img :src="img.image_url" :alt="`第${img.page_number || '?'}页图${img.id}`" />
            <div v-if="img.page_number" class="gallery-item-page">P{{ img.page_number }}</div>
            <div v-if="img.ocr_status === 'failed'" class="gallery-item-badge gallery-item-badge-failed">
              <el-icon><CircleClose /></el-icon>
            </div>
            <div v-else-if="img.ocr_status === 'pending'" class="gallery-item-badge gallery-item-badge-pending">
              <el-icon><Loading /></el-icon>
            </div>
          </div>
          <div v-if="img.ocr_text" class="gallery-item-text">
            {{ truncate(img.ocr_text, 80) }}
          </div>
        </div>
      </div>
    </div>

    <!-- 图片预览 dialog -->
    <el-dialog
      v-model="previewVisible"
      width="80%"
      top="5vh"
      :show-close="true"
      :align-center="true"
      :title="previewTitle"
    >
      <div v-if="currentImage" class="preview-container">
        <div class="preview-image">
          <img :src="currentImage.image_url" :alt="`图片 ${currentImage.id}`" />
        </div>
        <div class="preview-meta">
          <div class="meta-row">
            <span class="meta-label">状态：</span>
            <el-tag :type="ocrStatusType(currentImage.ocr_status)" size="small">
              {{ ocrStatusLabel(currentImage.ocr_status) }}
            </el-tag>
            <span v-if="currentImage.ocr_model" class="meta-extra">模型：{{ currentImage.ocr_model }}</span>
          </div>
          <div v-if="currentImage.page_number" class="meta-row">
            <span class="meta-label">页码：</span>
            <span>第 {{ currentImage.page_number }} 页</span>
          </div>
          <div v-if="currentImage.width && currentImage.height" class="meta-row">
            <span class="meta-label">尺寸：</span>
            <span>{{ currentImage.width }} × {{ currentImage.height }}</span>
          </div>
          <div v-if="currentImage.file_size" class="meta-row">
            <span class="meta-label">大小：</span>
            <span>{{ formatSize(currentImage.file_size) }}</span>
          </div>
          <div v-if="currentImage.ocr_text" class="meta-ocr">
            <div class="meta-label">OCR 文本：</div>
            <pre class="ocr-text">{{ currentImage.ocr_text }}</pre>
          </div>
          <div v-else-if="currentImage.ocr_error" class="meta-ocr">
            <div class="meta-label">OCR 错误：</div>
            <pre class="ocr-error">{{ currentImage.ocr_error }}</pre>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { CircleCheck, CircleClose, Loading, Refresh } from '@element-plus/icons-vue'

const props = defineProps({
  knowledgeId: { type: Number, required: true },
  showTrigger: { type: Boolean, default: true },
  emptyText: { type: String, default: '该知识条目暂无提取图片' },
})

const images = ref([])
const loading = ref(false)
const triggering = ref(false)
const stats = computed(() => ({
  done: images.value.filter((i) => i.ocr_status === 'done').length,
  failed: images.value.filter((i) => i.ocr_status === 'failed').length,
  pending: images.value.filter((i) => i.ocr_status === 'pending' || i.ocr_status === 'skipped').length,
}))

const previewVisible = ref(false)
const currentImage = ref(null)
const previewTitle = computed(() => currentImage.value ? `图片详情 #${currentImage.value.id}` : '')

const fetchImages = async () => {
  loading.value = true
  try {
    const { data } = await axios.get(`/api/v1/knowledge/${props.knowledgeId}/images`)
    images.value = data.items || []
  } catch (e) {
    ElMessage.error('获取图片列表失败')
    images.value = []
  } finally {
    loading.value = false
  }
}

const handleTrigger = async () => {
  triggering.value = true
  try {
    const { data } = await axios.post(`/api/v1/knowledge/${props.knowledgeId}/extract-multimodal`)
    if (data.ok) {
      const msg = data.skipped
        ? `未提取（${data.reason}）`
        : `提取完成：${data.images_total} 张图片 / ${data.images_ocr_ok} 张 OCR 成功`
      ElMessage.success(msg)
      await fetchImages()
    } else {
      ElMessage.warning(data.error || data.reason || '提取失败')
    }
  } catch (e) {
    ElMessage.error('触发提取失败')
  } finally {
    triggering.value = false
  }
}

const openImage = (img) => {
  currentImage.value = img
  previewVisible.value = true
}

const ocrStatusType = (s) => ({ done: 'success', failed: 'danger', pending: 'warning', skipped: 'info' }[s] || 'info')
const ocrStatusLabel = (s) => ({ done: '完成', failed: '失败', pending: '处理中', skipped: '跳过' }[s] || s)

const truncate = (text, n) => {
  if (!text) return ''
  return text.length > n ? text.slice(0, n) + '…' : text
}

const formatSize = (bytes) => {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

watch(() => props.knowledgeId, () => fetchImages(), { immediate: true })
</script>

<style scoped>
.knowledge-image-gallery {
  width: 100%;
}

.gallery-loading {
  padding: var(--space-4);
}

.gallery-empty {
  padding: var(--space-4);
}

.gallery-status {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
  flex-wrap: wrap;
}

.gallery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: var(--space-3);
}

.gallery-item {
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--color-bg-card);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.gallery-item:hover {
  border-color: var(--color-primary);
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.gallery-item-img {
  position: relative;
  width: 100%;
  aspect-ratio: 1;
  background: var(--color-bg-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.gallery-item-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.gallery-item-page {
  position: absolute;
  top: 4px;
  left: 4px;
  background: rgba(0, 0, 0, 0.6);
  color: white;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 500;
}

.gallery-item-badge {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 14px;
}

.gallery-item-badge-failed {
  background: var(--color-danger, #f56c6c);
}

.gallery-item-badge-pending {
  background: var(--color-warning, #e6a23c);
}

.gallery-item-text {
  padding: var(--space-2);
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  background: var(--color-bg-card);
  min-height: 36px;
}

.preview-container {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: var(--space-4);
  max-height: 75vh;
  overflow: hidden;
}

@media (max-width: 768px) {
  .preview-container {
    grid-template-columns: 1fr;
  }
}

.preview-image {
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-secondary);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  overflow: hidden;
  max-height: 75vh;
}

.preview-image img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.preview-meta {
  overflow-y: auto;
  max-height: 75vh;
  padding-right: var(--space-2);
}

.meta-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
  font-size: var(--font-size-sm);
}

.meta-label {
  color: var(--color-text-secondary);
  font-weight: 500;
  min-width: 70px;
}

.meta-extra {
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
}

.meta-ocr {
  margin-top: var(--space-3);
}

.ocr-text,
.ocr-error {
  background: var(--color-bg-secondary);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  font-family: var(--font-family-mono, 'Courier New', monospace);
  font-size: var(--font-size-sm);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 300px;
  overflow-y: auto;
  margin-top: var(--space-2);
}

.ocr-error {
  color: var(--color-danger, #f56c6c);
  background: #fef0f0;
}
</style>
