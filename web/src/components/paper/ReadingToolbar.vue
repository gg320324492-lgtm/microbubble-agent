<template>
  <!-- v28 step 20: 工具栏整体删除（用户原话：'工具栏删去吧，放大缩小以及这个什么箭头之类的'） -->
  <div v-if="false" class="reading-toolbar"></div>
</template>

<script setup>
/**
 * v28 step 20: ReadingToolbar 整体删除
 *
 * 用户原话：'工具栏删去吧，放大缩小以及这个什么箭头之类的'
 * 字号/行距/跳顶部都是装饰性，PDF 阅读器不需要这些工具栏。
 * 保留组件文件（避免 import 报错），但 template 不渲染任何内容。
 */
const props = defineProps({
  paper: { type: Object, default: () => ({}) },
})
</script>
