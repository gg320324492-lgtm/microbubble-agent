<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ResearchIcon from '../components/icons/ResearchIcon.vue'
import { useAuthStore } from '../stores/auth'
import { useProjectStore } from '../stores/research/project.store'
import { useUserStore } from '../stores/user'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const projectStore = useProjectStore()
const userStore = useUserStore()
const userMenuOpen = ref(false)
const notificationOpen = ref(false)
const projectSelectorOpen = ref(false)
const commandOpen = ref(false)
const userRegion = ref<HTMLElement | null>(null)
const userMenuTrigger = ref<HTMLButtonElement | null>(null)
const userMenu = ref<HTMLElement | null>(null)
const logoutButton = ref<HTMLButtonElement | null>(null)
const notificationRegion = ref<HTMLElement | null>(null)
const notificationTrigger = ref<HTMLButtonElement | null>(null)
const projectSelectorRegion = ref<HTMLElement | null>(null)
const projectSelectorTrigger = ref<HTMLButtonElement | null>(null)
const commandRegion = ref<HTMLElement | null>(null)
const commandTrigger = ref<HTMLButtonElement | null>(null)

const pageTitle = computed(() => {
  const meta = route.meta as { title?: string }
  return meta.title ?? '科研工作台'
})
const displayName = computed(() => userStore.profile?.name ?? '未登录')
const avatarUrl = computed(() => userStore.profile?.avatar ?? '')
const aiStatus = computed(() => {
  return {
    task: '尚未接入实时任务数据',
    state: '占位状态',
    context: projectStore.currentProject.name
  }
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

function toggleProjectSelector(): void {
  projectSelectorOpen.value = !projectSelectorOpen.value
}

async function closeProjectSelector(restoreFocus = false): Promise<void> {
  if (!projectSelectorOpen.value) return
  projectSelectorOpen.value = false
  if (restoreFocus) {
    await nextTick()
    projectSelectorTrigger.value?.focus()
  }
}

function toggleCommand(): void {
  commandOpen.value = !commandOpen.value
}

async function closeCommand(restoreFocus = false): Promise<void> {
  if (!commandOpen.value) return
  commandOpen.value = false
  if (restoreFocus) {
    await nextTick()
    commandTrigger.value?.focus()
  }
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
  if (projectSelectorOpen.value && !projectSelectorRegion.value?.contains(target)) void closeProjectSelector()
  if (commandOpen.value && !commandRegion.value?.contains(target)) void closeCommand()
}

function onGlobalKeydown(event: KeyboardEvent): void {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    toggleCommand()
  }
}

onMounted(() => {
  document.addEventListener('pointerdown', onDocumentPointerDown)
  document.addEventListener('keydown', onGlobalKeydown)
})
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocumentPointerDown)
  document.removeEventListener('keydown', onGlobalKeydown)
})

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
      <div ref="projectSelectorRegion" class="header-bar__project-region">
        <button
          ref="projectSelectorTrigger"
          data-testid="header-project"
          class="header-bar__project-trigger"
          type="button"
          aria-label="当前项目选择器"
          aria-controls="header-project-listbox"
          :aria-expanded="projectSelectorOpen"
          aria-haspopup="listbox"
          @click="toggleProjectSelector"
          @keydown.esc.stop="closeProjectSelector(true)"
        >
          <ResearchIcon name="project" :size="17" />
          <span class="header-bar__project-copy"><span>当前项目</span><strong>{{ projectStore.currentProject.name }}</strong></span>
          <ResearchIcon name="expand" :size="14" aria-hidden="true" />
        </button>
        <div v-if="projectSelectorOpen" id="header-project-listbox" class="header-bar__project-listbox" role="listbox" aria-label="当前项目选择器" @keydown.esc.stop="closeProjectSelector(true)">
          <div v-for="project in projectStore.projectList" :key="project.id" role="option" :aria-selected="project.id === projectStore.currentProject.id">
            <strong>{{ project.name }}</strong><span>{{ project.domain }} · {{ Math.round(project.progress * 100) }}%</span>
          </div>
        </div>
      </div>

      <div class="header-ai-status__system" role="status" aria-live="polite" aria-label="系统状态：待连接"><span aria-hidden="true" />系统状态：待连接</div>

      <div
        data-testid="header-ai-status"
        class="header-bar__ai header-bar__ai-status"
        role="status"
        aria-live="polite"
        aria-label="全局 AI 状态"
      >
        <ResearchIcon name="running" :size="16" aria-hidden="true" />
        <dl class="header-bar__ai-details">
          <div><dt>当前 AI 任务</dt><dd>{{ aiStatus.task }}</dd></div>
          <div><dt>状态</dt><dd>{{ aiStatus.state }}</dd></div>
          <div><dt>项目上下文</dt><dd>{{ aiStatus.context }}</dd></div>
        </dl>
      </div>

      <div ref="commandRegion" class="header-bar__command">
        <button ref="commandTrigger" class="header-bar__command-trigger" type="button" aria-label="打开命令与搜索" aria-controls="header-command-popover" :aria-expanded="commandOpen" aria-keyshortcuts="Control+K" @click="toggleCommand" @keydown.esc.stop="closeCommand(true)">
          <ResearchIcon name="search" :size="17" /><span>搜索或命令</span><kbd>Ctrl K</kbd>
        </button>
        <section v-if="commandOpen" id="header-command-popover" class="header-command-popover" role="dialog" aria-label="命令与搜索" @keydown.esc.stop="closeCommand(true)">
          <strong>命令与搜索</strong><p>全局科研搜索将在后续阶段接入。</p>
        </section>
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
.header-bar__project-region, .header-bar__command, .header-bar__notification { position: relative; }
.header-bar__project-trigger { display: flex; max-width: 290px; min-width: 0; align-items: center; gap: var(--research-space-2); padding: var(--research-space-1) var(--research-space-4) var(--research-space-1) 0; border: 0; border-inline-end: 1px solid var(--research-divider); background: transparent; color: var(--research-primary-600); font: inherit; cursor: pointer; text-align: start; }
.header-bar__project-copy { min-width: 0; }
.header-bar__project-copy span, .header-bar__project-copy strong { display: block; }
.header-bar__project-copy span { color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.header-bar__project-copy strong { overflow: hidden; color: var(--research-text-primary); font-size: var(--research-text-sm); font-weight: var(--research-font-weight-semibold); text-overflow: ellipsis; white-space: nowrap; }
.header-bar__project-listbox, .header-command-popover { position: absolute; z-index: var(--research-z-popover); inset-block-start: calc(100% + var(--research-space-2)); min-width: 260px; padding: var(--research-space-2); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-md); background: var(--research-bg-elevated); box-shadow: var(--research-shadow-floating); }
.header-bar__project-listbox { inset-inline-start: 0; }
.header-bar__project-listbox [role='option'] { display: grid; gap: var(--research-space-1); padding: var(--research-space-3); border-radius: var(--research-radius-sm); color: var(--research-text-secondary); }
.header-bar__project-listbox [aria-selected='true'] { background: var(--research-primary-50); color: var(--research-primary-700); }
.header-bar__project-listbox strong { color: var(--research-text-primary); font-size: var(--research-text-sm); }
.header-bar__project-listbox span { font-size: var(--research-text-xs); }
.header-ai-status__system { display: inline-flex; align-items: center; gap: var(--research-space-2); color: var(--research-warning-600); font-size: var(--research-text-xs); white-space: nowrap; }
.header-ai-status__system > span { width: 7px; height: 7px; border-radius: var(--research-radius-pill); background: currentColor; box-shadow: 0 0 0 4px var(--research-warning-50); }
.header-bar__ai { display: inline-flex; align-items: center; gap: var(--research-space-2); padding: var(--research-space-2) var(--research-space-3); border: 1px solid var(--research-success-100); border-radius: var(--research-radius-pill); background: var(--research-success-50); color: var(--research-success-700); font-size: var(--research-text-sm); font-weight: var(--research-font-weight-medium); white-space: nowrap; }
.header-bar__ai { max-width: min(560px, 38vw); border-color: var(--research-ai-100); background: var(--research-ai-50); color: var(--research-ai-700); }
.header-bar__ai-details { display: flex; min-width: 0; gap: var(--research-space-2); margin: 0; }
.header-bar__ai-details div { display: grid; min-width: 0; gap: 1px; }
.header-bar__ai-details div + div { padding-inline-start: var(--research-space-2); border-inline-start: 1px solid var(--research-ai-200); }
.header-bar__ai-details dt { color: var(--research-text-secondary); font-size: var(--research-text-xs); font-weight: var(--research-font-weight-regular); }
.header-bar__ai-details dd { max-width: 150px; overflow: hidden; margin: 0; color: inherit; font-size: var(--research-text-xs); font-weight: var(--research-font-weight-medium); text-overflow: ellipsis; white-space: nowrap; }
.header-bar__icon-button, .header-bar__user-button, .header-bar__menu button, .header-bar__notification-popover button, .header-bar__command-trigger { border: 0; font: inherit; cursor: pointer; }
.header-bar__command-trigger { display: inline-flex; min-height: 34px; align-items: center; gap: var(--research-space-2); padding: var(--research-space-2) var(--research-space-3); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-sm); background: var(--research-bg-panel); color: var(--research-text-secondary); }
.header-bar__command-trigger:hover { border-color: var(--research-primary-200); color: var(--research-primary-700); }
.header-bar__command-trigger kbd { padding: 1px var(--research-space-1); border: 1px solid var(--research-border-subtle); border-radius: 4px; color: var(--research-text-muted); font-family: var(--research-font-scientific); font-size: var(--research-text-xs); }
.header-command-popover { inset-inline-end: 0; color: var(--research-text-secondary); }
.header-command-popover strong, .header-command-popover p { display: block; margin: 0; }
.header-command-popover strong { color: var(--research-text-primary); }
.header-command-popover p { margin-block-start: var(--research-space-2); font-size: var(--research-text-sm); }
.header-bar__icon-button { display: grid; width: 38px; height: 38px; place-items: center; border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-button); background: var(--research-bg-panel); color: var(--research-text-secondary); }
.header-bar__icon-button:hover { border-color: var(--research-primary-200); background: var(--research-primary-50); color: var(--research-primary-700); }
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
.header-bar__icon-button:focus-visible, .header-bar__user-button:focus-visible, .header-bar__menu button:focus-visible, .header-bar__notification-popover button:focus-visible, .header-bar__project-trigger:focus-visible, .header-bar__command-trigger:focus-visible { outline: none; box-shadow: var(--research-shadow-focus-primary); }

@media (max-width: 1480px) {
  .header-bar__project-trigger { max-width: 220px; }
  .header-bar__project-copy > span, .header-bar__user-name, .header-ai-status__system, .header-bar__command-trigger span, .header-bar__command-trigger kbd { display: none; }
  .header-bar__ai-details div:nth-child(1), .header-bar__ai-details div:nth-child(2) { display: none; }
}
</style>
