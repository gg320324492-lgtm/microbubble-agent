<script setup lang="ts">
/**
 * 空状态占位 —— 列表为空时展示。
 */
import { computed } from 'vue'
import ResearchIcon from '../icons/ResearchIcon.vue'
import { isResearchIconName, type ResearchIconName } from '../icons/research-icons'

interface Props {
  icon?: string
  title?: string
  description?: string
}
const props = withDefaults(defineProps<Props>(), {
  icon: 'document',
  title: '暂无科研数据'
})

const LEGACY_ICON_MAP: Record<string, ResearchIconName> = {
  '\u{1F5C2}\uFE0F': 'folder',
  '\u{1F50D}': 'search',
  '\u{1F4CB}': 'document',
  '\u{1F4AC}': 'assistant',
  '\u2728': 'sparkles'
}
const resolvedIcon = computed<ResearchIconName>(() => {
  if (isResearchIconName(props.icon)) return props.icon
  return LEGACY_ICON_MAP[props.icon] ?? 'document'
})
</script>

<template>
  <div class="ui-empty">
    <div class="ui-empty__icon"><ResearchIcon :name="resolvedIcon" :size="30" /></div>
    <h4 class="ui-empty__title">{{ title }}</h4>
    <p v-if="description" class="ui-empty__desc">{{ description }}</p>
    <div v-if="$slots.action" class="ui-empty__action">
      <slot name="action" />
    </div>
  </div>
</template>

<style scoped>
.ui-empty {
  text-align: center;
  padding: var(--research-space-10) var(--research-space-4);
  color: var(--research-text-secondary);
}
.ui-empty__icon {
  display: grid;
  width: 52px;
  height: 52px;
  margin: 0 auto var(--research-space-3);
  place-items: center;
  border-radius: var(--research-radius-card);
  background: var(--research-primary-50);
  color: var(--research-primary-600);
}
.ui-empty__title {
  margin: 0 0 var(--research-space-2);
  font-size: var(--research-text-card-title);
  font-weight: var(--research-font-weight-semibold);
  color: var(--research-text-primary);
}
.ui-empty__desc {
  margin: 0;
  font-size: var(--research-text-sm);
  line-height: var(--research-line-height-body);
}
.ui-empty__action {
  margin-top: var(--research-space-4);
}
</style>
