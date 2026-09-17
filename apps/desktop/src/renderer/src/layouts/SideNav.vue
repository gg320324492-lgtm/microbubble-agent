<script setup lang="ts">
// 模块导航栏 — 收窄为图标竖栏（agent 工作台三栏的最左列），悬停 tooltip，底部用户头像
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import logoUrl from '../assets/logo.png'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

interface NavItem {
  to: string
  label: string
  icon: string
  badge?: string
}

const items: NavItem[] = [
  { to: '/app/assistant', label: 'AI 助手', icon: 'chat' },
  { to: '/app/eln', label: '实验 ELN', icon: 'flask' },
  { to: '/app/manuscripts', label: '稿件', icon: 'doc' },
  { to: '/app/knowledge', label: '知识库', icon: 'book' },
  { to: '/app/meetings', label: '会议', icon: 'calendar' },
  { to: '/app/settings', label: '设置', icon: 'gear' }
]

function isActive(item: NavItem): boolean {
  return route.path === item.to
}

async function onLogout(): Promise<void> {
  await auth.logout()
  void router.push({ name: 'login' })
}
</script>

<template>
  <nav class="rail" aria-label="工作台导航">
    <img class="rail-logo" :src="logoUrl" alt="微纳米气泡课题组" title="微纳米气泡课题组" />
    <div class="rail-items">
      <button
        v-for="item in items"
        :key="item.to"
        class="rail-item"
        :class="{ 'is-active': isActive(item) }"
        :title="item.label + (item.badge ? `（${item.badge}）` : '')"
        :aria-label="item.label"
        :aria-current="isActive(item) ? 'page' : undefined"
        @click="router.push(item.to)"
      >
        <svg v-if="item.icon === 'chat'" width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 12a8 8 0 0 1-8 8H4l2.5-2.5A8 8 0 1 1 21 12Z"/></svg>
        <svg v-else-if="item.icon === 'flask'" width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M9 3h6M10 3v6l-5.5 9.2A2 2 0 0 0 6.2 21h11.6a2 2 0 0 0 1.7-2.8L14 9V3"/><path d="M7.5 15h9"/></svg>
        <svg v-else-if="item.icon === 'doc'" width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z"/><path d="M14 3v5h5M9 13h6M9 17h4"/></svg>
        <svg v-else-if="item.icon === 'book'" width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V4a1 1 0 0 0-1-1H6.5A2.5 2.5 0 0 0 4 5.5v14Z"/><path d="M4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5"/></svg>
        <svg v-else-if="item.icon === 'calendar'" width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 10h18"/></svg>
        <svg v-else width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 1.55V21a2 2 0 1 1-4 0v-.09A1.7 1.7 0 0 0 9 19.4a1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.55-1H3a2 2 0 1 1 0-4h.09A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3.05V3a2 2 0 1 1 4 0v.09A1.7 1.7 0 0 0 15 4.6a1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.4 9c.26.6.85 1 1.51 1H21a2 2 0 1 1 0 4h-.09c-.66 0-1.25.4-1.51 1Z"/></svg>
        <span v-if="item.badge" class="rail-badge">{{ item.badge }}</span>
      </button>
    </div>
    <div class="rail-footer">
      <button
        v-if="auth.user"
        class="rail-avatar"
        :title="`${auth.user.displayName || auth.user.username} · 退出登录`"
        :aria-label="'账号菜单：' + (auth.user.displayName || auth.user.username)"
        @click="onLogout"
      >
        {{ (auth.user.displayName || auth.user.username).slice(0, 1) }}
      </button>
    </div>
  </nav>
</template>

<style scoped>
.rail {
  width: 56px;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 10px 0;
  gap: var(--space-2);
  background: var(--wb-panel-950);
}
.rail-logo {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-full);
  background: #fff;
  flex-shrink: 0;
}
.rail-items {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: var(--space-2);
  overflow-y: auto;
}
.rail-item {
  position: relative;
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border: none;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--wb-panel-text-dim);
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out);
}
.rail-item:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--wb-panel-text);
}
.rail-item.is-active {
  background: var(--color-primary);
  color: #fff;
}
.rail-badge {
  position: absolute;
  top: 2px;
  right: 2px;
  padding: 0 4px;
  border-radius: var(--radius-full);
  background: var(--color-bg-secondary);
  color: var(--color-text-secondary);
  font-size: 9px;
  line-height: 13px;
}
.rail-item.is-active .rail-badge {
  background: rgba(255, 255, 255, 0.25);
  color: #fff;
}
.rail-footer {
  padding-top: var(--space-2);
}
.rail-avatar {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border: none;
  border-radius: var(--radius-full);
  background: var(--gradient-welcome-hero);
  color: #fff;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  cursor: pointer;
}
</style>
