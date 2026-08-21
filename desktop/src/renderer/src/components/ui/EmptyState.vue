<script setup lang="ts">
/**
 * 空状态占位 —— 列表为空时展示。
 */
interface Props {
  icon?: string
  title?: string
  description?: string
}
withDefaults(defineProps<Props>(), { icon: '📭' })
</script>

<template>
  <div class="ui-empty">
    <div class="ui-empty__icon">{{ icon }}</div>
    <h4 class="ui-empty__title">{{ title ?? '暂无数据' }}</h4>
    <p v-if="description" class="ui-empty__desc">{{ description }}</p>
    <div v-if="$slots.action" class="ui-empty__action">
      <slot name="action" />
    </div>
  </div>
</template>

<style scoped>
.ui-empty {
  text-align: center;
  padding: 2.5rem 1rem;
  color: #94a3b8;
}
.ui-empty__icon {
  font-size: 3rem;
  margin-bottom: 0.5rem;
  opacity: 0.7;
}
.ui-empty__title {
  margin: 0 0 0.4rem;
  font-size: 0.95rem;
  font-weight: 500;
  color: #cbd5e1;
}
.ui-empty__desc {
  margin: 0;
  font-size: 0.85rem;
}
.ui-empty__action {
  margin-top: 1rem;
}
</style>
