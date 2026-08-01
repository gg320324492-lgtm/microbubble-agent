<template>
  <div
    class="pro-entries"
    :class="`mode-${mode}`"
    role="toolbar"
    :aria-label="ariaLabel"
    data-testid="pro-entries"
  >
    <button
      v-if="showGraph"
      type="button"
      class="entry-btn graph-btn"
      :aria-label="graphLabel"
      :title="graphLabel"
      @click.stop="onClick('graph')"
      data-testid="pro-graph"
    >
      <span class="entry-icon" aria-hidden="true">🕸️</span>
      <span v-if="mode === 'mobile'" class="entry-text">{{ graphLabel }}</span>
    </button>

    <button
      v-if="showFormula"
      type="button"
      class="entry-btn formula-btn"
      :aria-label="formulaLabel"
      :title="formulaLabel"
      @click.stop="onClick('formula')"
      data-testid="pro-formula"
    >
      <span class="entry-icon" aria-hidden="true">📐</span>
      <span v-if="mode === 'mobile'" class="entry-text">{{ formulaLabel }}</span>
    </button>

    <button
      v-if="showHypothesis"
      type="button"
      class="entry-btn hypothesis-btn"
      :aria-label="hypothesisLabel"
      :title="hypothesisLabel"
      @click.stop="onClick('hypothesis')"
      data-testid="pro-hypothesis"
    >
      <span class="entry-icon" aria-hidden="true">💡</span>
      <span v-if="mode === 'mobile'" class="entry-text">{{ hypothesisLabel }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
/**
 * ProEntries.vue — 知识图谱 / 公式 / 假设入口 (W100 +24)
 *
 * 设计要点:
 * - 复用 ChatMessageActions / FeedbackButtons 风格 (toolbar + tag button)
 * - 智能显示逻辑:
 *   - 🕸️ 知识图谱: 有 entity/keyword hint 或有 explore_knowledge_graph tool 时显示
 *   - 📐 公式: msg.content 含 LaTeX (`$...$` / `$$...$$`) 或调用 list_formulas 时显示
 *   - 💡 假设: 调用 list_hypotheses tool 时显示
 * - 通用 fallback: 3 个按钮都显示 (无任何信号时)
 * - 仅在 assistant 完成态 (state='idle' && content) 时父组件挂载
 *
 * 派工前提错配 #21 (类 20.21, 实战新增):
 * - 派工 brief 写 `/formulas` `/hypotheses` 独立路由 → 实际不存在
 *   → 实际入口是 `/knowledge?tab=formulas` `/knowledge?tab=hypotheses` (W86 mini-3 决策)
 *   → KnowledgeGraphView 路由 `/knowledge/graph` 保留作 fallback
 * - 派工 brief 写 `generate_hypothesis` 工具 → 实际工具名是 `list_hypotheses`
 *   → 类比 `list_formulas` / `explore_knowledge_graph`
 *   → 实施时按真实工具名判断, 不虚构
 *
 * a11y:
 * - role="toolbar" + aria-label 标识按钮组
 * - 单按钮 aria-label/title 描述
 * - 键盘 Tab + Enter (button 原生)
 * - focus-visible 2px outline
 */

import { computed } from 'vue'

export type EntryMode = 'desktop' | 'mobile'
export type EntryKind = 'graph' | 'formula' | 'hypothesis'

const props = withDefaults(
  defineProps<{
    /** 模式: desktop (hover 显示) / mobile (始终显示) */
    mode?: EntryMode
    /** 当前消息 intent (含 category / confidence / keywords) */
    intent?: { category?: string; confidence?: number; keywords?: string[] } | null
    /** 消息内容 (用于检测 LaTeX) */
    content?: string
    /** 工具调用 trace (用于检测 list_formulas / list_hypotheses / explore_knowledge_graph) */
    toolTrace?: Array<{ name?: string; toolName?: string; type?: string }>
    /** 是否强制显示所有按钮 (覆盖智能判断) */
    forceAll?: boolean
  }>(),
  { mode: 'desktop', intent: null, content: '', toolTrace: () => [], forceAll: false },
)

const emit = defineEmits<{
  /** 用户点击按钮 (kind: graph / formula / hypothesis) */
  'entry-click': [kind: EntryKind]
}>()

// === 智能显示逻辑 ===

const hasKeywordHint = computed(() => {
  const kws = props.intent?.keywords
  return Array.isArray(kws) && kws.length > 0
})

const hasLatexContent = computed(() => {
  const c = props.content || ''
  if (!c) return false
  // 行内公式 $...$ 或块级公式 $$...$$
  // 排除货币符号 ($ 后跟数字) 和简单转义
  return /\$\$[^$]+\$\$|\$[^$\n]{2,}\$/.test(c)
})

const toolNames = computed(() => {
  const names = new Set<string>()
  for (const t of props.toolTrace || []) {
    const n = t?.name || t?.toolName
    if (n) names.add(n)
  }
  return names
})

const calledGraphTool = computed(() => toolNames.value.has('explore_knowledge_graph'))
const calledFormulaTool = computed(() => toolNames.value.has('list_formulas'))
const calledHypothesisTool = computed(() => toolNames.value.has('list_hypotheses'))

const showGraph = computed(() => {
  if (props.forceAll) return true
  return hasKeywordHint.value || calledGraphTool.value
})

const showFormula = computed(() => {
  if (props.forceAll) return true
  return hasLatexContent.value || calledFormulaTool.value
})

const showHypothesis = computed(() => {
  if (props.forceAll) return true
  return calledHypothesisTool.value
})

// === a11y 标签 ===

const ariaLabel = computed(() => '专业模块入口工具栏')
const graphLabel = computed(() => '查看知识图谱')
const formulaLabel = computed(() => '查看相关公式')
const hypothesisLabel = computed(() => '查看相关假设')

function onClick(kind: EntryKind) {
  try {
    emit('entry-click', kind)
  } catch (e) {
    // eslint-disable-next-line no-console
    console.error('[ProEntries] entry-click handler threw', e)
  }
}
</script>

<style scoped>
/**
 * ProEntries — 知识图谱 / 公式 / 假设入口
 * 设计语言对齐 ChatMessageActions / FeedbackButtons:
 * - 暖橙珊瑚色系 + 透明背景
 * - hover 浅珊瑚高光 (--color-primary-alpha-10)
 * - tap 区域满足移动端 44px (mobile) / 桌面 28px (desktop)
 */
.pro-entries {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  position: relative;
}

/* desktop mode: 与 ChatMessageActions 一致, hover/focus 才显示 */
.pro-entries.mode-desktop {
  opacity: 0;
  transition: opacity 200ms ease;
}

.bot-bubble:hover .pro-entries.mode-desktop,
.bot-bubble:focus-within .pro-entries.mode-desktop,
.pro-entries.mode-desktop:focus-within {
  opacity: 1;
}

/* mobile mode: 始终显示 */
.pro-entries.mode-mobile {
  opacity: 1;
}

.entry-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  background: transparent;
  border: 1px solid var(--color-primary-alpha-20, rgba(255, 122, 92, 0.2));
  border-radius: var(--radius-sm, 4px);
  color: var(--color-text-secondary);
  cursor: pointer;
  font-size: 13px;
  line-height: 1;
  transition: background-color 150ms ease, border-color 150ms ease, color 150ms ease;
  /* 默认紧凑桌面尺寸 */
  min-width: 28px;
  height: 28px;
  padding: 0 6px;
}

.entry-btn:hover:not(:disabled) {
  background-color: var(--color-primary-alpha-10, rgba(255, 122, 92, 0.1));
  border-color: var(--color-primary-alpha-30, rgba(255, 122, 92, 0.3));
  color: var(--color-primary, #ff7a5c);
}

.entry-btn:focus-visible {
  outline: 2px solid var(--color-primary, #ff7a5c);
  outline-offset: 2px;
}

.entry-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.entry-icon {
  font-size: 14px;
  display: inline-block;
}

.entry-text {
  font-size: 12px;
}

/* mobile mode: tap 区域 ≥ 44px */
.pro-entries.mode-mobile .entry-btn {
  min-width: 44px;
  height: 44px;
  padding: 0 12px;
  font-size: 14px;
}

.pro-entries.mode-mobile .entry-icon {
  font-size: 18px;
}

/* dark mode: 文字色 + 高亮调整 */
[data-theme='dark'] .entry-btn {
  color: var(--color-text-secondary);
}

[data-theme='dark'] .entry-btn:hover:not(:disabled) {
  background-color: rgba(255, 122, 92, 0.15);
  color: var(--color-primary, #ff7a5c);
}
</style>