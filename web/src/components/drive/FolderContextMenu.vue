<!--
  FolderContextMenu.vue — Drive 文件夹/根项右键菜单 (v2.9 2026-07-10)

  v2.8 用了 el-dropdown trigger="contextmenu" 但 placement 是相对 trigger 元素位置,
  不是鼠标位置 → 菜单弹在 sidebar 左侧 (整个 trigger 块右边缘) 而非鼠标旁.

  v2.9 重写: 监听 @contextmenu.prevent 捕获 mouse X/Y + 屏幕 viewport 边界检测,
  自定义固定定位 popover. click outside + ESC 关闭.

  Props:
  - items: Array<{label, command, icon?, divided?, disabled?}> 菜单项
  - placement: String 'auto' (默认) | 'top-left' | 'top-right' (手动指定, 调试用)

  Events:
  - @command(cmd)  菜单项被点击, 把 cmd 字符串往上抛
  - @close()  菜单关闭 (click outside / ESC / 选完一项)
-->
<template>
  <span class="folder-menu-slot-wrap" @contextmenu.prevent="handleContextMenu">
    <slot />
  </span>
  <Teleport to="body">
    <Transition name="el-fade-in-linear">
      <ul
        v-if="visible"
        ref="menuRef"
        class="folder-context-menu"
        :style="menuStyle"
        @click.stop
      >
        <li
          v-for="(item, idx) in items"
          :key="item.command"
          class="folder-context-menu-item"
          :class="{
            'is-divided': item.divided,
            'is-disabled': item.disabled
          }"
          @click="onPick(item)"
        >
          <span class="folder-context-menu-label">{{ item.label }}</span>
        </li>
      </ul>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, nextTick, onBeforeUnmount } from 'vue'

const props = defineProps({
  items: { type: Array, required: true },
  placement: { type: String, default: 'auto' },
})

const emit = defineEmits(['command', 'close'])

const visible = ref(false)
const menuRef = ref(null)
const menuStyle = ref({ top: '0px', left: '0px' })
let menuPosition = { x: 0, y: 0 }

function handleContextMenu(e) {
  e.preventDefault()
  e.stopPropagation()
  menuPosition = { x: e.clientX, y: e.clientY }
  positionMenu()
  visible.value = true
  nextTick(() => attachListeners())
}

function positionMenu() {
  // 估算菜单尺寸 (后续可从 DOM 拿真实尺寸)
  const MENU_WIDTH = 180
  const MENU_HEIGHT = props.items.length * 36 + (props.items.filter(i => i.divided).length * 9) + 8

  // 视口边界检测 (v2.9: 智能 placement)
  const vw = window.innerWidth
  const vh = window.innerHeight
  let x = menuPosition.x
  let y = menuPosition.y
  // 右下越界 → 翻转
  if (x + MENU_WIDTH > vw - 8) x = Math.max(8, vw - MENU_WIDTH - 8)
  if (y + MENU_HEIGHT > vh - 8) y = Math.max(8, vh - MENU_HEIGHT - 8)

  menuStyle.value = {
    top: y + 'px',
    left: x + 'px',
  }
}

function onPick(item) {
  if (item.disabled) return
  emit('command', item.command)
  close()
}

function close() {
  visible.value = false
  detachListeners()
  emit('close')
}

// 关闭监听: 点外部 + ESC
function onDocClick(e) {
  if (menuRef.value && !menuRef.value.contains(e.target)) {
    close()
  }
}
function onEsc(e) {
  if (e.key === 'Escape') close()
}
function onScroll() {
  // 滚动时关闭 (避免菜单错位)
  close()
}

let listenersAttached = false
function attachListeners() {
  if (listenersAttached) return
  listenersAttached = true
  // useCapture: true 让 close 监听在 click 之前触发
  document.addEventListener('click', onDocClick, true)
  document.addEventListener('contextmenu', onDocClick, true)
  document.addEventListener('keydown', onEsc, true)
  window.addEventListener('scroll', onScroll, true)
}
function detachListeners() {
  if (!listenersAttached) return
  listenersAttached = false
  document.removeEventListener('click', onDocClick, true)
  document.removeEventListener('contextmenu', onDocClick, true)
  document.removeEventListener('keydown', onEsc, true)
  window.removeEventListener('scroll', onScroll, true)
}

onBeforeUnmount(() => {
  detachListeners()
})

defineExpose({ open: handleContextMenu, close })
</script>

<style scoped>
.folder-menu-slot-wrap {
  display: contents;  /* 不引入额外 DOM wrapper, 保留原 layout */
}

.folder-context-menu {
  position: fixed;
  z-index: 3000;  /* 高于 el-dialog (2000) + el-tooltip */
  min-width: 160px;
  margin: 0;
  padding: 4px 0;
  list-style: none;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  font-size: var(--font-size-sm);
  font-family: inherit;
  user-select: none;
}

.folder-context-menu-item {
  display: flex;
  align-items: center;
  height: 32px;
  padding: 0 16px;
  cursor: pointer;
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
  line-height: 1;
  transition: background var(--duration-fast) var(--ease-out);
}

.folder-context-menu-item:hover {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.folder-context-menu-item.is-divided {
  margin-top: 4px;
  border-top: 1px solid var(--color-border-light);
  padding-top: 4px;
}

.folder-context-menu-item.is-disabled {
  opacity: 0.5;
  cursor: not-allowed;
  pointer-events: none;
}

.folder-context-menu-label {
  white-space: nowrap;
}

/* dark mode (v2.9: 自定义菜单用 token 跟随, 不依赖 EP dark) */
[data-theme="dark"] .folder-context-menu {
  background: var(--color-bg-card);
  border-color: var(--color-border-base);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
}

[data-theme="dark"] .folder-context-menu-item {
  color: var(--color-text-primary);
}

[data-theme="dark"] .folder-context-menu-item:hover {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

[data-theme="dark"] .folder-context-menu-item.is-divided {
  border-top-color: var(--color-border-base);
}

/* enter animation (v2.9: 简化) */
.el-fade-in-linear-enter-active,
.el-fade-in-linear-leave-active {
  transition: opacity var(--duration-fast) var(--ease-out);
}
.el-fade-in-linear-enter-from,
.el-fade-in-linear-leave-to {
  opacity: 0;
}
</style>
