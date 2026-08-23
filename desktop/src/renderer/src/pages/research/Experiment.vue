<script setup lang="ts">
/**
 * 实验设计 — 升级版：AI假设生成 + 设计卡 + 分组展示。
 */
import { onMounted, ref } from 'vue'
import { useExperimentStore } from '../../stores/research/experiment.store'
import { experimentService } from '../../services/research/experiment.service'
import Timeline from '../../components/research/Timeline.vue'
import StatusBadge from '../../components/research/StatusBadge.vue'

const store = useExperimentStore()
const generatedHypotheses = ref<Array<{ statement: string; confidence: number }>>([])
const isGenerating = ref(false)
onMounted(() => store.loadDesign())

const steps = [
  { label: '研究问题定义', status: 'done' as const },
  { label: '科学假设生成', status: 'done' as const },
  { label: '变量与分组设计', status: 'done' as const },
  { label: '评价指标确定', status: 'current' as const },
  { label: '推荐分析模型', status: 'pending' as const },
]

async function genHypotheses() {
  if (!store.design || isGenerating.value) return
  isGenerating.value = true
  try { generatedHypotheses.value = await experimentService.generateHypotheses(store.design.question) }
  finally { isGenerating.value = false }
}

function varLabel(type: string) { return type === 'independent' ? '自变量' : type === 'dependent' ? '因变量' : '控制变量' }
function varStatus(type: string): 'success' | 'info' | 'neutral' { return type === 'dependent' ? 'info' : type === 'control' ? 'neutral' : 'success' }
</script>

<template>
  <div class="experiment" v-if="store.design">
    <div class="experiment__header">
      <h1 class="experiment__title">实验设计</h1>
      <StatusBadge :status="store.design.status === 'running' ? 'info' : 'success'" :label="store.design.status === 'running' ? '运行中' : '设计阶段'" />
    </div>

    <div class="experiment__body">
      <div class="experiment__workflow">
        <h3>设计流程</h3>
        <Timeline :steps="steps" />
      </div>

      <div class="experiment__content">
        <!-- 研究问题 -->
        <div class="experiment__section">
          <h3>研究问题</h3>
          <div class="experiment__question">{{ store.design.question }}</div>
        </div>

        <!-- AI 假设生成 -->
        <div class="experiment__section">
          <div class="experiment__section-header">
            <h3>科学假设</h3>
            <button class="experiment__gen-btn" @click="genHypotheses" :disabled="isGenerating">
              {{ isGenerating ? '生成中...' : 'AI 生成假设' }}
            </button>
          </div>
          <div class="experiment__hypothesis" v-for="(h, i) in store.design.hypotheses" :key="i">
            <span class="experiment__hypothesis-label">H{{ i + 1 }}</span>
            <div>
              <div>{{ h.statement }}</div>
              <div class="experiment__confidence">置信度 {{ (h.confidence * 100).toFixed(0) }}%</div>
            </div>
          </div>
          <div v-if="generatedHypotheses.length" class="experiment__gen-results">
            <div class="experiment__gen-label">AI 生成的新假设：</div>
            <div class="experiment__hypothesis" v-for="(h, i) in generatedHypotheses" :key="'gen-'+i">
              <span class="experiment__hypothesis-label">H{{ store.design.hypotheses.length + i + 1 }}</span>
              <div>
                <div>{{ h.statement }}</div>
                <div class="experiment__confidence">置信度 {{ (h.confidence * 100).toFixed(0) }}%</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 变量设计 -->
        <div class="experiment__section">
          <h3>变量设计</h3>
          <table class="experiment__table">
            <thead><tr><th>变量名</th><th>类型</th><th>范围</th></tr></thead>
            <tbody>
              <tr v-for="v in store.design.variables" :key="v.name">
                <td>{{ v.name }}</td>
                <td><StatusBadge :status="varStatus(v.type)" :label="varLabel(v.type)" /></td>
                <td>{{ v.range }} {{ v.unit }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 实验组 -->
        <div class="experiment__section">
          <h3>实验分组</h3>
          <table class="experiment__table">
            <thead><tr><th>组别</th><th>条件</th><th>目的</th></tr></thead>
            <tbody>
              <tr v-for="g in store.design.groups" :key="g.name">
                <td><strong>{{ g.name }}</strong></td>
                <td>{{ g.condition }}</td>
                <td>{{ g.purpose ?? '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 评价指标 -->
        <div class="experiment__section">
          <h3>评价指标</h3>
          <div class="experiment__metrics">
            <span class="experiment__metric" v-for="m in store.design.metrics" :key="m">{{ m }}</span>
          </div>
        </div>
      </div>

      <div class="experiment__right">
        <h3>推荐分析模型</h3>
        <div class="experiment__model-card">
          <div class="experiment__model-name">{{ store.design.model.name }}</div>
          <div class="experiment__model-conf">置信度 {{ (store.design.model.confidence * 100).toFixed(0) }}%</div>
        </div>
      </div>
    </div>
  </div>
  <div v-else class="experiment__empty">正在加载实验设计...</div>
</template>

<style scoped>
.experiment { padding: 24px 28px; }
.experiment__empty { padding: 40px; text-align: center; color: #94a3b8; }
.experiment__header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
.experiment__title { margin: 0; font-size: 20px; font-weight: 700; color: #0f172a; }
.experiment__body { display: grid; grid-template-columns: 180px 1fr 220px; gap: 20px; }
.experiment__workflow { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; }
.experiment__workflow h3 { margin: 0 0 12px; font-size: 13px; font-weight: 600; color: #0f172a; }
.experiment__content { display: flex; flex-direction: column; gap: 16px; }
.experiment__section { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; }
.experiment__section h3 { margin: 0 0 10px; font-size: 14px; font-weight: 600; color: #0f172a; }
.experiment__section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.experiment__section-header h3 { margin: 0; }
.experiment__gen-btn { padding: 6px 12px; background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 6px; font-size: 12px; color: #2563eb; cursor: pointer; }
.experiment__gen-btn:hover { background: #dbeafe; }
.experiment__gen-btn:disabled { opacity: .5; cursor: not-allowed; }
.experiment__gen-results { margin-top: 12px; padding-top: 12px; border-top: 1px solid #e5e7eb; }
.experiment__gen-label { font-size: 12px; color: #3b82f6; font-weight: 500; margin-bottom: 8px; }
.experiment__question { font-size: 15px; font-weight: 600; color: #1e293b; }
.experiment__hypothesis { display: flex; gap: 10px; margin-bottom: 10px; font-size: 13px; color: #334155; }
.experiment__hypothesis-label { font-weight: 700; color: #3b82f6; flex-shrink: 0; }
.experiment__confidence { font-size: 12px; color: #10b981; margin-top: 2px; }
.experiment__table { width: 100%; border-collapse: collapse; font-size: 13px; }
.experiment__table th { text-align: left; padding: 8px; color: #64748b; border-bottom: 1px solid #e5e7eb; font-weight: 500; }
.experiment__table td { padding: 8px; border-bottom: 1px solid #f1f5f9; }
.experiment__metrics { display: flex; flex-wrap: wrap; gap: 8px; }
.experiment__metric { font-size: 12px; padding: 4px 10px; background: #f0fdf4; color: #166534; border-radius: 4px; }
.experiment__right { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; }
.experiment__right h3 { margin: 0 0 12px; font-size: 13px; font-weight: 600; color: #0f172a; }
.experiment__model-card { background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 8px; padding: 14px; }
.experiment__model-name { font-size: 14px; font-weight: 600; color: #1e293b; font-family: monospace; }
.experiment__model-conf { font-size: 12px; color: #10b981; margin: 4px 0; }
</style>
