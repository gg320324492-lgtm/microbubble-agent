<template>
  <div class="reading-toolbar" v-if="visible">
    <div class="reading-toolbar-inner">
      <!-- 字号 / 行距（真的有用） -->
      <el-button-group size="small">
        <el-button @click="decreaseFontSize" :icon="ZoomOut" title="缩小字号" />
        <span class="value-display">{{ fontSize }}px</span>
        <el-button @click="increaseFontSize" :icon="ZoomIn" title="放大字号" />
      </el-button-group>

      <el-button-group size="small">
        <el-button @click="decreaseLineHeight" :icon="Minus" title="紧凑行距" />
        <span class="value-display">{{ lineHeight.toFixed(2) }}</span>
        <el-button @click="increaseLineHeight" :icon="Plus" title="宽松行距" />
      </el-button-group>

      <!-- 章节跳转：回到顶部（实用） -->
      <el-button-group size="small">
        <el-button @click="scrollToTop" :icon="Top" title="返回顶部" />
      </el-button-group>
    </div>
  </div>
</template>

<script setup>
/**
 * ReadingToolbar v3 — 仅保留 3 个真正有用的功能组
 *
 * v28 step 15: 删除「内嵌图 / 高置信度图」切换按钮 —— 图片必须自动展示
 *    （用户原话：以后的论文有图片的都应该是自动展示的，而不是还得选择展示与否）
 *
 * 删除的"无用功能"：
 * - 原文/翻译/双语模式切换（后端翻译 API 还没接入）
 * - 图总开关（与内嵌图切换重复）
 * - 复制引用（功能未实现）
 * - 内嵌图 / 高置信度图切换（v28 step 15：图片永远展示）
 *
 * 保留的功能：
 * - 字号、行距调整（持久化到 localStorage）
 * - 回到顶部
 */
import { ref, watch } from 'vue'
import { ZoomIn, ZoomOut, Plus, Minus, Top } from '@element-plus/icons-vue'

const props = defineProps({
  paper: { type: Object, default: () => ({}) },
})

const emit = defineEmits([])  // v28 step 15: 不再 emit 任何事件

const visible = ref(true)
const fontSize = ref(Number(localStorage.getItem('mnb:paper:fontSize')) || 16)
const lineHeight = ref(Number(localStorage.getItem('mnb:paper:lineHeight')) || 1.85)

watch([fontSize, lineHeight], ([fs, lh]) => {
  localStorage.setItem('mnb:paper:fontSize', String(fs))
  localStorage.setItem('mnb:paper:lineHeight', String(lh))
  // 实时应用到 article
  const article = document.querySelector('.paper-article')
  if (article) {
    article.style.setProperty('--paper-font-size', `${fs}px`)
    article.style.setProperty('--paper-line-height', String(lh))
  }
})

// 字号 / 行距档位
const FONT_SIZES = [14, 15, 16, 17, 18, 20]
const LINE_HEIGHTS = [1.5, 1.65, 1.85, 2.0, 2.2]

function increaseFontSize() {
  const idx = FONT_SIZES.indexOf(fontSize.value)
  if (idx < FONT_SIZES.length - 1) fontSize.value = FONT_SIZES[idx + 1]
}
function decreaseFontSize() {
  const idx = FONT_SIZES.indexOf(fontSize.value)
  if (idx > 0) fontSize.value = FONT_SIZES[idx - 1]
}
function increaseLineHeight() {
  const idx = LINE_HEIGHTS.indexOf(lineHeight.value)
  if (idx < LINE_HEIGHTS.length - 1) lineHeight.value = LINE_HEIGHTS[idx + 1]
}
function decreaseLineHeight() {
  const idx = LINE_HEIGHTS.indexOf(lineHeight.value)
  if (idx > 0) lineHeight.value = LINE_HEIGHTS[idx - 1]
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

// 挂载时应用持久化值到 article
if (typeof window !== 'undefined') {
  // 在 nextTick 应用（等 article 渲染）
  setTimeout(() => {
    const article = document.querySelector('.paper-article')
    if (article) {
      article.style.setProperty('--paper-font-size', `${fontSize.value}px`)
      article.style.setProperty('--paper-line-height', String(lineHeight.value))
    }
  }, 100)
}
</script>

<style scoped>
.reading-toolbar {
  position: sticky;
  top: 64px;
  z-index: 50;
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(8px);
  border: 1px solid var(--color-border-light);
  border-radius: 12px;
  padding: 8px 16px;
  margin: 0 0 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.reading-toolbar-inner {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.value-display {
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  color: #6B7280;
  min-width: 50px;
  justify-content: center;
}

/* 应用字号/行距到正文（动态 CSS 变量） */
:deep(.paper-article .block-paragraph) {
  font-size: var(--paper-font-size, 16px);
  line-height: var(--paper-line-height, 1.85);
}
</style>