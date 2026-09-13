<script setup lang="ts">
// 状态栏 — 本地数据状态 + 版本号（骨架设计的"桌面原生体验清单"第 5 项）
import { onMounted, ref } from 'vue'
import type { AppInfo } from '@shared/types'

const info = ref<AppInfo | null>(null)
const failed = ref(false)

onMounted(async () => {
  try {
    info.value = await window.api.app.info()
  } catch {
    failed.value = true
  }
})
</script>

<template>
  <footer class="statusbar">
    <div class="statusbar-left">
      <span class="statusbar-led" :class="failed ? 'is-off' : 'is-on'" aria-hidden="true"></span>
      <span>{{ failed ? '本地数据库未就绪' : '本地数据库就绪 · 数据存本机 · 断网可用' }}</span>
    </div>
    <div class="statusbar-right">
      <span v-if="info">v{{ info.version }}</span>
      <span class="statusbar-sep" aria-hidden="true">·</span>
      <span>SQLite</span>
    </div>
  </footer>
</template>

<style scoped>
.statusbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-4);
  background: var(--wb-panel-950);
  color: var(--wb-panel-text-dim);
  font-size: var(--font-size-xs);
}
.statusbar-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.statusbar-led {
  width: 7px;
  height: 7px;
  border-radius: var(--radius-full);
}
.statusbar-led.is-on {
  background: #67c23a;
  box-shadow: 0 0 6px rgba(103, 194, 58, 0.8);
}
.statusbar-led.is-off {
  background: #f56c6c;
}
.statusbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.statusbar-sep {
  opacity: 0.5;
}
</style>
