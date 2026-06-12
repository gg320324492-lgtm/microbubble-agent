<template>
  <el-config-provider :locale="zhCn">
    <router-view v-slot="{ Component, route }">
      <!-- 全局路由切换动画（fade-page）
           Chat 路由（SSE 流式）通过 .is-sse-route 类在 mobile-base.css 中关闭动画 -->
      <Transition name="fade-page" mode="out-in">
        <component
          :is="Component"
          :key="route.fullPath"
          :class="{ 'is-sse-route': isSseRoute(route) }"
        />
      </Transition>
    </router-view>
  </el-config-provider>
</template>

<script setup>
/**
 * App.vue — 全局应用壳
 *
 * PR #1 基建新增：
 * - 全局路由切换 fade-page 动画（180ms）
 * - Chat 路由 SSE 例外（is-sse-route 类关闭动画，防止 SSE 流被打断）
 * - useAdaptiveRoute() 监听 resize → 跨断点时 router.replace 触发重选组件
 */
import { useRoute } from 'vue-router'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import { useAdaptiveRoute } from '@/composables/useAdaptiveRoute'

const route = useRoute()

// PR #1：启动路由级响应式（resize → router.replace 触发 dynamic import 重选）
useAdaptiveRoute()

// SSE 例外判断：Chat 路由关闭 fade 动画
// 关键：避免组件切换的 transition 干扰 SSE 流式 yield（已切到 B 但 A 后台还在 yield）
function isSseRoute(r) {
  return r?.name === 'Chat'
}
</script>

<style>
/* 全局 body 字体（保持与原 App.vue 一致） */
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background-color: #f5f7fa;
}

#app {
  /* PR #1：移动端用 dvh 修复（iOS Safari 100vh 含地址栏） */
  height: var(--vh, 100vh);
  min-height: 100vh;
}
</style>