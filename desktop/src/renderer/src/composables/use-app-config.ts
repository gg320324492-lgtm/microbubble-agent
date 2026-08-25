// AppConfig Composable — Phase 8-M0-H0
// 渲染进程读取主进程注入的 AppConfig (dataDir / logDir / isDemo / version 等).
// Fallback 优先用 import.meta.env 与 vite build 时注入的常量, 避免在测试环境下访问 window.api.
import { ref, computed } from 'vue'
import type { AppConfigShape } from '../shared/config-types'

const APP_FALLBACK: AppConfigShape = {
  backendUrl: 'https://agent.mnb-lab.cn/api/v1',
  appName: 'MicroBubble Desktop',
  appVersion: '0.1.0',
  environment: 'development',
  dataDir: '',
  logDir: '',
  cacheDir: '',
  isDemo: false,
  windowMinWidth: 1024,
  windowMinHeight: 640
}

const configState = ref<AppConfigShape>(APP_FALLBACK)
const loaded = ref(false)

export function useAppConfig() {
  async function load(): Promise<void> {
    if (loaded.value) return
    try {
      // window.api 由 preload 注入; 在测试环境可能不存在
      const api = (window as unknown as { api?: { app?: { getConfig?: () => Promise<AppConfigShape | null> } } }).api
      const cfg = api?.app?.getConfig ? await api.app.getConfig() : null
      if (cfg) {
        configState.value = { ...APP_FALLBACK, ...cfg }
      }
    } catch {
      // 静默失败, 使用 fallback
    } finally {
      loaded.value = true
    }
  }

  return {
    config: computed(() => configState.value),
    isDemo: computed(() => configState.value.isDemo),
    appVersion: computed(() => configState.value.appVersion),
    environment: computed(() => configState.value.environment),
    dataDir: computed(() => configState.value.dataDir),
    logDir: computed(() => configState.value.logDir),
    loaded: computed(() => loaded.value),
    load
  }
}
