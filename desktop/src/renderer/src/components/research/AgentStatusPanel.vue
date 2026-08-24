<script lang="ts">
export type ResearchAgentStatus = 'idle' | 'running' | 'completed' | 'error'

/** 由科研页面传入的智能体运行状态。 */
export interface ResearchAgentStatusItem {
  name: string
  role: string
  status: ResearchAgentStatus
  queue?: number | string
  action?: string
}
</script>

<script setup lang="ts">
const props = withDefaults(defineProps<{
  agents?: ResearchAgentStatusItem[]
  ariaLabel?: string
}>(), {
  agents: () => [],
  ariaLabel: 'AI 研究活动'
})

const statusLabels: Record<ResearchAgentStatus, string> = {
  idle: '等待中',
  running: '运行中',
  completed: '已完成',
  error: '异常'
}
</script>

<template>
  <section class="agent-status-panel" :aria-label="props.ariaLabel">
    <header class="agent-status-panel__header">
      <h2 class="agent-status-panel__title">AI 研究活动</h2>
    </header>

    <div v-if="props.agents.length" class="agent-status-panel__list" role="list">
      <article v-for="agent in props.agents" :key="agent.name" class="agent-status-panel__item" role="listitem">
        <header class="agent-status-panel__item-header">
          <div>
            <h3 class="agent-status-panel__name">{{ agent.name }}</h3>
            <p class="agent-status-panel__role">{{ agent.role }}</p>
          </div>
          <span :class="['agent-status-panel__status', `is-${agent.status}`]" role="status">
            <span class="agent-status-panel__indicator" aria-hidden="true" />
            {{ statusLabels[agent.status] }}
          </span>
        </header>
        <dl class="agent-status-panel__details">
          <div>
            <dt>队列</dt>
            <dd>{{ agent.queue ?? 0 }}</dd>
          </div>
          <div>
            <dt>当前动作</dt>
            <dd>{{ agent.action || '暂无当前动作' }}</dd>
          </div>
        </dl>
      </article>
    </div>

    <p v-else class="agent-status-panel__empty" role="status">暂无智能体活动</p>
  </section>
</template>

<style scoped>
.agent-status-panel {
  min-width: 0;
  padding: var(--research-space-5);
  border: 1px solid var(--research-border-subtle);
  border-radius: var(--research-radius-panel);
  background: var(--research-bg-card);
  box-shadow: var(--research-shadow-soft);
}

.agent-status-panel__header { margin-bottom: var(--research-space-4); }

.agent-status-panel__title {
  margin: 0;
  color: var(--research-text-primary);
  font-size: var(--research-text-section-title);
  font-weight: var(--research-font-weight-semibold);
  line-height: var(--research-line-height-tight);
}

.agent-status-panel__list { display: grid; gap: var(--research-space-3); }

.agent-status-panel__item {
  min-width: 0;
  padding: var(--research-space-4);
  border: 1px solid var(--research-border-subtle);
  border-radius: var(--research-radius-card);
  background: var(--research-bg-panel);
}

.agent-status-panel__item-header {
  display: flex;
  justify-content: space-between;
  gap: var(--research-space-3);
}

.agent-status-panel__name,
.agent-status-panel__role { margin: 0; }

.agent-status-panel__name {
  color: var(--research-text-primary);
  font-size: var(--research-text-body);
  font-weight: var(--research-font-weight-semibold);
  line-height: var(--research-line-height-tight);
}

.agent-status-panel__role {
  margin-top: var(--research-space-1);
  color: var(--research-text-secondary);
  font-size: var(--research-text-sm);
  line-height: var(--research-line-height-body);
}

.agent-status-panel__status {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  align-self: flex-start;
  gap: var(--research-space-1);
  color: var(--research-text-secondary);
  font-size: var(--research-text-xs);
  font-weight: var(--research-font-weight-medium);
  white-space: nowrap;
}

.agent-status-panel__indicator {
  width: var(--research-space-1);
  height: var(--research-space-1);
  border-radius: var(--research-radius-pill);
  background: currentcolor;
}

.agent-status-panel__status.is-running { color: var(--research-ai-700); }
.agent-status-panel__status.is-running .agent-status-panel__indicator {
  animation: agent-status-pulse var(--research-duration-slow) var(--research-ease-standard) infinite;
}
.agent-status-panel__status.is-completed { color: var(--research-success-700); }
.agent-status-panel__status.is-error { color: var(--research-danger-600); }

.agent-status-panel__details {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 180px), 1fr));
  gap: var(--research-space-3);
  margin: var(--research-space-4) 0 0;
}

.agent-status-panel__details div { min-width: 0; }

.agent-status-panel__details dt {
  color: var(--research-text-secondary);
  font-size: var(--research-text-xs);
  font-weight: var(--research-font-weight-medium);
}

.agent-status-panel__details dd {
  margin: var(--research-space-1) 0 0;
  color: var(--research-text-primary);
  font-size: var(--research-text-sm);
  line-height: var(--research-line-height-body);
  overflow-wrap: anywhere;
}

.agent-status-panel__empty {
  margin: 0;
  color: var(--research-text-secondary);
  font-size: var(--research-text-body);
  line-height: var(--research-line-height-body);
}

@keyframes agent-status-pulse {
  50% { opacity: 0.45; }
}

@media (prefers-reduced-motion: reduce) {
  .agent-status-panel__status.is-running .agent-status-panel__indicator { animation: none; }
}
</style>
