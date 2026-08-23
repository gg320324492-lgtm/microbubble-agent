<script setup lang="ts">
/**
 * 智能体中心 — 升级版：AI任务输入 + 执行时间线 + 结果展示。
 */
import { ref, onMounted } from 'vue'
import { useAgentStore } from '../../stores/research/agent.store'
import { useWorkflowStore, type WorkflowTask } from '../../stores/research/workflow.store'
import AgentCard from '../../components/research/AgentCard.vue'
import StatusBadge from '../../components/research/StatusBadge.vue'

const agentStore = useAgentStore()
const workflowStore = useWorkflowStore()
onMounted(() => agentStore.loadSessions())

const researchInput = ref('')
const isRunning = ref(false)

const agents = [
  { icon: '📚', name: '文献智能体', status: 'running' as const, task: '正在分析文献' },
  { icon: '🧪', name: '实验智能体', status: 'idle' as const },
  { icon: '📊', name: '数据智能体', status: 'running' as const, task: '拟合动力学模型' },
  { icon: '✍️', name: '论文智能体', status: 'idle' as const },
  { icon: '🔍', name: '审稿智能体', status: 'idle' as const },
]

const timelineSteps = [
  { label: '理解研究问题', status: 'completed' as const, icon: '✓' },
  { label: '制定研究计划', status: 'completed' as const, icon: '✓' },
  { label: '检索相关文献', status: 'completed' as const, icon: '✓' },
  { label: '分析实验变量', status: 'running' as const, icon: '●' },
  { label: '生成科研建议', status: 'pending' as const, icon: '○' },
]

const resultCards = [
  { title: '研究问题', content: '如何优化臭氧微纳米气泡强化四环素降解效率？', icon: '❓', status: 'completed' as const },
  { title: '引用文献', content: '筛选 12 篇核心文献，涵盖 O₃-MNBs、TC、动力学、机理', icon: '📄', status: 'completed' as const },
  { title: '工具调用', content: '文献检索 → 动力学拟合 → 机理分析', icon: '⚙️', status: 'completed' as const },
  { title: '模型分析', content: '一级动力学 R²=0.9887，k=0.0243 min⁻¹', icon: '📊', status: 'completed' as const },
  { title: '最终结论', content: 'O₃-MNBs 对 TC 去除率达 98.6%，·OH 为主导活性物种', icon: '✅', status: 'completed' as const },
]

async function runResearch() {
  if (!researchInput.value.trim() || isRunning.value) return
  isRunning.value = true
  try { await agentStore.runResearch(researchInput.value.trim()) }
  finally { isRunning.value = false }
}
</script>

<template>
  <div class="agent-center">
    <div class="agent-center__header">
      <h1 class="agent-center__title">智能体中心</h1>
      <StatusBadge status="info" label="5 个智能体" />
    </div>

    <!-- AI 任务输入 -->
    <div class="agent-center__input-section">
      <h3>AI 任务输入</h3>
      <div class="agent-center__input-row">
        <input v-model="researchInput" type="text" placeholder="请输入您的科研问题，例如：如何优化臭氧微纳米气泡强化四环素降解实验？"
               @keyup.enter="runResearch" />
        <button class="agent-center__run-btn" @click="runResearch" :disabled="isRunning">
          {{ isRunning ? '执行中...' : '开始研究' }}
        </button>
      </div>
    </div>

    <!-- 智能体状态 -->
    <div class="agent-center__agents">
      <h3>智能体架构</h3>
      <div class="agent-center__supervisor">🧠 科研主管智能体</div>
      <div class="agent-center__agent-row">
        <AgentCard v-for="a in agents" :key="a.name" v-bind="a" />
      </div>
    </div>

    <!-- 执行时间线 -->
    <div class="agent-center__timeline-section">
      <h3>执行时间线</h3>
      <div class="agent-center__timeline">
        <div v-for="(step, i) in timelineSteps" :key="i" class="agent-center__step" :class="`agent-center__step--${step.status}`">
          <span class="agent-center__step-icon">{{ step.icon }}</span>
          <span class="agent-center__step-label">{{ step.label }}</span>
          <StatusBadge :status="step.status === 'completed' ? 'success' : step.status === 'running' ? 'info' : 'neutral'"
                       :label="step.status === 'completed' ? '完成' : step.status === 'running' ? '进行中' : '待执行'" />
        </div>
      </div>
    </div>

    <!-- 结果区域 -->
    <div class="agent-center__results">
      <h3>研究结果</h3>
      <div class="agent-center__result-cards">
        <div class="agent-center__result-card" v-for="r in resultCards" :key="r.title">
          <div class="agent-center__result-header">
            <span>{{ r.icon }}</span>
            <span class="agent-center__result-title">{{ r.title }}</span>
            <StatusBadge status="success" label="完成" />
          </div>
          <div class="agent-center__result-content">{{ r.content }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.agent-center { padding: 24px 28px; max-width: 1200px; }
.agent-center__header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
.agent-center__title { margin: 0; font-size: 20px; font-weight: 700; color: #0f172a; }
.agent-center__input-section { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 18px; margin-bottom: 16px; }
.agent-center__input-section h3 { margin: 0 0 10px; font-size: 14px; font-weight: 600; }
.agent-center__input-row { display: flex; gap: 10px; }
.agent-center__input-row input { flex: 1; border: 1px solid #d1d5db; border-radius: 8px; padding: 10px 14px; font-size: 13px; outline: none; }
.agent-center__input-row input:focus { border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,.15); }
.agent-center__run-btn { background: #2563eb; color: #fff; border: none; border-radius: 8px; padding: 10px 20px; font-size: 13px; font-weight: 500; cursor: pointer; white-space: nowrap; }
.agent-center__run-btn:hover { background: #1d4ed8; }
.agent-center__run-btn:disabled { opacity: .5; cursor: not-allowed; }
.agent-center__agents { margin-bottom: 16px; }
.agent-center__agents h3, .agent-center__timeline-section h3, .agent-center__results h3 { margin: 0 0 12px; font-size: 14px; font-weight: 600; }
.agent-center__supervisor { display: inline-block; background: #0f172a; color: #fff; padding: 10px 20px; border-radius: 10px; font-weight: 600; font-size: 14px; margin-bottom: 12px; text-align: center; }
.agent-center__agent-row { display: flex; justify-content: center; gap: 12px; flex-wrap: wrap; }
.agent-center__timeline-section { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 18px; margin-bottom: 16px; }
.agent-center__timeline { display: flex; flex-direction: column; gap: 6px; }
.agent-center__step { display: flex; align-items: center; gap: 10px; padding: 6px 10px; border-radius: 6px; font-size: 13px; }
.agent-center__step--completed { background: #f0fdf4; }
.agent-center__step--running { background: #eff6ff; }
.agent-center__step--pending { background: #f8fafc; }
.agent-center__step-icon { font-size: 14px; width: 20px; text-align: center; }
.agent-center__step--completed .agent-center__step-icon { color: #10b981; }
.agent-center__step--running .agent-center__step-icon { color: #3b82f6; }
.agent-center__step--pending .agent-center__step-icon { color: #94a3b8; }
.agent-center__step-label { flex: 1; color: #1e293b; }
.agent-center__results { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 18px; }
.agent-center__result-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
.agent-center__result-card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 14px; }
.agent-center__result-header { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; font-size: 13px; font-weight: 600; }
.agent-center__result-title { flex: 1; }
.agent-center__result-content { font-size: 12px; color: #64748b; line-height: 1.5; }
</style>
