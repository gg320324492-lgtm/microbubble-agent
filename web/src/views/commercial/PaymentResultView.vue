<!--
  支付结果页 (W74 第 1 批 B-2 真支付接入)

  支付成功 / 失败 / 退款 3 状态显示
  派工 v6 段 5 反馈 #6 实战:
  - 6 主题 dark mode 适配
  - 移动端 long-press navigator.vibrate(10) 触觉反馈
-->
<template>
  <div class="payment-result-view">
    <div :class="['result-card', `result-${statusType}`]">
      <div class="result-icon">
        <span class="icon-large">{{ statusIcon }}</span>
      </div>

      <h2 class="result-title">{{ statusTitle }}</h2>

      <div class="result-details" v-if="payment">
        <div class="detail-row">
          <span class="label">支付 ID</span>
          <span class="value">{{ payment.payment_id }}</span>
        </div>
        <div class="detail-row" v-if="payment.intent_id">
          <span class="label">Intent ID</span>
          <span class="value">{{ payment.intent_id }}</span>
        </div>
        <div class="detail-row" v-if="payment.provider">
          <span class="label">支付方式</span>
          <span class="value provider-badge">{{ payment.provider }}</span>
        </div>
        <div class="detail-row" v-if="payment.amount_cents">
          <span class="label">金额</span>
          <span class="value">¥{{ formatAmount(payment.amount_cents) }}</span>
        </div>
        <div class="detail-row" v-if="payment.completed_at">
          <span class="label">完成时间</span>
          <span class="value">{{ formatDate(payment.completed_at) }}</span>
        </div>
      </div>

      <div class="result-message" v-if="message">
        {{ message }}
      </div>

      <div class="actions">
        <el-button
          type="primary"
          size="large"
          @click="onReturn"
          @touchstart="onTouchStart"
          class="return-button"
        >
          返回账单
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps({
  payment: { type: Object, default: () => null },
  status: { type: String, default: 'success' },  // success / failed / pending / refunded
  message: { type: String, default: '' },
})

const emit = defineEmits(['return'])

const router = useRouter()

const statusType = computed(() => {
  return ['success', 'failed', 'pending', 'refunded'].includes(props.status) ? props.status : 'failed'
})

const statusIcon = computed(() => {
  const icons = {
    success: '✓',
    failed: '✗',
    pending: '⏳',
    refunded: '↩',
  }
  return icons[statusType.value] || '?'
})

const statusTitle = computed(() => {
  const titles = {
    success: '支付成功',
    failed: '支付失败',
    pending: '支付处理中',
    refunded: '已退款',
  }
  return titles[statusType.value] || '未知状态'
})

function formatAmount(cents) {
  return (cents / 100).toFixed(2)
}

function formatDate(isoString) {
  if (!isoString) return ''
  try {
    return new Date(isoString).toLocaleString('zh-CN')
  } catch {
    return isoString
  }
}

function onTouchStart() {
  // 移动端触觉反馈
  if (navigator.vibrate) {
    navigator.vibrate(10)
  }
}

function onReturn() {
  emit('return')
  router.push('/commercial/billing')
}
</script>

<style scoped>
.payment-result-view {
  padding: 24px 16px;
  max-width: 600px;
  margin: 0 auto;
}
.result-card {
  text-align: center;
  padding: 48px 24px;
  border-radius: 16px;
  background: var(--color-bg-card, #fff);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  border-top: 4px solid var(--color-primary, #FF7A5C);
}
.result-success {
  border-top-color: #67c23a;
}
.result-failed {
  border-top-color: #f56c6c;
}
.result-pending {
  border-top-color: #e6a23c;
}
.result-refunded {
  border-top-color: #909399;
}
.result-icon {
  font-size: 72px;
  margin-bottom: 16px;
}
.icon-large {
  display: inline-block;
  width: 96px;
  height: 96px;
  line-height: 96px;
  border-radius: 50%;
  background: var(--color-bg-soft, #f5f5f5);
}
.result-success .icon-large {
  background: rgba(103, 194, 58, 0.12);
  color: #67c23a;
}
.result-failed .icon-large {
  background: rgba(245, 108, 108, 0.12);
  color: #f56c6c;
}
.result-title {
  font-size: 24px;
  font-weight: 600;
  margin-bottom: 24px;
  color: var(--color-text-primary, #333);
}
.result-details {
  text-align: left;
  margin: 24px 0;
  padding: 16px;
  background: var(--color-bg-soft, #f5f5f5);
  border-radius: 8px;
}
.detail-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  font-size: 14px;
}
.label {
  color: var(--color-text-secondary, #666);
}
.value {
  color: var(--color-text-primary, #333);
  font-weight: 500;
  word-break: break-all;
  text-align: right;
  max-width: 60%;
}
.provider-badge {
  background: var(--color-primary, #FF7A5C);
  color: #fff;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}
.result-message {
  font-size: 14px;
  color: var(--color-text-secondary, #666);
  margin: 16px 0;
}
.actions {
  margin-top: 24px;
}
.return-button {
  min-width: 160px;
}

/* Dark mode (W72 第 2 批 C-3 实战: 6 主题 dark mode) */
:root[data-theme="dark"] .result-card,
html[data-theme="dark"] .result-card,
html.dark .result-card,
.theme-dark .result-card {
  background-color: var(--color-bg-card-dark, #1f1f1f);
  color: var(--color-text-primary-dark, #e0e0e0);
}
:root[data-theme="dark"] .result-title,
html[data-theme="dark"] .result-title,
html.dark .result-title,
.theme-dark .result-title {
  color: var(--color-text-primary-dark, #e0e0e0);
}
:root[data-theme="dark"] .result-details,
html[data-theme="dark"] .result-details,
html.dark .result-details,
.theme-dark .result-details {
  background-color: var(--color-bg-soft-dark, #2a2a2a);
}
:root[data-theme="dark"] .value,
html[data-theme="dark"] .value,
html.dark .value,
.theme-dark .value {
  color: var(--color-text-primary-dark, #e0e0e0);
}
</style>