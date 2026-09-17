<script setup lang="ts">
// 命令面板（M4）— 应用内 Ctrl+K 唤起的键值守面板（视觉对标主流命令面板）。
// 命令注册表经 props 注入；输入实时过滤、上下键选择、Enter 执行、Esc 关闭。
import { computed, nextTick, ref, watch } from 'vue'
import type { CommandRegistry, Command } from '@shared/command-registry'

const props = defineProps<{ registry: CommandRegistry; visible: boolean }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const query = ref('')
const activeIndex = ref(0)
const inputRef = ref<HTMLInputElement | null>(null)
const listEl = ref<HTMLElement | null>(null)

const results = computed<Command[]>(() => props.registry.filter(query.value))

watch(
  () => props.visible,
  (v) => {
    if (v) {
      query.value = ''
      activeIndex.value = 0
      void nextTick(() => inputRef.value?.focus())
    }
  }
)

function move(delta: number): void {
  const n = results.value.length
  if (n === 0) return
  activeIndex.value = (activeIndex.value + delta + n) % n
  void nextTick(() => {
    listEl.value?.querySelector(`[data-index="${activeIndex.value}"]`)?.scrollIntoView({ block: 'nearest' })
  })
}

function executeAt(index: number): void {
  const cmd = results.value[index]
  if (!cmd) return
  emit('close')
  cmd.action()
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    move(1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    move(-1)
  } else if (e.key === 'Enter') {
    e.preventDefault()
    executeAt(activeIndex.value)
  } else if (e.key === 'Escape') {
    e.preventDefault()
    emit('close')
  }
}

watch(query, () => {
  activeIndex.value = 0
})

function onRootKeydown(e: KeyboardEvent): void {
  onKeydown(e)
}
</script>

<template>
  <div v-if="visible" class="palette-mask" data-testid="palette-mask" @click.self="emit('close')">
      <div class="palette" role="dialog" aria-label="命令面板" @keydown="onRootKeydown">
        <input
          ref="inputRef"
          v-model="query"
          class="palette-input"
          placeholder="输入命令或搜索…（↑↓ 选择，Enter 执行，Esc 关闭）"
          data-testid="palette-input"
        />
        <div ref="listEl" class="palette-list" data-testid="palette-list">
          <div v-if="results.length === 0" class="palette-empty">没有匹配的命令</div>
          <button
            v-for="(cmd, i) in results"
            :key="cmd.id"
            class="palette-item"
            :class="{ active: i === activeIndex }"
            :data-index="i"
            :data-testid="`palette-item-${i}`"
            @mousemove="activeIndex = i"
            @click="executeAt(i)"
          >
            <span class="palette-title">{{ cmd.title }}</span>
            <span v-if="cmd.keywords" class="palette-keywords">{{ cmd.keywords }}</span>
          </button>
          <div v-if="results.length === 0" class="palette-empty-end"></div>
        </div>
      </div>
    </div>
</template>

<style scoped>
.palette-mask {
  position: fixed;
  inset: 0;
  z-index: 3000;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 12vh;
}
.palette {
  width: min(560px, 90vw);
  max-height: 60vh;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg, 0 12px 40px rgba(0, 0, 0, 0.25));
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.palette-input {
  height: 44px;
  padding: 0 16px;
  border: none;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-card);
  color: var(--color-text-primary);
  font-size: var(--font-size-base, 14px);
  outline: none;
}
.palette-list {
  max-height: 46vh;
  overflow: auto;
  padding: 4px 0;
}
.palette-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 16px;
  border: none;
  background: transparent;
  cursor: pointer;
  text-align: left;
  font-size: var(--font-size-sm, 13px);
  color: var(--color-text-primary);
}
.palette-item.active {
  background: rgba(var(--color-primary-rgb), 0.12);
}
.palette-item.active .palette-title {
  color: var(--color-primary);
  font-weight: 600;
}
.palette-title {
  flex-shrink: 0;
}
.palette-keywords {
  margin-left: auto;
  font-family: var(--font-family-mono);
  font-size: 10px;
  color: var(--color-text-placeholder);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 40%;
}
.palette-empty {
  padding: 18px 16px;
  font-size: var(--font-size-sm, 13px);
  color: var(--color-text-secondary);
  text-align: center;
}
.palette-empty-end {
  height: 4px;
}
</style>
