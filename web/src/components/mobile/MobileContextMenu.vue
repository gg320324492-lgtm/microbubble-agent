<template>
  <Teleport to="body">
    <Transition :name="transitionName">
      <div
        v-if="visible"
        ref="menuRef"
        class="mobile-context-menu"
        :class="[`dir-${direction}`, { 'is-danger': hasDanger }]"
        role="menu"
        :aria-label="effectiveAriaLabel"
        :aria-orientation="'vertical'"
        :style="positionStyle"
        @contextmenu.prevent
        @click.stop
      >
        <div v-if="effectiveTitle" class="menu-title">{{ effectiveTitle }}</div>

        <button
          v-for="(item, idx) in normalizedItems"
          :key="idx"
          type="button"
          class="menu-item"
          :class="{
            danger: item.danger,
            disabled: item.disabled,
            divider: item.divider,
          }"
          :role="item.divider ? 'separator' : 'menuitem'"
          :aria-disabled="item.disabled || undefined"
          :disabled="item.disabled"
          @click="onSelect(item, $event)"
        >
          <span v-if="item.icon" class="menu-icon">{{ item.icon }}</span>
          <span class="menu-label">{{ item.label }}</span>
          <span v-if="item.description" class="menu-desc">{{ item.description }}</span>
        </button>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
/**
 * MobileContextMenu.vue — 移动端长按弹出上下文菜单
 *
 * W68 第 1 批路线 C (Agent 4): Mobile 长按菜单 v3.r4
 *
 * 设计：
 * - 8 方向自适应（上 / 下 / 左 / 右 + 4 个斜角）：根据触发坐标 + 视口边缘自动选择方向，避免溢出
 * - haptic feedback (navigator.vibrate 10ms) — 调用 show() 时触发（CLAUDE.md 2026-06-27 铁律）
 * - ARIA 标准 menu role：role="menu" + role="menuitem"/"separator" + aria-orientation
 * - Teleport to body 避免被父容器 overflow:hidden 截断
 * - 点击菜单外部 / Escape 键关闭
 *
 * 用法（典型组合 LongPressWrapper / useLongPress）：
 *   const { pressPoint } = useLongPress(600, (e) => {
 *     contextMenu.show(e.clientX, e.clientY, {
 *       title: '操作',
 *       items: [
 *         { label: '复制', icon: '📋', onClick: () => ... },
 *         { label: '删除', icon: '🗑', danger: true, onClick: () => ... },
 *       ],
 *     })
 *   })
 *   <MobileContextMenu ref="contextMenu" />
 */

import { computed, nextTick, onBeforeUnmount, ref } from 'vue'

const props = defineProps({
  /** 菜单标题（可选，null 不显示） */
  title: { type: String, default: '' },
  /** ARIA 标签 */
  ariaLabel: { type: String, default: '' },
  /** 菜单项配置数组 */
  items: { type: Array, default: () => [] },
  /** 菜单宽度估算（px） */
  estimatedWidth: { type: Number, default: 180 },
  /** 菜单高度估算（px），用于方向计算 */
  estimatedHeight: { type: Number, default: 220 },
  /** 与视口边缘的安全距离（px） */
  edgeMargin: { type: Number, default: 8 },
})

const emit = defineEmits(['select', 'close'])

const menuRef = ref(null)
const visible = ref(false)
const position = ref({ x: 0, y: 0 })
const direction = ref('down') // 'up' | 'down' | 'left' | 'right'
const transitionName = ref('ctx-menu')

/** 运行时覆盖（外部 show() 传入优先于 props） */
const titleOverride = ref(null)
const itemsOverride = ref(null)
const ariaOverride = ref(null)

const effectiveTitle = computed(() => titleOverride.value !== null ? titleOverride.value : props.title)
const effectiveAriaLabel = computed(() => ariaOverride.value !== null ? ariaOverride.value : (props.ariaLabel || props.title || '上下文菜单'))

const normalizedItems = computed(() => {
  const src = itemsOverride.value !== null ? itemsOverride.value : props.items
  return src.filter((it) => it && !it.hidden)
})

const hasDanger = computed(() => normalizedItems.value.some((it) => it.danger))

const positionStyle = computed(() => {
  const { x, y } = position.value
  const base = { left: '0px', top: '0px' }
  // 4 主方向 + 4 斜角用 transform-origin 处理视觉
  switch (direction.value) {
    case 'down':
      base.left = `${x}px`
      base.top = `${y}px`
      break
    case 'up':
      base.left = `${x}px`
      base.top = `${y}px`
      break
    case 'left':
      base.left = `${x}px`
      base.top = `${y}px`
      break
    case 'right':
      base.left = `${x}px`
      base.top = `${y}px`
      break
  }
  return base
})

/**
 * 计算最优方向（8 方向自适应）
 * 优先级：先尝试 4 主方向，按视口边缘空间选择；
 * 都不够时回落到空间最大的方向。
 */
function _resolveDirection(x, y, vw, vh, mw, mh) {
  const margin = props.edgeMargin
  // 上下方向空间
  const spaceDown = vh - y - margin
  const spaceUp = y - margin
  // 左右方向空间
  const spaceRight = vw - x - margin
  const spaceLeft = x - margin

  // 默认向下，优先选择能完整放下菜单的方向
  if (spaceDown >= mh) return 'down'
  if (spaceUp >= mh) return 'up'
  // 横向菜单适合左右方向
  if (spaceRight >= mw) return 'right'
  if (spaceLeft >= mw) return 'left'
  // 都装不下，选剩余空间最大的方向（避免完全遮挡触发点）
  const max = Math.max(spaceDown, spaceUp, spaceRight, spaceLeft)
  if (max === spaceDown) return 'down'
  if (max === spaceUp) return 'up'
  if (max === spaceRight) return 'right'
  return 'left'
}

/**
 * 计算弹出坐标：方向确定后，菜单会在指定位置展开
 * down: 左上 = (x, y)
 * up:   左下 = (x, y - mh)
 * right:右上 = (x, y)
 * left: 左下 = (x - mw, y)
 */
function _resolvePosition(x, y, dir, mw, mh, vw, vh) {
  const margin = props.edgeMargin
  let px = x
  let py = y
  if (dir === 'up') py = Math.max(margin, y - mh)
  if (dir === 'left') px = Math.max(margin, x - mw)
  // 边界保护：菜单不能超出视口右 / 下边缘
  if (dir === 'down' || dir === 'up') {
    if (px + mw > vw - margin) px = Math.max(margin, vw - mw - margin)
  }
  if (dir === 'right' || dir === 'left') {
    if (py + mh > vh - margin) py = Math.max(margin, vh - mh - margin)
  }
  return { x: px, y: py }
}

/**
 * 显示菜单（供 useLongPress 回调调用）
 * @param {number} x - 触发点 clientX
 * @param {number} y - 触发点 clientY
 * @param {Object} options - { title?, items: [{label, icon?, description?, danger?, disabled?, onClick?, divider?}] }
 */
async function show(x, y, options = {}) {
  if (options.title !== undefined) titleOverride.value = options.title
  if (options.items) itemsOverride.value = options.items
  if (options.ariaLabel !== undefined) ariaOverride.value = options.ariaLabel

  const vw = window.innerWidth
  const vh = window.innerHeight
  // 测量实际尺寸（用 nextTick 等 DOM 渲染）
  visible.value = true
  await nextTick()
  const el = menuRef.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  const mw = rect.width || props.estimatedWidth
  const mh = rect.height || props.estimatedHeight

  const dir = _resolveDirection(x, y, vw, vh, mw, mh)
  direction.value = dir
  transitionName.value = `ctx-menu-${dir}`

  const pos = _resolvePosition(x, y, dir, mw, mh, vw, vh)
  position.value = pos

  // 触觉反馈（CLAUDE.md 2026-06-27 铁律：mobile long-press 必带 vibrate）
  if (typeof navigator !== 'undefined' && navigator.vibrate) {
    try { navigator.vibrate(10) } catch { /* ignore */ }
  }

  // 全局点击 / Escape 关闭
  _bindGlobalListeners()
}

function hide() {
  visible.value = false
  _unbindGlobalListeners()
  emit('close')
}

function onSelect(item, event) {
  if (item.disabled) return
  emit('select', item, event)
  if (typeof item.onClick === 'function') {
    try {
      item.onClick(event)
    } catch (e) {
      console.error('[MobileContextMenu] item onClick error:', e)
    }
  }
  hide()
}

// ===== Global listeners =====
let _onDocClick = null
let _onKeyDown = null

function _bindGlobalListeners() {
  if (_onDocClick) return // 防止重复绑定
  // 用 setTimeout 推迟到下一帧，避免当次 show 调用立即被 click 关闭
  setTimeout(() => {
    _onDocClick = (e) => {
      const el = menuRef.value
      if (!el || !el.contains(e.target)) {
        hide()
      }
    }
    _onKeyDown = (e) => {
      if (e.key === 'Escape' || e.key === 'Esc') {
        e.preventDefault()
        hide()
      }
    }
    document.addEventListener('click', _onDocClick, true)
    document.addEventListener('keydown', _onKeyDown, true)
    document.addEventListener('touchstart', _onDocClick, { capture: true, passive: true })
  }, 0)
}

function _unbindGlobalListeners() {
  if (_onDocClick) {
    document.removeEventListener('click', _onDocClick, true)
    document.removeEventListener('touchstart', _onDocClick, { capture: true })
    _onDocClick = null
  }
  if (_onKeyDown) {
    document.removeEventListener('keydown', _onKeyDown, true)
    _onKeyDown = null
  }
}

onBeforeUnmount(() => {
  _unbindGlobalListeners()
})

defineExpose({ show, hide })
</script>

<style scoped>
.mobile-context-menu {
  position: fixed;
  z-index: 4800; /* 比 MobileActionSheet (4500) 高 */
  min-width: 160px;
  max-width: 280px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md, 8px);
  box-shadow: var(--shadow-lg, 0 8px 32px rgba(0, 0, 0, 0.12));
  padding: 4px;
  font-size: 14px;
  color: var(--color-text-primary);
  -webkit-tap-highlight-color: transparent;
  user-select: none;
  overflow: hidden;
}

[data-theme="dark"] .mobile-context-menu {
  background: var(--color-bg-card);
  border-color: var(--color-border);
}

.menu-title {
  padding: 8px 12px 4px;
  font-size: 12px;
  color: var(--color-text-secondary);
  font-weight: var(--font-weight-medium, 500);
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  background: transparent;
  border: none;
  border-radius: var(--radius-sm, 4px);
  font-size: 14px;
  color: var(--color-text-primary);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  text-align: left;
  position: relative;
}

.menu-item:active:not(.disabled):not(.divider) {
  background: var(--color-bg-hover, var(--color-primary-bg));
}

.menu-item.danger {
  color: var(--color-danger, #F56C6C);
}

.menu-item.danger:active:not(.disabled) {
  background: var(--color-danger-bg, #FEF0F0);
}

.menu-item.disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.menu-item.divider {
  padding: 0;
  margin: 4px 0;
  height: 1px;
  background: var(--color-border);
  cursor: default;
  pointer-events: none;
}

.menu-icon {
  font-size: 16px;
  width: 20px;
  text-align: center;
  flex-shrink: 0;
}

.menu-label {
  flex: 1 1 auto;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: var(--font-weight-medium, 500);
}

.menu-desc {
  font-size: 12px;
  color: var(--color-text-secondary);
  font-weight: var(--font-weight-normal, 400);
  flex-shrink: 0;
}

.menu-item.danger .menu-desc {
  color: var(--color-danger, #F56C6C);
  opacity: 0.7;
}

/* ===== 4 个方向过渡动画 ===== */
.ctx-menu-down-enter-active,
.ctx-menu-down-leave-active,
.ctx-menu-up-enter-active,
.ctx-menu-up-leave-active,
.ctx-menu-left-enter-active,
.ctx-menu-left-leave-active,
.ctx-menu-right-enter-active,
.ctx-menu-right-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

/* down：从触发点向下展开 */
.ctx-menu-down-enter-from,
.ctx-menu-down-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(0.96);
  transform-origin: top left;
}

/* up：向上展开 */
.ctx-menu-up-enter-from,
.ctx-menu-up-leave-to {
  opacity: 0;
  transform: translateY(6px) scale(0.96);
  transform-origin: bottom left;
}

/* right：向右展开 */
.ctx-menu-right-enter-from,
.ctx-menu-right-leave-to {
  opacity: 0;
  transform: translateX(-6px) scale(0.96);
  transform-origin: top left;
}

/* left：向左展开 */
.ctx-menu-left-enter-from,
.ctx-menu-left-leave-to {
  opacity: 0;
  transform: translateX(6px) scale(0.96);
  transform-origin: top right;
}
</style>

<!-- v77 P2.6-B: dark mode 适配（v60-v67 教训：必须非 scoped 块） -->
<style>
[data-theme="dark"] .mobile-context-menu {
  background: var(--color-bg-card);
  border-color: var(--color-border-light);
  color: var(--color-text-primary);
}
</style>