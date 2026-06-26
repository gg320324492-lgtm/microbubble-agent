<template>
  <div class="card-list-root">
    <!-- 头部：标题 + 批量操作 -->
    <div v-if="title || $slots.header" class="list-header">
      <slot name="header">
        <div class="header-row">
          <h3 class="list-title">{{ title }}</h3>
          <span v-if="selectable && selected.length" class="selected-count">
            已选 {{ selected.length }} 项
          </span>
        </div>
      </slot>
    </div>

    <!-- 多选模式：顶部批量操作条 -->
    <div v-if="selectable && selected.length" class="batch-bar">
      <span class="batch-info">
        <span class="batch-count">{{ selected.length }}</span> 项已选
      </span>
      <div class="batch-actions">
        <slot name="batch-actions" :selected="selected" :clear="clearSelection" />
      </div>
    </div>

    <!-- 空态 -->
    <div v-if="items.length === 0" class="empty-state">
      <slot name="empty">
        <div class="empty-icon">{{ emptyIcon || '📭' }}</div>
        <div class="empty-title">{{ emptyTitle || '暂无数据' }}</div>
        <div v-if="emptyHint" class="empty-hint">{{ emptyHint }}</div>
      </slot>
    </div>

    <!-- 列表本体 -->
    <div v-else class="list-body" :class="{ 'multi-select': selectable }">
      <button
        v-for="(item, idx) in items"
        :key="getKey(item, idx)"
        type="button"
        class="list-item"
        :class="{
          selected: selectable && isSelected(item),
          'no-select': selectable,
        }"
        @click="onItemClick(item, idx)"
      >
        <!-- 多选 checkbox -->
        <span v-if="selectable" class="checkbox">
          <span v-if="isSelected(item)" class="check-mark">✓</span>
        </span>

        <div class="item-content">
          <!-- 可选：左侧头像（与桌面端 el-table 列对齐） -->
          <MemberAvatar
            v-if="avatarField"
            :member-id="avatarField(item)"
            :size="40"
            class="item-avatar"
          />

          <div class="item-body">
          <!-- 顶部行（主标题 + 状态） -->
          <div v-if="getField(item, 'title') || getField(item, 'subtitle') || getField(item, 'badge')" class="item-top">
            <div class="item-title-wrap">
              <div v-if="getField(item, 'title')" class="item-title">
                {{ getField(item, 'title') }}
              </div>
              <div v-if="getField(item, 'subtitle')" class="item-subtitle">
                {{ getField(item, 'subtitle') }}
              </div>
            </div>
            <div v-if="getField(item, 'badge')" class="item-badge">
              <span class="badge-tag" :style="badgeStyle(getField(item, 'badge'))">
                {{ getField(item, 'badge').label || getField(item, 'badge') }}
              </span>
            </div>
          </div>

          <!-- 中间字段（key-value 列表） -->
          <div v-if="hasFields(item)" class="item-fields">
            <div
              v-for="field in getMidFields(item)"
              :key="field.key"
              class="field-row"
            >
              <span class="field-key">{{ field.label }}</span>
              <span class="field-value">{{ formatField(item, field) }}</span>
            </div>
          </div>

          <!-- 底部 meta 行 -->
          <div v-if="getField(item, 'meta')" class="item-meta">
            {{ getField(item, 'meta') }}
          </div>

          <!-- 通用具名 slot：每项底部操作区（被 5 个移动端 view 依赖） -->
          <div v-if="$slots['item-actions']" class="item-slot">
            <slot name="item-actions" :item="item" :idx="idx" />
          </div>

          <!-- 动态单条 slot：item-{id} 形式（每行独立内容） -->
          <div v-if="$slots['item-' + getKey(item, idx)]" class="item-slot">
            <slot :name="'item-' + getKey(item, idx)" :item="item" :idx="idx" />
          </div>
          </div><!-- /item-body -->
        </div>

        <!-- 箭头 -->
        <span v-if="!selectable" class="item-arrow">›</span>
      </button>
    </div>

    <!-- 底部加载更多 -->
    <div v-if="items.length > 0" class="list-footer">
      <slot name="footer" :loading="loading" :has-more="hasMore">
        <div v-if="loading" class="loading-state">
          <div class="loading-spinner" />
          <span>加载中...</span>
        </div>
        <div v-else-if="hasMore && !autoLoadDisabled" class="load-more" @click="$emit('load-more')">
          点击加载更多
        </div>
        <div v-else-if="!hasMore && showEndHint" class="end-hint">
          —— 已经到底啦 ——
        </div>
      </slot>
    </div>
  </div>
</template>

<script setup>
/**
 * CardList.vue — 通用卡片列表组件（PR #7 核心）
 *
 * 替代桌面 5 个 el-table（按业务域）
 * - item 字段配置（title / subtitle / badge / fields[] / meta）
 * - 多选模式（selectable + v-model:selected）
 * - 滚动到底自动加载（hasMore）
 * - 完整 slot 体系（header / empty / footer / batch-actions / item-{key}）
 *
 * 用法：
 *   <CardList
 *     :items="meetings"
 *     :field-config="{
 *       title: (m) => m.title,
 *       subtitle: (m) => m.location,
 *       badge: (m) => ({ label: m.status, type: 'success' }),
 *       fields: [
 *         { key: 'time', label: '时间', value: (m) => formatDate(m.start_time) }
 *       ],
 *     }"
 *     selectable
 *     v-model:selected="selected"
 *     @item-click="viewDetail"
 *   />
 */

import { ref, computed, watch } from 'vue'
import MemberAvatar from './MemberAvatar.vue'

const props = defineProps({
  items: { type: Array, default: () => [] },
  title: { type: String, default: '' },
  /** 字段配置对象：每个字段返回 string 或 { label, type } */
  fieldConfig: { type: Object, default: () => ({}) },
  /** 唯一键字段名（默认 id） */
  rowKey: { type: String, default: 'id' },
  /** 可选：左侧头像（与桌面端 el-table 列对齐）。函数返回 memberId（从 memberStore 查 avatar） */
  avatarField: { type: Function, default: null },
  /** 是否支持多选 */
  selectable: { type: Boolean, default: false },
  /** 多选绑定值 */
  selected: { type: Array, default: () => [] },
  /** 是否正在加载 */
  loading: { type: Boolean, default: false },
  /** 是否还有更多（分页/滚动加载） */
  hasMore: { type: Boolean, default: false },
  /** 禁用自动加载 */
  autoLoadDisabled: { type: Boolean, default: false },
  /** 显示"已经到底" */
  showEndHint: { type: Boolean, default: true },
  /** 空态 */
  emptyIcon: { type: String, default: '' },
  emptyTitle: { type: String, default: '' },
  emptyHint: { type: String, default: '' },
})

const emit = defineEmits([
  'update:selected',
  'item-click',
  'load-more',
])

// 当前选中（v-model）
const localSelected = computed(() => props.selected)

// ============================================================================
// 字段取值工具
// ============================================================================
function getKey(item, idx) {
  return item[props.rowKey] ?? idx
}

function getField(item, name) {
  if (!props.fieldConfig || !props.fieldConfig[name]) return null
  const fn = props.fieldConfig[name]
  const raw = typeof fn === 'function' ? fn(item) : item[fn]
  return raw ?? null
}

function hasFields(item) {
  const fields = getField(item, 'fields')
  return Array.isArray(fields) && fields.length > 0
}

function getMidFields(item) {
  return getField(item, 'fields') || []
}

function formatField(item, field) {
  if (typeof field.value === 'function') {
    return field.value(item) ?? ''
  }
  if (typeof field.value === 'string') {
    return item[field.value] ?? ''
  }
  return ''
}

function badgeStyle(badge) {
  if (!badge || typeof badge !== 'object') return {}
  const colorMap = {
    primary: { bg: 'var(--color-primary-bg)', color: 'var(--color-primary)' },
    success: { bg: 'var(--color-success-bg)', color: 'var(--color-success)' },
    warning: { bg: 'var(--color-warning-bg)', color: 'var(--color-warning)' },
    danger: { bg: 'var(--color-danger-bg)', color: 'var(--color-danger)' },
    info: { bg: 'var(--color-info-bg)', color: 'var(--color-info)' },
  }
  const style = colorMap[badge.type] || colorMap.info
  return {
    background: badge.bg || style.bg,
    color: badge.color || style.color,
  }
}

// ============================================================================
// 多选逻辑
// ============================================================================
function isSelected(item) {
  return localSelected.value.some((s) => getKey(s) === getKey(item))
}

function toggleSelect(item) {
  const idx = localSelected.value.findIndex((s) => getKey(s) === getKey(item))
  let newSelected
  if (idx >= 0) {
    newSelected = [...localSelected.value]
    newSelected.splice(idx, 1)
  } else {
    newSelected = [...localSelected.value, item]
  }
  emit('update:selected', newSelected)
}

function clearSelection() {
  emit('update:selected', [])
}

// ============================================================================
// 点击处理
// ============================================================================
function onItemClick(item, idx) {
  if (props.selectable) {
    toggleSelect(item)
  } else {
    emit('item-click', item, idx)
  }
}

// 监听外部 selected 变化（清空等）
watch(
  () => props.selected,
  () => { /* 受控模式，无需处理 */ }
)
</script>

<style scoped>
.card-list-root {
  display: flex;
  flex-direction: column;
}

/* Header */
.list-header {
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
}
.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.list-title {
  margin: 0;
  font-size: 15px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary);
}
.selected-count {
  font-size: 12px;
  color: var(--color-primary);
  font-weight: var(--font-weight-medium, 500);
}

/* 批量操作条 */
.batch-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px var(--mobile-padding-x, 16px);
  background: var(--color-primary-bg);
  color: var(--color-primary);
  position: sticky;
  top: 0;
  z-index: 5;
}
.batch-info {
  font-size: 13px;
  font-weight: var(--font-weight-medium, 500);
}
.batch-count {
  font-size: 16px;
  font-weight: var(--font-weight-bold, 700);
  margin-right: 4px;
}
.batch-actions {
  display: flex;
  gap: 8px;
}

/* 空态 */
.empty-state {
  text-align: center;
  padding: 60px 20px;
}
.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}
.empty-title {
  font-size: 15px;
  color: var(--color-text-regular);
  margin-bottom: 4px;
}
.empty-hint {
  font-size: 12px;
  color: var(--color-text-secondary);
}

/* 列表项 */
.list-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 0 var(--mobile-padding-x, 16px);
}
.list-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  text-align: left;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: background 0.15s, border-color 0.15s;
}
.list-item:active {
  background: var(--color-bg-hover);
}
.list-item.no-select {
  user-select: none;
}
.list-item.selected {
  background: var(--color-primary-bg);
  border-color: var(--color-primary);
}

[data-theme="dark"] .list-item {
  border-color: var(--color-border-base);
}
[data-theme="dark"] .list-item.selected {
  background: rgba(255, 122, 92, 0.15);
  border-color: var(--color-primary);
}

/* Checkbox */
.checkbox {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid var(--color-border);
  background: var(--color-bg-card);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2px;
  transition: all 0.2s;
}
.list-item.selected .checkbox {
  background: var(--color-primary);
  border-color: var(--color-primary);
}
.check-mark {
  /* stylelint-disable-next-line color-named */
  color: white;
  font-size: 12px;
  font-weight: bold;
}

/* Item 内容 */
.item-content {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.item-avatar {
  flex-shrink: 0;
}
.item-body {
  flex: 1;
  min-width: 0;
}

.item-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}
.item-title-wrap {
  flex: 1;
  min-width: 0;
}
.item-title {
  font-size: 15px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
}
.item-subtitle {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 2px;
}
.item-badge {
  flex-shrink: 0;
}
.badge-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: var(--font-weight-medium, 500);
  background: var(--color-bg-page);
  color: var(--color-text-secondary);
}

/* 中间字段 */
.item-fields {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 6px 0;
}
.field-row {
  display: flex;
  font-size: 12px;
  line-height: 1.5;
}
.field-key {
  flex: 0 0 60px;
  color: var(--color-text-secondary);
}
.field-value {
  flex: 1;
  color: var(--color-text-primary);
  overflow-wrap: anywhere;
}

/* Meta */
.item-meta {
  margin-top: 6px;
  font-size: 11px;
  color: var(--color-text-secondary);
}

/* Slot */
.item-slot {
  margin-top: 6px;
}

/* 箭头 */
.item-arrow {
  font-size: 20px;
  color: var(--color-text-placeholder);
  flex-shrink: 0;
  margin-top: 2px;
}

/* Footer */
.list-footer {
  padding: 20px var(--mobile-padding-x, 16px);
  text-align: center;
}
.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 13px;
  color: var(--color-text-secondary);
}
.loading-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid var(--color-border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.load-more {
  padding: 12px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--color-text-regular);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.load-more:active {
  background: var(--color-bg-hover);
}

.end-hint {
  font-size: 12px;
  color: var(--color-text-placeholder);
}
</style>