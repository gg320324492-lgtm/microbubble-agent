<script setup>
/**
 * SessionActions.vue - 会话快捷操作组件 (W100 +28 UI-ARCHIVE)
 *
 * 3 个 action icon：
 *   📌 置顶/取消置顶
 *   🗄️ 归档/恢复
 *   🗑️ 删除（需确认）
 *
 * 两种 mode：
 *   sidebar - hover 显示（桌面侧栏）
 *   inline  - 始终显示（批量操作 bar / 移动端）
 *
 * a11y: 全部 button + aria-label + keyboard (Enter/Space)
 * tap target: 44px (WCAG 2.5.5)
 */
import { FolderOpened, Delete, Top } from '@element-plus/icons-vue'

const props = defineProps({
  session: { type: Object, required: true },
  mode: { type: String, default: 'sidebar' }, // 'sidebar' | 'inline'
})
const emit = defineEmits(['archive', 'delete', 'pin'])

const onPin = () => emit('pin', props.session)
const onArchive = () => emit('archive', props.session)
const onDelete = () => emit('delete', props.session)
</script>

<template>
  <div
    class="session-actions"
    :class="[mode, { 'is-pinned': session.is_pinned, 'is-archived': session.is_archived }]"
    data-testid="session-actions"
  >
    <button
      type="button"
      class="action-btn pin-btn"
      :class="{ active: session.is_pinned }"
      :aria-label="session.is_pinned ? '取消置顶' : '置顶会话'"
      :title="session.is_pinned ? '取消置顶' : '置顶会话'"
      data-testid="action-pin"
      @click.stop="onPin"
    >
      <el-icon><Top /></el-icon>
    </button>
    <button
      type="button"
      class="action-btn archive-btn"
      :class="{ active: session.is_archived }"
      :aria-label="session.is_archived ? '恢复会话' : '归档会话'"
      :title="session.is_archived ? '恢复会话' : '归档会话'"
      data-testid="action-archive"
      @click.stop="onArchive"
    >
      <el-icon><FolderOpened /></el-icon>
    </button>
    <button
      type="button"
      class="action-btn delete-btn danger"
      aria-label="删除会话"
      title="删除会话"
      data-testid="action-delete"
      @click.stop="onDelete"
    >
      <el-icon><Delete /></el-icon>
    </button>
  </div>
</template>

<style scoped>
.session-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}

/* sidebar mode: 默认隐藏,hover session-item 时显示 */
.session-actions.sidebar {
  opacity: 0;
  transition: opacity var(--duration-fast, 150ms) ease;
  pointer-events: none;
}
.session-item:hover .session-actions.sidebar,
.session-actions.sidebar:focus-within {
  opacity: 1;
  pointer-events: auto;
}

/* inline mode: 始终显示 */
.session-actions.inline {
  opacity: 1;
  pointer-events: auto;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: var(--radius-sm, 4px);
  background: transparent;
  cursor: pointer;
  color: var(--color-text-secondary);
  transition: background var(--duration-fast, 150ms), color var(--duration-fast, 150ms);
  -webkit-tap-highlight-color: transparent;
  /* 确保 tap target ≥ 44px (WCAG 2.5.5) - 通过 padding 扩展 */
  position: relative;
}
.action-btn::before {
  content: '';
  position: absolute;
  inset: -8px;
}

.action-btn:hover {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}
.action-btn:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}
.action-btn.active {
  color: var(--color-primary);
}
.action-btn.danger:hover {
  color: var(--color-danger);
  background: rgba(245, 108, 108, 0.1);
}
.action-btn .el-icon {
  font-size: 14px;
}

/* dark mode */
[data-theme="dark"] .action-btn {
  color: var(--color-text-secondary);
}
[data-theme="dark"] .action-btn:hover {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}
[data-theme="dark"] .action-btn.danger:hover {
  color: var(--color-danger);
}
</style>
