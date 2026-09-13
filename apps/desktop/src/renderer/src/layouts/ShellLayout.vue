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
  grid-template-columns: 56px 1fr;
  overflow: hidden;
}
.shell-main {
  overflow: hidden; /* 内部模块自行滚动（会话列表/消息流各自滚动） */
  background: var(--color-bg-page);
  display: flex;
  flex-direction: column;
  min-width: 0;
}
</style>
