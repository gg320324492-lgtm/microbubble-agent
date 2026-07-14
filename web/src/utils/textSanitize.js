/**
 * web/src/utils/textSanitize.js — 前端文本清洗工具
 *
 * 与 app/utils/text_sanitize.py 共享同套清洗思路 (前端版本优先 stable + 快)
 * 用于显示兜底, 防脏 description 仍渲染在卡片上 (后端 sanitize 是预防, 前端 sanitize 是兜底)
 *
 * 触发场景 (2026-07-15):
 *   - 后端清洗是预防, 已写库历史数据或 chat 路径旁路的脏 description 仍可能进入 UI
 *   - 前端 ProjectsPanel.vue 显示时调 cleanDescriptionForDisplay() 兜底
 *
 * 清洗策略:
 *   1. 剥离 markdown 字符 (* _ ` # > 等)
 *   2. 删除 LLM 套路开场白 (好的,非常荣幸.../以下是.../本计划旨在...)
 *   3. 优先抓 "项目名称:/研究方向:/核心目标:" 字段值
 *   4. 退而抓首句含研究动词 + 主题关键词的目标句
 *   5. cap 280 字符 + 优雅截断
 */

const DEFAULT_MAX_LEN = 280

// 粗暴剔除 inline markdown 字符
const INLINE_MD = /[*_`#>]+|\[.+?\]\(.+?\)/g
// 行首标题符
const HEADING_PREFIX = /^\s*#{1,6}\s*/gm
const LIST_DASH = /^\s*[-*]+\s+/gm
// 多空白收尾
const TRAILING_WS = /[ \t]+/g

// LLM 套路开场白 (仅在 stripped text 开头匹配)
const PREAMBLE_PATTERNS = [
  /^好的[，,。\s].{0,80}(计划|安排|为您|开始).{0,40}[。\n]/,
  /^非常荣幸[，,。\s].{0,80}[。\n]/,
  /^以下是.{0,30}计划[：:，,。\s].{0,40}[。\n]/,
  /^下面为?您.{0,30}规划[。\n]/,
  /^根据.{0,40}要求[，,。\s].{0,40}[。\n]/,
  /^感谢.{0,40}提问[。\n]/,
]

// LLM 计划字段 (贪婪 + 行末锚 + min 6 字避非贪婪 bug)
const FIELD_PATTERNS = [
  /项目名称\s*[:：]\s*([^\n\r]{6,280})/,
  /研究方向\s*[:：]\s*([^\n\r]{6,280})/,
  /核心目标\s*[:：]\s*([^\n\r]{6,280})/,
]

const FIELD_STOP_WORDS = ['6个月', '本计划', '团队人数', '团队角色', '3人',
  '项目周期', '团队构成', '团队配置']

const TOPIC_KEYWORDS = ['微纳米气泡', '微气泡', '气泡成核', '纳米气泡',
  '抗生素', '臭氧', '过氧化氢', '羟基自由基',
  '水处理', '降解', '高级氧化', '黑臭水体',
  '水产养殖', '饮用水', '稳定性', '消毒',
  '污染物', '底泥', '去除', '抑制', '效率', '机理', '效能']

const RESEARCH_VERBS = ['研究', '探索', '调查', '探讨', '开展', '开发', '提出', '构建',
  '建立', '分析', '设计', '研发', '实现', '优化', '验证']

const FIELD_LABEL_PREFIXES = ['项目名称', '项目周期', '团队构成',
  '团队配置', '核心目标', '具体任务',
  '阶段划分', '分阶段', '阶段产出',
  '第一阶段', '第二阶段', '第三阶段',
  '第四阶段', '第五阶段', '沟通与调整',
  '风险管控', '成果最大化', '祝您的',
  '项目总览']

// LLM 句首语气词 (Step C/D 跳过, 含 祝您/感谢/重要提示 等)
// 注意: 不含 "本计划/本项目" — 后面常跟有意义的研究句, 由 Step C-1 捕获
const LLM_TONE_STARTS = ['祝您', '感谢', '下面是', '以下为', '接下来',
  '后续我们', '我们希望', '我们建议',
  '请注意', '请参考',
  '重要提示', '风险评估']

function _stripMd(t) {
  return t.replace(INLINE_MD, '').replace(HEADING_PREFIX, '').replace(LIST_DASH, '')
}

function _endsWithPunc(s) {
  if (!s) return false
  const c = s[s.length - 1]
  return '。.!?！？…'.includes(c)
}

/**
 * 清洗 description 用于前端显示 (后端 sanitize 已预防, 此函数是 UI 兜底).
 *
 * @param {string|null|undefined} raw - 原始 description
 * @param {number} maxLen - 最大字符数 (默认 280)
 * @returns {string} 清洗后 ≤ maxLen 字符串; 空输入返回 ''
 */
export function cleanDescriptionForDisplay(raw, maxLen = DEFAULT_MAX_LEN) {
  if (!raw || !String(raw).trim()) return ''

  let text = String(raw)
  text = _stripMd(text)

  // Step A: 抓 LLM 字段值 (matchAll 多个 "项目名称:" 时回退到下一个)
  for (const pat of FIELD_PATTERNS) {
    const matches = text.matchAll(new RegExp(pat.source, 'g' + (pat.flags ? '' : pat.flags)))
    for (const m of matches) {
      const value = m[1].trim().replace(INLINE_MD, '').trim()
      if (FIELD_STOP_WORDS.some(w => value.includes(w))) continue
      if (value.length >= 6 && value.length <= maxLen) {
        return _endsWithPunc(value) ? value : value + '。'
      }
    }
  }

  // Step B: 删 LLM 套路开场白 (按句子切, 只在首句检测, 不污染后续内容)
  let stripped = text.trim()
  const firstBreak = stripped.search(/[。\n]/)
  const firstSent = firstBreak >= 0 ? stripped.slice(0, firstBreak) : stripped
  let preambleMatched = false
  for (const pat of PREAMBLE_PATTERNS) {
    if (pat.test(firstSent)) { preambleMatched = true; break }
  }
  if (preambleMatched && firstBreak >= 0) {
    stripped = stripped.slice(firstBreak + 1).trimLeft()
  } else if (preambleMatched) {
    // 整段就一句话且是 preamble → 整段丢弃
    stripped = ''
  }

  // Step C/D: 找首句
  const sentences = stripped.split(/[。\n]/).map(s => s.trim()).filter(s => s.length >= 8)
  let finalText = null

  // Step C-1: 研究动词 + 主题关键词
  for (const sent of sentences) {
    if (FIELD_LABEL_PREFIXES.some(p => sent.startsWith(p))) continue
    if (LLM_TONE_STARTS.some(t => sent.startsWith(t))) continue
    const hasVerb = RESEARCH_VERBS.some(v => sent.startsWith(v))
    const hasTopic = TOPIC_KEYWORDS.some(k => sent.includes(k))
    if (hasVerb && hasTopic) { finalText = sent; break }
  }

  // Step C-2: 多主题关键词 + 不长
  if (!finalText) {
    for (const sent of sentences) {
      if (FIELD_LABEL_PREFIXES.some(p => sent.startsWith(p))) continue
      if (LLM_TONE_STARTS.some(t => sent.startsWith(t))) continue
      const kwCount = TOPIC_KEYWORDS.filter(k => sent.includes(k)).length
      if (kwCount >= 2 && sent.length <= maxLen) { finalText = sent; break }
    }
  }

  // Step D: fallback
  if (!finalText) {
    for (const sent of sentences) {
      if (FIELD_LABEL_PREFIXES.some(p => sent.startsWith(p))) continue
      if (LLM_TONE_STARTS.some(t => sent.startsWith(t))) continue
      finalText = sent
      break
    }
  }

  if (!finalText) return ''

  // 优雅截断 (保证最终 ≤ maxLen)
  while (finalText.length > maxLen) {
    let truncated = finalText.slice(0, maxLen)
    let cutIdx = -1
    for (const sep of ['。', '；', ';', '—']) {
      const idx = truncated.lastIndexOf(sep)
      if (idx > maxLen / 2) { cutIdx = idx; break }
    }
    if (cutIdx > -1) {
      truncated = truncated.slice(0, cutIdx + 1)
    } else {
      truncated = finalText.slice(0, maxLen - 3).trimRight() + '...'
    }
    finalText = truncated
    if (finalText.length > maxLen) {
      finalText = finalText.slice(0, maxLen)
      break
    }
  }

  finalText = finalText.replace(TRAILING_WS, ' ').trim()
  if (finalText && !_endsWithPunc(finalText)) {
    finalText += '。'
  }

  return finalText
}

/**
 * 显示 description 字符串 (空时返 '暂无描述').
 */
export function displayDescription(raw, maxLen = DEFAULT_MAX_LEN) {
  const cleaned = cleanDescriptionForDisplay(raw, maxLen)
  return cleaned || '暂无描述'
}
