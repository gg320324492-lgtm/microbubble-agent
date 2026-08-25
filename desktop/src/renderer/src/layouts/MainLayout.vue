<script setup lang="ts">
/** 科研桌面主壳：侧栏、全局状态栏和可独立滚动的研究工作区。 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import Sidebar from './Sidebar.vue'
import HeaderBar from './HeaderBar.vue'
import DemoWarningBanner from '../components/shell/DemoWarningBanner.vue'

const route = useRoute()
const theme = computed(() => (route?.meta as { theme?: string } | undefined)?.theme ?? 'research')
</script>

<template>
  <div class="main-layout" :data-research-theme="theme">
    <Sidebar />
    <div class="main-layout__body">
      <HeaderBar />
      <DemoWarningBanner />
      <main class="main-layout__content" aria-label="科研工作区主内容">
        <slot />
      </main>
    </div>
  </div>
</template>

<style scoped>
.main-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: var(--research-bg-main);
  color: var(--research-text-primary);
  font-family: var(--research-font-sans);
}
.main-layout__body {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.main-layout__content {
  flex: 1;
  min-width: 0;
  overflow-x: hidden;
  overflow-y: auto;
  background: var(--research-bg-main);
}
</style>
