<!--
  ContentBriefDetail.vue — W100 +25 双段折叠 (brief / detail 自动识别 \n\n)

  用户视角 P1-B 兜底方案：在 assistant 消息中显示双段折叠。
  不依赖 msg.brief / msg.detail 字段（那两个字段 deprecated），
  通过 msg.content 中 \n\n 分段实现。

  行为：
  - 1 段 = 完整显示（不折叠）
  - 2+ 段 = 第一段 brief + 后续 detail 折叠
  - 可点击展开 / 折叠
  - a11y: aria-expanded + aria-controls + role="button" + Enter/Space 键盘
  - 移动端 compact tap ≥ 44px
-->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { renderMarkdown } from '@/utils/markdown'

const props = withDefaults(
  defineProps<{
    /** 原始内容（已含 markdown + \n\n 分段） */
    content: string
    /** 移动端紧凑模式 */
    compact?: boolean
  }>(),
  { compact: false },
)

const expanded = ref(false)

/** 按 \n\n 拆段，空段剔除 */
const paragraphs = computed(() => {
  if (!props.content) return []
  return props.content
    .split(/\n\n+/)
    .map((p) => p.trim())
    .filter(Boolean)
})

const brief = computed(() => paragraphs.value[0] ?? '')
const detail = computed(() => paragraphs.value.slice(1).join('\n\n'))
const hasDetail = computed(() => paragraphs.value.length >= 2)

const detailId = computed(
  () => `cbd-detail-${Math.random().toString(36).slice(2, 10)}`,
)

function toggle() {
  expanded.value = !expanded.value
}
</script>

<template>
  <div
    v-if="brief"
    class="cbd-root"
    :class="{ 'cbd-compact': compact }"
    :data-testid="'content-brief-detail'"
    :data-paragraph-count="paragraphs.length"
    :data-expanded="expanded ? 'true' : 'false'"
  >
    <!-- brief: 第一段始终显示（1 段时不折叠） -->
    <div
      class="cbd-brief"
      :class="{ 'cbd-brief-only': !hasDetail }"
      :data-testid="'cbd-brief'"
      v-html="renderMarkdown(brief)"
    />

    <!-- detail 折叠按钮 + 展开内容 -->
    <template v-if="hasDetail">
      <button
        type="button"
        class="cbd-toggle"
        :aria-expanded="expanded ? 'true' : 'false'"
        :aria-controls="detailId"
        :aria-label="expanded ? '折叠详情' : `展开详情（${paragraphs.length - 1} 段）`"
        :data-testid="'cbd-toggle'"
        @click="toggle"
        @keydown.enter.prevent="toggle"
        @keydown.space.prevent="toggle"
      >
        <span class="cbd-toggle-icon" aria-hidden="true">{{ expanded ? '▾' : '▸' }}</span>
        <span class="cbd-toggle-text">
          {{ expanded ? '收起详情' : `展开更多（${paragraphs.length - 1} 段）` }}
        </span>
      </button>

      <Transition name="cbd-fade">
        <div
          v-if="expanded"
          :id="detailId"
          class="cbd-detail"
          :class="{ 'cbd-compact': compact }"
          :data-testid="'cbd-detail'"
          role="region"
          aria-label="完整回答"
        >
          <!-- 多段 detail 渲染（按段分隔） -->
          <template v-if="paragraphs.length > 2">
            <div
              v-for="(para, idx) in paragraphs.slice(1)"
              :key="idx"
              class="cbd-detail-para"
              :data-testid="`cbd-detail-para-${idx}`"
              v-html="renderMarkdown(para)"
            />
          </template>
          <!-- 2 段时 detail 直接渲染 -->
          <template v-else>
            <div
              class="cbd-detail-para"
              :data-testid="'cbd-detail-para-0'"
              v-html="renderMarkdown(detail)"
            />
          </template>
        </div>
      </Transition>
    </template>
  </div>
</template>

<style scoped>
.cbd-root {
  display: block;
}

.cbd-brief {
  display: block;
}

.cbd-brief-only {
  display: block;
}

.cbd-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  padding: 6px 10px;
  border: 1px solid var(--color-border, #e5e5e5);
  background: var(--color-bg-card, #f7f7f7);
  color: var(--color-primary, #ff7a5c);
  font-size: 13px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 150ms ease, border-color 150ms ease;
  min-height: 28px;
  user-select: none;
}

.cbd-toggle:hover {
  background: var(--color-bg-card-hover, #efefef);
  border-color: var(--color-primary, #ff7a5c);
}

.cbd-toggle:focus-visible {
  outline: 2px solid var(--color-primary, #ff7a5c);
  outline-offset: 2px;
}

.cbd-toggle-icon {
  font-size: 12px;
  line-height: 1;
}

.cbd-toggle-text {
  font-weight: 500;
}

.cbd-detail {
  margin-top: 8px;
  padding-top: 4px;
}

.cbd-detail-para {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--color-border, #e5e5e5);
}

.cbd-detail-para:first-child {
  margin-top: 0;
  padding-top: 4px;
  border-top: none;
}

.cbd-detail-para :deep(p) {
  margin: 0 0 8px;
}
.cbd-detail-para :deep(p:last-child) {
  margin-bottom: 0;
}

/* 移动端 compact tap ≥ 44px */
.cbd-compact .cbd-toggle {
  min-height: 44px;
  padding: 12px 14px;
  font-size: 14px;
}

.cbd-compact .cbd-detail-para {
  margin-top: 12px;
  padding-top: 12px;
}

/* 折叠动画 */
.cbd-fade-enter-active,
.cbd-fade-leave-active {
  transition: opacity 200ms ease, transform 200ms ease;
}
.cbd-fade-enter-from {
  opacity: 0;
  transform: translateY(-4px);
}
.cbd-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

@media (prefers-reduced-motion: reduce) {
  .cbd-fade-enter-active,
  .cbd-fade-leave-active {
    transition: none;
  }
}

/* dark mode */
[data-theme='dark'] .cbd-toggle {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.15);
}

[data-theme='dark'] .cbd-detail-para {
  border-top-color: rgba(255, 255, 255, 0.12);
}
</style>