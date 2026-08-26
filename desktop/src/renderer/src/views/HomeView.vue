<script setup lang="ts">
// HomeView — Phase 13: 重设计为 research-design-tokens 风格 (与 LoginView 一致)
// 之前: 暗色简陋 (#0f172a/#f97316). 现在: paper + teal + instrument 配色, 与登录页 + research 主题统一.

import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useUserStore } from '../stores/user'
import { useAppStore } from '../stores/app'
import { isAdminRole } from '@shared/auth-types'

const router = useRouter()
const authStore = useAuthStore()
const userStore = useUserStore()
const appStore = useAppStore()

const displayName = computed(() => userStore.profile?.name ?? '?')
const username = computed(() => userStore.profile?.email ?? userStore.profile?.phone ?? 'no-contact')
const isAdmin = computed(() => isAdminRole(userStore.profile?.role))
const grade = computed(() => userStore.profile?.grade ?? '未知')
const researchArea = computed(() => userStore.profile?.research_area ?? '未填写')
const backendUrl = computed(() => appStore.backendUrl)

async function onLogout(): Promise<void> {
  await authStore.logout()
  await router.push({ name: 'login' })
}
function onEnter(name: 'data-snapshot' | 'web-history' | 'research-dashboard'): void {
  void router.push({ name })
}
</script>

<template>
  <main class="home-root">
    <header class="home-header">
      <div class="home-header__brand">
        <span class="home-header__mark" aria-hidden="true">∿</span>
        <div>
          <p class="home-header__eyebrow">MicroBubble Lab</p>
          <h1 class="home-header__title">{{ displayName }}</h1>
        </div>
      </div>
      <button class="home-logout" type="button" @click="onLogout">登出</button>
    </header>

    <section class="home-card home-card--primary">
      <p class="home-card__kicker">科研驾驶舱</p>
      <h2 class="home-card__title">让每一次实验，沉淀为可用的研究。</h2>
      <p class="home-card__copy">
        本地科研系统已就绪 · 离线数据存储 ·
        <span v-if="isAdmin" class="home-card__badge">admin</span>
        <span v-else class="home-card__badge home-card__badge--muted">member</span>
      </p>
      <div class="home-cta">
        <button class="home-cta__primary" type="button" @click="onEnter('research-dashboard')">
          进入科研驾驶舱
        </button>
        <button class="home-cta__ghost" type="button" @click="onEnter('web-history')">
          查看 Web 历史
        </button>
      </div>
    </section>

    <section class="home-card">
      <p class="home-card__kicker">Phase 11: Web 历史数据</p>
      <h3 class="home-card__subtitle">从网页端 PG 同步到本地 SQLite</h3>
      <p class="home-card__copy home-card__copy--sm">单向只读迁移, 完成后桌面端本地独立运行. 编辑不同步回 web.</p>
      <div class="home-actions">
        <button class="home-action" type="button" @click="onEnter('data-snapshot')">
          <span class="home-action__icon" aria-hidden="true">↓</span>
          <span class="home-action__label">数据快照</span>
          <span class="home-action__hint">触发拉取 + 进度</span>
        </button>
        <button class="home-action" type="button" @click="onEnter('web-history')">
          <span class="home-action__icon" aria-hidden="true">▣</span>
          <span class="home-action__label">查看 Web 历史</span>
          <span class="home-action__hint">7 个表只读浏览</span>
        </button>
      </div>
    </section>

    <section class="home-card">
      <p class="home-card__kicker">账户与安全</p>
      <dl class="home-dl">
        <div class="home-dl__row">
          <dt>用户名 / 邮箱</dt>
          <dd>{{ username }}</dd>
        </div>
        <div class="home-dl__row">
          <dt>级别</dt>
          <dd>{{ grade }}</dd>
        </div>
        <div class="home-dl__row">
          <dt>研究方向</dt>
          <dd>{{ researchArea }}</dd>
        </div>
        <div class="home-dl__row">
          <dt>后端</dt>
          <dd><code>{{ backendUrl }}</code></dd>
        </div>
      </dl>
      <p class="home-card__copy home-card__copy--sm home-card__copy--muted">
        access_token 仅主进程内存, refresh_token safeStorage 加密, JWT exp 自动计算过期.
        localStorage / sessionStorage / IndexedDB 永不含 token. 业务模块禁止直连 axios, 统一经 window.api.api.request.
      </p>
    </section>
  </main>
</template>

<style scoped>
.home-root {
  min-height: 100vh;
  padding: clamp(24px, 4vw, 56px);
  background: radial-gradient(circle at 88% 12%, var(--research-teal-50, #e7f3ef), transparent 32%), var(--research-mist-50, #f5f7fa);
  color: var(--research-text-primary, #0f172a);
  font-family: var(--research-font-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif);
  box-sizing: border-box;
}

.home-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 32px;
}
.home-header__brand {
  display: flex;
  align-items: center;
  gap: 16px;
}
.home-header__mark {
  display: grid;
  width: 56px;
  height: 56px;
  place-items: center;
  border: 1px solid var(--research-signal-green, #7ed6ad);
  border-radius: 14px;
  color: var(--research-signal-green, #7ed6ad);
  background: rgb(126 214 173 / 8%);
  font-size: 32px;
  line-height: 1;
}
.home-header__eyebrow {
  margin: 0 0 4px;
  color: var(--research-text-secondary, #6b7280);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.home-header__title {
  margin: 0;
  font-size: clamp(24px, 2.4vw, 32px);
  font-weight: 700;
  letter-spacing: -0.025em;
  color: var(--research-text-primary, #0f172a);
}
.home-logout {
  padding: 8px 16px;
  border: 1px solid var(--research-border, #e5e7eb);
  border-radius: 8px;
  background: var(--research-paper-0, #fff);
  color: var(--research-text-secondary, #6b7280);
  cursor: pointer;
  font-size: 13px;
  transition: color 0.15s, border-color 0.15s;
}
.home-logout:hover {
  color: #ef4444;
  border-color: #ef4444;
}

.home-card {
  background: var(--research-paper-0, #fff);
  border: 1px solid var(--research-border, #e5e7eb);
  border-radius: 16px;
  padding: 32px;
  max-width: 720px;
  margin-bottom: 16px;
}
.home-card--primary {
  background: linear-gradient(140deg, var(--research-instrument-900, #1a3742) 0%, #173438 100%);
  color: #e7f3ef;
  border-color: transparent;
}
.home-card__kicker {
  margin: 0 0 8px;
  color: var(--research-text-secondary, #6b7280);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
.home-card--primary .home-card__kicker {
  color: rgb(126 214 173 / 75%);
}
.home-card__title {
  margin: 0 0 12px;
  font-size: clamp(22px, 2vw, 28px);
  font-weight: 700;
  letter-spacing: -0.025em;
  color: var(--research-text-primary, #0f172a);
}
.home-card--primary .home-card__title {
  color: #e7f3ef;
}
.home-card__subtitle {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--research-text-primary, #0f172a);
}
.home-card__copy {
  margin: 0 0 20px;
  color: var(--research-text-secondary, #4b5563);
  font-size: 14px;
  line-height: 1.6;
}
.home-card--primary .home-card__copy {
  color: #c4d4d1;
}
.home-card__copy--sm {
  font-size: 13px;
  margin-bottom: 16px;
}
.home-card__copy--muted {
  color: var(--research-text-secondary, #9ca3af);
}
.home-card__badge {
  display: inline-block;
  margin-left: 8px;
  padding: 2px 8px;
  background: rgb(126 214 173 / 22%);
  color: var(--research-signal-green, #7ed6ad);
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}
.home-card__badge--muted {
  background: rgb(255 255 255 / 8%);
  color: #94a3b8;
}

.home-cta {
  display: flex;
  gap: 12px;
  margin-top: 16px;
}
.home-cta__primary {
  padding: 10px 22px;
  border: none;
  border-radius: 8px;
  background: var(--research-signal-green, #7ed6ad);
  color: var(--research-instrument-900, #1a3742);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, transform 0.05s;
}
.home-cta__primary:hover {
  background: #6bc79e;
}
.home-cta__primary:active {
  transform: translateY(1px);
}
.home-cta__ghost {
  padding: 10px 22px;
  border: 1px solid rgb(126 214 173 / 40%);
  border-radius: 8px;
  background: transparent;
  color: #e7f3ef;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}
.home-cta__ghost:hover {
  background: rgb(126 214 173 / 12%);
}

.home-actions {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  margin-top: 16px;
}
.home-action {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  border: 1px solid var(--research-border, #e5e7eb);
  border-radius: 12px;
  background: var(--research-surface-alt, #f9fafb);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s, background 0.15s;
}
.home-action:hover {
  border-color: var(--research-signal-green, #7ed6ad);
  background: var(--research-paper-0, #fff);
}
.home-action__icon {
  display: grid;
  width: 36px;
  height: 36px;
  place-items: center;
  border-radius: 8px;
  background: rgb(126 214 173 / 16%);
  color: var(--research-signal-green, #1a7a52);
  font-size: 18px;
  flex-shrink: 0;
}
.home-action__label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--research-text-primary, #0f172a);
}
.home-action__hint {
  display: block;
  font-size: 12px;
  color: var(--research-text-secondary, #6b7280);
  margin-top: 2px;
}

.home-dl {
  margin: 0 0 16px;
}
.home-dl__row {
  display: flex;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid var(--research-border-light, #f3f4f6);
  font-size: 13px;
}
.home-dl__row:last-child { border-bottom: none; }
.home-dl__row dt {
  margin: 0;
  color: var(--research-text-secondary, #6b7280);
}
.home-dl__row dd {
  margin: 0;
  color: var(--research-text-primary, #0f172a);
  font-weight: 500;
  text-align: right;
}
.home-dl__row dd code {
  font-family: monospace;
  font-size: 12px;
  background: var(--research-mist-100, #f3f4f6);
  padding: 1px 6px;
  border-radius: 4px;
}
</style>