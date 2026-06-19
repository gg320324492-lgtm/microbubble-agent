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

// 章节标题关键词（中英文，支持变体）
const SECTION_KEYWORDS = [
  { type: 'abstract', regex: /^(abstract|summary|摘要|内容摘要|文摘)\s*[:：]?\s*$/i },
  { type: 'keywords', regex: /^(keywords?|key\s*words?|关键词|关键字)\s*[:：]?\s*$/i },
  { type: 'introduction', regex: /^(introduction|引言|前言|绪论|序言)\s*[:：]?/i },
  { type: 'background', regex: /^(background|研究背景|问题背景)\s*[:：]?/i },
  { type: 'methods', regex: /^(method(s|ology)?|materials?\s+and\s+method(s|ology)?|experimental(\s+(section|methods?))?|材料与方法|实验方法|实验部分|方法|实验材料与方法|2\.\s*Experimental)\s*[:：]?/i },
  { type: 'results', regex: /^(results?(\s+and\s+discussion)?|结果(与讨论|和分析)?|实验结果|结果与讨论)\s*[:：]?/i },
  { type: 'discussion', regex: /^(discussion|讨论|分析与讨论)\s*[:：]?/i },
  { type: 'conclusion', regex: /^(conclusions?|总结|结论|结语|小结)\s*[:：]?/i },
  { type: 'acknowledgments', regex: /^(acknowledg(e)?ments?|致谢|鸣谢)\s*[:：]?/i },
  { type: 'references', regex: /^(references?|bibliography|参考文献|引用文献)\s*[:：]?/i },
  { type: 'supplementary', regex: /^(supporting\s+information|supplementary\s+(material|information|content)|附录|补充材料|补充信息)\s*[:：]?/i },
  { type: 'appendix', regex: /^(appendix|附录)\s*[:：]?/i },
]

// 编号章节模式（带或不带点）—— 只匹配前导编号 + 空白，不吞标题
const NUMBERED_SECTION_RE = /^\s*(\d+(?:\.\d+){0,3})\.?\s+/

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

// 链接识别
const DOI_RE = /\b(10\.\d{4,9}\/[-._;()\/:A-Z0-9]+)\b/gi
const URL_RE = /\bhttps?:\/\/[^\s<>"')]+/g
const EMAIL_RE = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z]{2,}\b/gi

// 引用模式：参考文献条目通常以 [1] / 1. / (Smith 2020) 开头
const REFERENCE_ENTRY_RE = /^\s*(?:\[\d+\]|\(\d+\)|\d+\.)\s+[A-Z一-龥]/


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
    .replace(/ /g, ' ')
    // 合并连续空行（≥3 个换行 → 2 个）
    .replace(/\n{3,}/g, '\n\n')
    // 去除行尾空格
    .replace(/[ \t]+\n/g, '\n')
    // 合并 OCR 异常断行：中文字符后被强行换行 + 下一行也是中文字符
    .replace(/([一-龥，。：；！？、])\n([一-龥])/g, '$1$2')
    .trim()
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
        current = {
          id: _genId('s'),
          title: trimmed.replace(/[:：]\s*$/, ''),
          level: match.level,
          type: match.type,
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

  // preamble 单独成一个 section（一般含标题、作者、摘要）
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

  return sections
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
 */
function _detectAbstractFromContent(content) {
  if (!content) return null
  // 摘要 20~2000 字符（中英文都兼容；中文摘要通常较短）
  const m = /(?:^|\n)\s*(?:abstract|摘要|内容摘要|文摘)\s*[:：]?\s*([\s\S]{20,2000}?)(?=\n\s*(?:keywords?|关键词|关键字|introduction|引言|1\s*\.?\s*Introduction|1\s*引言|1\s+引言))/i.exec(content)
  if (m) return _cleanText(m[1])
  return null
}

function _detectKeywordsFromContent(content) {
  if (!content) return []
  const m = /(?:^|\n)\s*(?:keywords?|关键词|关键字)\s*[:：]?\s*([^\n]{3,400})/i.exec(content)
  if (!m) return []
  return m[1].split(/[,;，；、]/).map(s => s.trim()).filter(Boolean).slice(0, 20)
}


/**
 * 关联图与图注
 *
 * 策略：
 * 1. 如果后端有 extractions（带 source_image_id），优先用这个关联
 * 2. 否则按出现顺序相邻匹配：
 *    - [FIGURE:N] 占位符 → 紧跟其后的 caption 文本
 *    - "Fig. 1" / "Figure 1" 关键词 → 同一段落或下一段作为 caption
 */
export function matchFiguresWithCaptions(figures, captions, textBlocks) {
  // 简单实现：保留 figures 原顺序，把 captions 按出现顺序附给对应图
  const result = figures.map((fig, i) => ({
    ...fig,
    caption: captions[i] || null,
  }))
  return result
}


/**
 * 构建右侧导航树
 * @returns {Array<{ id, title, type, level, anchor }>}
 */
export function buildAnchorTree(sections) {
  if (!Array.isArray(sections)) return []
  return sections
    .filter(s => s && s.title)
    .map(s => ({
      id: s.id,
      title: s.title,
      type: s.type,
      level: s.level || 1,
      anchor: `section-${s.id}`,
    }))
}


/**
 * 自动链接 DOI / URL / 邮箱
 * @returns {string} HTML 字符串（已转义）
 */
export function autoLinkContent(text) {
  if (!text) return ''
  let escaped = _escapeHtml(text)
  // DOI
  escaped = escaped.replace(
    DOI_RE,
    '<a class="auto-link doi-link" href="https://doi.org/$1" target="_blank" rel="noopener">$1</a>'
  )
  // URL
  escaped = escaped.replace(
    URL_RE,
    '<a class="auto-link url-link" href="$&" target="_blank" rel="noopener">$&</a>'
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
 * @param {Object} raw - 后端 /knowledge/{id} 返回的 KnowledgeResponse
 * @param {Object} extra - 附加数据 { images, extractions, related }
 * @returns {Object} PaperDetail
 */
export function normalizePaperData(raw, extra = {}) {
  if (!raw) return null
  const images = _normalizeImages(extra.images)
  const extractions = _normalizeExtractions(extra.extractions)

  // 1. 选内容源：优先 formatted_content（LLM 排版过的 markdown），其次 content
  const hasFormatted = !!(raw.formatted_content && raw.formatted_content.trim())
  const rawContent = raw.content || ''
  const content = hasFormatted ? raw.formatted_content : rawContent

  // 2. 提取页面/图表标记
  const pageMarkers = extractPageMarkers(content)
  const figureMarkers = extractFigureMarkers(content)

  // 3. 拆 section
  const isMd = hasFormatted
  const sections = parsePaperSections(content, { isMarkdown: isMd })

  // 4. 给每个 section 注入 page 标记和 block 列表
  sections.forEach(section => {
    if (section.type === 'preamble') {
      // preamble 内部按 [PAGE:N] 拆 block
      section.blocks = _buildContentBlocks(section.blocks[0]?.content || '')
      return
    }
    // 已有 blocks（从 markdown 来的）：给每个 block 标记 page
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

  // 5. 检测摘要和关键词
  let abstract = raw.summary || null
  let keywords = Array.isArray(raw.tags) ? raw.tags.slice() : []

  if (!abstract && rawContent) {
    abstract = _detectAbstractFromContent(rawContent)
  }
  if (rawContent && !keywords.length) {
    const detectedKw = _detectKeywordsFromContent(rawContent)
    if (detectedKw.length) keywords = detectedKw
  }

  // 6. 图表清单
  const figures = images.map(img => ({
    id: `fig-${img.id}`,
    imageId: img.id,
    page: img.page,
    src: img.src,
    width: img.width,
    height: img.height,
    ocrText: img.ocrText,
    ocrStatus: img.ocrStatus,
    caption: null, // 后端没存 caption，前端从内容上下文推断
  }))

  // 7. 参考文献 section
  const referencesSection = sections.find(s => s.type === 'references')
  let references = []
  if (referencesSection) {
    const refText = referencesSection.blocks
      .filter(b => b.type === 'paragraph')
      .map(b => b.content)
      .join('\n')
    references = splitReferences(refText)
  }

  // 8. 缩略图（来自 extractions 中的 chart 类型）
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

  // 9. 返回 PaperDetail
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
}
