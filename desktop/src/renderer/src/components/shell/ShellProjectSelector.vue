<script setup lang="ts">
/**
 * Shell ProjectSelector — Phase 8-M0-F 全局 Shell 升级
 *
 * 项目选择器 popover，参考 Linear：
 *   - 触发器显示当前项目
 *   - 下拉列表内含搜索过滤
 *   - 键盘 ↑ ↓ Enter Esc
 *   - aria-haspopup=listbox
 */
import { computed, nextTick, ref, watch } from 'vue'
import ResearchIcon from '../icons/ResearchIcon.vue'
import type { ResearchProject } from '../../stores/research/project.store'

const props = withDefaults(defineProps<{
  open: boolean
  current: ResearchProject
  projects: ResearchProject[]
}>(), { open: false })

const emit = defineEmits<{
  toggle: []
  close: [restoreFocus?: boolean]
  select: [project: ResearchProject]
}>()

const searchTerm = ref('')
const triggerRef = ref<HTMLButtonElement | null>(null)
const searchInputRef = ref<HTMLInputElement | null>(null)
const activeIndex = ref(0)

const filteredProjects = computed<ResearchProject[]>(() => {
  const term = searchTerm.value.trim().toLowerCase()
  if (!term) return props.projects
  return props.projects.filter((project) => {
    const hay = `${project.name} ${project.domain}`.toLowerCase()
    return hay.includes(term)
  })
})

watch(() => props.open, async (open) => {
  if (open) {
    searchTerm.value = ''
    activeIndex.value = Math.max(0, filteredProjects.value.findIndex((p) => p.id === props.current.id))
    await nextTick()
    searchInputRef.value?.focus()
  }
})

watch(filteredProjects, () => { activeIndex.value = 0 })

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    activeIndex.value = Math.min(activeIndex.value + 1, Math.max(0, filteredProjects.value.length - 1))
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    activeIndex.value = Math.max(0, activeIndex.value - 1)
  } else if (event.key === 'Enter') {
    event.preventDefault()
    const project = filteredProjects.value[activeIndex.value]
    if (project) emit('select', project)
  } else if (event.key === 'Escape') {
    event.preventDefault()
    emit('close', true)
  }
}

function statusToLabel(status: ResearchProject['status']): string {
  const labels = { active: '进行中', planning: '规划中', completed: '已完成', paused: '已暂停' } as const
  return labels[status]
}
</script>

<template>
  <div class="shell-project" @keydown="onKeydown">
    <button
      ref="triggerRef"
      type="button"
      class="shell-project__trigger"
      data-testid="header-project"
      aria-label="当前项目选择器"
      aria-controls="shell-project-listbox"
      :aria-expanded="open"
      aria-haspopup="listbox"
      @click="emit('toggle')"
      @keydown.esc.stop="emit('close', true)"
    >
      <ResearchIcon name="project" :size="17" />
      <span class="shell-project__copy">
        <span>当前项目</span>
        <strong>{{ current.name }}</strong>
      </span>
      <ResearchIcon name="expand" :size="14" aria-hidden="true" />
    </button>
    <Transition name="shell-project-popover">
      <div
        v-if="open"
        id="shell-project-listbox"
        class="shell-project__popover"
        role="listbox"
        aria-label="科研项目"
        @keydown.esc.stop="emit('close', true)"
      >
        <div class="shell-project__search">
          <ResearchIcon name="search" :size="14" aria-hidden="true" />
          <input
            ref="searchInputRef"
            v-model="searchTerm"
            type="text"
            class="shell-project__search-input"
            placeholder="搜索项目..."
            aria-label="搜索科研项目"
          >
        </div>
        <ul class="shell-project__list">
          <li v-if="filteredProjects.length === 0" class="shell-project__empty" role="status">
            未找到匹配项目
          </li>
          <li
            v-for="(project, idx) in filteredProjects"
            :key="project.id"
            class="shell-project__option"
            role="option"
            :aria-selected="project.id === current.id"
            :class="{ 'is-active': idx === activeIndex, 'is-current': project.id === current.id }"
            @click="emit('select', project)"
            @mouseenter="activeIndex = idx"
          >
            <div class="shell-project__option-meta">
              <strong>{{ project.name }}</strong>
              <span>{{ project.domain }} · {{ statusToLabel(project.status) }}</span>
            </div>
            <div class="shell-project__option-progress">
              <span class="shell-project__option-progress-bar">
                <span class="shell-project__option-progress-fill" :style="{ width: `${Math.round(project.progress * 100)}%` }" />
              </span>
              <span class="shell-project__option-progress-value">{{ Math.round(project.progress * 100) }}%</span>
            </div>
          </li>
        </ul>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.shell-project { position: relative; min-width: 0; }
.shell-project__trigger {
  display: flex;
  max-width: 290px;
  min-width: 0;
  align-items: center;
  gap: var(--research-space-2);
  padding: var(--research-space-1) var(--research-space-4) var(--research-space-1) 0;
  border: 0;
  border-inline-end: 1px solid var(--research-divider);
  background: transparent;
  color: var(--research-primary-600);
  font: inherit;
  cursor: pointer;
  text-align: start;
  transition: color var(--research-duration-fast) var(--research-ease-standard);
}
.shell-project__trigger:hover { color: var(--research-primary-700); }
.shell-project__trigger:focus-visible { outline: none; box-shadow: var(--research-shadow-focus-primary); }
.shell-project__copy { min-width: 0; }
.shell-project__copy span, .shell-project__copy strong { display: block; }
.shell-project__copy span { color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.shell-project__copy strong { overflow: hidden; color: var(--research-text-primary); font-size: var(--research-text-sm); font-weight: var(--research-font-weight-semibold); text-overflow: ellipsis; white-space: nowrap; }
.shell-project__popover {
  position: absolute;
  inset-block-start: calc(100% + var(--research-space-2));
  inset-inline-start: 0;
  z-index: var(--research-z-popover);
  width: 340px;
  padding: var(--research-space-2);
  border: 1px solid var(--research-border-subtle);
  border-radius: var(--research-radius-md);
  background: var(--research-bg-elevated);
  box-shadow: var(--research-shadow-floating);
}
.shell-project__search {
  display: flex;
  align-items: center;
  gap: var(--research-space-2);
  padding: var(--research-space-2) var(--research-space-3);
  border: 1px solid var(--research-border-subtle);
  border-radius: var(--research-radius-sm);
  background: var(--research-bg-panel);
  color: var(--research-text-muted);
}
.shell-project__search-input {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--research-text-primary);
  font: inherit;
  font-size: var(--research-text-sm);
}
.shell-project__search-input::placeholder { color: var(--research-text-muted); }
.shell-project__list { list-style: none; padding: 0; margin: var(--research-space-2) 0 0; display: flex; flex-direction: column; gap: 2px; max-height: 320px; overflow-y: auto; }
.shell-project__empty { padding: var(--research-space-4); text-align: center; color: var(--research-text-muted); font-size: var(--research-text-sm); }
.shell-project__option {
  display: grid;
  gap: var(--research-space-2);
  padding: var(--research-space-3);
  border-radius: var(--research-radius-sm);
  cursor: pointer;
  transition: background var(--research-duration-fast) var(--research-ease-standard);
}
.shell-project__option:hover, .shell-project__option.is-active { background: var(--research-bg-hover); }
.shell-project__option.is-current { background: var(--research-primary-50); }
.shell-project__option:focus-visible { outline: none; box-shadow: var(--research-shadow-focus-primary); }
.shell-project__option-meta { display: grid; gap: 2px; min-width: 0; }
.shell-project__option-meta strong { color: var(--research-text-primary); font-size: var(--research-text-sm); font-weight: var(--research-font-weight-semibold); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.shell-project__option-meta span { color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.shell-project__option.is-current .shell-project__option-meta strong { color: var(--research-primary-700); }
.shell-project__option-progress { display: flex; align-items: center; gap: var(--research-space-2); }
.shell-project__option-progress-bar { flex: 1; height: 4px; border-radius: var(--research-radius-pill); background: var(--research-primary-100); position: relative; overflow: hidden; display: block; }
.shell-project__option-progress-fill { display: block; height: 100%; background: var(--research-primary-600); border-radius: inherit; transition: width var(--research-duration-slow) var(--research-ease-emphasized); }
.shell-project__option.is-current .shell-project__option-progress-bar { background: var(--research-primary-200); }
.shell-project__option-progress-value { color: var(--research-text-secondary); font-size: var(--research-text-xs); font-family: var(--research-font-scientific); }

.shell-project-popover-enter-active, .shell-project-popover-leave-active { transition: opacity var(--research-duration-fast) var(--research-ease-standard), transform var(--research-duration-fast) var(--research-ease-emphasized); }
.shell-project-popover-enter-from, .shell-project-popover-leave-to { opacity: 0; transform: translateY(-4px); }

@media (prefers-reduced-motion: reduce) {
  .shell-project__trigger, .shell-project__option { transition: none; }
  .shell-project-popover-enter-active, .shell-project-popover-leave-active { transition: none; }
}
</style>
