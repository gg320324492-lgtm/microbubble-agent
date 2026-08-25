<script setup lang="ts">
/**
 * BootstrapRecoveryCard — Phase 8-M0-H1
 * 启动失败时的恢复入口, 不可关闭, 提供 重试 / 退出 / 查看日志 三种操作.
 */
import { computed } from 'vue'
import ResearchIcon from '../icons/ResearchIcon.vue'

const props = withDefaults(defineProps<{
  status?: 'loading' | 'ready' | 'failed'
  errorMessage?: string
  storePath?: string
  logDir?: string
}>(), {
  status: 'ready',
  errorMessage: '',
  storePath: '',
  logDir: ''
})

const emit = defineEmits<{
  retry: []
  exit: []
  viewLogs: []
}>()

const isFailed = computed(() => props.status === 'failed')
const isLoading = computed(() => props.status === 'loading')
const showCard = computed(() => isFailed.value)
</script>

<template>
  <section v-if="showCard" class="recovery-card" role="alert" aria-live="assertive" data-testid="bootstrap-recovery-card">
    <div class="recovery-card__icon" aria-hidden="true">
      <ResearchIcon name="error" :size="22" />
    </div>
    <div class="recovery-card__body">
      <h2 class="recovery-card__title">应用启动失败</h2>
      <p class="recovery-card__message">
        初始化过程中遇到未恢复错误, 已记录到日志目录供排查.
      </p>
      <p v-if="errorMessage" class="recovery-card__error" data-testid="bootstrap-error-message">
        {{ errorMessage }}
      </p>
      <ul v-if="storePath || logDir" class="recovery-card__meta">
        <li v-if="storePath"><strong>Store:</strong> <code>{{ storePath }}</code></li>
        <li v-if="logDir"><strong>Logs:</strong> <code>{{ logDir }}</code></li>
      </ul>
      <div class="recovery-card__actions">
        <button type="button" class="recovery-card__button recovery-card__button--primary" data-testid="bootstrap-retry" @click="emit('retry')">
          <ResearchIcon name="running" :size="14" />
          重试启动
        </button>
        <button type="button" class="recovery-card__button recovery-card__button--secondary" data-testid="bootstrap-logs" @click="emit('viewLogs')">
          <ResearchIcon name="document" :size="14" />
          查看日志
        </button>
        <button type="button" class="recovery-card__button recovery-card__button--danger" data-testid="bootstrap-exit" @click="emit('exit')">
          <ResearchIcon name="error" :size="14" />
          退出应用
        </button>
      </div>
    </div>
  </section>

  <div v-else-if="isLoading" class="recovery-loading" role="status" aria-live="polite" data-testid="bootstrap-loading">
    <span class="recovery-loading__dot recovery-loading__dot--1" />
    <span class="recovery-loading__dot recovery-loading__dot--2" />
    <span class="recovery-loading__dot recovery-loading__dot--3" />
    <p class="recovery-loading__text">正在初始化科研工作台...</p>
  </div>
</template>

<style scoped>
.recovery-card {
  display: grid;
  grid-template-columns: 56px 1fr;
  gap: var(--research-space-4);
  max-width: 720px;
  margin: var(--research-space-8) auto;
  padding: var(--research-space-5);
  border: 2px solid var(--research-danger-500);
  border-radius: var(--research-radius-panel);
  background: var(--research-danger-50);
  color: var(--research-text-primary);
}
.recovery-card__icon {
  display: grid;
  width: 56px;
  height: 56px;
  place-items: center;
  border-radius: var(--research-radius-pill);
  background: var(--research-danger-500);
  color: var(--research-text-inverse);
}
.recovery-card__body { display: grid; gap: var(--research-space-3); min-width: 0; }
.recovery-card__title { margin: 0; font-size: var(--research-text-section-title); font-weight: var(--research-font-weight-bold); color: var(--research-danger-600); }
.recovery-card__message { margin: 0; color: var(--research-text-secondary); font-size: var(--research-text-body); }
.recovery-card__error {
  margin: 0;
  padding: var(--research-space-2) var(--research-space-3);
  border-radius: var(--research-radius-sm);
  background: var(--research-bg-card);
  color: var(--research-danger-600);
  font-family: var(--research-font-scientific);
  font-size: var(--research-text-sm);
  word-break: break-all;
}
.recovery-card__meta { display: grid; gap: var(--research-space-1); padding: 0; margin: 0; list-style: none; color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.recovery-card__meta code { font-family: var(--research-font-scientific); word-break: break-all; color: var(--research-text-primary); }
.recovery-card__actions { display: flex; flex-wrap: wrap; gap: var(--research-space-2); margin-block-start: var(--research-space-2); }
.recovery-card__button {
  display: inline-flex;
  align-items: center;
  gap: var(--research-space-1);
  padding: var(--research-space-2) var(--research-space-4);
  border: 1px solid var(--research-border-subtle);
  border-radius: var(--research-radius-button);
  background: var(--research-bg-card);
  color: var(--research-text-primary);
  font: inherit;
  font-weight: var(--research-font-weight-medium);
  cursor: pointer;
  transition: background var(--research-duration-fast) var(--research-ease-standard);
}
.recovery-card__button:hover { background: var(--research-bg-hover); }
.recovery-card__button:focus-visible { outline: none; box-shadow: var(--research-shadow-focus-primary); }
.recovery-card__button--primary { background: var(--research-primary-500); border-color: var(--research-primary-600); color: var(--research-text-inverse); }
.recovery-card__button--primary:hover { background: var(--research-primary-600); }
.recovery-card__button--danger { background: var(--research-danger-500); border-color: var(--research-danger-600); color: var(--research-text-inverse); }
.recovery-card__button--danger:hover { background: var(--research-danger-600); }

.recovery-loading {
  display: grid;
  place-items: center;
  gap: var(--research-space-3);
  padding: var(--research-space-8);
  text-align: center;
}
.recovery-loading__dot { width: 10px; height: 10px; border-radius: var(--research-radius-pill); background: var(--research-primary-500); animation: recovery-bounce 1.2s ease-in-out infinite; }
.recovery-loading__dot--2 { animation-delay: 0.15s; }
.recovery-loading__dot--3 { animation-delay: 0.3s; }
.recovery-loading__text { margin: 0; color: var(--research-text-muted); font-size: var(--research-text-sm); }
@keyframes recovery-bounce {
  0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
  40% { transform: translateY(-8px); opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
  .recovery-loading__dot { animation: none; }
  .recovery-card__button { transition: none; }
}
@media (max-width: 1480px) {
  .recovery-card { grid-template-columns: 1fr; }
  .recovery-card__icon { margin: 0 auto; }
}
</style>
