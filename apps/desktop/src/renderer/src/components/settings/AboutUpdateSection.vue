<script setup lang="ts">
// 设置页「关于与更新」区块（M6-1）— 当前版本 + 检查更新 + 状态/进度 + 安装并重启（提示式）
// 全程不自动安装：下载由用户点击、安装前二次确认。
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UpdateState } from '@shared/types'

const currentVersion = ref('')
const state = ref<UpdateState>({
  status: 'idle',
  version: null,
  percent: 0,
  error: null,
  disabled: false,
  checkedAt: null
})
const autoCheck = ref(true)
const checking = ref(false)
const downloading = ref(false)

let offState: (() => void) | null = null

const statusText = computed(() => {
  const s = state.value
  // 环境不可用（未打包且无更新源，或适配层闸门关闭）必须如实说明，
  // 绝不落入「已是最新版本」——那会把"检查被跳过"伪装成"确实没有新版本"（M6-1 打回项 2）
  if (s.disabled) return '更新检查不可用（开发环境）'
  switch (s.status) {
    case 'checking':
      return '正在检查更新…'
    case 'available':
      return `发现新版本 v${s.version}`
    case 'downloading':
      return `正在下载 v${s.version}…`
    case 'ready':
      return `v${s.version} 已下载完成，可安装`
    case 'error':
      return `检查失败：${s.error ?? '未知错误'}`
    default:
      return s.checkedAt ? `已是最新版本（v${currentVersion.value}）` : '尚未检查'
  }
})

const canInstall = computed(() => state.value.status === 'ready' && !state.value.disabled)

async function load(): Promise<void> {
  try {
    const info = await window.api.app.info()
    currentVersion.value = info.version
  } catch {
    /* 状态栏已有兜底 */
  }
  try {
    autoCheck.value = (await window.api.settings.get('update.autoCheck')) !== false
  } catch {
    /* 默认开 */
  }
  try {
    state.value = await window.api.update.state()
  } catch {
    /* 保持初值 */
  }
}

async function onCheck(): Promise<void> {
  checking.value = true
  try {
    state.value = await window.api.update.check()
    if (state.value.status === 'available') ElMessage.success(`发现新版本 v${state.value.version}`)
    else if (state.value.status === 'error') ElMessage.error(state.value.error ?? '检查失败')
    else ElMessage.info('当前已是最新版本')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '检查失败')
  } finally {
    checking.value = false
  }
}

async function onDownload(): Promise<void> {
  downloading.value = true
  try {
    state.value = await window.api.update.download()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '下载失败')
  } finally {
    downloading.value = false
  }
}

async function onInstall(): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `将退出当前应用并安装 v${state.value.version}，安装完成后自动重新启动。未保存的输入可能丢失。确定继续？`,
      '安装并重启',
      { type: 'warning', confirmButtonText: '安装并重启', cancelButtonText: '稍后' }
    )
  } catch {
    return
  }
  try {
    const started = await window.api.update.install()
    if (!started) ElMessage.warning('当前状态不可安装，请重新检查更新')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '安装失败')
  }
}

async function onAutoSwitch(e: Event): Promise<void> {
  const value = (e.target as HTMLInputElement).checked
  try {
    await window.api.settings.set('update.autoCheck', value)
    autoCheck.value = value
    ElMessage.success(value ? '已开启启动自动检查更新' : '已关闭启动自动检查更新')
  } catch {
    ElMessage.error('保存失败')
  }
}

onMounted(() => {
  load().catch(() => undefined)
  offState = window.api.update.onStateChange((s) => {
    state.value = s
  })
})

onUnmounted(() => {
  offState?.()
})
</script>

<template>
  <section class="card block">
    <h2>关于与更新</h2>
    <div class="row">
      <dt>当前版本</dt>
      <dd data-testid="update-current-version">v{{ currentVersion }}</dd>
    </div>
    <div class="row">
      <dt>更新状态</dt>
      <dd>
        <span data-testid="update-status">{{ statusText }}</span>
        <div v-if="state.status === 'downloading'" class="progress" data-testid="update-progress">
          <div class="progress-bar" :style="{ width: `${state.percent}%` }"></div>
          <span class="progress-text">{{ state.percent }}%</span>
        </div>
      </dd>
    </div>
    <div class="row">
      <dt>操作</dt>
      <dd class="actions">
        <button
          class="mini-btn"
          data-testid="update-check-btn"
          :disabled="checking || state.disabled || state.status === 'checking' || state.status === 'downloading'"
          @click="onCheck"
        >
          {{ checking || state.status === 'checking' ? '检查中…' : '检查更新' }}
        </button>
        <button
          v-if="state.status === 'available'"
          class="mini-btn primary"
          data-testid="update-download-btn"
          :disabled="downloading"
          @click="onDownload"
        >
          {{ downloading ? '下载中…' : '下载更新' }}
        </button>
        <button
          class="mini-btn primary"
          data-testid="update-install-btn"
          :disabled="!canInstall"
          @click="onInstall"
        >
          安装并重启
        </button>
      </dd>
    </div>
    <div class="row">
      <dt>自动检查</dt>
      <dd>
        <label class="switch-label">
          <input type="checkbox" :checked="autoCheck" data-testid="update-auto-switch" @change="onAutoSwitch" />
          启动后自动检查更新（5 秒后后台检查，失败不打扰）
        </label>
      </dd>
    </div>
    <p v-if="state.disabled" class="hint" data-testid="update-disabled-hint">
      更新检查不可用（开发环境）：当前未打包且未指定更新源，electron-updater 会整体跳过检查。
      打包版自动启用；联调时用 MNB_UPDATE_FEED 指向更新源即可。
    </p>
    <p class="hint section-note">
      提示式更新：发现新版本后由你确认下载，安装前再次确认，全程不会自动安装。
    </p>
  </section>
</template>

<style scoped>
.block {
  padding: var(--space-6);
}
.block h2 {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  margin-bottom: var(--space-4);
}
.row {
  display: flex;
  padding: var(--space-2) 0;
  border-bottom: 1px dashed var(--color-border-light);
}
.row dt {
  width: 110px;
  flex-shrink: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}
.row dd {
  color: var(--color-text-regular);
  font-size: var(--font-size-sm);
  flex: 1;
}
.actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.switch-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
}
.mini-btn {
  padding: 5px 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg-card);
  cursor: pointer;
  font-size: var(--font-size-xs);
  color: var(--color-text-regular);
}
.mini-btn:hover:not(:disabled) {
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.mini-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.mini-btn.primary:not(:disabled) {
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.progress {
  position: relative;
  margin-top: var(--space-2);
  height: 14px;
  border-radius: var(--radius-full);
  background: var(--color-bg-page);
  overflow: hidden;
}
.progress-bar {
  height: 100%;
  background: var(--color-primary);
  transition: width 0.2s ease;
}
.progress-text {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  color: var(--color-text-primary);
}
.hint {
  margin-top: var(--space-2);
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  line-height: 1.7;
}
.section-note {
  border-top: none;
}
</style>
