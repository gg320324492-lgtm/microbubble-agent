<template>
  <div class="router-skeleton">
    <!-- 模拟 PageHeader -->
    <div class="skeleton-header">
      <div class="skeleton-bar w-100" style="height: 16px" />
    </div>

    <!-- 模拟主体 -->
    <div class="skeleton-body">
      <!-- 顶部欢迎/统计 -->
      <div v-if="!compact" class="skeleton-hero">
        <div class="skeleton-bar w-60" style="height: 28px; margin-bottom: 12px" />
        <div class="skeleton-bar w-90" style="height: 14px; margin-bottom: 8px" />
        <div class="skeleton-bar w-70" style="height: 14px" />
      </div>

      <!-- 列表卡片骨架 -->
      <div class="skeleton-cards">
        <div
          v-for="i in cardCount"
          :key="i"
          class="skeleton-card"
        >
          <div class="skeleton-row">
            <div class="skeleton-circle" />
            <div class="skeleton-content">
              <div class="skeleton-bar w-80" style="height: 16px; margin-bottom: 8px" />
              <div class="skeleton-bar w-50" style="height: 12px" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * RouterFallbackSkeleton.vue — 路由级骨架屏
 *
 * PR #9: 用于 router-view Suspense fallback
 * - 显示通用页面骨架（模拟 header + 内容）
 * - compact 模式：只显示卡片列表（用于深嵌套路由）
 */

defineProps({
  compact: { type: Boolean, default: false },
  cardCount: { type: Number, default: 4 },
})
</script>

<style scoped>
.router-skeleton {
  min-height: 100vh;
  background: var(--color-bg-page);
}

.skeleton-header {
  position: sticky;
  top: 0;
  z-index: 100;
  background: var(--color-bg-card);
  border-bottom: 1px solid var(--color-border);
  padding: 14px var(--mobile-padding-x, 16px);
  display: flex;
  align-items: center;
  min-height: 52px;
}

.skeleton-body {
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
}

.skeleton-hero {
  background: linear-gradient(135deg, var(--color-primary-bg) 0%, var(--color-accent-bg) 100%);
  border-radius: var(--radius-md);
  padding: 20px;
  margin-bottom: 16px;
}

[data-theme="dark"] .skeleton-hero {
  background: rgba(var(--color-primary-rgb), 0.12);
}

/* 卡片骨架 */
.skeleton-cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.skeleton-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  padding: 14px;
}
[data-theme="dark"] .skeleton-card {
  border-color: var(--color-border-base);
}

.skeleton-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.skeleton-circle {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--color-border);
  flex-shrink: 0;
  position: relative;
  overflow: hidden;
}

.skeleton-content {
  flex: 1;
  min-width: 0;
}

/* 通用骨架条 */
.skeleton-bar {
  background: var(--color-border);
  border-radius: var(--radius-sm);
  position: relative;
  overflow: hidden;
}
.skeleton-bar::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, var(--color-bg-warm), transparent);
  animation: shimmer 1.5s infinite;
}
.skeleton-circle::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, var(--color-bg-warm), transparent);
  animation: shimmer 1.5s infinite;
}
.w-40 { width: 40%; }
.w-50 { width: 50%; }
.w-60 { width: 60%; }
.w-70 { width: 70%; }
.w-80 { width: 80%; }
.w-90 { width: 90%; }
.w-100 { width: 100%; }

</style>