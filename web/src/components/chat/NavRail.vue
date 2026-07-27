<!--
NavRail.vue — W72 B-1 子 plan ③ 起步核心组件 (派工 v8 段 8 实战)
依据: docs/w72-final-decision-2026-07-24.md §3
- desktop >= 768px 固定左侧，mobile < 768px 抽屉式
- /chat /knowledge /drive /tasks /meetings /workspace 六类路由
- orange/ocean/forest × light/dark 全部走设计 token
- useUiStore 持久化折叠偏好；当前路由高亮与键盘可访问
-->
<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  ChatDotRound, Collection, FolderOpened, List, Microphone, DataBoard,
  Fold, Expand, Close,
} from '@element-plus/icons-vue'
import { useUiStore } from '@/stores/useUiStore'

interface NavItem {
  path: string
  label: string
  icon: typeof ChatDotRound
}

interface Props { mobileOpen?: boolean }

const props = withDefaults(defineProps<Props>(), { mobileOpen: false })
const emit = defineEmits<{
  (event: 'update:mobileOpen', value: boolean): void
}>()
const route = useRoute()
const uiStore = useUiStore()
const collapsed = computed<boolean>(() => uiStore.navRailCollapsed)

const items: NavItem[] = [
  { path: '/chat', label: '对话', icon: ChatDotRound },
  { path: '/knowledge', label: '知识库', icon: Collection },
  { path: '/drive', label: '网盘', icon: FolderOpened },
  { path: '/tasks', label: '任务', icon: List },
  { path: '/meetings', label: '会议', icon: Microphone },
  { path: '/workspace', label: '项目', icon: DataBoard },
]

function isActive(path: string): boolean {
  return route.path === path || route.path.startsWith(`${path}/`)
}
function closeMobile(): void { emit('update:mobileOpen', false) }
</script>

<template>
  <nav
    class="nav-rail"
    :class="{ collapsed, 'mobile-open': props.mobileOpen }"
    aria-label="主导航"
    data-testid="nav-rail"
  >
    <div class="nav-rail-brand">
      <span class="brand-icon" aria-hidden="true">MNB</span>
      <span v-if="!collapsed" class="brand-text">微纳米气泡</span>
      <button
        class="mobile-close" type="button" aria-label="关闭导航" title="关闭导航"
        @click="closeMobile"
      >
        <el-icon><Close /></el-icon>
      </button>
    </div>

    <ul class="nav-rail-items">
      <li
        v-for="item in items" :key="item.path" class="nav-rail-item"
        :class="{ active: isActive(item.path) }"
      >
        <router-link
          :to="item.path"
          :aria-label="item.label"
          :title="collapsed ? item.label : undefined"
          :aria-current="isActive(item.path) ? 'page' : undefined"
          :data-route="item.path"
          @click="closeMobile"
        >
          <span class="nav-icon" aria-hidden="true">
            <el-icon><component :is="item.icon" /></el-icon>
          </span>
          <span v-if="!collapsed" class="nav-label">{{ item.label }}</span>
          <span v-if="!collapsed && isActive(item.path)" class="active-mark" aria-hidden="true" />
        </router-link>
      </li>
    </ul>

    <button
      class="collapse-btn" type="button"
      :aria-label="collapsed ? '展开导航' : '折叠导航'"
      :title="collapsed ? '展开导航' : '折叠导航'"
      @click="uiStore.toggleNavRail()"
    >
      <el-icon><component :is="collapsed ? Expand : Fold" /></el-icon>
      <span v-if="!collapsed">收起导航</span>
    </button>
  </nav>
  <button
    v-if="props.mobileOpen" class="nav-rail-scrim" type="button"
    aria-label="关闭导航" @click="closeMobile"
  />
</template>

<style scoped>
.nav-rail {
  --nav-rail-width: 200px;
  position: relative; z-index: 30;
  display: flex; flex: 0 0 var(--nav-rail-width); flex-direction: column;
  width: var(--nav-rail-width); min-height: 100vh; padding: 14px 10px 12px;
  overflow: hidden; color: var(--color-text-primary); background: var(--color-bg-card);
  border-right: 1px solid var(--color-border-light);
  box-shadow: 8px 0 24px color-mix(in srgb, var(--color-primary) 5%, transparent);
  transition: width var(--duration-slow, 300ms) ease,
    flex-basis var(--duration-slow, 300ms) ease,
    transform var(--duration-slow, 300ms) ease;
}
.nav-rail.collapsed { --nav-rail-width: 60px; padding-inline: 6px; }
.nav-rail-brand {
  display: flex; align-items: center; min-height: 42px; padding: 2px 5px 14px;
  border-bottom: 1px solid var(--color-border-light);
}
.brand-icon {
  display: grid; flex: 0 0 38px; width: 38px; height: 38px; place-items: center;
  color: var(--el-color-white, #fff); background: var(--color-primary);
  border-radius: 11px 11px 11px 3px; box-shadow: var(--shadow-primary);
  font: 800 11px ui-monospace, "SFMono-Regular", Consolas, monospace;
  letter-spacing: -0.04em;
}
.brand-text {
  margin-left: 10px; overflow: hidden; font-size: 14px; font-weight: 700;
  letter-spacing: 0.08em; white-space: nowrap;
}
.mobile-close { display: none; }
.nav-rail-items {
  display: flex; flex: 1; flex-direction: column; gap: 5px;
  margin: 16px 0; padding: 0; list-style: none;
}
.nav-rail-item a,
.collapse-btn {
  display: flex; align-items: center; width: 100%; min-height: 44px;
  color: var(--color-text-secondary); background: transparent; border: 0;
  border-radius: var(--radius-lg); cursor: pointer; text-decoration: none;
  transition: color var(--duration-fast, 150ms) ease,
    background var(--duration-fast, 150ms) ease,
    transform var(--duration-fast, 150ms) ease;
}
.nav-rail-item a { position: relative; padding: 0 10px; }
.nav-rail.collapsed .nav-rail-item a { justify-content: center; padding-inline: 0; }
.nav-rail-item a:hover,
.collapse-btn:hover { color: var(--color-text-primary); background: var(--color-bg-hover); }
.nav-rail-item a:focus-visible,
.collapse-btn:focus-visible,
.mobile-close:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; }
.nav-rail-item.active a {
  color: var(--color-primary); background: var(--color-primary-bg); font-weight: 650;
}
.nav-icon {
  display: grid; flex: 0 0 24px; width: 24px; place-items: center; font-size: 19px;
}
.nav-label { margin-left: 11px; overflow: hidden; font-size: 13px; white-space: nowrap; }
.active-mark {
  position: absolute; right: 9px; width: 5px; height: 5px;
  background: var(--color-primary); border-radius: 50%;
  box-shadow: 0 0 0 4px var(--color-primary-bg);
}
.collapse-btn {
  justify-content: flex-start; gap: 10px; padding: 0 12px;
  font: inherit; font-size: 12px; white-space: nowrap;
}
.nav-rail.collapsed .collapse-btn { justify-content: center; padding-inline: 0; }
.nav-rail-scrim { display: none; }

@media (max-width: 767px) {
  .nav-rail {
    --nav-rail-width: min(82vw, 280px);
    position: fixed; inset: 0 auto 0 0; z-index: 1001;
    width: var(--nav-rail-width); transform: translateX(-105%); box-shadow: var(--shadow-lg);
  }
  .nav-rail.collapsed { --nav-rail-width: min(82vw, 280px); padding-inline: 10px; }
  .nav-rail.mobile-open { transform: translateX(0); }
  .nav-rail.collapsed .nav-rail-item a,
  .nav-rail.collapsed .collapse-btn { justify-content: flex-start; padding-inline: 10px; }
  .nav-rail.collapsed .nav-label,
  .nav-rail.collapsed .brand-text { display: initial; }
  .collapse-btn { display: none; }
  .mobile-close {
    display: grid; width: 36px; height: 36px; margin-left: auto; place-items: center;
    color: var(--color-text-secondary); background: transparent; border: 0;
    border-radius: var(--radius-md);
  }
  .nav-rail-scrim {
    position: fixed; inset: 0; z-index: 1000; display: block; padding: 0;
    background: rgba(18, 24, 32, 0.46); border: 0; backdrop-filter: blur(2px);
  }
}
@media (prefers-reduced-motion: reduce) {
  .nav-rail, .nav-rail-item a, .collapse-btn { transition: none; }
}
</style>

<!-- 6 主题 (orange/ocean/forest × light/dark) 由非 scoped token 边界统一透传 -->
<style>
[data-theme="dark"] .nav-rail {
  background: var(--color-bg-card); border-right-color: var(--color-border-light);
  box-shadow: 8px 0 28px rgba(0, 0, 0, 0.22);
}
[data-theme="dark"] .nav-rail-item a:hover,
[data-theme="dark"] .nav-rail .collapse-btn:hover { background: var(--color-bg-hover); }
[data-theme="dark"] .nav-rail-item.active a {
  color: var(--color-primary); background: var(--color-primary-bg);
}
</style>
