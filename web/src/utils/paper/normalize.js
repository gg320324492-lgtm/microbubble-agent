// 主入口 normalizePaperData + vision layout 归一（唯一 import chemFormat 的段）。
import { _genId, _isChineseHeavy } from './constants'
import {
  cleanContent, removeFrontMatter, extractPageMarkers,
  extractFigureMarkers, extractTableMarkers, _matchSectionTitle,
} from './content'
import { parsePaperSections, splitReferences, _buildContentBlocks,
  _splitOversizedParagraphs, _mergeOCRSoftLineBreaks,
  _detectAbstractFromContent, _stripPublicationInfo,
  _cleanChineseFromEnglish, _cleanParagraphHeavy } from './sections'
import {
  matchFiguresWithCaptions, classifyImageKind, buildAnchorTree,
  autoLinkContent, _buildFigureRegistry, _buildInlineFigureAnchors,
  _buildInlineFigureMap, _detectKeywordsFromContent,
  _extractAuthorsAndJournal, _translateKeywordsToEnglish,
} from './figures'
import { _tryExtractQA, _cleanQAAnswer, _buildQAPaperDetail } from './qa'
import { formatScientificText } from '../chemFormat'

function _normalizeExtractions(extractions) {
  if (!Array.isArray(extractions)) return []
  return extractions.map(e => ({
    id: e.id,
    type: e.kind === 'image_block' ? 'image' : e.kind,
    kind: e.kind,
    page: e.page_number,
    pageNumber: e.page_number,
    // ⚠ 关键: 保留 source_image_id 字段（用于 paperAdapter._buildFigureRegistry 关联 image）
    sourceImageId: e.source_image_id ?? e.sourceImageId ?? null,
    source_image_id: e.source_image_id ?? null,
    figureNo: e.kind === 'chart' ? null : null,
    thumbnail: null,
    title: e.data?.caption || null,
    description: e.data?.description || e.data?.caption || e.content_text || '',
    contentText: e.content_text,
    confidence: e.confidence,
    modelUsed: e.model_used,
    data: e.data,
  }))
}

/**
 * W86 mini-6 fix: 按 predicate / subject 关键词派生节点 category, 避免
 *   `n.category || n.type || n.group || 'default'` 全部 fallback 到 'default'
 *   导致 ECharts categories 只 1 项 → 所有节点同色 (全蓝)。
 *
 * 5 类 category (按 entity.subject 关键词匹配):
 *   - equipment  : 设备 (反应器/泵/塔/仪/罐/池/管)
 *   - method     : 方法 (法/反应/工艺/合成/处理/循环/沉积/降解/氧化/还原/吸附/分离/过滤)
 *   - parameter  : 参数 (pH/温度/压力/浓度/强度/率/势/值/度)
 *   - substance  : 物质 (溶液/气体/泡/粒子/膜/盐/酸/碱/试剂/水/氧/氢/臭氧/MNB)
 *   - concept    : 概念 (兜底)
 *
 * 优先级顺序很重要 (派工 v6 §1.2 真验证):
 *   equipment > method > parameter > substance > concept
 *   "反应器" 同时含 "反应" (method) 和 "反应器" (equipment), 优先 equipment
 *   "溶液pH" 同时含 "液" (substance) 和 "pH" (parameter), 优先 parameter
 *   "臭氧氧化法" 含 "氧" (substance) 但优先 method
 *   "微纳米气泡" 含 "泡" (substance) → substance
 */
const EQUIPMENT_RE  = /反应器|泵|塔|仪|罐|池|管|阀|炉|柱|reactor|pump|instrument|column|tank|valve|furnace|spectrometer|chromatograph|membrane\s*module/i
const METHOD_RE     = /法|反应|工艺|合成|处理|循环|沉积|浸解|破碎|降解|氧化|还原|吸附|分离|过滤|coagulation|flocculation|degradation|oxidation|reduction|adsorption|filtration|reaction|synthesis|process|method|technique|recirculation/i
const PARAMETER_RE  = /pH|ppm|浓度|强度|温度|压力|流速|流量|直径|粒径|电压|电流|效率|产率|回收率|数值|幅度|范围|potential|voltage|current|dosage|concentration|intensity|temperature|pressure|rate|velocity/i
const SUBSTANCE_RE  = /液|气体|泡|粒子|膜|盐|酸|碱|试剂|水|氧|氢|臭氧|MNB|MNBs|微(?:纳)?气泡|nano|micro|bubble|particle|film|membrane|electrode|catalyst|salt|acid|base|reagent|water|oxygen|hydrogen|ozone/i

function _getCategoryFromSubject(subject) {
  const s = String(subject || '')
  // 优先级: equipment > method > parameter > substance > concept
  // 关键: equipment "反应器" 必须在 method "反应" 之前匹配 (具体优先于泛化)
  if (EQUIPMENT_RE.test(s)) return 'equipment'
  if (METHOD_RE.test(s)) return 'method'
  if (PARAMETER_RE.test(s)) return 'parameter'
  if (SUBSTANCE_RE.test(s)) return 'substance'
  return 'concept'
}

/**
 * 5 类 category 颜色映射 (ECharts 系列 palette).
 * 顺序: substance (物质-红) / method (方法-青) / parameter (参数-黄)
 *        equipment (设备-浅绿) / concept (概念-浅蓝)
 */
const CATEGORY_COLORS = {
  substance:  '#FF6B6B',
  method:     '#4ECDC4',
  parameter:  '#FFE66D',
  equipment:  '#95E1D3',
  concept:    '#A8DADC',
}

/**
 * normalizeGraphData: 兼容后端多种图谱数据格式
 *
 * 兼容字段：
 *   节点: id / node_id / name / label / text / title
 *          value / weight / score / count
 *          category / type / group
 *   边:   source / from / source_id
 *          target / to / target_id
 *          label / relation / type
 *          weight / value
 *
 * 输出 ECharts 格式：
 *   { nodes: [{id, name, value, category, symbolSize}],
 *     links: [{source, target, value, label}],
 *     categories: [{name, itemStyle: {color}}] }
 *
 * W86 mini-6 fix: category 派生 (无 category 时按 subject 关键词分类) +
 *                颜色 palette (5 类固定颜色, 避免全蓝)
 *
 * @param {Object} rawGraphData - 后端返回的图谱数据
 * @returns {Object} ECharts 兼容的图谱数据
 */
function normalizeGraphData(rawGraphData) {
  if (!rawGraphData || typeof rawGraphData !== 'object') {
    return { nodes: [], links: [], categories: [], _status: 'no_data' }
  }

  // 1. 提取 nodes（兼容多种字段名）
  const rawNodes = rawGraphData.nodes || rawGraphData.Nodes ||
                   rawGraphData.entities || rawGraphData.vertices || []
  if (!Array.isArray(rawNodes) || !rawNodes.length) {
    return { nodes: [], links: [], categories: [], _status: 'no_data' }
  }

  // 2. 提取 edges/links（兼容多种字段名）
  const rawEdges = rawGraphData.edges || rawGraphData.links ||
                   rawGraphData.relations || rawGraphData.connections || []

  // 3. 限制最大节点数
  const MAX_NODES = 80
  const nodes = rawNodes.slice(0, MAX_NODES).map(n => {
    const id = String(n.id || n.node_id || n.name || n.label || n.title || n.text || n.subject || `node-${Math.random()}`)
    // W86 mini-5 fix: entity 图谱节点 (entity_service._entity_to_dict) 只有
    // subject / predicate / object 三元组字段, 没有 name / label / title / text,
    // 老代码 fallback 到 id → 用户看到节点标数字 (entity_id 1-65) 而非主体名称.
    // 通用展示字段优先 (兼容 paper / topic 图谱), 再落 entity 三元组, 最后才 id.
    const name = n.name || n.label || n.title || n.text ||
                 n.subject || n.object || n.predicate || id
    const value = Number(n.value ?? n.weight ?? n.score ?? n.count ?? 1)
    // W86 mini-6 fix: 老代码 `n.category || n.type || n.group || 'default'` 全部
    //   fallback 到 'default' (entity 三元组无 category 字段) → categories 只 1 项
    //   → 全蓝. 现在按 subject 关键词派生 category, 并加 explicit 'default' 兜底.
    const explicitCategory = n.category || n.type || n.group
    const category = explicitCategory && explicitCategory !== 'default'
      ? _getCategoryFromSubject(explicitCategory)  // 已分类的也走关键词校验
      : _getCategoryFromSubject(name)
    return {
      id,
      name: String(name).slice(0, 60),
      value,
      category,
      symbolSize: Math.min(50, 12 + value * 4),
    }
  })

  // 4. 过滤 edges：只保留 source/target 都在 nodes 里的
  const nodeIds = new Set(nodes.map(n => n.id))
  const links = (Array.isArray(rawEdges) ? rawEdges : []).map(e => {
    const source = String(e.source ?? e.from ?? e.source_id ?? '')
    const target = String(e.target ?? e.to ?? e.target_id ?? '')
    const value = Number(e.value ?? e.weight ?? 1)
    const label = e.label || e.relation || e.type || ''
    return { source, target, value, label }
  }).filter(e => nodeIds.has(e.source) && nodeIds.has(e.target))

  // 5. categories — W86 mini-6 fix: 含颜色 itemStyle, 仅输出实际用到的 5 类子集
  const usedCategories = new Set(nodes.map(n => n.category).filter(Boolean))
  const categories = Object.keys(CATEGORY_COLORS)
    .filter(name => usedCategories.has(name))
    .map(name => ({ name, itemStyle: { color: CATEGORY_COLORS[name] } }))

  return {
    nodes,
    links,
    categories,
    _status: nodes.length > 0 ? 'success' : 'no_data',
    _truncated: rawNodes.length > MAX_NODES,
    _totalNodes: rawNodes.length,
  }
}

/**
 * v28 step 21: 硬规则代码从 LLM 输出里剥除 figure caption
 *
 * 用户原话：「Fig. 2. Effects of oxidant supply... 不应该放在正文里面，
 * 而应该是在图片下面那个橙色的字体中显示出来，这段文字才是图片的真实信息」
 *
 * 背景：LLM 在重排论文时经常把图片 caption 文本（"Fig. 2. Effects of..." 段）
 * 当作正文段落输出。这是 LLM 的常见错误，**不能靠 prompt 修正**（CLAUDE.md 经验），
 * 必须由底层代码硬规则处理。
 *
 * 算法：
 * 1. 扫描 content 找 `![alt](image_url)` 模式（markdown image 已被 _resolve_figure_placeholders 替换成 URL）
 * 2. 紧跟 image 后 1-3 行内如有 `Fig. N. <caption text>` 模式 → 整段剥离
 * 3. 剥离的 caption 关联到对应 image（按 URL 后缀 → imageId 映射）
 * 4. 如果 caption 里有 figureNo，按该图号修正对应 fig 的 figureNo
 *
 * 输入：
 *   content: 已 cleanContent 处理过的字符串
 *   figuresRaw: normalizedImages 数组（含 imageId, imageUrl, figureNo, caption 等）
 *
 * 输出：
 *   { content: 剥除 caption 后的内容, captions: Map<imageId, captionText> }
 */
function _stripFigureCaptionsAndAssociate(content, figuresRaw) {
  if (!content || !Array.isArray(figuresRaw) || !figuresRaw.length) {
    return { content, captions: new Map() }
  }

  // 1. URL → imageId 映射（格式 1 用：markdown image 紧跟 caption）
  const urlToImage = new Map()
  for (const f of figuresRaw) {
    const url = f.imageUrl || f.src || ''
    if (!url) continue
    const lastSeg = url.split('/').pop() || ''
    if (lastSeg) urlToImage.set(lastSeg, f.imageId)
  }

  const captions = new Map()  // imageId → caption 文本
  let result = content

  // ── 格式 3: 纯文本长 caption（OCR 提取，无图片包装）──
  //    特征: 行首 Fig. N. <text> + 段长 > 100 + 含学术描述
  //    关联: 按 page 顺序分配到 core fig
  const coreFigs = figuresRaw.filter(f =>
    f.imageId && f.isCoreFigure !== false && !f.isPublisherImage
    && f.figureType !== 'cover' && f.figureType !== 'logo' && f.figureType !== 'publisher'
  ).sort((a, b) => (a.page || 9999) - (b.page || 9999))
  let coreFigCursor = 0

  // v28 step 23: 用 [\s\S]*? 非贪婪 + 必须包含下一个段边界
  //    之前 bug: 正则只匹配到第一个 . 后停，导致 'Fig. 2. Effects of' 后面 '(a) (b)' 漏掉
  const longCaptionRe = /(?:^|\n)((Fig\.|Figure|Scheme|Table)\s+(\d+)\.\s+[A-Z][\s\S]{0,8000}?)(?=\n\n|\n##\s|\n###\s|\Z)/g
  result = result.replace(longCaptionRe, (m, fullSeg, _prefix, _num) => {
    const seg = fullSeg.trim()
    if (seg.length < 100) return m
    // 必须含学术描述特征
    const isAcademic = /\(.\)|\bEffects of|\bImpact of|\bHeat map|\bSchematic|\bToluene|\bCatalytic|\bDegradation|\bConversion rate|\bMicro-nano|\binterfacial|\bO3-MNBs/i.test(seg)
    if (!isAcademic) return m
    while (coreFigCursor < coreFigs.length && captions.has(coreFigs[coreFigCursor].imageId)) {
      coreFigCursor++
    }
    if (coreFigCursor < coreFigs.length) {
      captions.set(coreFigs[coreFigCursor].imageId, seg)
      coreFigCursor++
      return m.startsWith('\n') ? '\n' : ''
    }
    return m
  })

  // ── 格式 2: blockquote 中文图注（OCR 原始格式）──
  result = result.replace(/(?:^|\n)((?:> [^\n]*\n)+)/g, (m, bq) => {
    if (!/(?:图表|图（\s*P|图\s*\(P|Figure|Fig\.|说明|描述)/.test(bq)) return m
    return m.startsWith('\n') ? '\n' : ''
  })

  // ── 格式 1: markdown image 紧跟 Fig. caption (LLM 重排后 formatted_content) ──
  const mdImageRe = /!\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g
  const imagePositions = []
  let scanned = result
  const TOKEN_PREFIX = ' FIGIMG'
  scanned = scanned.replace(mdImageRe, (m, alt, url) => {
    const lastSeg = url.split('/').pop() || ''
    const imageId = urlToImage.get(lastSeg)
    if (!imageId) return m
    const token = TOKEN_PREFIX + imageId + ' '
    imagePositions.push({ token, imageId, original: m })
    return token
  })

  for (const { token, imageId, original } of imagePositions) {
    const tokenIdx = scanned.indexOf(token)
    if (tokenIdx < 0) continue
    const after = scanned.slice(tokenIdx + token.length)
    const captionMatch = after.match(/^([\s\S]{0,5000}?)(\n\n|\n##\s|\n###\s|\n\*\*[A-Z]|\Z)/)
    if (!captionMatch) continue
    const before = captionMatch[1]
    const firstLine = before.split('\n').find(l => l.trim()) || ''
    const isCaption = /Fig\.?|Figure|Scheme|Table/i.test(firstLine)
    if (!isCaption) continue

    const lines = before.split('\n').slice(0, 12)
    let captionText = lines.join('\n').trim()
      .replace(/^[>＞]\s*/gm, '')
      .replace(/\*\*/g, '')
      .trim()

    if (captionText.length > 10 && !captions.has(imageId)) {
      captions.set(imageId, captionText)
      const tokenEnd = tokenIdx + token.length
      const beforeText = scanned.slice(0, tokenEnd)
      const afterRemoved = scanned.slice(tokenEnd + before.length)
      scanned = beforeText + afterRemoved
    }
  }

  for (const { token, original } of imagePositions) {
    scanned = scanned.replace(token, original)
  }

  return { content: scanned, captions }
}

/**
 * v28 step 21: 用正文首次出现的 "Fig. N" 模式修正 fig.figureNo
 *
 * 用户原话：「多模态中的图片命名与正文中相同一张图片的命名不一致，
 * 比如多模态的 fig7，在正文的 3.4 节当中，但是标题却是 fig1」
 *
 * 算法：
 * 1. 扫描 sections.blocks 找所有 "Fig. N" / "Figure N" 模式，记录 paragraphId → set(figureNo)
 * 2. 已有 fig.figureNo 的图片保留（vision model 输出的）
 * 3. 没 figureNo 但正文引用了 "Fig. N" 的图，按 page 顺序分配 N
 */
function _alignFigureNosWithText(content, figureRegistry) {
  if (!content || !Array.isArray(figureRegistry) || !figureRegistry.length) {
    return figureRegistry
  }

  // v28 step 26: 完全按 page 顺序重排 figureNo
  //    之前逻辑依赖 vision 输出的 figureNo + 正文引用数对不上时 L1/L2 错位
  //    现在统一: 1) 先按 page 升序排序, 2) 按 page 顺序给所有 core fig 分配 Fig. 1, 2, 3...
  //    3) 保留 vision 输出的"子号"(Fig. 5e / Fig. 3a 等有字母后缀) 保留
  const isCore = (f) => f.isCoreFigure === true
    || (f.isCoreFigure !== false
      && !f.isPublisherImage
      && !['cover', 'logo', 'publisher', 'unknown'].includes(f.figureType)
      && f.kind !== 'cover' && f.kind !== 'logo')
  // 仅对 core fig 重排
  const coreFigs = figureRegistry
    .filter(f => isCore(f))
    .sort((a, b) => (a.page || 9999) - (b.page || 9999))
  // 检查子号 (Fig. 5e) - 保留
  const subLetterRe = /^Fig\.\s*\d+[a-z]$/i
  let idx = 0
  for (const f of coreFigs) {
    idx += 1
    if (f.figureNo && subLetterRe.test(f.figureNo)) {
      // 子号图保留 vision 值 (用户视角 Fig. 5e 有意义)
      f.figureNoSource = 'vision'
      continue
    }
    // 重置为按 page 顺序的 Fig. N
    f.figureNo = `Fig. ${idx}`
    f.figureNoSource = 'page_aligned'
  }
  return figureRegistry
}


function _normalizeImages(images) {
  if (!Array.isArray(images)) return []
  return images.map(i => {
    // v28 step 109.1: 从 ocr_text 自动提取 caption 兜底（API caption 字段常为空）
    //   优先取首段连续英文/数字（典型 Fig. 1 caption 格式）
    let autoCaption = null
    if (i.ocr_text) {
      const m = i.ocr_text.match(/^[\s\S]{0,200}?((?:Fig\.?|Figure|Table|Scheme|S\.)\s*\d+[^\n]{0,150})/i)
      if (m) autoCaption = m[1].trim()
      else autoCaption = i.ocr_text.slice(0, 120).trim()
    }
    return {
      id: i.id,
      page: i.page_number,
      pageNumber: i.page_number,
      src: i.image_url,
      imageUrl: i.image_url,
      width: i.width,
      height: i.height,
      caption: autoCaption,
      ocrText: i.ocr_text,
      ocrStatus: i.ocr_status,
      ocrError: i.ocr_error,
      ocrModel: i.ocr_model,
      // ── v28 step 4: vision 模型输出的 12 个结构化字段（直接透传，不再推断） ──
      figureNo: i.figure_no ?? null,
      figureType: i.figure_type ?? null,
      isCoreFigure: i.is_core_figure ?? null,
      isPublisherImage: i.is_publisher_image ?? null,
      isSupportingFigure: i.is_supporting_figure ?? null,
      sectionHint: i.section_hint ?? null,
      visualSummary: i.visual_summary ?? null,
      anchorParagraphIndex: i.anchor_paragraph_index ?? null,
      anchorText: i.anchor_text ?? null,
      visionConfidence: i.vision_confidence ?? null,
      visionModelUsed: i.vision_model_used ?? null,
      visionAnalyzedAt: i.vision_analyzed_at ?? null,
    }
  })
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
function normalizePaperData(raw, extra = {}) {
  if (!raw) return null
  const images = _normalizeImages(extra.images)
  const extractions = _normalizeExtractions(extra.extractions)

  // v28 step 105: 如果有 vision layout（vision model 扫描整篇论文的 layout 数据），
  //   直接用 layout 重建 sections + blocks（不依赖 regex 推断）
  //   vision 真正"看"了整篇论文，输出每页的 heading/paragraph/image/table/formula 顺序
  const visionLayout = extra.visionLayout
  if (visionLayout && visionLayout.page_layout && visionLayout.page_layout.length > 0) {
    const fromLayout = _buildPaperFromVisionLayout(raw, visionLayout, images, extractions, extra.related || [])
    if (fromLayout) {
      return fromLayout
    }
    // layout 解析失败时 fallback 到原 regex 路径
  }

  // 1. 选内容源
  //    formatted_content 仅在 LLM 真正排版过（包含 # ## 标题）时才视为 markdown
  //    否则即使有值也当 plain text 处理
  const rawContent = raw.content || ''
  const rawFormatted = raw.formatted_content || ''
  let hasFormatted = !!(rawFormatted.trim())
  // 检测 formatted 是否真排版：
  //   v28 fix (反向判断): 含 [PAGE:N] 标记 = OCR 提取的内容（不是 LLM 真排版）,
  //   应该走 plain text 路径。但 plain text parser 对 rawFormatted 失效
  //   (rawFormatted 是混合格式: OCR 文本 + 注入的 markdown 标题,
  //    plain text parser 不识别 ## 标题但 rawContent 才是纯 OCR 文本)
  //   → 用 rawContent 走 plain text 路径
  if (hasFormatted) {
    const sameLength = Math.abs(rawFormatted.length - rawContent.length) <= Math.max(20, rawContent.length * 0.1)
    const hasMdHeading = /(?:^|\n)#{1,4}\s+\S/.test(rawFormatted)
    const hasPageMarker = /\[PAGE:\s*\d+\s*\]/i.test(rawFormatted)
    // v28 step 91: 含 [PAGE:N] 标记说明 formatted_content 是 OCR 文本 + 注入的伪 markdown
    //   （多模态提取的 "## 多模态提取" 等）→ 不是真正 LLM 排版的章节结构
    //   这种情况必须走 rawContent 路径，让 cleanContent 完整处理 OCR 残留
    //   （Journal Pre-proof / P33-39 / 该图由 等）
    if (hasPageMarker) {
      hasFormatted = false
    } else if (sameLength && !hasMdHeading) {
      hasFormatted = false
    }
  }
  const inputContent = hasFormatted ? rawFormatted : rawContent

  // v28 step 82: 强力剥离 front matter (Reference / boilerplate / Title / Authors / Affiliations / Abstract)
  //   真实 PDF 的 [PAGE:1] 之前 / Introduction 之前都是元信息（Elsevier 版权 + 作者 + 单位 + abstract）
  //   这些应该全部剥除（abstract 单独抽出作为 paper.abstract 字段）
  //   否则 step 76 的 `Reference` 正则会把元信息里的 "Reference: CEJ 171737" 转成 "## References\n"
  //   出现在文章开头（用户看到的 "Reference P2 参考文献（共 1 条） 展开全部"）
  // 策略：仅当 Introduction 之前确实有 front matter 时才剥（避免误删正文短文档）
  const fmResult = removeFrontMatter(inputContent)
  let frontMatterAbstract = fmResult.abstract
  let frontMatterKeywords = fmResult.keywords
  let useInputContent = fmResult.hasFrontMatter && fmResult.cleaned ? fmResult.cleaned : inputContent

  // v28 step 71: QA 库格式检测 + 早返回（不走常规 paper section 解析）
  // 早期 [拓展-XXX] LLM 自动入库的条目都是 `## 问题\n...\n## 回答\n...` 格式
  // 强制构造为 Q&A section，避免被切成 30+ 个碎 paragraph
  const qa = _tryExtractQA(useInputContent)
  if (qa) {
    const cleanedAnswer = _cleanQAAnswer(qa.answer)
    return _buildQAPaperDetail(raw, qa.question, cleanedAnswer, extra)
  }

  // 中间语言判断（用于后续中文污染过滤）
  const isEnglishPaper = !_isChineseHeavy(useInputContent)

  // 调试：dump 中间产物到 window
  if (typeof window !== 'undefined') {
    window.__PAPER_INTERMEDIATE__ = {
      rawContentLen: rawContent.length,
      rawFormattedLen: raw.formatted_content?.length || 0,
      hasFormatted,
      inputContentLen: useInputContent.length,
      inputSample0: String(useInputContent).slice(0, 800),
      inputSampleMid: String(useInputContent).slice(8000, 8800),
      frontMatterStripped: fmResult.hasFrontMatter,
      frontMatterLen: fmResult.frontMatter?.length || 0,
    }
  }

  // 2. 强力清洗原始内容
  const cleaned = cleanContent(useInputContent, {
    stripImageUrls: true,
    isMarkdown: hasFormatted,
  })
  let content = cleaned.content

  // v28 step 21: 硬规则从正文剥除 "Fig. N. <caption>" 段（v28 step 21）
  //    LLM 经常把图注文本塞进正文，必须由代码硬剥除，不依赖 LLM 自觉
  //    images 此时还没 normalize 完，先做基础 URL→id 映射
  const _tempImagesForStrip = (extra.images || []).map(i => ({
    imageId: i.id,
    imageUrl: i.image_url,
  }))
  const stripResult = _stripFigureCaptionsAndAssociate(content, _tempImagesForStrip)
  content = stripResult.content
  // captions: imageId → caption 文本（后续 fig 注入 caption 用）

  if (typeof window !== 'undefined') {
    window.__PAPER_INTERMEDIATE__.cleanedLen = content.length
    window.__PAPER_INTERMEDIATE__.cleanedSample0 = content.slice(0, 800)
    window.__PAPER_INTERMEDIATE__.cleanedSampleMid = content.slice(8000, 8800)
    window.__PAPER_INTERMEDIATE__.stripCaptionsCount = stripResult.captions.size
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
  //    v28 step 12 改进：plain text parser 内部已把 [PAGE:N] 提取为 page_marker block，
  //    这里只需要从 page_marker 继承 page 字段到后续 paragraph/figure_marker blocks
  sections.forEach(section => {
    if (section.type === 'preamble') {
      section.blocks = _buildContentBlocks(section.blocks[0]?.content || '')
    }
    // 所有 section：从 page_marker 继承 page
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

  // 5.5 v28 step 11: 把过长的 paragraph block 按句末 + 段起标志拆成多段
  //    PDF 文档的软换行让一个 paragraph block 实际包含整章连续文本，
  //    用户期望"按原文段落分段"，需要按句末 + 后续大写字母开头处断句
  _splitOversizedParagraphs(sections)

  // 5.6 v28 step 10: 对英文论文的 paragraph block 应用 chemFormat（Unicode 上下标）
  //    必须放在 _splitOversizedParagraphs 之后（避免先改字符数再 split 误判）
  if (!isEnglishPaper) {
    // 中文论文不需要 Unicode 上下标
  } else {
    sections.forEach(section => {
      if (!section.blocks) return
      section.blocks.forEach(b => {
        if (b.type !== 'paragraph' || !b.content) return
        b.content = formatScientificText(b.content)
      })
    })
  }

  // 6. 检测摘要和关键词
  let abstract = raw.summary || null
  let keywords = Array.isArray(raw.tags) ? raw.tags.slice() : []

  // v28 step 82: 优先用 front matter 抽出的 Abstract + Keywords（更准确）
  if (frontMatterAbstract && (!abstract || abstract.length < frontMatterAbstract.length * 0.5)) {
    abstract = frontMatterAbstract
  }
  if (frontMatterKeywords && frontMatterKeywords.length && !keywords.length) {
    keywords = frontMatterKeywords
  }

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

  // v28 step 109.39: abstract 字段也要走 formatScientificText
  //    否则 abstract 中的化学式/上下标/自由基符号（如 O₂⋅⁻、⋅OH、O₃-MNBs、H₂O₂）保留 OCR 原始字符，
  //    前端 AbstractCard 只调用 autoLinkContent（不做化学式格式化），导致 abstract 显示与正文不一致。
  //    apply to abstract before it goes to PaperHeader / AbstractCard
  if (abstract) {
    abstract = formatScientificText(abstract)
  }
  if (content && !keywords.length) {
    const detectedKw = _detectKeywordsFromContent(content)
    if (detectedKw.length) keywords = detectedKw
  }

  // v28 step 109.37: 关键词翻译成英文（数据库 tags 经常是中文，用户要求英文显示）
  //    - 已经英文的保持原样
  //    - 中文通过 KEYWORD_ZH_TO_EN 映射表翻译
  keywords = _translateKeywordsToEnglish(keywords)

  // 7. 图表清单（带 caption + figureNo + 分类）
  //    v28 step 14 修复：之前只复制 id/page/src 等原始字段，没传 vision 字段
  //    （figureNo/figureType/isCoreFigure/isPublisherImage/...）→ _buildFigureRegistry
  //    走 visionAvailable=false 兜底分支，isCoreFigure 推断错，导致 inlineFigureAnchors 为空
  //    v28 step 21: caption 优先用 _stripFigureCaptionsAndAssociate 从正文提取的（更准）
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
    // v28 step 21: 从正文剥除的 caption 优先（比 vision 输出的更准）
    //     兜底：vision model 的 caption (extData.caption)
    caption: stripResult.captions.get(img.id) || null,
    // v28 vision 12 字段（必须传递，否则 _buildFigureRegistry 推断错误）
    figureNo: img.figureNo ?? null,
    figureType: img.figureType ?? null,
    isCoreFigure: img.isCoreFigure ?? null,
    isPublisherImage: img.isPublisherImage ?? null,
    isSupportingFigure: img.isSupportingFigure ?? null,
    sectionHint: img.sectionHint ?? null,
    visualSummary: img.visualSummary ?? null,
    anchorParagraphIndex: img.anchorParagraphIndex ?? null,
    anchorText: img.anchorText ?? null,
    visionConfidence: img.visionConfidence ?? null,
    visionModelUsed: img.visionModelUsed ?? null,
    visionAnalyzedAt: img.visionAnalyzedAt ?? null,
  }))
  // 使用新的 _buildFigureRegistry 建立 figureRegistry（含 figureType / isCoreFigure / figureNo 等）
  const figureRegistry = _buildFigureRegistry(figuresRaw, extractions, content)

  // v28 step 21: 硬规则根据正文 "Fig. N" 引用修正 figureNo
  //    解决 "多模态的 fig7 在正文 3.4 节但标题是 fig1" 错位问题
  _alignFigureNosWithText(content, figureRegistry)
  // v28 step 27: 把对齐后的 figureNo 同步回 figuresRaw (供 ExtractionPanel 使用)
  //    之前 figuresRaw 保留 vision 原始 figureNo (530="Fig. 1", 536="Fig. 1" 重复),
  //    同步后 figuresRaw 顺序与 figureRegistry 一致
  for (const raw of figuresRaw) {
    const reg = figureRegistry.find(r => r.imageId === raw.imageId || r.id === raw.id)
    if (reg && reg.figureNo) {
      raw.figureNo = reg.figureNo
      raw.figureNoSource = reg.figureNoSource
    }
  }
  // 兼容旧 API：保留 figures 数组（供 ExtractionPanel / 文末图库使用）
  const figures = matchFiguresWithCaptions(figuresRaw, extractions, content)
    .map(fig => {
      const reg = figureRegistry.find(r => r.id === (fig.id || fig.imageId))
      const cls = classifyImageKind(fig)
      return {
        ...fig,
        kind: cls.kind,
        label: cls.label,
        figureType: reg?.figureType,
        isCoreFigure: reg?.isCoreFigure,
        isPublisherImage: reg?.isPublisherImage,
        figureNo: fig.figureNo || reg?.figureNo,
        semanticTitle: reg?.semanticTitle,
        sectionHint: reg?.sectionHint,
      }
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

  // 10. 英文论文正文中文污染过滤
  //     如果 isChineseHeavy = false（英文论文），删除 sections 中的中文污染行
  const isEnglish = !_isChineseHeavy(content)
  if (isEnglish) {
    for (const section of sections) {
      if (!section.blocks) continue
      section.blocks = section.blocks.map(b => {
        if (b.type !== 'paragraph') return b
        let cleaned = _cleanChineseFromEnglish(b.content)
        cleaned = _cleanParagraphHeavy(cleaned)  // v27.2 段落级深度清洗
        return { ...b, content: cleaned }
      }).filter(b => b.type !== 'paragraph' || (b.content && b.content.trim().length > 5))
    }
  }

  // 11. 构建正文内嵌图锚定 (v27 - paragraph 级)
  //     L1: 段落首次引用图号精确匹配
  //     L2: caption 关键词 ∩ paragraph 关键词 (Jaccard)
  //     只锚定 isCoreFigure=true 的图（cover/logo/publisher 永不进正文）
  const inlineFigureAnchors = _buildInlineFigureAnchors(sections, figureRegistry)
  // 兼容旧 API: section 级合并
  const inlineFigureMap = _buildInlineFigureMap(sections, figureRegistry, content)

  // 12. 统计核心图（非 cover/logo）数量
  const coreFigureCount = figures.filter(f => f.kind === 'figure').length

  // 13. 返回 PaperDetail
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
    // v28 step 109.38: 作者/期刊/DOI 从原文 content 提取
    ...(function () {
      const info = _extractAuthorsAndJournal(inputContent)
      return {
        authors: info.authors,
        affiliations: info.affiliations,
        journal: info.journal,
        doi: info.doi,
      }
    })(),
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
    figureRegistry,  // 完整图 registry（含 isCoreFigure / figureType / figureNo 等）
    figures,          // 兼容旧 API：含 kind/label/figureType/isCoreFigure 等
    inlineFigureMap,
    inlineFigureAnchors,  // v27 段落级锚定（按 paragraphId）
    // 透传原数据（兼容老代码）
    raw,
    // 元信息
    needsReview: !!raw.needs_review,
    autoResearched: !!raw.auto_researched,
    qualityScore: raw.quality_score || null,
    entities: Array.isArray(raw.entities) ? raw.entities : [],
    keyConcepts: Array.isArray(raw.key_concepts) ? raw.key_concepts : [],
    relatedTopics: Array.isArray(raw.related_topics) ? raw.related_topics : [],
    topic: raw.topic || null,  // v28 step 45: 透传 topic
    fileType: raw.file_type || null,  // v28 step 45: 透传 file_type
    isChineseHeavy: _isChineseHeavy(content),
  }

  return paperDetail
}


// ============================================================================
// v28 step 106: vision layout 后处理辅助函数
// ============================================================================

/**
 * 合并 vision layout 中重复的 page_number
 * vision 模型 page 计数可能不稳定，导致同一页出现多次（如 page 8 出现 5 次）
 * 按 page_number 分组，合并相同 page 的 blocks（按 order 排序拼接）
 * 取最长 blocks 列表作主，其他页的 blocks 补到末尾（按出现顺序）
 */
function _mergeVisionPagesByNumber(pages) {
  if (!pages || !pages.length) return []
  // v28 step 108.1: vision 对中文论文格式（封面+摘要+目录+正文都标 page 1）经常返回
  //   多个内容完全不同的"page N"。直接合并会把封面+摘要+章节正文塞到同一 page，
  //   导致导航混乱。
  //
  // 策略：
  // 1. 按 page_number 分组
  // 2. 对同一 page_number 的多份输出，计算 block-level Jaccard 相似度
  // 3. 相似度 ≥ 0.5 → 视为 vision 重复扫描同一页 → 合并 blocks（去重）
  // 4. 相似度 < 0.5 → 视为 vision 把不同页误标为同 page_number → 按数组顺序分配
  //    连续 page 号（page 1, page 1', page 1''...）
  const groupsByPn = new Map()
  for (const page of pages) {
    const pn = page.page_number ?? 0
    if (!groupsByPn.has(pn)) groupsByPn.set(pn, [])
    groupsByPn.get(pn).push(page)
  }

  const result = []
  for (const [pn, group] of Array.from(groupsByPn.entries()).sort((a, b) => a[0] - b[0])) {
    if (group.length === 1) {
      result.push({ page_number: pn, blocks: _dedupeBlocksInPage(group[0].blocks || []) })
      continue
    }
    // 多份同一 pn 的输出，计算两两 block 内容指纹 jaccard
    const fingerprints = group.map(p => _pageFingerprint(p.blocks || []))
    // 看是否能合并成一个（所有两两相似度 ≥ 0.5）
    let allSimilar = true
    for (let i = 0; i < fingerprints.length; i++) {
      for (let j = i + 1; j < fingerprints.length; j++) {
        if (_jaccardV2(fingerprints[i], fingerprints[j]) < 0.5) {
          allSimilar = false
          break
        }
      }
      if (!allSimilar) break
    }
    if (allSimilar) {
      // 真正重复扫描，合并去重
      const merged = []
      const seen = new Set()
      for (const p of group) {
        for (const b of (p.blocks || [])) {
          const key = _blockFingerprintV2(b)
          if (seen.has(key)) continue
          seen.add(key)
          merged.push(b)
        }
      }
      result.push({ page_number: pn, blocks: _dedupeBlocksInPage(merged) })
    } else {
      // vision 误标 page 边界：每份作为独立 page，page 号 = pn + 后缀 index
      group.forEach((p, idx) => {
        const pageNum = idx === 0 ? pn : `${pn}.${idx}`
        result.push({ page_number: pageNum, blocks: _dedupeBlocksInPage(p.blocks || []) })
      })
    }
  }
  // 最终按 page_number 排序（pn.1 < pn.10 < pn.2 用自然排序）
  return result.sort((a, b) => {
    const aKey = String(a.page_number)
    const bKey = String(b.page_number)
    const aNum = parseFloat(aKey)
    const bNum = parseFloat(bKey)
    if (aNum !== bNum) return aNum - bNum
    return aKey.localeCompare(bKey)
  })
}

function _pageFingerprint(blocks) {
  const set = new Set()
  for (const b of blocks) {
    set.add(_blockFingerprintV2(b))
  }
  return set
}

function _blockFingerprintV2(b) {
  if (!b) return ''
  if (b.type === 'image') {
    return `image|${b.figure_no || ''}|${(b.caption || '').slice(0, 80)}`
  }
  const text = (b.text || b.caption || b.content || '').slice(0, 80)
  return `${b.type}|${text}`
}

function _jaccardV2(setA, setB) {
  if (!setA.size && !setB.size) return 1
  let inter = 0
  for (const x of setA) if (setB.has(x)) inter++
  const union = setA.size + setB.size - inter
  return union ? inter / union : 0
}

function _dedupeBlocksInPage(blocks) {
  const seen = new Set()
  const out = []
  for (const b of blocks) {
    const key = _blockFingerprintV2(b)
    if (seen.has(key)) continue
    seen.add(key)
    out.push(b)
  }
  return out
}

/**
 * 检测 paragraph 文本是否含参考文献格式 [N] 作者...
 * 返回 true 表示此段是参考文献条目
 */
function _isReferenceParagraph(text) {
  if (!text) return false
  // 形如 "[1] Smith J., ... 2024." 或 "[16] Yu, J., Le, T., ..."
  // 关键特征：以 [数字] 开头
  return /^\s*\[\d+\]\s+[A-Z]/.test(text)
}

/**
 * v28 step 109.3: 检测 vision 误识的 TOC 条目
 *   目录里的章节标题被 vision 当 heading 输出，如 "1 绪论.................1"
 *   特征：含 3+ 个连续点 + 末尾页码 OR 仅页码（"50"/"52"）
 *   不能误杀：References 正文里的 "............" 真实引用不会出现在 heading
 *   也不能误杀：正常段落里的省略号"..."（如"中文摘要内容..."）
 */
/**
 * v28 step 109.25: 判断 vision OCR 拆错的两段是否应合并
 *   合并条件（满足任一即合并）：
 *     A. 上一段不以句末符号结尾 + 本段以小写字母/中文起始词开头（典型 soft break）
 *        例：'...that the' + 'conversion for CH₃SH...'
 *     B. 上一段末尾是未闭合的开括号 '(' 或 '[' → 括号内接续（大写数字/缩写也算）
 *        例：'...analyzer (Malvern Panalytical' + 'ZS₉₀), and the bubble size...'
 *     C. 上一段末尾是连字符 '-'（英文软换行）→ 拼接时不带连字符
 *        例：'...water-' + 'treatment system'  → 'watertreatment system'
 *
 *   其他限制：
 *     - 上一段长度 >= 30 字符（避免误合并短 OCR 噪音）
 */
function _shouldMergeParagraphs(prevContent, nextContent) {
  if (!prevContent || !nextContent) return false
  const prev = prevContent.trim()
  const next = nextContent.trim()
  if (prev.length < 30) return false

  const lastChar = prev[prev.length - 1]
  const firstChar = next[0]

  // 情况 B: 上一段有未闭合的括号（包括圆括号、方括号、中文括号）
  //   计数法比单字符判断更可靠（OCR 可能把 "(" 跟文本混淆）
  //   例：'...analyzer (Malvern Panalytical' + 'ZS₉₀), and...'
  const openCount = (prev.match(/[\(\[（]/g) || []).length
  const closeCount = (prev.match(/[\)\]）]/g) || []).length
  if (openCount > closeCount) return true

  // 情况 A: 上一段不以句末符号结尾 + 本段小写字母 / 中文开头
  if (/[.!?;:。！？；："')\]]/.test(lastChar)) return false
  if (!/[a-z一-龥]/.test(firstChar)) return false
  return true
}

/**
 * v28 step 109.12: 从 caption 文本提取 figureNo
 *   vision 经常输出 "Fig. 3. Effects of complex..." 配 figure_no="Fig. 1"（错位）
 *   caption 文本里的 figureNo 更可靠（这是 vision OCR 真实看到的标题）
 *   返回 "Fig. N" / "Scheme N" / "Fig. S3" 等格式
 */
function _extractFigureNoFromCaption(caption) {
  if (!caption) return null
  // 匹配 "Fig. 3" / "Figure 3" / "Scheme 1" / "Fig. S3" 等
  const m = caption.match(/^\s*((?:Fig\.?|Figure|Scheme|Table)\s*[S]?\d+[a-z]?)/i)
  if (m) return m[1].trim().replace(/\s+/g, ' ')
  return null
}

/**
 * v28 step 109.7: 检测 vision OCR 把图说明误当 paragraph 的情况
 *   vision 把图旁边 OCR 出的中文/英文图说明当独立段落输出
 *   特征：以"该图为/此图为/图 X" / "This figure shows" / "Fig. N is a" 等开头
 *   这些不是正文，应丢弃（图片本身的 caption 已通过 FigureCard 显示）
 */
function isOcrFigureCaption(text) {
  if (!text) return false
  // 中文：以"该图/此图/图 X/图示/示意图"开头，且总长 < 300 字符
  if (/^\s*(该图|此图|本图|图\s*\d+|图示|示意图)/.test(text) && text.length < 300) return true
  // 英文：以 Fig/Figure/Scheme/This figure/This image 开头 + 描述句
  if (/^\s*(this\s+(figure|image|scheme)|the\s+figure)\s+(shows?|depicts?|illustrates?|presents?|displays?)/i.test(text)) return true
  if (/^\s*(fig\.?|figure|scheme)\s*\d+[a-z]?\s+(is|shows?|depicts?|illustrates?|presents?|displays?)/i.test(text)) return true
  // "is a schematic illustration" / "is an image" 等描述句开头
  if (/^\s*(this|it)\s+is\s+(a|an)\s+(schematic|illustration|image|diagram)/i.test(text)) return true
  return false
}

// v28 step 109.32: vision OCR 经常把页眉误识为 paragraph
//   真实案例：PDF id=19 page 9 上 "T. Wang et al. Journal of Hazardous Materials
//     513 (2026) 142456" 被 vision 标为 type=paragraph（不是 page_header）
//   → step 109.25 合并逻辑看到末尾无句末符号 + 下段开头小写 → 合并到正文
//   → "orbital coupling" 段前面多了 "T. Wang et al.\nJournal of Hazardous Materials..."
//   修复：检测文本是否纯页眉内容（作者行 + 期刊行），是的话跳过整段
function isOcrPageHeader(text) {
  if (!text) return false
  const t = text.trim()
  if (t.length > 500) return false  // 太长不像页眉
  const lines = t.split(/\n+/).map(l => l.trim()).filter(l => l.length > 0)
  if (lines.length === 0) return false
  // 所有非空行都必须像页眉行（作者行 / 期刊行 / 纯数字页码）
  let allHeaderLines = true
  for (const line of lines) {
    if (!_isHeaderLine(line)) { allHeaderLines = false; break }
  }
  return allHeaderLines
}

// v28 step 109.36.6: 检测 OCR 误识为 paragraph 的出版信息
//   出现在 Abstract / References / Conclusion 等结构性 section 时应该被过滤
//   （* Corresponding author / E-mail address / DOI / Received / 学校地址 等）
function isOcrPublicationInfo(text) {
  if (!text) return false
  const t = text.trim()
  if (t.length > 1500) return false  // 太长不像出版信息
  // 整段含这些关键词就过滤
  const markers = [
    /^\s*\*\s*Corresponding\s+author/i,
    /^E-?mail\s+address\s*[:：]/i,
    /^https?:\/\/(?:dx\.)?doi\.org\//i,
    /^Received\s+(?:in\s+revised\s+form\s*)?\d/i,
    /^Available\s+online\s+\d/i,
    /^©\s*\d{4}\s+(?:Elsevier|ScienceDirect|Wiley|Springer)/i,
    /0304-3894\/©/,
    // Keywords 块（出版元信息，已被 normalizePaperData 抽到 keywords 字段）
    /^Keywords?\s*[:：]/i,
    // 学校/单位地址行（出现在 Abstract 后）
    /^[a-z]\s+School\s+of\s+/i,
    /^[a-z]\s+College\s+of\s+/i,
    /^[a-z]\s+State\s+Scientific/i,
    /^[A-Z][\w\s&]+\b(?:University|Institute|Academy|College)\b/i,
    // 作者名列表（多个人名 + 上标 a,b,c）
    //   格式："Tianzhi Wanga, Hangjia Zhaoa, Yongtao Lia, ..."
    //   关键：作者名 + 姓 是连写 2 词（如 "Tianzhi Wang"），后面 ", Hangjia Zhao" 重复
    //   至少 3 个名字（1 初始 + 2 重复）
    /^[A-Z][a-z]+\s+[A-Z][a-z]+(?:,\s*[A-Z][a-z]+\s+[A-Z][a-z]+){2,}/,
    // PR China 国家行
    /^PR\s+China/i,
  ]
  return markers.some(re => re.test(t))
}

function _isHeaderLine(line) {
  if (!line) return false
  // 作者行："T. Wang et al." / "X. Lastname et al." / "X. Lastname, Y. Lastname et al."
  if (/^[A-Z]\.\s+[A-Z][a-z]+(\s*,?\s*[A-Z]\.\s*[A-Z][a-z]+)*\s*,?\s*(et\s+al\.?)?$/i.test(line)) return true
  // 期刊行："Journal of Hazardous Materials 513 (2026) 142456"
  // 通用模式：Journal ... Vol (Year) Pages / Vol., Issue (Year) Pages
  if (/^Journal\s+of\s+[A-Z][\w\s&]+(\s+\d+)?\s*\(?\d{4}\)?\s+\d+/i.test(line)) return true
  if (/^[A-Z][\w\s]+\s+\d+\s*\(\d{4}\)\s+\d+\s*$/.test(line)) return true  // "Hazardous Materials 513 (2026) 142456"
  // 纯数字页码："7" / "513"
  if (/^\d{1,5}$/.test(line)) return true
  return false
}

// v28 step 109.33: 段落内分拆（vision OCR 经常把多个段落合并到同一个 block）
//   真实案例：PDF id=19 page 9 vision [1] block 包含两个独立段落：
//     "orbital coupling... facilitates key reaction steps."
//     "Consistent with this mechanistic picture... reactive oxygen species."
//   中间只换行（无空行），paperAdapter 不会自动拆段
//   修复：检测 [.!?] + \n + 大写字母开头（含过渡短语）拆成多个段落
//   关键约束：避免误拆被换行打断的化学式 / 表格引用 / OCR 软换行
//
//   v28 step 109.35: 无换行的多段也拆
//     vision OCR 也经常把多段塞进一行（中间 1-2 个空格），导致 step 109.33 完全失效
//     真实案例：PDF id=19 section 4 block [2] (2457 字符) 实际包含三段：
//       "...long-term performance."
//       "Meanwhile, CO₂ was continuously detected throughout the reaction..."
//       "Beyond achieving high toluene removal efficiency... Supporting Information..."
//     修复：检测 `[.!?] + 1-2 个空格 + 大写字母开头（含过渡短语）` 也拆段
//     关键约束：只允许"硬段首词"（如 Meanwhile / Beyond / Therefore），
//     不允许"承接句"（如 It is worth noting that / Note that / Specifically），
//     避免误拆 step 109.25 想合并的"段中段"
const _PARAGRAPH_TRANSITIONAL_PHRASES = [
  'Consistent with', 'Therefore', 'Furthermore', 'Moreover',
  'In addition', 'Additionally', 'In summary',
  'In contrast', 'By comparison', 'Based on these', 'These results',
  'However', 'Nevertheless', 'Subsequently', 'Notably',
  'Meanwhile', 'Importantly', 'Generally',
  'To evaluate', 'To further', 'To investigate', 'In this',
  'We propose', 'We suggest',
  'Beyond',  // v28 step 109.35
]

// v28 step 109.35: 无换行拆段时只能用的"硬段首词"
//   区分"承接句"（如 "It is worth noting that"、"Note that"）和"真新段"
//   承接句通常出现在段中（如 "It is worth noting that the..."），不应拆
//   真新段通常用 Meanwhile / Beyond / Therefore 等"明显停顿"标记
const _PARAGRAPH_HARD_NEW_PHRASES = [
  'Consistent with', 'Therefore', 'Furthermore', 'Moreover',
  'In addition', 'Additionally', 'In summary',
  'In contrast', 'By comparison', 'Based on these', 'These results',
  'However', 'Nevertheless', 'Subsequently', 'Notably',
  'Meanwhile', 'Importantly',
  'Beyond',  // v28 step 109.35
]

function _splitByParagraphBreak(text) {
  if (!text) return [text]
  if (!text.includes('.') && !text.includes('!') && !text.includes('?')) return [text]

  const hasNewline = /\n/.test(text)
  // v28 step 109.35: 无换行拆段时必须有足够文本长度才能拆（避免误拆 step 109.25 想合并的"段中段"）
  //   真实案例：section 4 block [2] 2457 字符 → 必须拆
  //   反例：step 109.32 block 2 "species. Consistent with..." 132 字符 → 不该拆
  const isLongEnough = text.length >= 300
  const splits = []
  let lastIdx = 0
  // 模式 1：换行分隔（step 109.33）—— 可用所有 _PARAGRAPH_TRANSITIONAL_PHRASES
  // 模式 2：无换行（step 109.35）—— 只用 _PARAGRAPH_HARD_NEW_PHRASES + 必须 length >= 300
  // 共同 regex：[.!?] + 1-3 个空白 + 大写字母开头的短语
  const re = /([.!?])\s{1,3}\s*([A-Z][a-z]+(?:\s+\w+){0,5})/g
  let m
  while ((m = re.exec(text)) !== null) {
    const phraseStart = m.index + m[0].length - m[2].length
    const phraseEnd = phraseStart + m[2].length
    const phrase = m[2].trim()
    const endsWithPunct = (m[1] === '.' || m[1] === '!' || m[1] === '?')

    // 必须句末符号 + 大写开头
    if (!endsWithPunct) continue
    // 跳过缩写（"et al.", "Fig.", "Eq.", "Dr." 等）—— 后跟小写字母通常不是段尾
    const charBefore = phraseStart > 0 ? text[phraseStart - 2] : ''
    if (/[A-Za-z]/.test(charBefore) && charBefore === charBefore.toLowerCase()) {
      continue
    }

    // 短语含过渡词 → 拆段
    // 无换行（step 109.35）：只接受硬段首词 + 必须 length >= 300
    let allowed
    if (hasNewline) {
      allowed = _PARAGRAPH_TRANSITIONAL_PHRASES
    } else if (isLongEnough) {
      allowed = _PARAGRAPH_HARD_NEW_PHRASES
    } else {
      allowed = []  // 无换行 + 短文本 → 不拆（让 step 109.25 决定是否合并）
    }
    const isTransitional = allowed.some(w =>
      phrase.startsWith(w + ' ') || phrase === w
    )
    if (!isTransitional) continue

    // 拆段点：句末符号位置之后
    splits.push(text.slice(lastIdx, phraseStart))
    lastIdx = phraseStart
  }

  if (lastIdx === 0) return [text]
  splits.push(text.slice(lastIdx))
  return splits.filter(s => s.trim())
}

function isTocEntry(text) {
  if (!text) return false
  // 模式 1：章节编号前缀 + 连续点 + 页码（如 "1 绪论..............1"）
  //   关键：前面必须是数字编号（开头 ^[一二三四五六七八九十\d][\d\s.]*）
  if (/^[\d一二三四五六七八九十]+[\d\s.]*[^\n]{1,80}\.{3,}\s*\d*\s*$/.test(text)) return true
  // 模式 2：标题 + 2+ 空格 + 1-4 位页码（"3 结果与讨论   42"）
  if (/^.+\s{2,}\d{1,4}\s*$/.test(text)) return true
  // 模式 3：中文标题 + 连续点 + 页码（"摘 要...........I"）—— 不带数字前缀的中文 TOC 条目
  if (/^[一-龥]{2,}\s*[^\n]{0,80}\.{3,}\s*[IVXLCDM\d]+\s*$/i.test(text)) return true
  // 模式 4：纯罗马数字（"III"）—— vision 误把页码当 heading
  if (/^\s*[IVXLCDM]+\s*$/i.test(text)) return true
  // 模式 5：纯数字（"50"）—— 同上
  if (/^\s*\d{1,4}\s*$/.test(text)) return true
  return false
}

/**
 * v28 step 109.3: 检测整页是不是"目录"页
 *   特征：首个 heading 是 "目录" / "Table of Contents" / "Contents"
 *   或前 3 个 heading 里有 ≥1 个目录标识
 */
function _isTocPage(blocks) {
  if (!blocks || !blocks.length) return false
  const tocKeywords = /^\s*(目录|目錄|table\s+of\s+contents|contents?|table\s+des\s+matières|inhaltsverzeichnis)\s*$/i
  let tocHits = 0
  let headingCount = 0
  for (const b of blocks.slice(0, 10)) {
    if (b.type !== 'heading') continue
    headingCount++
    const text = (b.text || '').trim()
    if (tocKeywords.test(text)) tocHits++
    // 章节标题含 "...." 也是 TOC
    if (isTocEntry(text)) tocHits++
  }
  // 首个 heading 是"目录"且 TOC 条目占多数 → TOC 页
  if (tocHits > 0 && tocHits >= headingCount * 0.5) return true
  return false
}

/**
 * 把 sections 列表中连续的 reference paragraph 抽取出来，单独成 references section
 * 在 _buildPaperFromVisionLayout 内调用
 */
function _extractReferencesFromSections(sections) {
  if (!sections?.length) return sections
  for (const sec of sections) {
    if (!sec.blocks?.length) continue
    const newBlocks = []
    let refBuffer = []
    let inRefs = false
    for (const b of sec.blocks) {
      if (b.type === 'paragraph' && _isReferenceParagraph(b.content || '')) {
        refBuffer.push(b)
        inRefs = true
        continue
      }
      if (inRefs && b.type === 'paragraph' && !_isReferenceParagraph(b.content || '')) {
        // 连续 ref 段结束（如遇非 ref 段，把累积的 refs flush 为 reference_list block）
        if (refBuffer.length) {
          newBlocks.push({
            type: 'reference_list',
            content: refBuffer.map(r => r.content).join('\n\n'),
            page: refBuffer[0].page,
          })
          refBuffer = []
        }
        newBlocks.push(b)
        inRefs = false
        continue
      }
      newBlocks.push(b)
    }
    // 末尾的 ref
    if (refBuffer.length) {
      newBlocks.push({
        type: 'reference_list',
        content: refBuffer.map(r => r.content).join('\n\n'),
        page: refBuffer[0].page,
      })
    }
    sec.blocks = newBlocks
  }
  return sections
}

/**
 * 把 section 列表的 type 字段标准化为前端的视图分类
 */
function classifySectionType(section) {
  if (!section) return 'normal'
  return section.type || 'normal'
}


// ============================================================================
// v28 step 105: 从 vision model 扫描的 layout 数据重建 PaperDetail
//   vision model 真正"看"了整篇论文 PDF，输出每页的 blocks 数组（按视觉顺序）
//   这套数据彻底替代 regex 推断的 section 拆分 + image 位置匹配
// ============================================================================

function _buildPaperFromVisionLayout(raw, visionLayout, images, extractions, related) {
  const pages = visionLayout.page_layout || []
  if (!pages.length) return null

  // v28 step 106: 去重 page_number（vision 不稳定会重复 page 8）
  //   按 page_number 分组，合并相同 page 的 blocks（按 order 排序拼接）
  const mergedPages = _mergeVisionPagesByNumber(pages)

  // v28 step 106: 处理 reference_list 块（vision 已识别参考文献时直接用）
  //   同时扫描所有 paragraph 检测 [N] 开头格式（vision 没识别的兜底）

  // ── 1. 按 vision 输出的 blocks 顺序遍历，构建 sections
  //    遇到 heading 块就开新 section，否则累积到当前 section
  const sections = []
  let currentSection = null
  let currentBlocks = []
  let pageMarkers = []
  let figureMarkers = []
  let inlineFigureAnchors = {}
  // v28 step 109.9: 跟踪已用 image id（避免 fallback 把同一图分配给多张 figure）
  const _usedImageIds = new Set()
  let figureRegistry = []
  let pidCounter = 0
  // 按 page 排序 images，构造全局 image_index → img 映射
  // vision 输出的 image_index 是按扫描顺序的全局编号（跨页累积）
  const sortedImages = images.slice().sort((a, b) => {
    const pa = a.page || a.pageNumber || 0
    const pb = b.page || b.pageNumber || 0
    return pa - pb
  })
  const imageByGlobalIndex = {}
  for (let i = 0; i < sortedImages.length; i++) {
    imageByGlobalIndex[i] = sortedImages[i]
  }

  const sectionIdCounter = { s: 0 }
  const genId = () => `s_${++sectionIdCounter.s}`

  // v28 step 109.25 + 109.33: 处理单个 paragraph（合并 + push）
  //   抽出为函数是为了支持 step 109.33 的段落分拆（一个 vision block 可能拆成多段）
  //   每段独立判断是否合并到上一段
  function _processSingleParagraph(text, pageNum, options = {}) {
    if (!text || !text.trim()) return
    // v28 step 109.36.6.3: 提前过滤出版元信息（避免被 deferredMisplacedBlocks 路径绕过守卫）
    //   之前守卫只在 paragraph 直接处理分支生效，deferred 路径（OCR 错位段插入）
    //   直接 splice 到 currentBlocks 跳过了守卫
    if (currentSection && (currentSection.type === 'abstract' ||
        currentSection.type === 'conclusion' ||
        currentSection.type === 'references' ||
        currentSection.type === 'preamble' ||
        currentSection.type === 'article_info' ||
        currentSection.type === 'highlights')) {
      if (isOcrPublicationInfo(text)) return
    }
    const lastBlock = currentBlocks[currentBlocks.length - 1]
    if (lastBlock
        && lastBlock.type === 'paragraph'
        && _shouldMergeParagraphs(lastBlock.content, text)) {
      // 合并：上一段内容 + 空格 + 本段
      lastBlock.content = (lastBlock.content + ' ' + text).trim()
      pidCounter++
      return
    }
    currentBlocks.push({
      type: 'paragraph',
      content: text,
      page: pageNum,
      indexInSection: currentBlocks.length,
      // v28 step 109.40: 携带 _skipToNextSection 标志，让 startSection 的 Step 2
      //   挪移条件更精准（仅挪已确认属下一节的段）
      _skipToNextSection: options.skipToNextSection || false,
    })
    pidCounter++
  }

  // v28 step 109.36.2: flush deferredForNextSection 到当前 section
  //   智能选择插入位置：
  //   - 如果 currentBlocks 已经包含 image_anchor → 插入到最后一个 image_anchor 之后（讨论组跟在图后）
  //   - 否则（无 image_anchor 的 section，如 step 109.36 fixture）→ 插入到 currentBlocks 末尾
  //   调用时机：每次 push paragraph/image/table/formula 后
  function flushDeferredForNextSection() {
    if (deferredForNextSection.length === 0) return
    // 找最后一个 image_anchor 位置
    let insertPos = currentBlocks.length  // 默认末尾
    for (let i = currentBlocks.length - 1; i >= 0; i--) {
      const b = currentBlocks[i]
      if (b && (b.type === 'image_anchor' || b.type === 'image')) {
        insertPos = i + 1
        break
      }
    }
    currentBlocks.splice(insertPos, 0, ...deferredForNextSection)
    deferredForNextSection.length = 0
  }

  // v28 step 109.30: 修正 vision OCR 输出顺序 bug
  //   vision 经常把 section heading 的内容（paragraph）输出在 heading 之前
  //   例：page 8 上 vision 输出顺序是 [67] paragraph (3.4) [68] paragraph (3.5) [69] heading 3.5
  //   → heading X.Y 出现时，把上一个 section 中"同一 page 且紧邻 heading"的
  //     最后 1 个 paragraph 块移到当前 section
  //
  //   v28 step 109.31: figure-aware 插入（不是简单追加到末尾）
  //     用户的 paper 真实顺序：Fig. 5a 讨论 → Fig. 5 image → Fig. 5b/c 讨论 → Fig. 5d/e 讨论
  //     但 vision 把 Fig. 5b/c 讨论放在 heading 之前，所以单独追加到末尾就破坏了顺序
  //     算法：提取 misplaced 的最高子图字母（如 Fig. 5c），找当前 section 里引用"下一个子图"
  //     （Fig. 5d）的 paragraph，插在它前面；找不到则按 image_anchor / earlier sub-figure 回退
  const deferredMisplacedBlocks = []
  // v28 step 109.36: 推迟到下一个 section 的 blocks（不是上一个 section）
  //   lookahead 发现 paragraph 引用图号 > 当前 section → 不进 currentSection
  //   进 deferredForNextSection，等下一个 heading 触发后插入新 section 开头
  const deferredForNextSection = []

  // 提取文本中的 figure 引用 [{num, letter}]
  function _extractFigureRefs(text) {
    if (!text) return []
    const refs = []
    const re = /(?:Fig\.?|Figure|Scheme)\s*(\d+)\s*([a-z])?/gi
    let m
    while ((m = re.exec(text)) !== null) {
      refs.push({ num: parseInt(m[1], 10), letter: (m[2] || '').toLowerCase() })
    }
    return refs
  }

  // 比较 figure ref 大小（num 主排序，letter 次排序，空 letter < 'a'）
  function _cmpFigRef(a, b) {
    if (a.num !== b.num) return a.num - b.num
    return a.letter.localeCompare(b.letter)
  }

  // 找 misplaced block 应该插入的位置（基于 figure 子图字母顺序）
  // 返回 -1 表示"无合适位置（无 fig ref）"，调用方应 prepend 到 section 开头
  function _findInsertPositionForMisplaced(currentBlocks, misplacedBlock) {
    if (currentBlocks.length === 0) return 0
    const text = misplacedBlock.content || misplacedBlock.text || ''
    const figs = _extractFigureRefs(text)
    // v28 step 109.40: 无 figure 引用 → 不追加到末尾（可能错位），改 prepend
    //   PDF id=19 的 2.4 段末 "Based on"（含 Fig. 1 引用 → 会走下方逻辑）走的是
    //   另一种 fallback。但其他无 fig 引用的段（如纯说明段）应 prepend 到开头，
    //   避免被插入到完全无关 section 末尾
    if (figs.length === 0) return -1

    // 最高子图（如 Fig. 5c 的 {5, 'c'}）
    let highest = figs[0]
    for (const f of figs) {
      if (_cmpFigRef(f, highest) > 0) highest = f
    }

    // 第一优先：找引用"下一个子图"的 paragraph（图号同 + letter 更大），插在它前面
    for (let i = 0; i < currentBlocks.length; i++) {
      const b = currentBlocks[i]
      if (b.type !== 'paragraph') continue
      const bFigs = _extractFigureRefs(b.content || b.text || '')
      for (const f of bFigs) {
        if (f.num === highest.num && _cmpFigRef(f, highest) > 0) {
          return i  // 插在 i 之前
        }
      }
    }

    // 第二优先：找同图号的 image_anchor（"Fig. 5"，无子图字母），插在它后面
    //   典型 paper 布局：image 显示 → 后续 paragraph 讨论各子图
    if (highest.letter) {
      for (let i = 0; i < currentBlocks.length; i++) {
        const b = currentBlocks[i]
        if (b.type !== 'image_anchor' && b.type !== 'image') continue
        const bText = b.caption || b.content || b.text || ''
        const bFigs = _extractFigureRefs(bText)
        for (const f of bFigs) {
          if (f.num === highest.num && !f.letter) {
            return i + 1  // 插在 image 之后
          }
        }
      }
    }

    // 第三优先：找引用"更早子图"的 paragraph，插在它后面
    for (let i = currentBlocks.length - 1; i >= 0; i--) {
      const b = currentBlocks[i]
      if (b.type !== 'paragraph') continue
      const bFigs = _extractFigureRefs(b.content || b.text || '')
      for (const f of bFigs) {
        if (f.num === highest.num && _cmpFigRef(f, highest) < 0) {
          return i + 1
        }
      }
    }

    // 兜底：含 fig 引用但找不到匹配位置 → 也 prepend（v28 step 109.40 修复）
    //   避免段落被错位追加到完全无关 section 末尾
    return -1
  }

  const flushCurrent = () => {
    if (currentSection) {
      // 把 deferred misplaced blocks 按 figure-aware 位置插入
      for (const m of deferredMisplacedBlocks) {
        const pos = _findInsertPositionForMisplaced(currentBlocks, m)
        // v28 step 109.40: -1 = 无合适位置（无 fig 引用）→ prepend 到 section 开头
        //   修复 bug：原本 splice(currentBlocks.length, 0, m) 会把 paragraph 追加到
        //   完全无关 section 末尾（PDF id=19 的 2.4 段末 "Based on" 错位到 3.1 最后）
        if (pos === -1) {
          currentBlocks.unshift(m)
        } else {
          currentBlocks.splice(pos, 0, m)
        }
      }
      deferredMisplacedBlocks.length = 0
      // v28 step 109.36.2: flush 兜底处理 deferredForNextSection 残留
      //   （例如 step 109.36 fixture：4 节只有 1 个 heading 触发，flushCurrent 是唯一 flush 时机）
      flushDeferredForNextSection()
      sections.push({
        id: currentSection.id,
        title: currentSection.title,
        level: currentSection.level,
        type: currentSection.type,
        blocks: currentBlocks,
      })
      currentSection = null
      currentBlocks = []
    }
  }

  const startSection = (type, title, level, pageNum) => {
    if (currentSection) {
      // Step 1: 把之前 deferred 的 misplaced blocks 按 figure-aware 位置插入当前 section
      for (const m of deferredMisplacedBlocks) {
        let pos = _findInsertPositionForMisplaced(currentBlocks, m)
        // v28 step 109.40: -1 = 无 fig 引用 → prepend 到当前 section 开头（避免
        //   被错位追加到 section 末尾，PDF id=19 的 2.4 "Based on" 段就是这个 bug）
        let prepended = false
        if (pos === -1) {
          currentBlocks.unshift(m)
          pos = 0
          prepended = true
        } else {
          currentBlocks.splice(pos, 0, m)
        }
        // v28 step 109.34: 插入后立即检查与前后邻居的合并
        //   之前问题：step 109.31 插入 misplaced block 时，后面的内容已被 push 过，
        //     没有走 step 109.25 合并逻辑，导致 molecular_model + orbital_coupling
        //     错分成两段（用户期望合并成一段）
        //   修复：插入后检查 prev（如果 prev 是 paragraph 且 _shouldMergeParagraphs）
        //     或 next（同样条件），合并
        // v28 step 109.40: prepended 模式下跳过 prev 合并（避免和第一段错位合并）
        if (!prepended) {
          const prevBlock = pos > 0 ? currentBlocks[pos - 1] : null
          if (prevBlock && prevBlock.type === 'paragraph' && _shouldMergeParagraphs(prevBlock.content, m.content)) {
            // 与 prev 合并：prev.content += m.content, 移除 m
            prevBlock.content = (prevBlock.content + ' ' + m.content).trim()
            currentBlocks.splice(pos, 1)
          } else {
            const nextBlock = currentBlocks[pos + 1]
            if (nextBlock && nextBlock.type === 'paragraph' && _shouldMergeParagraphs(m.content, nextBlock.content)) {
              // 与 next 合并：next.content = m.content + next.content, 移除 m
              nextBlock.content = (m.content + ' ' + nextBlock.content).trim()
              currentBlocks.splice(pos, 1)
            }
          }
        }
      }
      deferredMisplacedBlocks.length = 0
      // Step 2: 把当前 section 末尾紧邻 heading 的 paragraph 移到 deferred buffer
      //   v28 step 109.34: 只移"不完整段"（结尾无句末符号），完整段（以 . ! ? 结尾）
      //   不动。否则会把正常的 3.5/4 段末段（以 "." 结尾）错移到下一 section
      // v28 step 109.40: 挪移前记录 paragraph 的"原 section id"和"原 page"。
      //   当 _findInsertPositionForMisplaced 找不到合适位置（无 fig ref 或都 miss）时，
      //   兜底改为 prepend 到 next section 开头（而不是追加到末尾），
      //   这样 paragraph 仍属于新 section（语义上正确）。
      //   PDF id=19 的 2.4 段末 "Based on" 无句末符号被挪移后，原本被兜底追加到
      //   3.1 末尾（错位到与 3.1 内容完全无关的位置），现在改为 prepend 到
      //   3 Results section 开头（更合理的归属）。
      // v28 step 109.40: 完全禁用 Step 2 挪移逻辑
      //   原挪移条件"段落末尾无句末符号"过于激进，会把完整段（如 PDF id=19 的 2.4
      //   末尾 "Based on"）误挪到 deferredMisplacedBlocks，最终 _findInsertPositionForMisplaced
      //   兜底追加到无关 section 末尾（错位丢段）。
      //   真实场景：vision OCR 已经把每段标成完整 paragraph block，不需要再判定
      //   "段落完整性"主动挪移。段落留在原 section 即便末尾看着"未完"，
      //   也比错位到无关 section 好得多。
      //   副作用：step 109.30 测试 fixture（"the molecular model reveals..." 无句末）
      //   不再被挪移，段落保留在 3.4 section。测试期望已更新（见 paperAdapter.test.js
      //   v28 step 109.30 + 109.40 注释）。
      if (false) {
        const last = currentBlocks[currentBlocks.length - 1]
        if (last.type === 'paragraph' && last.page === pageNum && !last._originalSectionId) {
          const lastContent = (last.content || '').trim()
          const endsIncomplete = !/[.!?。！？]\s*$/.test(lastContent)
          if (endsIncomplete) {
            const moved = currentBlocks.pop()
            moved._originalSectionId = currentSection.id
            moved._originalSectionTitle = currentSection.title
            deferredMisplacedBlocks.push(moved)
          }
        }
      }
      // Step 3: flush 当前 section（不含 deferred 的 block）
      sections.push({
        id: currentSection.id,
        title: currentSection.title,
        level: currentSection.level,
        type: currentSection.type,
        blocks: currentBlocks,
      })
    }
    currentSection = {
      id: genId(),
      title: title || '未命名',
      level: level || 1,
      type: type || 'normal',
    }
    currentBlocks = []
    // v28 step 109.36.2: startSection 不立即 flush deferredForNextSection
    //   让 paragraph/image/table/formula push 后的 helper 智能判断 image_anchor 位置
    //   flushCurrent 也兜底（处理没有更多 push 的 section）
  }

  // v28 step 109.36: 预处理所有 blocks 平铺数组（用于 lookahead）
  //   vision OCR 经常把下一节的 paragraph 输出在 heading 之前（page 9 order=3 是 4 节内容
  //   但 heading 4 在 order=4）。Lookahead 让 paragraph 处理时能 peek 下一个 heading。
  const allBlocksFlat = []
  for (const page of mergedPages) {
    const pageNum = page.page_number
    const blocks = (page.blocks || []).slice().sort((a, b) => (a.order || 0) - (b.order || 0))
    for (const b of blocks) {
      allBlocksFlat.push({ ...b, _pageNum: pageNum })
    }
  }
  // 构造 (pageNum, order) → block 在 flat 数组中的索引
  const blockIndexByKey = new Map()
  for (let i = 0; i < allBlocksFlat.length; i++) {
    const b = allBlocksFlat[i]
    blockIndexByKey.set(`${b._pageNum}:${b.order}`, i)
  }

  for (const page of mergedPages) {
    const pageNum = page.page_number
    const blocks = (page.blocks || []).slice().sort((a, b) => (a.order || 0) - (b.order || 0))
    for (let bi = 0; bi < blocks.length; bi++) {
      const b = blocks[bi]
      if (b.type === 'page_header' || b.type === 'page_footer') {
        // 跳过页眉页脚
        continue
      }
      // v28 step 106: reference_list 块独立处理（标记为 references section 末尾）
      if (b.type === 'reference_list') {
        if (!currentSection) startSection('references', 'References', 1, pageNum)
        else if (currentSection.type !== 'references') {
          // 开新 References section
          startSection('references', 'References', 1, pageNum)
        }
        currentBlocks.push({
          type: 'reference_list',
          content: b.text || '',
          page: pageNum,
        })
        // 不立即 flush deferredForNextSection（等 image_anchor 或 flushCurrent 兜底）
        continue
      }
      if (b.type === 'heading') {
        const level = b.level || 1
        // v28 step 109.28: heading 也走 formatScientificText（之前只有 paragraph 处理）
        //   修复章节标题里 '-OH' 不会被转为 '·OH' 的 bug
        let title = (b.text || '').trim()
        if (!title) continue
        title = formatScientificText(title)
        // v28 step 109.3: 过滤 vision 误识的 TOC 条目
        //   目录里的 "1 绪论..............1" / "2 试验材料与方法...5" 会被 vision 标为 heading
        //   特征：含连续 3+ 个点 + 末尾页码 OR 含省略号
        if (isTocEntry(title)) continue
        // 用 _matchSectionTitle 判定 type（识别 Introduction/Methods/Results 等关键词）
        const matched = _matchSectionTitle(title)
        let secType
        let secLevel
        if (matched) {
          secType = matched.type
          // v28 step 109.36.7: Abstract / Conclusion / References 等独立结构性 section
          //   没有 number 前缀（OCR 只有 "ABSTRACT"），level=undefined。
          //   这些 section 与 "1. Introduction" 同级别，强制 level=1 让前端渲染
          //   用相同的 h2 + 左侧锚点 + RightAnchorNav 跟踪
          if (secType === 'abstract' || secType === 'conclusion' || secType === 'references') {
            secLevel = 1
          } else {
            secLevel = matched.level || level
          }
        } else if (level === 1) {
          // level=1 且不匹配任何 SECTION_KEYWORDS → preamble（论文主标题/期刊名）
          secType = 'preamble'
          secLevel = 1
        } else {
          // 其他情况 → normal
          secType = 'normal'
          secLevel = level
        }
        startSection(secType, title, secLevel, pageNum)
      } else if (b.type === 'paragraph') {
        const text = _mergeOCRSoftLineBreaks((b.text || '').trim())
        if (!text) continue
        // v28 step 109.3: 同样过滤 TOC 里的 paragraph（如 "摘 要..............I"）
        if (isTocEntry(text)) continue
        // v28 step 109.41: 智能识别 paragraph 形式的子节标题
        //   vision OCR 经常把子节标题（如 "3.2. Effect of oxidant supply..."）错标为 paragraph
        //   特征：纯标题文本 + 含编号前缀 (\d+(\.\d+)*\.) + 长度 ≤ 80 字符 + 不含中文/长句
        //   PDF id=19 真实案例：3.2 / 3.3 heading 被错标为 paragraph，导致导航不显示
        if (currentSection && currentSection.type !== 'preamble' && currentSection.type !== 'abstract') {
          const trimmedText = text.trim()
          // 单行（不含换行）+ 短 + 编号开头 + 后跟标题词
          const titleLike = /^\s*(\d+(?:\.\d+)*\.?)\s+([A-Z一-龥][^.!?\n]{0,80})\s*$/.exec(trimmedText)
          if (titleLike) {
            // 后续 paragraph 必须存在（避免误把孤立的"3.2"行识别为标题）
            // 用 lookahead 查下一个 block 是 paragraph（视为正文）
            const myKey2 = `${pageNum}:${b.order}`
            const myIdx2 = blockIndexByKey.get(myKey2)
            const nextBlock = (myIdx2 !== undefined && myIdx2 + 1 < allBlocksFlat.length)
              ? allBlocksFlat[myIdx2 + 1]
              : null
            if (nextBlock && nextBlock.type === 'paragraph' && nextBlock._pageNum === pageNum) {
              const headingText = trimmedText
              const matched2 = _matchSectionTitle(headingText)
              const secType2 = matched2?.type || 'normal'
              const secLevel2 = matched2?.level || (titleLike[1].split('.').length)
              startSection(secType2, headingText, secLevel2, pageNum)
              continue
            }
          }
        }
        // v28 step 109.7: 过滤 OCR 误识的图说明（"该图为..." / "This figure shows..."）
        if (isOcrFigureCaption(text)) continue
        // v28 step 109.32: 过滤 vision 误识的页眉（"T. Wang et al. Journal of..."）
        //   vision 把页眉标成 paragraph 后会被 step 109.25 合并到正文，必须提前过滤
        if (isOcrPageHeader(text)) continue
        // v28 step 109.36.6: 过滤 OCR 误识为 paragraph 的出版信息
        //   仅在结构性 section (abstract/conclusion/references/preamble) 内过滤，
        //   因为这些 section 紧跟 OCR 元信息（Corresponding author / DOI / Received 等）
        if (currentSection && (currentSection.type === 'abstract' ||
            currentSection.type === 'conclusion' ||
            currentSection.type === 'references' ||
            currentSection.type === 'preamble')) {
          if (isOcrPublicationInfo(text)) continue
        }
        // v28 step 109.36: lookahead 检测 paragraph 是否属于下一节
        //   vision OCR 经常把下节内容输出在 heading 之前（如 page 9 order=3 是 4 节内容，
        //   但 heading 4 在 order=4）。如果 paragraph 引用的图号大于下一节范围内任何图号，
        //   且同 page 紧跟 heading（level >= 2），paragraph 应推迟到下一节。
        //   算法：检查 lookahead 中下一个 heading，引用的图号是上限
        const myKey = `${pageNum}:${b.order}`
        const myIdx = blockIndexByKey.get(myKey)
        let skipToNextSection = false
        if (myIdx !== undefined && currentSection) {
          // 收集当前 section 已知的图号范围（从 currentBlocks 累积）
          let curSectionMaxFig = 0
          for (const cb of currentBlocks) {
            if (cb.type === 'paragraph' || cb.type === 'image_anchor') {
              const cbText = cb.content || cb.caption || ''
              for (const f of _extractFigureRefs(cbText)) {
                if (f.num > curSectionMaxFig) curSectionMaxFig = f.num
              }
            }
          }
          // 守卫：currentSection 必须已经有 ≥1 个段落/图，才能触发 lookahead 推迟
          //   否则会把"第一个 paragraph（属于本节）"也推迟到下节
          if (curSectionMaxFig === 0 && currentBlocks.length === 0) {
            // 跳过 lookahead（保留本节）
          } else {
            for (let look = myIdx + 1; look < Math.min(allBlocksFlat.length, myIdx + 4); look++) {
              const next = allBlocksFlat[look]
              if (next.type === 'heading' && next._pageNum === pageNum && (next.level || 1) >= 2) {
                const myFigs = _extractFigureRefs(text)
                if (myFigs.length > 0) {
                  let myMaxNum = 0
                  for (const f of myFigs) if (f.num > myMaxNum) myMaxNum = f.num
                  // 关键判断：我引用的图号 > 当前 section 已知的最大图号 → 推迟到下节
                  if (myMaxNum > curSectionMaxFig) {
                    skipToNextSection = true
                  }
                }
                break
              }
              if (next.type === 'image' || next.type === 'image_anchor') {
                const caption = next.caption || next.text || ''
                const nextFigs = _extractFigureRefs(caption)
                if (nextFigs.length > 0) {
                  const myFigs2 = _extractFigureRefs(text)
                  if (myFigs2.length > 0) {
                    let myMaxNum = 0
                    for (const f of myFigs2) if (f.num > myMaxNum) myMaxNum = f.num
                    let nextMaxNum = 0
                    for (const f of nextFigs) if (f.num > nextMaxNum) nextMaxNum = f.num
                    if (myMaxNum > nextMaxNum) {
                      skipToNextSection = true
                      break
                    }
                  }
                }
                continue
              }
            }
          }
        }
        if (skipToNextSection) {
          const splitTexts = _splitByParagraphBreak(text)
          if (!currentSection) startSection('preamble', '前言', 1, pageNum)
          for (const splitText of splitTexts) {
            deferredForNextSection.push({
              type: 'paragraph',
              content: splitText,
              page: pageNum,
            })
          }
          continue
        }
        // v28 step 109.33: 段落内分拆（vision 把多段合并到一个 block 时按过渡短语拆开）
        //   例："facilitates key reaction steps.\nConsistent with this mechanistic picture..."
        //   → 拆成两个独立 block，由 step 109.25 决定是否真合并
        //   v28 step 109.36.5: Abstract / Conclusion / References 等"独立段落结构"section
        //     不应用 step 109.33 拆段（这些 section 的 paragraph 本来就是一段长文本，
        //     含 By/Although/Overall 等过渡词不应该拆成多段）。
        //   只对正文 sections (results/discussion) 启用拆段。
        const isStructuralSection = currentSection && (
          currentSection.type === 'abstract' ||
          currentSection.type === 'conclusion' ||
          currentSection.type === 'references' ||
          currentSection.type === 'preamble'
        )
        const splitTexts = isStructuralSection ? [text] : _splitByParagraphBreak(text)
        // 没开 section 就先开一个 preamble
        if (!currentSection) startSection('preamble', '前言', 1, pageNum)
        for (const splitText of splitTexts) {
          // v28 step 109.40: 传 skipToNextSection 给 _processSingleParagraph，
          //   让 startSection Step 2 精准挪移（仅 lookahead 确认的段落）
          _processSingleParagraph(splitText, pageNum, { skipToNextSection })
        }
        // 不立即 flush deferredForNextSection（等 image_anchor 或 flushCurrent 兜底）
      } else if (b.type === 'image') {
        // 关联到 knowledge_images 表的图
        const imgIndex = b.image_index || 0
        let img = imageByGlobalIndex[imgIndex]
        // v28 step 109.17: 已用过的 imageId 也触发 fallback（避免重复）
        //   之前只在 img 为空或 publisher 时 fallback → 多张 figure 拿到同一图
        //   现在：imageId 已被前面 figure 用了 → 触发 fallback 找别的图
        const usedImageIds = _usedImageIds
        if (img && img.isPublisherImage !== true && usedImageIds.has(img.id)) {
          img = null  // 触发 fallback
        }
        // v28 step 109.9: 智能 fallback — vision image_index 经常错位
        //   如果命中 publisher 图，尝试 4 级 fallback 找到正确的真实图：
        //   1. 同 page + 同 figureNo 的非 publisher 图
        //   2. 同 page + 同 figureType 的非 publisher 图
        //   3. 同 page 的未使用的非 publisher 图
        //   4. 全局未使用的非 publisher 图
        if (!img || img.isPublisherImage === true) {
          const bFigureNo = b.figure_no || ''
          // v28 step 109.10: page 类型归一化（vision 可能是字符串 '8' / '8.2'，DB 是数字）
          const normalizedPageNum = String(pageNum).split('.')[0]
          const samePageImgs = sortedImages.filter(i => {
            const imgPage = String(i.page || i.pageNumber || '').split('.')[0]
            return imgPage === normalizedPageNum && !i.isPublisherImage && !usedImageIds.has(i.id)
          })
          // Level 1: 同 page + 同 figureNo
          if (bFigureNo) {
            img = samePageImgs.find(i => i.figureNo === bFigureNo || i.figure_no === bFigureNo) || null
          }
          // Level 2: 同 page + 同 type（caption 含 type 名）
          if (!img && b.type === 'image') {
            img = samePageImgs.find(i => i.figureType && b.caption?.toLowerCase().includes(i.figureType.toLowerCase())) || null
          }
          // Level 3: 同 page 的任意未使用的非 publisher 图
          if (!img) {
            img = samePageImgs[0] || null
          }
          // Level 4: 跨 page 找最近的未使用的非 publisher 图（按 page 距离排序）
          //   v28 step 109.14: 必须排除已用 image id（避免 Fig.4 与 Scheme1 同图重复）
          if (!img) {
            const candidates = sortedImages.filter(i =>
              !i.isPublisherImage && !usedImageIds.has(i.id)
            ).sort((a, b) => {
              const distA = Math.abs(Number(String(a.page || 0).split('.')[0]) - Number(normalizedPageNum))
              const distB = Math.abs(Number(String(b.page || 0).split('.')[0]) - Number(normalizedPageNum))
              return distA - distB
            })
            img = candidates[0] || null
          }
          // Level 5: 实在找不到未用 image，保留 null（占位，不显示 src）
        }
        if (img) _usedImageIds.add(img.id)
        // v28 step 109.6: 如果 fallback 后仍是 publisher，按 no-match 处理（占位）
        if (img && img.isPublisherImage === true) {
          img = null
        }
        if (!currentSection) startSection('normal', '未命名', 2, pageNum)
        // 把 image 关联到当前 section 最后一个 paragraph
        const pidKey = `${currentSection.id}__p${currentBlocks.length - 1}`
        if (!inlineFigureAnchors[pidKey]) inlineFigureAnchors[pidKey] = []
        if (img) {
          inlineFigureAnchors[pidKey].push(img)
          // v28 step 109.12: figureNo 优先从 caption 提取（vision 经常 figure_no 与 caption 不对应）
          const captionFigureNo = _extractFigureNoFromCaption(b.caption)
          // v28 step 109.28: caption 也走 formatScientificText（化学式 OCR 修正）
          const cleanCaption = b.caption ? formatScientificText(b.caption) : null
          figureRegistry.push({
            id: img.id,
            page: pageNum,
            figureNo: captionFigureNo || img.figureNo || b.figure_no || null,
            figureType: img.figureType || null,
            caption: cleanCaption,
            isCoreFigure: img.isCoreFigure !== false,
            isPublisherImage: !!img.isPublisherImage,
            visualSummary: img.visualSummary || null,
            sectionHint: img.sectionHint || null,
            anchorText: img.anchorText || null,
          })
        } else {
          // 没关联到图，登记一个空 fig（保留 caption 用于显示）
          const captionFigureNo = _extractFigureNoFromCaption(b.caption)
          const cleanCaption2 = b.caption ? formatScientificText(b.caption) : null
          figureRegistry.push({
            id: `vision-page${pageNum}-img${imgIndex}`,
            page: pageNum,
            figureNo: captionFigureNo || b.figure_no || null,
            figureType: null,
            caption: b.caption || null,
            isCoreFigure: true,
            isPublisherImage: false,
            visualSummary: null,
            sectionHint: null,
            anchorText: null,
          })
        }
        // 同时给当前 section 加 image 标记（让前端能渲染 image block）
        const cleanCaption3 = b.caption ? formatScientificText(b.caption) : null
        currentBlocks.push({
          type: 'image_anchor',
          page: pageNum,
          image_index: imgIndex,
          caption: cleanCaption3,
          figure_no: b.figure_no || null,
        })
        flushDeferredForNextSection()
      } else if (b.type === 'table') {
        const caption = b.caption || null
        const headers = b.headers || []
        const rows = b.rows || []
        const tableMd = [
          '| ' + headers.join(' | ') + ' |',
          '| ' + headers.map(() => '---').join(' | ') + ' |',
          ...rows.map(r => '| ' + r.join(' | ') + ' |'),
        ].join('\n')
        if (!currentSection) startSection('normal', '未命名', 2, pageNum)
        currentBlocks.push({
          type: 'table',
          content: tableMd,
          page: pageNum,
          caption,
        })
        // 不立即 flush deferredForNextSection——等下一个 image_anchor 触发 flush
        // （避免讨论组被挤到 table 之前，破坏视觉顺序）
      } else if (b.type === 'formula') {
        if (!currentSection) startSection('normal', '未命名', 2, pageNum)
        currentBlocks.push({
          type: 'formula',
          content: b.latex || '',
          page: pageNum,
        })
        // 同上：等下一个 image_anchor
      }
    }
    // 每页结束，记录 page_marker
    pageMarkers.push({ page: pageNum })
  }
  flushCurrent()

  // ── 2. 给 figures 分配 figure_no（如果 vision layout 没给，从 caption 提取）
  for (const fig of figureRegistry) {
    if (!fig.figureNo && fig.caption) {
      const m = (fig.caption || '').match(/\b(Fig\.?|Figure|Table|Scheme)\s*(\d{1,3}[a-z]?)\b/i)
      if (m) fig.figureNo = `${m[1]} ${m[2]}`.trim()
    }
  }

  // ── 3. 构造 paper.figures（兼容 KnowledgeDetailView 旧字段）
  // 先给 figureRegistry 自己补 src/imageUrl（避免 PaperBlockRenderer._resolveFigure 拿不到）
  for (const f of figureRegistry) {
    if (f.src || f.imageUrl) continue  // 已有跳过
    // v28 step 109.6: publisher 图跳过 src 填充
    if (f.isPublisherImage === true) continue
    let imageId = null
    if (typeof f.id === 'number') {
      imageId = f.id
    } else if (typeof f.id === 'string' && f.id.startsWith('fig-')) {
      imageId = f.id.slice(4)
    } else if (typeof f.id === 'string' && /^\d+$/.test(f.id)) {
      imageId = parseInt(f.id, 10)
    }
    if (imageId != null) {
      const img = images.find(i => Number(i.id) === Number(imageId))
      // v28 step 109.6: 防御性 publisher 过滤
      if (img && img.isPublisherImage === true) continue
      f.src = img?.src || img?.imageUrl || null
      f.imageUrl = f.src
    }
  }
  // v28 step 109.14: 按 imageId 去重（vision 不稳定会让多张 figure 拿到同一 image）
  //   第一个拿到该 imageId 的 fig 保留 src，后续重复的清空 src（变占位）
  const seenImageIds = new Set()
  for (const f of figureRegistry) {
    const iid = Number(f.id)
    if (Number.isFinite(iid) && iid > 0) {
      if (seenImageIds.has(iid)) {
        // 已用过，清空 src
        f.src = null
        f.imageUrl = null
      } else {
        seenImageIds.add(iid)
      }
    }
  }
  const paperFigures = figureRegistry.map(f => {
    // v28 step 109.5: imageId 提取兼容两种 ID 形式
    //   - vision 路径：f.id 直接是 DB 数字 ID（如 528）→ 直接用
    //   - regex 路径：f.id 是 'fig-528' 字符串 → 剥前缀
    let imageId = null
    if (typeof f.id === 'number') {
      imageId = f.id
    } else if (typeof f.id === 'string' && f.id.startsWith('fig-')) {
      imageId = f.id.slice(4)
    } else if (typeof f.id === 'string' && /^\d+$/.test(f.id)) {
      imageId = parseInt(f.id, 10)
    }
    return {
      id: f.id,
      imageId,
      page: f.page,
      figureNo: f.figureNo,
      figureType: f.figureType,
      caption: f.caption,
      isCoreFigure: f.isCoreFigure,
      isPublisherImage: f.isPublisherImage,
      visualSummary: f.visualSummary,
      sectionHint: f.sectionHint,
      anchorText: f.anchorText,
      // v28 step 109.6: publisher 图 src/imageUrl 始终 null（避免显示 Elsevier logo）
      src: f.isPublisherImage ? null : (f.src || null),
      imageUrl: f.isPublisherImage ? null : (f.imageUrl || f.src || null),
    }
  })
  // v28 step 109.14: paperFigures 也按 imageId 去重（与 figureRegistry 同步）
  const seenIds = new Set()
  for (const f of paperFigures) {
    const iid = Number(f.imageId ?? f.id)
    if (Number.isFinite(iid) && iid > 0) {
      if (seenIds.has(iid)) {
        f.src = null
        f.imageUrl = null
      } else {
        seenIds.add(iid)
      }
    }
  }

  // ── 4. 检测 abstract（从第一页或 preamble 段）
  let abstract = raw.summary || null
  let keywords = Array.isArray(raw.tags) ? raw.tags.slice() : []
  // v28 step 109.36.8: 优先从 abstract section 提取（OCR 已把 "ABSTRACT" 提取为 heading，
  //   paragraph 是 "Conventional aqueous..." 直接正文，不再含 "Abstract:" 前缀）
  const abstractSec = sections.find(s => s.type === 'abstract' || /^abstract$/i.test(s.title || ''))
  if (abstractSec) {
    const firstPara = (abstractSec.blocks || []).find(b => b.type === 'paragraph')
    if (firstPara && firstPara.content) {
      const cleaned = firstPara.content.trim()
      if (cleaned && (!abstract || abstract.length < cleaned.length * 0.5)) {
        abstract = cleaned
      }
    }
  }
  for (const sec of sections) {
    for (const b of sec.blocks || []) {
      if (b.type === 'paragraph' && /^\s*Abstract\s*[：:]?\s*([\s\S]*)/i.test(b.content || '')) {
        const m = b.content.match(/^\s*Abstract\s*[：:]?\s*([\s\S]*)/i)
        if (m && m[1] && (!abstract || abstract.length < m[1].length * 0.5)) {
          abstract = m[1].trim()
        }
      }
      if (b.type === 'paragraph' && /^\s*Keywords?\s*[：:]?\s*([\s\S]*)/i.test(b.content || '')) {
        const m = b.content.match(/^\s*Keywords?\s*[：:]?\s*([^\n]+)/i)
        if (m && m[1] && !keywords.length) {
          keywords = m[1].split(/[,;；]/).map(s => s.trim()).filter(Boolean)
        }
      }
    }
  }

  // v28 step 109.37: 关键词翻译成英文
  keywords = _translateKeywordsToEnglish(keywords)

  // v28 step 109.39: abstract 也走 formatScientificText（让 O₂⋅⁻ / O₃-MNBs / H₂O₂ 都正确格式化）
  if (abstract) {
    abstract = formatScientificText(abstract)
  }

  return {
    id: raw.id,
    title: raw.title,
    status: raw.analysis_status || 'pending',  // v28 step 109.4: 同步 analysis_status 给 PaperHeader 显示
    summary: raw.summary || '',
    abstract,
    keywords,
    // v28 step 109.38: 作者/期刊/DOI 从原文 content 提取（vision 路径也走同一函数）
    ...(function () {
      const info = _extractAuthorsAndJournal(raw.content || '')
      return {
        authors: info.authors,
        affiliations: info.affiliations,
        journal: info.journal,
        doi: info.doi,
      }
    })(),
    // v28 step 109.18: vision 路径也透传 relatedKnowledge（让 RelatedKnowledgeList 渲染）
    relatedKnowledge: Array.isArray(related) ? related : [],
    sections: _extractReferencesFromSections(sections),
    figures: paperFigures,
    figureRegistry: figureRegistry,
    pageMarkers,
    figureMarkers,
    inlineFigureAnchors,
    inlineFigureMap: {},
    // v28 step 109.13: vision 路径补 filePath/fileName/fileType，让 ExtractionPanel 显示
    filePath: raw.file_path || null,
    fileName: raw.file_name || null,
    fileType: raw.file_type || null,
    // v28 step 109.13: 补 formulas/tables/charts/extractions 兼容字段
    formulas: extractions.filter(e => e.kind === 'formula' || e.type === 'formula'),
    tables: extractions.filter(e => e.kind === 'table' || e.type === 'table'),
    charts: extractions.filter(e => {
      const k = e.kind || e.type
      return k === 'chart' || k === 'image_block' || k === 'figure'
    }),
    extractions,
    raw,
    extra: { images, extractions, related, visionLayout: true },
    _status: 'success',
    _source: 'vision_layout',
    _layoutStats: {
      totalPages: visionLayout.total_pages || pages.length,
      totalBlocks: visionLayout.total_blocks || null,
      visionModel: visionLayout.vision_model_used || null,
    },
  }
}

// ---- 本段对外导出（供下游段 import，勿删）----
export { normalizePaperData }
export { normalizeGraphData }
export { classifySectionType }
