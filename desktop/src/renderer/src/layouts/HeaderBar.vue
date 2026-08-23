<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ResearchIcon from '../components/icons/ResearchIcon.vue'
import { useAuthStore } from '../stores/auth'
import { useProjectStore } from '../stores/research/project.store'
import { useWorkflowStore } from '../stores/research/workflow.store'
import { useUserStore } from '../stores/user'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const projectStore = useProjectStore()
const workflowStore = useWorkflowStore()
const userStore = useUserStore()
const userMenuOpen = ref(false)
const notificationOpen = ref(false)
const userRegion = ref<HTMLElement | null>(null)
const userMenuTrigger = ref<HTMLButtonElement | null>(null)
const userMenu = ref<HTMLElement | null>(null)
const logoutButton = ref<HTMLButtonElement | null>(null)
const notificationRegion = ref<HTMLElement | null>(null)
const notificationTrigger = ref<HTMLButtonElement | null>(null)

const pageTitle = computed(() => {
  const meta = route.meta as { title?: string }
  return meta.title ?? '科研工作台'
})
const displayName = computed(() => userStore.profile?.name ?? '未登录')
const avatarUrl = computed(() => userStore.profile?.avatar ?? '')
const aiStatus = computed(() => {
  if (workflowStore.errors.length > 0) {
    return { tone: 'error', label: `${workflowStore.errors.length} 项异常`, icon: 'error' as const }
  }
  if (workflowStore.runningTasks.length > 0) {
    return { tone: 'running', label: `${workflowStore.runningTasks.length} 项任务运行中`, icon: 'running' as const }
  }
  return { tone: 'ready', label: 'AI 已就绪', icon: 'check' as const }
})

async function toggleUserMenu(): Promise<void> {
  userMenuOpen.value = !userMenuOpen.value
  if (userMenuOpen.value) {
    await nextTick()
    logoutButton.value?.focus()
  }
}

async function closeUserMenu(restoreFocus = false): Promise<void> {
  if (!userMenuOpen.value) return
  userMenuOpen.value = false
  if (restoreFocus) {
    await nextTick()
    userMenuTrigger.value?.focus()
  }
}

function onUserMenuKeydown(event: KeyboardEvent): void {
  if (!['ArrowDown', 'ArrowUp', 'Home', 'End', 'Escape'].includes(event.key)) return
  event.preventDefault()
  if (event.key === 'Escape') {
    void closeUserMenu(true)
    return
  }
  logoutButton.value?.focus()
}

function toggleNotification(): void {
  notificationOpen.value = !notificationOpen.value
}

async function closeNotification(restoreFocus = false): Promise<void> {
  if (!notificationOpen.value) return
  notificationOpen.value = false
  if (restoreFocus) {
    await nextTick()
    notificationTrigger.value?.focus()
  }
}

function onDocumentPointerDown(event: PointerEvent): void {
  const target = event.target
  if (!(target instanceof Node)) return
  if (userMenuOpen.value && !userRegion.value?.contains(target)) void closeUserMenu()
  if (notificationOpen.value && !notificationRegion.value?.contains(target)) void closeNotification()
}

onMounted(() => document.addEventListener('pointerdown', onDocumentPointerDown))
onBeforeUnmount(() => document.removeEventListener('pointerdown', onDocumentPointerDown))

async function onLogout(): Promise<void> {
  await closeUserMenu()
  await authStore.logout()
  await router.push({ name: 'login' })
}
</script>

<template>
  <header class="header-bar">
    <div class="header-bar__context" data-testid="header-context">
      <span class="header-bar__eyebrow">科研工作台</span>
      <h2 class="header-bar__title">{{ pageTitle }}</h2>
    </div>

    <div class="header-bar__right">
      <div class="header-bar__project" data-testid="header-project" title="当前项目">
        <ResearchIcon name="project" :size="17" />
        <div>
          <span>当前项目</span>
          <strong>{{ projectStore.currentProject.name }}</strong>
        </div>
      </div>

      <div
        data-testid="header-ai-status"
        :class="['header-bar__ai', `is-${aiStatus.tone}`]"
        role="status"
        aria-live="polite"
      >
        <ResearchIcon :name="aiStatus.icon" :size="16" />
        <span>{{ aiStatus.label }}</span>
      </div>

      <div ref="notificationRegion" class="header-bar__notification">
        <button
          ref="notificationTrigger"
          data-testid="notification-button"
          class="header-bar__icon-button"
          type="button"
          aria-label="查看科研通知"
          title="查看科研通知"
          aria-controls="research-notification-popover"
          :aria-expanded="notificationOpen"
          @click="toggleNotification"
          @keydown.esc.stop="closeNotification(true)"
        >
          <ResearchIcon name="notification" :size="19" />
        </button>
        <section
          v-if="notificationOpen"
          id="research-notification-popover"
          class="header-bar__notification-popover"
          role="status"
          aria-label="科研通知"
          aria-live="polite"
          tabindex="-1"
          @keydown.esc.stop="closeNotification(true)"
        >
          <div>
            <strong>科研通知</strong>
            <button
              data-testid="notification-close"
              type="button"
              aria-label="关闭科研通知"
              @click="closeNotification(true)"
            >
              <ResearchIcon name="error" :size="15" />
            </button>
          </div>
          <ResearchIcon name="notification" :size="22" />
          <p>暂无科研通知</p>
        </section>
      </div>

      <div v-if="authStore.isAuthenticated" ref="userRegion" class="header-bar__user">
        <button
          ref="userMenuTrigger"
          data-testid="user-menu-button"
          class="header-bar__user-button"
          type="button"
          aria-label="打开用户菜单"
          :aria-expanded="userMenuOpen"
          aria-controls="research-user-menu"
          aria-haspopup="menu"
          @click="toggleUserMenu"
          @keydown.esc.stop="closeUserMenu(true)"
        >
          <span class="header-bar__avatar" aria-hidden="true">
            <img v-if="avatarUrl" :src="avatarUrl" alt="" />
            <span v-else>{{ displayName.charAt(0) }}</span>
          </span>
          <span class="header-bar__user-name">{{ displayName }}</span>
          <ResearchIcon name="expand" :size="14" />
        </button>
        <div
          v-if="userMenuOpen"
          id="research-user-menu"
          ref="userMenu"
          class="header-bar__menu"
          role="menu"
          tabindex="-1"
          @keydown="onUserMenuKeydown"
        >
          <div class="header-bar__menu-profile">
            <strong>{{ displayName }}</strong>
            <span>{{ userStore.profile?.research_area ?? '未设置研究方向' }}</span>
          </div>
          <button ref="logoutButton" data-testid="logout-button" type="button" role="menuitem" tabindex="0" @click="onLogout">
            <ResearchIcon name="expand" :size="15" />
            退出登录
          </button>
        </div>
      </div>
    </div>
  </header>
</template>

<style scoped>
.header-bar { position: relative; z-index: var(--research-z-header); display: flex; height: var(--research-header-height); flex: 0 0 var(--research-header-height); align-items: center; justify-content: space-between; gap: var(--research-space-5); padding-inline: var(--research-space-6); border-block-end: 1px solid var(--research-border-subtle); background: var(--research-bg-card); box-shadow: var(--research-shadow-inset); }
.header-bar__context { min-width: 0; }
.header-bar__eyebrow { display: block; margin-block-end: var(--research-space-1); color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.header-bar__title { margin: 0; color: var(--research-text-primary); font-size: var(--research-text-section-title); font-weight: var(--research-font-weight-semibold); line-height: var(--research-line-height-tight); }
.header-bar__right { display: flex; min-width: 0; align-items: center; gap: var(--research-space-3); }
.header-bar__project { display: flex; max-width: 290px; min-width: 0; align-items: center; gap: var(--research-space-2); padding-inline-end: var(--research-space-4); border-inline-end: 1px solid var(--research-divider); color: var(--research-primary-600); }
.header-bar__project div { min-width: 0; }
.header-bar__project span, .header-bar__project strong { display: block; }
.header-bar__project span { color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.header-bar__project strong { overflow: hidden; color: var(--research-text-primary); font-size: var(--research-text-sm); font-weight: var(--research-font-weight-semibold); text-overflow: ellipsis; white-space: nowrap; }
.header-bar__ai { display: inline-flex; align-items: center; gap: var(--research-space-2); padding: var(--research-space-2) var(--research-space-3); border: 1px solid var(--research-success-100); border-radius: var(--research-radius-pill); background: var(--research-success-50); color: var(--research-success-700); font-size: var(--research-text-sm); font-weight: var(--research-font-weight-medium); white-space: nowrap; }
.header-bar__ai.is-running { border-color: var(--research-ai-100); background: var(--research-ai-50); color: var(--research-ai-700); }
.header-bar__ai.is-error { border-color: var(--research-danger-100); background: var(--research-danger-50); color: var(--research-danger-600); }
.header-bar__icon-button, .header-bar__user-button, .header-bar__menu button, .header-bar__notification-popover button { border: 0; font: inherit; cursor: pointer; }
.header-bar__icon-button { display: grid; width: 38px; height: 38px; place-items: center; border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-button); background: var(--research-bg-panel); color: var(--research-text-secondary); }
.header-bar__icon-button:hover { border-color: var(--research-primary-200); background: var(--research-primary-50); color: var(--research-primary-700); }
.header-bar__notification { position: relative; }
.header-bar__notification-popover { position: absolute; inset-block-start: calc(100% + var(--research-space-2)); inset-inline-end: 0; display: grid; width: 260px; min-height: 150px; place-items: center; padding: var(--research-space-4); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-card); background: var(--research-bg-elevated); color: var(--research-text-secondary); box-shadow: var(--research-shadow-floating); }
.header-bar__notification-popover > div { display: flex; width: 100%; align-items: center; justify-content: space-between; }
.header-bar__notification-popover > div strong { color: var(--research-text-primary); font-size: var(--research-text-card-title); }
.header-bar__notification-popover > div button { display: grid; width: 30px; height: 30px; place-items: center; border-radius: var(--research-radius-button); background: transparent; color: var(--research-text-secondary); }
.header-bar__notification-popover > div button:hover { background: var(--research-bg-hover); color: var(--research-danger-600); }
.header-bar__notification-popover > .research-icon { color: var(--research-primary-500); }
.header-bar__notification-popover p { margin: 0; font-size: var(--research-text-sm); }
.header-bar__user { position: relative; }
.header-bar__user-button { display: flex; min-height: 42px; align-items: center; gap: var(--research-space-2); padding: var(--research-space-1) var(--research-space-2); border-radius: var(--research-radius-button); background: transparent; color: var(--research-text-secondary); }
.header-bar__user-button:hover { background: var(--research-bg-hover); color: var(--research-text-primary); }
.header-bar__avatar { display: grid; width: 32px; height: 32px; overflow: hidden; place-items: center; border-radius: var(--research-radius-pill); background: var(--research-primary-100); color: var(--research-primary-700); font-size: var(--research-text-sm); font-weight: var(--research-font-weight-bold); }
.header-bar__avatar img { width: 100%; height: 100%; object-fit: cover; }
.header-bar__user-name { max-width: 88px; overflow: hidden; font-size: var(--research-text-sm); font-weight: var(--research-font-weight-medium); text-overflow: ellipsis; white-space: nowrap; }
.header-bar__menu { position: absolute; inset-block-start: calc(100% + var(--research-space-2)); inset-inline-end: 0; width: 210px; overflow: hidden; border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-card); background: var(--research-bg-elevated); box-shadow: var(--research-shadow-floating); }
.header-bar__menu-profile { padding: var(--research-space-4); border-block-end: 1px solid var(--research-divider); }
.header-bar__menu-profile strong, .header-bar__menu-profile span { display: block; }
.header-bar__menu-profile strong { color: var(--research-text-primary); font-size: var(--research-text-body); }
.header-bar__menu-profile span { margin-block-start: var(--research-space-1); color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.header-bar__menu button { display: flex; width: 100%; align-items: center; gap: var(--research-space-2); padding: var(--research-space-3) var(--research-space-4); background: transparent; color: var(--research-danger-600); text-align: start; }
.header-bar__menu button:hover { background: var(--research-danger-50); }
.header-bar__icon-button:focus-visible, .header-bar__user-button:focus-visible, .header-bar__menu button:focus-visible, .header-bar__notification-popover button:focus-visible { outline: none; box-shadow: var(--research-shadow-focus-primary); }

@media (max-width: 1480px) {
  .header-bar__project { max-width: 220px; }
  .header-bar__project span, .header-bar__user-name { display: none; }
}
</style>
