<script setup lang="ts">
/**
 * AboutPage — Phase 8-M0-H0 关于页
 * 展示应用版本 / 环境 / 数据目录 / 日志目录 / 许可 / 致谢.
 */
import { computed } from 'vue'
import { useAppConfig } from '../composables/use-app-config'

const { config, appVersion, environment, dataDir, logDir } = useAppConfig()

const sections = computed(() => [
  {
    title: '应用信息',
    items: [
      { label: '应用名', value: config.value.appName },
      { label: '版本号', value: `v${appVersion.value}` },
      { label: '环境', value: environment.value },
      { label: '后端地址', value: config.value.backendUrl }
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
      { label: '许可证', value: 'UNLICENSED (内部科研使用)' }
    ]
  }
])
</script>

<template>
  <main class="about" aria-label="关于">
    <header class="about__hero">
      <h1 class="about__title">关于 {{ config.appName }}</h1>
      <p class="about__subtitle">Scientific Research OS · 微纳米气泡课题组内部科研工作台</p>
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
