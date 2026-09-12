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
      <span v-if="item.count" class="tab-strip__count" :class="{ 'is-hot': item.countHot }">{{ item.count }}</span>
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
   批次⑩.77 选型 C「分段药丸」: 一体胶囊容器 + mono 段 + 选中墨实底
   (亮色墨底白字 / 暗色青底墨字), 与 TaskView 分段药丸、输入区模式切换同族。
   ===================================================================== */
.tab-strip {
  --ts-ink: #16232a; --ts-steel: #5a6b6a; --ts-fog: #8ba0a0;
  --ts-hair: #c9d2ca; --ts-teal: #0e766e; --ts-coral: #ef7256;
  --ts-mono: Consolas, 'Courier New', monospace;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 3px;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid var(--ts-hair);
  border-radius: 999px;
  transition: var(--transition-all-fast, all 0.15s ease);
  animation: fadeSlideUp var(--duration-slow, 300ms) var(--ease-out, cubic-bezier(0, 0, 0.2, 1)) both;
}

.tab-strip__item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 16px;
  background: transparent;
  border: none;
  border-radius: 999px;
  cursor: pointer;
  font-family: var(--ts-mono);
  font-size: 12px;
  letter-spacing: 0.1em;
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
}

.tab-strip__item:focus-visible {
  outline: 2px solid var(--ts-teal);
  outline-offset: 1px;
}

.tab-strip__item.is-active {
  background: var(--ts-ink);
  color: #fbfcfb;
  font-weight: 700;
  box-shadow: none;
  transform: none;
}
.tab-strip__item.is-active .tab-strip__no { color: rgba(251, 252, 251, 0.7); }
.tab-strip__item.is-active .tab-strip__icon { color: rgba(251, 252, 251, 0.85); }

.tab-strip__icon {
  display: inline-flex;
  align-items: center;
  line-height: 1;
}

.tab-strip__label {
  display: inline-block;
}

/* 批次⑩.78: 段内 mono 计数 chip (item.count > 0 时显示; countHot = 需关注色) */
.tab-strip__count {
  font-family: var(--ts-mono);
  font-size: 9.5px;
  letter-spacing: 0.04em;
  padding: 1px 7px;
  border-radius: 999px;
  background: rgba(128, 128, 128, 0.14);
  color: var(--ts-steel);
  line-height: 1.4;
}
.tab-strip__count.is-hot {
  background: rgba(163, 84, 63, 0.14);
  color: #a3543f;
}
.tab-strip__item.is-active .tab-strip__count {
  background: rgba(251, 252, 251, 0.22);
  color: inherit;
}
[data-theme="dark"] .tab-strip__count.is-hot {
  background: rgba(248, 152, 152, 0.18);
  color: #f89898;
}
[data-theme="dark"] .tab-strip__item.is-active .tab-strip__count {
  background: rgba(11, 21, 18, 0.22);
  color: inherit;
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

/* underline 变体: 与默认分段药丸同构 (保留 variant 入参兼容旧调用) */
.tab-strip--underline {
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid var(--ts-hair);
  padding: 3px;
  gap: 2px;
  border-radius: 999px;
}

.tab-strip--underline .tab-strip__item {
  border-radius: 999px;
}
</style>

<!-- 铁律 26（v60-v67 第 9 次强化）：dark mode 覆盖必须用非 scoped 块 -->
<style>
[data-theme="dark"] .tab-strip {
  --ts-ink: #dfe9e6; --ts-steel: #9ab0ae; --ts-fog: #6b8286;
  --ts-hair: #27363e; --ts-teal: #35c2a4; --ts-coral: #ef7256;
  background: rgba(255, 255, 255, 0.03);
}
[data-theme="dark"] .tab-strip--underline {
  background: rgba(255, 255, 255, 0.03);
}
/* 批次⑩.77: 分段药丸 dark — 选中青实底墨字 */
[data-theme="dark"] .tab-strip__item.is-active {
  background: #35c2a4;
  color: #0b1512;
}
[data-theme="dark"] .tab-strip__item.is-active .tab-strip__no { color: rgba(11, 21, 18, 0.65); }
[data-theme="dark"] .tab-strip__item.is-active .tab-strip__icon { color: rgba(11, 21, 18, 0.8); }
[data-theme="dark"] .tab-strip__item:hover {
  background: rgba(255, 255, 255, 0.05);
  color: var(--ts-ink);
}
</style>