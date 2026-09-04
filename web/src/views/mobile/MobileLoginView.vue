<template>
  <div class="mobile-login mg-page">
    <!-- 装饰气泡 (品牌意象: 微纳米气泡上浮) -->
    <div class="bg-decoration" aria-hidden="true">
      <span class="deco-bubble b1" />
      <span class="deco-bubble b2" />
      <span class="deco-bubble b3" />
      <span class="deco-bubble b4" />
    </div>

    <main class="login-main" :style="{ paddingTop: 'calc(60px + var(--sat))' }">
      <div class="logo-section mg-rise">
        <div class="logo-circle">
          <span class="logo-icon">🫧</span>
        </div>
        <h1 class="logo-title">小气助手</h1>
        <p class="logo-subtitle">微纳米气泡课题组的 AI 拍档</p>
      </div>

      <form class="login-form mg-glass-strong mg-rise mg-stagger-2" @submit.prevent="handleLogin">
        <div class="form-field">
          <span class="field-icon">👤</span>
          <input
            ref="usernameInputRef"
            v-model="loginForm.username"
            type="text"
            class="field-input"
            placeholder="用户名"
            autocomplete="username"
            aria-label="用户名"
            title="用户名"
            @input="clearError"
          />
        </div>

        <div class="form-field">
          <span class="field-icon">🔒</span>
          <input
            v-model="loginForm.password"
            :type="showPassword ? 'text' : 'password'"
            class="field-input"
            placeholder="密码"
            autocomplete="current-password"
            aria-label="密码"
            title="密码"
            @input="clearError"
          />
          <button
            type="button"
            class="toggle-password"
            :aria-label="showPassword ? '隐藏密码' : '显示密码'"
            :title="showPassword ? '隐藏密码' : '显示密码'"
            @click="showPassword = !showPassword"
          >{{ showPassword ? '🙈' : '👁' }}</button>
        </div>

        <div v-if="errorMessage" class="error-message">
          ⚠️ {{ errorMessage }}
        </div>

        <button
          type="submit"
          class="login-btn mg-btn-primary"
          :disabled="loading"
        >
          <span v-if="loading" class="loading-spinner" />
          <span>{{ loading ? '登录中...' : '登 录' }}</span>
        </button>

        <div class="login-hint">
          <p>账号由课题组统一签发</p>
        </div>
      </form>

      <footer class="login-foot">
        MICROBUBBLE LAB · AGENT
      </footer>
    </main>
  </div>
</template>

<script setup>
/**
 * MobileLoginView.vue — 移动端登录页
 *
 * PR #8a: 全屏表单（不用 el-dialog + CSS 全屏 hack）
 * 2026-08-31 液态毛玻璃升级 (风格 D):
 * - 极光渐变背景 (.mg-page) + 品牌气泡上浮装饰
 * - 圆角玻璃 logo 磁贴 + 深玻璃表单卡 (.mg-glass-strong)
 * - 紫粉渐变主按钮 (.mg-btn-primary)
 * - 登录逻辑零改动 (仍复用 /api/v1/auth/login)
 */

import { ref, reactive, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()
const usernameInputRef = ref(null)
const loading = ref(false)
const showPassword = ref(false)
const errorMessage = ref('')

const loginForm = reactive({
  username: '',
  password: '',
})

function clearError() {
  if (errorMessage.value) errorMessage.value = ''
}

async function handleLogin() {
  // 基础验证
  if (!loginForm.username.trim()) {
    errorMessage.value = '请输入用户名'
    return
  }
  if (!loginForm.password) {
    errorMessage.value = '请输入密码'
    return
  }
  if (loginForm.password.length < 6) {
    errorMessage.value = '密码长度不能少于6位'
    return
  }

  loading.value = true
  try {
    const res = await axios.post('/api/v1/auth/login', {
      username: loginForm.username.trim(),
      password: loginForm.password,
    })

    const { access_token, refresh_token, user } = res.data

    localStorage.setItem('access_token', access_token)
    localStorage.setItem('refresh_token', refresh_token)
    localStorage.setItem('user_info', JSON.stringify(user))
    axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`

    router.push('/')
  } catch (error) {
    errorMessage.value = error.response?.data?.detail || '登录失败，请重试'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  nextTick(() => usernameInputRef.value?.focus())
})
</script>

<style scoped>
.mobile-login {
  position: fixed;
  inset: 0;
  overflow: hidden;
  z-index: 1000;
}

/* ----- 装饰气泡: 玻璃小球缓浮 (品牌=微纳米气泡) ----- */
.bg-decoration {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}
.deco-bubble {
  position: absolute;
  border-radius: 50%;
  background:
    radial-gradient(circle at 32% 28%, rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 0.18) 45%, rgba(255, 255, 255, 0.05) 70%);
  border: 1px solid rgba(255, 255, 255, 0.75);
  box-shadow: 0 8px 24px rgba(120, 90, 180, 0.12);
  animation: bubble-float 9s ease-in-out infinite;
}
[data-theme="dark"] .deco-bubble {
  background:
    radial-gradient(circle at 32% 28%, rgba(200, 180, 255, 0.35), rgba(140, 110, 220, 0.1) 45%, rgba(140, 110, 220, 0.04) 70%);
  border-color: rgba(168, 150, 224, 0.3);
}
.b1 { width: 110px; height: 110px; top: 9%; right: -28px; animation-delay: 0s; }
.b2 { width: 56px; height: 56px; top: 26%; left: -14px; animation-delay: 1.6s; }
.b3 { width: 30px; height: 30px; bottom: 22%; right: 16%; animation-delay: 3.2s; }
.b4 { width: 74px; height: 74px; bottom: -18px; left: 12%; animation-delay: 4.6s; }
@keyframes bubble-float {
  0%, 100% { transform: translateY(0) scale(1); }
  50% { transform: translateY(-14px) scale(1.04); }
}
@media (prefers-reduced-motion: reduce) {
  .deco-bubble { animation: none; }
}

/* ----- 主区 ----- */
.login-main {
  position: relative;
  z-index: 1;
  min-height: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 40px var(--mobile-padding-x, 20px) calc(40px + var(--sab));
}

/* ----- Logo ----- */
.logo-section {
  text-align: center;
  margin-bottom: 30px;
}
.logo-circle {
  width: 88px;
  height: 88px;
  margin: 0 auto 18px;
  border-radius: 30px;
  background: var(--mg-glass-bg-strong);
  border: 1.5px solid var(--mg-glass-border);
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
  box-shadow: var(--mg-shadow-lg);
  display: flex;
  align-items: center;
  justify-content: center;
}
.logo-icon {
  font-size: 44px;
}
.logo-title {
  font-size: 27px;
  font-weight: 800;
  color: var(--mg-text-strong);
  margin: 0 0 6px;
  letter-spacing: 2px;
}
.logo-subtitle {
  font-size: 12.5px;
  color: var(--mg-text-soft);
  margin: 0;
  letter-spacing: 1px;
}

/* ----- 表单 (玻璃配方由 .mg-glass-strong 提供) ----- */
.login-form {
  border-radius: var(--mg-radius-xl);
  padding: 24px 20px;
}

.form-field {
  position: relative;
  display: flex;
  align-items: center;
  gap: 4px;
  background: var(--mg-glass-bg-strong);
  border: 1px solid var(--mg-glass-border);
  border-radius: var(--mg-radius-md);
  padding: 0 14px;
  margin-bottom: 12px;
  transition: border-color 150ms ease, box-shadow 150ms ease;
}
.form-field:focus-within {
  border-color: var(--mg-primary);
  box-shadow: 0 0 0 3px var(--mg-tint);
}

.field-icon {
  font-size: 17px;
  margin-right: 8px;
  color: var(--mg-text-soft);
  flex-shrink: 0;
}

.field-input {
  flex: 1;
  border: none;
  background: transparent;
  padding: 14px 0;
  font-size: 16px;
  color: var(--mg-text);
  outline: none;
  font-family: inherit;
  min-width: 0;
}
.field-input::placeholder {
  color: var(--mg-text-faint);
}

.toggle-password {
  background: transparent;
  border: none;
  font-size: 17px;
  padding: 8px;
  cursor: pointer;
  color: var(--mg-text-soft);
}

.error-message {
  padding: 9px 12px;
  margin-bottom: 12px;
  background: var(--mg-danger-soft);
  color: var(--mg-danger);
  border-radius: 12px;
  font-size: 13px;
  text-align: center;
  font-weight: 600;
}

.login-btn {
  width: 100%;
  padding: 15px;
  font-size: 16px;
  letter-spacing: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 8px;
  -webkit-tap-highlight-color: transparent;
}
.login-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.loading-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid var(--mg-on-primary);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

.login-hint {
  text-align: center;
  margin-top: 16px;
  font-size: 12px;
  color: var(--mg-text-soft);
}
.login-hint p { margin: 0; }

.login-foot {
  margin-top: 34px;
  text-align: center;
  font-size: 10px;
  letter-spacing: 3px;
  color: var(--mg-text-faint);
}
</style>
