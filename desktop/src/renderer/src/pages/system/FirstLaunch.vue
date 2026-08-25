<script setup lang="ts">
/**
 * FirstLaunch — Phase 8-M1-A
 * 首次启动入口页: 包装 FirstLaunchWizard 组件, 负责持久化 + 路由跳转.
 */
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import FirstLaunchWizard, { type WizardState } from '../../components/system/FirstLaunchWizard.vue'

const router = useRouter()
const lastState = ref<WizardState | null>(null)

async function persistAndComplete(state: WizardState): Promise<void> {
  lastState.value = state
  // 通过 IPC 持久化到 LocalPersistenceAdapter (system namespace)
  try {
    const api = (window as unknown as {
      api?: { app?: { persistenceSave: (n: string, k: string, v: unknown) => Promise<{ ok: true }> } }
    }).api
    if (api?.app?.persistenceSave) {
      await api.app.persistenceSave('system', 'firstLaunchCompleted', { value: true })
      await api.app.persistenceSave('system', 'selectedMode', { value: state.mode })
      await api.app.persistenceSave('system', 'dataDirectory', { value: state.dataDirectory })
    }
  } catch {
    // 持久化失败不阻塞完成
  }
  await router.push({ name: 'research-dashboard' })
}

function onCancel(): void {
  void router.push({ name: 'research-dashboard' })
}
</script>

<template>
  <main class="first-launch" data-testid="first-launch-page">
    <FirstLaunchWizard
      @complete="persistAndComplete"
      @change-directory="() => undefined"
      @select-mode="() => undefined"
      @cancel="onCancel"
    />
    <p v-if="lastState" class="first-launch__debug">
      上次完成状态: 模式 {{ lastState.mode }} · Demo {{ lastState.enableDemo ? '已启用' : '未启用' }}
    </p>
  </main>
</template>

<style scoped>
.first-launch { min-height: 100vh; padding: var(--research-page-gutter); background: var(--research-bg-main); }
.first-launch__debug { margin: var(--research-space-3) auto 0; max-width: 720px; padding: var(--research-space-2) var(--research-space-3); border-radius: var(--research-radius-sm); background: var(--research-bg-panel); color: var(--research-text-muted); font-family: var(--research-font-scientific); font-size: var(--research-text-xs); }
</style>
