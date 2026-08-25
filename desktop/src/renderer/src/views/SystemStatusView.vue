<script setup lang="ts">
/**
 * SystemStatusView — Phase 8-M0-H0 系统状态页
 * 展示后端连通 / 路由 / 后台服务状态, 提供手动 ping 验证.
 */
import { ref } from 'vue'
import { useAppConfig } from '../composables/use-app-config'

const { appVersion, environment, dataDir, logDir } = useAppConfig()

interface StatusCheck {
  id: string
  label: string
  description: string
  state: 'pending' | 'ok' | 'warn' | 'fail'
  detail?: string
}

const checks = ref<StatusCheck[]>([
  { id: 'backend', label: '后端连通', description: 'Ping agent.mnb-lab.cn', state: 'pending' },
  { id: 'storage', label: '本地存储', description: 'dataDir 路径可写', state: 'pending' },
  { id: 'log', label: '日志目录', description: 'logDir 路径可写', state: 'pending' },
  { id: 'renderer', label: '渲染层', description: 'Vue 3 + Pinia + Router', state: 'pending' },
  { id: 'preload', label: '预加载', description: 'contextBridge 已挂载 window.api', state: 'pending' }
])

const lastProbeAt = ref<string>('—')

async function probe(): Promise<void> {
  lastProbeAt.value = new Date().toLocaleTimeString()
  // 后端
  checks.value = checks.value.map((c) => c.id === 'backend' ? { ...c, state: 'pending' } : c)
  try {
    const api = (window as unknown as { api?: { ping?: (p?: unknown) => Promise<{ success: boolean; message: string }> } }).api
    if (api?.ping) {
      const pong = await api.ping({ message: 'healthcheck' })
      update('backend', pong.success ? 'ok' : 'fail', pong.message)
    } else {
      update('backend', 'warn', '无 preload contextBridge (测试环境)')
    }
  } catch (err) {
    update('backend', 'fail', err instanceof Error ? err.message : '未知错误')
  }
  // 存储 / 日志 / 渲染层 / 预加载
  update('storage', dataDir.value ? 'ok' : 'warn', dataDir.value || 'dataDir 未设置')
  update('log', logDir.value ? 'ok' : 'warn', logDir.value || 'logDir 未设置')
  update('renderer', 'ok', 'Pinia + Router + Composables 在线')
  update('preload', (window as unknown as Record<string, unknown>).api ? 'ok' : 'warn',
    (window as unknown as Record<string, unknown>).api ? 'window.api 已挂载' : '无 window.api')
}

function update(id: string, state: StatusCheck['state'], detail: string): void {
  checks.value = checks.value.map((c) => c.id === id ? { ...c, state, detail } : c)
}

function badgeClass(state: StatusCheck['state']): string {
  return `system-status__badge system-status__badge--${state}`
}

function badgeLabel(state: StatusCheck['state']): string {
  switch (state) {
    case 'pending': return '检测中'
    case 'ok': return '正常'
    case 'warn': return '警告'
    case 'fail': return '异常'
  }
}
</script>

<template>
  <main class="system-status" aria-label="系统状态">
    <header class="system-status__hero">
      <h1 class="system-status__title">系统状态</h1>
      <p class="system-status__subtitle">环境 {{ environment }} · v{{ appVersion }} · 上次检测 {{ lastProbeAt }}</p>
      <button type="button" class="system-status__probe" @click="probe">运行健康检查</button>
    </header>

    <ul class="system-status__list" role="list">
      <li v-for="check in checks" :key="check.id" class="system-status__item">
        <div :class="badgeClass(check.state)">{{ badgeLabel(check.state) }}</div>
        <div class="system-status__copy">
          <strong>{{ check.label }}</strong>
          <span>{{ check.description }}</span>
          <small v-if="check.detail">{{ check.detail }}</small>
        </div>
      </li>
    </ul>
  </main>
</template>

<style scoped>
.system-status {
  display: grid;
  gap: var(--research-space-5);
  max-width: var(--research-content-max-width);
  margin-inline: auto;
  padding: var(--research-page-gutter);
  min-width: 0;
  overflow-x: clip;
}
.system-status__hero { display: grid; gap: var(--research-space-2); padding: var(--research-space-5); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-panel); background: var(--research-bg-card); }
.system-status__title { margin: 0; font-size: var(--research-text-page-title); font-weight: var(--research-font-weight-bold); color: var(--research-text-primary); }
.system-status__subtitle { margin: 0; color: var(--research-text-secondary); font-size: var(--research-text-sm); font-family: var(--research-font-scientific); }
.system-status__probe { justify-self: start; padding: var(--research-space-2) var(--research-space-4); border: 0; border-radius: var(--research-radius-button); background: var(--research-primary-500); color: var(--research-text-inverse); font: inherit; font-weight: var(--research-font-weight-semibold); cursor: pointer; transition: background var(--research-duration-fast) var(--research-ease-standard); }
.system-status__probe:hover { background: var(--research-primary-600); }
.system-status__probe:focus-visible { outline: none; box-shadow: var(--research-shadow-focus-primary); }
.system-status__list { list-style: none; padding: 0; margin: 0; display: grid; gap: var(--research-space-3); }
.system-status__item { display: grid; grid-template-columns: 80px 1fr; gap: var(--research-space-4); align-items: center; padding: var(--research-space-3) var(--research-space-4); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-card); background: var(--research-bg-card); }
.system-status__copy { display: grid; gap: 2px; min-width: 0; }
.system-status__copy strong { color: var(--research-text-primary); font-size: var(--research-text-card-title); }
.system-status__copy span { color: var(--research-text-secondary); font-size: var(--research-text-sm); }
.system-status__copy small { color: var(--research-text-muted); font-size: var(--research-text-xs); font-family: var(--research-font-scientific); word-break: break-all; }
.system-status__badge { display: grid; place-items: center; padding: var(--research-space-1) var(--research-space-2); border-radius: var(--research-radius-pill); font-size: var(--research-text-xs); font-weight: var(--research-font-weight-semibold); }
.system-status__badge--pending { background: var(--research-bg-panel); color: var(--research-text-secondary); }
.system-status__badge--ok { background: var(--research-success-50); color: var(--research-success-700); }
.system-status__badge--warn { background: var(--research-warning-50); color: var(--research-warning-700); }
.system-status__badge--fail { background: var(--research-danger-50); color: var(--research-danger-600); }
@media (max-width: 1480px) {
  .system-status__item { grid-template-columns: 64px 1fr; }
}
</style>
