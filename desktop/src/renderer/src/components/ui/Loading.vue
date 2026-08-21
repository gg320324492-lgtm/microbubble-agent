<script setup lang="ts">
/**
 * Loading 占位 —— 骨架屏 / 旋转 spinner。
 * 不引 Element Plus el-skeleton。
 */
interface Props {
  variant?: 'spinner' | 'skeleton'
  text?: string
  rows?: number
}
withDefaults(defineProps<Props>(), { variant: 'spinner', rows: 3 })
</script>

<template>
  <div v-if="variant === 'spinner'" class="ui-loading ui-loading--spinner">
    <span class="ui-spinner" />
    <p v-if="text" class="ui-loading__text">{{ text }}</p>
  </div>
  <div v-else class="ui-loading ui-loading--skeleton">
    <div v-for="i in rows" :key="i" class="ui-skeleton" :style="{ width: 70 - i * 5 + '%' }" />
  </div>
</template>

<style scoped>
.ui-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem 1rem;
  color: #94a3b8;
  font-size: 0.85rem;
}
.ui-loading--skeleton {
  align-items: stretch;
  gap: 0.6rem;
}
.ui-loading__text {
  margin: 0.5rem 0 0;
}
.ui-spinner {
  width: 28px;
  height: 28px;
  border: 3px solid #334155;
  border-top-color: #f97316;
  border-radius: 50%;
  animation: ui-spin 0.8s linear infinite;
}
@keyframes ui-spin {
  to { transform: rotate(360deg); }
}
.ui-skeleton {
  height: 14px;
  background: linear-gradient(90deg, #334155 0%, #475569 50%, #334155 100%);
  background-size: 200% 100%;
  border-radius: 3px;
  animation: ui-shimmer 1.4s ease-in-out infinite;
}
@keyframes ui-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
