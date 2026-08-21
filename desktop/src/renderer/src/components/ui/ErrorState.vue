<script setup lang="ts">
/**
 * 错误状态占位 —— API 失败 / 异常时展示。
 * 严禁引 Element Plus el-alert。
 */
import { computed } from 'vue'
import Button from './Button.vue'

interface Props {
  title?: string
  message: string
  retryable?: boolean
}
const props = withDefaults(defineProps<Props>(), {
  title: '出错了',
  retryable: true
})

const emit = defineEmits<{ retry: [] }>()

const finalTitle = computed(() => props.title)
</script>

<template>
  <div class="ui-error">
    <div class="ui-error__icon">⚠️</div>
    <h4 class="ui-error__title">{{ finalTitle }}</h4>
    <p class="ui-error__message">{{ message }}</p>
    <div v-if="retryable" class="ui-error__action">
      <Button variant="secondary" size="small" @click="emit('retry')">重试</Button>
    </div>
  </div>
</template>

<style scoped>
.ui-error {
  text-align: center;
  padding: 2rem 1rem;
  background: rgba(239, 68, 68, 0.06);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
  color: #fecaca;
}
.ui-error__icon {
  font-size: 2.4rem;
  margin-bottom: 0.5rem;
}
.ui-error__title {
  margin: 0 0 0.4rem;
  font-size: 1rem;
  font-weight: 600;
  color: #f87171;
}
.ui-error__message {
  margin: 0;
  font-size: 0.85rem;
  color: #fca5a5;
}
.ui-error__action {
  margin-top: 1rem;
}
</style>
