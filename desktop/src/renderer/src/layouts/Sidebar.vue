<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import ResearchIcon from '../components/icons/ResearchIcon.vue'
import type { ResearchIconName } from '../components/icons/research-icons'
import { useProjectStore } from '../stores/research/project.store'

interface NavItem {
  label: string
  icon: ResearchIconName
  routeName: string
}

const COLLAPSE_KEY = 'research-sidebar-collapsed'
const NAV_ITEMS: ReadonlyArray<NavItem> = [
  { label: '科研驾驶舱', icon: 'home', routeName: 'research-dashboard' },
  { label: '演示场景', icon: 'sparkles', routeName: 'research-demo' },
  { label: '科研助手', icon: 'assistant', routeName: 'research-assistant' },
  { label: '研究工作区', icon: 'project', routeName: 'research-project' },
  { label: '文献研究', icon: 'literature', routeName: 'research-literature' },
  { label: '实验设计', icon: 'experiment', routeName: 'research-experiment' },
  { label: '数据分析', icon: 'data', routeName: 'research-data-analysis' },
  { label: 'SCI写作', icon: 'manuscript', routeName: 'research-manuscript' },
  { label: '知识图谱', icon: 'graph', routeName: 'research-knowledge-graph' },
  { label: 'AI研究团队', icon: 'agent', routeName: 'research-agent-center' },
  { label: '实验控制中心', icon: 'experiment', routeName: 'research-experiment-control' },
  { label: '系统设置', icon: 'settings', routeName: 'research-settings' }
]

const route = useRoute()
const projectStore = useProjectStore()
const collapsed = ref(localStorage.getItem(COLLAPSE_KEY) === '1')
const activeName = computed(() => typeof route.name === 'string' ? route.name : '')
const projectProgress = computed(() => Math.round(projectStore.currentProject.progress * 100))
const projectStatus = computed(() => {
  const labels = { active: '进行中', planning: '规划中', completed: '已完成', paused: '已暂停' } as const
  return labels[projectStore.currentProject.status]
})

function toggleCollapsed(): void {
  collapsed.value = !collapsed.value
  localStorage.setItem(COLLAPSE_KEY, collapsed.value ? '1' : '0')
}
</script>

<template>
  <aside :class="['sidebar', { 'is-collapsed': collapsed }]" aria-label="科研工作台导航">
    <div class="sidebar__brand">
      <span class="sidebar__brand-mark" aria-hidden="true">
        <ResearchIcon name="sparkles" :size="22" />
      </span>
      <div v-if="!collapsed" class="sidebar__brand-copy">
        <strong>小气科研操作系统</strong>
        <span>智能科研工作台</span>
      </div>
    </div>

    <p v-if="!collapsed" class="sidebar__group-label">科研工作区</p>
    <nav class="sidebar__nav" aria-label="科研模块">
      <RouterLink
        v-for="item in NAV_ITEMS"
        :key="item.routeName"
        :to="{ name: item.routeName }"
        :data-nav="item.routeName"
        :class="['sidebar__link', { 'is-active': activeName === item.routeName }]"
        :aria-label="item.label"
        :aria-current="activeName === item.routeName ? 'page' : undefined"
        :title="item.label"
      >
        <span class="sidebar__link-icon" aria-hidden="true">
          <ResearchIcon :name="item.icon" :size="19" />
        </span>
        <span v-if="!collapsed" class="sidebar__link-label">{{ item.label }}</span>
      </RouterLink>
    </nav>

    <section
      data-testid="current-research"
      :class="['sidebar__research', { 'is-hidden': collapsed }]"
      :aria-hidden="collapsed"
      aria-label="当前研究"
    >
      <template v-if="!collapsed">
        <div class="sidebar__research-heading">
          <ResearchIcon name="project" :size="15" />
          <span>当前研究</span>
        </div>
        <strong class="sidebar__research-name">{{ projectStore.currentProject.name }}</strong>
        <div class="sidebar__research-meta">
          <span>{{ projectStatus }}</span>
          <span>{{ projectProgress }}%</span>
        </div>
        <div
          class="sidebar__progress"
          role="progressbar"
          aria-label="项目进度"
          aria-valuemin="0"
          aria-valuemax="100"
          :aria-valuenow="projectProgress"
        >
          <span :style="{ width: `${projectProgress}%` }" />
        </div>
      </template>
    </section>

    <div class="sidebar__controls">
      <button
        data-testid="sidebar-toggle"
        class="sidebar__toggle"
        type="button"
        :aria-label="collapsed ? '展开导航栏' : '收起导航栏'"
        :title="collapsed ? '展开导航栏' : '收起导航栏'"
        @click="toggleCollapsed"
      >
        <ResearchIcon :name="collapsed ? 'expand' : 'collapse'" :size="18" />
        <span v-if="!collapsed">收起导航栏</span>
      </button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  position: relative;
  display: flex;
  flex-direction: column;
  flex: 0 0 var(--research-sidebar-width);
  width: var(--research-sidebar-width);
  min-width: var(--research-sidebar-width);
  height: 100vh;
  overflow: hidden;
  border-inline-end: 1px solid var(--research-border-subtle);
  background: var(--research-bg-card);
  color: var(--research-text-secondary);
  transition: width var(--research-duration-normal) var(--research-ease-standard), flex-basis var(--research-duration-normal) var(--research-ease-standard), min-width var(--research-duration-normal) var(--research-ease-standard);
}
.sidebar.is-collapsed { flex-basis: var(--research-sidebar-collapsed-width); width: var(--research-sidebar-collapsed-width); min-width: var(--research-sidebar-collapsed-width); }
.sidebar__brand { display: flex; min-height: var(--research-header-height); align-items: center; gap: var(--research-space-3); padding-inline: var(--research-space-4); border-block-end: 1px solid var(--research-divider); }
.sidebar__brand-mark { display: grid; width: 38px; height: 38px; flex: 0 0 38px; place-items: center; border-radius: var(--research-radius-card); background: var(--research-primary-600); color: var(--research-text-inverse); box-shadow: var(--research-shadow-soft); }
.sidebar__brand-copy { min-width: 0; }
.sidebar__brand-copy strong, .sidebar__brand-copy span { display: block; white-space: nowrap; }
.sidebar__brand-copy strong { color: var(--research-text-primary); font-size: var(--research-text-card-title); }
.sidebar__brand-copy span { margin-block-start: var(--research-space-1); color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.sidebar__group-label { margin: var(--research-space-5) var(--research-space-5) var(--research-space-2); color: var(--research-text-secondary); font-size: var(--research-text-xs); font-weight: var(--research-font-weight-semibold); letter-spacing: .08em; }
.sidebar__nav { display: flex; min-height: 0; flex: 1; flex-direction: column; gap: var(--research-space-1); overflow-y: auto; padding: var(--research-space-2); }
.sidebar__link { position: relative; display: flex; min-height: 42px; align-items: center; gap: var(--research-space-3); padding: var(--research-space-2) var(--research-space-3); border-radius: var(--research-radius-button); color: var(--research-text-secondary); font-size: 13px; font-weight: var(--research-font-weight-medium); text-decoration: none; transition: background var(--research-duration-fast) var(--research-ease-standard), color var(--research-duration-fast) var(--research-ease-standard); }
.sidebar__link::before { position: absolute; inset-block: var(--research-space-2); inset-inline-start: calc(var(--research-space-2) * -1); width: 3px; border-radius: 0 var(--research-radius-pill) var(--research-radius-pill) 0; background: transparent; content: ''; }
.sidebar__link:hover { background: var(--research-bg-hover); color: var(--research-text-primary); }
.sidebar__link.is-active { background: var(--research-primary-50); color: var(--research-primary-700); }
.sidebar__link.is-active::before { background: var(--research-primary-600); }
.sidebar__link:focus-visible, .sidebar__toggle:focus-visible { outline: none; box-shadow: var(--research-shadow-focus-primary); }
.sidebar__link-icon { display: grid; width: 22px; flex: 0 0 22px; place-items: center; }
.sidebar__link-label { min-width: 0; white-space: nowrap; }
.is-collapsed .sidebar__link { justify-content: center; padding-inline: var(--research-space-2); }
.sidebar__research { margin: var(--research-space-3); padding: var(--research-space-4); border: 1px solid var(--research-ai-100); border-radius: var(--research-radius-card); background: var(--research-ai-50); transition: opacity var(--research-duration-fast) var(--research-ease-standard); }
.sidebar__research.is-hidden { height: 0; margin: 0; padding: 0; overflow: hidden; border: 0; opacity: 0; }
.sidebar__research-heading { display: flex; align-items: center; gap: var(--research-space-2); color: var(--research-ai-700); font-size: var(--research-text-xs); font-weight: var(--research-font-weight-semibold); }
.sidebar__research-name { display: -webkit-box; margin-block: var(--research-space-2); overflow: hidden; color: var(--research-text-primary); font-size: 13px; line-height: var(--research-line-height-body); -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.sidebar__research-meta { display: flex; justify-content: space-between; color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.sidebar__progress { height: 5px; margin-block-start: var(--research-space-2); overflow: hidden; border-radius: var(--research-radius-pill); background: var(--research-ai-100); }
.sidebar__progress span { display: block; height: 100%; border-radius: inherit; background: var(--research-ai-500); transition: width var(--research-duration-slow) var(--research-ease-emphasized); }
.sidebar__controls { padding: var(--research-space-3); border-block-start: 1px solid var(--research-divider); }
.sidebar__toggle { display: flex; width: 100%; min-height: 38px; align-items: center; justify-content: center; gap: var(--research-space-2); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-button); background: var(--research-bg-panel); color: var(--research-text-secondary); font: inherit; font-size: var(--research-text-sm); cursor: pointer; }
.sidebar__toggle:hover { border-color: var(--research-border-strong); color: var(--research-primary-700); }
@media (prefers-reduced-motion: reduce) { .sidebar, .sidebar__progress span { transition: none; } }
</style>
