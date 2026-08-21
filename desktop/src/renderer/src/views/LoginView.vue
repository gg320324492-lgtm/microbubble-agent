<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useAppStore } from '../stores/app'

const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()

const form = reactive({
  username: '',
  password: ''
})

const error = ref<string | null>(null)
const loading = ref(false)

async function onSubmit(): Promise<void> {
  if (!form.username || !form.password) {
    error.value = '请输入用户名/邮箱和密码'
    return
  }
  error.value = null
  loading.value = true
  try {
    const result = await authStore.login(form.username, form.password)
    if (result.success) {
      const url = await window.api.auth.getBackendUrl()
      appStore.setBackendUrl(url)
      await router.push({ name: 'home' })
    } else {
      error.value = result.error.message
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login-root">
    <form class="login-card" @submit.prevent="onSubmit">
      <h1>MicroBubble Desktop</h1>
      <p class="hint">Phase 1 登录（access_token 内存，refresh_token safeStorage 加密）</p>

      <label class="field">
        <span>用户名 / 邮箱</span>
        <input
          v-model="form.username"
          type="text"
          autocomplete="username"
          :disabled="loading"
          placeholder="wukongshuo 或 wukongshuo@xxx.com"
        />
      </label>

      <label class="field">
        <span>密码</span>
        <input
          v-model="form.password"
          type="password"
          autocomplete="current-password"
          :disabled="loading"
        />
      </label>

      <button class="submit" type="submit" :disabled="loading">
        {{ loading ? '登录中…' : '登录' }}
      </button>

      <div v-if="error" class="error">{{ error }}</div>

      <p class="footer-hint">
        后端：<code>{{ appStore.backendUrl || '尚未连接' }}</code>
      </p>
    </form>
  </main>
</template>

<style scoped>
.login-root {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: #0f172a;
  color: #e2e8f0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
.login-card {
  width: 360px;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 2rem;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}
h1 {
  margin: 0 0 0.4rem;
  font-size: 1.4rem;
  color: #f97316;
}
.hint {
  margin: 0 0 1.5rem;
  font-size: 0.8rem;
  color: #94a3b8;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-bottom: 1rem;
}
.field span {
  font-size: 0.8rem;
  color: #cbd5e1;
}
.field input {
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 4px;
  padding: 0.5rem 0.7rem;
  color: #f1f5f9;
  font-size: 0.95rem;
}
.field input:focus {
  outline: none;
  border-color: #f97316;
}
.submit {
  width: 100%;
  background: #f97316;
  border: 0;
  color: #fff;
  padding: 0.6rem;
  border-radius: 4px;
  font-size: 0.95rem;
  cursor: pointer;
  transition: background 0.15s;
}
.submit:hover:not(:disabled) {
  background: #ea580c;
}
.submit:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.error {
  margin-top: 1rem;
  padding: 0.6rem 0.8rem;
  background: #7f1d1d;
  border-left: 3px solid #ef4444;
  border-radius: 4px;
  font-size: 0.85rem;
  color: #fee2e2;
}
.footer-hint {
  margin: 1rem 0 0;
  font-size: 0.75rem;
  color: #64748b;
  text-align: center;
}
.footer-hint code {
  background: #0f172a;
  padding: 0.1em 0.4em;
  border-radius: 3px;
  color: #fbbf24;
}
</style>
