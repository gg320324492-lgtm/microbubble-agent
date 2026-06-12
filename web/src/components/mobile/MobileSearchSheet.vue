<template>
  <Teleport to="body">
    <Transition name="search-sheet">
      <div v-if="modelValue" class="sheet-overlay" @click.self="close">
        <div class="sheet-panel" :style="{ paddingBottom: panelPaddingBottom }">
          <div class="sheet-handle" />

          <div class="search-header">
            <h3 class="search-title">{{ title || '搜索' }}</h3>
            <button
              type="button"
              class="close-btn"
              aria-label="关闭"
              title="关闭"
              @click="close"
            >✕</button>
          </div>

          <!-- 主搜索框 -->
          <div class="search-input-wrap">
            <span class="search-icon">🔍</span>
            <input
              ref="searchInputRef"
              v-model="localKeyword"
              type="search"
              class="search-input"
              :placeholder="placeholder"
              @keyup.enter="onConfirm"
            />
            <button
              v-if="localKeyword"
              type="button"
              class="clear-btn"
              aria-label="清空"
              title="清空"
              @click="localKeyword = ''"
            >✕</button>
          </div>

          <!-- 附加筛选器 -->
          <div v-if="filters.length" class="filters">
            <div v-for="filter in filters" :key="filter.key" class="filter-group">
              <div class="filter-label">{{ filter.label }}</div>
              <div class="filter-options">
                <button
                  v-for="opt in filter.options"
                  :key="opt.value"
                  type="button"
                  class="filter-option"
                  :class="{ active: isFilterActive(filter, opt.value) }"
                  @click="toggleFilter(filter, opt.value)"
                >
                  {{ opt.label }}
                </button>
              </div>
            </div>
          </div>

          <!-- 操作按钮 -->
          <div class="search-actions">
            <button
              type="button"
              class="btn-secondary"
              @click="onReset"
            >重置</button>
            <button
              type="button"
              class="btn-primary"
              @click="onConfirm"
            >搜索</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
/**
 * MobileSearchSheet.vue — 通用移动端搜索 Sheet
 *
 * PR #6: 替代桌面搜索表单（多条件筛选）
 * - 关键词搜索 + 多条件筛选 chip
 * - v-model:show 控制显示
 * - confirm/reset 事件
 *
 * 用法：
 *   <MobileSearchSheet
 *     v-model:show="show"
 *     v-model:keyword="kw"
 *     :filters="[
 *       { key: 'status', label: '状态', options: [{ value: 'all', label: '全部' }, ...] }
 *     ]"
 *     @confirm="onSearch"
 *     @reset="onReset"
 *   />
 */

import { ref, computed, watch, nextTick } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  keyword: { type: String, default: '' },
  title: { type: String, default: '' },
  placeholder: { type: String, default: '搜索...' },
  /** 附加筛选器 */
  filters: { type: Array, default: () => [] },
  /** 当前已选筛选（外部传入，emit:update） */
  selectedFilters: { type: Object, default: () => ({}) },
})

const emit = defineEmits([
  'update:modelValue',
  'update:keyword',
  'update:filters',
  'confirm',
  'reset',
])

const localKeyword = ref(props.keyword || '')
const localFilters = ref({ ...props.selectedFilters })
const searchInputRef = ref(null)

const panelPaddingBottom = computed(() => {
  return `calc(16px + var(--sab, 0px) + var(--tabbar-height, 56px))`
})

watch(
  () => props.keyword,
  (v) => { localKeyword.value = v || '' }
)
watch(
  () => props.selectedFilters,
  (v) => { localFilters.value = { ...v } },
  { deep: true }
)
watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      nextTick(() => searchInputRef.value?.focus())
    }
  }
)

function isFilterActive(filter, value) {
  const current = localFilters.value[filter.key]
  // 'all' 或未设置时不高亮
  if (!current || current === 'all') return value === 'all'
  return current === value
}

function toggleFilter(filter, value) {
  localFilters.value[filter.key] = value
}

function close() {
  emit('update:modelValue', false)
}

function onConfirm() {
  emit('update:keyword', localKeyword.value)
  emit('update:filters', { ...localFilters.value })
  emit('confirm', {
    keyword: localKeyword.value,
    filters: { ...localFilters.value },
  })
  close()
}

function onReset() {
  localKeyword.value = ''
  filters.forEach?.((f) => {
    localFilters.value[f.key] = 'all'
  })
  localFilters.value = {}
  emit('update:keyword', '')
  emit('update:filters', {})
  emit('reset')
  close()
}
</script>

<style scoped>
.sheet-overlay {
  position: fixed;
  inset: 0;
  z-index: 4500;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.sheet-panel {
  width: 100%;
  background: var(--color-bg-card);
  border-radius: var(--sheet-radius, 16px) var(--sheet-radius, 16px) 0 0;
  padding: 8px 16px;
  max-height: 85vh;
  overflow-y: auto;
}
[data-theme="dark"] .sheet-panel {
  background: var(--color-bg-card);
}

.sheet-handle {
  width: var(--sheet-handle-w, 36px);
  height: var(--sheet-handle-h, 4px);
  background: var(--color-border);
  border-radius: 2px;
  margin: 0 auto 12px;
}

.search-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.search-title {
  margin: 0;
  font-size: 16px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary);
}
.close-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 18px;
  color: var(--color-text-regular);
  cursor: pointer;
}
.close-btn:active { background: var(--color-bg-hover); }

/* 搜索框 */
.search-input-wrap {
  display: flex;
  align-items: center;
  background: var(--color-bg-page);
  border-radius: var(--radius-md);
  padding: 10px 12px;
  margin-bottom: 12px;
  gap: 8px;
}
.search-icon {
  font-size: 16px;
  color: var(--color-text-secondary);
}
.search-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 15px;
  color: var(--color-text-primary);
  outline: none;
  font-family: inherit;
}
.search-input::placeholder {
  color: var(--color-text-placeholder);
}
.clear-btn {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--color-border);
  border: none;
  font-size: 12px;
  color: var(--color-text-regular);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.clear-btn:active { opacity: 0.6; }

/* 筛选器 */
.filters {
  margin-bottom: 16px;
}
.filter-group {
  margin-bottom: 12px;
}
.filter-label {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-bottom: 6px;
}
.filter-options {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.filter-option {
  padding: 6px 12px;
  background: var(--color-bg-page);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  font-size: 13px;
  color: var(--color-text-regular);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.filter-option.active {
  background: var(--color-primary);
  color: white;
  border-color: var(--color-primary);
}

/* 操作按钮 */
.search-actions {
  display: flex;
  gap: 8px;
}
.btn-secondary, .btn-primary {
  flex: 1;
  padding: 12px;
  border-radius: var(--radius-md);
  border: none;
  font-size: 14px;
  font-weight: var(--font-weight-medium, 500);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.btn-secondary {
  background: var(--color-bg-page);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border);
}
.btn-primary {
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
  color: white;
}

/* 进出动画 */
.search-sheet-enter-active, .search-sheet-leave-active {
  transition: opacity 0.25s ease;
}
.search-sheet-enter-active .sheet-panel,
.search-sheet-leave-active .sheet-panel {
  transition: transform 0.3s ease;
}
.search-sheet-enter-from, .search-sheet-leave-to { opacity: 0; }
.search-sheet-enter-from .sheet-panel,
.search-sheet-leave-to .sheet-panel {
  transform: translateY(100%);
}
</style>