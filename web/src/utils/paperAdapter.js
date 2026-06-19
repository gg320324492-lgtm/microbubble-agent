/**
 * 论文数据适配器（paperAdapter.js）
 *
 * 通用论文阅读器渲染层。把后端返回的原始数据（OCR/PDF 解析/多模态提取）
 * 统一转成 PaperDetail 结构，方便前端组件渲染。
 *
 * 设计原则：
 * - 后端数据格式不固定：可能是格式化后的 markdown，也可能是带 [PAGE:N]/[FIGURE:N] 占位符的纯文本
 * - 论文结构不一定完整：缺摘要、缺结论、缺参考文献、缺图都常见
 * - 永远不抛错：所有识别失败都返回合理的 fallback
 *
 * 公开入口：
 *   normalizePaperData(rawData, extra) - 主入口
 *   parsePaperSections(content)        - 拆 section（仅在没 formatted_content 时用）
 *   extractPageMarkers(content)        - 提取 [PAGE:N] 占位符
 *   extractFigureMarkers(content)      - 提取 [FIGURE:N] 占位符
 *   matchFiguresWithCaptions(...)      - 关联图与图注
 *   buildAnchorTree(sections)          - 生成右侧导航树
 *   splitReferences(content)           - 拆分参考文献
 *   autoLinkContent(text)              - DOI/URL/邮箱自动链接
 */

// ============================================================
// 常量：通用识别规则
// ============================================================

// 章节标题关键词（严格 ^...$ 锚定，只匹配独立行的标题）
// 不用宽松的 \b 匹配，避免正文中含 "method"/"result"/"experimental"
// 等词的句子被误识别为章节标题
const SECTION_KEYWORDS = [
  // 复合 keyword 在前（避免被短 keyword 误吃）
  { type: 'graphical_abstract', regex: /^\s*(graphical\s+abstract|图解摘要|图形摘要)\s*[:：]?\s*$/i },
  { type: 'article_info', regex: /^\s*(article\s+info(rmation)?|文章信息|论文信息)\s*[:：]?\s*$/i },
  { type: 'highlights', regex: /^\s*(highlights?|亮点|研究亮点)\s*[:：]?\s*$/i },
  { type: 'abstract', regex: /^\s*(abstract|summary|摘要|内容摘要|文摘)\s*[:：]?\s*$/i },
  { type: 'keywords', regex: /^\s*(keywords?|key\s*words?|关键词|关键字)\s*[:：]?\s*$/i },
  // methods / results / discussion / conclusion / introduction / background
  // 全部带 ^ 锚定 + 行尾 \s*$，且 methods/results 必须带编号前缀或独立
  { type: 'introduction', regex: /^\s*(\d+(\.\d+)*\.?\s+)?(introduction|引言|前言|绪论|序言)\s*[:：]?\s*$/i },
  { type: 'background', regex: /^\s*(\d+(\.\d+)*\.?\s+)?(background|研究背景|问题背景)\s*[:：]?\s*$/i },
  { type: 'methods', regex: /^\s*(\d+(\.\d+)*\.?\s+)?(method(s|ology)?|materials?\s+and\s+method(s|ology)?|experimental(\s+(section|methods?|setup))?|材料与方法|实验方法|实验部分|方法|实验材料与方法)\s*[:：]?\s*$/i },
  { type: 'results', regex: /^\s*(\d+(\.\d+)*\.?\s+)?(results?(\s+and\s+discussion)?|结果(与讨论|和分析)?|实验结果|结果与讨论)\s*[:：]?\s*$/i },
  { type: 'discussion', regex: /^\s*(\d+(\.\d+)*\.?\s+)?(discussion|讨论|分析与讨论)\s*[:：]?\s*$/i },
  { type: 'conclusion', regex: /^\s*(\d+(\.\d+)*\.?\s+)?(conclusions?|总结|结论|结语|小结)\s*[:：]?\s*$/i },
  { type: 'acknowledgments', regex: /^\s*(acknowledg(e)?ments?|致谢|鸣谢)\s*[:：]?\s*$/i },
  { type: 'references', regex: /^\s*(references?|bibliography|参考文献|引用文献)\s*[:：]?\s*$/i },
  { type: 'supplementary', regex: /^\s*(supporting\s+information|supplementary\s+(material|information|content)|附录|补充材料|补充信息)\s*[:：]?\s*$/i },
  { type: 'appendix', regex: /^\s*(appendix|附录)\s*[:：]?\s*$/i },
]

// 编号章节模式（带或不带点）—— 只匹配前导编号 + 空白，不吞标题
// 严格限制：
// - 数字 1-2 位（避免匹配 "2018. Formation" 这种年份开头）
// - 必须后跟大写或中文字符（避免匹配 "[55] (14)" 这种参考文献条目）
// - 容忍 "1.Introduction"（无空格）和 "1. Introduction"（有空格）
const NUMBERED_SECTION_RE = /^\s*(\d{1,2}(\.\d{1,2}){0,3})\.?\s*([A-Z一-龥])/

// 页码占位符（多种形式）
const PAGE_MARKER_RES = [
  /\[PAGE:(\d+)\]/g,
  /\[Page\s*(\d+)\]/gi,
  /\[页\s*(\d+)\]/g,
  /第\s*(\d+)\s*页\s*[\n\r]/g,
  /\bPAGE\s+(\d+)\b/g,
  /\bPage\s+(\d+)\b/g,
]

// 图/表占位符（多种形式）
const FIGURE_MARKER_RE = /\[FIGURE:([\d.a-zA-Z]+)\]/g
const TABLE_MARKER_RE = /\[TABLE:([\d.a-zA-Z]+)\]/g

// 链接识别（DOI 不含特殊字符的简单版，避免后向引用错乱）
const DOI_RE = /\b(10\.\d{4,9}\/[A-Za-z0-9._;()\/\-:]+)/gi
const URL_RE = /\bhttps?:\/\/[^\s<>"')]+/g
const EMAIL_RE = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g

// 引用模式：参考文献条目通常以 [1] / 1. / (Smith 2020) 开头
// 兼容真实 OCR 格式：
// - [1] Author, A. B. (2020). Title. Journal. https://doi.org/...
// - [55] (14), 9691-9710. Title. Journal.  ← (14) 是卷号，紧跟空格
// - 1. Author. Title. Journal.
// - 100031. https://doi.org/...           ← 只剩 DOI 的精简条目
// 关键: 整行必须以 [N] / N. / N 开头（数字），否则不是参考文献
const REFERENCE_ENTRY_RE = /^\s*(?:\[\d+\]|\d+\.)\s+\S/

// 图片扩展名（识别裸图片 URL）
const IMG_EXT_RE = /\.(?:jpe?g|png|webp|gif|bmp|svg)(?:\?[^\s]*)?$/i

// 系统内部标记（不应在正文中显示）
const INTERNAL_MARKER_RES = [
  /<!--\s*MULTIMODAL_INLINED[^*]*-->/gi,
  /<!--\s*OCR_TEXT[^>]*-->/gi,
  /<!--[\s\S]*?-->/g, // 任意 HTML 注释
  /\bJSON\s*(?:格式|output|response)\s*[:：]?\s*[{\[][^\n]*/gi, // LLM prompt 残留
  /\b(?:json|markdown)\s*(?:格式|output|format)\s*[:：]?\s*$/gim, // 单独的格式要求行
  /\[FIGURE:\d+\]/g, // [FIGURE:N] 占位符转锚点（不应在正文中显示）
  /\[TABLE:\d+\]/g,
  /\[IMAGE:[^\]]*\]/g,
  /\[图\s*[Pp]?\d+\]/g, // [图 P1] 等
]

// HTML 属性残留
const HTML_ATTR_RES = [
  /\s+target\s*=\s*"[^"]*"/gi,
  /\s+target\s*=\s*'[^']*'/gi,
  /\s+rel\s*=\s*"[^"]*"/gi,
  /\s+rel\s*=\s*'[^']*'/gi,
  /\s+class\s*=\s*"[^"]*"/gi,
  /\s+class\s*=\s*'[^']*'/gi,
  /\s+style\s*=\s*"[^"]*"/gi,
  /\s+style\s*=\s*'[^']*'/gi,
  /\s+width\s*=\s*"\d+%?"/gi,
  /\s+height\s*=\s*"\d+%?"/gi,
  /\s+id\s*=\s*"[^"]*"/gi,
]

// 重复 DOI 链接修复
// 匹配 (https?://(dx.)?doi.org/)+ 后面再有 (https?://(dx.)?doi.org/)* 的情况
const DOI_DUP_RE = /(?:https?:\/\/(?:dx\.)?doi\.org\/){2,}/gi
// 修复 doi.org/doi.org/xxx（无协议，2 个连续 doi.org/）
const DOI_DUP_NOPROTO_RE = /(?:(?:dx\.)?doi\.org\/){2,}/gi

// PDF 页脚 / 出版信息模式（不直接删除，但避免反复出现在正文中）
const FOOTER_PATTERNS = [
  /Journal\s+of\s+[A-Z][a-zA-Z\s&]+\d+\s*\(\d{4}\)\s*\d+/g, // Journal of Xxx 123 (2024) 456
  /Available\s+online\s+\d+\s+\w+\s+\d{4}/gi,
  /©\s*\d{4}\s+(?:Elsevier|Elsevier\s+B\.V\.|Springer|Wiley|American\s+Chemical\s+Society).*$/gim,
  /https?:\/\/(?:www\.)?sciencedirect\.com\/science\/article\/[^\s]+/gi,
  /Received\s+in\s+revised\s+form\s+\d+\s+\w+\s+\d{4}.*?Accepted\s+\d+\s+\w+\s+\d{4}/gi,
  /Received\s+\d+\s+\w+\s+\d{4}.*?Available\s+online\s+\d+\s+\w+\s+\d{4}/gi,
]

// 字符间隔的标题（H I G H L I G H T S → HIGHLIGHTS）
const SPACED_TITLE_RE = /\b([A-Z])\s+([A-Z])\s+([A-Z])\s+([A-Z](?:\s+[A-Z])+)\b/g


// ============================================================
// 工具函数
// ============================================================

let _idCounter = 0
function _genId(prefix = 'b') {
  _idCounter += 1
  return `${prefix}_${_idCounter.toString(36)}`
}

function _escapeHtml(s) {
  if (s == null) return ''
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function _isChineseHeavy(text) {
  if (!text) return false
  const cn = (text.match(/[一-龥]/g) || []).length
  return cn / Math.max(1, text.length) > 0.2
}

function _cleanText(text) {
  if (!text) return ''
  return text
    .replace(/\r\n/g, '\n')
    // 合并连续空行（≥3 个换行 → 2 个）
    .replace(/\n{3,}/g, '\n\n')
    // 去除行尾空格
    .replace(/[ \t]+\n/g, '\n')
    // 合并 OCR 异常断行：中文字符后被强行换行 + 下一行也是中文字符
    .replace(/([一-龥，。：；！？、])\n([一-龥])/g, '$1$2')
    .trim()
}

/**
 * DOI 文本规范化：修复各种重复 / 错误前缀
 *
 * 规则：
 * - https://doi.org/https://doi.org/xxx → https://doi.org/xxx
 * - http://dx.doi.org/https://doi.org/xxx → https://doi.org/xxx
 * - doi.org/doi.org/xxx → https://doi.org/xxx
 * - DOI: https://doi.org/xxx → https://doi.org/xxx
 * - 裸 DOI 10.xxxx/xxxxx → https://doi.org/10.xxxx/xxxxx（不修改，给 autoLinkContent 处理）
 */
export function normalizeDoiText(text) {
  if (!text) return ''
  let result = String(text)
  // 1. 多个完整 DOI URL 串联 → 保留最后一个完整
  result = result.replace(/(?:https?:\/\/(?:dx\.)?doi\.org\/)+/gi, 'https://doi.org/')
  // 2. dx.doi.org 前缀 → doi.org
  result = result.replace(/https?:\/\/dx\.doi\.org\//gi, 'https://doi.org/')
  // 3. 裸 doi.org/ 重复
  result = result.replace(/(?:(?:dx\.)?doi\.org\/){2,}/gi, 'doi.org/')
  // 4. "DOI:" / "DOI：" 前缀剥除（保留 URL）
  result = result.replace(/\bDOI\s*[:：]\s*(https?:\/\/(?:dx\.)?doi\.org\/)/gi, '$1')
  return result
}

/**
 * 行内章节标题切分
 *
 * 真实 OCR / LLM 输出常把章节标题挤在前一段文字中：
 *   "...conditions. 1. Introduction The emission of..."
 *   "...support at room temperature. 2. Materials and methods 2.1 Experimental system..."
 *   "...kinetics. 3. Results and discussion..."
 *
 * 把这些模式前面插入换行符，让它们变成独立行。
 */
export function insertSectionBreaks(text) {
  if (!text) return ''
  let result = String(text)

  // 处理 字符间隔的标题（OCR 字符全大写带空格）
  // "H I G H L I G H T S" → "HIGHLIGHTS"（独立成行）
  result = result.replace(/\b([A-Z])\s+([A-Z])\s+([A-Z])\s+([A-Z](?:\s+[A-Z])+)\b/g, (m) => {
    return '\n' + m.replace(/\s+/g, '') + '\n'
  })

  // 多个标题合并（HIGHLIGHTSGRAPHICALABSTRACTARTICLEINFO）→ 拆成多行
  // 用大写英文单词做拆分点
  const mergedTitleRe = /(?<![A-Z])(HIGHLIGHTS|GRAPHICAL\s+ABSTRACT|ARTICLE\s+INFO(?:RMATION)?|KEYWORDS|ABSTRACT|INTRODUCTION|MATERIALS\s+AND\s+METHODS|RESULTS?\s+AND\s+DISCUSSION|CONCLUSIONS?|REFERENCES|ACKNOWLEDGEMENTS|GRAPHICALABSTRACT|ARTICLEINFO)/gi
  result = result.replace(mergedTitleRe, '\n$1\n')

  // 同行内章节标题：句末+编号+标题
  // "conditions. 1. Introduction" → "conditions.\n1. Introduction"
  result = result.replace(
    /([。.!?;]|\b[a-z]+\b)\s+(\d+(?:\.\d+)?\.?\s+(Introduction|引言)\b)/gi,
    '$1\n$2'
  )
  result = result.replace(
    /([。.!?;]|\b[a-z]+\b)\s+(\d+(?:\.\d+)?\.?\s+(Materials\s+and\s+methods|Methods|Experimental(?:\s+section)?|Methods\s+and\s+materials|材料与方法|实验方法|方法)\b)/gi,
    '$1\n$2'
  )
  result = result.replace(
    /([。.!?;]|\b[a-z]+\b)\s+(\d+(?:\.\d+)?\.?\s+(Results?\s+and\s+discussion|Results|Discussion|结果与讨论|结果|讨论)\b)/gi,
    '$1\n$2'
  )
  result = result.replace(
    /([。.!?;]|\b[a-z]+\b)\s+(\d+(?:\.\d+)?\.?\s+(Conclusions?|Conclusion|结论|总结)\b)/gi,
    '$1\n$2'
  )
  result = result.replace(
    /([。.!?;]|\b[a-z]+\b)\s+(\d+(?:\.\d+)?\.?\s+(References|参考文献)\b)/gi,
    '$1\n$2'
  )
  result = result.replace(
    /([。.!?;]|\b[a-z]+\b)\s+(\d+(?:\.\d+)?\.?\s+(Acknowledg(?:e)?ments?|致谢)\b)/gi,
    '$1\n$2'
  )

  // 中文无编号章节
  result = result.replace(
    /([。！？])\s*(摘要|引言|前言|材料与方法|实验方法|结果与讨论|结论|参考文献|致谢)\b/g,
    '$1\n$2'
  )

  // 合并连续空行
  result = result.replace(/\n{3,}/g, '\n\n')
  return result
}

/**
 * 删除正文开头的 front matter
 * （HIGHLIGHTS / GRAPHICAL ABSTRACT / ARTICLE INFO / ABSTRACT / KEYWORDS / 作者单位 / 标题）
 *
 * 返回正文从 Introduction（或第一个正文段）开始的内容
 */
export function removeFrontMatter(content) {
  if (!content) return { cleaned: '', abstract: null, keywords: [], hasFrontMatter: false }

  let result = String(content)

  // 1. 找第一个 Introduction / 引言 位置（正文从此开始）
  const introMatch = result.match(/(?:^|\n)\s*(\d+(\.\d+)*\.?\s+)?(Introduction|引言|前言|绪论)\b/i)
  const introIdx = introMatch ? introMatch.index : -1

  if (introIdx < 0) {
    // 没找到 Introduction 起点，原样返回
    return { cleaned: result, abstract: null, keywords: [], hasFrontMatter: false }
  }

  const frontMatter = result.slice(0, introIdx)
  const body = result.slice(introIdx)

  return {
    cleaned: body.trim(),
    frontMatter: frontMatter.trim(),
    hasFrontMatter: true,
  }
}

/**
 * 强力清洗论文原始正文（OCR / LLM 输出 / PDF 抽取）
 *
 * 流程：
 *   1. insertSectionBreaks  → 拆分行内章节标题
 *   2. HTML 属性 / markdown 图片 / 裸图片 URL / 系统内部标记
 *   3. DOI 规范化
 *   4. PDF 页脚
 *   5. 字符间隔 / 强调 / 孤立元行
 */
export function cleanContent(text, options = {}) {
  if (!text) return { content: '', extractedImages: [] }
  const extractedImages = []
  const { stripImageUrls = true, isMarkdown = false } = options

  let result = String(text)

  // 0. 先剥除 LLM blockquote 图描述（> 📊 **图表说明（Px）**\n> ... 整段）
  //    这些是 inline 进正文的图注描述，不应作为正文段落
  //    保留为 figure caption 候选
  const captionBlocks = []
  result = result.replace(/^[ \t]*>[ \t]*((?:📊|📈|📉|🖼|🧪|⚗|🔬|🔍|💠)?[ \t]*[*_]*\s*(?:图表说明|Figure\s+caption|Table\s+caption|Caption|图表描述|Figure description)[^]*?)(?=\n[ \t]*[^>]|\n\n|$)/gim, (m, captionText) => {
    captionBlocks.push(captionText.replace(/^[ \t]*>[ \t]*/gm, '').trim())
    return '' // 整段剥除
  })

  // 0.1 剥除 OCR 风格作者列表 + 单位块（开头常见）
  //    "Tianzhi Wang a, Hangjia Zhao a, ...\nFawei Lin a,*\na School of ..., Tianjin 300072"
  //    标题之下、Abstract 之前的 author + affiliation 整段
  result = result.replace(
    /^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+[a-z](?:[,\s]+[A-Z][a-z]+\s+[a-z])+[,]?\s*(?:\d[,\s]*)+(?:[\n\r]\s*[A-Z][a-z]+\s+[a-z][\s,]*[*†‡§]?)*\s*[\n\r]\s*(?:[a-z]\s+(?:School|College|Institute|Department|University)[^\n]+(?:\n[^\n]+){0,3}))/m,
    ''
  )

  // 0.2 先拆分行内章节标题（markdown 模式跳过，会破坏 # 标记）
  if (!isMarkdown) {
    result = insertSectionBreaks(result)
  }

  // 1. HTML 属性残留
  for (const re of HTML_ATTR_RES) {
    result = result.replace(re, '')
  }

  // 2. Markdown 图片语法 ![alt](url) → 提取到 figures，剥除
  result = result.replace(/!\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g, (m, alt, url) => {
    if (url.match(IMG_EXT_RE) || /\/minio\//.test(url)) {
      extractedImages.push({ url: url.trim(), alt: (alt || '').trim() })
      return ''
    }
    return m
  })

  // 3. 裸图片 URL
  if (stripImageUrls) {
    result = result.replace(/^[ \t]*(https?:\/\/[^\s<>"')]+)\s*$/gim, (m, url) => {
      if (IMG_EXT_RE.test(url) || /\/minio\//.test(url)) {
        extractedImages.push({ url: url.trim(), alt: '' })
        return ''
      }
      return m
    })
    result = result.replace(URL_RE, (m) => {
      if (IMG_EXT_RE.test(m) || /\/minio\//.test(m)) {
        extractedImages.push({ url: m, alt: '' })
        return ''
      }
      return m
    })
  }

  // 4. 系统内部标记
  for (const re of INTERNAL_MARKER_RES) {
    result = result.replace(re, '')
  }

  // 5. DOI 规范化
  result = normalizeDoiText(result)

  // 6. PDF 页脚
  for (const re of FOOTER_PATTERNS) {
    result = result.replace(re, '')
  }

  // 7. 字符间隔的标题（insertSectionBreaks 已处理大部分，这里兜底；markdown 跳过）
  if (!isMarkdown) {
    result = result.replace(SPACED_TITLE_RE, (m) => m.replace(/\s+/g, ''))
  }

  // 8. Markdown 强调 `**text**` → text（仅 markdown 处理）
  if (isMarkdown) {
    result = result.replace(/\*\*([^*\n]+)\*\*/g, '$1')
  }

  // 9. 孤立的元行
  result = result.replace(/^图表说明\s*\([Pp]\d+\)\s*$/gm, '')
  result = result.replace(/^Caption\s*[:：]?\s*$/gim, '')

  // 10. 合并空行 + 行尾空白
  result = result.replace(/\n{3,}/g, '\n\n').replace(/[ \t]+\n/g, '\n').trim()

  return { content: result, extractedImages }
}


// ============================================================
// 识别器
// ============================================================

/**
 * 提取 [PAGE:N] 占位符
 * @returns {Array<{page: number, index: number, length: number}>}
 */
export function extractPageMarkers(content) {
  if (!content) return []
  const results = []
  const seenPage = new Set()
  for (const re of PAGE_MARKER_RES) {
    re.lastIndex = 0
    let m
    while ((m = re.exec(content)) !== null) {
      const page = parseInt(m[1], 10)
      if (!Number.isFinite(page)) continue
      // 同一页码只保留第一个出现的标记
      if (seenPage.has(page)) continue
      seenPage.add(page)
      results.push({ page, index: m.index, length: m[0].length })
    }
  }
  results.sort((a, b) => a.index - b.index)
  return results
}

/**
 * 提取 [FIGURE:N] 占位符
 */
export function extractFigureMarkers(content) {
  if (!content) return []
  const results = []
  let m
  FIGURE_MARKER_RE.lastIndex = 0
  while ((m = FIGURE_MARKER_RE.exec(content)) !== null) {
    results.push({
      id: m[1],
      index: m.index,
      length: m[0].length,
    })
  }
  return results
}

/**
 * 提取 [TABLE:N] 占位符
 */
export function extractTableMarkers(content) {
  if (!content) return []
  const results = []
  let m
  TABLE_MARKER_RE.lastIndex = 0
  while ((m = TABLE_MARKER_RE.exec(content)) !== null) {
    results.push({
      id: m[1],
      index: m.index,
      length: m[0].length,
    })
  }
  return results
}

/**
 * 从文本中匹配章节标题
 * @returns {{ type: string, level: number } | null}
 */
function _matchSectionTitle(text) {
  const trimmed = text.trim()
  if (!trimmed || trimmed.length > 120) return null

  // 尝试剥离前导编号：1 / 1.1 / 1.1.1 / 1. / 一、
  let stripped = trimmed
  let level = 1
  const numbered = trimmed.match(NUMBERED_SECTION_RE)
  let cnNumbered = null
  if (numbered) {
    stripped = trimmed.slice(numbered[0].length).trim()
    level = numbered[1].split('.').length
  } else {
    cnNumbered = /^[一二三四五六七八九十]+[、.]\s*/.exec(trimmed)
    if (cnNumbered) {
      stripped = trimmed.slice(cnNumbered[0].length).trim()
      level = 1
    }
  }

  // 优先匹配关键词
  for (const kw of SECTION_KEYWORDS) {
    if (kw.regex.test(stripped)) {
      return { type: kw.type, level }
    }
  }

  // 编号章节：1 / 1.1 / 1.1.1 / 1 Title / 一、xxx
  if (numbered) {
    return { type: 'normal', level }
  }

  // 中文编号：一、二、三、
  if (cnNumbered) {
    return { type: 'normal', level: 1 }
  }

  return null
}

/**
 * 把 content 拆成多个 section
 *
 * 输入示例：
 *   "[PAGE:1]Title\nAbstract\nThis paper...\n[PAGE:2]\n1 Introduction\n..."
 *
 * @returns {Array<PaperSection>}
 */
export function parsePaperSections(content, options = {}) {
  if (!content) return []
  const { isMarkdown = false } = options

  // 如果是 markdown，# / ## / ### 已经是结构化标题
  if (isMarkdown) {
    return _parseMarkdownSections(content)
  }

  // 纯文本：按行扫描，识别章节标题
  return _parsePlainTextSections(content)
}

function _parseMarkdownSections(content) {
  const lines = content.split('\n')
  const sections = []
  let current = null
  let paragraphBuf = []
  let preambleBuf = []

  const flushParagraph = () => {
    if (!current) return
    if (paragraphBuf.length) {
      current.blocks.push({
        type: 'paragraph',
        content: paragraphBuf.join('\n').trim(),
      })
      paragraphBuf = []
    }
  }

  const pushCurrent = () => {
    if (!current) return
    flushParagraph()
    // 即使 blocks 为空，仍保留（让 H1 标题等单独成 section 出现在导航里）
    sections.push(current)
  }

  for (const line of lines) {
    const headingMatch = /^(#{1,4})\s+(.+)$/.exec(line)
    if (headingMatch) {
      pushCurrent()
      const level = headingMatch[1].length
      const title = headingMatch[2].trim()
      const matched = _matchSectionTitle(title)
      current = {
        id: _genId('s'),
        title,
        level,
        type: matched?.type || 'normal',
        blocks: [],
      }
      continue
    }
    // 第一个标题之前累积为 preamble
    if (!current) {
      if (line.trim()) preambleBuf.push(line)
    } else {
      if (line.trim()) paragraphBuf.push(line)
    }
  }
  pushCurrent()

  // 处理 preamble：如果没找到任何标题，把整段当一个 normal section
  if (!sections.length && preambleBuf.length) {
    sections.push({
      id: _genId('s'),
      title: '内容',
      level: 1,
      type: 'normal',
      blocks: [{ type: 'paragraph', content: preambleBuf.join('\n').trim() }],
    })
  } else if (preambleBuf.length && !sections.length) {
    sections.unshift({
      id: _genId('s'),
      title: '内容',
      level: 1,
      type: 'normal',
      blocks: [{ type: 'paragraph', content: preambleBuf.join('\n').trim() }],
    })
  }
  return sections
}

function _parsePlainTextSections(content) {
  const lines = content.split('\n')
  const sections = []
  let current = null
  let buffer = []
  let preamble = []

  const pushCurrent = () => {
    if (!current) return
    if (buffer.length) {
      current.blocks.push({
        type: 'paragraph',
        content: buffer.join('\n').trim(),
      })
      buffer = []
    }
    // 即使 blocks 为空也保留 section（让所有识别到的标题都进 sections 数组）
    sections.push(current)
  }

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i]
    const trimmed = line.trim()
    const match = _matchSectionTitle(trimmed)

    // 标题行：要求是较短的单行，且后面有内容
    if (match && trimmed.length < 100 && i + 1 < lines.length) {
      // 看一下下面是否真的开始新内容（不是孤立行）
      const nextNonEmpty = lines.slice(i + 1).find(l => l.trim())
      // 编号章节或关键词章节单独成行也算
      const isLikelyTitle =
        match.type !== 'normal' ||
        /^\d+(\.\d+)*\.?\s+/.test(trimmed) ||
        (nextNonEmpty && nextNonEmpty.trim().length > 0)

      if (isLikelyTitle) {
        pushCurrent()
        // 章节 type 净化：abstract/keywords/highlights/article_info 都视为 metadata
        const normalizedType = match.type
        current = {
          id: _genId('s'),
          title: trimmed.replace(/[:：]\s*$/, ''),
          level: match.level,
          type: normalizedType,
          blocks: [],
        }
        continue
      }
    }

    if (current) {
      if (trimmed) buffer.push(line)
    } else {
      if (trimmed) preamble.push(line)
    }
  }
  pushCurrent()

  // preamble 单独成一个 section（一般含标题、作者）
  if (preamble.length) {
    sections.unshift({
      id: _genId('s'),
      title: '前言',
      level: 1,
      type: 'preamble',
      blocks: [{ type: 'paragraph', content: preamble.join('\n').trim() }],
    })
  }

  // 如果完全没有识别到任何 section，把整段当一个
  if (!sections.length) {
    sections.push({
      id: _genId('s'),
      title: '内容',
      level: 1,
      type: 'normal',
      blocks: [{ type: 'paragraph', content: content.trim() }],
    })
  }

  // 去重 OCR 重复识别的章节（不只相邻，全局去重）
  // 规则：同 type + title 相似（lowercase 比较）→ 跳过（保留第一次出现）
  const deduped = []
  const seenKeys = new Set()
  for (const s of sections) {
    const key = `${s.type}::${(s.title || '').toLowerCase().trim()}`
    if (seenKeys.has(key)) {
      // 重复：合并到第一次出现的 sections
      const first = deduped.find(d => `${d.type}::${(d.title || '').toLowerCase().trim()}` === key)
      if (first) {
        first.blocks = (first.blocks || []).concat(s.blocks || [])
      }
      continue
    }
    seenKeys.add(key)
    deduped.push(s)
  }
  return deduped
}


/**
 * 拆分参考文献
 * @returns {Array<string>}
 */
export function splitReferences(content) {
  if (!content) return []
  const lines = content.split('\n')
  const entries = []
  let buffer = []
  for (const line of lines) {
    if (REFERENCE_ENTRY_RE.test(line)) {
      if (buffer.length) {
        entries.push(buffer.join('\n').trim())
        buffer = []
      }
    }
    if (line.trim()) buffer.push(line)
  }
  if (buffer.length) entries.push(buffer.join('\n').trim())
  return entries.filter(e => e.length > 10)
}


/**
 * 把 [PAGE:N] / [FIGURE:N] / 链接替换成锚点标记
 * 用于在原文段落中插入不可见锚点，让右侧导航能跳转
 */
function _embedAnchors(blocks, pageMarkers, figureMarkers, tableMarkers) {
  // 简化：给每个 block 加上 page 标记（在哪个页码）
  let currentPage = null
  // 简化处理：blocks 是按行聚合后的，纯文本情况下"页码标记"通常跨段落
  // 此处只在 _buildContentBlocks 流程中处理
  return blocks
}


/**
 * 从 content 构建 block 列表（带 page/figure 锚点）
 */
function _buildContentBlocks(content, options = {}) {
  const blocks = []
  if (!content) return blocks

  const lines = content.split('\n')
  let currentPage = null
  let paragraphBuf = []

  const flushParagraph = () => {
    if (!paragraphBuf.length) return
    const text = paragraphBuf.join('\n').trim()
    if (text) {
      blocks.push({
        type: 'paragraph',
        content: text,
        page: currentPage,
      })
    }
    paragraphBuf = []
  }

  for (const line of lines) {
    const trimmed = line.trim()

    // [PAGE:N]
    const pageMatch = /\[(?:PAGE|Page|页)\s*[:：]?\s*(\d+)\s*\]?/i.exec(trimmed)
    if (pageMatch) {
      flushParagraph()
      currentPage = parseInt(pageMatch[1], 10)
      blocks.push({
        type: 'page_marker',
        content: currentPage,
        page: currentPage,
      })
      continue
    }

    // [FIGURE:N]
    const figureMatch = /\[FIGURE:([\d.a-zA-Z]+)\]/.exec(trimmed)
    if (figureMatch && trimmed === `[FIGURE:${figureMatch[1]}]`) {
      flushParagraph()
      blocks.push({
        type: 'figure_marker',
        content: figureMatch[1],
        page: currentPage,
      })
      continue
    }

    // [TABLE:N]
    const tableMatch = /\[TABLE:([\d.a-zA-Z]+)\]/.exec(trimmed)
    if (tableMatch && trimmed === `[TABLE:${tableMatch[1]}]`) {
      flushParagraph()
      blocks.push({
        type: 'figure_marker',
        content: `Table ${tableMatch[1]}`,
        kind: 'table',
        page: currentPage,
      })
      continue
    }

    // 空行：段落结束
    if (!trimmed) {
      flushParagraph()
      continue
    }

    paragraphBuf.push(line)
  }
  flushParagraph()

  return blocks
}


/**
 * 自动识别摘要（如果后端没返回 summary 也没 formatted_content）
 *
 * 起点：ABSTRACT / Abstract / 摘要
 * 终点（按优先级）：
 *   1. Keywords / KEYWORDS / 关键词
 *   2. 1. Introduction / Introduction / 引言
 *   3. Article info / Received
 *   4. [PAGE:N]
 *
 * 同时剥除摘要内的出版信息（Corresponding author / E-mail / Received / DOI 等）
 */
function _detectAbstractFromContent(content) {
  if (!content) return null
  const m = /(?:^|\n)\s*(?:abstract|摘要|内容摘要|文摘)\s*[:：]?\s*([\s\S]{20,3000}?)(?=\n\s*(?:keywords?|关键词|关键字|introduction|引言|1\s*\.?\s*Introduction|1\s*引言|1\s+引言|article\s+info|received|available\s+online|\[PAGE:))/i.exec(content)
  if (!m) return null
  let abstract = _cleanText(m[1])
  // 去掉开头的残留（"\]" 等）
  abstract = abstract.replace(/^[\s\]\}>]+/, '').trim()
  // 剥除出版信息行
  abstract = _stripPublicationInfo(abstract)
  return abstract
}

/**
 * 从摘要/正文段中剥除出版信息
 */
function _stripPublicationInfo(text) {
  if (!text) return ''
  const lines = String(text).split('\n')
  const keep = []
  const skipKeywords = [
    /^Corresponding\s+author/i,
    /^E-?mail\s+address/i,
    /^E-?mail\s*[:：]/i,
    /^Tel\.?\s*[:：]/i,
    /^ScienceDirect/i,
    /^journal\s+homepage/i,
    /^Contents?\s+lists?\s+available/i,
    /^Received\s+(?:in\s+revised\s+form\s+)?\d/i,
    /^Revised\s+\d/i,
    /^Accepted\s+\d/i,
    /^Available\s+online\s+\d/i,
    /^©\s*\d{4}/i,
    /^Copyright/i,
    /^\s*\[PAGE:\d+\]/i,
    /^https?:\/\/(?:dx\.)?doi\.org\//i,
    /^DOI\s*[:：]/i,
    // 期刊名 + 卷号 + 年份（J. Hazard. Mater. 513 (2026) 142456）
    /^[A-Z][a-z]+(?:\.\s*[A-Z][a-z]+)*\s+\d+\s*\(\d{4}\)\s*\d+/,
    // 学校/单位地址行
    /^a\s+School\s+of\s+/i,
    /^b\s+College\s+of\s+/i,
    /^c\s+State\s+Scientific/i,
    // "Graphical abstract" 孤立行
    /^Graphical\s+abstract\s*$/i,
    // Highlights 标题行
    /^Highlights?\s*$/i,
    // 作者名列表（3+ 人名用逗号分隔，含上标 a,b,c）
    /^[A-Z][a-z]+\s+[A-Z][a-z]+\s+[a-z](?:\s*,\s*[A-Z][a-z]+\s+[A-Z][a-z]+\s+[a-z]){2,}/,
    // 大学/学院全名行（中文/英文）
    /^(?:School|College|Institute|Department|University|Center|Centre|Laboratory)\s+of\s+/i,
    // "PR China" / "PR Ch" 等国家行
    /^PR\s+China/i,
    /^PR\s+Ch\s*$/i,
    // "a,*" 或 "b" 等作者上标标识行
    /^[a-z]\s*[*†‡§]?\s*$/,
    // blockquote 图描述残留
    /^>\s*(?:📊|📈|📉|🖼|🧪|⚗|🔬|🔍|💠)?\s*[*_]*\s*(?:图表说明|Figure\s+caption|Table\s+caption|Caption|图表描述)/i,
  ]
  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) {
      keep.push(line)
      continue
    }
    if (skipKeywords.some(re => re.test(trimmed))) {
      continue
    }
    keep.push(line)
  }
  return keep.join('\n').replace(/\n{3,}/g, '\n\n').trim()
}

function _detectKeywordsFromContent(content) {
  if (!content) return []
  // 多行匹配：Keywords: 后到下一个空行（≥2 个 \n）或章节标题前
  // 停止词：Introduction / 引言 / Article info / Received / ABSTRACT / Highlights
  const m = /(?:^|\n)\s*(?:keywords?|关键词|关键字)\s*[:：]?\s*([\s\S]{3,800}?)(?=\n\s*(?:introduction|引言|1\s*\.?\s*Introduction|1\s*引言|article\s+info|received|available\s+online|abstract|摘要|highlights|亮点|\[PAGE:))/i.exec(content)
  if (!m) return []
  // 截到第一个空行（避免抓过整个 abstract 段）
  const firstParagraph = m[1].split(/\n\s*\n/)[0] || m[1]
  return firstParagraph.split(/[,;，；、\n]/).map(s => s.trim()).filter(Boolean).slice(0, 20)
}


/**
 * 关联图与图注
 *
 * 策略：
 * 1. 优先用 extractions[].data.caption 作为图注
 * 2. 否则在 content 文本中按 fig_idx 找 "Fig. 1" 后 1-3 句作为图注候选
 *
 * @param {Array} figures - 后端返回的 images 适配列表
 * @param {Array} extractions - 后端返回的 extractions 适配列表
 * @param {string} content - 原始正文
 * @returns {Array<{...figure, caption: string|null, figureNo: string|null}>}
 */
export function matchFiguresWithCaptions(figures, extractions, content) {
  if (!Array.isArray(figures)) return []

  // 1. 从 extractions 找 caption
  const captionsByFigureId = {}
  if (Array.isArray(extractions)) {
    for (const ex of extractions) {
      if (!ex?.data) continue
      if (ex.kind === 'image_block' && ex.data?.caption) {
        const sid = ex.sourceImageId || ex.data?.source_image_id
        if (sid) captionsByFigureId[sid] = ex.data.caption
      }
      // chart 也可能含图描述
      if (ex.kind === 'chart' && ex.data?.caption) {
        const sid = ex.sourceImageId || ex.data?.source_image_id
        if (sid) captionsByFigureId[sid] = ex.data.caption
      }
    }
  }

  // 2. 从 content 找 "Fig. N" / "Figure N" / "图 N" 后 1-3 句
  const captionsByFigIdx = _scanFigCaptionsInContent(content)

  // 3. 给每个 figure 分配 caption
  return figures.map((fig, idx) => {
    // 优先按 fig idx 在 content 里找（fig.id 通常是 DB 顺序，idx+1 对应正文"图 N"）
    const figIdx = idx + 1
    let caption = captionsByFigureId[fig.imageId || fig.id] || null
    if (!caption && captionsByFigIdx[figIdx]) {
      caption = captionsByFigIdx[figIdx]
    }
    return {
      ...fig,
      caption,
      figureNo: `Fig. ${figIdx}`,
    }
  })
}

/**
 * 在 content 文本中扫描 "Fig. N" / "Figure N" / "图 N" 后 1-3 句作为图注
 * @returns {Object<figIdx, caption>}
 */
function _scanFigCaptionsInContent(content) {
  if (!content) return {}
  const result = {}
  // 匹配 Fig. 1 / Figure 1 / 图 1 / 表 1 / Scheme 1 等
  // 中文 "图" / "表" 前后不是 word char，\b 不适用
  const figRefRe = /(?:Fig\.?|Figure|Scheme|图|表)\s*(\d{1,3})\b[.\s:：]?/gi
  let m
  while ((m = figRefRe.exec(content)) !== null) {
    const idx = parseInt(m[1], 10)
    if (!Number.isFinite(idx)) continue
    if (result[idx]) continue // 已记录过
    // 提取后续 200 字符作为图注候选
    const after = content.slice(m.index + m[0].length, m.index + m[0].length + 300)
    // 截到第一个换行 / 下一个 "Fig." / 中文/英文句号
    const stopMatch = after.match(/\n|\b(?:Fig\.?|Figure|Scheme)\s*\d|\.\s+[A-Z一-龥]/)
    const caption = (stopMatch ? after.slice(0, stopMatch.index) : after)
      .replace(/\s+/g, ' ')
      .trim()
      .replace(/^[.,;。：:]\s*/, '') // 去掉前导标点
      .slice(0, 280)
    if (caption && caption.length > 8) {
      result[idx] = caption
    }
  }
  return result
}

/**
 * 图片分类：cover/logo vs figure/chart/scheme
 *
 * @param {Object} image - { id, page, ocrText, width, height, ... }
 * @returns {{ kind: 'cover'|'logo'|'figure'|'table', label: string }}
 */
export function classifyImageKind(image) {
  if (!image) return { kind: 'figure', label: '图' }
  const text = (image.ocrText || '').toLowerCase()
  const url = (image.imageUrl || image.src || '').toLowerCase()
  const filename = (url.split('/').pop() || '').toLowerCase()

  // 1. 封面/出版信息识别
  const coverKeywords = [
    'elsevier', 'springer', 'wiley', 'copyright', '©', 'all rights reserved',
    'published by', 'journal of', 'contents', 'editorial board',
    'issn', 'isbn', 'doi.org/', 'sciencedirect',
  ]
  for (const kw of coverKeywords) {
    if (text.includes(kw) || filename.includes(kw.replace(/\s+/g, ''))) {
      return { kind: 'cover', label: '封面/出版' }
    }
  }

  // 2. Logo/装饰识别
  const logoKeywords = ['logo', 'brand', 'watermark']
  for (const kw of logoKeywords) {
    if (filename.includes(kw) || text.includes(kw)) {
      return { kind: 'logo', label: 'Logo' }
    }
  }

  // 3. 极小尺寸（< 50x50 或 < 5KB 且无 OCR）→ 装饰
  if (image.width && image.height && (image.width < 50 || image.height < 50)) {
    return { kind: 'logo', label: '装饰' }
  }

  // 4. 早期页码（cover 多在 P1） + 无 OCR 文本 + 大尺寸 → 可能是封面
  if (image.page === 1 && !text && image.width && image.height && image.width >= 800) {
    return { kind: 'cover', label: '封面' }
  }

  return { kind: 'figure', label: '图' }
}


/**
 * 构建右侧导航树
 *
 * 输出结构：
 * {
 *   sections: Array<{id, title, type, level, anchor}>,  // 论文章节
 *   modules: Array<{id, title, type, anchor, count}>     // 模块入口（图表/提取物/相关知识）
 * }
 */
export function buildAnchorTree(sections, options = {}) {
  if (!Array.isArray(sections)) return { sections: [], modules: [] }
  const { moduleCounts = {} } = options

  const sectionAnchors = sections
    .filter(s => s && s.title)
    .map(s => ({
      id: s.id,
      title: s.title,
      type: s.type,
      level: s.level || 1,
      anchor: `section-${s.id}`,
    }))

  // 模块入口：图表、提取物、相关知识
  const modules = []
  if (moduleCounts.figures) {
    modules.push({
      id: 'm-figures',
      title: `多模态提取 (${moduleCounts.figures})`,
      type: 'module',
      anchor: 'paper-extractions',
      count: moduleCounts.figures,
    })
  }
  if (moduleCounts.related) {
    modules.push({
      id: 'm-related',
      title: `相关知识 (${moduleCounts.related})`,
      type: 'module',
      anchor: 'paper-related',
      count: moduleCounts.related,
    })
  }

  return { sections: sectionAnchors, modules }
}


/**
 * 自动链接 DOI / URL / 邮箱
 * @returns {string} HTML 字符串（已转义）
 */
export function autoLinkContent(text) {
  if (!text) return ''
  let escaped = _escapeHtml(text)

  // 先修复重复 DOI 链接（避免下面 DOI_RE 重复添加前缀）
  escaped = escaped.replace(DOI_DUP_RE, 'https://doi.org/')
  escaped = escaped.replace(DOI_DUP_NOPROTO_RE, 'doi.org/')

  // 1. DOI URL 已有的（https://doi.org/10.xxx）→ 整体包成链接
  escaped = escaped.replace(
    /https?:\/\/(?:dx\.)?doi\.org\/(10\.\d{4,9}\/[-._;()\/:A-Z0-9]+)/gi,
    '<a class="auto-link doi-link" href="https://doi.org/$1">$1</a>'
  )
  // 2. 裸 DOI（未被 doi.org 包裹的）→ 加前缀
  //    负向 lookbehind：前面不是 doi.org/ 或 "doi.org/" 或已链接的
  escaped = escaped.replace(
    /(?<!doi\.org\/)(?<!href="https:\/\/doi\.org\/)\b(10\.\d{4,9}\/[-._;()\/:A-Z0-9]+)\b(?![^<]*<\/a>)/gi,
    '<a class="auto-link doi-link" href="https://doi.org/$1">$1</a>'
  )
  // 3. 非 DOI URL（跳过 doi.org / minio / 图片）
  escaped = escaped.replace(
    URL_RE,
    (m) => {
      if (IMG_EXT_RE.test(m) || /\/minio\//.test(m)) return m
      if (/doi\.org/i.test(m)) return m
      return `<a class="auto-link url-link" href="${m}" target="_blank" rel="noopener">${m}</a>`
    }
  )
  // 邮箱
  escaped = escaped.replace(
    EMAIL_RE,
    '<a class="auto-link email-link" href="mailto:$&">$&</a>'
  )
  return escaped
}


/**
 * 把后端 extractions 适配成 ExtractionItem 列表
 */
function _normalizeExtractions(extractions) {
  if (!Array.isArray(extractions)) return []
  return extractions.map(e => ({
    id: e.id,
    type: e.kind === 'image_block' ? 'image' : e.kind, // 'formula' | 'table' | 'chart' | 'image'
    kind: e.kind,
    page: e.page_number,
    pageNumber: e.page_number,
    figureNo: e.kind === 'chart' ? null : null, // 后端没存 figureNo，前端按 page+id 显示
    thumbnail: null, // 提取物本身没图，缩略图在 figures 里
    title: e.data?.caption || null,
    description: e.data?.description || e.data?.caption || e.content_text || '',
    contentText: e.content_text,
    confidence: e.confidence,
    modelUsed: e.model_used,
    data: e.data,
  }))
}

function _normalizeImages(images) {
  if (!Array.isArray(images)) return []
  return images.map(i => ({
    id: i.id,
    page: i.page_number,
    pageNumber: i.page_number,
    src: i.image_url,
    imageUrl: i.image_url,
    width: i.width,
    height: i.height,
    caption: null,
    ocrText: i.ocr_text,
    ocrStatus: i.ocr_status,
    ocrError: i.ocr_error,
    ocrModel: i.ocr_model,
  }))
}


/**
 * 主入口：把后端原始数据 + 多模态数据 → PaperDetail
 *
 * 流程：
 * 1. 选内容源（formatted_content > content）
 * 2. cleanContent 强力清洗（剥 HTML 属性 / 图片 URL / 系统标记 / 重复 DOI / PDF 页脚 / 字符间隔标题）
 * 3. 重新提取 [PAGE:N] / [FIGURE:N] 占位符
 * 4. parsePaperSections 拆章节
 * 5. 给每个 section 注入 page 标记
 * 6. 检测摘要 / 关键词（先取 raw.summary / raw.tags，再 fallback）
 * 7. matchFiguresWithCaptions 给图绑定 caption + figureNo
 * 8. classifyImageKind 给图分类 cover/logo/figure
 * 9. 收集 references / thumbnails / extractions
 * 10. 返回 PaperDetail
 *
 * @param {Object} raw - 后端 /knowledge/{id} 返回的 KnowledgeResponse
 * @param {Object} extra - 附加数据 { images, extractions, related }
 * @returns {Object} PaperDetail
 */
export function normalizePaperData(raw, extra = {}) {
  if (!raw) return null
  const images = _normalizeImages(extra.images)
  const extractions = _normalizeExtractions(extra.extractions)

  // 1. 选内容源
  //    formatted_content 仅在 LLM 真正排版过（包含 # ## 标题）时才视为 markdown
  //    否则即使有值也当 plain text 处理
  const rawContent = raw.content || ''
  const rawFormatted = raw.formatted_content || ''
  let hasFormatted = !!(rawFormatted.trim())
  // 检测 formatted 是否真排版：含 # 标题 或 与 content 长度差异 > 10%
  if (hasFormatted) {
    const sameLength = Math.abs(rawFormatted.length - rawContent.length) <= Math.max(20, rawContent.length * 0.1)
    const hasMdHeading = /(?:^|\n)#{1,4}\s+\S/.test(rawFormatted)
    if (sameLength && !hasMdHeading) {
      hasFormatted = false // 后端直接复制 content 到 formatted_content，当作 plain text
    }
  }
  const inputContent = hasFormatted ? rawFormatted : rawContent

  // 调试：dump 中间产物到 window
  if (typeof window !== 'undefined') {
    window.__PAPER_INTERMEDIATE__ = {
      rawContentLen: rawContent.length,
      rawFormattedLen: raw.formatted_content?.length || 0,
      hasFormatted,
      inputContentLen: inputContent.length,
      inputSample0: String(inputContent).slice(0, 800),
      inputSampleMid: String(inputContent).slice(8000, 8800),
    }
  }

  // 2. 强力清洗原始内容
  const cleaned = cleanContent(inputContent, {
    stripImageUrls: true,
    isMarkdown: hasFormatted,
  })
  const content = cleaned.content

  if (typeof window !== 'undefined') {
    window.__PAPER_INTERMEDIATE__.cleanedLen = content.length
    window.__PAPER_INTERMEDIATE__.cleanedSample0 = content.slice(0, 800)
    window.__PAPER_INTERMEDIATE__.cleanedSampleMid = content.slice(8000, 8800)
  }
  const extraFromClean = cleaned.extractedImages || []

  // 3. 提取页面/图表标记
  const pageMarkers = extractPageMarkers(content)
  const figureMarkers = extractFigureMarkers(content)

  // 4. 拆 section
  const isMd = hasFormatted
  let sections = parsePaperSections(content, { isMarkdown: isMd })

  // 兜底：markdown 解析若只产出 1 个 preamble section（说明实际不是 markdown），
  // 强制按 plain text 重新解析
  if (isMd && sections.length <= 1) {
    sections = parsePaperSections(content, { isMarkdown: false })
  }

  // 5. 给每个 section 注入 page 标记
  sections.forEach(section => {
    if (section.type === 'preamble') {
      // preamble 内部按 [PAGE:N] 拆 block
      section.blocks = _buildContentBlocks(section.blocks[0]?.content || '')
      return
    }
    let currentPage = null
    section.blocks = section.blocks.map(b => {
      if (b.type === 'page_marker') {
        currentPage = b.content
        return b
      }
      if (b.type === 'figure_marker') {
        return { ...b, page: currentPage }
      }
      return { ...b, page: currentPage }
    })
  })

  // 6. 检测摘要和关键词
  let abstract = raw.summary || null
  let keywords = Array.isArray(raw.tags) ? raw.tags.slice() : []

  if (!abstract && content) {
    abstract = _detectAbstractFromContent(content)
  }

  // 即使 abstract 来自后端 summary，也要 strip 出版信息
  if (abstract) {
    abstract = _stripPublicationInfo(abstract)
    abstract = abstract.replace(/^[\s\]\}>]+/, '').trim()
  }

  // 即使 abstract 来自后端 summary，也要 strip 出版信息
  if (abstract) {
    abstract = _stripPublicationInfo(abstract)
    abstract = abstract.replace(/^[\s\]\}>]+/, '').trim()
  }
  if (content && !keywords.length) {
    const detectedKw = _detectKeywordsFromContent(content)
    if (detectedKw.length) keywords = detectedKw
  }

  // 7. 图表清单（带 caption + figureNo + 分类）
  const figuresRaw = images.map(img => ({
    id: `fig-${img.id}`,
    imageId: img.id,
    page: img.page,
    src: img.src,
    imageUrl: img.imageUrl,
    width: img.width,
    height: img.height,
    ocrText: img.ocrText,
    ocrStatus: img.ocrStatus,
    ocrError: img.ocrError,
    ocrModel: img.ocrModel,
    caption: null,
  }))
  const figures = matchFiguresWithCaptions(figuresRaw, extractions, content)
    .map(fig => {
      const cls = classifyImageKind(fig)
      return { ...fig, kind: cls.kind, label: cls.label }
    })

  // 7.5 补充从 cleanContent 抽出的图片（如果后端 images 为空，但正文中出现了图片 URL）
  if (extraFromClean.length && figuresRaw.length === 0) {
    for (const img of extraFromClean) {
      const cls = classifyImageKind({ src: img.url, ocrText: img.alt })
      figures.push({
        id: `ext-${_genId('i')}`,
        imageId: null,
        page: null,
        src: img.url,
        imageUrl: img.url,
        width: null,
        height: null,
        ocrText: img.alt,
        ocrStatus: 'pending',
        caption: img.alt || null,
        figureNo: null,
        kind: cls.kind,
        label: cls.label,
      })
    }
  }

  // 8. 参考文献 section
  const referencesSection = sections.find(s => s.type === 'references')
  let references = []
  if (referencesSection) {
    const refText = referencesSection.blocks
      .filter(b => b.type === 'paragraph')
      .map(b => b.content)
      .join('\n')
    references = splitReferences(refText)
  }

  // 9. 缩略图（来自 extractions 中的 chart/table/formula 类型）
  const thumbnails = extractions
    .filter(e => e.kind === 'chart' || e.kind === 'table' || e.kind === 'formula')
    .map(e => ({
      id: e.id,
      type: e.type,
      kind: e.kind,
      page: e.page,
      title: e.title || e.description?.slice(0, 50),
      description: e.description,
      confidence: e.confidence,
      data: e.data,
      contentText: e.contentText,
    }))

  // 10. 统计核心图（非 cover/logo）数量
  const coreFigureCount = figures.filter(f => f.kind === 'figure').length

  // 11. 返回 PaperDetail
  return {
    id: raw.id,
    title: raw.title || '（无标题）',
    fileName: raw.file_name || null,
    fileType: raw.file_type || null,
    filePath: raw.file_path || null,
    status: raw.analysis_status || 'pending',
    uploadTime: raw.created_at || null,
    updatedAt: raw.updated_at || null,
    tags: keywords,
    category: raw.category || null,
    knowledgeType: raw.knowledge_type || null,
    summary: abstract,
    abstract,
    keywords,
    authors: [],
    journal: null,
    doi: null,
    sections,
    figures,
    tables: extractions.filter(e => e.kind === 'table'),
    formulas: extractions.filter(e => e.kind === 'formula'),
    extractions: thumbnails,
    relatedKnowledge: Array.isArray(extra.related) ? extra.related : [],
    references,
    pageMarkers,
    figureMarkers,
    coreFigureCount,
    // 透传原数据（兼容老代码）
    raw,
    // 元信息
    needsReview: !!raw.needs_review,
    autoResearched: !!raw.auto_researched,
    qualityScore: raw.quality_score || null,
    entities: Array.isArray(raw.entities) ? raw.entities : [],
    keyConcepts: Array.isArray(raw.key_concepts) ? raw.key_concepts : [],
    relatedTopics: Array.isArray(raw.related_topics) ? raw.related_topics : [],
    isChineseHeavy: _isChineseHeavy(content),
  }
}


/**
 * 把 section 列表的 type 字段标准化为前端的视图分类
 */
export function classifySectionType(section) {
  if (!section) return 'normal'
  return section.type || 'normal'
}


export default {
  normalizePaperData,
  parsePaperSections,
  extractPageMarkers,
  extractFigureMarkers,
  extractTableMarkers,
  matchFiguresWithCaptions,
  buildAnchorTree,
  splitReferences,
  autoLinkContent,
  classifySectionType,
  classifyImageKind,
  cleanContent,
}
