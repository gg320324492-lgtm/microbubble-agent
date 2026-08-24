<script lang="ts">
export type ResearchTimelineStatus = 'neutral' | 'pending' | 'running' | 'completed' | 'error'

/** 由科研页面传入的研究流程节点。 */
export interface ResearchTimelineItem {
  id: string | number
  title: string
  description: string
  timestamp?: string
  status: 'neutral' | 'pending' | 'running' | 'completed' | 'error'
  actor?: string
  href?: string
}
</script>

<script setup lang="ts">
const props = withDefaults(defineProps<{
  items?: ResearchTimelineItem[]
  ariaLabel?: string
}>(), {
  items: () => [],
  ariaLabel: '研究活动时间线'
})

const statusLabels: Record<ResearchTimelineStatus, string> = {
  neutral: '待处理',
  pending: '待开始',
  running: '进行中',
  completed: '已完成',
  error: '异常'
}
</script>

<template>
  <section class="research-timeline" :aria-label="props.ariaLabel">
    <header class="research-timeline__header">
      <h2 class="research-timeline__title">研究活动</h2>
    </header>

    <ol v-if="props.items.length" class="research-timeline__list" role="list">
      <li v-for="item in props.items" :key="item.id" class="research-timeline__item">
        <component
          :is="item.href ? 'a' : 'div'"
          class="research-timeline__entry"
          :href="item.href"
          :aria-current="item.status === 'running' ? 'step' : undefined"
        >
          <span
            :class="['research-timeline__marker', `research-timeline__marker--${item.status}`]"
            aria-hidden="true"
          />
          <span class="research-timeline__content">
            <span class="research-timeline__item-heading">
              <span class="research-timeline__item-title">{{ item.title }}</span>
              <span :class="['research-timeline__status', `is-${item.status}`]" role="status">
                {{ statusLabels[item.status] }}
              </span>
            </span>
            <span v-if="item.description" class="research-timeline__description">{{ item.description }}</span>
            <span v-if="item.actor || item.timestamp" class="research-timeline__metadata">
              <span v-if="item.actor">{{ item.actor }}</span>
              <time v-if="item.timestamp" :datetime="item.timestamp">{{ item.timestamp }}</time>
            </span>
          </span>
        </component>
      </li>
    </ol>

    <p v-else class="research-timeline__empty" role="status">暂无研究活动</p>
  </section>
</template>

<style scoped>
.research-timeline {
  min-width: 0;
  padding: var(--research-space-5);
  border: 1px solid var(--research-border-subtle);
  border-radius: var(--research-radius-panel);
  background: var(--research-bg-card);
  box-shadow: var(--research-shadow-soft);
}

.research-timeline__header { margin-bottom: var(--research-space-4); }

.research-timeline__title {
  margin: 0;
  color: var(--research-text-primary);
  font-size: var(--research-text-section-title);
  font-weight: var(--research-font-weight-semibold);
  line-height: var(--research-line-height-tight);
}

.research-timeline__list {
  display: grid;
  gap: var(--research-space-3);
  margin: 0;
  padding: 0;
  list-style: none;
}

.research-timeline__item { min-width: 0; }

.research-timeline__entry {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--research-space-3);
  min-width: 0;
  color: inherit;
  text-decoration: none;
}

a.research-timeline__entry:focus-visible {
  border-radius: var(--research-radius-sm);
  outline: none;
  box-shadow: var(--research-shadow-focus-primary);
}

.research-timeline__marker {
  width: var(--research-space-2);
  height: var(--research-space-2);
  margin-top: var(--research-space-2);
  border-radius: var(--research-radius-pill);
  background: var(--research-border-strong);
}

.research-timeline__marker--neutral { background: var(--research-border-strong); }

.research-timeline__marker--running {
  background: var(--research-ai-500);
  animation: research-timeline-pulse var(--research-duration-slow) var(--research-ease-standard) infinite;
}

.research-timeline__marker--completed { background: var(--research-success-500); }
.research-timeline__marker--error { background: var(--research-danger-500); }
.research-timeline__content { display: grid; min-width: 0; gap: var(--research-space-1); }

.research-timeline__item-heading {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--research-space-2);
  min-width: 0;
}

.research-timeline__item-title {
  min-width: 0;
  color: var(--research-text-primary);
  font-size: var(--research-text-body);
  font-weight: var(--research-font-weight-medium);
  line-height: var(--research-line-height-body);
  overflow-wrap: anywhere;
}

.research-timeline__status {
  color: var(--research-text-secondary);
  font-size: var(--research-text-xs);
  font-weight: var(--research-font-weight-medium);
  white-space: nowrap;
}

.research-timeline__status.is-neutral { color: var(--research-text-secondary); }
.research-timeline__status.is-running { color: var(--research-ai-700); }
.research-timeline__status.is-completed { color: var(--research-success-700); }
.research-timeline__status.is-error { color: var(--research-danger-600); }

.research-timeline__description,
.research-timeline__metadata {
  color: var(--research-text-secondary);
  font-size: var(--research-text-sm);
  line-height: var(--research-line-height-body);
  overflow-wrap: anywhere;
}

.research-timeline__metadata { display: flex; flex-wrap: wrap; gap: var(--research-space-2); }

.research-timeline__empty {
  margin: 0;
  color: var(--research-text-secondary);
  font-size: var(--research-text-body);
  line-height: var(--research-line-height-body);
}

@keyframes research-timeline-pulse {
  50% { opacity: 0.45; }
}

@media (prefers-reduced-motion: reduce) {
  .research-timeline__marker--running { animation: none; }
}
</style>
