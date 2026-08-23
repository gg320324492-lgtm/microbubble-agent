<script setup lang="ts">
import ResearchIcon from '../icons/ResearchIcon.vue'

const props = defineProps<{
  state: 'loading' | 'empty' | 'error'
  title?: string
  description?: string
}>()

const emit = defineEmits<{ retry: [] }>()

const COPY = {
  loading: { icon: 'sparkles', title: 'AI 正在分析...', description: '正在整理科研数据与证据，请稍候。' },
  empty: { icon: 'document', title: '暂无科研数据', description: '导入资料或创建研究任务后，这里会显示结果。' },
  error: { icon: 'error', title: '分析失败，请重试', description: '已有内容不会丢失，可以重新发起本次分析。' }
} as const
</script>

<template>
  <section
    :class="['research-state', `research-state--${state}`]"
    :aria-busy="state === 'loading'"
    :role="state === 'error' ? 'alert' : 'status'"
    :aria-live="state === 'error' ? 'assertive' : 'polite'"
    aria-atomic="true"
  >
    <span class="research-state__icon" aria-hidden="true">
      <ResearchIcon :name="COPY[state].icon" :size="28" />
    </span>
    <h3 class="research-state__title">{{ props.title ?? COPY[state].title }}</h3>
    <p class="research-state__description">{{ props.description ?? COPY[state].description }}</p>
    <button v-if="state === 'error'" class="research-state__retry" type="button" @click="emit('retry')">
      <ResearchIcon name="running" :size="15" />
      重新分析
    </button>
    <slot />
  </section>
</template>

<style scoped>
.research-state {
  display: flex;
  min-height: 188px;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  padding: var(--research-space-8);
  border: 1px dashed var(--research-border-strong);
  border-radius: var(--research-radius-card);
  background: var(--research-bg-panel);
  color: var(--research-text-secondary);
  text-align: center;
}
.research-state__icon {
  display: grid;
  width: 48px;
  height: 48px;
  margin-block-end: var(--research-space-3);
  place-items: center;
  border-radius: var(--research-radius-card);
  background: var(--research-primary-50);
  color: var(--research-primary-600);
}
.research-state--loading .research-state__icon { background: var(--research-ai-50); color: var(--research-ai-600); }
.research-state--error .research-state__icon { background: var(--research-danger-50); color: var(--research-danger-500); }
.research-state__title { margin: 0; color: var(--research-text-primary); font-size: var(--research-text-card-title); }
.research-state__description { max-width: 440px; margin: var(--research-space-2) 0 0; font-size: var(--research-text-sm); line-height: var(--research-line-height-body); }
.research-state__retry {
  display: inline-flex;
  align-items: center;
  gap: var(--research-space-2);
  margin-block-start: var(--research-space-4);
  padding: var(--research-space-2) var(--research-space-4);
  border: 1px solid var(--research-danger-100);
  border-radius: var(--research-radius-button);
  background: var(--research-bg-card);
  color: var(--research-danger-600);
  font: inherit;
  font-weight: var(--research-font-weight-medium);
  cursor: pointer;
}
.research-state__retry:focus-visible { outline: none; box-shadow: var(--research-shadow-focus-primary); }
</style>
