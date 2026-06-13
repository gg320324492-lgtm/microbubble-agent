<template>
  <div class="mobile-login">
    <!-- 装饰背景 -->
    <div class="bg-decoration">
      <div class="bg-circle circle-1" />
      <div class="bg-circle circle-2" />
      <div class="bg-circle circle-3" />
    </div>

    <main class="login-main" :style="{ paddingTop: 'calc(60px + var(--sat))' }">
      <div class="logo-section">
        <div class="logo-circle">
          <span class="logo-icon">💬</span>
        </div>
        <h1 class="logo-title">小气助手</h1>
        <p class="logo-subtitle">微纳米气泡课题组智能 Agent</p>
      </div>

      <form class="login-form" @submit.prevent="handleLogin">
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
          class="login-btn"
          :disabled="loading"
        >
          <span v-if="loading" class="loading-spinner" />
          <span>{{ loading ? '登录中...' : '登 录' }}</span>
        </button>

        <div class="login-hint">
          <p>请联系管理员获取账号密码</p>
        </div>
      </form>
    </main>
  </div>
</template>

<script setup>
/**
 * MobileLoginView.vue — 移动端登录页
 *
 * PR #8a: 全屏表单（不用 el-dialog + CSS 全屏 hack）
 * - 大 logo + 装饰背景
 * - 用户名/密码字段（明文切换）
 * - 错误提示
 * - 复用 /api/v1/auth/login 接口
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
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-accent) 100%);
  overflow: hidden;
  z-index: 1000;
}

/* 装饰背景圆 */
.bg-decoration {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}
.bg-circle {
  position: absolute;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
}
.circle-1 {
  width: 300px;
  height: 300px;
  top: -100px;
  right: -100px;
}
.circle-2 {
  width: 200px;
  height: 200px;
  bottom: -50px;
  left: -50px;
}
.circle-3 {
  width: 150px;
  height: 150px;
  top: 40%;
  right: -75px;
}

/* 主区 */
.login-main {
  position: relative;
  z-index: 1;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 40px var(--mobile-padding-x, 16px) 40px;
}

/* Logo */
.logo-section {
  text-align: center;
  margin-bottom: 32px;
}
.logo-circle {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.95);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
}
.logo-icon {
  font-size: 40px;
}
.logo-title {
  font-size: 28px;
  font-weight: var(--font-weight-bold, 700);
  color: white;
  margin: 0 0 4px;
  letter-spacing: 1px;
}
.logo-subtitle {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.85);
  margin: 0;
}

/* 表单 */
.login-form {
  background: rgba(255, 255, 255, 0.95);
  border-radius: var(--radius-xl, 16px);
  padding: 24px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.1);
  backdrop-filter: blur(8px);
}

.form-field {
  position: relative;
  display: flex;
  align-items: center;
  background: var(--color-bg-page);
  border-radius: var(--radius-md);
  padding: 0 14px;
  margin-bottom: 14px;
}
.form-field:focus-within {
  background: var(--color-bg-card);
  box-shadow: 0 0 0 2px var(--color-primary-bg);
}

.field-icon {
  font-size: 18px;
  margin-right: 10px;
  color: var(--color-text-secondary);
  flex-shrink: 0;
}

.field-input {
  flex: 1;
  border: none;
  background: transparent;
  padding: 14px 0;
  font-size: 16px;
  color: var(--color-text-primary);
  outline: none;
  font-family: inherit;
  min-width: 0;
}
.field-input::placeholder {
  color: var(--color-text-placeholder);
}

.toggle-password {
  background: transparent;
  border: none;
  font-size: 18px;
  padding: 8px;
  cursor: pointer;
  color: var(--color-text-secondary);
}

.error-message {
  padding: 8px 12px;
  margin-bottom: 12px;
  background: var(--color-danger-bg);
  color: var(--color-danger, #F56C6C);
  border-radius: var(--radius-sm);
  font-size: 13px;
  text-align: center;
}

.login-btn {
  width: 100%;
  padding: 14px;
  border: none;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-light) 100%);
  color: white;
  font-size: 16px;
  font-weight: var(--font-weight-medium, 500);
  letter-spacing: 2px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  box-shadow: 0 4px 16px rgba(255, 122, 92, 0.3);
  margin-top: 8px;
  -webkit-tap-highlight-color: transparent;
}
.login-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}
.login-btn:active:not(:disabled) {
  transform: scale(0.98);
}

.loading-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid white;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.login-hint {
  text-align: center;
  margin-top: 16px;
  font-size: 12px;
  color: var(--color-text-secondary);
}
.login-hint p { margin: 0; }
</style>