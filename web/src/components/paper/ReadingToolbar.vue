<template>
  <div class="reading-toolbar" v-if="visible">
    <div class="reading-toolbar-inner">
      <div class="toolbar-left">
        <el-button-group size="small">
          <el-button
            :type="readingMode === 'original' ? 'primary' : 'default'"
            @click="setMode('original')"
          >原文</el-button>
          <el-button
            :type="readingMode === 'translation' ? 'primary' : 'default'"
            @click="setMode('translation')"
            :disabled="!hasTranslation"
          >翻译</el-button>
          <el-button
            :type="readingMode === 'bilingual' ? 'primary' : 'default'"
            @click="setMode('bilingual')"
            :disabled="!hasTranslation"
          >双语</el-button>
        </el-button-group>
      </div>

      <div class="toolbar-right">
        <el-button-group size="small">
          <el-button @click="decreaseFontSize" :icon="ZoomOut" title="缩小字号" />
          <span class="font-size-display">{{ fontSize }}px</span>
          <el-button @click="increaseFontSize" :icon="ZoomIn" title="放大字号" />
        </el-button-group>

        <el-button-group size="small">
          <el-button @click="decreaseLineHeight" :icon="Minus" title="紧凑行距" />
          <span class="line-height-display">{{ lineHeight.toFixed(2) }}</span>
          <el-button @click="increaseLineHeight" :icon="Plus" title="宽松行距" />
        </el-button-group>

        <el-button-group size="small">
          <!-- v27.2: 切换"正文内嵌图"显示 -->
          <el-button
            @click="showInlineFigures = !showInlineFigures"
            :icon="showInlineFigures ? Picture : Hide"
            :title="showInlineFigures ? '隐藏正文图片（用右侧图表栏）' : '显示正文图片'"
          />
          <!-- v28 step 6: 仅显示高置信度图（confidence >= 0.85） -->
          <el-button
            v-if="showInlineFigures"
            @click="showHighConfidenceOnly = !showHighConfidenceOnly"
            :icon="showHighConfidenceOnly ? Star : StarFilled"
            :title="`仅高置信度图 (≥0.85) · 当前最高 ${maxConfidencePct}% · ${showHighConfidenceOnly ? '开' : '关'}`"
          >
            <span v-if="showHighConfidenceOnly" class="confidence-badge">{{ maxConfidencePct }}%</span>
          </el-button>
          <el-button @click="toggleImages" :icon="visible ? Picture : Hide" :title="visible ? '显示图片' : '隐藏图片'" />
          <el-button @click="copyCitation" :icon="CopyDocument" title="复制引用" />
          <el-button @click="scrollToTop" :icon="Top" title="返回顶部" />
        </el-button-group>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * ReadingToolbar - 阅读器工具栏（阶段 2 功能）
 *
 * 当前为前端组件结构预留 + 本地状态管理。
 * 翻译功能（按钮 disabled）等待后端翻译接口接入。
 *
 * Props:
 *   paper - PaperDetail 对象
 * Emits:
 *   mode-change, font-size-change, line-height-change
 */
import { ref, computed, watch, onMounted } from 'vue'
import { ZoomIn, ZoomOut, Plus, Minus, Picture, Hide, CopyDocument, Top, Star, StarFilled } from '@element-plus/icons-vue'

const props = defineProps({
  paper: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['mode-change', 'font-size-change', 'line-height-change', 'toggle-inline-figures', 'toggle-high-confidence'])

const readingMode = ref('original')  // 'original' | 'translation' | 'bilingual'
const fontSize = ref(16)
const lineHeight = ref(1.85)
// v28: 默认显示正文内嵌图（图片自动嵌入 Fig. N 引用位置 — 像 PDF 阅读器）
const showInlineFigures = ref(localStorage.getItem('mnb:paper:showInlineFigures') !== 'false')
watch(showInlineFigures, (v) => {
  localStorage.setItem('mnb:paper:showInlineFigures', String(v))
  emit('toggle-inline-figures', v)
})
const visible = ref(true)  // 图片总开关
const hasTranslation = ref(false)  // 等待后端翻译 API 接入

// v28 step 6: 默认显示所有图（读者像 PDF 一样看到全部图，不预设阈值过滤）
const showHighConfidenceOnly = ref(localStorage.getItem('mnb:paper:showHighConfidenceOnly') !== 'false')
watch(showHighConfidenceOnly, (v) => {
  localStorage.setItem('mnb:paper:showHighConfidenceOnly', String(v))
  emit('toggle-high-confidence', v)
})

// v28 step 6: 计算当前 paper.figures 里的最高 confidence（显示在工具栏按钮上）
// confidence 字段来源：paperAdapter.js v28 step 4 → img.visionConfidence ?? ext.confidence ?? 0.5
const maxConfidencePct = computed(() => {
  const figs = props.paper?.figures || []
  if (!figs.length) return 0
  let max = 0
  for (const f of figs) {
    const c = f?.confidence ?? 0
    if (c > max) max = c
  }
  return Math.round(max * 100)
})

// 字号 / 行距档位
const FONT_SIZES = [14, 15, 16, 17, 18, 20]
const LINE_HEIGHTS = [1.5, 1.65, 1.85, 2.0, 2.2]

function setMode(mode) {
  if (!['original', 'translation', 'bilingual'].includes(mode)) return
  readingMode.value = mode
  emit('mode-change', mode)

  // 触发翻译/双语模式时：
  // L1: 优先调后端 API（POST /api/v1/papers/{id}/translate）
  // L2: 后端不可用时，用浏览器内置 Translator API（Chrome 129+）
  // L3: 都没有 → 显示"翻译功能开发中"
  if (mode === 'translation' || mode === 'bilingual') {
    if (props.paper?.id) {
      // 通知父组件（KnowledgeDetailView）触发后端翻译
      // 父组件会调 TranslationPanel 显示
      window.dispatchEvent(new CustomEvent('paper-translate-request', {
        detail: { paperId: props.paper.id, mode }
      }))
    }
    // 浏览器内置 Translator API 兜底（Chrome 129+ 支持）
    if ('Translator' in window) {
      console.log('[ReadingToolbar] 浏览器 Translator API 可用')
    } else {
      console.log('[ReadingToolbar] 浏览器 Translator API 不可用，等后端 API')
    }
  }
}

function increaseFontSize() {
  const idx = FONT_SIZES.indexOf(fontSize.value)
  if (idx < FONT_SIZES.length - 1) {
    fontSize.value = FONT_SIZES[idx + 1]
    emit('font-size-change', fontSize.value)
  }
}

function decreaseFontSize() {
  const idx = FONT_SIZES.indexOf(fontSize.value)
  if (idx > 0) {
    fontSize.value = FONT_SIZES[idx - 1]
    emit('font-size-change', fontSize.value)
  }
}

function increaseLineHeight() {
  const idx = LINE_HEIGHTS.indexOf(lineHeight.value)
  if (idx < LINE_HEIGHTS.length - 1) {
    lineHeight.value = LINE_HEIGHTS[idx + 1]
    emit('line-height-change', lineHeight.value)
  }
}

function decreaseLineHeight() {
  const idx = LINE_HEIGHTS.indexOf(lineHeight.value)
  if (idx > 0) {
    lineHeight.value = LINE_HEIGHTS[idx - 1]
    emit('line-height-change', lineHeight.value)
  }
}

function toggleImages() {
  visible.value = !visible.value
}

function copyCitation() {
  // TODO: 复制 APA / GB-T 7714 / BibTeX 格式引用
  if (navigator.clipboard && props.paper) {
    const cite = `${props.paper.title || ''} - ${(props.paper.raw?.source || 'Unknown')}`
    navigator.clipboard.writeText(cite).catch(() => {})
  }
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

// 暴露给父组件（KnowledgeDetailView）通过 ref 调
defineExpose({ readingMode, fontSize, lineHeight, visible })
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
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.font-size-display,
.line-height-display {
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  color: #6B7280;
  min-width: 44px;
  text-align: center;
}

/* v28 step 6: 工具栏 confidence 徽章 */
.confidence-badge {
  display: inline-flex;
  align-items: center;
  margin-left: 4px;
  font-size: 10px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, #10B981, #059669);
  padding: 0 6px;
  border-radius: 8px;
  line-height: 16px;
}
</style>
