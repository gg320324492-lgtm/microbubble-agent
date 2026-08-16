<template>
  <div class="chat-message-actions" :class="modeClass" role="toolbar" :aria-label="ariaLabel">
    <button
      type="button"
      class="action-btn regenerate-btn"
      :aria-label="regenerateLabel"
      :title="regenerateLabel"
      :disabled="regenerating"
      @click.stop="onRegenerateClick"
    >
      <el-icon class="action-icon" aria-hidden="true">
        <component :is="regenerating ? Loading : Refresh" />
      </el-icon>
      <span v-if="mode === 'mobile'" class="action-text">{{ regenerateLabel }}</span>
    </button>
    <button
      type="button"
      class="action-btn copy-btn"
      :aria-label="copyLabel"
      :title="copyLabel"
      :disabled="copying"
      @click.stop="onCopyClick"
    >
      <el-icon class="action-icon" aria-hidden="true">
        <component :is="copying ? Check : CopyDocument" />
      </el-icon>
      <span v-if="mode === 'mobile'" class="action-text">{{ copyLabel }}</span>
    </button>
    <!-- 可视复制反馈 (desktop hover-mode 显示) -->
    <span v-if="copying" class="copy-feedback" role="status">{{ copyFeedback }}</span>
    <!-- 可视重新生成反馈 -->
    <span v-if="regenerating" class="regen-feedback" role="status">{{ regenerateFeedback }}</span>
  </div>
</template>

<script setup lang="ts">
/**
 * ChatMessageActions.vue — 消息气泡操作按钮 (W100 +23)
 *
 * 设计要点:
 * - 仅在 assistant 完成态 (state='idle' && content) 时显示
 * - 桌面端 mode='desktop': hover 才显示 (透明度 0→1, 200ms 渐显)
 * - 移动端 mode='mobile': 始终显示, tap 区域 ≥ 44px
 * - 与 FeedbackButtons 风格统一 (icon + tooltip + 视觉一致性)
 *
 * a11y:
 * - role="toolbar" + aria-label 标识按钮组
 * - 单按钮 aria-label/title 描述
 * - 键盘 Tab + Enter (button 原生)
 * - 复制中状态 aria-live 通过 .copy-feedback role="status"
 */

import { computed, ref } from 'vue'
import { Refresh, CopyDocument, Check, Loading } from '@element-plus/icons-vue'

const props = defineProps({
  /** 模式: desktop (hover 显示) / mobile (始终显示) */
  mode: { type: String, default: 'desktop', validator: (v: string) => ['desktop', 'mobile'].includes(v) },
  /** 当前消息 id (用于埋点/调试) */
  messageId: { type: [String, Number], default: null },
})

const emit = defineEmits<{
  regenerate: []
  copy: []
}>()

const regenerating = ref(false)
const copying = ref(false)
const copyFeedback = ref('已复制')
const regenerateFeedback = ref('正在重新生成...')

const ariaLabel = computed(() => '消息操作工具栏')

const modeClass = computed(() => `mode-${props.mode}`)

const regenerateLabel = computed(() => (regenerating.value ? regenerateFeedback.value : '重新生成回答'))
const copyLabel = computed(() => (copying.value ? copyFeedback.value : '复制消息内容'))

function onRegenerateClick() {
  if (regenerating.value) return
  regenerating.value = true
  regenerateFeedback.value = '正在重新生成...'
  try {
    emit('regenerate')
  } catch (e) {
    regenerating.value = false
    // eslint-disable-next-line no-console
    console.error('[ChatMessageActions] regenerate handler threw', e)
  }
  // 3 秒后自动复位 (UX: 防止误以为卡死; 如果 sendMessage 内部启动新流式, 新气泡会重新挂组件)
  setTimeout(() => {
    regenerating.value = false
  }, 3000)
}

function onCopyClick() {
  if (copying.value) return
  copying.value = true
  copyFeedback.value = '已复制'
  try {
    emit('copy')
  } catch (e) {
    copying.value = false
    // eslint-disable-next-line no-console
    console.error('[ChatMessageActions] copy handler threw', e)
    return
  }
  // 1.5 秒后自动复位 (UX: 短暂反馈即可, 避免长时间绿勾)
  setTimeout(() => {
    copying.value = false
  }, 1500)
}
</script>

<style scoped>
/**
 * ChatMessageActions — 消息气泡操作按钮 (W100 +23)
 *
 * 设计语言对齐 FeedbackButtons:
 * - 暖橙珊瑚色系 + 透明背景
 * - hover 浅珊瑚高光 (--color-primary-alpha-10)
 * - tap 区域满足移动端 44px (mobile) / 桌面 32px (desktop)
 */
.chat-message-actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  position: relative;
}

/* 2026-08-16 #69: 用户要求复制/重新生成按钮**常驻显示** (不 hover), 同时删除 reactions-bar.
   旧规则: hover 才显示 (避免视觉杂乱). 新规则: 常驻 (用户明确要求).
   mobile mode 仍走 line 147 的 opacity:1 */
.chat-message-actions.mode-desktop {
  opacity: 1;
}

/* mobile mode: 始终显示 */
.chat-message-actions.mode-mobile {
  opacity: 1;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-sm, 4px);
  color: var(--color-text-secondary);
  cursor: pointer;
  font-size: 13px;
  line-height: 1;
  transition: background-color 150ms ease, border-color 150ms ease, color 150ms ease;
  /* 默认紧凑桌面尺寸 */
  min-width: 28px;
  height: 28px;
  padding: 0 6px;
}

.action-btn:hover:not(:disabled) {
  background-color: var(--color-primary-alpha-10, rgba(255, 122, 92, 0.1));
  border-color: var(--color-primary-alpha-30, rgba(255, 122, 92, 0.3));
  color: var(--color-primary, #ff7a5c);
}

.action-btn:focus-visible {
  outline: 2px solid var(--color-primary, #ff7a5c);
  outline-offset: 2px;
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: wait;
}

.action-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  line-height: 1;
  vertical-align: middle;
}

.action-icon :deep(svg) {
  width: 1em;
  height: 1em;
}

.action-text {
  font-size: 12px;
}

/* mobile mode: tap 区域 ≥ 44px */
.chat-message-actions.mode-mobile .action-btn {
  min-width: 44px;
  height: 44px;
  padding: 0 12px;
  font-size: 14px;
}

.chat-message-actions.mode-mobile .action-icon {
  font-size: 18px;
}
/* dark mode: 文字色 + 高亮调整 */
[data-theme='dark'] .action-btn {
  color: var(--color-text-secondary);
}

[data-theme='dark'] .action-btn:hover:not(:disabled) {
  background-color: rgba(255, 122, 92, 0.15);
  color: var(--color-primary, #ff7a5c);
}

/* 反馈文字气泡 (desktop hover 模式下用 absolute 浮在按钮上方) */
.copy-feedback,
.regen-feedback {
  position: absolute;
  bottom: calc(100% + 4px);
  left: 50%;
  transform: translateX(-50%);
  background: var(--color-bg-card, #fff);
  color: var(--color-text-primary);
  font-size: 11px;
  padding: 4px 8px;
  border-radius: var(--radius-sm, 4px);
  box-shadow: var(--shadow-md, 0 2px 8px rgba(0, 0, 0, 0.12));
  white-space: nowrap;
  pointer-events: none;
  z-index: 10;
}

[data-theme='dark'] .copy-feedback,
[data-theme='dark'] .regen-feedback {
  background: var(--color-bg-card, #2a2a2a);
}
</style>