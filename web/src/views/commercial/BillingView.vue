<template>
  <div class="billing-view">
    <el-card class="header-card">
      <h2>商业化订阅</h2>
      <p class="subtitle">当前订阅状态、用量统计、账单管理</p>
    </el-card>

    <div v-if="loading" class="loading-state">
      <el-skeleton :rows="6" animated />
    </div>

    <div v-else>
      <el-card class="plan-card" v-if="currentPlan">
        <div class="plan-header">
          <div>
            <h3>{{ currentPlan.display_name }}</h3>
            <el-tag :type="subscription ? 'success' : 'info'" size="small">
              {{ subscription ? '已订阅' : '未订阅' }}
            </el-tag>
          </div>
          <div v-if="subscription" class="plan-price">
            ¥{{ formatCents(currentPlan.monthly_price_cents) }}/月
          </div>
        </div>
        <div v-if="subscription" class="plan-expiry">
          到期: {{ formatDate(subscription.expires_at) }}
        </div>
      </el-card>

      <el-card class="usage-card">
        <h3>用量统计</h3>
        <el-table :data="usageRows" stripe>
          <el-table-column prop="metric" label="指标" />
          <el-table-column prop="value" label="用量" />
        </el-table>
      </el-card>

      <el-card class="invoice-card">
        <h3>账单管理</h3>
        <PlanSelector @plan-selected="onPlanSelected" />
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import axios from 'axios'
import PlanSelector from './PlanSelector.vue'
import { ElMessage } from 'element-plus'

const loading = ref(true)
const plans = ref([])
const tenant = ref(null)
const subscription = ref(null)
const usage = ref({ summary: {} })

const currentPlan = computed(() => {
  if (!tenant.value) return null
  return plans.value.find(p => p.plan_code === tenant.value.plan_code)
})

const usageRows = computed(() => {
  return Object.entries(usage.value.summary).map(([metric, value]) => ({ metric, value }))
})

function formatCents(cents) {
  return (cents / 100).toFixed(2)
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('zh-CN')
}

const headers = {
  'X-Tenant-ID': localStorage.getItem('mb_tenant_id') || '',
  'X-API-Key': localStorage.getItem('mb_api_key') || ''
}

async function loadAll() {
  loading.value = true
  try {
    const [plansRes, meRes, subRes, usageRes] = await Promise.all([
      axios.get('/api/v1/commercial/billing/plans'),
      axios.get('/api/v1/commercial/billing/tenants/me', { headers }),
      axios.get('/api/v1/commercial/billing/subscriptions/me', { headers }).catch(() => ({ data: null })),
      axios.get('/api/v1/commercial/billing/usage/summary', { headers }).catch(() => ({ data: { summary: {} } }))
    ])
    plans.value = plansRes.data
    tenant.value = meRes.data
    subscription.value = subRes.data
    usage.value = usageRes.data
  } catch (e) {
    ElMessage.error('加载失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

async function onPlanSelected(plan) {
  try {
    const { data: invoice } = await axios.post('/api/v1/commercial/billing/invoices', {
      plan_code: plan.plan_code,
      period: 'monthly',
      payment_provider: 'mock'
    }, { headers })
    await axios.post(`/api/v1/commercial/billing/invoices/${invoice.invoice_id}/pay`, {}, { headers })
    ElMessage.success(`订阅 ${plan.display_name} 成功`)
    await loadAll()
  } catch (e) {
    ElMessage.error('订阅失败: ' + (e.response?.data?.detail || e.message))
  }
}

onMounted(loadAll)
</script>

<style scoped>
.billing-view {
  padding: 24px;
  max-width: 960px;
  margin: 0 auto;
}
.header-card {
  margin-bottom: 24px;
}
.subtitle {
  color: var(--color-text-secondary, #666);
  margin-top: 8px;
}
.plan-card, .usage-card, .invoice-card {
  margin-bottom: 24px;
}
.plan-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.plan-price {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-primary, #FF7A5C);
}
.plan-expiry {
  margin-top: 8px;
  color: var(--color-text-secondary, #666);
}
h3 {
  margin-top: 0;
}
</style>
