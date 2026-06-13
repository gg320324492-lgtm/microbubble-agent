<template>
  <el-config-provider :locale="zhCn">
    <router-view v-slot="{ Component, route }">
      <!-- 全局路由切换动画（fade-page）
           Chat 路由（SSE 流式）通过 .is-sse-route 类在 mobile-base.css 中关闭动画 -->
      <Suspense>
        <component
          :is="Component"
          v-if="Component"
          :key="route.fullPath"
          :class="{ 'is-sse-route': isSseRoute(route) }"
        />

        <template #fallback>
          <RouterFallbackSkeleton />
        </template>
      </Suspense>
    </router-view>

    <!-- 离线检测提示横幅 -->
    <Transition name="offline-banner">
      <div v-if="showOfflineBanner" class="offline-banner">
        <span class="offline-icon">📡</span>
        <span class="offline-text">网络已断开，部分功能可能不可用</span>
        <button
          type="button"
          class="offline-retry"
          @click="checkOnline"
        >重试</button>
      </div>
    </Transition>
  </el-config-provider>
</template>

<script setup>
/**
 * App.vue — 全局应用壳
 *
 * PR #1 基建：
 * - 全局路由切换 fade-page 动画
 * - Chat 路由 SSE 例外（is-sse-route 类关闭动画）
 * - useAdaptiveRoute 监听 resize → router.replace 重选组件
 *
 * PR #9 新增：
 * - Suspense + RouterFallbackSkeleton 路由级骨架屏
 * - 离线检测横幅（online/offline 事件 + 手动重试）
 */
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import { useAdaptiveRoute } from '@/composables/useAdaptiveRoute'
import RouterFallbackSkeleton from '@/components/common/RouterFallbackSkeleton.vue'

const route = useRoute()

// PR #1：启动路由级响应式
useAdaptiveRoute()

// SSE 例外判断：Chat 路由关闭 fade 动画
function isSseRoute(r) {
  return r?.name === 'Chat'
}

// PR #9：离线检测
const showOfflineBanner = ref(false)
let onlineHandler = null
let offlineHandler = null

function setOnline() {
  showOfflineBanner.value = false
}

function setOffline() {
  showOfflineBanner.value = true
}

function checkOnline() {
  if (typeof navigator !== 'undefined' && navigator.onLine) {
    setOnline()
    // 可选：window.location.reload() 重新尝试请求
  } else {
    setOffline()
  }
}

onMounted(() => {
  if (typeof navigator !== 'undefined') {
    onlineHandler = setOnline
    offlineHandler = setOffline
    window.addEventListener('online', onlineHandler)
    window.addEventListener('offline', offlineHandler)
    if (!navigator.onLine) setOffline()
  }
})

onUnmounted(() => {
  if (typeof window !== 'undefined') {
    if (onlineHandler) window.removeEventListener('online', onlineHandler)
    if (offlineHandler) window.removeEventListener('offline', offlineHandler)
  }
})
</script>

<style>
/* 全局 body 字体（保持与原 App.vue 一致） */
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background-color: #f5f7fa;
}

#app {
  /* PR #1：移动端用 dvh 修复 */
  height: var(--vh, 100vh);
  min-height: 100vh;
}

/* PR #9: 离线检测横幅 */
.offline-banner {
  position: fixed;
  bottom: calc(var(--tabbar-height, 56px) + 12px + var(--sab, 0px));
  left: 12px;
  right: 12px;
  z-index: 5000;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: var(--color-warning, #E6A23C);
  color: white;
  border-radius: var(--radius-md);
  font-size: 13px;
  box-shadow: 0 4px 12px rgba(230, 162, 60, 0.3);
}
.offline-icon { font-size: 18px; flex-shrink: 0; }
.offline-text { flex: 1; }
.offline-retry {
  background: rgba(255, 255, 255, 0.25);
  border: none;
  color: white;
  padding: 4px 12px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  cursor: pointer;
  font-weight: var(--font-weight-medium, 500);
}
.offline-retry:active { background: rgba(255, 255, 255, 0.4); }

.offline-banner-enter-active, .offline-banner-leave-active {
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), opacity 0.3s;
}
.offline-banner-enter-from, .offline-banner-leave-to {
  transform: translateY(100%);
  opacity: 0;
}
</style>