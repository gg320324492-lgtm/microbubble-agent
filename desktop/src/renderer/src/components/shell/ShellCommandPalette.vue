<script setup lang="ts">
/**
 * Shell CommandPalette — Phase 8-M0-F 全局 Shell 升级
 *
 * Cursor / Linear 风格的命令面板：
 *   - 顶部搜索（实时过滤）
 *   - 分组：导航 / 命令 / 项目
 *   - 键盘 ↑ ↓ 选择，Enter 触发，Esc 关闭
 *   - 焦点可见 / 减弱动画 / role=dialog
 */
import { computed, nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import ResearchIcon from '../icons/ResearchIcon.vue'
import type { ResearchIconName } from '../icons/research-icons'
import { useProjectStore } from '../../stores/research/project.store'

interface CommandItem {
  id: string
  label: string
  hint?: string
  group: 'navigation' | 'command' | 'project'
  icon?: ResearchIconName
  action: () => void
}

const props = withDefaults(defineProps<{
  open: boolean
}>(), { open: false })

const emit = defineEmits<{
  close: [restoreFocus?: boolean]
}>()

const router = useRouter()
const projectStore = useProjectStore()

const searchTerm = ref('')
const activeIndex = ref(0)
const inputRef = ref<HTMLInputElement | null>(null)
const listRef = ref<HTMLElement | null>(null)

const NAV_ITEMS: ReadonlyArray<{ name: string; label: string; icon: ResearchIconName }> = [
  { name: 'research-dashboard', label: '科研驾驶舱', icon: 'home' },
  { name: 'research-assistant', label: '科研助手', icon: 'assistant' },
  { name: 'research-project', label: '研究工作区', icon: 'project' },
  { name: 'research-literature', label: '文献研究', icon: 'literature' },
  { name: 'research-experiment', label: '实验设计', icon: 'experiment' },
  { name: 'research-data-analysis', label: '数据分析', icon: 'data' },
  { name: 'research-manuscript', label: 'SCI写作', icon: 'manuscript' },
  { name: 'research-knowledge-graph', label: '知识图谱', icon: 'graph' },
  { name: 'research-agent-center', label: 'AI研究团队', icon: 'agent' },
  { name: 'research-experiment-control', label: '实验控制中心', icon: 'experiment' },
  { name: 'research-settings', label: '系统设置', icon: 'settings' }
]

const baseCommands: CommandItem[] = [
  {
    id: 'cmd-toggle-sidebar',
    label: '收起 / 展开侧栏',
    hint: '导航',
    group: 'command',
    icon: 'collapse',
    action: () => emit('close')
  },
  {
    id: 'cmd-jump-dashboard',
    label: '跳转到科研驾驶舱',
    hint: '⌘1',
    group: 'command',
    icon: 'home',
    action: () => { void router.push({ name: 'research-dashboard' }); emit('close') }
  },
  {
    id: 'cmd-jump-assistant',
    label: '打开 AI 科研助手',
    hint: '⌘2',
    group: 'command',
    icon: 'assistant',
    action: () => { void router.push({ name: 'research-assistant' }); emit('close') }
  },
  {
    id: 'cmd-jump-graph',
    label: '打开知识图谱',
    hint: '⌘3',
    group: 'command',
    icon: 'graph',
    action: () => { void router.push({ name: 'research-knowledge-graph' }); emit('close') }
  }
]

const allItems = computed<CommandItem[]>(() => {
  const navigationItems: CommandItem[] = NAV_ITEMS.map((nav) => ({
    id: `nav-${nav.name}`,
    label: nav.label,
    hint: '页面',
    group: 'navigation',
    icon: nav.icon,
    action: () => { void router.push({ name: nav.name }); emit('close') }
  }))
  const projectItems: CommandItem[] = projectStore.projectList.map((project) => ({
    id: `project-${project.id}`,
    label: project.name,
    hint: project.domain,
    group: 'project',
    icon: 'project',
    action: () => emit('close')
  }))
  return [...navigationItems, ...baseCommands, ...projectItems]
})

const filteredItems = computed<CommandItem[]>(() => {
  const term = searchTerm.value.trim().toLowerCase()
  if (!term) return allItems.value
  return allItems.value.filter((item) => item.label.toLowerCase().includes(term))
})

const groupedItems = computed<{ navigation: CommandItem[]; command: CommandItem[]; project: CommandItem[] }>(() => {
  const groups: { navigation: CommandItem[]; command: CommandItem[]; project: CommandItem[] } = {
    navigation: [],
    command: [],
    project: []
  }
  for (const item of filteredItems.value) groups[item.group].push(item)
  return groups
})

const flatItems = computed<CommandItem[]>(() => [
  ...groupedItems.value.navigation,
  ...groupedItems.value.command,
  ...groupedItems.value.project
])

watch(() => props.open, async (open) => {
  if (open) {
    searchTerm.value = ''
    activeIndex.value = 0
    await nextTick()
    inputRef.value?.focus()
  }
})

watch(filteredItems, () => { activeIndex.value = 0 })

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    activeIndex.value = Math.min(activeIndex.value + 1, Math.max(0, flatItems.value.length - 1))
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    activeIndex.value = Math.max(0, activeIndex.value - 1)
  } else if (event.key === 'Enter') {
    event.preventDefault()
    const item = flatItems.value[activeIndex.value]
    if (item) item.action()
  } else if (event.key === 'Escape') {
    event.preventDefault()
    emit('close', true)
  }
}

function selectItem(item: CommandItem): void {
  item.action()
}

function closePalette(): void {
  emit('close', true)
}
</script>

<template>
  <Transition name="shell-palette">
    <div
      v-if="open"
      class="shell-palette"
      role="dialog"
      aria-label="命令与搜索面板"
      aria-modal="true"
      @keydown="onKeydown"
    >
      <div class="shell-palette__backdrop" aria-hidden="true" @click="closePalette" />
      <div class="shell-palette__panel" role="document">
        <div class="shell-palette__search">
          <ResearchIcon name="search" :size="18" aria-hidden="true" />
          <input
            ref="inputRef"
            v-model="searchTerm"
            type="text"
            class="shell-palette__input"
            placeholder="搜索页面、命令或项目..."
            aria-label="搜索命令与项目"
          >
          <kbd class="shell-palette__shortcut">Esc</kbd>
        </div>
        <ul ref="listRef" class="shell-palette__list" role="listbox">
          <li v-if="flatItems.length === 0" class="shell-palette__empty" role="status">
            未找到匹配项
          </li>
          <template v-else>
            <li v-if="groupedItems.navigation.length > 0" class="shell-palette__group" role="presentation">
              <span class="shell-palette__group-title">页面</span>
              <ul class="shell-palette__group-list">
                <li
                  v-for="item in groupedItems.navigation"
                  :key="item.id"
                  class="shell-palette__item"
                  role="option"
                  :aria-selected="flatItems.indexOf(item) === activeIndex"
                  :class="{ 'is-active': flatItems.indexOf(item) === activeIndex }"
                  @click="selectItem(item)"
                  @mouseenter="activeIndex = flatItems.indexOf(item)"
                >
                  <ResearchIcon v-if="item.icon" :name="item.icon" :size="16" />
                  <span class="shell-palette__item-label">{{ item.label }}</span>
                  <span v-if="item.hint" class="shell-palette__item-hint">{{ item.hint }}</span>
                </li>
              </ul>
            </li>
            <li v-if="groupedItems.command.length > 0" class="shell-palette__group" role="presentation">
              <span class="shell-palette__group-title">命令</span>
              <ul class="shell-palette__group-list">
                <li
                  v-for="item in groupedItems.command"
                  :key="item.id"
                  class="shell-palette__item"
                  role="option"
                  :aria-selected="flatItems.indexOf(item) === activeIndex"
                  :class="{ 'is-active': flatItems.indexOf(item) === activeIndex }"
                  @click="selectItem(item)"
                  @mouseenter="activeIndex = flatItems.indexOf(item)"
                >
                  <ResearchIcon v-if="item.icon" :name="item.icon" :size="16" />
                  <span class="shell-palette__item-label">{{ item.label }}</span>
                  <span v-if="item.hint" class="shell-palette__item-hint">{{ item.hint }}</span>
                </li>
              </ul>
            </li>
            <li v-if="groupedItems.project.length > 0" class="shell-palette__group" role="presentation">
              <span class="shell-palette__group-title">项目</span>
              <ul class="shell-palette__group-list">
                <li
                  v-for="item in groupedItems.project"
                  :key="item.id"
                  class="shell-palette__item"
                  role="option"
                  :aria-selected="flatItems.indexOf(item) === activeIndex"
                  :class="{ 'is-active': flatItems.indexOf(item) === activeIndex }"
                  @click="selectItem(item)"
                  @mouseenter="activeIndex = flatItems.indexOf(item)"
                >
                  <ResearchIcon v-if="item.icon" :name="item.icon" :size="16" />
                  <span class="shell-palette__item-label">{{ item.label }}</span>
                  <span v-if="item.hint" class="shell-palette__item-hint">{{ item.hint }}</span>
                </li>
              </ul>
            </li>
          </template>
        </ul>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.shell-palette {
  position: fixed;
  inset: 0;
  z-index: var(--research-z-modal);
  display: grid;
  place-items: start center;
  padding-block-start: 12vh;
}
.shell-palette__backdrop {
  position: absolute;
  inset: 0;
  background: var(--research-overlay);
  backdrop-filter: blur(6px);
}
.shell-palette__panel {
  position: relative;
  width: min(620px, 92vw);
  max-height: 70vh;
  overflow: hidden;
  border: 1px solid var(--research-border-subtle);
  border-radius: var(--research-radius-panel);
  background: var(--research-bg-elevated);
  box-shadow: var(--research-shadow-modal);
  display: grid;
  grid-template-rows: auto 1fr;
}
.shell-palette__search {
  display: flex;
  align-items: center;
  gap: var(--research-space-3);
  padding: var(--research-space-4) var(--research-space-5);
  border-block-end: 1px solid var(--research-divider);
  color: var(--research-text-secondary);
}
.shell-palette__input {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--research-text-primary);
  font: inherit;
  font-size: var(--research-text-body);
}
.shell-palette__input::placeholder { color: var(--research-text-muted); }
.shell-palette__shortcut {
  padding: 2px var(--research-space-2);
  border: 1px solid var(--research-border-subtle);
  border-radius: 4px;
  color: var(--research-text-muted);
  font-family: var(--research-font-scientific);
  font-size: var(--research-text-xs);
}
.shell-palette__list {
  list-style: none;
  padding: var(--research-space-2);
  margin: 0;
  overflow-y: auto;
}
.shell-palette__empty {
  padding: var(--research-space-6);
  text-align: center;
  color: var(--research-text-muted);
  font-size: var(--research-text-sm);
}
.shell-palette__group { margin-bottom: var(--research-space-2); }
.shell-palette__group:last-child { margin-bottom: 0; }
.shell-palette__group-title {
  display: block;
  padding: var(--research-space-2) var(--research-space-3);
  color: var(--research-text-muted);
  font-size: var(--research-text-xs);
  font-weight: var(--research-font-weight-semibold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.shell-palette__group-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.shell-palette__item {
  display: flex;
  align-items: center;
  gap: var(--research-space-3);
  padding: var(--research-space-2) var(--research-space-3);
  border-radius: var(--research-radius-sm);
  color: var(--research-text-secondary);
  font-size: var(--research-text-sm);
  cursor: pointer;
  transition: background var(--research-duration-fast) var(--research-ease-standard);
}
.shell-palette__item.is-active {
  background: var(--research-primary-50);
  color: var(--research-primary-700);
}
.shell-palette__item-label { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.shell-palette__item-hint { color: var(--research-text-muted); font-size: var(--research-text-xs); font-family: var(--research-font-scientific); }
.shell-palette__item:focus-visible { outline: none; box-shadow: var(--research-shadow-focus-primary); }

.shell-palette-enter-active, .shell-palette-leave-active { transition: opacity var(--research-duration-normal) var(--research-ease-standard); }
.shell-palette-enter-from, .shell-palette-leave-to { opacity: 0; }
.shell-palette-enter-active .shell-palette__panel,
.shell-palette-leave-active .shell-palette__panel {
  transition: transform var(--research-duration-normal) var(--research-ease-emphasized);
}
.shell-palette-enter-from .shell-palette__panel { transform: translateY(-12px) scale(0.98); }
.shell-palette-leave-to .shell-palette__panel { transform: translateY(-8px) scale(0.98); }

@media (prefers-reduced-motion: reduce) {
  .shell-palette-enter-active, .shell-palette-leave-active { transition: none; }
  .shell-palette-enter-active .shell-palette__panel,
  .shell-palette-leave-active .shell-palette__panel { transition: none; }
}
</style>
