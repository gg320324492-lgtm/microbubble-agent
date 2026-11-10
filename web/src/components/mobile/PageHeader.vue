<template>
  <header class="mobile-page-header mg-page-header" :style="headerStyle">
    <div class="header-inner" :style="innerStyle">
      <!-- 左侧：返回按钮（slot 也可覆盖） -->
      <div class="header-left">
        <slot name="left">
          <button
            v-if="showBack"
            type="button"
            class="header-back"
            :aria-label="'返回'"
            :title="'返回'"
            @click="onBack"
          >
            <span class="back-icon">‹</span>
          </button>
        </slot>
      </div>

      <!-- 中间：标题 -->
      <div class="header-center">
        <slot>
          <h1 class="header-title">{{ title }}</h1>
        </slot>
      </div>

      <!-- 右侧：操作按钮 -->
      <div class="header-right">
        <slot name="right" />
      </div>
    </div>
  </header>
</template>

<script setup>
/**
 * PageHeader.vue — 移动端页面顶部（极简 header）
 *
 * PR #2: 统一 14 个移动端页面的 header 模式
 * - 左侧：返回按钮（默认）或自定义 slot
 * - 中间：标题或自定义 slot
 * - 右侧：操作按钮 slot（可放多个按钮）
 *
 * 用法：
 *   <PageHeader title="任务管理" show-back @back="router.back()" />
 *   <PageHeader title="知识库">
 *     <template #right>
 *       <button @click="onSearch">🔍</button>
 *       <button @click="onAdd">+</button>
 *     </template>
 *   </PageHeader>
 */

import { computed, getCurrentInstance } from 'vue'

const props = defineProps({
  title: { type: String, default: '' },
  showBack: { type: Boolean, default: false },
  /** 应用 safe-area 顶部 padding */
  safeAreaTop: { type: Boolean, default: true },
})

const emit = defineEmits(['back'])
const instance = getCurrentInstance()

const headerStyle = computed(() => ({
  paddingTop: props.safeAreaTop ? 'var(--sat)' : '0',
}))

const innerStyle = computed(() => ({
  height: 'var(--header-mobile-height, 52px)',
}))

function onBack() {
  // 2026-11-10 修复: 组件**自己** history.back() 的同时, 大量调用方也在
  // `@back` 里 router.back() ⇒ 一次点击连退两级 (详情页直接回主界面)。
  // 正确规则: 有监听方 ⇒ 完全交给监听方; 没有监听方才走默认 history.back()。
  // 这是"返回按钮"的唯一权威实现, 别在调用方再写第二份 (类 20.250 ①)。
  emit('back')
  // ⚠️ 不能用 useAttrs(): defineEmits 声明过的监听器会被 Vue 从 attrs 剔除,
  //    attrs.onBack 恒为 undefined ⇒ 会把双重返回修成"永远返回两次"。
  //    唯一可靠判据是 vnode.props 上有没有 onBack 监听器。
  const hasListener = typeof instance?.vnode?.props?.onBack === 'function'
  if (!hasListener && window.history.length > 1) {
    window.history.back()
  }
}
</script>

<style scoped>
.mobile-page-header {
  position: sticky;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  /* 2026-08-31 液态毛玻璃: 玻璃配方由 .mg-page-header 提供 (mobile-glass.css) */
}

.header-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--mobile-padding-x, 16px);
  gap: 12px;
  min-height: var(--header-mobile-height, 52px);
}

.header-left,
.header-right {
  flex: 0 0 auto;
  min-width: 44px; /* 触觉目标 */
  display: flex;
  align-items: center;
  gap: 4px;
}

.header-center {
  flex: 1 1 auto;
  min-width: 0;
  text-align: center;
}

.header-title {
  font-size: var(--font-size-md, 15px);
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary);
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.header-back {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: transparent;
  border: none;
  color: var(--color-text-regular);
  cursor: pointer;
  transition: background-color var(--duration-fast, 150ms);
  -webkit-tap-highlight-color: transparent;
}

.header-back:active {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.back-icon {
  font-size: 28px;
  line-height: 1;
  font-weight: 300;
  margin-top: -3px;
}
</style>

<!-- v77 P2.6-B: dark mode 适配（v60-v67 教训：必须非 scoped） -->
<style>
/* .glass 工具类在 dark 模式自动适配，但 header-bottom-border 与 hairline 需明确 */
[data-theme="dark"] .mobile-page-header {
  border-bottom: 1px solid var(--color-border-light);
}
[data-theme="dark"] .header-back:active {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}
</style>