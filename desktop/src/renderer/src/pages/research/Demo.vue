<script setup lang="ts">
/**
 * Demo Page — Phase 8-M0-G 演示场景主入口.
 *
 * 启用演示模式 + 展示完整科研闭环工作流 (7 阶段导航):
 *   1. 项目总览 (本页 Workspace)
 *   2. 文献研究 (Literature)
 *   3. 实验设计 (Experiment)
 *   4. 知识图谱 (Knowledge Graph)
 *   5. 数据分析 (Data Analysis)
 *   6. 论文撰写 (Manuscript)
 *   7. AI 助手 (Assistant)
 */
import { computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import ResearchIcon from '../../components/icons/ResearchIcon.vue'
import type { ResearchIconName } from '../../components/icons/research-icons'
import ResearchPanel from '../../components/research/ResearchPanel.vue'
import ResearchState from '../../components/research/ResearchState.vue'
import DemoWorkspace from '../../components/demo/DemoWorkspace.vue'
import { useDemoMode } from '../../composables/use-demo-mode'
import { DEMO_PROJECT } from '../../services/demo/demo-project'

const router = useRouter()
const { isDemoMode, enableDemoMode, disableDemoMode } = useDemoMode()

interface WorkflowStep {
  id: string
  label: string
  description: string
  icon: ResearchIconName
  routeName: string
}

const STEPS: ReadonlyArray<WorkflowStep> = [
  { id: 'demo-literature', label: '文献流程', description: '论文导入 → 实体抽取 → 证据链', icon: 'literature', routeName: 'research-literature' },
  { id: 'demo-experiment', label: '实验流程', description: '变量设计 → 实验组 → 设备状态', icon: 'experiment', routeName: 'research-experiment' },
  { id: 'demo-graph', label: '知识图谱', description: '实体关系 → 图谱可视化', icon: 'graph', routeName: 'research-knowledge-graph' },
  { id: 'demo-data', label: '数据流程', description: 'CSV → 统计 → 模型 → 图表', icon: 'data', routeName: 'research-data-analysis' },
  { id: 'demo-manuscript', label: '论文流程', description: '章节 → 引用 → Reviewer 意见', icon: 'manuscript', routeName: 'research-manuscript' },
  { id: 'demo-assistant', label: 'AI 助手', description: '对话式科研查询', icon: 'assistant', routeName: 'research-assistant' }
]

const stepCount = computed(() => STEPS.length)
const projectName = computed(() => DEMO_PROJECT.name)

function goToStep(step: WorkflowStep): void {
  void router.push({ name: step.routeName })
}

onMounted(() => {
  enableDemoMode()
})

// [类 20.201] 2026-08-28: 离开 Demo 页时自动 disable, 防止 demo 状态泄漏到其他页.
//   之前 demo 模式是 session singleton, 用户一旦进过 demo 页就一直 demo 数据, banner 永远显示.
onUnmounted(() => {
  disableDemoMode()
})
</script>

<template>
  <main class="demo" data-research-theme="research" aria-label="演示场景">
    <ResearchState
      v-if="!isDemoMode"
      state="loading"
      title="正在启用演示模式"
      description="为现有 service 注入演示专用 adapter"
    />

    <template v-else>
      <header class="demo__header">
        <span class="demo__badge" data-testid="demo-mode-badge">
          <ResearchIcon name="sparkles" :size="14" />
          <span>演示模式 · {{ projectName }}</span>
        </span>
        <h1 class="demo__title">科研闭环 Demo · O₃-MNBs 强化四环素降解</h1>
        <p class="demo__subtitle">覆盖文献 → 实验 → 图谱 → 数据 → 论文 → AI 助手 6 个阶段, 全部使用演示专用 fixture 数据, 不污染真实 Store。</p>
      </header>

      <DemoWorkspace />

      <ResearchPanel title="演示流程" subtitle="7 阶段完整闭环导航">
        <ol class="demo__steps" role="list" data-testid="demo-workflow-steps">
          <li
            v-for="(step, idx) in STEPS"
            :key="step.id"
            class="demo__step"
            :data-step-id="step.id"
            @click="goToStep(step)"
            @keydown.enter.prevent="goToStep(step)"
          >
            <button type="button" class="demo__step-button" :aria-label="`跳转到 ${step.label}`">
              <span class="demo__step-index">{{ idx + 1 }}</span>
              <span class="demo__step-copy">
                <strong>{{ step.label }}</strong>
                <span>{{ step.description }}</span>
              </span>
              <ResearchIcon :name="step.icon" :size="20" />
            </button>
          </li>
        </ol>
        <p class="demo__summary">演示流程共 {{ stepCount }} 步, 每步均跳转至对应真实模块并加载演示数据。</p>
      </ResearchPanel>
    </template>
  </main>
</template>

<style scoped>
.demo { display: grid; gap: var(--research-space-5); min-width: 0; padding: var(--research-page-gutter); max-width: var(--research-content-max-width); margin-inline: auto; overflow-x: clip; }
.demo__header { display: grid; gap: var(--research-space-2); padding: var(--research-space-5); border: 1px solid var(--research-ai-100); border-radius: var(--research-radius-panel); background: linear-gradient(135deg, var(--research-ai-50) 0%, var(--research-bg-card) 60%); }
.demo__badge { display: inline-flex; align-items: center; gap: var(--research-space-1); align-self: start; padding: 2px var(--research-space-2); border-radius: var(--research-radius-pill); background: var(--research-ai-500); color: var(--research-text-inverse); font-size: var(--research-text-xs); font-weight: var(--research-font-weight-semibold); }
.demo__title { margin: 0; color: var(--research-text-primary); font-size: var(--research-text-page-title); font-weight: var(--research-font-weight-bold); line-height: var(--research-line-height-tight); }
.demo__subtitle { margin: 0; color: var(--research-text-secondary); font-size: var(--research-text-body); line-height: var(--research-line-height-body); }

.demo__steps { list-style: none; padding: 0; margin: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 240px), 1fr)); gap: var(--research-space-3); }
.demo__step { display: contents; }
.demo__step-button { display: grid; grid-template-columns: 32px 1fr auto; gap: var(--research-space-3); align-items: center; width: 100%; padding: var(--research-space-3) var(--research-space-4); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-card); background: var(--research-bg-card); color: var(--research-text-primary); font: inherit; cursor: pointer; text-align: start; transition: border-color var(--research-duration-fast) var(--research-ease-standard), box-shadow var(--research-duration-fast) var(--research-ease-standard), transform var(--research-duration-fast) var(--research-ease-standard); }
.demo__step-button:hover { border-color: var(--research-primary-200); box-shadow: var(--research-shadow-soft); transform: translateY(-1px); }
.demo__step-button:focus-visible { outline: none; box-shadow: var(--research-shadow-focus-primary); }
.demo__step-index { display: grid; place-items: center; width: 32px; height: 32px; border-radius: var(--research-radius-pill); background: var(--research-primary-50); color: var(--research-primary-700); font-family: var(--research-font-scientific); font-weight: var(--research-font-weight-bold); }
.demo__step-copy { display: grid; gap: 2px; min-width: 0; }
.demo__step-copy strong { color: var(--research-text-primary); font-size: var(--research-text-card-title); font-weight: var(--research-font-weight-semibold); }
.demo__step-copy span { color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.demo__summary { margin: var(--research-space-3) 0 0; color: var(--research-text-muted); font-size: var(--research-text-xs); }
@media (prefers-reduced-motion: reduce) { .demo__step-button { transition: none; transform: none; } }
</style>
