<script setup lang="ts">
/**
 * 科研操作系统侧边导航栏。
 * 10 个模块，全部中文标签。
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'

interface NavItem {
  name: string
  label: string
  icon: string
  routeName: string
}

const NAV_ITEMS: ReadonlyArray<NavItem> = [
  { name: 'assistant',       label: '科研助手',     icon: '💬', routeName: 'research-assistant' },
  { name: 'dashboard',       label: '项目空间',     icon: '📁', routeName: 'research-dashboard' },
  { name: 'literature',      label: '文献智能库',   icon: '📚', routeName: 'research-literature' },
  { name: 'experiment',      label: '实验设计',     icon: '🧪', routeName: 'research-experiment' },
  { name: 'data-analysis',   label: '数据分析',     icon: '📊', routeName: 'research-data-analysis' },
  { name: 'manuscript',      label: '论文助手',     icon: '📝', routeName: 'research-manuscript' },
  { name: 'knowledge-graph', label: '知识图谱',     icon: '🔗', routeName: 'research-knowledge-graph' },
  { name: 'agent-center',    label: '智能体中心',   icon: '🤖', routeName: 'research-agent-center' },
  { name: 'settings',        label: '系统设置',     icon: '⚙️', routeName: 'research-settings' },
]

const route = useRoute()
const activeName = computed(() => (typeof route.name === 'string' ? route.name : ''))
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar__brand">
      <span class="sidebar__brand-icon">🔬</span>
      <div class="sidebar__brand-text">
        <span class="sidebar__brand-name">MicroBubble</span>
        <span class="sidebar__brand-sub">Research OS</span>
      </div>
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
      </RouterLink>
    </nav>

    <div class="sidebar__footer">
      <div class="sidebar__user">
        <div class="sidebar__avatar">王</div>
        <span class="sidebar__username">王天志</span>
      </div>
      <span class="sidebar__version">v1.0.0</span>
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
  gap: 10px;
  padding: 18px 16px 14px;
  border-bottom: 1px solid #1e293b;
}
.sidebar__brand-icon { font-size: 22px; }
.sidebar__brand-name { font-size: 15px; font-weight: 700; color: #f97316; display: block; }
.sidebar__brand-sub { font-size: 10px; color: #64748b; letter-spacing: .05em; text-transform: uppercase; }

.sidebar__nav {
  flex: 1;
  padding: 10px 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;
}
.sidebar__link {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 8px;
  color: #94a3b8;
  text-decoration: none;
  font-size: 13px;
  transition: background .12s, color .12s;
}
.sidebar__link:hover {
  background: rgba(148, 163, 184, 0.08);
  color: #e2e8f0;
}
.sidebar__link.is-active {
  background: rgba(249, 115, 22, 0.14);
  color: #f97316;
  font-weight: 600;
}
.sidebar__link-icon { font-size: 15px; width: 20px; text-align: center; flex-shrink: 0; }
.sidebar__link-label { flex: 1; }

.sidebar__footer {
  padding: 12px 16px;
  border-top: 1px solid #1e293b;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.sidebar__user { display: flex; align-items: center; gap: 8px; }
.sidebar__avatar {
  width: 28px; height: 28px; border-radius: 50%;
  background: linear-gradient(135deg, #f97316, #fbbf24);
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700; color: #fff;
}
.sidebar__username { font-size: 12px; color: #94a3b8; }
.sidebar__version { font-size: 10px; color: #475569; }
</style>
