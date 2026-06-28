<!--
  ThemeToggleButton.vue — 桌面端主题切换按钮
  2026-06-26 v68 新增：
  - 桌面 MainLayout 顶栏铃铛与用户头像之间
  - 36px 圆形按钮，emoji ☀️/🌙（与移动端 MobileHeader 一致）
  - hover scale(1.1) + 主色背景 + 阴影

  ★ 重要：dark mode 规则必须放非 scoped <style> 块 ★
  v68 首次部署用 :global([data-theme="dark"]) .theme-toggle-btn:hover 在 scoped 块里
  → Vue 编译器把 :global() + 后代选择器组合处理错，编译产物为
    [data-theme=dark]{...} 单独的规则（剥掉了 .theme-toggle-btn:hover），
    实际作用到 <html> 而不是按钮（与 sw.js v61 教训同款）。
  修法：第二个非 scoped 块彻底绕过 Vue scoped 编译，规则全局生效直接命中按钮。
-->
<template>
  <button
    type="button"
    class="theme-toggle-btn"
    :aria-label="theme.isDark ? '切换到浅色主题' : '切换到深色主题'"
    :title="theme.isDark ? '切换到浅色主题' : '切换到深色主题'"
    @click="theme.toggle()"
  >
    <span class="theme-icon">{{ theme.isDark ? '☀️' : '🌙' }}</span>
  </button>
</template>

<script setup>
import { useThemeStore } from '@/stores/useThemeStore'

const theme = useThemeStore()
</script>

<style scoped>
.theme-toggle-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  padding: 0;
  border-radius: 50%;
  border: 1px solid rgba(144, 147, 153, 0.15);
  background: rgba(144, 147, 153, 0.1);
  cursor: pointer;
  transition: all 200ms var(--ease-out);
  -webkit-tap-highlight-color: transparent;
}
.theme-toggle-btn:hover {
  background: var(--color-primary-bg);
  border-color: var(--color-primary-light, #FF9D85);
  transform: scale(1.1);
  box-shadow: 0 2px 8px rgba(var(--color-primary-rgb), 0.2);
}
.theme-toggle-btn:active {
  transform: scale(0.95);
}
.theme-icon {
  font-size: 18px;
  line-height: 1;
  transition: transform 250ms var(--ease-out);
  display: inline-block;
}
.theme-toggle-btn:hover .theme-icon {
  transform: rotate(20deg) scale(1.1);
}
</style>

<!-- v68 dark mode 必须放非 scoped 块（v62/v61 教训：scoped + :global + 后代选择器编译错位） -->
<style>
[data-theme="dark"] .theme-toggle-btn {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.1);
}
[data-theme="dark"] .theme-toggle-btn:hover {
  background: rgba(var(--color-primary-rgb), 0.15);
  border-color: rgba(var(--color-primary-light-rgb), 0.5);
  box-shadow: 0 2px 12px rgba(var(--color-primary-rgb), 0.3);
}
</style>