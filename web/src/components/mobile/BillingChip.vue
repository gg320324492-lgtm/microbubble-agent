<!--
  BillingChip.vue — W72 第 2 批 C-3 移动端顶栏计费 chip
  显示当前套餐 + 剩余天数 + 点击跳转订阅页
  - 6 主题 dark + NutUI 4 chip 样式
  - 长期 vibrate(10) 反馈 (CLAUDE.md 2026-06-27 教训)
  - 集成到 MobileHeader.vue
-->
<template>
  <button
    v-if="visible"
    type="button"
    class="billing-chip"
    :class="[`chip-${currentPlan?.tier || 'free'}`, { 'is-expiring': isExpiring }]"
    :aria-label="ariaLabel"
    :title="ariaLabel"
    @click="onClick"
  >
    <span v-if="loading" class="chip-icon">⏳</span>
    <span v-else class="chip-icon" :style="iconStyle">{{ tierIcon }}</span>
    <span class="chip-text">
      <span class="chip-tier">{{ tierLabel }}</span>
      <span v-if="daysRemaining !== null && daysRemaining !== undefined" class="chip-days">
        {{ daysRemaining }}天
      </span>
      <span v-else-if="currentPlan?.tier !== 'free'" class="chip-days">活跃</span>
    </span>
  </button>
</template>

<script setup>
/**
 * BillingChip.vue — 移动端顶栏计费 chip
 *
 * 功能：
 * - 顶部栏右侧小 chip
 * - 显示当前套餐 (免费/基础/专业) + 剩余天数
 * - 点击跳转订阅页 (/mobile/subscription)
 * - 长期 vibrate(10) 触觉反馈
 * - 6 主题 dark 适配
 *
 * 数据来源：
 * - 复用 W72 第 2 批 B-5 计费 API: GET /api/v1/billing/plans 返回的 current 字段
 * - 失败时静默 fallback 到免费版
 */

import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const props = defineProps({
  /** 长期触觉反馈开关 (默认 true) */
  hapticsEnabled: { type: Boolean, default: true },
  /** 自动刷新间隔 (ms, 0 = 不刷新) */
  refreshInterval: { type: Number, default: 60000 },
})

const emit = defineEmits(['click'])

const currentPlan = ref(null)
const loading = ref(false)
let refreshTimer = null

const tierIcon = computed(() => {
  switch (currentPlan.value?.tier) {
    case 'pro': return '💎'
    case 'basic': return '✨'
    default: return '🆓'
  }
})

const tierLabel = computed(() => {
  switch (currentPlan.value?.tier) {
    case 'pro': return '专业'
    case 'basic': return '基础'
    default: return '免费'
  }
})

const daysRemaining = computed(() => {
  return currentPlan.value?.days_remaining
})

const isExpiring = computed(() => {
  return daysRemaining.value !== null && daysRemaining.value !== undefined && daysRemaining.value <= 7
})

const visible = computed(() => {
  // 总可见 (免费版也显示，鼓励升级)
  return currentPlan.value !== undefined
})

const ariaLabel = computed(() => {
  const tier = tierLabel.value
  const days = daysRemaining.value
  if (days !== null && days !== undefined) {
    return `当前套餐 ${tier}，剩余 ${days} 天，点击管理订阅`
  }
  return `当前套餐 ${tier}，点击管理订阅`
})

const iconStyle = computed(() => {
  const tier = currentPlan.value?.tier
  if (tier === 'pro') {
    return { background: 'linear-gradient(135deg, #FF7A5C, #FFB347)' }
  }
  if (tier === 'basic') {
    return { background: 'linear-gradient(135deg, #5CACEE, #6495ED)' }
  }
  return {}
})

async function loadCurrent() {
  loading.value = true
  try {
    const token = localStorage.getItem('access_token') || ''
    const resp = await fetch('/api/v1/billing/plans', {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()
    currentPlan.value = data.current || { tier: 'free', days_remaining: null }
  } catch (err) {
    // API 未就绪时 fallback
    currentPlan.value = { tier: 'free', days_remaining: null }
    // eslint-disable-next-line no-console
    console.warn('[BillingChip] plans API unreachable, using fallback:', err.message)
  } finally {
    loading.value = false
  }
}

function onClick(e) {
  // CLAUDE.md 2026-06-27 教训：长按必含 navigator.vibrate(10)
  // 顶栏 chip 点击也属触觉反馈场景
  if (props.hapticsEnabled && typeof navigator !== 'undefined' && navigator.vibrate) {
    try { navigator.vibrate(10) } catch (_) { /* noop */ }
  }
  emit('click', e)
  router.push('/mobile/subscription')
}

function startAutoRefresh() {
  if (props.refreshInterval <= 0) return
  refreshTimer = setInterval(loadCurrent, props.refreshInterval)
}

function stopAutoRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

onMounted(() => {
  loadCurrent()
  startAutoRefresh()
})

onBeforeUnmount(() => {
  stopAutoRefresh()
})

// 暴露给父组件手动刷新
defineExpose({ refresh: loadCurrent })
</script>

<style scoped>
.billing-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 12px;
  border: 1px solid var(--color-border);
  background: var(--color-bg-card);
  color: var(--color-text-primary);
  font-size: 12px;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: transform 0.1s, background 0.15s;
  max-width: 110px;
  white-space: nowrap;
}
.billing-chip:active {
  transform: scale(0.95);
}
.billing-chip.is-expiring {
  border-color: var(--color-warning, #E6A23C);
  background: rgba(230, 162, 60, 0.08);
}

.chip-icon {
  font-size: 12px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.chip-text {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  line-height: 1.1;
}
.chip-tier {
  font-weight: 600;
  font-size: 11px;
}
.chip-days {
  font-size: 10px;
  color: var(--color-text-secondary);
}

/* 套餐专属色 (light 模式 fallback) */
.chip-free .chip-icon { background: #e0e0e0; }
.chip-basic .chip-icon { background: linear-gradient(135deg, #5CACEE, #6495ED); color: white; }
.chip-pro .chip-icon { background: linear-gradient(135deg, #FF7A5C, #FFB347); color: white; }
</style>

<!--
  W72 第 2 批 C-3 dark mode 跨组件适配
  CLAUDE.md v60-v67 第 5 次强化：dark mode 跨组件必须非 scoped
-->
<style>
[data-theme="dark"] .billing-chip {
  background: #222222;
  border-color: #2a2a2a;
  color: #e0e0e0;
}
[data-theme="dark"] .billing-chip.is-expiring {
  background: rgba(230, 162, 60, 0.15);
  border-color: var(--color-warning, #E6A23C);
}
[data-theme="dark"] .billing-chip .chip-days {
  color: #888888;
}
[data-theme="dark"] .billing-chip.chip-free .chip-icon {
  background: #3a3a3a;
  color: #a0a0a0;
}
</style>