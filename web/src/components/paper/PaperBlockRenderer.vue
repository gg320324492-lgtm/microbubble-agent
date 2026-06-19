<template>
  <div class="paper-block" :class="blockClasses">
    <!-- 页码标记 -->
    <div v-if="block.type === 'page_marker'" class="block-page-marker">
      <span class="page-line"></span>
      <span class="page-label">Page {{ block.content }}</span>
      <span class="page-line"></span>
    </div>

    <!-- 图表占位符 -->
    <div
      v-else-if="block.type === 'figure_marker'"
      :id="`figure-marker-${block.content}`"
      class="block-figure-marker"
    >
      <el-icon><Picture /></el-icon>
      <span class="figure-label">图 {{ block.content }}</span>
      <span v-if="block.page" class="figure-page">P{{ block.page }}</span>
    </div>

    <!-- 段落（含 auto-link） -->
    <p
      v-else-if="block.type === 'paragraph'"
      class="block-paragraph"
      :class="{ 'block-chinese': isChinese }"
      v-html="renderedContent"
    ></p>

    <!-- 标题（section 内部小标题） -->
    <h4 v-else-if="block.type === 'heading'" class="block-heading">
      {{ block.content }}
    </h4>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Picture } from '@element-plus/icons-vue'
import { autoLinkContent } from '@/utils/paperAdapter'
import { formatChemicalText } from '@/utils/chemFormat'

const props = defineProps({
  block: { type: Object, required: true },
  isChinese: { type: Boolean, default: false },
})

const blockClasses = computed(() => ({
  'block-page': props.block.type === 'page_marker',
  'block-figure-marker': props.block.type === 'figure_marker',
  'block-paragraph-wrapper': props.block.type === 'paragraph',
}))

const renderedContent = computed(() => {
  const raw = props.block.content || ''
  // 渲染管线（v26 回归修复）：
  //   raw (纯文本)
  //     → formatChemicalText (纯文本 + Unicode 上下标)
  //     → autoLinkContent (escape + DOI/URL/邮箱包 <a>)
  //     → v-html 渲染
  //
  // 注意：formatChemicalText 已改为返回纯文本（不再返回 <span class="chem-formula">），
  // 因此 autoLinkContent 的 _escapeHtml 不会再次转义化学式 → 不会泄漏 HTML 源码。
  const formatted = props.isChinese ? raw : formatChemicalText(raw)
  return autoLinkContent(formatted)
})
</script>

<style scoped>
.paper-block {
  margin: 0;
}

.block-paragraph {
  font-size: 15.5px;
  line-height: 1.85;
  color: #1F2937;
  margin: 0 0 14px;
  word-break: break-word;
  overflow-wrap: break-word;
  text-indent: 0;
}

.block-paragraph.block-chinese {
  line-height: 1.85;
  text-indent: 2em;
}

.block-paragraph :deep(.auto-link) {
  color: #2563EB;
  text-decoration: none;
  transition: color 0.15s;
}

.block-paragraph :deep(.auto-link:hover) {
  color: #1D4ED8;
  text-decoration: underline;
}

/* 化学式 / 离子 / 自由基样式（v26 回归修复：改为 Unicode 字符）
   formatChemicalText 现已返回纯 Unicode 上下标字符，不再输出 <span> 标签。
   浏览器原生渲染 O₃ / H₂O₂ / OH⁻ / mg·L⁻¹，无需特殊样式。
   如需视觉强调（如 ·OH 自由基），用 CSS 标记包裹：见下面 ::first-letter 等。 */

.block-heading {
  font-size: 16px;
  font-weight: 600;
  color: #1F2937;
  margin: 20px 0 10px;
}

.block-page-marker {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 28px 0 20px;
  user-select: none;
}

.page-line {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--color-border) 50%, transparent);
}

.page-label {
  font-size: 11px;
  color: #9CA3AF;
  background: #F3F4F6;
  padding: 2px 10px;
  border-radius: 10px;
  font-weight: 500;
  letter-spacing: 0.5px;
}

.block-figure-marker {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin: 18px 0 10px;
  padding: 4px 10px;
  background: var(--color-accent-bg);
  border: 1px dashed rgba(255, 179, 71, 0.4);
  border-radius: 6px;
  font-size: 12px;
  color: #B45309;
  font-weight: 500;
  scroll-margin-top: 80px;
}

.figure-label {
  font-weight: 600;
}

.figure-page {
  color: #9CA3AF;
  font-size: 11px;
  margin-left: 4px;
}
</style>
