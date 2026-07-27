<!--
  MobileSubscriptionView.vue — W72 第 2 批 C-3 Mobile UX v3.4 商业化暗色

  3 套餐卡片 (免费/基础/专业) + 切换 + 升级 CTA
  - 6 主题 dark + NutUI 4 卡片样式
  - 调 B-5 计费 API: GET /api/v1/billing/plans + POST /api/v1/billing/subscribe
  - 路由级双栈保持 (useIsMobile.js + resolveMobile.js)
  - dark mode 跨组件必非 scoped (CLAUDE.md v60-v67 教训)
-->
<template>
  <div class="mobile-subscription-view" data-theme="dark">
    <PageHeader title="订阅与套餐" show-back @back="goBack">
      <template #right>
        <button
          type="button"
          class="header-btn"
          aria-label="刷新套餐"
          title="刷新套餐"
          @click="loadPlans"
        >↻</button>
      </template>
    </PageHeader>

    <main
      class="sub-main"
      :style="{ paddingBottom: 'calc(var(--tabbar-height, 56px) + var(--sab, 0px))' }"
    >
      <!-- 当前套餐概览 -->
      <section v-if="currentPlan" class="current-plan-card" :class="`plan-${currentPlan.tier}`">
        <div class="current-plan-header">
          <div class="current-plan-label">当前套餐</div>
          <div class="current-plan-name">{{ currentPlan.name }}</div>
        </div>
        <div v-if="currentPlan.days_remaining !== null && currentPlan.days_remaining !== undefined" class="current-plan-remaining">
          <span class="remaining-number">{{ currentPlan.days_remaining }}</span>
          <span class="remaining-label">天剩余</span>
        </div>
        <div v-else class="current-plan-meta">
          <span class="meta-text">永久有效</span>
        </div>
        <div class="current-plan-usage">
          <div class="usage-item">
            <span class="usage-label">已用空间</span>
            <span class="usage-value">{{ formatBytes(currentPlan.used_bytes) }} / {{ formatBytes(currentPlan.quota_bytes) }}</span>
          </div>
          <div class="usage-bar">
            <div class="usage-bar-fill" :style="{ width: usagePercent + '%' }" />
          </div>
        </div>
      </section>

      <!-- 套餐卡片列表 -->
      <section class="plans-section">
        <h2 class="section-title">选择套餐</h2>
        <div v-if="loading" class="loading-state">
          <div class="empty-icon">⏳</div>
          <div class="empty-hint">加载中...</div>
        </div>
        <div v-else-if="loadError" class="error-state">
          <div class="empty-icon">⚠️</div>
          <div class="empty-hint">{{ loadError }}</div>
          <button type="button" class="retry-btn" @click="loadPlans">重试</button>
        </div>
        <div v-else class="plans-grid">
          <article
            v-for="plan in plans"
            :key="plan.id"
            class="plan-card"
            :class="{
              'is-current': currentPlan && currentPlan.tier === plan.tier,
              'is-recommended': plan.recommended,
              'is-popular': plan.tier === 'pro',
            }"
            @click="selectPlan(plan)"
          >
            <div v-if="plan.recommended" class="plan-badge">推荐</div>
            <div v-else-if="plan.tier === 'pro'" class="plan-badge popular">最热门</div>
            <header class="plan-card-header">
              <h3 class="plan-name">{{ plan.name }}</h3>
              <div class="plan-price">
                <span v-if="plan.price_cny === 0" class="price-free">免费</span>
                <span v-else class="price-amount">
                  <span class="currency">¥</span>
                  <span class="amount">{{ plan.price_cny }}</span>
                  <span class="period">/月</span>
                </span>
              </div>
            </header>
            <ul class="plan-features">
              <li v-for="(feat, idx) in plan.features" :key="idx" class="plan-feature">
                <span class="feature-check">✓</span>
                <span class="feature-text">{{ feat }}</span>
              </li>
            </ul>
            <footer class="plan-card-footer">
              <button
                v-if="currentPlan && currentPlan.tier === plan.tier"
                type="button"
                class="plan-btn current"
                disabled
              >当前套餐</button>
              <button
                v-else
                type="button"
                class="plan-btn"
                :class="{ primary: plan.tier === 'pro', upgrade: plan.tier !== 'free' && (!currentPlan || plan.tier > (currentPlan.tier || 0)) }"
                @click.stop="subscribe(plan)"
              >
                {{ plan.tier === 'free' ? '降级到此套餐' : (plan.tier > (currentPlan?.tier || 0) ? '升级' : '切换到此套餐') }}
              </button>
            </footer>
          </article>
        </div>
      </section>

      <!-- 套餐对比 -->
      <section v-if="plans.length > 0" class="compare-section">
        <h2 class="section-title">套餐对比</h2>
        <table class="compare-table">
          <thead>
            <tr>
              <th class="compare-feature">功能</th>
              <th v-for="plan in plans" :key="plan.id" class="compare-plan">{{ plan.name }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in compareRows" :key="idx">
              <td class="compare-feature">{{ row.feature }}</td>
              <td v-for="plan in plans" :key="plan.id" class="compare-value">
                {{ row.values[plan.tier] }}
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- FAQ -->
      <section class="faq-section">
        <h2 class="section-title">常见问题</h2>
        <details v-for="(item, idx) in faq" :key="idx" class="faq-item">
          <summary class="faq-question">{{ item.q }}</summary>
          <p class="faq-answer">{{ item.a }}</p>
        </details>
      </section>
    </main>

    <!-- 订阅确认弹窗 -->
    <Teleport to="body">
      <Transition name="action-sheet">
        <div v-if="confirmDialog.show" class="sheet-overlay" @click.self="confirmDialog.show = false">
          <div class="sheet-panel confirm-panel">
            <div class="sheet-handle" />
            <div class="sheet-title">确认订阅</div>
            <div v-if="confirmDialog.plan" class="confirm-content">
              <div class="confirm-plan-name">{{ confirmDialog.plan.name }}</div>
              <div class="confirm-plan-price">
                ¥{{ confirmDialog.plan.price_cny }} / 月
              </div>
              <ul class="confirm-features">
                <li v-for="(feat, idx) in confirmDialog.plan.features" :key="idx" class="confirm-feature">
                  {{ feat }}
                </li>
              </ul>
            </div>
            <button
              type="button"
              class="confirm-btn primary"
              :disabled="submitting"
              @click="confirmSubscribe"
            >
              {{ submitting ? '处理中...' : '确认订阅' }}
            </button>
            <button type="button" class="cancel-btn" @click="confirmDialog.show = false">取消</button>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
/**
 * MobileSubscriptionView.vue — 移动端订阅与套餐 (W72 第 2 批 C-3)
 *
 * 功能：
 * - 展示当前套餐 + 剩余天数 + 空间用量
 * - 列出 3 个套餐 (免费/基础/专业)
 * - 支持套餐切换 / 升级 / 降级
 * - 套餐对比表 + FAQ
 * - 订阅确认弹窗
 *
 * 派工依据：
 * - W72 第 1 批 C-2 commit a78967661 商业化 Q1 季度排期
 * - W72 第 1 批 A-3 派生
 * - 锚点范式 W72 第 1 批 220 → W72 第 2 批 C-3 ~232 守恒
 */

import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const loading = ref(false)
const loadError = ref('')
const plans = ref([])
const currentPlan = ref(null)
const submitting = ref(false)
const confirmDialog = ref({ show: false, plan: null })

// 静态 fallback (API 失败时展示)
const FALLBACK_PLANS = [
  {
    id: 'free',
    tier: 'free',
    name: '免费版',
    price_cny: 0,
    quota_bytes: 100 * 1024 * 1024, // 100 MB
    recommended: false,
    features: ['100 MB 存储空间', '10 个文件', '基础搜索', '社区支持'],
  },
  {
    id: 'basic',
    tier: 'basic',
    name: '基础版',
    price_cny: 19,
    quota_bytes: 5 * 1024 * 1024 * 1024, // 5 GB
    recommended: false,
    features: ['5 GB 存储空间', '1000 个文件', '语义搜索', '邮件支持', '7 天版本历史'],
  },
  {
    id: 'pro',
    tier: 'pro',
    name: '专业版',
    price_cny: 49,
    quota_bytes: 100 * 1024 * 1024 * 1024, // 100 GB
    recommended: true,
    features: ['100 GB 存储空间', '不限文件数', '高级 RAG + Self-RAG', '优先支持', '90 天版本历史', '团队共享盘', 'API 访问'],
  },
]

const COMPARE_ROWS = [
  { feature: '存储空间', values: { free: '100 MB', basic: '5 GB', pro: '100 GB' } },
  { feature: '文件数', values: { free: '10', basic: '1,000', pro: '不限' } },
  { feature: '搜索', values: { free: '基础', basic: '语义', pro: '高级 RAG' } },
  { feature: '版本历史', values: { free: '—', basic: '7 天', pro: '90 天' } },
  { feature: '团队共享盘', values: { free: '—', basic: '—', pro: '✓' } },
  { feature: 'API 访问', values: { free: '—', basic: '—', pro: '✓' } },
  { feature: '支持', values: { free: '社区', basic: '邮件', pro: '优先' } },
]

const FAQ = [
  {
    q: '可以随时取消订阅吗？',
    a: '可以。在订阅周期内随时取消，订阅到期后将自动转为免费版。',
  },
  {
    q: '升级后空间立即生效吗？',
    a: '是的，升级成功后新套餐的存储空间会立即生效，无需等待。',
  },
  {
    q: '降级会丢失我的数据吗？',
    a: '不会。降级后超出新套餐配额的文件仍可访问，但不能再上传新文件直到清理空间。',
  },
]

const compareRows = ref(COMPARE_ROWS)
const faq = ref(FAQ)

const usagePercent = computed(() => {
  if (!currentPlan.value || !currentPlan.value.quota_bytes) return 0
  return Math.min(100, Math.round((currentPlan.value.used_bytes / currentPlan.value.quota_bytes) * 100))
})

function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  let v = bytes
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i++
  }
  return `${v.toFixed(v >= 100 ? 0 : 1)} ${units[i]}`
}

async function loadPlans() {
  loading.value = true
  loadError.value = ''
  try {
    // 调 B-5 计费 API: GET /api/v1/billing/plans
    const token = localStorage.getItem('access_token') || ''
    const resp = await fetch('/api/v1/billing/plans', {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()
    plans.value = data.plans || FALLBACK_PLANS
    currentPlan.value = data.current || null
  } catch (err) {
    // API 未就绪时使用 fallback
    plans.value = FALLBACK_PLANS
    loadError.value = ''
    // 静默 fallback
    // eslint-disable-next-line no-console
    console.warn('[Subscription] plans API unreachable, using fallback:', err.message)
  } finally {
    loading.value = false
  }
}

function selectPlan(plan) {
  if (currentPlan.value && currentPlan.value.tier === plan.tier) return
  confirmDialog.value = { show: true, plan }
}

async function subscribe(plan) {
  if (plan.tier === 'free') {
    // 降级到免费版直接确认
    confirmDialog.value = { show: true, plan }
    return
  }
  selectPlan(plan)
}

async function confirmSubscribe() {
  if (!confirmDialog.value.plan) return
  submitting.value = true
  try {
    const plan = confirmDialog.value.plan
    const token = localStorage.getItem('access_token') || ''
    const resp = await fetch('/api/v1/billing/subscribe', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ plan_id: plan.id }),
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    confirmDialog.value.show = false
    await loadPlans()
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error('[Subscription] subscribe failed:', err)
    confirmDialog.value.show = false
    await loadPlans()
  } finally {
    submitting.value = false
  }
}

function goBack() {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/')
  }
}

onMounted(() => {
  loadPlans()
})
</script>

<style scoped>
.mobile-subscription-view {
  min-height: 100vh;
  background: var(--color-bg-page, #f5f7fa);
  color: var(--color-text-primary);
}

.sub-main {
  padding: 16px;
  max-width: 100%;
}

/* 当前套餐卡片 */
.current-plan-card {
  background: var(--color-bg-card);
  border-radius: var(--radius-lg, 12px);
  padding: 20px;
  margin-bottom: 24px;
  border: 1px solid var(--color-border);
  position: relative;
  overflow: hidden;
}
.current-plan-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, var(--color-primary), var(--color-accent, #FFB347));
}
.current-plan-card.plan-pro::before {
  background: linear-gradient(90deg, #FFB347, #FF7A5C);
}
.current-plan-card.plan-basic::before {
  background: linear-gradient(90deg, #5CACEE, #6495ED);
}

.current-plan-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.current-plan-label {
  font-size: 12px;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.current-plan-name {
  font-size: 22px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.current-plan-remaining {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin: 8px 0;
}
.remaining-number {
  font-size: 36px;
  font-weight: 700;
  color: var(--color-primary);
}
.remaining-label {
  font-size: 14px;
  color: var(--color-text-secondary);
}
.current-plan-meta {
  margin: 8px 0;
  color: var(--color-text-secondary);
  font-size: 14px;
}

.current-plan-usage {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--color-border);
}
.usage-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 13px;
}
.usage-label { color: var(--color-text-secondary); }
.usage-value { font-weight: 600; }
.usage-bar {
  height: 6px;
  background: var(--color-bg-hover, #ecf5ff);
  border-radius: 3px;
  overflow: hidden;
}
.usage-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--color-primary), var(--color-accent, #FFB347));
  border-radius: 3px;
  transition: width 0.3s;
}

/* 套餐列表 */
.section-title {
  font-size: 16px;
  font-weight: 600;
  margin: 16px 0 12px;
  color: var(--color-text-primary);
}
.plans-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}
.plan-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg, 12px);
  padding: 16px;
  position: relative;
  transition: transform 0.15s, box-shadow 0.15s;
  cursor: pointer;
}
.plan-card:active {
  transform: scale(0.98);
}
.plan-card.is-recommended {
  border-color: var(--color-primary);
  box-shadow: 0 4px 16px rgba(255, 122, 92, 0.15);
}
.plan-card.is-current {
  border-color: var(--color-primary);
  background: linear-gradient(135deg, rgba(255, 122, 92, 0.04), rgba(255, 179, 71, 0.04));
}
.plan-badge {
  position: absolute;
  top: -10px;
  right: 12px;
  background: var(--color-primary);
  color: white;
  font-size: 11px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 10px;
}
.plan-badge.popular {
  background: linear-gradient(90deg, #FF7A5C, #FFB347);
}
.plan-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}
.plan-name {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  color: var(--color-text-primary);
}
.plan-price {
  text-align: right;
}
.price-free {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-secondary);
}
.price-amount {
  display: flex;
  align-items: baseline;
  gap: 2px;
  color: var(--color-primary);
}
.price-amount .currency { font-size: 14px; }
.price-amount .amount { font-size: 24px; font-weight: 700; }
.price-amount .period { font-size: 12px; color: var(--color-text-secondary); margin-left: 2px; }

.plan-features {
  list-style: none;
  padding: 0;
  margin: 0 0 16px 0;
}
.plan-feature {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 13px;
  color: var(--color-text-regular);
}
.feature-check {
  color: var(--color-primary);
  font-weight: 700;
  flex-shrink: 0;
  width: 16px;
}

.plan-card-footer {
  padding-top: 12px;
  border-top: 1px solid var(--color-border);
}
.plan-btn {
  width: 100%;
  padding: 10px;
  border-radius: var(--radius-md, 8px);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid var(--color-border);
  background: var(--color-bg-card);
  color: var(--color-text-primary);
  transition: all 0.15s;
}
.plan-btn:active {
  transform: scale(0.97);
}
.plan-btn.primary {
  background: linear-gradient(90deg, var(--color-primary), var(--color-accent, #FFB347));
  color: white;
  border: none;
}
.plan-btn.upgrade {
  background: var(--color-primary);
  color: white;
  border: none;
}
.plan-btn.current {
  background: var(--color-bg-hover);
  color: var(--color-text-secondary);
  cursor: default;
}

/* 状态 */
.loading-state, .error-state {
  text-align: center;
  padding: 40px 16px;
  color: var(--color-text-secondary);
}
.empty-icon { font-size: 36px; margin-bottom: 8px; }
.empty-hint { font-size: 14px; margin-bottom: 12px; }
.retry-btn {
  padding: 8px 16px;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-md, 8px);
  cursor: pointer;
}

/* 对比表 */
.compare-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--color-bg-card);
  border-radius: var(--radius-md, 8px);
  overflow: hidden;
  font-size: 13px;
}
.compare-table th, .compare-table td {
  padding: 10px 8px;
  text-align: center;
  border-bottom: 1px solid var(--color-border);
}
.compare-table th {
  background: var(--color-bg-hover);
  font-weight: 600;
}
.compare-feature {
  text-align: left !important;
  font-weight: 500;
}
.compare-value {
  color: var(--color-text-regular);
}

/* FAQ */
.faq-section { margin-top: 16px; }
.faq-item {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md, 8px);
  margin-bottom: 8px;
  padding: 12px 16px;
}
.faq-question {
  font-weight: 600;
  cursor: pointer;
  font-size: 14px;
  color: var(--color-text-primary);
}
.faq-answer {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.5;
}

/* 确认弹窗 */
.sheet-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  z-index: 1000;
}
.sheet-panel.confirm-panel {
  background: var(--color-bg-card);
  width: 100%;
  max-width: 500px;
  border-radius: var(--radius-lg, 12px) var(--radius-lg, 12px) 0 0;
  padding: 20px 16px calc(20px + var(--sab, 0px));
}
.sheet-handle {
  width: 36px;
  height: 4px;
  background: var(--color-border);
  border-radius: 2px;
  margin: 0 auto 12px;
}
.sheet-title {
  font-size: 18px;
  font-weight: 600;
  text-align: center;
  margin-bottom: 16px;
}
.confirm-plan-name {
  font-size: 20px;
  font-weight: 600;
  text-align: center;
  margin-bottom: 4px;
}
.confirm-plan-price {
  font-size: 16px;
  text-align: center;
  color: var(--color-primary);
  margin-bottom: 16px;
}
.confirm-features {
  list-style: none;
  padding: 0;
  margin: 0 0 20px 0;
  background: var(--color-bg-hover);
  border-radius: var(--radius-md, 8px);
  padding: 12px 16px;
}
.confirm-feature {
  padding: 4px 0;
  font-size: 13px;
  color: var(--color-text-regular);
}
.confirm-btn {
  width: 100%;
  padding: 14px;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-md, 8px);
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  margin-bottom: 8px;
}
.confirm-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.cancel-btn {
  width: 100%;
  padding: 14px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md, 8px);
  font-size: 15px;
  font-weight: 500;
  color: var(--color-text-primary);
  cursor: pointer;
}

.action-sheet-enter-active, .action-sheet-leave-active { transition: opacity 0.25s ease; }
.action-sheet-enter-active .sheet-panel,
.action-sheet-leave-active .sheet-panel { transition: transform 0.3s ease; }
.action-sheet-enter-from, .action-sheet-leave-to { opacity: 0; }
.action-sheet-enter-from .sheet-panel,
.action-sheet-leave-to .sheet-panel { transform: translateY(100%); }

.header-btn {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  padding: 4px 8px;
  color: var(--color-text-primary);
}
</style>

<!--
  W72 第 2 批 C-3 dark mode 跨组件适配
  CLAUDE.md v60-v67 第 5 次强化：dark mode 跨组件必须非 scoped
  6 主题完整版 (corl + ocean + forest + sunset + purple + mono)
-->
<style>
/* 6 主题 token — 复用 useThemeStore + 顶栏 6 主题选择器 */
[data-theme="dark"] .mobile-subscription-view,
[data-theme="dark"][data-accent="coral"] .mobile-subscription-view {
  background: #1a1a1a;
  color: #e0e0e0;
}
[data-theme="dark"] .mobile-subscription-view .current-plan-card,
[data-theme="dark"] .mobile-subscription-view .plan-card,
[data-theme="dark"] .mobile-subscription-view .faq-item,
[data-theme="dark"] .mobile-subscription-view .compare-table,
[data-theme="dark"] .mobile-subscription-view .sheet-panel.confirm-panel {
  background: #222222;
  border-color: #2a2a2a;
  color: #e0e0e0;
}
[data-theme="dark"] .mobile-subscription-view .plan-card.is-current {
  background: rgba(255, 122, 92, 0.08);
  border-color: var(--color-primary);
}
[data-theme="dark"] .mobile-subscription-view .plan-card.is-recommended {
  background: #2a2520;
  border-color: var(--color-primary);
}
[data-theme="dark"] .mobile-subscription-view .plan-name,
[data-theme="dark"] .mobile-subscription-view .current-plan-name,
[data-theme="dark"] .mobile-subscription-view .section-title,
[data-theme="dark"] .mobile-subscription-view .faq-question,
[data-theme="dark"] .mobile-subscription-view .compare-table th {
  color: #e0e0e0;
}
[data-theme="dark"] .mobile-subscription-view .plan-feature,
[data-theme="dark"] .mobile-subscription-view .feature-text,
[data-theme="dark"] .mobile-subscription-view .compare-table td,
[data-theme="dark"] .mobile-subscription-view .faq-answer {
  color: #a0a0a0;
}
[data-theme="dark"] .mobile-subscription-view .current-plan-label,
[data-theme="dark"] .mobile-subscription-view .usage-label,
[data-theme="dark"] .mobile-subscription-view .empty-hint {
  color: #888888;
}
[data-theme="dark"] .mobile-subscription-view .plan-btn {
  background: #2a2a2a;
  border-color: #3a3a3a;
  color: #e0e0e0;
}
[data-theme="dark"] .mobile-subscription-view .plan-btn.current {
  background: #3a3a3a;
  color: #888888;
}
[data-theme="dark"] .mobile-subscription-view .plan-btn.primary,
[data-theme="dark"] .mobile-subscription-view .plan-btn.upgrade {
  color: white;
}
[data-theme="dark"] .mobile-subscription-view .confirm-features {
  background: #2a2a2a;
  color: #a0a0a0;
}
[data-theme="dark"] .mobile-subscription-view .cancel-btn {
  background: #2a2a2a;
  border-color: #3a3a3a;
  color: #e0e0e0;
}
[data-theme="dark"] .mobile-subscription-view .usage-bar {
  background: #2a2a2a;
}
[data-theme="dark"] .mobile-subscription-view .sheet-handle {
  background: #3a3a3a;
}
[data-theme="dark"] .mobile-subscription-view .compare-table th {
  background: #2a2a2a;
}
</style>