<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useAppStore } from '../stores/app'

const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()

const form = reactive({ username: '', password: '' })
const error = ref<string | null>(null)
const loading = ref(false)

async function onSubmit(): Promise<void> {
  if (!form.username || !form.password) {
    error.value = '请输入用户名和密码'
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
    <section class="login-shell" aria-labelledby="login-title">
      <aside class="login-identity" data-testid="login-identity" aria-label="Scientific Research OS 产品说明">
        <div class="login-brand">
          <span class="login-brand__mark" aria-hidden="true">∿</span>
          <span>MicroBubble Lab</span>
        </div>
        <p class="login-identity__kicker">Scientific Research OS</p>
        <h1>让每一次实验，沉淀为可用的研究。</h1>
        <p class="login-identity__copy">连接实验设备、原始数据、分析结果与实验记录，在同一套本地科研工作台中持续推进。</p>
        <p class="login-identity__status">
          <span class="login-identity__status-dot" aria-hidden="true"></span>
          本地科研系统已就绪 <b aria-hidden="true">•</b> 离线数据存储
        </p>
      </aside>

      <div class="login-form-panel">
        <form class="login-form" @submit.prevent="onSubmit">
          <p class="login-form__eyebrow">欢迎回来</p>
          <h2 id="login-title">进入科研工作台</h2>
          <p class="login-form__lede">请使用你的本地科研账号登录。</p>

          <label for="login-username">用户名</label>
          <input id="login-username" v-model="form.username" type="text" autocomplete="username" :disabled="loading" placeholder="例如：researcher_01" />

          <label for="login-password">密码</label>
          <input id="login-password" v-model="form.password" type="password" autocomplete="current-password" :disabled="loading" placeholder="输入你的密码" />

          <button type="submit" :disabled="loading">{{ loading ? '登录中…' : '安全登录' }}</button>
          <p v-if="error" class="login-form__error" role="alert">{{ error }}</p>
          <p class="login-form__local-note"><span aria-hidden="true">▣</span>账号和实验数据仅保存在本机。首次使用请联系系统管理员创建本地账号。</p>
        </form>
      </div>
    </section>
  </main>
</template>

<style scoped>
.login-root {
  display: grid;
  min-height: 100vh;
  padding: clamp(20px, 4vw, 56px);
  place-items: center;
  background: radial-gradient(circle at 88% 12%, var(--research-teal-50), transparent 30%), var(--research-mist-50);
  color: var(--research-text-primary);
  font-family: var(--research-font-ui);
}

.login-shell {
  display: grid;
  grid-template-columns: minmax(360px, 45%) minmax(420px, 55%);
  width: min(1120px, 100%);
  min-height: 580px;
  overflow: hidden;
  border: 1px solid var(--research-border-subtle);
  border-radius: 22px;
  background: var(--research-paper-0);
  box-shadow: var(--research-shadow-modal);
}

.login-identity {
  position: relative;
  isolation: isolate;
  overflow: hidden;
  padding: 48px;
  color: var(--research-instrument-text);
  background: linear-gradient(145deg, var(--research-instrument-950), var(--research-instrument-900) 60%, #173438);
}

.login-identity::before {
  position: absolute;
  inset: 0;
  z-index: -1;
  content: '';
  opacity: 0.34;
  background-image: linear-gradient(rgb(126 214 173 / 21%) 1px, transparent 1px), linear-gradient(90deg, rgb(126 214 173 / 21%) 1px, transparent 1px);
  background-size: 32px 32px;
  mask-image: linear-gradient(to bottom, #000, transparent 78%);
}

.login-identity::after {
  position: absolute;
  z-index: -1;
  right: -180px;
  bottom: -200px;
  width: 420px;
  height: 420px;
  content: '';
  border: 1px solid rgb(126 214 173 / 38%);
  border-radius: 50%;
  box-shadow: 0 0 0 46px rgb(126 214 173 / 5%), 0 0 0 92px rgb(126 214 173 / 4%);
}

.login-brand {
  display: flex;
  gap: var(--research-space-3);
  align-items: center;
  font-size: 13px;
  font-weight: var(--research-font-weight-bold);
  letter-spacing: 0.02em;
}

.login-brand__mark {
  display: grid;
  width: 38px;
  height: 38px;
  place-items: center;
  border: 1px solid rgb(126 214 173 / 46%);
  border-radius: var(--research-radius-md);
  color: var(--research-signal-green);
  background: rgb(126 214 173 / 7%);
  font-size: 23px;
  line-height: 1;
}

.login-identity__kicker {
  margin: 78px 0 0;
  color: var(--research-instrument-muted);
  font-size: var(--research-text-xs);
  font-weight: var(--research-font-weight-bold);
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.login-identity h1 {
  max-width: 410px;
  margin: var(--research-space-5) 0;
  font-size: clamp(32px, 3vw, 40px);
  line-height: 1.08;
  letter-spacing: -0.035em;
}

.login-identity__copy {
  max-width: 340px;
  margin: 0;
  color: #c4d4d1;
  font-size: 15px;
  line-height: var(--research-line-height-reading);
}

.login-identity__status {
  position: absolute;
  bottom: 42px;
  display: flex;
  gap: var(--research-space-2);
  align-items: center;
  margin: 0;
  color: var(--research-instrument-muted);
  font-size: var(--research-text-sm);
}

.login-identity__status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--research-signal-green);
  box-shadow: 0 0 12px var(--research-signal-green);
}

.login-identity__status b { color: #506b68; }

.login-form-panel {
  display: grid;
  padding: 46px 64px;
  place-items: center;
}

.login-form { width: min(100%, 390px); }

.login-form__eyebrow {
  margin: 0;
  color: var(--research-teal-700);
  font-size: var(--research-text-sm);
  font-weight: var(--research-font-weight-bold);
  letter-spacing: 0.09em;
}

.login-form h2 {
  margin: var(--research-space-3) 0 var(--research-space-2);
  color: var(--research-text-primary);
  font-size: 30px;
  line-height: var(--research-line-height-tight);
  letter-spacing: var(--research-letter-spacing-title);
}

.login-form__lede {
  margin: 0 0 34px;
  color: var(--research-text-secondary);
  font-size: var(--research-text-body);
  line-height: var(--research-line-height-body);
}

.login-form label {
  display: block;
  margin: 18px 0 var(--research-space-2);
  color: var(--research-graphite-700);
  font-size: 13px;
  font-weight: var(--research-font-weight-semibold);
}

.login-form input {
  width: 100%;
  height: 48px;
  border: 1px solid var(--research-border-strong);
  border-radius: var(--research-radius-input);
  padding: 0 var(--research-space-3);
  color: var(--research-text-primary);
  background: var(--research-paper-0);
  font: inherit;
  transition: border-color var(--research-duration-fast) var(--research-ease-standard), box-shadow var(--research-duration-fast) var(--research-ease-standard);
}

.login-form input::placeholder { color: var(--research-text-tertiary); }

.login-form input:focus {
  padding: 0 11px;
  outline: 0;
  border: 2px solid var(--research-teal-700);
  box-shadow: var(--research-shadow-focus-primary);
}

.login-form button {
  width: 100%;
  height: 50px;
  margin-top: var(--research-space-7);
  border: 0;
  border-radius: var(--research-radius-button);
  color: var(--research-text-inverse);
  background: var(--research-teal-700);
  box-shadow: 0 8px 16px rgb(14 118 110 / 20%);
  font: inherit;
  font-weight: var(--research-font-weight-bold);
  cursor: pointer;
  transition: background var(--research-duration-fast) var(--research-ease-standard), transform var(--research-duration-fast) var(--research-ease-standard);
}

.login-form button:hover:not(:disabled) {
  background: var(--research-teal-500);
  transform: translateY(-1px);
}

.login-form button:focus-visible {
  outline: 0;
  box-shadow: var(--research-shadow-focus-primary);
}

.login-form button:disabled,
.login-form input:disabled {
  opacity: var(--research-state-disabled-opacity);
  cursor: not-allowed;
}

.login-form__error {
  margin: var(--research-space-4) 0 0;
  border: 1px solid var(--research-red-100);
  border-radius: var(--research-radius-sm);
  padding: var(--research-space-3);
  color: var(--research-red-600);
  background: var(--research-red-50);
  font-size: var(--research-text-sm);
  line-height: var(--research-line-height-body);
}

.login-form__local-note {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  margin: var(--research-space-5) 0 0;
  border-top: 1px solid var(--research-divider);
  padding-top: var(--research-space-4);
  color: var(--research-text-muted);
  font-size: var(--research-text-sm);
  line-height: 1.55;
}

.login-form__local-note span { color: var(--research-teal-700); }

@media (max-width: 760px) {
  .login-root { padding: 0; place-items: stretch; }
  .login-shell { grid-template-columns: 1fr; min-height: 100vh; border: 0; border-radius: 0; }
  .login-identity { min-height: 250px; padding: 30px; }
  .login-identity__kicker { margin-top: 38px; }
  .login-identity h1 { margin: var(--research-space-4) 0; font-size: 30px; }
  .login-identity__copy { display: none; }
  .login-identity__status { bottom: 24px; font-size: 11px; }
  .login-form-panel { padding: 36px 28px; }
}
</style>
