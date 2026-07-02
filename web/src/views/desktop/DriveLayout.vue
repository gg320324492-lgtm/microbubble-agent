<!--
  DriveLayout.vue — 桌面端网盘容器 (v2 PR7 修复)

  功能:
  - 左侧: DriveSubSidebar (4 项导航, 可折叠, localStorage 持久化)
  - 右侧: <router-view /> (nested children: /drive /drive/trash /drive/activity /drive/requests 之一)

  关键设计:
  - 子侧边栏只在容器 mount 时挂载一次, 4 个 view 切换不会 remount, 折叠状态保持
  - activeKey 自动响应 $route.path (无需 view 手动传 prop)
  - 移动端不渲染本组件 (resolveMobileComponent 走 MobileDriveView 独立页面)

  使用:
    router/index.js: path 'drive' parent component = this DriveLayout (desktop only)
    4 children: DesktopDriveView / DriveTrashView / ActivityFeedView / FileRequestListView
-->
<template>
  <div class="drive-layout">
    <!-- v2 PR7: 网盘内部子侧边栏 (始终保持渲染, 4 view 切换不闪烁) -->
    <DriveSubSidebar
      :collapsed="collapsed"
      :active-key="activeKey"
      @toggle="toggle"
    />

    <!-- nested view: 4 个子 view 之一 -->
    <main class="drive-layout-content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import DriveSubSidebar from '@/components/drive/DriveSubSidebar.vue'
import { useDriveSubSidebarCollapsed } from '@/composables/useDriveSubSidebarCollapsed'

const route = useRoute()
const { collapsed, toggle } = useDriveSubSidebarCollapsed()

// activeKey 自动响应 $route.path (4 view 切换时子侧边栏 active 高亮即时更新)
const activeKey = computed(() => {
  const p = route.path
  if (p.startsWith('/drive/trash')) return 'trash'
  if (p.startsWith('/drive/activity')) return 'activity'
  if (p.startsWith('/drive/requests')) return 'requests'
  return 'files'  // /drive 及其子路径 (含 /drive/file/:id 详情页仍走 files active)
})
</script>

<style scoped>
.drive-layout {
  display: flex;
  height: 100%;
  background: var(--color-bg-page, #fafbfc);
  overflow: hidden;
}
.drive-layout-content {
  flex: 1;
  min-width: 0;
  overflow: auto;
}
</style>

<!-- v60-v67 教训: dark mode 跨组件覆盖必须非 scoped 块 -->
<style>
html.dark .drive-layout {
  background: var(--color-bg-page, #1a1d23);
}
</style>
