<script setup lang="ts">
// 设置 — 账号信息 / 模型服务 / 应用信息
import { onMounted, ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import ModelServiceSection from '../components/settings/ModelServiceSection.vue'
import WorkspaceSection from '../components/settings/WorkspaceSection.vue'
import type { AppInfo } from '@shared/types'

const auth = useAuthStore()
const info = ref<AppInfo | null>(null)

onMounted(async () => {
  try {
    info.value = await window.api.app.info()
  } catch {
    /* 状态栏已有兜底提示 */
  }
})

function fmtDate(ts: number): string {
  return new Date(ts).toLocaleString('zh-CN')
}
</script>

<template>
  <div class="settings">
    <h1>设置</h1>

    <section class="card block">
      <h2>本机账号</h2>
      <dl v-if="auth.user">
        <div class="row"><dt>用户名</dt><dd>{{ auth.user.username }}</dd></div>
        <div class="row"><dt>显示名称</dt><dd>{{ auth.user.displayName || '—' }}</dd></div>
        <div class="row"><dt>角色</dt><dd>{{ auth.user.role === 'admin' ? '管理员' : '研究员' }}</dd></div>
        <div class="row"><dt>创建时间</dt><dd>{{ fmtDate(auth.user.createdAt) }}</dd></div>
      </dl>
      <p class="hint">账号管理（创建成员账号 / 修改密码）将在后续里程碑提供；当前阶段本机为单管理员。</p>
    </section>

    <section class="card block">
      <h2>应用</h2>
      <dl v-if="info">
        <div class="row"><dt>名称</dt><dd>{{ info.appName }}</dd></div>
        <div class="row"><dt>版本</dt><dd>v{{ info.version }}</dd></div>
        <div class="row"><dt>平台</dt><dd>{{ info.platform }}</dd></div>
        <div class="row"><dt>数据库路径</dt><dd class="mono">{{ info.dbPath }}</dd></div>
      </dl>
      <p class="hint">所有数据保存在上述本地数据库文件中，可随时备份。</p>
    </section>

    <ModelServiceSection />

    <WorkspaceSection />

    <section class="card block">
      <h2>云端同步</h2>
      <p class="hint">本地库 ⇄ 云端的可选同步将在后续里程碑提供。当前工作台完全本地运行。</p>
    </section>
  </div>
</template>

<style scoped>
.settings {
  max-width: 680px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}
.settings h1 {
  font-size: 20px;
  font-weight: var(--font-weight-semibold);
}
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
  word-break: break-all;
}
.mono {
  font-family: var(--font-family-mono);
  font-size: var(--font-size-xs) !important;
}
.hint {
  margin-top: var(--space-4);
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  line-height: 1.7;
}
</style>
