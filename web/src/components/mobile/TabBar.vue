<template>
  <nav
    class="mobile-tabbar"
    role="navigation"
    aria-label="主导航"
  >
    <nut-tabbar
      :model-value="activeRoute"
      safe-area-inset-bottom
      placeholder
      bottom
      inactive-color="#909399"
      active-color="#FF7A5C"
      @switch="handleSwitch"
    >
      <nut-tabbar-item
        v-for="item in items"
        :key="item.name"
        :name="item.name"
        :icon="item.icon"
        :to="item.path"
      >
        <span class="tabbar-label">{{ item.title }}</span>
      </nut-tabbar-item>
    </nut-tabbar>
  </nav>
</template>

<script setup>
/**
 * TabBar.vue — 移动端底部导航（基于 NutUI nut-tabbar）
 *
 * PR #2: 5 项底部导航（首页 / 智能对话 / 任务 / 知识 / 我的）
 * 2026-06-25 调整: 5 项保持，"对话"放正中间（第 3 位），
 *                删去"知识"，换成"听会"（/meetings）。
 * 物理隔离：仅 isMobile 时渲染（MainLayout.vue 控制）
 *
 * 注意：使用 Element Plus 图标（项目已统一），通过 v-for 动态渲染
 *      NutUI tabbar item 不直接支持 Element Plus 图标组件，所以这里用
 *      v-html 渲染 emoji 或内联 SVG（更轻）
 */

import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

// 5 项导航（2026-06-25 调整：对话居中，知识 → 听会）
// 顺序：首页 / 听会 / 对话(中间) / 任务 / 我的
const items = [
  { name: 'dashboard', path: '/dashboard', title: '首页', icon: 'home' },
  { name: 'meetings',  path: '/meetings',  title: '听会', icon: 'microphone' },
  { name: 'chat',      path: '/chat',      title: '对话', icon: 'chat' },
  { name: 'tasks',     path: '/tasks',     title: '任务', icon: 'list' },
  { name: 'settings',  path: '/settings',  title: '我的', icon: 'user' },
]

const activeRoute = computed(() => {
  // 取最高优先级匹配的路由 name
  return route.name || route.path.replace('/', '') || 'dashboard'
})

function handleSwitch(name) {
  const target = items.find((i) => i.name === name)
  if (target && target.path !== route.path) {
    router.push(target.path)
  }
}
</script>

<style scoped>
.mobile-tabbar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 2500; /* 高于一般内容，低于录音 FAB */
  background: rgba(255, 255, 255, 0.92);
  -webkit-backdrop-filter: blur(16px);
  backdrop-filter: blur(16px);
  border-top: 1px solid var(--color-border);
}

/* Dark mode */
[data-theme="dark"] .mobile-tabbar {
  background: rgba(26, 29, 35, 0.92);
  border-top-color: var(--color-border-base);
}

/* 调整 NutUI tabbar 默认样式 */
:deep(.nut-tabbar) {
  --nut-tabbar-height: var(--tabbar-height, 56px);
}
:deep(.nut-tabbar-item) {
  color: var(--color-text-secondary);
  min-height: var(--touch-target-min, 44px);
}
:deep(.nut-tabbar-item.active) {
  color: var(--color-primary);
}

.tabbar-label {
  font-size: 11px;
  line-height: 1.2;
  margin-top: 2px;
}

/* NutUI icon 占位（emoji fallback） */
:deep(.nut-tabbar-item-icon) {
  font-size: 22px;
  line-height: 22px;
}
</style>