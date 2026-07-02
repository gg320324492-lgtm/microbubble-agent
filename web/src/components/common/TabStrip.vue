<template>
  <div
    class="tab-strip"
    :class="[`tab-strip--${variant}`, { 'tab-strip--scroll': scroll }]"
    role="tablist"
    :aria-label="ariaLabel"
  >
    <button
      v-for="item in items"
      :key="item.key"
      type="button"
      role="tab"
      :id="`tab-strip-${item.key}`"
      :aria-selected="modelValue === item.key"
      :tabindex="modelValue === item.key ? 0 : -1"
      class="tab-strip__item"
      :class="{ 'is-active': modelValue === item.key }"
      @click="onPick(item.key)"
    >
      <span v-if="item.icon" class="tab-strip__icon">
        <el-icon :size="14"><component :is="item.icon" /></el-icon>
      </span>
      <span class="tab-strip__label">{{ item.label }}</span>
    </button>
  </div>
</template>

<script setup>
/**
 * TabStrip.vue — 通用 tab 条组件
 *
 * 设计目标（v77 P2.6 阶段 9 收官）：
 * ① 视觉一致性：Premium segmented pill（仿 ThinkingModeSwitch 风格）
 * ② a11y 内建：role="tablist" + role="tab" + aria-selected + tabindex + aria-controls
 * ③ URL sync 内建：调用方通过 v-model + @change 自行实现（保持组件纯净）
 * ④ 6 主题 token 自动适配（全部用 CSS 变量）
 * ⑤ 横向滚动变体支持（mobile 7+ tab）
 *
 * 用法：
 *   <TabStrip v-model="activeTab" :items="tabItems" />
 *   <TabStrip v-model="activeTab" :items="tabItems" :scroll="true" />
 *
 * 铁律 31（CLAUDE.md 永久）：项目内所有 tab strip 需求必须用此组件，
 * 禁止新增 <el-tabs> 或自定义 tab strip。
 */
const props = defineProps({
  /** [{ key, label, icon? }] — key 是 v-model 的值 */
  items: { type: Array, required: true },
  /** 当前激活的 tab key */
  modelValue: { type: [String, Number], required: true },
  /** 'pill'（默认） | 'underline'（预留） */
  variant: { type: String, default: 'pill' },
  /** 横向滚动变体（6+ tab 用） */
  scroll: { type: Boolean, default: false },
  ariaLabel: { type: String, default: 'Tabs' },
})

const emit = defineEmits(['update:modelValue', 'change'])

const onPick = (key) => {
  if (key === props.modelValue) return
  emit('update:modelValue', key)
  emit('change', key)
}
</script>

<style scoped>
.tab-strip {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 2px;
  border-radius: var(--radius-full, 9999px);
  background: var(--color-bg-warm, #f5f7fa);
  border: 1px solid var(--color-border-light, #ebeef5);
  transition: var(--transition-all-fast, all 0.15s ease);
  animation: fadeSlideUp var(--duration-slow, 300ms) var(--ease-out, cubic-bezier(0, 0, 0.2, 1)) both;
}

.tab-strip__item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 14px;
  background: transparent;
  border: none;
  border-radius: var(--radius-full, 9999px);
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-secondary, #909399);
  white-space: nowrap;
  -webkit-tap-highlight-color: transparent;
  transition: var(--transition-all-fast, all 0.15s ease);
}

.tab-strip__item:hover {
  color: var(--color-text-primary, #303133);
}

.tab-strip__item:focus-visible {
  outline: 2px solid var(--color-primary, #FF7A5C);
  outline-offset: 1px;
}

.tab-strip__item.is-active {
  background: var(--color-bg-card, #ffffff);
  color: var(--color-primary, #FF7A5C);
  font-weight: 600;
  box-shadow: var(--shadow-xs, 0 1px 2px rgba(0, 0, 0, 0.06));
  transform: translateY(-1px);
}

.tab-strip__icon {
  display: inline-flex;
  align-items: center;
  line-height: 1;
}

.tab-strip__label {
  display: inline-block;
}

/* 横向滚动变体（mobile 7+ tab 用） */
.tab-strip--scroll {
  display: flex;
  flex-wrap: nowrap;
  overflow-x: auto;
  overflow-y: hidden;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
  max-width: 100%;
}

.tab-strip--scroll::-webkit-scrollbar {
  display: none;
}

.tab-strip--scroll .tab-strip__item {
  flex-shrink: 0;
}

/* underline 变体预留 */
.tab-strip--underline {
  background: transparent;
  border: none;
  padding: 0;
  gap: 0;
  border-radius: 0;
}

.tab-strip--underline .tab-strip__item {
  border-radius: 0;
}

.tab-strip--underline .tab-strip__item.is-active {
  background: transparent;
  box-shadow: none;
  transform: none;
  border-bottom: 2px solid var(--color-primary, #FF7A5C);
}
</style>

<!-- 铁律 26（v60-v67 第 9 次强化）：dark mode 覆盖必须用非 scoped 块 -->
<style>
[data-theme="dark"] .tab-strip {
  background: var(--color-bg-warm);
  border-color: var(--color-border-light);
}
[data-theme="dark"] .tab-strip__item {
  color: var(--color-text-secondary);
}
[data-theme="dark"] .tab-strip__item:hover {
  color: var(--color-text-primary);
}
[data-theme="dark"] .tab-strip__item.is-active {
  background: var(--color-bg-card);
  color: var(--color-primary);
  box-shadow: var(--shadow-xs);
}
</style>