<script setup lang="ts">
// 工作台外壳 — 自绘标题栏 + 侧边栏六项 + 状态栏（骨架设计 §3 信息架构）
import TitleBar from './TitleBar.vue'
import SideNav from './SideNav.vue'
import StatusBar from './StatusBar.vue'
</script>

<template>
  <div class="shell">
    <TitleBar />
    <div class="shell-body">
      <SideNav />
      <main class="shell-main">
        <router-view />
      </main>
    </div>
    <StatusBar />
  </div>
</template>

<style scoped>
.shell {
  height: 100vh;
  display: grid;
  grid-template-rows: var(--wb-titlebar-height) 1fr var(--wb-statusbar-height);
  background: var(--color-bg-page);
}
.shell-body {
  display: grid;
  grid-template-columns: var(--wb-sidebar-width) 1fr;
  overflow: hidden;
}
.shell-main {
  overflow-y: auto;
  padding: var(--space-6);
  background: var(--color-bg-page);
}
</style>
