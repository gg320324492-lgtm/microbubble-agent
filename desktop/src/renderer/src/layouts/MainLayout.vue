<script setup lang="ts">
/**
 * Main Layout —— 桌面端登录后主页壳。
 *
 * 结构: Sidebar (左, 220px) | Header (上, 60px) + Content (中, 弹性)
 *
 * Phase 2-Impl-1: 无菜单 collapse / 主题切换 / 全局搜索等进阶功能。
 */
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
  background: #020617;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  color: #e2e8f0;
}
.main-layout__body {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.main-layout__content {
  flex: 1;
  overflow-y: auto;
  background: #020617;
  /* 子页面自管 padding */
}
</style>
