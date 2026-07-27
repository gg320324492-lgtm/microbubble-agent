<!--
  MobileSettingsUpgradeEntry.vue — W72 第 2 批 C-3 设置页升级入口组件
  嵌入 MobileSettingsView 末尾 + 6 主题 dark
  独立组件避免修改 MobileSettingsView 老路径 (符合 §3 0 production code 改动铁律)
-->
<template>
  <button
    type="button"
    class="settings-upgrade-entry"
    :aria-label="'升级到专业版'"
    :title="'升级到专业版'"
    @click="onClick"
  >
    <div class="entry-icon">💎</div>
    <div class="entry-info">
      <div class="entry-title">升级到专业版</div>
      <div class="entry-desc">100 GB 空间 + 高级 RAG + 团队共享盘</div>
    </div>
    <span class="entry-arrow">›</span>
  </button>
</template>

<script setup>
/**
 * MobileSettingsUpgradeEntry.vue — 设置页升级入口
 *
 * 派工依据:
 * - W72 第 2 批 C-3 Mobile UX v3.4 商业化暗色
 * - 0 production code 改动铁律例外 1 (web Mobile v3.4, 已批)
 * - 不修改 MobileSettingsView 老代码, 独立组件嵌入
 *
 * 用法 (在 MobileSettingsView template 节末尾插入):
 *   <MobileSettingsUpgradeEntry />
 */

import { useRouter } from 'vue-router'

const router = useRouter()

function onClick() {
  // CLAUDE.md 2026-06-27 教训: 长按/点击触发式操作必含 navigator.vibrate(10)
  if (typeof navigator !== 'undefined' && navigator.vibrate) {
    try { navigator.vibrate(10) } catch (_) { /* noop */ }
  }
  router.push('/mobile/subscription')
}
</script>

<style scoped>
.settings-upgrade-entry {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 14px 16px;
  margin: 12px 0;
  background: linear-gradient(90deg, rgba(255, 122, 92, 0.08), rgba(255, 179, 71, 0.08));
  border: 1px solid rgba(255, 122, 92, 0.25);
  border-radius: var(--radius-md, 8px);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: transform 0.1s;
}
.settings-upgrade-entry:active {
  transform: scale(0.98);
}
.entry-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #FF7A5C, #FFB347);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}
.entry-info {
  flex: 1;
  text-align: left;
}
.entry-title {
  font-size: 15px;
  font-weight: 700;
  background: linear-gradient(90deg, #FF7A5C, #FFB347);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  margin-bottom: 2px;
}
.entry-desc {
  font-size: 12px;
  color: var(--color-text-secondary);
}
.entry-arrow {
  font-size: 20px;
  color: var(--color-text-secondary);
  flex-shrink: 0;
}
</style>

<!--
  W72 第 2 批 C-3 dark mode 跨组件适配
  CLAUDE.md v60-v67 第 5 次强化: dark mode 跨组件必须非 scoped
-->
<style>
[data-theme="dark"] .settings-upgrade-entry {
  background: linear-gradient(90deg, rgba(255, 122, 92, 0.15), rgba(255, 179, 71, 0.15));
  border-color: rgba(255, 122, 92, 0.35);
}
[data-theme="dark"] .settings-upgrade-entry .entry-desc {
  color: #a0a0a0;
}
[data-theme="dark"] .settings-upgrade-entry .entry-arrow {
  color: #888888;
}
</style>