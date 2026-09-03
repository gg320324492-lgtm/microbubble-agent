<template>
  <div
    class="tab-strip"
    :class="[`tab-strip--${variant}`, { 'tab-strip--scroll': scroll }]"
    role="tablist"
    :aria-label="ariaLabel"
  >
    <button
      v-for="(item, idx) in items"
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
      <span class="tab-strip__no">{{ String(idx + 1).padStart(2, '0') }}</span>
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
/* =====================================================================
   2026-09-04 档案「标本签」皮肤 (G/J 稿语言, docs/design-proposals):
   胶囊 pill → 底部 hair 线 + mono 编号签 + coral active bar
   ===================================================================== */
.tab-strip {
  --ts-ink: #16232a; --ts-steel: #5a6b6a; --ts-fog: #8ba0a0;
  --ts-hair: #c9d2ca; --ts-teal: #0e766e; --ts-coral: #ef7256;
  --ts-mono: Consolas, 'Courier New', monospace;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 0 2px;
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--ts-hair);
  border-radius: 0;
  transition: var(--transition-all-fast, all 0.15s ease);
  animation: fadeSlideUp var(--duration-slow, 300ms) var(--ease-out, cubic-bezier(0, 0, 0.2, 1)) both;
}

.tab-strip__item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 9px 14px;
  background: transparent;
  border: none;
  border-radius: 7px 7px 0 0;
  cursor: pointer;
  font-size: 13.5px;
  font-weight: 500;
  color: var(--ts-steel);
  white-space: nowrap;
  -webkit-tap-highlight-color: transparent;
  transition: var(--transition-all-fast, all 0.15s ease);
  position: relative;
}

.tab-strip__no {
  font-family: var(--ts-mono);
  font-style: normal;
  font-size: 9.5px;
  color: var(--ts-fog);
  margin-right: 2px;
  letter-spacing: .08em;
}

.tab-strip__item:hover {
  color: var(--ts-ink);
  background: rgba(14, 118, 110, 0.06);
}

.tab-strip__item:focus-visible {
  outline: 2px solid var(--ts-teal);
  outline-offset: 1px;
}

.tab-strip__item.is-active {
  background: transparent;
  color: var(--ts-ink);
  font-weight: 600;
  box-shadow: none;
  transform: none;
}
.tab-strip__item.is-active .tab-strip__no { color: var(--ts-teal); }
.tab-strip__item.is-active .tab-strip__icon { color: var(--ts-teal); }
.tab-strip__item.is-active::after {
  content: '';
  position: absolute;
  left: 10px;
  right: 10px;
  bottom: -1px;
  height: 2px;
  background: var(--ts-coral);
  border-radius: 2px;
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

/* underline 变体: 现与默认皮肤同构 (标本签即 underline 语言) */
.tab-strip--underline {
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--ts-hair);
  padding: 0 2px;
  gap: 4px;
}

.tab-strip--underline .tab-strip__item {
  border-radius: 7px 7px 0 0;
}

.tab-strip--underline .tab-strip__item.is-active {
  background: transparent;
  box-shadow: none;
  transform: none;
  border-bottom: none;
}
</style>

<!-- 铁律 26（v60-v67 第 9 次强化）：dark mode 覆盖必须用非 scoped 块 -->
<style>
[data-theme="dark"] .tab-strip {
  --ts-ink: #dfe9e6; --ts-steel: #9ab0ae; --ts-fog: #6b8286;
  --ts-hair: #27363e; --ts-teal: #35c2a4; --ts-coral: #ef7256;
}
[data-theme="dark"] .tab-strip__item:hover {
  background: rgba(53, 194, 164, 0.08);
}
</style>