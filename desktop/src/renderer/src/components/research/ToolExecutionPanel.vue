<script setup lang="ts">
/**
 * 单个工具调用的展示契约。调用方只传入已经存在的执行记录；组件不推断
 * Agent、阶段、耗时或输出。
 */
export interface ToolExecution {
  id: string | number
  agent?: string
  tool: string
  stage?: string
  duration?: string
  status: 'running' | 'completed' | 'error'
  output?: string
}

const props = withDefaults(defineProps<{
  executions?: ToolExecution[]
  ariaLabel?: string
}>(), {
  executions: () => [],
  ariaLabel: '工具执行记录'
})

function toolStatusLabel(status: ToolExecution['status']): string {
  if (status === 'running') return '运行中'
  if (status === 'completed') return '已完成'
  return '异常'
}
</script>

<template>
  <section class="tool-execution-panel" :aria-label="props.ariaLabel">
    <header class="tool-execution-panel__header">
      <div>
        <p class="tool-execution-panel__eyebrow">Agent 运行可观测性</p>
        <h2 class="tool-execution-panel__title">工具执行</h2>
      </div>
      <span class="tool-execution-panel__count" aria-hidden="true">{{ props.executions.length }}</span>
    </header>

    <p
      v-if="props.executions.length === 0"
      class="tool-execution-panel__empty"
      role="status"
      aria-live="polite"
    >
      暂无工具执行记录
    </p>

    <ol v-else class="tool-execution-panel__list">
      <li
        v-for="(execution, index) in props.executions"
        :key="`${execution.id}-${index}`"
        class="tool-execution-panel__item"
      >
        <details class="tool-execution-panel__details">
          <summary class="tool-execution-panel__summary">
            <span class="tool-execution-panel__summary-content">
              <span class="tool-execution-panel__summary-label">工具</span>
              <span class="tool-execution-panel__summary-value">
                {{ execution.tool }}
              </span>
            </span>
            <span
              class="tool-execution-panel__status"
              :class="`is-${execution.status}`"
              :aria-label="`工具状态：${toolStatusLabel(execution.status)}`"
            >
              <span class="tool-execution-panel__status-marker" aria-hidden="true" />
              {{ toolStatusLabel(execution.status) }}
            </span>
          </summary>

          <dl class="tool-execution-panel__fields">
            <div class="tool-execution-panel__field">
              <dt>Agent</dt>
              <dd>{{ execution.agent || '待接入数据' }}</dd>
            </div>
            <div class="tool-execution-panel__field">
              <dt>工具</dt>
              <dd>{{ execution.tool }}</dd>
            </div>
            <div class="tool-execution-panel__field">
              <dt>阶段</dt>
              <dd>{{ execution.stage || '待接入数据' }}</dd>
            </div>
            <div class="tool-execution-panel__field">
              <dt>耗时</dt>
              <dd>{{ execution.duration || '暂无耗时数据' }}</dd>
            </div>
            <div class="tool-execution-panel__field">
              <dt>状态</dt>
              <dd :aria-label="`状态：${toolStatusLabel(execution.status)}`">
                {{ toolStatusLabel(execution.status) }}
              </dd>
            </div>
            <div class="tool-execution-panel__field tool-execution-panel__field--output">
              <dt>输出</dt>
              <dd>{{ execution.output || '暂无工具输出' }}</dd>
            </div>
          </dl>
        </details>
      </li>
    </ol>
  </section>
</template>

<style scoped>
.tool-execution-panel {
  display: grid;
  min-width: 0;
  gap: var(--research-space-4);
  padding: var(--research-space-5);
  border: 1px solid var(--research-border-subtle);
  border-radius: var(--research-radius-panel);
  background: var(--research-bg-card);
  box-shadow: var(--research-shadow-soft);
}

.tool-execution-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--research-space-3);
  min-width: 0;
}

.tool-execution-panel__eyebrow,
.tool-execution-panel__title { margin: 0; }

.tool-execution-panel__eyebrow {
  color: var(--research-text-secondary);
  font-size: var(--research-text-xs);
  font-weight: var(--research-font-weight-semibold);
  letter-spacing: .04em;
}

.tool-execution-panel__title {
  margin-top: var(--research-space-1);
  color: var(--research-text-primary);
  font-size: var(--research-text-section-title);
  font-weight: var(--research-font-weight-semibold);
  line-height: var(--research-line-height-tight);
}

.tool-execution-panel__count {
  display: grid;
  min-width: var(--research-space-6);
  min-height: var(--research-space-6);
  place-items: center;
  border-radius: var(--research-radius-pill);
  background: var(--research-primary-50);
  color: var(--research-primary-700);
  font-family: var(--research-font-numeric);
  font-size: var(--research-text-xs);
  font-weight: var(--research-font-weight-semibold);
}

.tool-execution-panel__list {
  display: grid;
  min-width: 0;
  gap: var(--research-space-3);
  margin: 0;
  padding: 0;
  list-style: none;
}

.tool-execution-panel__item,
.tool-execution-panel__details { min-width: 0; }

.tool-execution-panel__details {
  overflow: clip;
  border: 1px solid var(--research-border-subtle);
  border-radius: var(--research-radius-card);
  background: var(--research-bg-panel);
}

.tool-execution-panel__summary {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--research-space-3);
  min-width: 0;
  padding: var(--research-space-3);
  color: var(--research-text-primary);
  cursor: pointer;
  list-style: none;
}

.tool-execution-panel__summary::-webkit-details-marker { display: none; }

.tool-execution-panel__summary:focus-visible {
  border-radius: var(--research-radius-card);
  outline: none;
  box-shadow: var(--research-shadow-focus-primary);
}

.tool-execution-panel__summary-content {
  display: grid;
  min-width: 0;
  gap: var(--research-space-1);
}

.tool-execution-panel__summary-label,
.tool-execution-panel__field dt {
  color: var(--research-text-secondary);
  font-size: var(--research-text-xs);
  font-weight: var(--research-font-weight-medium);
}

.tool-execution-panel__summary-value,
.tool-execution-panel__field dd {
  min-width: 0;
  color: var(--research-text-primary);
  font-size: var(--research-text-sm);
  line-height: var(--research-line-height-body);
  overflow-wrap: anywhere;
}

.tool-execution-panel__status {
  display: inline-flex;
  align-items: center;
  gap: var(--research-space-1);
  color: var(--research-text-secondary);
  font-size: var(--research-text-xs);
  font-weight: var(--research-font-weight-medium);
  white-space: nowrap;
}

.tool-execution-panel__status-marker {
  width: var(--research-space-2);
  height: var(--research-space-2);
  border-radius: var(--research-radius-pill);
  background: var(--research-text-muted);
}

.tool-execution-panel__status.is-running { color: var(--research-ai-700); }
.tool-execution-panel__status.is-running .tool-execution-panel__status-marker {
  background: var(--research-ai-500);
  animation: tool-execution-panel-pulse var(--research-duration-slow) var(--research-ease-standard) infinite;
}
.tool-execution-panel__status.is-completed { color: var(--research-success-700); }
.tool-execution-panel__status.is-completed .tool-execution-panel__status-marker { background: var(--research-success-500); }
.tool-execution-panel__status.is-error { color: var(--research-danger-600); }
.tool-execution-panel__status.is-error .tool-execution-panel__status-marker { background: var(--research-danger-500); }

.tool-execution-panel__fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--research-space-3);
  min-width: 0;
  margin: 0;
  padding: 0 var(--research-space-3) var(--research-space-3);
  border-top: 1px solid var(--research-divider);
}

.tool-execution-panel__field {
  display: grid;
  min-width: 0;
  gap: var(--research-space-1);
  padding-top: var(--research-space-3);
}

.tool-execution-panel__field dd { margin: 0; }
.tool-execution-panel__field--output { grid-column: 1 / -1; }

.tool-execution-panel__empty {
  margin: 0;
  color: var(--research-text-secondary);
  font-size: var(--research-text-body);
  line-height: var(--research-line-height-body);
}

@keyframes tool-execution-panel-pulse {
  50% { opacity: .45; transform: scale(.8); }
}

@media (max-width: 520px) {
  .tool-execution-panel__fields { grid-template-columns: minmax(0, 1fr); }
  .tool-execution-panel__field--output { grid-column: auto; }
}

@media (prefers-reduced-motion: reduce) {
  .tool-execution-panel__status.is-running .tool-execution-panel__status-marker { animation: none; }
}
</style>
