<script setup lang="ts">
/**
 * FirstLaunchWizard — Phase 8-M1-A
 * 首次启动向导 (5 步): 欢迎 / 数据目录 / 研究模式 / Demo 选项 / 完成.
 *
 * Props-only 组件, 禁止依赖 service / store. 所有变更通过 emit 抛回上层.
 */
import { computed, ref } from 'vue'
import ResearchIcon from '../icons/ResearchIcon.vue'

export type ResearchMode = 'live' | 'demo'
export type WizardStepId = 'welcome' | 'directory' | 'mode' | 'demo' | 'finish'

export interface WizardState {
  step: WizardStepId
  dataDirectory: string
  mode: ResearchMode
  enableDemo: boolean
  completed: boolean
}

const props = withDefaults(defineProps<{
  initialDirectory?: string
  defaultMode?: ResearchMode
}>(), {
  initialDirectory: '',
  defaultMode: 'live'
})

const emit = defineEmits<{
  complete: [state: WizardState]
  'change-directory': [next: string]
  'select-mode': [mode: ResearchMode]
  cancel: []
}>()

const stepIndex = ref(0)
const dataDirectory = ref(props.initialDirectory)
const mode = ref<ResearchMode>(props.defaultMode)
const enableDemo = ref(false)

const STEPS: ReadonlyArray<{ id: WizardStepId; title: string; description: string }> = [
  { id: 'welcome', title: '欢迎使用 Scientific Research OS', description: '基于 Electron + Vue 3 的科研桌面工作台, 对接 MicroBubble Agent 后端 API.' },
  { id: 'directory', title: '数据目录', description: '所有项目数据 / 日志 / 缓存都存放在本地, 不上传云端.' },
  { id: 'mode', title: '研究模式', description: 'Live 模式连接真实后端, Demo 模式使用 fixture 数据.' },
  { id: 'demo', title: 'Demo 选项', description: '是否在 Demo 模式下额外加载示例项目.' },
  { id: 'finish', title: '准备就绪', description: '配置已保存, 可以进入科研驾驶舱.' }
]

const currentStep = computed(() => STEPS[stepIndex.value])
const isFirst = computed(() => stepIndex.value === 0)
const isLast = computed(() => stepIndex.value === STEPS.length - 1)

function next(): void {
  if (isLast.value) {
    emit('complete', {
      step: 'finish',
      dataDirectory: dataDirectory.value,
      mode: mode.value,
      enableDemo: enableDemo.value,
      completed: true
    })
    return
  }
  stepIndex.value = Math.min(STEPS.length - 1, stepIndex.value + 1)
}

function prev(): void {
  stepIndex.value = Math.max(0, stepIndex.value - 1)
}

function onDirectoryInput(event: Event): void {
  const value = (event.target as HTMLInputElement).value
  dataDirectory.value = value
  emit('change-directory', value)
}

function selectMode(next: ResearchMode): void {
  mode.value = next
  emit('select-mode', next)
}

function toggleDemo(): void {
  enableDemo.value = !enableDemo.value
}
</script>

<template>
  <section class="wizard" role="dialog" aria-modal="true" aria-label="首次启动向导" data-testid="first-launch-wizard">
    <header class="wizard__head">
      <ol class="wizard__steps" aria-label="向导进度">
        <li
          v-for="(step, idx) in STEPS"
          :key="step.id"
          class="wizard__step-marker"
          :class="{ 'is-active': idx === stepIndex, 'is-done': idx < stepIndex }"
          :aria-current="idx === stepIndex ? 'step' : undefined"
        >
          <span class="wizard__step-index">{{ idx + 1 }}</span>
          <span class="wizard__step-title">{{ step.title }}</span>
        </li>
      </ol>
    </header>

    <div class="wizard__body">
      <h2 class="wizard__title">{{ currentStep.title }}</h2>
      <p class="wizard__description">{{ currentStep.description }}</p>

      <div v-if="currentStep.id === 'welcome'" class="wizard__panel" data-testid="wizard-step-welcome">
        <ResearchIcon name="sparkles" :size="48" />
        <p>本向导仅用于初始化本地环境, 不会向服务器发送任何数据。</p>
      </div>

      <div v-else-if="currentStep.id === 'directory'" class="wizard__panel" data-testid="wizard-step-directory">
        <label class="wizard__label">
          <span>本地数据目录</span>
          <input
            type="text"
            class="wizard__input"
            :value="dataDirectory"
            placeholder="例如 ~/.local/share/ScientificResearchOS"
            aria-label="本地数据目录"
            data-testid="wizard-directory-input"
            @input="onDirectoryInput"
          >
        </label>
        <p class="wizard__hint">应用根目录 + userData 模式. 首次启动会自动创建.</p>
      </div>

      <div v-else-if="currentStep.id === 'mode'" class="wizard__panel" data-testid="wizard-step-mode">
        <div class="wizard__radios">
          <button
            type="button"
            class="wizard__radio"
            :class="{ 'is-active': mode === 'live' }"
            data-testid="wizard-mode-live"
            :aria-pressed="mode === 'live'"
            @click="selectMode('live')"
          >
            <strong>Live 模式</strong>
            <span>连接 MicroBubble Agent 后端, 真实实验数据</span>
          </button>
          <button
            type="button"
            class="wizard__radio"
            :class="{ 'is-active': mode === 'demo' }"
            data-testid="wizard-mode-demo"
            :aria-pressed="mode === 'demo'"
            @click="selectMode('demo')"
          >
            <strong>Demo 模式</strong>
            <span>使用内置 O₃-MNBs fixture, 不影响真实项目</span>
          </button>
        </div>
      </div>

      <div v-else-if="currentStep.id === 'demo'" class="wizard__panel" data-testid="wizard-step-demo">
        <label class="wizard__toggle">
          <input
            type="checkbox"
            :checked="enableDemo"
            aria-label="启用演示示例"
            data-testid="wizard-demo-toggle"
            @change="toggleDemo"
          >
          <span>启用 O₃-MNBs 演示示例项目 (含 6 阶段完整流程)</span>
        </label>
        <p class="wizard__hint">Demo 数据完全隔离, 不会写入真实项目.</p>
      </div>

      <div v-else-if="currentStep.id === 'finish'" class="wizard__panel" data-testid="wizard-step-finish">
        <ResearchIcon name="check" :size="48" />
        <p>配置已保存. 点击下一步进入科研驾驶舱.</p>
      </div>
    </div>

    <footer class="wizard__actions">
      <button
        type="button"
        class="wizard__button wizard__button--secondary"
        :disabled="isFirst"
        data-testid="wizard-prev"
        @click="prev"
      >
        上一步
      </button>
      <button
        type="button"
        class="wizard__button wizard__button--primary"
        data-testid="wizard-next"
        @click="next"
      >
        {{ isLast ? '完成' : '下一步' }}
      </button>
      <button
        type="button"
        class="wizard__button wizard__button--ghost"
        data-testid="wizard-cancel"
        @click="emit('cancel')"
      >
        跳过
      </button>
    </footer>
  </section>
</template>

<style scoped>
.wizard {
  display: grid;
  gap: var(--research-space-5);
  max-width: 720px;
  margin: var(--research-space-8) auto;
  padding: var(--research-space-6);
  border: 1px solid var(--research-border-subtle);
  border-radius: var(--research-radius-panel);
  background: var(--research-bg-card);
  box-shadow: var(--research-shadow-modal);
}
.wizard__head { border-block-end: 1px solid var(--research-divider); padding-block-end: var(--research-space-4); }
.wizard__steps { display: flex; flex-wrap: wrap; gap: var(--research-space-3); padding: 0; margin: 0; list-style: none; }
.wizard__step-marker { display: grid; grid-template-columns: 28px 1fr; gap: var(--research-space-2); align-items: center; color: var(--research-text-muted); font-size: var(--research-text-xs); }
.wizard__step-marker.is-active { color: var(--research-primary-700); font-weight: var(--research-font-weight-semibold); }
.wizard__step-marker.is-done { color: var(--research-success-700); }
.wizard__step-index { display: grid; place-items: center; width: 28px; height: 28px; border-radius: var(--research-radius-pill); background: var(--research-bg-panel); }
.wizard__step-marker.is-active .wizard__step-index { background: var(--research-primary-500); color: var(--research-text-inverse); }
.wizard__step-marker.is-done .wizard__step-index { background: var(--research-success-500); color: var(--research-text-inverse); }
.wizard__step-title { white-space: nowrap; }
.wizard__title { margin: 0; font-size: var(--research-text-section-title); font-weight: var(--research-font-weight-bold); color: var(--research-text-primary); }
.wizard__description { margin: 0; color: var(--research-text-secondary); font-size: var(--research-text-body); }
.wizard__panel { display: grid; gap: var(--research-space-3); padding: var(--research-space-4); border-radius: var(--research-radius-card); background: var(--research-bg-panel); color: var(--research-text-primary); }
.wizard__label { display: grid; gap: var(--research-space-2); }
.wizard__label > span { font-size: var(--research-text-sm); color: var(--research-text-secondary); }
.wizard__input { width: 100%; padding: var(--research-space-2) var(--research-space-3); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-input); background: var(--research-bg-card); color: var(--research-text-primary); font: inherit; }
.wizard__hint { margin: 0; font-size: var(--research-text-xs); color: var(--research-text-muted); }
.wizard__radios { display: grid; grid-template-columns: 1fr 1fr; gap: var(--research-space-3); }
.wizard__radio { display: grid; gap: var(--research-space-1); padding: var(--research-space-3); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-card); background: var(--research-bg-card); color: var(--research-text-primary); text-align: start; cursor: pointer; transition: border-color var(--research-duration-fast) var(--research-ease-standard), box-shadow var(--research-duration-fast) var(--research-ease-standard); }
.wizard__radio:hover { border-color: var(--research-primary-200); }
.wizard__radio:focus-visible { outline: none; box-shadow: var(--research-shadow-focus-primary); }
.wizard__radio.is-active { border-color: var(--research-primary-500); box-shadow: var(--research-shadow-focus-primary); }
.wizard__radio strong { font-size: var(--research-text-card-title); }
.wizard__radio span:last-child { color: var(--research-text-secondary); font-size: var(--research-text-sm); }
.wizard__toggle { display: grid; grid-template-columns: 24px 1fr; gap: var(--research-space-3); align-items: center; cursor: pointer; }
.wizard__actions { display: flex; gap: var(--research-space-2); justify-content: flex-end; flex-wrap: wrap; }
.wizard__button { padding: var(--research-space-2) var(--research-space-4); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-button); background: var(--research-bg-card); color: var(--research-text-primary); font: inherit; cursor: pointer; transition: background var(--research-duration-fast) var(--research-ease-standard); }
.wizard__button:hover { background: var(--research-bg-hover); }
.wizard__button:focus-visible { outline: none; box-shadow: var(--research-shadow-focus-primary); }
.wizard__button:disabled { opacity: 0.5; cursor: not-allowed; }
.wizard__button--primary { background: var(--research-primary-500); border-color: var(--research-primary-600); color: var(--research-text-inverse); }
.wizard__button--primary:hover { background: var(--research-primary-600); }
.wizard__button--ghost { background: transparent; border-color: transparent; color: var(--research-text-secondary); }
@media (max-width: 1480px) {
  .wizard__radios { grid-template-columns: 1fr; }
}
@media (prefers-reduced-motion: reduce) {
  .wizard__radio { transition: none; }
  .wizard__button { transition: none; }
}
</style>
