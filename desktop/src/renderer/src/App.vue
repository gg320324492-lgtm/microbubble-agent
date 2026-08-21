<script setup lang="ts">
// 根组件：仅作为 router-view 容器。
</script>

<template>
  <router-view />
</template>

<style>
/* 全局 reset —— scoped 样式不进 root，否则 router-view 内的样式被锁住 */
:root {
  color-scheme: dark light;
}
body {
  margin: 0;
  background: #0f172a;
}
</style>
