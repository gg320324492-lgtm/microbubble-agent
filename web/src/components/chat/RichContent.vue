<script setup>
/**
 * RichContent.vue — 结构化富文本块分发器
 *
 * 用法：
 *   <RichContent :block="richBlock" />
 *
 * 实际渲染组件由 blocks/registry.ts 按 block.type 选择
 */
import { resolveBlock } from './blocks/registry'

defineProps({ block: { type: Object, required: true } })
</script>

<template>
  <component :is="resolveBlock(block.type)" :block="block" />
</template>
