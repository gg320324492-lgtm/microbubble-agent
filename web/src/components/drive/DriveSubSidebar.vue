<!--
  DriveSubSidebar.vue — 网盘页面内部子侧边栏 (v2 PR7)

  功能：在网盘页面左侧显示 4 个导航项（我的文件/回收站/活动动态/文件请求）
  折叠状态：localStorage (key: mnb:ui:drive:subSidebarCollapsed)
  展开时宽度：200px；折叠时宽度：64px（仅图标）

  使用：
    <DriveSubSidebar :collapsed="..." :active-key="..." @toggle="..." />

  父组件（DesktopDriveView）负责 activeKey 计算和路由分发。
-->
<template>
  <aside
    class="drive-sub-sidebar"
    :class="{ collapsed }"
    aria-label="网盘子侧边栏"
  >
    <!-- 折叠/展开按钮 -->
    <div
      class="sub-sidebar-toggle"
      role="button"
      tabindex="0"
      :aria-label="collapsed ? '展开子侧边栏' : '收起子侧边栏'"
      @click="$emit('toggle')"
      @keydown.enter="$emit('toggle')"
      @keydown.space.prevent="$emit('toggle')"
    >
      <el-icon><Fold v-if="!collapsed" /><Expand v-else /></el-icon>
      <span v-if="!collapsed" class="toggle-label">收起</span>
    </div>

    <!-- 侧边栏项列表 -->
    <nav class="sub-sidebar-items">
      <router-link
        v-for="item in items"
        :key="item.key"
        :to="item.to"
        class="sub-sidebar-item"
        :class="{ active: activeKey === item.key }"
        :title="collapsed ? item.label : ''"
        :aria-label="item.label"
      >
        <el-icon size="18"><component :is="item.icon" /></el-icon>
        <span v-if="!collapsed" class="sub-sidebar-item-label">{{ item.label }}</span>
      </router-link>
    </nav>
  </aside>
</template>

<script setup>
import { Folder, Delete, Bell, Promotion, Fold, Expand } from '@element-plus/icons-vue'

defineProps({
  collapsed: { type: Boolean, default: false },
  activeKey: { type: String, default: 'files' }
})
defineEmits(['toggle'])

const items = [
  { key: 'files',     label: '我的文件', icon: Folder,    to: '/drive' },
  { key: 'trash',     label: '回收站',   icon: Delete,    to: '/drive/trash' },
  { key: 'activity',  label: '活动动态', icon: Bell,      to: '/drive/activity' },
  { key: 'requests',  label: '文件请求', icon: Promotion, to: '/drive/requests' }
]
</script>

<style scoped>
.drive-sub-sidebar {
  width: 200px;
  background: var(--color-bg-card, #ffffff);
  border-right: 1px solid var(--color-border-light, #ebeef5);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: width 0.2s var(--ease-out, ease-out);
  overflow: hidden;
}

.drive-sub-sidebar.collapsed {
  width: 64px;
}

.sub-sidebar-toggle {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
  padding: 14px 20px;
  cursor: pointer;
  color: var(--color-text-secondary, #606266);
  border-bottom: 1px solid var(--color-border-lighter, #f0f0f0);
  user-select: none;
  font-size: 13px;
  transition: color 0.15s var(--ease-out, ease-out);
}

.sub-sidebar-toggle:hover {
  color: var(--color-primary, #ff7a5c);
}

.sub-sidebar-toggle:focus-visible {
  outline: 2px solid var(--color-primary, #ff7a5c);
  outline-offset: -2px;
}

.collapsed .sub-sidebar-toggle {
  justify-content: center;
  padding: 14px 0;
}

.toggle-label {
  white-space: nowrap;
}

.sub-sidebar-items {
  flex: 1;
  padding: 12px 0;
  overflow-y: auto;
}

.sub-sidebar-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 20px;
  color: var(--color-text-regular, #303133);
  text-decoration: none;
  font-size: 14px;
  transition: background 0.15s var(--ease-out, ease-out),
              color 0.15s var(--ease-out, ease-out);
  cursor: pointer;
  white-space: nowrap;
}

.sub-sidebar-item:hover {
  background: var(--color-primary-light-9, #fff5f0);
  color: var(--color-primary, #ff7a5c);
}

.sub-sidebar-item.active {
  background: var(--color-primary-light-8, rgba(255, 122, 92, 0.15));
  color: var(--color-primary, #ff7a5c);
  font-weight: 500;
  border-right: 3px solid var(--color-primary, #ff7a5c);
}

.sub-sidebar-item:focus-visible {
  outline: 2px solid var(--color-primary, #ff7a5c);
  outline-offset: -2px;
}

.collapsed .sub-sidebar-item {
  justify-content: center;
  padding: 11px 0;
  gap: 0;
  border-right: none;
}

.collapsed .sub-sidebar-item.active {
  border-right: none;
  border-left: 3px solid var(--color-primary, #ff7a5c);
}

.collapsed .sub-sidebar-item-label {
  display: none;
}
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped 块
  DesktopDriveView.vue 末尾统一覆盖 .drive-sub-sidebar 在 dark mode 下的颜色
-->
