<template>
  <div
    class="long-press-wrapper"
    :class="{ 'is-pressing': isPressing }"
    v-bind="bind"
  >
    <slot />
  </div>
</template>

<script setup>
/**
 * LongPressWrapper.vue — 长按手势包装器
 *
 * PR #3: 移动端长按触发操作菜单（复制/删除/收藏）
 * - 600ms 触发
 * - 移动 >10px 取消
 * - 触发时短震动反馈
 *
 * 用法：
 *   <LongPressWrapper @longpress="onLongPress">
 *     <div class="bubble">消息内容</div>
 *   </LongPressWrapper>
 */

import { useLongPress } from '@/composables/chat/useLongPress'

const props = defineProps({
  delay: { type: Number, default: 600 },
})

const emit = defineEmits(['longpress'])

const { bind, isPressing } = useLongPress(props.delay, (e) => {
  emit('longpress', e)
})
</script>

<style scoped>
.long-press-wrapper {
  display: contents; /* 不影响子元素布局 */
  /* 按下时视觉反馈 */
  transition: opacity 150ms;
}
.long-press-wrapper.is-pressing {
  opacity: 0.7;
}
</style>

<!-- v77 P2.6-B: dark mode 适配（v60-v67 教训：必须非 scoped） -->
<style>
[data-theme="dark"] .long-press-wrapper {
  /* 组件本身无背景色，但确保子元素在 dark 下不被父容器透出的暗色影响可读性 */
  color: var(--color-text-regular);
}
</style>