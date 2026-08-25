<script setup lang="ts">
/**
 * AboutPage — Phase 8-M1-A
 * 显示真实的应用元信息 (从 IPC 拉取, 无硬编码版本字符串).
 */
import { computed, onMounted, ref } from 'vue'
import { useAppConfig } from '../composables/use-app-config'

const { appVersion, environment, dataDir, logDir } = useAppConfig()

interface ApplicationInfo {
  name: string
  version: string
  buildNumber: string
  commitHash: string
  buildTime: string
  channel: 'stable' | 'beta' | 'dev'
  environment: 'production' | 'development'
}

const appInfo = ref<ApplicationInfo | null>(null)

onMounted(async () => {
  try {
    const api = (window as unknown as { api?: { app?: { getInfo?: () => Promise<ApplicationInfo | null> } } }).api
    if (api?.app?.getInfo) appInfo.value = await api.app.getInfo()
  } catch {
    // 静默失败, fallback 到 useAppConfig
  }
})

const productName = computed(() => appInfo.value?.name ?? 'Scientific Research OS')
const version = computed(() => appInfo.value?.version ?? appVersion.value)
const buildNumber = computed(() => appInfo.value?.buildNumber ?? 'unknown')
const commitHash = computed(() => appInfo.value?.commitHash ?? 'unknown')
const buildTime = computed(() => appInfo.value?.buildTime ?? 'unknown')
const channel = computed(() => appInfo.value?.channel ?? 'dev')
const envLabel = computed(() => appInfo.value?.environment ?? environment.value)
const channelLabel = computed(() => {
  const map = { stable: '稳定版', beta: 'Beta 通道', dev: '开发版' } as const
  return map[channel.value]
})

const sections = computed(() => [
  {
    title: '应用信息',
    items: [
      { label: '产品名', value: productName.value },
      { label: '版本号', value: `v${version.value}` },
      { label: '构建号', value: buildNumber.value },
      { label: '提交哈希', value: commitHash.value },
      { label: '构建时间', value: buildTime.value },
      { label: '发布通道', value: `${channelLabel.value} (${channel.value})` },
      { label: '运行环境', value: envLabel.value }
    ]
  },
  {
    title: '本地存储',
    items: [
      { label: '数据目录', value: dataDir.value || '(开发环境未指定)' },
      { label: '日志目录', value: logDir.value || '(开发环境未指定)' }
    ]
  },
  {
    title: '构建信息',
    items: [
      { label: '运行时', value: 'Electron 32 + Vue 3.5 + TypeScript 5.6' },
      { label: '打包工具', value: 'electron-vite + electron-builder' },
      { label: '分发平台', value: 'Windows (NSIS) · macOS (dmg) · Linux (AppImage)' },
      { label: '许可证', value: 'UNLICENSED (内部科研使用)' }
    ]
  }
])
</script>

<template>
  <main class="about" aria-label="关于">
    <header class="about__hero">
      <h1 class="about__title">关于 {{ productName }}</h1>
      <p class="about__subtitle">Scientific Research OS · 微纳米气泡课题组内部科研工作台 · v{{ version }} · {{ buildNumber }}</p>
    </header>

    <section v-for="section in sections" :key="section.title" class="about__section" :aria-label="section.title">
      <h2 class="about__section-title">{{ section.title }}</h2>
      <dl class="about__list">
        <div v-for="item in section.items" :key="item.label" class="about__row">
          <dt class="about__label">{{ item.label }}</dt>
          <dd class="about__value">{{ item.value }}</dd>
        </div>
      </dl>
    </section>
  </main>
</template>

<style scoped>
.about {
  display: grid;
  gap: var(--research-space-6);
  max-width: var(--research-content-max-width);
  margin-inline: auto;
  padding: var(--research-page-gutter);
  min-width: 0;
  overflow-x: clip;
}
.about__hero {
  display: grid;
  gap: var(--research-space-2);
  padding: var(--research-space-6);
  border: 1px solid var(--research-border-subtle);
  border-radius: var(--research-radius-panel);
  background: linear-gradient(135deg, var(--research-bg-card) 0%, var(--research-primary-50) 100%);
}
.about__title { margin: 0; font-size: var(--research-text-page-title); font-weight: var(--research-font-weight-bold); color: var(--research-text-primary); }
.about__subtitle { margin: 0; color: var(--research-text-secondary); font-size: var(--research-text-body); }
.about__section { display: grid; gap: var(--research-space-3); min-width: 0; }
.about__section-title { margin: 0; font-size: var(--research-text-card-title); font-weight: var(--research-font-weight-semibold); color: var(--research-text-primary); }
.about__list { display: grid; gap: var(--research-space-1); margin: 0; }
.about__row {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: var(--research-space-4);
  padding: var(--research-space-3);
  border-block-end: 1px solid var(--research-divider-soft);
}
.about__row:last-child { border-block-end: 0; }
.about__label { color: var(--research-text-muted); font-size: var(--research-text-sm); }
.about__value {
  margin: 0;
  color: var(--research-text-primary);
  font-family: var(--research-font-scientific);
  font-size: var(--research-text-sm);
  word-break: break-all;
}
@media (max-width: 1480px) {
  .about__row { grid-template-columns: 100px 1fr; }
}
</style>
