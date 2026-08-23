<script setup lang="ts">
/**
 * 错误状态占位 —— API 失败 / 异常时展示。
 * 严禁引 Element Plus el-alert。
 */
import Button from './Button.vue'
import ResearchIcon from '../icons/ResearchIcon.vue'

interface Props {
  title?: string
  message?: string
  retryable?: boolean
}
const props = withDefaults(defineProps<Props>(), {
  title: '分析失败，请重试',
  message: '已有内容不会丢失，可以重新发起本次分析。',
  retryable: true
})

const emit = defineEmits<{ retry: [] }>()

</script>

<template>
  <div class="ui-error">
    <div class="ui-error__icon"><ResearchIcon name="error" :size="28" /></div>
    <h4 class="ui-error__title">{{ props.title }}</h4>
    <p class="ui-error__message">{{ message }}</p>
    <div v-if="retryable" class="ui-error__action">
      <Button variant="secondary" size="small" @click="emit('retry')">重试</Button>
    </div>
  </div>
</template>

<style scoped>
.ui-error {
  text-align: center;
  padding: var(--research-space-8) var(--research-space-4);
  background: var(--research-danger-50);
  border: 1px solid var(--research-danger-100);
  border-radius: var(--research-radius-card);
  color: var(--research-danger-600);
}
.ui-error__icon {
  margin-bottom: var(--research-space-2);
}
.ui-error__title {
  margin: 0 0 var(--research-space-2);
  font-size: var(--research-text-card-title);
  font-weight: var(--research-font-weight-semibold);
  color: var(--research-danger-600);
}
.ui-error__message {
  margin: 0;
  font-size: var(--research-text-sm);
  color: var(--research-text-secondary);
  line-height: var(--research-line-height-body);
}
.ui-error__action {
  margin-top: var(--research-space-4);
}
</style>
