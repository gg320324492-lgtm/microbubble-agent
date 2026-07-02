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

    <!-- 铁律 31: 全项目 tab 统一用 <TabStrip> -->
    <div class="tab-strip-wrapper">
      <TabStrip
        v-model="activeTab"
        :items="tabItems"
        :scroll="true"
        aria-label="团队协作视图切换"
        @change="onTabChange"
      />
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

import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Folder, User, Microphone } from '@element-plus/icons-vue'
import TabStrip from '@/components/common/TabStrip.vue'
import PageHeader from '@/components/mobile/PageHeader.vue'
import MobileProjectsPanel from './mobile-workspace/MobileProjectsPanel.vue'
import MobileMembersPanel from './mobile-workspace/MobileMembersPanel.vue'
import MobileVoiceprintsPanel from './mobile-workspace/MobileVoiceprintsPanel.vue'

const route = useRoute()
const router = useRouter()

// 铁律 29: URL ?tab= 同步双向（VALID_TABS 白名单 + watch + replace）
const VALID_TABS = ['projects', 'members', 'voiceprint']
const activeTab = ref(
  route.query.tab && VALID_TABS.includes(String(route.query.tab))
    ? String(route.query.tab)
    : 'projects'
)

// 铁律 30: EP 图标 named import + 通过 props 传入
const tabItems = [
  { key: 'projects',   label: '项目', icon: Folder },
  { key: 'members',    label: '成员', icon: User },
  { key: 'voiceprint', label: '声纹', icon: Microphone },
]

const PANEL_MAP = {
  projects: MobileProjectsPanel,
  members: MobileMembersPanel,
  voiceprint: MobileVoiceprintsPanel,
}
const currentPanel = computed(() => PANEL_MAP[activeTab.value] || MobileProjectsPanel)

// TabStrip emit update:modelValue 已自动改 activeTab, 这里只同步 URL
function onTabChange(name) {
  router.replace({ path: '/workspace', query: { ...route.query, tab: name } })
}

// 铁律 29: tab → URL 同步（兜底, 防止 TabStrip emit 漏掉）
watch(activeTab, (tab) => {
  router.replace({ path: '/workspace', query: { ...route.query, tab } })
})

// 铁律 29: URL → tab 反向同步（浏览器前进/后退）
watch(() => route.query.tab, (t) => {
  if (t && VALID_TABS.includes(String(t)) && String(t) !== activeTab.value) {
    activeTab.value = String(t)
  }
})

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

/* TabStrip 容器（铁律 31: 替代原 .tab-strip 自定义） */
.tab-strip-wrapper {
  padding: 12px 16px;
  background: var(--color-bg-card);
  border-bottom: 1px solid var(--color-border);
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
/* 铁律 26: 旧 .tab-strip / .tab-strip-item 已迁移到 TabStrip, dark 由组件自身处理 */
/* 仅保留 .tab-strip-wrapper 在 dark 下的背景 */
[data-theme="dark"] .tab-strip-wrapper {
  background: var(--color-bg-card);
  border-bottom-color: var(--color-border);
}
</style>