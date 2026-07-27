<template>
  <div class="plan-selector">
    <el-radio-group v-model="selectedPeriod" class="period-toggle">
      <el-radio-button label="monthly">月付</el-radio-button>
      <el-radio-button label="yearly">年付</el-radio-button>
    </el-radio-group>

    <div class="plan-grid">
      <el-card
        v-for="plan in plans"
        :key="plan.plan_code"
        :class="['plan-card', { 'plan-card-featured': plan.plan_code === 'pro' }]"
        shadow="hover"
      >
        <div class="plan-name">{{ plan.display_name }}</div>
        <div class="plan-price">
          <span class="price-currency">¥</span>
          <span class="price-value">{{ formatPrice(plan) }}</span>
          <span class="price-period">/{{ selectedPeriod === 'monthly' ? '月' : '年' }}</span>
        </div>
        <ul class="plan-features">
          <li v-for="(limit, metric) in plan.limits" :key="metric">
            {{ metric }}: {{ formatLimit(metric, limit) }}
          </li>
        </ul>
        <el-button
          type="primary"
          :disabled="currentPlanCode === plan.plan_code"
          @click="selectPlan(plan)"
          class="plan-button"
        >
          {{ currentPlanCode === plan.plan_code ? '当前' : '选择' }}
        </el-button>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  plans: { type: Array, default: () => [] },
  currentPlanCode: { type: String, default: 'free' }
})

const emit = defineEmits(['plan-selected'])

const selectedPeriod = ref('monthly')

function formatPrice(plan) {
  const cents = selectedPeriod.value === 'monthly' ? plan.monthly_price_cents : plan.yearly_price_cents
  return (cents / 100).toFixed(0)
}

function formatLimit(metric, value) {
  if (metric === 'storage_mb') return value >= 1024 ? `${(value / 1024).toFixed(0)} GB` : `${value} MB`
  if (metric === 'api_calls') return value.toLocaleString() + ' 次/月'
  return value
}

function selectPlan(plan) {
  emit('plan-selected', { plan_code: plan.plan_code, period: selectedPeriod.value })
}
</script>

<style scoped>
.plan-selector {
  padding: 16px 0;
}
.period-toggle {
  margin-bottom: 24px;
}
.plan-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}
.plan-card {
  text-align: center;
  border: 2px solid transparent;
  transition: border-color 0.2s;
}
.plan-card-featured {
  border-color: var(--color-primary, #FF7A5C);
}
.plan-name {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 12px;
}
.plan-price {
  margin-bottom: 16px;
}
.price-currency {
  font-size: 14px;
  vertical-align: top;
}
.price-value {
  font-size: 36px;
  font-weight: 700;
  color: var(--color-primary, #FF7A5C);
}
.price-period {
  font-size: 12px;
  color: var(--color-text-secondary, #666);
}
.plan-features {
  list-style: none;
  padding: 0;
  margin: 0 0 16px 0;
  text-align: left;
  font-size: 13px;
  color: var(--color-text-secondary, #666);
}
.plan-features li {
  padding: 4px 0;
}
.plan-button {
  width: 100%;
}
</style>
