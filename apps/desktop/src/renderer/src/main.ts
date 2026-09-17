// Renderer 入口 — 设计令牌（单一来源包）先行加载
import '@mb/design-tokens/variables.css'
import './assets/app.css'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'

// 锁定页面缩放 — 应用不提供缩放功能；拦截触控板捏合 / Ctrl+滚轮误触
// （Chromium 会按 origin 持久化缩放级别，重启不恢复，故必须从源头拦截）
window.addEventListener(
  'wheel',
  (e) => {
    if (e.ctrlKey) e.preventDefault()
  },
  { passive: false }
)

createApp(App).use(createPinia()).use(router).use(ElementPlus).mount('#app')
