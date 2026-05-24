<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <h1>微纳米气泡课题组</h1>
        <p>智能Agent管理系统</p>
      </div>

      <el-form
        ref="loginFormRef"
        :model="loginForm"
        :rules="loginRules"
        class="login-form"
        @keyup.enter="handleLogin"
      >
        <el-form-item prop="username">
          <el-input
            v-model="loginForm.username"
            placeholder="请输入用户名"
            size="large"
            prefix-icon="User"
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="loginForm.password"
            type="password"
            placeholder="请输入密码"
            size="large"
            prefix-icon="Lock"
            show-password
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            class="login-button"
            :loading="loading"
            @click="handleLogin"
          >
            登录
          </el-button>
        </el-form-item>
      </el-form>

      <div class="login-footer">
        <p>请联系管理员获取账号密码</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const router = useRouter()
const loginFormRef = ref(null)
const loading = ref(false)

const loginForm = reactive({
  username: '',
  password: ''
})

const loginRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' }
  ]
}

const handleLogin = async () => {
  if (!loginFormRef.value) return

  await loginFormRef.value.validate(async (valid) => {
    if (!valid) return

    loading.value = true
    try {
      const res = await axios.post('/api/v1/auth/login', {
        username: loginForm.username,
        password: loginForm.password
      })

      const { access_token, refresh_token, user } = res.data

      // 保存令牌和用户信息
      localStorage.setItem('access_token', access_token)
      localStorage.setItem('refresh_token', refresh_token)
      localStorage.setItem('user_info', JSON.stringify(user))

      // 设置axios默认header
      axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`

      ElMessage.success('登录成功')
      router.push('/')
    } catch (error) {
      const message = error.response?.data?.detail || '登录失败，请重试'
      ElMessage.error(message)
    } finally {
      loading.value = false
    }
  })
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-accent) 100%);
  animation: fadeSlideUp var(--duration-slower) var(--ease-out) both;
}

.login-card {
  width: min(400px, 90vw);
  padding: var(--space-10);
  background: var(--color-bg-card);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  animation: fadeSlideUp var(--duration-slow) var(--ease-out) 80ms both;
}

@media (max-width: 768px) {
  .login-card {
    padding: var(--space-6);
  }
  .login-header h1 {
    font-size: 20px;
  }
}

.login-header {
  text-align: center;
  margin-bottom: var(--space-8);
}

.login-header h1 {
  font-size: var(--font-size-xl);
  color: var(--color-text-primary);
  margin-bottom: var(--space-2);
}

.login-header p {
  font-size: var(--font-size-base);
  color: var(--color-text-secondary);
}

.login-form {
  margin-bottom: var(--space-5);
}

.login-button {
  width: 100%;
  border-radius: var(--radius-md);
  font-weight: var(--font-weight-semibold);
  box-shadow: var(--shadow-primary);
  transition: all var(--duration-normal) var(--ease-out);
}

.login-button:hover {
  transform: translateY(-2px);
  filter: brightness(1.08);
  box-shadow: 0 8px 24px rgba(255, 122, 92, 0.40);
}

.login-button:active {
  transform: translateY(0);
}

.login-footer {
  text-align: center;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.login-footer p {
  margin: var(--space-1) 0;
}
</style>
