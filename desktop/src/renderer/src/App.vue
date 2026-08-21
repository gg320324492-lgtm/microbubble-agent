<script setup lang="ts">
/**
 * Root App —— 按 route meta.layout 切换外壳。
 *
 * Phase 2-Impl-1:
 *   - layout=main  → MainLayout (Sidebar + Header)
 *   - layout=plain → 直接 router-view (LoginView / debug)
 *
 * 未登录也会渲染 plain (login) layout；登录后 main layout。
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import MainLayout from './layouts/MainLayout.vue'

const route = useRoute()
const layout = computed(() => {
  const meta = route.meta as { layout?: 'main' | 'plain' }
  return meta.layout ?? 'plain'
})
</script>

<template>
  <MainLayout v-if="layout === 'main'">
    <router-view />
  </MainLayout>
  <router-view v-else />
</template>

<style>
:root {
  color-scheme: dark light;
}
body {
  margin: 0;
  background: #020617;
  color: #e2e8f0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
</style>
