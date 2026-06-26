<template>
  <aside class="right-image-rail" :class="{ 'is-empty': figures.length === 0 }">
    <div class="rail-header">
      <el-icon><Picture /></el-icon>
      <span class="rail-title">本节图表</span>
      <span v-if="figures.length" class="rail-count">{{ figures.length }}</span>
    </div>

    <div v-if="figures.length === 0" class="rail-empty">
      <el-icon class="empty-icon"><Picture /></el-icon>
      <span class="empty-text">本节暂无匹配图表</span>
    </div>

    <div v-else class="rail-list">
      <figure
        v-for="fig in figures"
        :key="fig.id"
        class="rail-item"
        @click="handleClick(fig)"
      >
        <div class="rail-thumb">
          <img
            :src="fig.src || fig.imageUrl"
            :alt="`图 ${fig.figureNo || fig.id}`"
            loading="lazy"
          />
          <div class="rail-overlay">
            <el-icon><ZoomIn /></el-icon>
          </div>
        </div>
        <div class="rail-meta">
          <div class="rail-meta-top">
            <span v-if="fig.figureNo" class="rail-fig-no">{{ fig.figureNo }}</span>
            <span v-if="fig.page" class="rail-page">P{{ fig.page }}</span>
          </div>
          <div v-if="fig.semanticTitle || fig.caption" class="rail-caption">
            {{ truncate(fig.semanticTitle || fig.caption, 50) }}
          </div>
        </div>
      </figure>
    </div>

    <!-- 预览 dialog -->
    <el-dialog
      v-model="previewVisible"
      :title="previewFigure ? `图片详情 #${previewFigure.id}` : '图片详情'"
      width="80%"
      top="5vh"
      align-center
    >
      <div v-if="previewFigure" class="rail-preview">
        <img :src="previewFigure.src || previewFigure.imageUrl" :alt="`图片 ${previewFigure.id}`" />
        <div v-if="previewFigure.caption || previewFigure.semanticTitle" class="rail-preview-caption">
          {{ previewFigure.semanticTitle || previewFigure.caption }}
        </div>
      </div>
    </el-dialog>
  </aside>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Picture, ZoomIn } from '@element-plus/icons-vue'

const props = defineProps({
  /**
   * 当前 section 的图片列表
   * 父组件按 sectionId 过滤好后传入
   */
  figures: { type: Array, default: () => [] },
  /**
   * 当前激活的 section id（用于高亮等）
   */
  activeSectionId: { type: String, default: '' },
})

const previewVisible = ref(false)
const previewFigure = ref(null)

function truncate(s, n) {
  if (!s) return ''
  return s.length > n ? s.slice(0, n) + '...' : s
}

function handleClick(fig) {
  previewFigure.value = fig
  previewVisible.value = true
}
</script>

<style scoped>
.right-image-rail {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: 12px;
  padding: 12px 14px;
  box-shadow: var(--shadow-md);
  position: sticky;
  top: 88px;
  max-height: calc(100vh - 110px);
  overflow-y: auto;
}

.rail-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--color-border-light);
}

.rail-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary, #1F2937);
  flex: 1;
}

.rail-count {
  font-size: 11px;
  font-weight: 500;
  color: var(--color-primary, #FF7A5C);
  background: var(--color-primary-bg, rgba(255, 122, 92, 0.1));
  padding: 1px 6px;
  border-radius: 8px;
}

.rail-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 20px 8px;
  color: var(--color-text-placeholder);
  font-size: 12px;
}

.empty-icon {
  font-size: 24px;
  opacity: 0.5;
}

.rail-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.rail-item {
  background: #FAFAFA;
  border: 1px solid var(--color-border-light);
  border-radius: 8px;
  overflow: hidden;
  cursor: zoom-in;
  transition: border-color 0.15s, transform 0.15s;
}

.rail-item:hover {
  border-color: var(--color-primary, #FF7A5C);
  transform: translateY(-1px);
}

.rail-thumb {
  position: relative;
  background: var(--color-bg-card);
  padding: 8px;
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.rail-thumb img {
  max-width: 100%;
  max-height: 84px;
  object-fit: contain;
}

.rail-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 18px;
  opacity: 0;
  transition: opacity 0.15s;
}

.rail-item:hover .rail-overlay {
  opacity: 1;
}

.rail-meta {
  padding: 8px 10px;
  background: var(--color-bg-card);
  border-top: 1px solid var(--color-border-light);
}

.rail-meta-top {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.rail-fig-no {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-primary, #FF7A5C);
  background: var(--color-primary-bg, rgba(255, 122, 92, 0.1));
  padding: 1px 6px;
  border-radius: 4px;
}

.rail-page {
  font-size: 10px;
  color: var(--color-text-placeholder);
  background: #F3F4F6;
  padding: 1px 5px;
  border-radius: 6px;
}

.rail-caption {
  font-size: 11px;
  line-height: 1.5;
  color: var(--color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.rail-preview {
  text-align: center;
}

.rail-preview img {
  max-width: 100%;
  max-height: 70vh;
  object-fit: contain;
}

.rail-preview-caption {
  margin-top: 12px;
  padding: 12px;
  background: #F9FAFB;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-text-regular);
  text-align: left;
}
</style>
