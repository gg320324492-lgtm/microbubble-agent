<script setup lang="ts">
// 工作台外壳 — 自绘标题栏 + 侧边栏六项 + 状态栏（骨架设计 §3 信息架构）
import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import TitleBar from './TitleBar.vue'
import SideNav from './SideNav.vue'
import StatusBar from './StatusBar.vue'

const router = useRouter()
let offOpenSettings: (() => void) | null = null

// M6-1：更新通知被点击 → 主进程聚焦窗口并推送本事件，这里落到设置页
onMounted(() => {
  offOpenSettings = window.api.update.onOpenSettings(() => {
    void router.push({ name: 'settings' })
  })
})

onUnmounted(() => {
  offOpenSettings?.()
})
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
  /* M7 随车必办①：矮窗口下内容可滚（M5-2 遗留缺陷——此前 overflow:hidden 会把超长
     内容直接裁掉且无法滚动，设置页最先暴露）。
     列表型视图根容器是 min-height:auto 的列向 flex item，不会收缩到内容以下，
     因此内容超高时由本容器滚动；对话页 .workbench 显式 min-height:0 恰好填满，
     仍走内部独立滚动（消息流/会话列表各自滚动），不会出现双滚动条。 */
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--color-bg-page);
  display: flex;
  flex-direction: column;
  min-width: 0;
}
</style>
