<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useUserStore } from '../stores/user'
import { useAppStore } from '../stores/app'

const router = useRouter()
const authStore = useAuthStore()
const userStore = useUserStore()
const appStore = useAppStore()

const username = computed(() => userStore.profile?.username ?? '?')
const fullName = computed(() => userStore.profile?.full_name ?? '')
const isAdmin = computed(() => userStore.profile?.is_admin === true)

async function onLogout(): Promise<void> {
  await authStore.logout()
  await router.push({ name: 'login' })
}
</script>

<template>
  <main class="home-root">
    <header>
      <h1>欢迎，{{ username }}</h1>
      <button class="logout" @click="onLogout">登出</button>
    </header>

    <section class="info-card">
      <h2>Phase 1 自检</h2>
      <ul>
        <li>
          <strong>登录状态：</strong>
          <span :class="authStore.isAuthenticated ? 'ok' : 'ng'">
            {{ authStore.isAuthenticated ? '已登录' : '未登录' }}
          </span>
        </li>
        <li>
          <strong>用户：</strong>
          <span>{{ username }}<span v-if="fullName">（{{ fullName }}）</span><span v-if="isAdmin"> · admin</span></span>
        </li>
        <li>
          <strong>后端：</strong>
          <code>{{ appStore.backendUrl }}</code>
        </li>
      </ul>

      <div class="security-info">
        <strong>安全基线：</strong>
        <ul>
          <li>access_token 仅活内存</li>
          <li>refresh_token 由 safeStorage 加密存于 OS Keychain</li>
          <li>localStorage / sessionStorage 永不含 token</li>
          <li>preload contextBridge 仅暴露白名单 window.api.auth.*</li>
        </ul>
      </div>

      <p class="next-hint">
        Phase 2 起步 → P0 模块迁移（任务 / 知识库 / 会议 ...）。等待授权。
      </p>
    </section>
  </main>
</template>

<style scoped>
.home-root {
  min-height: 100vh;
  background: #0f172a;
  color: #e2e8f0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  padding: 2rem;
  box-sizing: border-box;
}
header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}
h1 {
  margin: 0;
  color: #f97316;
  font-size: 1.4rem;
}
.logout {
  background: transparent;
  color: #ef4444;
  border: 1px solid #ef4444;
  padding: 0.4rem 0.8rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
}
.logout:hover {
  background: #ef4444;
  color: #fff;
}
.info-card {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 1.5rem;
  max-width: 640px;
}
.info-card h2 {
  margin: 0 0 1rem;
  font-size: 1.1rem;
}
ul {
  margin: 0;
  padding: 0;
  list-style: none;
}
li {
  padding: 0.4rem 0;
  font-size: 0.9rem;
}
.ok { color: #10b981; }
.ng { color: #ef4444; }
code {
  background: #0f172a;
  padding: 0.1em 0.4em;
  border-radius: 3px;
  font-family: monospace;
  color: #fbbf24;
}
.security-info {
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid #334155;
  font-size: 0.85rem;
}
.security-info ul {
  margin-top: 0.5rem;
  list-style: disc;
  padding-left: 1.5rem;
  color: #94a3b8;
}
.next-hint {
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid #334155;
  font-size: 0.8rem;
  color: #64748b;
}
</style>
