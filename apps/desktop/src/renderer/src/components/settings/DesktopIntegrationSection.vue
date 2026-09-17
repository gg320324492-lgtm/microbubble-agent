<script setup lang="ts">
// 设置页「桌面集成」区块 — 关闭行为开关 + 全局快捷键展示/修改/禁用 + 注册状态反馈
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

const closeToTray = ref(true)
const shortcutInput = ref('')
const shortcutState = ref<{ ok: boolean; error?: string } | null>(null)
const loading = ref(false)
const saving = ref(false)

async function load(): Promise<void> {
  loading.value = true
  try {
    closeToTray.value = (await window.api.settings.get('desktop.closeAction')) !== 'exit'
    const sc = await window.api.settings.get('desktop.globalShortcut')
    shortcutInput.value = typeof sc === 'string' ? sc : 'Ctrl+Alt+M'
    // 触发一次重新应用以获取当前生效状态（无副作用：同值幂等）
    const res = await window.api.desktop.applyShortcut(shortcutInput.value)
    shortcutState.value = { ok: res.ok, error: res.error }
  } catch {
    /* 首次未设置时走默认值 */
  } finally {
    loading.value = false
  }
}

async function onCloseSwitch(e: Event): Promise<void> {
  const value = (e.target as HTMLInputElement).checked ? 'tray' : 'exit'
  try {
    await window.api.settings.set('desktop.closeAction', value)
    closeToTray.value = value === 'tray'
    ElMessage.success(value === 'tray' ? '关闭按钮将最小化到托盘' : '关闭按钮将退出应用')
  } catch {
    ElMessage.error('保存失败')
  }
}

async function applyShortcut(): Promise<void> {
  saving.value = true
  try {
    const res = await window.api.desktop.applyShortcut(shortcutInput.value.trim())
    shortcutState.value = { ok: res.ok, error: res.error }
    if (res.ok) {
      await window.api.settings.set('desktop.globalShortcut', shortcutInput.value.trim())
      ElMessage.success(shortcutInput.value.trim() ? `全局快捷键已生效：${res.accelerator}` : '全局快捷键已禁用')
    } else {
      ElMessage.error(res.error ?? '注册失败')
    }
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '应用失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  load().catch(() => undefined)
})
</script>

<template>
  <section class="card block">
    <h2>桌面集成</h2>
    <div class="row">
      <dt>关闭行为</dt>
      <dd>
        <label class="switch-label">
          <input type="checkbox" :checked="closeToTray" @change="onCloseSwitch" data-testid="close-tray-switch" />
          关闭按钮最小化到托盘（关闭 = 退出应用）
        </label>
      </dd>
    </div>
    <div class="row">
      <dt>全局快捷键</dt>
      <dd>
        <div class="shortcut-row">
          <input
            v-model="shortcutInput"
            class="shortcut-input"
            placeholder="Ctrl+Alt+M"
            data-testid="shortcut-input"
          />
          <button class="mini-btn" data-testid="shortcut-apply" @click="applyShortcut">应用</button>
        </div>
        <p v-if="shortcutState && !shortcutState.ok" class="hint error-text" data-testid="shortcut-error">
          {{ shortcutState.error }}
        </p>
        <p v-else class="hint">如 Ctrl+Alt+M（任意应用前台可呼出/隐藏主窗口）。留空 = 禁用。注册失败会自动降级为禁用。</p>
      </dd>
    </div>
    <p class="hint section-note">以上设置保存在本机数据库，按登录用户隔离。</p>
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
}
.switch-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
}
.shortcut-row {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}
.shortcut-input {
  width: 180px;
  height: 32px;
  padding: 0 var(--space-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-page);
  color: var(--color-text-primary);
  font-family: var(--font-family-mono);
  font-size: var(--font-size-xs);
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
.mini-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.hint {
  margin-top: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  line-height: 1.7;
}
.error-text {
  color: var(--color-danger, #d64545);
}
.section-note {
  border-top: none;
  margin-top: var(--space-2);
}
</style>
