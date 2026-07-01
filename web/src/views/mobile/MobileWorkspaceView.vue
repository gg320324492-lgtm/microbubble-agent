<template>
  <div class="mobile-workspace-view">
    <PageHeader title="团队协作" show-back @back="$router.back()">
      <template #right>
        <button
          v-if="activeTab === 'projects'"
          type="button"
          class="header-action primary"
          aria-label="新建项目"
          title="新建项目"
          @click="onCreateProject"
        >+</button>
        <button
          v-if="activeTab === 'members'"
          type="button"
          class="header-action"
          aria-label="搜索"
          title="搜索"
          @click="onSearchMember"
        >🔍</button>
        <button
          v-if="activeTab === 'members'"
          type="button"
          class="header-action primary"
          aria-label="添加成员"
          title="添加成员"
          @click="onCreateMember"
        >+</button>
      </template>
    </PageHeader>

    <div class="tab-strip">
      <button
        v-for="t in tabs"
        :key="t.name"
        type="button"
        class="tab-strip-item"
        :class="{ active: activeTab === t.name }"
        @click="onTabClick(t.name)"
      >{{ t.label }}</button>
    </div>

    <main
      class="workspace-main"
      :style="{ paddingBottom: 'calc(var(--tabbar-height, 56px) + var(--sab, 0px))' }"
    >
      <keep-alive>
        <component :is="currentPanel" :key="activeTab" />
      </keep-alive>
    </main>
  </div>
</template>

<script setup>
/**
 * MobileWorkspaceView.vue — v78 "团队协作" 移动端容器
 *
 * 设计:
 * - 顶栏: PageHeader (复用) + 动态 right 按钮 (按 tab 切换显示)
 * - tab-strip: 横向滚动条 + 3 tab (项目/成员/声纹)
 * - main: keep-alive 包裹 component, 切 tab 不重渲染
 *
 * 复用 web-minimal / mobile 模式 (PageHeader + CardList + MobileFormSheet + VoiceprintEnrollFlow)
 */

import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeader from '@/components/mobile/PageHeader.vue'
import MobileProjectsPanel from './mobile-workspace/MobileProjectsPanel.vue'
import MobileMembersPanel from './mobile-workspace/MobileMembersPanel.vue'
import MobileVoiceprintsPanel from './mobile-workspace/MobileVoiceprintsPanel.vue'

const route = useRoute()
const router = useRouter()

const VALID_TABS = ['projects', 'members', 'voiceprint']
const tabs = [
  { name: 'projects', label: '项目' },
  { name: 'members', label: '成员' },
  { name: 'voiceprint', label: '声纹' },
]
const activeTab = ref(route.query.tab && VALID_TABS.includes(route.query.tab) ? route.query.tab : 'projects')

const PANEL_MAP = {
  projects: MobileProjectsPanel,
  members: MobileMembersPanel,
  voiceprint: MobileVoiceprintsPanel,
}
const currentPanel = computed(() => PANEL_MAP[activeTab.value] || MobileProjectsPanel)

function onTabClick(name) {
  activeTab.value = name
  router.replace({ path: '/workspace', query: { tab: name } })
}

// header right 按钮代理到对应 panel 的方法
// 各 panel 暴露 :ref 拿不到, 改用全局事件总线模式 (简单 window event)
function onCreateProject() {
  window.dispatchEvent(new CustomEvent('workspace:create-project'))
}
function onSearchMember() {
  window.dispatchEvent(new CustomEvent('workspace:search-member'))
}
function onCreateMember() {
  window.dispatchEvent(new CustomEvent('workspace:create-member'))
}

onMounted(() => {
  // 默认 tab 同步到 URL
  if (!route.query.tab) {
    router.replace({ path: '/workspace', query: { tab: 'projects' } })
  }
})
</script>

<style scoped>
.mobile-workspace-view {
  min-height: 100vh;
  background: var(--color-bg-page);
  display: flex;
  flex-direction: column;
}

.tab-strip {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  background: var(--color-bg-card);
  border-bottom: 1px solid var(--color-border);
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.tab-strip::-webkit-scrollbar { display: none; }

.tab-strip-item {
  flex-shrink: 0;
  padding: 8px 16px;
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  font-size: 14px;
  color: var(--color-text-regular);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: all var(--transition-all-fast) var(--ease-out);
}

.tab-strip-item.active {
  background: var(--color-primary);
  /* stylelint-disable-next-line color-named */
  color: white;
  border-color: var(--color-primary);
}

.workspace-main {
  flex: 1;
  padding: 12px 0;
}

.header-action {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 18px;
  color: var(--color-text-regular);
  cursor: pointer;
  margin-left: 4px;
  -webkit-tap-highlight-color: transparent;
}
.header-action:active { background: var(--color-primary-bg); }
.header-action.primary {
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
  /* stylelint-disable-next-line color-named */
  color: white;
  font-weight: 600;
  font-size: 22px;
}
</style>

<!-- v60-v67 教训: dark mode 跨组件覆盖必须非 scoped 块 -->
<style>
[data-theme="dark"] .tab-strip {
  background: var(--color-bg-card);
  border-bottom-color: var(--color-border);
}
[data-theme="dark"] .tab-strip-item {
  background: transparent;
  border-color: var(--color-border);
  color: var(--color-text-regular);
}
[data-theme="dark"] .tab-strip-item.active {
  background: var(--color-primary);
  border-color: var(--color-primary);
}
</style>