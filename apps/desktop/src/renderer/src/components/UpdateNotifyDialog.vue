<script setup lang="ts">
// DL-7 Part B — 启动期更新通知弹窗：新版本号 + 更新日志正文 + 「立即更新 / 稍后」。
// 与设置页 AboutUpdateSection（M6-1）共用同一状态机与 window.api.update 通道，
// 本组件只做「启动通知」的呈现层：不新增任何检查/下载/安装逻辑，不重造更新轮子。
// 打扰节流：同一版本号「稍后」后 24h 内不再弹；设置页在场时不叠加（避免两套入口打架）。
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import type { UpdateState } from '@shared/types'

const route = useRoute()
const state = ref<UpdateState | null>(null)
const visible = ref(false)
/** 用户已点「立即更新」→ 下载完成（ready）且弹窗仍开着时自动重启安装；关闭弹窗即取消 */
const installArmed = ref(false)
const installing = ref(false)
let offState: (() => void) | null = null

const DISMISS_PREFIX = 'update.notifyDismissed.'
const DAY_MS = 24 * 60 * 60 * 1000

function dismissedAt(version: string): number | null {
  try {
    const raw = localStorage.getItem(DISMISS_PREFIX + version)
    const t = raw ? Number(raw) : NaN
    return Number.isFinite(t) ? t : null
  } catch {
    return null
  }
}

function markDismissed(version: string): void {
  try {
    localStorage.setItem(DISMISS_PREFIX + version, String(Date.now()))
  } catch {
    /* 存不了就退化为本次会话内不弹（visible 已关） */
  }
}

function shouldShowFor(s: UpdateState): boolean {
  if (s.status !== 'available' || !s.version) return false
  const at = dismissedAt(s.version)
  if (at && Date.now() - at < DAY_MS) return false
  if (route.name === 'settings') return false
  return true
}

function refresh(s: UpdateState): void {
  state.value = s
  if (shouldShowFor(s)) visible.value = true
  if (visible.value && s.status === 'ready' && installArmed.value && !installing.value) {
    // 「立即更新」的既定链路收尾：下载完成 → 重启安装（用户已显式授权本次安装）
    void installNow()
  }
}

async function onUpdateClick(): Promise<void> {
  if (state.value?.status !== 'available') return
  installArmed.value = true
  try {
    await window.api.update.download() // resolve 后状态经 onStateChange 推进到 ready/error
  } catch {
    /* 下载失败由 state.error 呈现（download-error），弹窗保持可关 */
  }
}

async function installNow(): Promise<void> {
  installing.value = true
  try {
    const ok = await window.api.update.install() // 成功 = quitAndInstall（应用即将重启）
    if (!ok) {
      // 未处于可安装态（竞态）：解除武装，交还设置页入口
      installing.value = false
      installArmed.value = false
    }
  } catch (e) {
    installing.value = false
    installArmed.value = false
    console.error('[update-notify] 安装失败', e)
  }
}

function onLater(): void {
  if (state.value?.version) markDismissed(state.value.version)
  visible.value = false
  installArmed.value = false
}

function onEsc(e: KeyboardEvent): void {
  if (e.key === 'Escape' && visible.value) onLater()
}

onMounted(async () => {
  window.addEventListener('keydown', onEsc)
  try {
    const s = await window.api.update.state()
    refresh(s)
  } catch {
    state.value = null
  }
  offState = window.api.update.onStateChange((s) => refresh(s))
})
onUnmounted(() => {
  window.removeEventListener('keydown', onEsc)
  offState?.()
})
</script>

<template>
  <div v-if="visible && state" class="upd-mask" data-testid="update-notify-mask" @click.self="onLater">
    <div class="upd-panel" data-testid="update-notify-panel" role="dialog" aria-modal="true" aria-labelledby="update-notify-title">
      <header class="upd-head">
        <h2 id="update-notify-title" class="upd-title">
          发现新版本 <span class="upd-ver" data-testid="update-notify-version">v{{ state.version }}</span>
        </h2>
        <p class="upd-sub">当前版本可更新，日志如下。更新包经课题组 CDN 分发，国内可直达。</p>
      </header>

      <div class="upd-notes" data-testid="update-notify-notes">
        <pre v-if="state.releaseNotes" class="upd-notes-body">{{ state.releaseNotes }}</pre>
        <p v-else class="upd-notes-empty" data-testid="update-notify-notes-empty">本次更新未提供更新日志。</p>
      </div>

      <p v-if="state.status === 'downloading'" class="upd-progress" data-testid="update-notify-progress">
        正在下载更新包… {{ state.percent }}%
      </p>
      <p v-else-if="state.status === 'ready'" class="upd-progress" data-testid="update-notify-ready">
        下载完成，正在重启安装…
      </p>
      <p v-else-if="state.status === 'error' && state.error" class="upd-error" data-testid="update-notify-error">
        {{ state.error }}
      </p>

      <footer class="upd-actions">
        <button
          class="upd-btn upd-btn-primary"
          data-testid="update-notify-update"
          :disabled="state.status !== 'available' || installing"
          @click="onUpdateClick"
        >
          {{
            state.status === 'available'
              ? '立即更新'
              : state.status === 'downloading'
                ? '更新中…'
                : state.status === 'ready'
                  ? '下载完成'
                  : '更新失败'
          }}
        </button>
        <button class="upd-btn" data-testid="update-notify-later" :disabled="installing" @click="onLater">稍后</button>
      </footer>
    </div>
  </div>
</template>

<style scoped>
/* 暖白学院风（M7 令牌），浮层结构与 CommandPalette 同族 */
.upd-mask {
  position: fixed;
  inset: 0;
  z-index: 3000;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
}
.upd-panel {
  width: min(520px, 90vw);
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg, 0 12px 40px rgba(0, 0, 0, 0.25));
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.upd-head {
  padding: var(--space-4) var(--space-5) var(--space-2);
}
.upd-title {
  margin: 0;
  font-size: var(--font-size-lg, 16px);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}
.upd-ver {
  color: var(--color-primary);
}
.upd-sub {
  margin: var(--space-1) 0 0;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
.upd-notes {
  margin: 0 var(--space-5);
  max-height: 40vh;
  overflow: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-page);
}
.upd-notes-body {
  margin: 0;
  padding: var(--space-3) var(--space-4);
  font-family: inherit;
  font-size: var(--font-size-sm);
  line-height: 1.7;
  color: var(--color-text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}
.upd-notes-empty {
  margin: 0;
  padding: var(--space-4);
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}
.upd-progress {
  margin: var(--space-2) var(--space-5) 0;
  font-size: var(--font-size-sm);
  color: var(--color-primary);
}
.upd-error {
  margin: var(--space-2) var(--space-5) 0;
  font-size: var(--font-size-xs);
  color: var(--color-danger);
}
.upd-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  padding: var(--space-4) var(--space-5);
}
.upd-btn {
  padding: 8px 20px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-card);
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.upd-btn:hover:not(:disabled) {
  border-color: var(--color-primary);
}
.upd-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.upd-btn-primary {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
}
.upd-btn-primary:hover:not(:disabled) {
  filter: brightness(1.06);
}
</style>
