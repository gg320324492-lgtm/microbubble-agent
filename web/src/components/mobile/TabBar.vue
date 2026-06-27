<template>
  <nav
    class="mobile-tabbar glass glass-lg"
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
  /* v77 P2.5.1: backdrop-filter + 半透 background 由 .glass 工具类提供 */
  border-top: 1px solid var(--color-border);
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
  background: rgba(var(--color-primary-rgb), 0.18);
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

/* v61 (2026-06-26) 修复 v60 编译 bug：Vue 3 scoped CSS 组合 [attr] 属性选择器
   + :deep() 有坑。v60 写 [data-theme="dark"] :deep(.nut-tabbar-item)，
   编译器把 data-v-2c0c6d65 加到了 [data-theme="dark"] 上而不是 :deep 内部选择器，
   编译产物为 [data-theme=dark][data-v-2c0c6d65] .nut-tabbar-item，
   需要同一个元素同时有两个属性才匹配——但 <html> 只有 data-theme，
   <nav> 只有 data-v，**永远不匹配**。
   修复：先试 :global([data-theme="dark"]) :deep(.nut-tabbar-item)，
   但 Vue 把 :global() 后面的 :deep() + 后代选择器组合处理错了：
   编译产物变成 [data-theme=dark]{color:var(--color-accent)} 单独的规则，
   把后代选择器和 :deep() 部分都丢了——而且这条规则会作用到 <html> 而不是 .nut-tabbar-item！
   所以 v61 还是错的。

   v62 终极修复：把 dark mode 规则移到 Vue SFC 的**第二个非 scoped \3c style> 块**。
   非 scoped 块不会附加 data-v，规则全局生效，直接命中 NutUI 元素。 */
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

<!-- v62 (2026-06-26) 第二个非 scoped <style> 块：dark mode 覆盖 NutUI TabBar 颜色。
     为什么需要非 scoped：v60 的 [data-theme="dark"] :deep(.nut-tabbar-item) 被 Vue
     scoped CSS 编译器把 data-v 错误附加到 [data-theme="dark"] 上，规则永远不匹配；
     v61 试 :global() :deep() 组合也被 Vue 处理错（编译产物是单独的 [data-theme=dark]
     规则，作用于 <html> 而不是 .nut-tabbar-item，且后一条规则被丢弃）。
     非 scoped 块彻底绕过 Vue scoped 编译，规则全局生效直接命中 NutUI 元素。
     纪律：Vue SFC 中如果 dark mode 规则要跨组件生效（如 NutUI 第三方元素），
     优先用第二个非 scoped <style> 块，不要在 scoped 块里玩 [attr] + :deep() 组合。 -->
<style>
[data-theme="dark"] .nut-tabbar-item {
  color: var(--color-text-regular); /* dark=#c0c4cc 亮灰，与 #1a1d23 背景对比清晰 */
}
[data-theme="dark"] .nut-tabbar-item:not(.nut-tabbar-item__icon--unactive) {
  color: var(--color-accent);        /* dark=#FFC067 金橙，比 #FF9D85 亮更区分 */
  background: rgba(var(--color-accent-rgb), 0.18); /* 金橙调背景与 #FFC067 协调 */
}

/* v63 (2026-06-26) 修复 inactive tab icon 颜色：v62 上面第一条规则
   [data-theme="dark"] .nut-tabbar-item 设的是父元素 color，但 NutUI 编译 CSS
   rule 15 直接在子元素 .nut-tabbar-item__icon--unactive 上设
   color: var(--nut-black, #000)，本项目 nutui-theme.scss:35 定义 --nut-black = #2D2D2D。
   子元素直接设色切断继承 → v62 的父规则对 inactive icon 无效 → 图标仍是 #2D2D2D。
   修复：直接命中 NutUI 实际设色的子元素选择器 .nut-tabbar-item__icon--unactive。
   特异性对比: NutUI rule 15 = (0,1,0)，本规则 = (0,2,0)，胜出。 */
[data-theme="dark"] .nut-tabbar-item__icon--unactive {
  color: var(--color-text-regular);
}

/* v64 (2026-06-26) 修复 .mobile-tabbar 容器背景：v62/v63 只把 nut-tabbar-item
   颜色移到这里，但漏了 .mobile-tabbar 容器背景。容器背景 dark 模式还在 scoped
   \3c style> 块里：scoped CSS 编译 [data-theme="dark"] .mobile-tabbar 时把 data-v 错误
   附加到属性选择器（同 v60 教训），编译产物 [data-theme=dark] .mobile-tabbar
   [data-v-xxx] 要求同一元素同时有两属性——<html> 只有 data-theme，<nav> 只有
   data-v，**永不匹配** → dark 容器背景永远不生效，TabBar 一直是白底
   （rgba(255,255,255,0.92) 半透明叠加在深色页面背景上呈现奶油色）。
   用户截图反馈"底部导航栏全白的"就是这个 bug。
   修复：把 .mobile-tabbar dark 背景也移到非 scoped 块。 */

/* v65 (2026-06-26) 视觉歧义修复：v64 的 rgba(26,29,35,0.92) 半透明 + backdrop-filter
   blur(16px) 在深色页面背景上视觉上呈现"雾化灰白"——8% 透明区透出深色 + 模糊混合
   + 白色图标叠加 = 看起来像浅色 TabBar。DevTools console.table 6 项全 ✓ 深色，
   但用户截图仍显示白色 → 是 backdrop-filter 视觉错觉，不是 CSS bug。
   修复：改成完全不透明 rgb(26, 29, 35) 消除 8% 透明，dark 模式 TabBar 绝对实心深色，
   不可能再被误解为白色。light 模式保留 0.92 半透明（不影响视觉）。 */
[data-theme="dark"] .mobile-tabbar {
  background: rgb(26, 29, 35);
  border-top-color: var(--color-border-base);
}

/* v67 (2026-06-26) 修复 .nut-tabbar 子元素白色盖住父元素：v66 后 .mobile-tabbar
   (父) 已经是深色 rgb(26,29,35)，但 NutUI 内部的 .nut-tabbar 元素（子）有自己
   的 background: var(--nut-white, #fff) 规则直接设白色，覆盖了 .mobile-tabbar
   的深色背景。NutUI 有 .nut-theme-dark .nut-tabbar 的 dark 模式 fallback（用
   --nut-dark-background），但项目用 [data-theme="dark"] 不是 .nut-theme-dark，
   所以 NutUI 的 dark 规则不生效。
   修复：直接给 .nut-tabbar 加 [data-theme="dark"] 覆盖，背景设 rgb(26,29,35)
   与父元素同步。特异性 (0,2,0) vs NutUI .nut-tabbar (0,1,0) 胜出。
   .nut-tabbar__placeholder 是 NutUI 的 placeholder 元素（TabBar.vue 用了
   placeholder prop），也加覆盖兜底。
   教训：CSS 框架的子组件（NutUI/MUI/Element Plus 等）会用 CSS 变量 + class
   设自己的主题，但它们的 dark class（.nut-theme-dark）通常和我们项目的
   [data-theme="dark"] 不一致——必须为每个有 background 的子组件单独写
   [data-theme="dark"] 覆盖，不能假设"父元素深色子元素就深色"。 */
[data-theme="dark"] .nut-tabbar,
[data-theme="dark"] .nut-tabbar__placeholder {
  background: rgb(26, 29, 35);
  border-top: 1px solid var(--color-border-base);
  border-bottom: 1px solid var(--color-border-base);
}
</style>