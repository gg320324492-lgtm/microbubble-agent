<script setup lang="ts">
import { computed } from 'vue'

export interface EditorSection {
  sectionType: string
  title: string
  content: string
}

const props = withDefaults(defineProps<{
  section?: EditorSection | null
  wordCount?: number
  ariaLabel?: string
}>(), {
  section: null,
  wordCount: 0,
  ariaLabel: '论文正文编辑区'
})

const displayContent = computed(() => {
  if (props.section && typeof props.section.content === 'string') {
    return props.section.content
  }
  return ''
})

const displayTitle = computed(() => {
  if (props.section && typeof props.section.title === 'string') {
    return props.section.title
  }
  return '未选择章节'
})

const sectionType = computed(() => props.section?.sectionType ?? '')

const isEmpty = computed(() => !props.section || !displayContent.value)
</script>

<template>
  <section class="scientific-editor-panel" :aria-label="ariaLabel">
    <header class="scientific-editor-panel__head">
      <h2 class="scientific-editor-panel__title">{{ displayTitle }}</h2>
      <span class="scientific-editor-panel__meta">
        <span class="scientific-editor-panel__type">{{ sectionType }}</span>
        <span class="scientific-editor-panel__count">{{ wordCount }} 字</span>
      </span>
    </header>

    <article v-if="!isEmpty" class="scientific-editor-panel__content" :aria-label="`章节 ${displayTitle} 正文`">
      <p v-for="(paragraph, idx) in displayContent.split(/\n+/).filter((p) => p.trim().length > 0)" :key="idx" class="scientific-editor-panel__paragraph">
        {{ paragraph }}
      </p>
    </article>

    <div v-else class="scientific-editor-panel__empty" role="status">暂无正文</div>
  </section>
</template>

<style scoped>
.scientific-editor-panel {
  min-width: 0;
  max-width: 720px;
  overflow-x: hidden;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
}
.scientific-editor-panel:focus-visible {
  outline: 2px solid var(--research-primary-500, #FF7A5C);
  outline-offset: 2px;
}
.scientific-editor-panel__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
}
.scientific-editor-panel__title {
  font-size: 18px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}
.scientific-editor-panel__meta {
  display: flex;
  align-items: center;
  gap: 12px;
}
.scientific-editor-panel__type {
  font-size: 11px;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.scientific-editor-panel__count {
  font-size: 12px;
  color: #475569;
}
.scientific-editor-panel__content {
  font-size: 14px;
  line-height: 1.75;
  color: #1e293b;
  font-family: 'Source Han Serif SC', 'Songti SC', serif;
  max-width: 640px;
}
.scientific-editor-panel__paragraph {
  margin: 0 0 14px;
  text-align: justify;
  word-break: break-word;
}
.scientific-editor-panel__empty {
  text-align: center;
  padding: 48px;
  color: #94a3b8;
  font-size: 13px;
}
@media (max-width: 1480px) {
  .scientific-editor-panel {
    padding: 16px;
  }
  .scientific-editor-panel__content {
    max-width: 100%;
  }
}
@media (min-width: 1720px) {
  .scientific-editor-panel {
    padding: 24px;
  }
  .scientific-editor-panel__content {
    max-width: 720px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .scientific-editor-panel,
  .scientific-editor-panel * {
    transition: none !important;
  }
}
</style>