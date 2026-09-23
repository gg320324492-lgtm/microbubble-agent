<script setup lang="ts">
// 云端数据源引导态（UI1-3 §1 收口）
//
// 背景：M2-3b 时引导态硬编码在 KnowledgeView 里，与空态并存过（外观瑕疵）。
// 现抽成独立组件，**文案全部由主进程集中状态机给出**（guidance.ts），组件零硬编码措辞
// —— 后续统一登录/多端语义变化只改状态机。
interface GateInfo {
  state: 'ready' | 'unbound' | 'offline' | 'expired'
  title: string
  hint: string
  canOpenSettings: boolean
  actionLabel?: string
}

defineProps<{
  /** 引导信息（来自主进程集中状态机） */
  gate: GateInfo
  /** 功能名，仅用于默认图标/标题兜底 */
  feature?: string
}>()

const emit = defineEmits<{ (e: 'open-settings'): void; (e: 'retry'): void }>()

function onOpenSettings(): void {
  emit('open-settings')
}
function onRetry(): void {
  emit('retry')
}
</script>

<template>
  <div class="kb-guide" data-testid="kb-guide">
    <div class="kb-guide-icon" aria-hidden="true">{{ gate.state === 'offline' ? '📡' : '🔑' }}</div>
    <h2 class="kb-guide-title" data-testid="kb-guide-title">{{ gate.title }}</h2>
    <p class="kb-guide-hint" data-testid="kb-guide-hint">{{ gate.hint }}</p>
    <div class="kb-guide-actions">
      <button v-if="gate.canOpenSettings" class="btn-primary" data-testid="kb-guide-settings" @click="onOpenSettings">
        {{ gate.actionLabel || '前往设置 · 账号' }}
      </button>
      <button v-if="gate.state === 'offline'" class="ghost-btn" data-testid="kb-guide-retry" @click="onRetry">
        重试
      </button>
    </div>
  </div>
</template>

<style scoped>
.kb-guide {
  max-width: 520px;
  margin: 10vh auto 0;
  text-align: center;
  padding: var(--space-6);
}
.kb-guide-icon {
  font-size: 40px;
  line-height: 1;
  margin-bottom: var(--space-3);
}
.kb-guide-title {
  margin: 0 0 var(--space-2);
  font-size: var(--font-size-lg);
  color: var(--color-text-primary);
}
.kb-guide-hint {
  margin: 0 0 var(--space-4);
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  line-height: 1.7;
}
.kb-guide-actions {
  display: flex;
  gap: var(--space-2);
  justify-content: center;
}
</style>
