<script setup lang="ts">
import { computed } from 'vue'

export interface ReviewerIssue {
  type: string
  location: string
  description: string
  severity: 'low' | 'medium' | 'high'
  suggestion: string
}

const props = withDefaults(defineProps<{
  issues?: ReviewerIssue[]
  ariaLabel?: string
}>(), {
  issues: () => [],
  ariaLabel: 'Reviewer 智能体审稿意见'
})

const issueItems = computed(() => props.issues ?? [])

const severityColor = computed(() => ({
  high: '#ef4444',
  medium: '#f59e0b',
  low: '#3b82f6'
}))

const severityLabel = computed(() => ({
  high: '严重',
  medium: '中',
  low: '轻'
}))

const highCount = computed(() => issueItems.value.filter((i) => i.severity === 'high').length)
const mediumCount = computed(() => issueItems.value.filter((i) => i.severity === 'medium').length)
const lowCount = computed(() => issueItems.value.filter((i) => i.severity === 'low').length)
</script>

<template>
  <section class="reviewer-insight-panel" :aria-label="ariaLabel">
    <header class="reviewer-insight-panel__head">
      <h2 class="reviewer-insight-panel__title">Reviewer 审稿意见</h2>
      <span class="reviewer-insight-panel__count">{{ issueItems.length }} 条</span>
    </header>

    <div v-if="issueItems.length > 0" class="reviewer-insight-panel__summary" aria-hidden="true">
      <span class="reviewer-insight-panel__chip" data-severity="high">严重 {{ highCount }}</span>
      <span class="reviewer-insight-panel__chip" data-severity="medium">中 {{ mediumCount }}</span>
      <span class="reviewer-insight-panel__chip" data-severity="low">轻 {{ lowCount }}</span>
    </div>

    <ul v-if="issueItems.length > 0" class="reviewer-insight-panel__list">
      <li
        v-for="(issue, idx) in issueItems"
        :key="`${issue.location}-${idx}`"
        class="reviewer-insight-panel__item"
        :data-severity="issue.severity"
      >
        <div class="reviewer-insight-panel__head-row">
          <span
            class="reviewer-insight-panel__severity"
            :data-severity="issue.severity"
            :style="{ background: severityColor[issue.severity] }"
          >{{ severityLabel[issue.severity] }}</span>
          <span class="reviewer-insight-panel__type">{{ issue.type }}</span>
          <span class="reviewer-insight-panel__location">{{ issue.location }}</span>
        </div>
        <p class="reviewer-insight-panel__description">{{ issue.description }}</p>
        <p class="reviewer-insight-panel__suggestion">
          <span class="reviewer-insight-panel__suggestion-label">建议：</span>{{ issue.suggestion }}
        </p>
      </li>
    </ul>

    <div v-else class="reviewer-insight-panel__empty" role="status">暂无 Reviewer 意见</div>
  </section>
</template>

<style scoped>
.reviewer-insight-panel {
  min-width: 0;
  overflow-x: hidden;
  background: linear-gradient(180deg, #ffffff 0%, #fef3ec 100%);
  border: 1px solid rgba(255, 122, 92, 0.2);
  border-radius: 12px;
  padding: 16px;
}
.reviewer-insight-panel:focus-visible {
  outline: 2px solid var(--research-primary-500, #FF7A5C);
  outline-offset: 2px;
}
.reviewer-insight-panel__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12px;
}
.reviewer-insight-panel__title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}
.reviewer-insight-panel__count {
  font-size: 12px;
  color: #94a3b8;
}
.reviewer-insight-panel__summary {
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.reviewer-insight-panel__chip {
  font-size: 11px;
  color: white;
  padding: 2px 8px;
  border-radius: 999px;
}
.reviewer-insight-panel__chip[data-severity='high'] { background: #ef4444; }
.reviewer-insight-panel__chip[data-severity='medium'] { background: #f59e0b; }
.reviewer-insight-panel__chip[data-severity='low'] { background: #3b82f6; }
.reviewer-insight-panel__list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.reviewer-insight-panel__item {
  background: white;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 8px;
  padding: 12px;
}
.reviewer-insight-panel__item[data-severity='high'] {
  border-color: rgba(239, 68, 68, 0.4);
}
.reviewer-insight-panel__item[data-severity='medium'] {
  border-color: rgba(245, 158, 11, 0.4);
}
.reviewer-insight-panel__head-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.reviewer-insight-panel__severity {
  font-size: 11px;
  color: white;
  padding: 1px 6px;
  border-radius: 999px;
}
.reviewer-insight-panel__type {
  font-size: 12px;
  font-weight: 600;
  color: #1e293b;
}
.reviewer-insight-panel__location {
  font-size: 11px;
  color: #94a3b8;
}
.reviewer-insight-panel__description {
  font-size: 12px;
  color: #475569;
  margin: 0 0 6px;
  line-height: 1.5;
}
.reviewer-insight-panel__suggestion {
  font-size: 12px;
  color: #1e293b;
  margin: 0;
  background: rgba(255, 122, 92, 0.06);
  padding: 6px 8px;
  border-radius: 4px;
}
.reviewer-insight-panel__suggestion-label {
  font-weight: 600;
  color: var(--research-primary-500, #FF7A5C);
  margin-right: 4px;
}
.reviewer-insight-panel__empty {
  text-align: center;
  padding: 24px;
  color: #94a3b8;
  font-size: 13px;
}
@media (max-width: 1480px) {
  .reviewer-insight-panel {
    padding: 12px;
  }
}
@media (min-width: 1720px) {
  .reviewer-insight-panel {
    padding: 20px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .reviewer-insight-panel,
  .reviewer-insight-panel * {
    transition: none !important;
  }
}
</style>