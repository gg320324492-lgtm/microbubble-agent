<template>
  <Teleport to="body">
    <Transition :name="transitionName">
      <div
        v-if="modelValue"
        class="share-sheet-overlay"
        role="dialog"
        aria-modal="true"
        aria-label="分享"
        @click.self="close"
      >
        <div class="share-sheet-panel" :style="{ paddingBottom: panelPaddingBottom }">
          <div class="share-sheet-handle" />

          <div v-if="title || description" class="share-sheet-header">
            <h3 v-if="title" class="share-sheet-title">{{ title }}</h3>
            <p v-if="description" class="share-sheet-desc">{{ description }}</p>
          </div>

          <div class="share-sheet-grid">
            <button
              v-for="(item, idx) in availableItems"
              :key="idx"
              type="button"
              class="share-grid-item"
              :disabled="item.disabled"
              :class="{ disabled: item.disabled }"
              :aria-label="item.ariaLabel || item.label"
              :title="item.label"
              @click="onItemClick(item)"
            >
              <span class="share-grid-icon-wrap" :style="{ background: item.bgColor || 'var(--color-primary-bg, #fff1ed)' }">
                <span class="share-grid-icon">{{ item.icon }}</span>
              </span>
              <span class="share-grid-label">{{ item.label }}</span>
            </button>
          </div>

          <button
            type="button"
            class="share-sheet-cancel"
            :aria-label="'取消分享'"
            @click="close"
          >取消</button>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
/**
 * MobileShareSheet.vue — 移动端自定义分享面板 (Web Share API fallback)
 *
 * W68 第 8 批 B-3: Mobile UX v3.2 iOS 分享集成
 *
 * 设计：
 * - 当 navigator.share 不可用 / 用户点击"更多分享"时弹出
 * - 6 个内置图标: 微信 / QQ / 微博 / 复制链接 / 保存图片 / 系统分享
 * - 点击触发回调 (父组件决定具体动作: 比如复制 + ElMessage, 或打开微信 URL scheme)
 * - v-model:show 控制显示
 * - Teleport to body + safe-area inset
 *
 * 用法:
 *   const shareSheet = ref({ show: false, title: '', description: '', data: null })
 *   <MobileShareSheet v-model:show="shareSheet.show" :title="..." @share="onShare" />
 */

import { computed, ref } from 'vue'
import { useHaptic } from '@/composables/chat/useHaptic'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '' },
  description: { type: String, default: '' },
  /** 链接 URL (可选, 用于复制) */
  url: { type: String, default: '' },
  /** 文本 (可选, 用于复制 / 微信分享) */
  text: { type: String, default: '' },
  /** 文件 (可选, 用于保存/分享文件) */
  file: { type: Object, default: null },
  /** 文件名 (file 模式必填) */
  filename: { type: String, default: '' },
  /** 是否显示"系统分享"按钮 (默认 true, 调 navigator.share) */
  showNativeShare: { type: Boolean, default: true },
  /** 隐藏某些 item (按 key 排除): 'wechat', 'qq', 'weibo', 'copy', 'save', 'native' */
  hiddenItems: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue', 'share', 'close'])

const haptic = useHaptic()
const transitionName = ref('share-sheet-up')

// safe-area inset
const panelPaddingBottom = computed(() => {
  if (typeof window === 'undefined') return 'calc(20px + var(--sab, 0px))'
  return 'calc(20px + var(--sab, 0px) + var(--tabbar-height, 56px))'
})

// 颜色映射
function wechatColor() {
  return '#1AAD19'
}
function qqColor() {
  return '#12B7F5'
}
function weiboColor() {
  return '#E6162D'
}
function copyColor() {
  return 'var(--color-primary, #FF7A5C)'
}
function saveColor() {
  return 'var(--color-accent, #FFB347)'
}
function nativeColor() {
  return 'var(--color-info, #909399)'
}

// 可用 item 列表
const availableItems = computed(() => {
  const items = [
    {
      key: 'wechat',
      label: '微信',
      icon: '💬',
      bgColor: wechatColor(),
      ariaLabel: '分享到微信',
      disabled: !props.url && !props.text,
    },
    {
      key: 'qq',
      label: 'QQ',
      icon: '🐧',
      bgColor: qqColor(),
      ariaLabel: '分享到 QQ',
      disabled: !props.url && !props.text,
    },
    {
      key: 'weibo',
      label: '微博',
      icon: '📢',
      bgColor: weiboColor(),
      ariaLabel: '分享到微博',
      disabled: !props.url && !props.text,
    },
    {
      key: 'copy',
      label: '复制链接',
      icon: '🔗',
      bgColor: copyColor(),
      ariaLabel: '复制链接',
      disabled: !props.url,
    },
    {
      key: 'save',
      label: '保存图片',
      icon: '💾',
      bgColor: saveColor(),
      ariaLabel: '保存图片到相册',
      disabled: !props.file,
    },
    {
      key: 'native',
      label: '系统分享',
      icon: '📤',
      bgColor: nativeColor(),
      ariaLabel: '系统分享',
      disabled: !props.showNativeShare,
    },
  ]
  return items.filter((i) => !props.hiddenItems.includes(i.key))
})

function close() {
  emit('update:modelValue', false)
  emit('close')
}

async function onItemClick(item) {
  if (item.disabled) return
  haptic.tap()
  const payload = {
    key: item.key,
    label: item.label,
    url: props.url,
    text: props.text,
    file: props.file,
    filename: props.filename,
  }
  emit('share', payload)
  close()
}
</script>

<style scoped>
.share-sheet-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 9999;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  -webkit-tap-highlight-color: transparent;
}

.share-sheet-panel {
  width: 100%;
  max-width: 600px;
  background: var(--color-bg-card, #ffffff);
  border-top-left-radius: var(--radius-xl, 16px);
  border-top-right-radius: var(--radius-xl, 16px);
  padding: 8px 16px 20px;
  box-shadow: var(--shadow-lg, 0 8px 32px rgba(0, 0, 0, 0.15));
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.share-sheet-handle {
  width: 36px;
  height: 4px;
  background: var(--color-border, #dcdfe6);
  border-radius: 2px;
  margin: 8px auto 0;
}

.share-sheet-header {
  text-align: center;
  padding: 4px 12px;
}
.share-sheet-title {
  font-size: 16px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary);
  margin: 0 0 4px;
}
.share-sheet-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin: 0;
  word-break: break-word;
}

.share-sheet-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px 12px;
  padding: 0 4px;
}

.share-grid-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  background: transparent;
  border: none;
  padding: 4px;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  font-family: inherit;
}
.share-grid-item.disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.share-grid-item:active:not(.disabled) {
  transform: scale(0.96);
}

.share-grid-icon-wrap {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  transition: transform 0.15s ease;
}

.share-grid-icon {
  font-size: 28px;
  filter: brightness(0) invert(1); /* 让 emoji 颜色变为 white on colored bg */
}

.share-grid-label {
  font-size: 12px;
  color: var(--color-text-primary);
  white-space: nowrap;
}

.share-sheet-cancel {
  width: 100%;
  padding: 14px;
  margin-top: 4px;
  border: none;
  border-radius: var(--radius-md, 8px);
  background: var(--color-bg-page, #f5f7fa);
  color: var(--color-text-primary);
  font-size: 15px;
  font-weight: var(--font-weight-medium, 500);
  cursor: pointer;
  font-family: inherit;
  -webkit-tap-highlight-color: transparent;
}
.share-sheet-cancel:active {
  background: var(--color-border-light, #ebeef5);
}

/* 入场动画 */
.share-sheet-up-enter-active,
.share-sheet-up-leave-active {
  transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.2s ease;
}
.share-sheet-up-enter-from,
.share-sheet-up-leave-to {
  transform: translateY(100%);
  opacity: 0;
}
.share-sheet-up-enter-active .share-sheet-panel,
.share-sheet-up-leave-active .share-sheet-panel {
  transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
</style>

<!-- v77 P2.6-B: dark mode 适配 (v60-v67 第 5 次强化) -->
<style>
[data-theme="dark"] .share-sheet-overlay {
  background: rgba(0, 0, 0, 0.7);
}
[data-theme="dark"] .share-sheet-panel {
  background: var(--color-bg-card, #1f1f1f);
  border-top: 1px solid var(--color-border-light, #2c2c2c);
}
[data-theme="dark"] .share-grid-label {
  color: var(--color-text-primary);
}
[data-theme="dark"] .share-sheet-cancel {
  background: var(--color-bg-page, #141414);
  color: var(--color-text-primary);
}
[data-theme="dark"] .share-sheet-cancel:active {
  background: var(--color-border-light, #2c2c2c);
}
</style>
