<!--
  支付方式选择器 (W74 第 1 批 B-2 真支付接入)

  3 支付方式:
  - stripe (国际信用卡)
  - alipay (支付宝)
  - wechat_pay (微信支付)

  派工 v6 段 5 反馈 #6 实战:
  - 3 支付方式均 mock (真接入主拍拍板)
  - 6 主题 dark mode 适配
  - 移动端 long-press navigator.vibrate(10) 触觉反馈
-->
<template>
  <div class="payment-method-selector">
    <h3 class="title">选择支付方式</h3>
    <p class="subtitle">3 支付方式均 mock, 真接入须主拍单独拍板 (派工 v6 段 5 反馈 #6 实战)</p>

    <div class="methods-grid">
      <div
        v-for="method in paymentMethods"
        :key="method.provider"
        :class="['method-card', { 'method-card-selected': selected === method.provider }]"
        :data-provider="method.provider"
        @click="selectMethod(method.provider)"
      >
        <div class="method-icon">
          <span :class="['icon', `icon-${method.provider}`]">{{ method.icon }}</span>
        </div>
        <div class="method-info">
          <div class="method-name">{{ method.name }}</div>
          <div class="method-desc">{{ method.description }}</div>
        </div>
        <div class="method-radio">
          <el-radio v-model="selected" :label="method.provider">
            <span class="sr-only">{{ method.name }}</span>
          </el-radio>
        </div>
      </div>
    </div>

    <div class="actions">
      <el-button
        type="primary"
        size="large"
        :disabled="!selected"
        :loading="loading"
        @click="confirmPayment"
        @touchstart="onTouchStart"
        @touchend="onTouchEnd"
        class="confirm-button"
      >
        确认支付 ({{ formatAmount }})
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const props = defineProps({
  invoiceId: { type: String, required: true },
  amountCents: { type: Number, required: true },
  currency: { type: String, default: 'CNY' },
  tenantId: { type: String, required: true },
  apiKey: { type: String, required: true },
})

const emit = defineEmits(['payment-success', 'payment-error'])

const selected = ref('mock')
const loading = ref(false)
const longPressTimer = ref(null)

const paymentMethods = [
  {
    provider: 'stripe',
    name: 'Stripe',
    description: '国际信用卡 (Visa / Master / AmEx)',
    icon: '💳',
  },
  {
    provider: 'alipay',
    name: '支付宝',
    description: '中国主流移动支付',
    icon: '🅰️',
  },
  {
    provider: 'wechat_pay',
    name: '微信支付',
    description: '微信扫码 / JSAPI',
    icon: '💚',
  },
]

const formatAmount = computed(() => {
  return `¥${(props.amountCents / 100).toFixed(2)}`
})

function selectMethod(provider) {
  selected.value = provider
  // 移动端 long-press 触觉反馈 (W72 第 2 批 C-3 实战)
  if (navigator.vibrate) {
    navigator.vibrate(10)
  }
}

function onTouchStart() {
  // 长按反馈 (移动端)
  if (navigator.vibrate) {
    longPressTimer.value = setTimeout(() => {
      navigator.vibrate(10)
    }, 200)
  }
}

function onTouchEnd() {
  if (longPressTimer.value) {
    clearTimeout(longPressTimer.value)
    longPressTimer.value = null
  }
}

async function confirmPayment() {
  if (!selected.value) {
    ElMessage.warning('请选择支付方式')
    return
  }
  loading.value = true
  try {
    // Step 1: init payment
    const initResp = await axios.post(
      '/api/v1/commercial/billing/payments/init',
      {
        invoice_id: props.invoiceId,
        provider: selected.value,
      },
      {
        headers: {
          'X-Tenant-ID': props.tenantId,
          'X-API-Key': props.apiKey,
        },
      }
    )
    const { payment_id } = initResp.data

    // Step 2: confirm payment
    const confirmResp = await axios.post(
      `/api/v1/commercial/billing/payments/${payment_id}/confirm`,
      {},
      {
        headers: {
          'X-Tenant-ID': props.tenantId,
          'X-API-Key': props.apiKey,
        },
      }
    )

    ElMessage.success(`支付成功 (${selected.value})`)
    emit('payment-success', { ...confirmResp.data, payment_id })
  } catch (err) {
    console.error('payment failed:', err)
    ElMessage.error(`支付失败: ${err.response?.data?.detail || err.message}`)
    emit('payment-error', err)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.payment-method-selector {
  padding: 16px;
}
.title {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--color-text-primary, #333);
}
.subtitle {
  font-size: 13px;
  color: var(--color-text-secondary, #666);
  margin-bottom: 24px;
}
.methods-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}
.method-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border: 2px solid var(--color-border-light, #eee);
  border-radius: 12px;
  cursor: pointer;
  transition: border-color 0.2s, background-color 0.2s;
  background: var(--color-bg-card, #fff);
}
.method-card:hover {
  border-color: var(--color-primary, #FF7A5C);
}
.method-card-selected {
  border-color: var(--color-primary, #FF7A5C);
  background-color: rgba(255, 122, 92, 0.06);
}
.method-icon {
  font-size: 32px;
  flex-shrink: 0;
}
.method-info {
  flex: 1;
  min-width: 0;
}
.method-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary, #333);
  margin-bottom: 4px;
}
.method-desc {
  font-size: 12px;
  color: var(--color-text-secondary, #666);
}
.method-radio {
  flex-shrink: 0;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
}
.actions {
  margin-top: 24px;
}
.confirm-button {
  width: 100%;
}

/* Dark mode (W72 第 2 批 C-3 实战: 6 主题 dark mode) */
:root[data-theme="dark"] .method-card,
html[data-theme="dark"] .method-card,
html.dark .method-card,
.theme-dark .method-card {
  background-color: var(--color-bg-card-dark, #1f1f1f);
  border-color: var(--color-border-dark, #333);
}
:root[data-theme="dark"] .title,
html[data-theme="dark"] .title,
html.dark .title,
.theme-dark .title {
  color: var(--color-text-primary-dark, #e0e0e0);
}
</style>