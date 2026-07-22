<template>
  <div class="mobile-fab-root" @click="close">
    <div v-if="isExpanded" class="mobile-fab-dismiss" aria-hidden="true" />
    <TransitionGroup name="mobile-fab-action" tag="div" class="mobile-fab-actions" :class="{ 'is-expanded': isExpanded }">
      <button
        v-for="(action, index) in actions"
        v-show="isExpanded"
        :key="action.name || index"
        type="button"
        class="mobile-fab-action"
        :class="{ danger: action.danger }"
        :style="{ '--fab-index': index }"
        :aria-label="action.label"
        @click.stop="handleAction(action)"
      >
        <span class="mobile-fab-action-icon" aria-hidden="true">{{ action.icon }}</span>
        <span class="mobile-fab-action-label">{{ action.label }}</span>
      </button>
    </TransitionGroup>

    <LongPressWrapper :delay="600" @longpress="handleLongPress">
      <button
        type="button"
        class="mobile-fab-trigger"
        :class="{ 'is-expanded': isExpanded }"
        aria-label="快速操作"
        :aria-expanded="isExpanded"
        @click.stop="toggle"
      >
        <span aria-hidden="true">{{ isExpanded ? '×' : '+' }}</span>
      </button>
    </LongPressWrapper>
  </div>
</template>

<script setup>
import LongPressWrapper from '@/components/mobile/LongPressWrapper.vue'
import { useMobileFab } from '@/composables/useMobileFab'

const props = defineProps({
  actions: { type: Array, default: () => [] },
})

const { isExpanded, toggle, close, expand } = useMobileFab(props.actions)

function handleLongPress() {
  expand()
}

function handleAction(action) {
  close()
  if (typeof action.handler === 'function') action.handler(action)
}
</script>

<style scoped>
.mobile-fab-root {
  position: fixed;
  right: 20px;
  bottom: calc(80px + env(safe-area-inset-bottom, 0px));
  z-index: 2000;
  width: 56px;
  min-height: 56px;
  pointer-events: none;
}
.mobile-fab-root :deep(.long-press-wrapper),
.mobile-fab-trigger,
.mobile-fab-action { pointer-events: auto; }
.mobile-fab-dismiss {
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: auto;
}
  position: absolute;
  right: 0;
  bottom: 66px;
  display: flex;
  flex-direction: column-reverse;
  align-items: flex-end;
  gap: 10px;
  width: 190px;
}
.mobile-fab-action {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  align-self: flex-end;
  min-height: 40px;
  max-width: 180px;
  padding: 7px 12px 7px 8px;
  border: 1px solid var(--color-border-light);
  border-radius: 22px;
  background: var(--color-bg-card);
  color: var(--color-text-primary);
  box-shadow: var(--shadow-md, 0 6px 18px rgba(28, 25, 23, .15));
  font-size: 13px;
  white-space: nowrap;
  cursor: pointer;
  animation-delay: calc(var(--fab-index) * 45ms);
}
.mobile-fab-action.danger { color: var(--color-danger, #f56c6c); }
.mobile-fab-action-icon {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--color-primary-bg);
  font-size: 15px;
}
.mobile-fab-action-label { overflow: hidden; text-overflow: ellipsis; }
.mobile-fab-trigger {
  display: grid;
  place-items: center;
  width: 56px;
  height: 56px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  color: var(--el-color-white, #fff);
  box-shadow: var(--shadow-lg);
  font-size: 30px;
  line-height: 1;
  cursor: pointer;
  transition: transform var(--duration-fast, 150ms), box-shadow var(--duration-fast, 150ms);
  -webkit-tap-highlight-color: transparent;
}
.mobile-fab-trigger:active { transform: scale(.94); }
.mobile-fab-trigger.is-expanded { transform: rotate(45deg); }
.mobile-fab-trigger.is-expanded:active { transform: rotate(45deg) scale(.94); }
.mobile-fab-enter-active, .mobile-fab-leave-active { transition: opacity 180ms ease, transform 180ms ease; }
.mobile-fab-enter-from, .mobile-fab-leave-to { opacity: 0; transform: translateY(8px) scale(.85); }
@media (prefers-reduced-motion: reduce) {
  .mobile-fab-trigger, .mobile-fab-action { transition: none; animation: none; }
}
</style>

<!-- Dark mode must cross the component boundary. Keep this block unscoped. -->
<style>
[data-theme="dark"] .mobile-fab-action {
  background: var(--color-bg-card);
  border-color: var(--color-border);
  color: var(--color-text-primary);
}
[data-theme="dark"] .mobile-fab-action-icon { background: var(--color-primary-bg); }
</style>
