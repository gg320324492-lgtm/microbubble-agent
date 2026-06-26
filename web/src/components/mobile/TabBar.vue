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
  transition: background 0.25s ease, transform 0.25s ease;
}
/* 2026-06-25: iOS 风格卡片背景 (active 项)
   注意: NutUI 4 不加 .active class，而是用反向命名 .nut-tabbar-item__icon--unactive
   所以 active 选择器是 :not(.nut-tabbar-item__icon--unactive) */
:deep(.nut-tabbar-item:not(.nut-tabbar-item__icon--unactive)) {
  color: var(--color-primary);
  background: var(--color-primary-bg);
  border-radius: 10px;
  margin: 6px 4px;
  padding: 4px 0;
  position: relative;
  z-index: 1;
}
[data-theme="dark"] :deep(.nut-tabbar-item:not(.nut-tabbar-item__icon--unactive)) {
  background: rgba(255, 122, 92, 0.18);
}

/* v60 (2026-06-26) 修复深色模式 TabBar 颜色"看不出变化"：
   根因：上面 .nut-tabbar-item 用 var(--color-text-secondary)，但 variables.css:501
   在 light/dark 都保持 #909399（次要文字色设计上不变）。所以 inactive 在深色模式
   看起来和浅色一样——用户感知"没变"。
   active 用 var(--color-primary) 在 dark = #FF9D85，与 light = #FF7A5C 差异只有
   亮度 +15%，也几乎看不出。
   修复：在 [data-theme="dark"] 块覆盖两个颜色：
   - inactive: var(--color-text-regular) = #c0c4cc (dark)，亮灰与 #1a1d23 背景清晰对比
   - active: var(--color-accent) = #FFC067 (dark)，金橙比 #FF9D85 更亮更区分
   纪律：NutUI 内部的 nut-tabbar-item__icon--unactive 选择器用的是
   --nut-dark-color-gray / --nut-text-color，**不消费** --nut-tabbar-inactive-color；
   所以 v59 在 nutui-theme.scss 加的 --nut-tabbar-*-color 实际只影响 tips 角标。
   真正驱动 TabBar 颜色的是这里 scoped :deep(...) CSS，必须改这里 + dark 覆盖。 */
[data-theme="dark"] :deep(.nut-tabbar-item) {
  color: var(--color-text-regular);
}
[data-theme="dark"] :deep(.nut-tabbar-item:not(.nut-tabbar-item__icon--unactive)) {
  color: var(--color-accent);
  background: rgba(255, 179, 71, 0.18); /* dark active 背景：与 #FFC067 金橙协调 */
}
:deep(.nut-tabbar-item:not(.nut-tabbar-item__icon--unactive) .nut-tabbar-item-icon) {
  transform: scale(1.08);
  transition: transform 0.25s ease;
}
:deep(.nut-tabbar-item:not(.nut-tabbar-item__icon--unactive) .tabbar-label) {
  font-weight: 700;
  font-size: 12px;
  transition: all 0.25s ease;
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