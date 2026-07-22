// Passive event listener 补丁 — 消除 Chrome 滚轮事件性能警告
// 2026-06-18 修复：只强制 wheel/mousewheel 为 passive（Chrome 滚轮性能警告根因）
// touchstart/touchmove **不强制** — 移动端组件（语音按钮、longpress）需要 preventDefault 取消默认行为
// 之前 v1 (commit 77398a4a) 把 4 个事件都强制 passive，导致：
// 1. MobileInputBar @touchstart.prevent 失效（语音按钮"按住说话"行为异常）
// 2. Element Plus 内部 popover/dialog 的 preventDefault 抛 'Unable to preventDefault inside passive' 警告
;(() => {
  const PASSIVE_EVENTS = new Set(['wheel', 'mousewheel'])
  const orig = EventTarget.prototype.addEventListener
  EventTarget.prototype.addEventListener = function (type, listener, options) {
    if (PASSIVE_EVENTS.has(type) && (options === undefined || options === null)) {
      options = { passive: true }
    }
    return orig.call(this, type, listener, options)
  }
})()

// 2026-07-20 cache-bust 诊断: build 时间戳 (由 vite.config.js define 注入)
// 浏览器 DevTools 顶部 console 第一行即可看到 build 时间, 运维判断"页面没更新"时
// 让用户截图这行 → 对比服务器部署时间 → 知道是 CDN 没回源 / 用户没刷新 / 部署没生效
// 注意: 必须在 createApp 之前 console.log, 否则 build 标识信息被业务日志覆盖
console.info(
  `%c[build] ${__BUILD_TIMESTAMP__} (id=${__BUILD_ID__})`,
  'color:#FF7A5C;font-weight:600;'
)

import { createApp } from 'vue'
import { createPinia } from 'pinia'
// 全局样式加载顺序：
// 1. variables.css 设计令牌（必须在最前）
// 2. element-plus-overrides.css 桌面组件覆盖
// 3. mobile-base.css 移动端通用基础（PR #1 新增）
// 4. nutui-theme.scss NutUI 4 主题变量（PR #2 新增）
import './assets/variables.css'
import './assets/element-plus-overrides.css'
import './assets/glass.css'  // v77 P2: 玻璃态工具类 (6 主题自适应 + dark mode 适配)
import './assets/pet-animations.css'  // v77 P2: DashboardPet 9 个 pet-* keyframes 抽离
import './assets/styles/_runtime-style-tokens.scss'  // v77 P2.6-D.3: CSS-in-JS 收敛 (14 个枚举 class)
import './assets/mobile-base.css'
import './assets/nutui-theme.scss'
// v28 step 35: MathJax CHTML 样式通过 index.html <link> 引入（CDN），
// mathjax-full 没自带 dist css 文件
// ElMessage / ElMessageBox 是 JS 服务调用，unplugin-vue-components 无法检测模板中的使用，需手动导入 CSS
import 'element-plus/theme-chalk/el-message.css'
import 'element-plus/theme-chalk/el-message-box.css'
import axios from 'axios'

import App from './App.vue'
import router from './router'

// PR #1 基建：初始化主题 store（避免刷新闪烁；必须在 router 之前）
import { useThemeStore } from './stores/useThemeStore'

// PWA Service Worker 注册（webhint cache-busting 修复）
// 用 Vue composable 替代 vite-plugin-pwa 自动注入的 <script src="/registerSW.js">，
// 避免静态 registerSW.js 缺 hash 触发 cache-busting 警告。
import { useRegisterSW } from 'virtual:pwa-register/vue'

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

// PWA Service Worker 注册（webhint cache-busting 修复）
// 监听 sw.js activate 钩子发的 SW_UPDATED 消息，触发自动 reload 让用户拿到新资源
// （修复事故：之前 server 返回 octet-stream 时期 SW NetworkFirst 缓存了污染响应，
// 现在 SW 升级会清空所有 cache + 通知客户端 reload）
// v28 step 33: 服务器部署滞后时（如服务器 sw.js 仍是老版本），坏 SW 持续报
// bad-precaching-response 错误且永远不更新。临时方案：直接 fetch 服务器 sw.js
// 文本，检查是否包含黑名单字符串（精确匹配 SW 字面量，不匹配 index bundle 里的字符串）。
// 命中 → 强制 unregister + 清 cache + reload。
// v28 step 78: 之前误把 '"manifest.webmanifest"' 加进黑名单，导致新 index bundle 也命中
//   → 无限循环 unregister + reload。改成只在 sw.js 上下文里匹配：
//   'SW_VERSION' + 'manifest.webmanifest' + 老 SW 版本号同时存在时才算坏 SW。
// v28 step 83: 扩到 v36 之前的所有版本（v2[0-5] → v2[0-5]|v3[0-5]）
// v28 step 85: 扩到 v37 之前（v(?:2[0-9]|3[0-6])），加入 v36 字面量
const SW_BLACKLIST_CONTENT_PATTERNS = [
  // 老 sw.js 同时包含 SW_VERSION 字面量 + manifest.webmanifest 旧路径（说明是老 SW）
  /SW_VERSION\s*=\s*["']v(?:2[0-9]|3[0-6])-/,
  // 老 SW_VERSION 字面量（v28 step 33 之前的版本）
  'v25-smart-reader-2026-06-19',
  'v35-card-fallback-fetch-retry-2026-06-21',  // v28 step 79-82 的 SW，precache 列表有 404 文件
  'v36-precache-purge-2026-06-21',  // v28 step 83-84 的 SW，浏览器可能仍加载旧 chunk
]

async function checkSwBlacklist() {
  try {
    const r = await fetch('/sw.js', { cache: 'no-store' })
    const text = await r.text()
    for (const pat of SW_BLACKLIST_CONTENT_PATTERNS) {
      // v28 step 79: 同时支持字符串（includes）和正则（test）
      const matched = pat instanceof RegExp ? pat.test(text) : text.includes(pat)
      if (matched) {
        console.warn('[PWA] SW content blacklisted (pattern: ' + pat + '), unregistering')
        const regs = await navigator.serviceWorker.getRegistrations()
        for (const reg of regs) {
          await reg.unregister()
          console.log('[PWA] Unregistered:', reg.scope)
        }
        if (window.caches) {
          const keys = await caches.keys()
          await Promise.all(keys.map(k => caches.delete(k)))
          console.log('[PWA] Cleared caches:', keys.length)
        }
        // 阻止后续 SW 注册 + reload
        return true
      }
    }
    console.log('[PWA] SW content OK, no blacklist match')
    return false
  } catch (e) {
    console.warn('[PWA] Failed to check SW blacklist:', e)
    return false
  }
}

useRegisterSW({
  immediate: true,
  onRegisteredSW(swUrl) {
    console.log('[PWA] SW registered:', swUrl)
  },
  onRegisterError(err) {
    console.warn('[PWA] SW registration failed:', err)
  },
})

// SW 更新由顶层 PwaUpdateToast 呈现；广播自定义事件也让组件在 SW
// 注册回调早于 Vue mount 时不丢失消息。
navigator.serviceWorker.addEventListener('message', (event) => {
  if (event.data?.type === 'SW_UPDATED') {
    window.dispatchEvent(new CustomEvent('pwa-update-available', { detail: event.data }))
  }
})

// 2026-07-02 SW 升级加固：controllerchange 仅记录状态，不再强制 reload。
// 用户可能正在编辑内容，刷新由 PwaUpdateToast 的明确按钮触发。
let swFirstActivation = true
navigator.serviceWorker.addEventListener('controllerchange', () => {
  if (swFirstActivation) {
    swFirstActivation = false
    console.log('[PWA] First SW activation, no reload')
    return
  }
  console.log('[PWA] New SW controller; waiting for user refresh')
})

// 防御性：app 加载时如果已有 waiting SW（上次访问下载了新 SW 但未 activate），
// 主动激活 + 走 controllerchange 路径强制 reload。
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.getRegistration().then(reg => {
    if (reg?.waiting) {
      console.log('[PWA] Waiting SW detected on init, force activating...')
      reg.waiting.postMessage({ type: 'SKIP_WAITING' })
      // SW 的 self.skipWaiting() 已生效；SKIP_WAITING 是冗余但无害，
      // controllerchange 会在 waiting → active 时触发
    }
  })
}

// v28 step 33: 页面加载后立即检查服务器 sw.js 内容是否在黑名单
// 不依赖 SW 自身响应消息（坏 SW 不会响应），直接 fetch 服务器 sw.js 文本判断
checkSwBlacklist().then((blacklisted) => {
  if (blacklisted) {
    // 阻止 service worker 再次自动注册（通过临时删除 registerSW 标记）
    // 实际实现：reload 即可让浏览器看到新 sw.js 前不复活
    console.log('[PWA] Reloading in 2s to clear bad SW...')
    setTimeout(() => window.location.reload(), 2000)
  }
})

app.mount('#app')
