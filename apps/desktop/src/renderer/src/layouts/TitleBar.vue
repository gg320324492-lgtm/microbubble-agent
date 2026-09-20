<script setup lang="ts">
// 自绘标题栏 — 拖拽区 + 三键（三键实现已抽出为通用 WindowControls，R-9 A1）
import { APP_NAME } from '@shared/constants'
import { useAuthStore } from '../stores/auth'
import WindowControls from '../components/WindowControls.vue'
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
    <WindowControls variant="panel" />
  </header>
</template>

<style scoped>
.titlebar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-left: var(--space-3);
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
</style>
