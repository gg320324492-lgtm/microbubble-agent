<script setup lang="ts">
/**
 * Root App —— 按 route meta.layout 切换外壳。
 *
 * Phase 2-Impl-1:
 *   - layout=main  → MainLayout (Sidebar + Header)
 *   - layout=plain → 直接 router-view (LoginView / debug)
 *
 * Phase 8-M0-H1:
 *   - 启动失败 → BootstrapRecoveryCard 兜底, 提供 retry/quit/viewLogs 入口
 *
 * 未登录也会渲染 plain (login) layout；登录后 main layout。
 */
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import MainLayout from './layouts/MainLayout.vue'
import BootstrapRecoveryCard from './components/shell/BootstrapRecoveryCard.vue'
import { useAppConfig } from './composables/use-app-config'
import { useProjectStore } from './stores/research/project.store'

const route = useRoute()
const { bootstrapStatus, bootstrapError, dataDir, logDir, load, retryBootstrap, quitApp } = useAppConfig()
const layout = computed(() => {
  const meta = route.meta as { layout?: 'main' | 'plain' }
  return meta.layout ?? 'plain'
})
const isBootstrapFailed = computed(() => bootstrapStatus.value === 'failed')

onMounted(() => {
  void load()
  // [类 20.194] 2026-08-27: App 启动时调 loadProjects (之前 HeaderBar 调用但只一次,
  // 直接路由到 ProjectWorkspace 不走 HeaderBar 的话 currentProject 一直 null).
  // 改: 移到 App.vue 根 onMounted, 保证所有页面首次访问时 currentProject 都有值.
  void useProjectStore().loadProjects()
})
</script>

<template>
  <BootstrapRecoveryCard
    v-if="isBootstrapFailed"
    status="failed"
    :error-message="bootstrapError"
    :store-path="dataDir"
    :log-dir="logDir"
    @retry="retryBootstrap"
    @exit="quitApp"
  />
  <MainLayout v-else-if="layout === 'main'">
    <RouterView v-slot="{ Component }">
      <!-- [类 20.216] 2026-08-28: 加 :duration="240" 避免 CSS transitionend 不触发时
           Vue 永远卡在 leave 阶段, 新组件永远进不来. 设 240ms 兜底超时. -->
      <Transition name="research-page" mode="out-in" :duration="240">
        <component :is="Component" :key="route.fullPath" />
      </Transition>
    </RouterView>
  </MainLayout>
  <RouterView v-else v-slot="{ Component }">
    <Transition name="research-page" mode="out-in" :duration="240">
      <component :is="Component" :key="route.fullPath" />
    </Transition>
  </RouterView>
</template>
