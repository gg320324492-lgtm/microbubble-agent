// Passive event listener 补丁 — 消除 Chrome 滚动事件性能警告
// 让 wheel/mousewheel/touchstart/touchmove 默认 passive，同时保留显式 passive:false 的能力
;(() => {
  const PASSIVE_EVENTS = new Set(['wheel', 'mousewheel', 'touchstart', 'touchmove'])
  const orig = EventTarget.prototype.addEventListener
  EventTarget.prototype.addEventListener = function (type, listener, options) {
    if (PASSIVE_EVENTS.has(type) && (options === undefined || options === null)) {
      options = { passive: true }
    }
    return orig.call(this, type, listener, options)
  }
})()

import { createApp } from 'vue'
import { createPinia } from 'pinia'
// 全局样式加载顺序：
// 1. variables.css 设计令牌（必须在最前）
// 2. element-plus-overrides.css 桌面组件覆盖
// 3. mobile-base.css 移动端通用基础（PR #1 新增）
// 4. nutui-theme.scss NutUI 4 主题变量（PR #2 新增）
import './assets/variables.css'
import './assets/element-plus-overrides.css'
import './assets/mobile-base.css'
import './assets/nutui-theme.scss'
// ElMessage / ElMessageBox 是 JS 服务调用，unplugin-vue-components 无法检测模板中的使用，需手动导入 CSS
import 'element-plus/theme-chalk/el-message.css'
import 'element-plus/theme-chalk/el-message-box.css'
import axios from 'axios'

import App from './App.vue'
import router from './router'

// PR #1 基建：初始化主题 store（避免刷新闪烁；必须在 router 之前）
import { useThemeStore } from './stores/useThemeStore'

// 配置axios拦截器
axios.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

axios.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    // 如果是401错误且不是刷新令牌请求
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken) {
        try {
          const res = await axios.post('/api/v1/auth/refresh', {
            refresh_token: refreshToken
          })

          const { access_token } = res.data
          localStorage.setItem('access_token', access_token)

          // 重试原始请求
          originalRequest.headers.Authorization = `Bearer ${access_token}`
          return axios(originalRequest)
        } catch (refreshError) {
          // 刷新令牌也失败，跳转到登录页
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          localStorage.removeItem('user_info')
          router.push('/login')
          return Promise.reject(refreshError)
        }
      } else {
        // 没有刷新令牌，跳转到登录页
        router.push('/login')
      }
    }

    return Promise.reject(error)
  }
)

const app = createApp(App)

app.use(createPinia())
app.use(router)

// 主题初始化（在 Pinia/router 注册后立即调用，避免刷新时 brief flash）
useThemeStore()

app.mount('#app')
