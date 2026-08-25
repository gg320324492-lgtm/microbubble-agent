<script setup lang="ts">
import { computed } from 'vue'

export interface OutlineSection {
  sectionType: string
  title: string
  status?: 'pending' | 'drafting' | 'review' | 'complete'
  wordCount?: number
}

const props = withDefaults(defineProps<{
  sections?: OutlineSection[]
  activeSection?: string
  ariaLabel?: string
}>(), {
  sections: () => [],
  activeSection: '',
  ariaLabel: '章节结构大纲'
})

const sectionItems = computed(() => props.sections ?? [])

const statusLabel = computed(() => ({
  pending: '待撰写',
  drafting: '撰写中',
  review: '审稿中',
  complete: '已完成'
}))

const statusColor = computed(() => ({
  pending: '#94a3b8',
  drafting: '#FF7A5C',
  review: '#f59e0b',
  complete: '#10b981'
}))

function statusFor(section: OutlineSection): 'pending' | 'drafting' | 'review' | 'complete' {
  return section.status ?? 'pending'
}

function isActive(section: OutlineSection): boolean {
  return props.activeSection === section.sectionType
}
</script>

<template>
  <section class="manuscript-outline-panel" :aria-label="ariaLabel">
    <header class="manuscript-outline-panel__head">
      <h2 class="manuscript-outline-panel__title">章节结构</h2>
      <span class="manuscript-outline-panel__count">{{ sectionItems.length }} 节</span>
    </header>

    <ul v-if="sectionItems.length > 0" class="manuscript-outline-panel__list">
      <li
        v-for="section in sectionItems"
        :key="section.sectionType"
        class="manuscript-outline-panel__item"
        :data-active="isActive(section) ? 'true' : 'false'"
        :data-status="statusFor(section)"
      >
        <button
          type="button"
          class="manuscript-outline-panel__button"
          :aria-current="isActive(section) ? 'true' : 'false'"
          :aria-label="`打开章节 ${section.title}`"
        >
          <span class="manuscript-outline-panel__title-text">{{ section.title }}</span>
          <span
            class="manuscript-outline-panel__status"
            :style="{ background: statusColor[statusFor(section)] }"
          >{{ statusLabel[statusFor(section)] }}</span>
          <span v-if="section.wordCount !== undefined" class="manuscript-outline-panel__count-text">
            {{ section.wordCount }} 字
          </span>
        </button>
      </li>
    </ul>

    <div v-else class="manuscript-outline-panel__empty" role="status">暂无章节</div>
  </section>
</template>

<style scoped>
.manuscript-outline-panel {
  min-width: 0;
  overflow-x: hidden;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  padding: 16px;
}
.manuscript-outline-panel:focus-visible {
  outline: 2px solid var(--research-primary-500, #FF7A5C);
  outline-offset: 2px;
}
.manuscript-outline-panel__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12px;
}
.manuscript-outline-panel__title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}
.manuscript-outline-panel__count {
  font-size: 12px;
  color: #94a3b8;
}
.manuscript-outline-panel__list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.manuscript-outline-panel__item {
  display: block;
}
.manuscript-outline-panel__button {
  width: 100%;
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid transparent;
  background: rgba(15, 23, 42, 0.02);
  cursor: pointer;
  font: inherit;
}
.manuscript-outline-panel__item[data-active='true'] .manuscript-outline-panel__button {
  background: rgba(255, 122, 92, 0.08);
  border-color: var(--research-primary-500, #FF7A5C);
}
.manuscript-outline-panel__button:focus-visible {
  outline: 2px solid var(--research-primary-500, #FF7A5C);
  outline-offset: 2px;
}
.manuscript-outline-panel__title-text {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}
.manuscript-outline-panel__status {
  align-self: flex-start;
  font-size: 11px;
  color: white;
  padding: 1px 6px;
  border-radius: 999px;
}
.manuscript-outline-panel__count-text {
  font-size: 11px;
  color: #94a3b8;
}
.manuscript-outline-panel__empty {
  text-align: center;
  padding: 24px;
  color: #94a3b8;
  font-size: 13px;
}
@media (max-width: 1480px) {
  .manuscript-outline-panel {
    padding: 12px;
  }
}
@media (min-width: 1720px) {
  .manuscript-outline-panel {
    padding: 20px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .manuscript-outline-panel,
  .manuscript-outline-panel * {
    transition: none !important;
  }
}
</style>