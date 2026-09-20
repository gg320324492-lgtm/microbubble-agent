<script setup lang="ts">
// 窗口控制三键（最小化/最大化还原/关闭）— R-9 A1 抽出为通用组件。
//
// 存在意义：自绘标题栏（frame: false）后，任何**不含 TitleBar 的页面**（登录页/注册页）
// 都会失去窗口控制能力，用户无法最小化或关闭窗口。此前三键逻辑只写在 TitleBar 内，
// auth 页无从复用 —— 本组件是唯一实现，TitleBar 与 auth 页共用，杜绝两份逻辑漂移。
//
// 变体：panel（深色 chrome 底，用于 TitleBar）/ page（浅色页面底，用于 auth 页）。
import { onUnmounted, ref } from 'vue'

const props = withDefaults(defineProps<{ variant?: 'panel' | 'page' }>(), { variant: 'panel' })

const api = window.api
const maximized = ref(false)
const offState = window.api.window.onStateChange((s) => (maximized.value = s))
void window.api.window.isMaximized().then((v) => (maximized.value = v))
onUnmounted(offState)
</script>

<template>
  <div class="wc" :class="`wc--${props.variant}`" data-testid="window-controls">
    <button class="wc-btn" type="button" title="最小化" aria-label="最小化" @click="api.window.minimize()">
      <svg width="11" height="11" viewBox="0 0 12 12" aria-hidden="true"><path d="M1 6h10" stroke="currentColor" stroke-width="1.2" /></svg>
    </button>
    <button
      class="wc-btn"
      type="button"
      :title="maximized ? '还原' : '最大化'"
      :aria-label="maximized ? '还原窗口' : '最大化窗口'"
      @click="api.window.toggleMaximize()"
    >
      <svg v-if="!maximized" width="11" height="11" viewBox="0 0 12 12" aria-hidden="true">
        <rect x="2" y="2" width="8" height="8" fill="none" stroke="currentColor" stroke-width="1.2" />
      </svg>
      <svg v-else width="11" height="11" viewBox="0 0 12 12" aria-hidden="true">
        <rect x="1.5" y="3.5" width="7" height="7" fill="none" stroke="currentColor" stroke-width="1.2" />
        <path d="M3.5 3.5v-2h7v7h-2" fill="none" stroke="currentColor" stroke-width="1.2" />
      </svg>
    </button>
    <button class="wc-btn wc-close" type="button" title="关闭" aria-label="关闭" @click="api.window.close()">
      <svg width="11" height="11" viewBox="0 0 12 12" aria-hidden="true"><path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" stroke-width="1.2" /></svg>
    </button>
  </div>
</template>

<style scoped>
.wc {
  display: flex;
  height: 100%;
  -webkit-app-region: no-drag; /* 按钮区豁免拖拽 */
}
.wc-btn {
  width: 46px;
  height: 100%;
  display: grid;
  place-items: center;
  border: none;
  background: transparent;
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out);
}

/* 深色 chrome（TitleBar） */
.wc--panel .wc-btn {
  color: var(--wb-panel-text-dim);
}
.wc--panel .wc-btn:hover {
  background: rgba(255, 255, 255, 0.14);
  color: var(--wb-panel-text);
}
.wc--panel .wc-btn:active {
  background: rgba(255, 255, 255, 0.22);
}
.wc--panel .wc-close:hover {
  background: #e81123;
  color: #fff;
}

/* 浅色页面（登录/注册页） */
.wc--page .wc-btn {
  color: var(--color-text-secondary);
  border-radius: var(--radius-sm);
}
.wc--page .wc-btn:hover {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}
.wc--page .wc-btn:active {
  background: var(--color-bg-secondary);
}
.wc--page .wc-close:hover {
  background: var(--color-danger);
  color: #fff;
}
</style>
