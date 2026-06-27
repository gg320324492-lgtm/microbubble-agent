<template>
  <component
    :is="resolved"
    :block="block"
    :compact="true"
    class="mobile-rich-card"
  />
</template>

<script setup>
/**
 * MobileRichCard.vue — 移动端富文本块壳组件
 *
 * PR #3:
 * - 接收 block: { type, data, title }
 * - 根据 type 从 RichContent 映射到对应 block 组件
 * - 桌面端 RichContent 通过 props.compact 切换紧凑模式
 *
 * 注意：复用桌面端 10 个 Rich Block 组件（MeetingCard/TaskListBlock/etc.），
 * 它们的模板用 el-table / el-card，移动端用 mobile-styles.css 强制覆盖。
 * 仅 ChartBlock 需要单独的 mobile 版本（pinch 双指缩放）。
 */

import { computed } from 'vue'
import RichContent from '@/components/chat/RichContent.vue'

const props = defineProps({
  block: { type: Object, required: true },
})

// 直接复用 RichContent（已支持 :compact 模式）
const resolved = computed(() => RichContent)
</script>

<style>
/* 全局 RichCard 移动端适配（在 mobile-base.css 范围外追加更具体规则） */
.mobile-rich-card {
  font-size: 13px;
}
.mobile-rich-card .el-table {
  font-size: 12px;
}
.mobile-rich-card pre {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  max-width: 100%;
}
</style>

<!-- v77 P2.6-B: dark mode 适配（v60-v67 教训：必须非 scoped） -->
<style>
/* MobileRichCard 是 RichContent 包装；内嵌 10 个 Rich Block 已有 dark 块（v77 P2.6-A 验证） */
[data-theme="dark"] .mobile-rich-card .rich-card {
  background: var(--color-bg-card);
  color: var(--color-text-regular);
  border: 1px solid var(--color-border-light);
}
[data-theme="dark"] .mobile-rich-card pre,
[data-theme="dark"] .mobile-rich-card code {
  background: var(--color-bg-page);
  color: var(--color-text-primary);
}
</style>