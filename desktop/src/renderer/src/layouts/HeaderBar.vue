<script setup lang="ts">
/**
 * 顶部 Header Bar。
 *
 * 职责:
 * - 当前页面标题（取自 route.meta.title）
 * - 用户头像 + 显示名 (Pinia user store)
 * - logout 入口
 *
 * Phase 2-Impl-1: 不做主题切换 / 全局搜索等（Phase 5+）。
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useUserStore } from '../stores/user'
import { isAdminRole } from '@shared/auth-types'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const userStore = useUserStore()

const pageTitle = computed(() => {
  const meta = route.meta as { title?: string }
  return meta.title ?? 'MicroBubble'
})
const displayName = computed(() => userStore.profile?.name ?? '用户')
const isAdmin = computed(() => isAdminRole(userStore.profile?.role))
const avatarUrl = computed(() => userStore.profile?.avatar ?? '')

async function onLogout(): Promise<void> {
  await authStore.logout()
  await router.push({ name: 'login' })
}
</script>

<template>
  <header class="header-bar">
    <div class="header-bar__left">
      <h2 class="header-bar__title">{{ pageTitle }}</h2>
    </div>

    <div class="header-bar__right">
      <div v-if="authStore.isAuthenticated" class="header-bar__user">
        <div class="header-bar__avatar" :title="displayName">
          <img
            v-if="avatarUrl"
            :src="avatarUrl"
            :alt="displayName"
            @error="(e) => ((e.target as HTMLImageElement).style.display = 'none')"
          />
          <span v-else>{{ displayName.charAt(0) }}</span>
        </div>
        <div class="header-bar__user-info">
          <span class="header-bar__user-name">{{ displayName }}</span>
          <span v-if="isAdmin" class="header-bar__user-role">admin</span>
        </div>
        <button class="header-bar__logout" type="button" @click="onLogout">登出</button>
      </div>
    </div>
  </header>
</template>

<style scoped>
.header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.85rem 1.5rem;
  background: #0f172a;
  border-bottom: 1px solid #1e293b;
  height: 60px;
  flex-shrink: 0;
}
.header-bar__left {
  display: flex;
  align-items: center;
}
.header-bar__title {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 600;
  color: #f1f5f9;
}
.header-bar__right {
  display: flex;
  align-items: center;
  gap: 1rem;
}
.header-bar__user {
  display: flex;
  align-items: center;
  gap: 0.7rem;
}
.header-bar__avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, #f97316, #fbbf24);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  color: #fff;
  font-size: 0.95rem;
  overflow: hidden;
}
.header-bar__avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.header-bar__user-info {
  display: flex;
  flex-direction: column;
  line-height: 1.1;
}
.header-bar__user-name {
  font-size: 0.85rem;
  color: #f1f5f9;
  font-weight: 500;
}
.header-bar__user-role {
  font-size: 0.65rem;
  color: #f97316;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.header-bar__logout {
  background: transparent;
  border: 1px solid #334155;
  color: #94a3b8;
  padding: 0.3rem 0.7rem;
  border-radius: 4px;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.15s;
}
.header-bar__logout:hover {
  border-color: #ef4444;
  color: #ef4444;
}
</style>
