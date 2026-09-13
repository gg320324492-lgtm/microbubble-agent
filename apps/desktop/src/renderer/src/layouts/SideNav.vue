<script setup lang="ts">
// 侧边栏 — 六项信息架构（AI 助手 / 实验 ELN / 稿件 / 知识库 / 会议 / 设置），底部当前用户
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

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
  { to: '/app/eln', label: '实验 ELN', icon: 'flask', badge: 'M3' },
  { to: '/app/manuscripts', label: '稿件', icon: 'doc', badge: 'M3' },
  { to: '/app/knowledge', label: '知识库', icon: 'book', badge: 'M2' },
  { to: '/app/meetings', label: '会议', icon: 'calendar', badge: 'M2' },
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
  <nav class="sidenav" aria-label="工作台导航">
    <div class="sidenav-scroll">
      <button
        v-for="item in items"
        :key="item.to"
        class="sidenav-item"
        :class="{ 'is-active': isActive(item) }"
        :aria-current="isActive(item) ? 'page' : undefined"
        @click="router.push(item.to)"
      >
        <span class="sidenav-icon" aria-hidden="true">
          <svg v-if="item.icon === 'chat'" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 12a8 8 0 0 1-8 8H4l2.5-2.5A8 8 0 1 1 21 12Z"/></svg>
          <svg v-else-if="item.icon === 'flask'" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M9 3h6M10 3v6l-5.5 9.2A2 2 0 0 0 6.2 21h11.6a2 2 0 0 0 1.7-2.8L14 9V3"/><path d="M7.5 15h9"/></svg>
          <svg v-else-if="item.icon === 'doc'" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z"/><path d="M14 3v5h5M9 13h6M9 17h4"/></svg>
          <svg v-else-if="item.icon === 'book'" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V4a1 1 0 0 0-1-1H6.5A2.5 2.5 0 0 0 4 5.5v14Z"/><path d="M4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5"/></svg>
          <svg v-else-if="item.icon === 'calendar'" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 10h18"/></svg>
          <svg v-else width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 1.55V21a2 2 0 1 1-4 0v-.09A1.7 1.7 0 0 0 9 19.4a1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.55-1H3a2 2 0 1 1 0-4h.09A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3.05V3a2 2 0 1 1 4 0v.09A1.7 1.7 0 0 0 15 4.6a1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.4 9c.26.6.85 1 1.51 1H21a2 2 0 1 1 0 4h-.09c-.66 0-1.25.4-1.51 1Z"/></svg>
        </span>
        <span class="sidenav-label">{{ item.label }}</span>
        <span v-if="item.badge" class="sidenav-badge">{{ item.badge }}</span>
      </button>
    </div>

    <div class="sidenav-footer">
      <div class="sidenav-user" v-if="auth.user">
        <span class="sidenav-avatar" aria-hidden="true">{{ (auth.user.displayName || auth.user.username).slice(0, 1) }}</span>
        <span class="sidenav-user-meta">
          <span class="sidenav-user-name">{{ auth.user.displayName || auth.user.username }}</span>
          <span class="sidenav-user-role">{{ auth.user.role === 'admin' ? '管理员' : '研究员' }}</span>
        </span>
      </div>
      <button class="sidenav-logout" @click="onLogout">退出登录</button>
    </div>
  </nav>
</template>

<style scoped>
.sidenav {
  display: flex;
  flex-direction: column;
  background: var(--color-bg-card);
  border-right: 1px solid var(--color-border);
  overflow: hidden;
}
.sidenav-scroll {
  flex: 1;
  padding: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;
}
.sidenav-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 9px var(--space-3);
  border: none;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-text-regular);
  font-size: var(--font-size-base);
  cursor: pointer;
  text-align: left;
  transition: background var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out);
}
.sidenav-item:hover {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}
.sidenav-item.is-active {
  background: var(--color-primary-bg);
  color: var(--color-primary);
  font-weight: var(--font-weight-semibold);
}
.sidenav-badge {
  margin-left: auto;
  padding: 1px 7px;
  border-radius: var(--radius-full);
  background: var(--color-bg-secondary);
  color: var(--color-text-secondary);
  font-size: 10px;
  font-weight: var(--font-weight-medium);
}
.sidenav-item.is-active .sidenav-badge {
  background: rgba(var(--color-primary-rgb), 0.15);
  color: var(--color-primary-dark);
}
.sidenav-footer {
  padding: var(--space-3);
  border-top: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.sidenav-user {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2);
  border-radius: var(--radius-md);
  background: var(--color-bg-warm);
}
.sidenav-avatar {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border-radius: var(--radius-md);
  background: var(--gradient-welcome-hero);
  color: #fff;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
}
.sidenav-user-meta {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
  min-width: 0;
}
.sidenav-user-name {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sidenav-user-role {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
.sidenav-logout {
  padding: 6px var(--space-2);
  border: none;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  cursor: pointer;
  text-align: left;
  transition: all var(--duration-fast) var(--ease-out);
}
.sidenav-logout:hover {
  background: var(--color-danger-bg);
  color: var(--color-danger);
}
</style>
