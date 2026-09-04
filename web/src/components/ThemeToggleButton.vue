<!--
  ThemeToggleButton.vue — 桌面端主题切换 (E 案「昼夜滑轨」, 2026-09-04 主拍)
  - 46×22 胶囊轨道, 16px 滑块内嵌 1.6px 线性日/月图标 (与 G 稿 sprite 同族)
  - 滑块位置 = 当前主题: 左=白天 (墨底纸字太阳), 右=夜览 (teal 底墨字月亮)
  - 视觉源 docs/design-proposals/theme-toggle-2026-09/index.html E 卡, 色板与 --dg-* 顶栏一致
  - dark 态由 theme.isDark 类直接驱动 (规则都在同元素, 不踩 v60-v67 scoped+:global 坑);
    仍保留非 scoped 块兜底 [data-theme=dark] 场景 (组件若在别处无 store 类挂载)
-->
<template>
  <button
    type="button"
    class="theme-toggle-btn"
    :class="{ 'is-night': theme.isDark }"
    role="switch"
    :aria-checked="theme.isDark"
    :aria-label="theme.isDark ? '切换到浅色主题' : '切换到深色主题'"
    :title="theme.isDark ? '切换到浅色主题' : '切换到深色主题'"
    @click="theme.toggle()"
  >
    <span class="knob">
      <svg class="g-sun" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true">
        <circle cx="8" cy="8" r="3"/>
        <path d="M8 1v1.6M8 13.4V15M1 8h1.6M13.4 8H15M3 3l1.1 1.1M11.9 11.9 13 13M13 3l-1.1 1.1M4.1 11.9 3 13"/>
      </svg>
      <svg class="g-moon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" aria-hidden="true">
        <path d="M13.2 9.8A6 6 0 1 1 6.2 2.8a4.7 4.7 0 0 0 7 7Z"/>
      </svg>
    </span>
  </button>
</template>

<script setup>
import { useThemeStore } from '@/stores/useThemeStore'

const theme = useThemeStore()
</script>

<style scoped>
.theme-toggle-btn {
  position: relative;
  width: 46px;
  height: 22px;
  padding: 0;
  border-radius: 12px;
  border: 1px solid #c9d2ca;
  background: #eaece7;
  cursor: pointer;
  transition: background 200ms ease, border-color 200ms ease;
  -webkit-tap-highlight-color: transparent;
  flex-shrink: 0;
}
.theme-toggle-btn:hover { background: #dcece5; }
.theme-toggle-btn:focus-visible { outline: 2px solid #0e766e; outline-offset: 2px; }
.knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #16232a;
  color: #fdfefc;
  display: grid;
  place-items: center;
  transition: left 280ms cubic-bezier(0.6, 0, 0.2, 1), background 200ms ease, color 200ms ease;
}
.knob svg { width: 10px; height: 10px; }
.g-moon { display: none; }
.theme-toggle-btn.is-night { background: #12312b; border-color: #2c3d44; }
.theme-toggle-btn.is-night:hover { background: #16403a; }
.theme-toggle-btn.is-night .knob { left: 26px; background: #35c2a4; color: #0c1215; }
.theme-toggle-btn.is-night .g-sun { display: none; }
.theme-toggle-btn.is-night .g-moon { display: block; }
</style>

<!-- 兜底: html[data-theme=dark] 下即使 is-night 类没挂上 (异步时序), 轨道也走深色底 -->
<style>
[data-theme="dark"] .theme-toggle-btn:not(.is-night) {
  background: #12312b;
  border-color: #2c3d44;
}
[data-theme="dark"] .theme-toggle-btn:not(.is-night) .knob {
  left: 26px;
  background: #35c2a4;
  color: #0c1215;
}
</style>
