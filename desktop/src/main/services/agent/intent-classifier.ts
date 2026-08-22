// Intent Classifier (Phase 8-B0: Research Intent Understanding).
//
// Phase 8-B0: deterministic rule-based classification of a user request into
// a ResearchIntent. NO LLM call, NO randomness. Keyword scoring over fixed
// domain / task tables (+ constraint tags), stable tie-break by enum order.
//
// Phase 8-B0 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - Does NOT import model-provider / auth / chat / backend
//   - Pure functions only (deterministic for equal inputs)

import type {
  ResearchDomain,
  PlannerTaskType,
  ResearchIntent,
  IntentEvidence
} from '../../../shared/agent/planner-schema'
import {
  RESEARCH_DOMAINS,
  PLANNER_TASK_TYPES
} from '../../../shared/agent/planner-schema'

// ============ Keyword tables (Phase 8-B0 deterministic) ============

export const DOMAIN_KEYWORDS: Readonly<Record<ResearchDomain, readonly string[]>> = Object.freeze({
  environment: Object.freeze([
    'environment', 'environmental', 'water', 'air quality', 'gas', 'soil', 'pollut',
    'bubble', 'environment data',
    '水', '空气', '环境', '土壤', '污染', '气泡'
  ]),
  chemistry: Object.freeze([
    'chemistry', 'chemical', 'reaction', 'molecule', 'molecular', 'catalyst',
    'synthesis', 'formula',
    '化学', '反应', '分子', '催化剂', '合成', '公式'
  ]),
  communication: Object.freeze([
    'communication', 'communi', 'signal', 'transmission', 'wireless',
    '通信', '通讯', '信号', '传输', '无线'
  ]),
  control: Object.freeze([
    'control', 'controller', 'pid', 'stability', 'feedback', 'regulation', 'robust',
    '控制', 'pid', '反馈', '调节', '稳定'
  ]),
  experiment: Object.freeze([
    'experiment', 'experimental', 'measurement', 'test rig', 'apparatus', 'protocol',
    '实验', '测量', '装置', '仪器', '试验'
  ])
})

export const TASK_KEYWORDS: Readonly<Record<PlannerTaskType, readonly string[]>> = Object.freeze({
  'literature-review': Object.freeze([
    'literature', 'literature review', 'review', 'survey', 'state of the art',
    '文献', '综述', '文献综述', '调研'
  ]),
  'experiment-analysis': Object.freeze([
    'experiment analysis', 'experimental analysis', 'analyze experiment',
    'analyse experiment', 'experiment result',
    '实验分析', '实验结果', '试验分析'
  ]),
  'data-analysis': Object.freeze([
    'data analysis', 'analyze data', 'analyse data', 'regression', 'fitting',
    'statistics', 'statistical', '统计', '拟合', '回归', '数据分析', '分析数据'
  ]),
  simulation: Object.freeze([
    'simulation', 'simulate', 'modeling', 'modelling', 'numerical', 'cfd', 'computation',
    '模拟', '仿真', '数值', '建模', '模型'
  ]),
  'paper-writing': Object.freeze([
    'paper writing', 'write paper', 'manuscript', 'write up', 'polish',
    '论文', '写作', '润色', '撰写'
  ])
})

export const CONSTRAINT_RULES: ReadonlyArray<Readonly<{ key: string; pattern: RegExp }>> = Object.freeze([
  Object.freeze({ key: 'quantitative', pattern: /\bquantitative\b|定量/ }),
  Object.freeze({ key: 'recent', pattern: /\brecent\b|近三年|近期|最新/ }),
  Object.freeze({ key: 'chinese', pattern: /\bchinese\b|中文/ }),
  Object.freeze({ key: 'fast', pattern: /\bfast\b|快速/ }),
  Object.freeze({ key: 'precise', pattern: /\bprecise(?:ly)?\b|精确/ }),
  Object.freeze({ key: 'compare', pattern: /\bcompare\b|compare[ds]?\b|对比|对照|比较/ })
])

/**
 * Phase 8-B0: capabilities each task template requires.
 * Values align with Phase 7-T3 ToolTaskType vocabulary where possible.
 */
export const CAPABILITIES_BY_TASK: Readonly<Record<PlannerTaskType, readonly string[]>> = Object.freeze({
  'literature-review': Object.freeze(['literature-processing', 'summarization']),
  'experiment-analysis': Object.freeze(['experiment-analysis', 'statistics', 'visualization']),
  'data-analysis': Object.freeze(['data-analysis', 'statistics', 'regression', 'visualization']),
  simulation: Object.freeze(['simulation', 'modeling']),
  'paper-writing': Object.freeze(['writing', 'summarization'])
})

// ============ Matching helpers (deterministic) ============

function normalize(text: string): string {
  return text.toLowerCase().replace(/\s+/g, ' ')
}

function countMatches(haystack: string, keywords: readonly string[]): number {
  let n = 0
  for (const kw of keywords) {
    if (haystack.includes(kw)) n += 1
  }
  return n
}

function matchedKeywords(haystack: string, keywords: readonly string[]): string[] {
  return keywords.filter((kw) => haystack.includes(kw))
}

/** Phase 8-B0: first sentence of the request (deterministic topic source). */
export function extractTopic(text: string): string {
  const first = text.split(/[。！？?!;；\n，,.]/u, 1)[0] ?? ''
  const seg = first.trim()
  if (seg.length === 0) return 'general topic'
  return seg.length > 60 ? seg.slice(0, 60) : seg
}

function extractConstraints(text: string): string[] {
  const out: string[] = []
  for (const rule of CONSTRAINT_RULES) {
    if (rule.pattern.test(text)) out.push(rule.key)
  }
  return out
}

// ============ Public API ============

const FALLBACK_DOMAIN: ResearchDomain = 'experiment'
const FALLBACK_TASK: PlannerTaskType = 'data-analysis'

function assertValidText(userText: string): string {
  if (typeof userText !== 'string') {
    throw new Error('intent classifier: userText must be a string (Phase 8-B0 strict)')
  }
  const trimmed = userText.trim()
  if (trimmed.length === 0) {
    throw new Error('intent classifier: userText must be a non-empty string (Phase 8-B0 strict)')
  }
  return trimmed
}

/**
 * Phase 8-B0: classify a user request into a ResearchIntent.
 * Throws on empty / non-string input. Deterministic.
 */
export function classifyIntent(userText: string): ResearchIntent {
  const evidence = classifyIntentWithEvidence(userText)
  return evidence.intent
}

/**
 * Phase 8-B0: classify + return the raw match evidence (used for confidence).
 */
export function classifyIntentWithEvidence(userText: string): IntentEvidence {
  const text = assertValidText(userText)
  const goal = text.replace(/\s+/g, ' ')
  const hay = normalize(text)

  // Domain scoring: max count wins; stable tie-break by enum order.
  let domain: ResearchDomain = FALLBACK_DOMAIN
  let domainScore = 0
  let domainMatched: string[] = []
  for (const d of RESEARCH_DOMAINS) {
    const score = countMatches(hay, DOMAIN_KEYWORDS[d])
    if (score > domainScore) {
      domain = d
      domainScore = score
      domainMatched = matchedKeywords(hay, DOMAIN_KEYWORDS[d])
    }
  }
  if (domainScore === 0) {
    domain = FALLBACK_DOMAIN
    domainMatched = []
  }

  // Task scoring: same rule.
  let task: PlannerTaskType = FALLBACK_TASK
  let taskScore = 0
  let taskMatched: string[] = []
  for (const t of PLANNER_TASK_TYPES) {
    const score = countMatches(hay, TASK_KEYWORDS[t])
    if (score > taskScore) {
      task = t
      taskScore = score
      taskMatched = matchedKeywords(hay, TASK_KEYWORDS[t])
    }
  }
  if (taskScore === 0) {
    task = FALLBACK_TASK
    taskMatched = []
  }

  const intent: ResearchIntent = {
    topic: extractTopic(text),
    goal,
    domain,
    taskType: task,
    constraints: extractConstraints(text),
    requiredCapabilities: [...CAPABILITIES_BY_TASK[task]]
  }

  return { intent, domain, domainScore, domainMatched, task, taskScore, taskMatched }
}

export const __testHelpers = {
  FALLBACK_DOMAIN,
  FALLBACK_TASK,
  normalize,
  countMatches,
  matchedKeywords
}