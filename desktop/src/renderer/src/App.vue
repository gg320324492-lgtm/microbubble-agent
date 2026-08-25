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

const route = useRoute()
const { bootstrapStatus, bootstrapError, dataDir, logDir, load, retryBootstrap, quitApp } = useAppConfig()
const layout = computed(() => {
  const meta = route.meta as { layout?: 'main' | 'plain' }
  return meta.layout ?? 'plain'
})
const isBootstrapFailed = computed(() => bootstrapStatus.value === 'failed')

onMounted(() => { void load() })
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
      <Transition name="research-page" mode="out-in">
        <component :is="Component" :key="route.fullPath" />
      </Transition>
    </RouterView>
  </MainLayout>
  <RouterView v-else v-slot="{ Component }">
    <Transition name="research-page" mode="out-in">
      <component :is="Component" :key="route.fullPath" />
    </Transition>
  </RouterView>
</template>
