// Renderer 入口 — 设计令牌（单一来源包）先行加载
import '@mb/design-tokens/variables.css'
import './assets/app.css'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
// M7：宣纸暖白令牌覆盖层 —— 必须最后加载：
//   ① EP 变量映射块用 :root[data-theme='paper']（0,2,0）压过 EP 的 :root（0,1,0）
//   ② 同时用加载顺序兜底，避免 EP 随需 CSS 晚到
import './assets/theme-paper.css'
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'

// 主题轴 — M7 起唯一主题为 paper（宣纸暖白）；属性选择器可稳定压过 EP 的 :root 变量
document.documentElement.dataset.theme = 'paper'

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
