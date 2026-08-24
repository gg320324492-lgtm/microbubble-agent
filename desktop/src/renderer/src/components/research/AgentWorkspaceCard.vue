<script setup lang="ts">
/** 研究工作区中的单个 Agent 展示契约；所有运行数据由调用方传入。 */
type AgentWorkspaceStatus = 'pending' | 'running' | 'completed' | 'error'

const props = withDefaults(defineProps<{
  name: string
  role: string
  status?: AgentWorkspaceStatus
  currentTask?: string
  queue?: string | number
  dataAvailable?: boolean
}>(), {
  dataAvailable: false
})

const statusLabels: Record<AgentWorkspaceStatus, string> = {
  pending: '待处理',
  running: '运行中',
  completed: '已完成',
  error: '异常'
}

const statusText = (status: 'pending' | 'running' | 'completed' | 'error' | undefined): string =>
  props.dataAvailable && status
    ? statusLabels[status]
    : '待接入数据'

const currentTaskText = (): string => {
  if (!props.dataAvailable || !props.currentTask) return '待接入数据'
  return props.currentTask
}

const queueText = (): string | number =>
  props.dataAvailable && props.queue !== undefined && props.queue !== null && props.queue !== ''
    ? props.queue
    : '待接入数据'
</script>

<template>
  <article
    class="agent-workspace-card"
    :class="props.dataAvailable && props.status ? `is-${props.status}` : 'is-unavailable'"
    :aria-label="`Agent 工作区：${props.name}`"
  >
    <header class="agent-workspace-card__header">
      <div class="agent-workspace-card__identity">
        <p class="agent-workspace-card__eyebrow">Agent</p>
        <h3 class="agent-workspace-card__name">{{ props.name }}</h3>
      </div>
      <span class="agent-workspace-card__indicator" aria-hidden="true" />
    </header>

    <dl class="agent-workspace-card__details">
      <div class="agent-workspace-card__detail">
        <dt>角色</dt>
        <dd>{{ props.role }}</dd>
      </div>
      <div class="agent-workspace-card__detail">
        <dt>状态</dt>
        <dd
          class="agent-workspace-card__status"
          role="status"
          aria-live="polite"
          :aria-label="`状态：${statusText(props.status)}`"
        >
          <template v-if="props.dataAvailable">
            <span class="agent-workspace-card__status-marker" aria-hidden="true" />
            <span v-if="props.status">{{ props.status && statusLabels[props.status] }}</span>
            <span v-else>待接入数据</span>
            <span class="agent-workspace-card__status-code" aria-hidden="true">{{ props.status }}</span>
          </template>
          <span v-else>待接入数据</span>
        </dd>
      </div>
      <div class="agent-workspace-card__detail">
        <dt>当前任务</dt>
        <dd :aria-label="`当前任务：${currentTaskText()}`">
          <template v-if="props.dataAvailable">
            <span v-if="props.currentTask">{{ props.currentTask }}</span>
            <span v-else>待接入数据</span>
          </template>
          <span v-else>待接入数据</span>
        </dd>
      </div>
      <div class="agent-workspace-card__detail">
        <dt>队列</dt>
        <dd class="agent-workspace-card__queue" :aria-label="`队列：${queueText()}`">
          <template v-if="props.dataAvailable">
            <span v-if="props.queue !== undefined && props.queue !== null && props.queue !== ''">
              {{ props.queue }}
            </span>
            <span v-else>待接入数据</span>
          </template>
          <span v-else>待接入数据</span>
        </dd>
      </div>
    </dl>
  </article>
</template>

<style scoped>
.agent-workspace-card {
  display: grid;
  min-width: 0;
  gap: var(--research-space-4);
  padding: var(--research-space-4);
  border: 1px solid var(--research-border-subtle);
  border-radius: var(--research-radius-card);
  background: var(--research-bg-card);
  box-shadow: var(--research-shadow-soft);
}

.agent-workspace-card:focus-visible {
  outline: none;
  box-shadow: var(--research-shadow-focus-primary);
}

.agent-workspace-card__header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
  gap: var(--research-space-3);
  min-width: 0;
}

.agent-workspace-card__identity { min-width: 0; }

.agent-workspace-card__eyebrow,
.agent-workspace-card__name { margin: 0; }

.agent-workspace-card__eyebrow {
  color: var(--research-text-secondary);
  font-size: var(--research-text-xs);
  font-weight: var(--research-font-weight-semibold);
  letter-spacing: .04em;
}

.agent-workspace-card__name {
  margin-top: var(--research-space-1);
  color: var(--research-text-primary);
  font-size: var(--research-text-card-title);
  font-weight: var(--research-font-weight-semibold);
  line-height: var(--research-line-height-tight);
  overflow-wrap: anywhere;
}

.agent-workspace-card__indicator,
.agent-workspace-card__status-marker {
  width: var(--research-space-2);
  height: var(--research-space-2);
  flex: 0 0 auto;
  border-radius: var(--research-radius-pill);
  background: var(--research-text-muted);
}

.agent-workspace-card__details {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--research-space-3);
  min-width: 0;
  margin: 0;
}

.agent-workspace-card__detail {
  display: grid;
  min-width: 0;
  gap: var(--research-space-1);
}

.agent-workspace-card__detail dt {
  color: var(--research-text-secondary);
  font-size: var(--research-text-xs);
  font-weight: var(--research-font-weight-medium);
}

.agent-workspace-card__detail dd {
  min-width: 0;
  margin: 0;
  color: var(--research-text-primary);
  font-size: var(--research-text-sm);
  line-height: var(--research-line-height-body);
  overflow-wrap: anywhere;
}

.agent-workspace-card__status {
  display: inline-flex;
  align-items: center;
  gap: var(--research-space-1);
}

.agent-workspace-card__status-code { display: none; }

.agent-workspace-card.is-pending .agent-workspace-card__indicator,
.agent-workspace-card.is-pending .agent-workspace-card__status-marker { background: var(--research-warning-500); }

.agent-workspace-card.is-running .agent-workspace-card__indicator,
.agent-workspace-card.is-running .agent-workspace-card__status-marker { background: var(--research-ai-500); }

.agent-workspace-card.is-running .agent-workspace-card__indicator,
.agent-workspace-card.is-running .agent-workspace-card__status-marker {
  animation: agent-workspace-card-pulse var(--research-duration-slow) var(--research-ease-standard) infinite;
}

.agent-workspace-card.is-completed .agent-workspace-card__indicator,
.agent-workspace-card.is-completed .agent-workspace-card__status-marker { background: var(--research-success-500); }

.agent-workspace-card.is-error .agent-workspace-card__indicator,
.agent-workspace-card.is-error .agent-workspace-card__status-marker { background: var(--research-danger-500); }

@keyframes agent-workspace-card-pulse {
  50% { opacity: .42; transform: scale(.8); }
}

@media (max-width: 420px) {
  .agent-workspace-card__details { grid-template-columns: minmax(0, 1fr); }
}

@media (prefers-reduced-motion: reduce) {
  .agent-workspace-card.is-running .agent-workspace-card__indicator,
  .agent-workspace-card.is-running .agent-workspace-card__status-marker { animation: none; }
}
</style>
