<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import ResearchIcon from '../../components/icons/ResearchIcon.vue'
import ResearchState from '../../components/research/ResearchState.vue'
import StatusBadge from '../../components/research/StatusBadge.vue'
import { experimentService } from '../../services/research/experiment.service'
import { useExperimentStore } from '../../stores/research/experiment.store'

type PageState = 'loading' | 'empty' | 'error' | null
type OperationState = 'idle' | 'loading' | 'success' | 'error'

const store = useExperimentStore()
const pageState = ref<PageState>('loading')
const generatedHypotheses = ref<Array<{ statement: string; confidence: number }>>([])
const generationState = ref<OperationState>('idle')
const saveState = ref<OperationState>('idle')
const variableRanges = ref<string[]>([])

const isReadOnly = computed(() => store.design?.status === 'running' || store.design?.status === 'completed')
const statusLabel = computed(() => {
  if (store.design?.status === 'running') return '运行中'
  if (store.design?.status === 'completed') return '已完成'
  return '设计阶段'
})
const statusTone = computed<'success' | 'info' | 'neutral'>(() =>
  store.design?.status === 'running' ? 'info' : store.design?.status === 'completed' ? 'success' : 'neutral'
)

watch(
  () => store.design,
  design => { variableRanges.value = design?.variables.map(variable => variable.range) ?? [] },
  { immediate: true }
)

async function loadDesign() {
  pageState.value = 'loading'
  try {
    await store.loadDesign()
    pageState.value = store.design ? null : 'empty'
  } catch {
    pageState.value = 'error'
  }
}

async function generateHypotheses() {
  if (!store.design || generationState.value === 'loading') return
  generationState.value = 'loading'
  try {
    generatedHypotheses.value = await experimentService.generateHypotheses(store.design.question)
    generationState.value = 'success'
  } catch {
    generationState.value = 'error'
  }
}

function markDraftChanged() {
  if (saveState.value !== 'loading') saveState.value = 'idle'
}

async function saveDesign() {
  if (!store.design || saveState.value === 'loading' || isReadOnly.value) return
  saveState.value = 'loading'
  const variables = store.design.variables.map((variable, index) => ({
    ...variable,
    range: variableRanges.value[index] ?? variable.range
  }))
  try {
    await experimentService.updateDesign({ variables })
    saveState.value = 'success'
  } catch {
    saveState.value = 'error'
  }
}

function variableType(type: 'independent' | 'dependent' | 'control') {
  return type === 'independent' ? '自变量' : type === 'dependent' ? '因变量' : '控制变量'
}

function variableTone(type: 'independent' | 'dependent' | 'control'): 'success' | 'info' | 'neutral' {
  return type === 'independent' ? 'success' : type === 'dependent' ? 'info' : 'neutral'
}

function variableLabel(name: string, unit: string) {
  return `${name}范围${unit ? `（${unit}）` : ''}`
}

onMounted(loadDesign)
</script>

<template>
  <section class="experiment" aria-labelledby="experiment-title">
    <header class="experiment__header">
      <div>
        <p class="experiment__eyebrow">实验方案工作台</p>
        <h1 id="experiment-title">实验设计</h1>
        <p v-if="store.design" data-testid="experiment-question">{{ store.design.question }}</p>
        <p v-else>构建可验证假设、变量、分组与评价指标。</p>
      </div>
      <div v-if="store.design" class="experiment__header-actions">
        <StatusBadge
          data-testid="experiment-status"
          :data-status="store.design.status"
          :status="statusTone"
          :label="statusLabel"
        />
        <button
          class="experiment__save"
          data-testid="save-experiment"
          type="button"
          :disabled="isReadOnly || saveState === 'loading'"
          :aria-busy="saveState === 'loading'"
          @click="saveDesign"
        >
          <ResearchIcon :name="saveState === 'success' ? 'check' : 'document'" :size="15" />
          {{ saveState === 'loading' ? '正在保存...' : '确认保存' }}
        </button>
      </div>
    </header>

    <ResearchState
      v-if="pageState"
      class="experiment__empty"
      data-testid="experiment-page-state"
      :state="pageState"
      :description="pageState === 'empty' ? '创建研究问题后，可在这里构建实验方案。' : undefined"
      @retry="loadDesign"
    />

    <template v-else-if="store.design">
      <div v-if="saveState === 'success'" class="experiment__saved" data-testid="experiment-save-status" role="status" aria-live="polite">
        <ResearchIcon name="check" :size="15" />实验设计已保存
      </div>
      <ResearchState
        v-else-if="saveState === 'error'"
        class="experiment__operation-state"
        data-testid="experiment-save-error"
        state="error"
        title="分析失败，请重试"
        description="实验设计未保存，当前编辑内容仍保留。"
        @retry="saveDesign"
      />

      <div class="experiment__workspace" data-testid="experiment-workspace">
        <aside class="experiment__hypotheses" aria-label="研究假设">
          <div class="experiment__panel-heading">
            <div class="experiment__panel-icon experiment__panel-icon--primary"><ResearchIcon name="experiment" :size="17" /></div>
            <div><p>科学推断</p><h2>研究假设</h2></div>
          </div>
          <div class="experiment__hypothesis-list">
            <article
              v-for="(hypothesis, index) in store.design.hypotheses"
              :key="`${hypothesis.statement}-${index}`"
              class="experiment__hypothesis"
              :data-testid="`design-hypothesis-${index}`"
            >
              <span>H{{ index + 1 }}</span>
              <p>{{ hypothesis.statement }}</p>
              <strong>置信度 {{ Math.round(hypothesis.confidence * 100) }}%</strong>
            </article>
          </div>
          <p class="experiment__column-note">假设来源于当前实验设计，不自动覆盖已确认方案。</p>
        </aside>

        <section class="experiment__variables" aria-label="实验变量">
          <div class="experiment__panel-heading">
            <div class="experiment__panel-icon experiment__panel-icon--success"><ResearchIcon name="data" :size="17" /></div>
            <div><p>参数与分组</p><h2>实验变量</h2></div>
          </div>

          <div class="experiment__variable-list" aria-label="变量编辑列表">
            <label
              v-for="(variable, index) in store.design.variables"
              :key="`${variable.name}-${index}`"
              class="experiment__variable"
              :data-variable-index="index"
            >
              <span class="experiment__variable-name">{{ variable.name }}</span>
              <StatusBadge :status="variableTone(variable.type)" :label="variableType(variable.type)" />
              <span class="experiment__input-wrap">
                <input
                  v-model="variableRanges[index]"
                  type="text"
                  :disabled="isReadOnly || saveState === 'loading'"
                  :aria-label="variableLabel(variable.name, variable.unit)"
                  @input="markDraftChanged"
                />
                <em>{{ variable.unit || '无单位' }}</em>
              </span>
            </label>
          </div>

          <section class="experiment__groups" aria-labelledby="experiment-groups-title">
            <div class="experiment__subheading">
              <h3 id="experiment-groups-title">实验分组</h3><span>{{ store.design.groups.length }} 组</span>
            </div>
            <article
              v-for="(group, index) in store.design.groups"
              :key="`${group.name}-${index}`"
              class="experiment__group"
              :data-group-index="index"
            >
              <strong>{{ group.name }}</strong>
              <p>{{ group.condition }}</p>
              <span>{{ group.purpose ?? '目的待确认' }}</span>
            </article>
          </section>

          <section class="experiment__outcomes" data-testid="experiment-outcomes" aria-labelledby="experiment-outcomes-title">
            <div class="experiment__subheading"><h3 id="experiment-outcomes-title">评价指标</h3><span>结果观测</span></div>
            <div><span v-for="metric in store.design.metrics" :key="metric">{{ metric }}</span></div>
          </section>
        </section>

        <aside class="experiment__advice" aria-label="AI 实验建议">
          <div class="experiment__panel-heading">
            <div class="experiment__panel-icon experiment__panel-icon--ai"><ResearchIcon name="sparkles" :size="17" /></div>
            <div><p>辅助推理</p><h2>AI 实验建议</h2></div>
          </div>

          <article class="experiment__model">
            <span>推荐分析模型</span>
            <strong>{{ store.design.model.name }}</strong>
            <p>模型匹配度 {{ Math.round(store.design.model.confidence * 100) }}%</p>
          </article>

          <button
            class="experiment__generate"
            data-testid="generate-hypotheses"
            type="button"
            :disabled="generationState === 'loading'"
            :aria-busy="generationState === 'loading'"
            @click="generateHypotheses"
          >
            <ResearchIcon name="sparkles" :size="15" />
            {{ generationState === 'loading' ? 'AI 正在分析...' : '生成实验建议' }}
          </button>

          <ResearchState
            v-if="generationState === 'error'"
            class="experiment__advice-state"
            state="error"
            @retry="generateHypotheses"
          />
          <div v-else-if="generatedHypotheses.length" class="experiment__suggestions" aria-live="polite">
            <article
              v-for="(hypothesis, index) in generatedHypotheses"
              :key="`${hypothesis.statement}-${index}`"
              :data-testid="`ai-suggestion-${index}`"
            >
              <span>AI 建议 {{ index + 1 }}</span>
              <p>{{ hypothesis.statement }}</p>
              <strong>置信度 {{ Math.round(hypothesis.confidence * 100) }}%</strong>
            </article>
          </div>
          <p
            v-else-if="generationState === 'success'"
            class="experiment__advice-empty"
            data-testid="ai-suggestion-empty"
            role="status"
            aria-live="polite"
          ><strong>暂无 AI 实验建议</strong><span>本次未生成可用建议</span></p>
          <p v-else class="experiment__advice-empty">建议只在用户主动生成后显示，不写回实验设计。</p>
        </aside>
      </div>
    </template>
  </section>
</template>

<style scoped>
.experiment { min-width: 0; padding: var(--research-page-gutter); color: var(--research-text-primary); }
.experiment__header { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--research-space-5); margin-bottom: var(--research-space-5); }
.experiment__eyebrow,
.experiment__header h1,
.experiment__header p,
.experiment__panel-heading p,
.experiment__panel-heading h2,
.experiment__hypothesis p,
.experiment__column-note,
.experiment__subheading h3,
.experiment__group p,
.experiment__model p,
.experiment__suggestions p,
.experiment__advice-empty { margin: 0; }
.experiment__eyebrow { color: var(--research-primary-600); font-size: var(--research-text-xs); font-weight: var(--research-font-weight-bold); letter-spacing: .08em; text-transform: uppercase; }
.experiment__header h1 { margin-top: var(--research-space-1); font-size: var(--research-text-page-title); letter-spacing: var(--research-letter-spacing-title); }
.experiment__header > div > p:last-child { max-width: 720px; margin-top: var(--research-space-2); color: var(--research-text-secondary); font-size: var(--research-text-body); line-height: var(--research-line-height-body); }
.experiment__header-actions { display: flex; align-items: center; gap: var(--research-space-3); }
.experiment__save,
.experiment__generate { display: inline-flex; align-items: center; justify-content: center; gap: var(--research-space-2); min-height: 38px; padding: var(--research-space-2) var(--research-space-4); border-radius: var(--research-radius-button); font: inherit; font-size: var(--research-text-sm); font-weight: var(--research-font-weight-semibold); cursor: pointer; }
.experiment__save { border: 1px solid var(--research-primary-500); background: var(--research-primary-500); color: var(--research-text-inverse); }
.experiment__generate { width: 100%; margin-top: var(--research-space-4); border: 1px solid var(--research-ai-500); background: var(--research-ai-500); color: var(--research-text-inverse); }
.experiment__save:focus-visible { outline: none; box-shadow: var(--research-shadow-focus-primary); }
.experiment__generate:focus-visible { outline: none; box-shadow: var(--research-shadow-focus-ai); }
.experiment__save:disabled,
.experiment__generate:disabled { border-color: var(--research-border-strong); background: var(--research-bg-hover); color: var(--research-text-secondary); cursor: not-allowed; }
.experiment__saved { display: flex; align-items: center; gap: var(--research-space-2); margin-bottom: var(--research-space-4); padding: var(--research-space-3) var(--research-space-4); border: 1px solid var(--research-success-100); border-radius: var(--research-radius-card); background: var(--research-success-50); color: var(--research-success-700); font-size: var(--research-text-sm); font-weight: var(--research-font-weight-semibold); }
.experiment__operation-state { min-height: 138px; margin-bottom: var(--research-space-4); }
.experiment__workspace { display: grid; min-width: 0; grid-template-columns: minmax(0,var(--research-rail-standard)) minmax(0,1fr) minmax(0,var(--research-rail-standard)); gap: var(--research-grid-gap); align-items: start; }
.experiment__hypotheses,
.experiment__variables,
.experiment__advice { min-width: 0; overflow: hidden; padding: var(--research-space-5); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-panel); background: var(--research-bg-card); box-shadow: var(--research-shadow-soft); }
.experiment__panel-heading { display: flex; align-items: center; gap: var(--research-space-3); margin-bottom: var(--research-space-4); }
.experiment__panel-icon { display: grid; width: 36px; height: 36px; place-items: center; border-radius: var(--research-radius-button); }
.experiment__panel-icon--primary { background: var(--research-primary-50); color: var(--research-primary-600); }
.experiment__panel-icon--success { background: var(--research-success-50); color: var(--research-success-700); }
.experiment__panel-icon--ai { background: var(--research-ai-50); color: var(--research-ai-700); }
.experiment__panel-heading p { color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.experiment__panel-heading h2 { margin-top: var(--research-space-1); font-size: var(--research-text-card-title); }
.experiment__hypothesis-list { display: grid; gap: var(--research-space-3); }
.experiment__hypothesis { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: var(--research-space-2) var(--research-space-3); padding: var(--research-space-4); border: 1px solid var(--research-primary-100); border-radius: var(--research-radius-card); background: var(--research-primary-50); }
.experiment__hypothesis > span { grid-row: 1 / 3; color: var(--research-primary-700); font-size: var(--research-text-sm); font-weight: var(--research-font-weight-bold); }
.experiment__hypothesis p { color: var(--research-text-primary); font-size: var(--research-text-sm); line-height: var(--research-line-height-body); }
.experiment__hypothesis strong { color: var(--research-success-700); font-size: var(--research-text-xs); font-weight: var(--research-font-weight-semibold); }
.experiment__column-note { margin-top: var(--research-space-4); color: var(--research-text-secondary); font-size: var(--research-text-xs); line-height: var(--research-line-height-body); }
.experiment__variable-list { display: grid; gap: var(--research-space-2); }
.experiment__variable { display: grid; grid-template-columns: minmax(110px, .8fr) auto minmax(160px, 1fr); align-items: center; gap: var(--research-space-3); padding: var(--research-space-3); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-card); background: var(--research-bg-panel); }
.experiment__variable-name { font-size: var(--research-text-sm); font-weight: var(--research-font-weight-semibold); }
.experiment__input-wrap { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; overflow: hidden; border: 1px solid var(--research-border-strong); border-radius: var(--research-radius-input); background: var(--research-bg-card); }
.experiment__input-wrap:focus-within { border-color: var(--research-primary-500); box-shadow: var(--research-shadow-focus-primary); }
.experiment__input-wrap input { width: 100%; min-width: 0; height: 36px; padding-inline: var(--research-space-3); border: 0; outline: 0; background: transparent; color: var(--research-text-primary); font: inherit; font-size: var(--research-text-sm); }
.experiment__input-wrap input:disabled { background: var(--research-bg-hover); color: var(--research-text-secondary); cursor: not-allowed; }
.experiment__input-wrap em { padding-inline: var(--research-space-3); color: var(--research-text-secondary); font-size: var(--research-text-xs); font-style: normal; }
.experiment__groups,
.experiment__outcomes { margin-top: var(--research-space-5); padding-top: var(--research-space-5); border-top: 1px solid var(--research-divider); }
.experiment__subheading { display: flex; align-items: center; justify-content: space-between; gap: var(--research-space-3); margin-bottom: var(--research-space-3); }
.experiment__subheading h3 { font-size: var(--research-text-card-title); }
.experiment__subheading > span { color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.experiment__group { display: grid; grid-template-columns: minmax(72px, .45fr) minmax(0, 1fr) minmax(84px, .55fr); gap: var(--research-space-3); padding: var(--research-space-3) 0; border-bottom: 1px solid var(--research-divider); font-size: var(--research-text-sm); }
.experiment__group:last-child { border-bottom: 0; }
.experiment__group p { color: var(--research-text-secondary); }
.experiment__group span { color: var(--research-text-secondary); }
.experiment__outcomes > div:last-child { display: flex; flex-wrap: wrap; gap: var(--research-space-2); }
.experiment__outcomes > div:last-child span { padding: var(--research-space-1) var(--research-space-3); border-radius: var(--research-radius-pill); background: var(--research-success-50); color: var(--research-success-700); font-size: var(--research-text-xs); }
.experiment__model { padding: var(--research-space-4); border: 1px solid var(--research-ai-100); border-radius: var(--research-radius-card); background: var(--research-ai-50); }
.experiment__model > span { display: block; color: var(--research-ai-700); font-size: var(--research-text-xs); }
.experiment__model strong { display: block; margin-top: var(--research-space-2); font-size: var(--research-text-card-title); }
.experiment__model p { margin-top: var(--research-space-2); color: var(--research-success-700); font-size: var(--research-text-xs); font-weight: var(--research-font-weight-semibold); }
.experiment__suggestions { display: grid; gap: var(--research-space-3); margin-top: var(--research-space-4); }
.experiment__suggestions article { padding: var(--research-space-4); border: 1px solid var(--research-ai-100); border-radius: var(--research-radius-card); background: var(--research-ai-50); }
.experiment__suggestions span { color: var(--research-ai-700); font-size: var(--research-text-xs); font-weight: var(--research-font-weight-semibold); }
.experiment__suggestions p { margin-top: var(--research-space-2); font-size: var(--research-text-sm); line-height: var(--research-line-height-body); }
.experiment__suggestions strong { display: block; margin-top: var(--research-space-2); color: var(--research-success-700); font-size: var(--research-text-xs); }
.experiment__advice-empty { display: grid; gap: var(--research-space-1); margin-top: var(--research-space-4); color: var(--research-text-secondary); font-size: var(--research-text-xs); line-height: var(--research-line-height-body); }
.experiment__advice-empty strong { color: var(--research-text-primary); font-size: var(--research-text-sm); }
.experiment__advice-state { min-height: 190px; margin-top: var(--research-space-4); padding: var(--research-space-4); }

@media (max-width: 1480px) {
  .experiment__workspace { grid-template-columns: minmax(0,var(--research-rail-compact)) minmax(0,1fr) minmax(0,var(--research-rail-standard)); gap: var(--research-space-3); }
  .experiment__hypotheses,
  .experiment__variables,
  .experiment__advice { padding: var(--research-space-4); }
  .experiment__variable { grid-template-columns: minmax(92px, .65fr) auto minmax(142px, 1fr); gap: var(--research-space-2); }
}

@media (min-width: 1720px) {
  .experiment__workspace { grid-template-columns: minmax(0,var(--research-rail-standard)) minmax(0,1fr) minmax(0,var(--research-rail-wide)); }
}
</style>
