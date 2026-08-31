<template>
  <nav
    class="mobile-tabbar mg-tabbar"
    role="navigation"
    aria-label="主导航"
  >
    <nut-tabbar
      :model-value="activeRoute"
      safe-area-inset-bottom
      bottom
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
        <span class="tabbar-dot" aria-hidden="true" />
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
 * 2026-08-31 液态毛玻璃升级: 悬浮玻璃胶囊形态。全部视觉规则收敛到
 *                assets/mobile-glass.css 的 .mg-tabbar 层（含 dark 变体），
 *                本组件只保留定位骨架 + active 微反馈。
 * 物理隔离：仅 isMobile 时渲染（MainLayout.vue 控制）
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
  // 2026-06-25: 转小写匹配 item.name
  // router.name 是 'Dashboard' 大写，item.name 是 'dashboard' 小写
  // NutUI 4 strict equality 'Dashboard' === 'dashboard' → false
  // 所以所有 tab 一直处于 unactive 状态 (历史 bug，之前没人验证过)
  return (route.name || route.path.replace('/', '') || 'dashboard').toString().toLowerCase()
})

function handleSwitch(name) {
  const target = items.find((i) => i.name === name)
  if (target && target.path !== route.path) {
    router.push(target.path)
  }
}
</script>

<style scoped>
/* 定位骨架 (胶囊外观全部在 mobile-glass.css .mg-tabbar) */
.mobile-tabbar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 2500; /* 高于一般内容，低于录音 FAB */
}

:deep(.nut-tabbar) {
  --nut-tabbar-height: var(--mg-tabbar-h, 58px);
}
:deep(.nut-tabbar-item) {
  min-height: var(--touch-target-min, 44px);
  transition: color 0.25s ease, transform 0.25s ease;
}
/* NutUI 4 不加 .active class，用反向命名 .nut-tabbar-item__icon--unactive
   所以 active 选择器是 :not(.nut-tabbar-item__icon--unactive) */
:deep(.nut-tabbar-item:not(.nut-tabbar-item__icon--unactive) .nut-tabbar-item-icon) {
  transform: scale(1.08);
  transition: transform 0.25s ease;
}
:deep(.nut-tabbar-item:not(.nut-tabbar-item__icon--unactive) .tabbar-label) {
  font-weight: 800;
}

.tabbar-label {
  font-size: 10.5px;
  line-height: 1.2;
  margin-top: 2px;
}

/* NutUI icon 占位（emoji fallback） */
:deep(.nut-tabbar-item-icon) {
  font-size: 21px;
  line-height: 21px;
}
</style>

<!-- dark 变体与玻璃配方在 mobile-glass.css（非 scoped 全局层）。
     教训保留 (v60-v67): Vue scoped 编译器会把 [data-theme="dark"] :deep(...) 的
     data-v 错误附加到属性选择器上，规则永远不匹配——跨组件 dark 覆盖必须放全局
     CSS 文件（本项目: mobile-glass.css），不要在 SFC 里玩 [attr]+:deep() 组合。 -->
