<script setup lang="ts">
/** 科研桌面主壳：侧栏、全局状态栏和可独立滚动的研究工作区。 */
import Sidebar from './Sidebar.vue'
import HeaderBar from './HeaderBar.vue'
</script>

<template>
  <div class="main-layout">
    <Sidebar />
    <div class="main-layout__body">
      <HeaderBar />
      <main class="main-layout__content">
        <router-view />
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
