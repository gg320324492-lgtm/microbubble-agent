<template>
  <div
    class="safe-area"
    :class="`safe-area-${position}`"
    :style="areaStyle"
    :aria-hidden="true"
  />
</template>

<script setup>
/**
 * SafeArea.vue — Safe Area 渲染组件
 *
 * PR #2: 渲染对应方向的 env(safe-area-inset-*) padding
 *
 * 用法：
 *   <SafeArea position="top" />            ← 顶部刘海/灵动岛
 *   <SafeArea position="bottom" />         ← 底部 Home Indicator
 *   <SafeArea position="left" />           ← 横屏左侧
 *   <SafeArea position="right" />          ← 横屏右侧
 *
 * 也可以用作 wrapper：
 *   <SafeArea position="bottom" tag="div">
 *     <button>底部按钮</button>
 *   </SafeArea>
 */

import { computed } from 'vue'

const props = defineProps({
  position: {
    type: String,
    default: 'bottom',
    validator: (v) => ['top', 'bottom', 'left', 'right', 'all'].includes(v),
  },
  /** 是否渲染可见占位（用于布局占位）；默认 true */
  visible: { type: Boolean, default: true },
})

const areaStyle = computed(() => {
  if (props.position === 'all') {
    return {
      paddingTop: 'var(--sat)',
      paddingRight: 'var(--sar)',
      paddingBottom: 'var(--sab)',
      paddingLeft: 'var(--sal)',
    }
  }
  const map = {
    top: 'var(--sat)',
    bottom: 'var(--sab)',
    left: 'var(--sal)',
    right: 'var(--sar)',
  }
  const prop = map[props.position]
  return {
    [props.position === 'top' || props.position === 'bottom' ? 'height' : 'width']: `var(--s${props.position === 'top' ? 'at' : props.position === 'bottom' ? 'ab' : props.position === 'left' ? 'al' : 'ar'})`,
    // 实际上不需要硬编码 height/width，padding 就够了
    paddingTop: props.position === 'top' ? prop : 0,
    paddingBottom: props.position === 'bottom' ? prop : 0,
    paddingLeft: props.position === 'left' ? prop : 0,
    paddingRight: props.position === 'right' ? prop : 0,
  }
})
</script>

<style scoped>
.safe-area {
  flex-shrink: 0;
  /* 通过 padding 实现 safe area 适配，父容器需要 flex 布局 */
}
</style>