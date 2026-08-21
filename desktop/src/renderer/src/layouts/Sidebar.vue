<script setup lang="ts">
/**
 * 左侧导航 Sidebar。
 *
 * 职责:
 * - 主导航（占位，Phase 2+ 业务模块填充）
 * - 当前页路由高亮
 * - 折叠/展开（Phase 5+ 增强）
 *
 * Phase 2-Impl-1: 仅 dashboard / tasks / knowledge / meeting 4 个占位链接
 *   真实模块路由 Phase 2 后续批次加入。
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'

interface NavItem {
  name: string
  label: string
  icon: string
  routeName: string
  badge?: 'wip' | 'soon'
}

const NAV_ITEMS: ReadonlyArray<NavItem> = [
  { name: 'dashboard', label: '仪表盘', icon: '🏠', routeName: 'dashboard', badge: 'wip' },
  { name: 'tasks', label: '任务', icon: '📋', routeName: 'tasks', badge: 'soon' },
  { name: 'knowledge', label: '知识库', icon: '📚', routeName: 'knowledge', badge: 'soon' },
  { name: 'meeting', label: '会议', icon: '🎙️', routeName: 'meeting', badge: 'soon' }
]

const route = useRoute()
const activeName = computed(() => (typeof route.name === 'string' ? route.name : ''))
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar__brand">
      <span class="sidebar__brand-icon">🔬</span>
      <span class="sidebar__brand-text">MicroBubble</span>
    </div>

    <nav class="sidebar__nav">
      <RouterLink
        v-for="item in NAV_ITEMS"
        :key="item.name"
        :to="{ name: item.routeName }"
        :class="['sidebar__link', { 'is-active': activeName === item.routeName }]"
      >
        <span class="sidebar__link-icon">{{ item.icon }}</span>
        <span class="sidebar__link-label">{{ item.label }}</span>
        <span v-if="item.badge" :class="['sidebar__link-badge', `sidebar__link-badge--${item.badge}`]">
          {{ item.badge === 'wip' ? '建设中' : '待开工' }}
        </span>
      </RouterLink>
    </nav>

    <div class="sidebar__footer">
      <span class="sidebar__version">v0.1.0</span>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  width: 220px;
  min-width: 220px;
  height: 100vh;
  background: #0f172a;
  border-right: 1px solid #1e293b;
  color: #cbd5e1;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
.sidebar__brand {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 1.2rem 1rem;
  font-size: 1.05rem;
  font-weight: 600;
  color: #f97316;
  border-bottom: 1px solid #1e293b;
}
.sidebar__brand-icon {
  font-size: 1.4rem;
}
.sidebar__brand-text {
  letter-spacing: 0.02em;
}

.sidebar__nav {
  flex: 1;
  padding: 1rem 0.6rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.sidebar__link {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.6rem 0.75rem;
  border-radius: 6px;
  color: #94a3b8;
  text-decoration: none;
  font-size: 0.9rem;
  transition: background 0.12s, color 0.12s;
}
.sidebar__link:hover {
  background: rgba(148, 163, 184, 0.06);
  color: #f1f5f9;
}
.sidebar__link.is-active {
  background: rgba(249, 115, 22, 0.12);
  color: #f97316;
  font-weight: 600;
}
.sidebar__link-icon {
  font-size: 1.05rem;
  width: 1.4rem;
  text-align: center;
}
.sidebar__link-label {
  flex: 1;
}
.sidebar__link-badge {
  font-size: 0.65rem;
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
}
.sidebar__link-badge--wip {
  background: #92400e;
  color: #fde68a;
}
.sidebar__link-badge--soon {
  background: #1e293b;
  color: #64748b;
}

.sidebar__footer {
  padding: 0.8rem 1rem;
  border-top: 1px solid #1e293b;
  font-size: 0.75rem;
  color: #475569;
}
</style>
