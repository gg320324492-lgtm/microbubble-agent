<script setup lang="ts">
// 自绘标题栏 — 整条可拖拽，右侧窗口控制按钮；双击最大化
import { APP_NAME } from '@shared/constants'
import { useAuthStore } from '../stores/auth'
import logoUrl from '../assets/logo.png'

const auth = useAuthStore()
const api = window.api // 模板作用域内不可直接访问 window，桥接引用
</script>

<template>
  <header class="titlebar" @dblclick="api.window.toggleMaximize()">
    <div class="titlebar-brand">
      <img class="titlebar-logo" :src="logoUrl" alt="微纳米气泡课题组" />
      <span class="titlebar-name">{{ APP_NAME }}</span>
      <span v-if="auth.user" class="titlebar-user">· {{ auth.user.displayName || auth.user.username }}</span>
    </div>
    <div class="titlebar-controls">
      <button class="titlebar-btn" title="最小化" aria-label="最小化" @click="api.window.minimize()">
        <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><path d="M1 6h10" stroke="currentColor" stroke-width="1.2" /></svg>
      </button>
      <button class="titlebar-btn" title="最大化 / 还原" aria-label="最大化或还原" @click="api.window.toggleMaximize()">
        <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><rect x="2" y="2" width="8" height="8" fill="none" stroke="currentColor" stroke-width="1.2" /></svg>
      </button>
      <button class="titlebar-btn titlebar-close" title="关闭" aria-label="关闭" @click="api.window.close()">
        <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" stroke-width="1.2" /></svg>
      </button>
    </div>
  </header>
</template>

<style scoped>
.titlebar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-left: var(--space-4);
  background: var(--wb-panel-950);
  -webkit-app-region: drag; /* 整条拖拽区 */
}
.titlebar-brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--wb-panel-text);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
}
.titlebar-logo {
  width: 20px;
  height: 20px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
}
.titlebar-user {
  color: var(--wb-panel-text-dim);
  font-weight: var(--font-weight-normal);
}
.titlebar-controls {
  display: flex;
  height: 100%;
  -webkit-app-region: no-drag; /* 按钮区豁免拖拽 */
}
.titlebar-btn {
  width: 46px;
  height: 100%;
  display: grid;
  place-items: center;
  border: none;
  background: transparent;
  color: var(--wb-panel-text-dim);
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out);
}
.titlebar-btn:hover {
  background: rgba(255, 255, 255, 0.12);
  color: var(--wb-panel-text);
}
.titlebar-close:hover {
  background: #e81123;
  color: #fff;
}
</style>
