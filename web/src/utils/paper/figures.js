// 图表处理：figure registry / inline anchors / 图注匹配 / 锚点树 / autoLink。
import {
  URL_RE, EMAIL_RE, DOI_DUP_RE, DOI_DUP_NOPROTO_RE, IMG_EXT_RE,
  _escapeHtml,
} from './constants'

function _buildFigureRegistry(images, extractions, content) {
  if (!Array.isArray(images)) return []

  // 1. 构建 extractions 按 source_image_id 索引（仍需要 caption / description / confidence）
  //    兼容三种字段名: sourceImageId (camelCase, _normalizeExtractions 输出)
  //                    source_image_id (snake_case, 后端原始)
  //                    "fig-N" 字符串 (figuresRaw 的 id)
  const extByImageId = {}
  for (const ex of (extractions || [])) {
    const sid = ex?.sourceImageId ?? ex?.source_image_id
    if (sid == null) continue
    extByImageId[sid] = ex
    extByImageId[String(sid)] = ex
    extByImageId[`fig-${sid}`] = ex
  }

  // 2. 扫描正文，识别每个 figureNo 出现的 page（仍用 figPages 增强 sectionHint）
  const figPages = _scanFigurePages(content)

  // ── v28 step 4 简化策略 ──
  // 后端 vision model 已输出 12 个结构化字段（figure_no / figure_type / is_core_figure /
  // is_publisher_image / section_hint / anchor_paragraph_index / anchor_text / vision_confidence ...）
  // 前端不再做正则推断，直接读字段。figure_no 20% 覆盖率由 anchor_text 反推补足。
  //
  // Graceful Degradation：当 vision model 不可用（旧数据 / vision 调用失败 / OCR-only 数据）
  // 时（所有 v28 字段都为 null），回退到旧的关键词推断 + L1 inference 兜底逻辑。
  // 这是渐进式演进：旧论文 + 旧测试 + 老用户数据不会爆。
  const result = images.map((img) => {
    const imgId = img.imageId ?? img.id
    const ext = extByImageId[imgId] || extByImageId[img.id] || {}
    const extData = ext.data || {}

    // ── 检测 vision model 是否可用 ──
    const visionAvailable = img.figureNo != null
      || img.figureType != null
      || img.isCoreFigure != null
      || img.isPublisherImage != null
      || img.sectionHint != null
      || img.visionConfidence != null

    // 3.1 figureNo: vision 优先 → anchor_text fallback → 旧 _extractFigureNo
    let figureNo = null
    let figureNoSource = null
    if (visionAvailable) {
      figureNo = img.figureNo ?? null
      if (figureNo) figureNoSource = 'vision'
      if (!figureNo && img.anchorText) {
        const m = img.anchorText.match(/\b(?:Fig\.?|Figure|Scheme|Table)\s*(\d{1,3}[a-z]?)\b/i)
        if (m) {
          figureNo = m[0]
          figureNoSource = 'anchor_fallback'
        }
      }
    } else {
      // 旧 fallback：6 字段正则提取
      figureNo = _extractFigureNoLegacy(img, ext)
      if (figureNo) figureNoSource = 'legacy_extracted'
    }

    // 3.2 figureType: vision 优先 → 旧 _inferFigureTypeV2
    let figureType
    if (visionAvailable) {
      figureType = img.figureType ?? 'figure'
    } else {
      figureType = _inferFigureTypeV2Legacy(img, ext)
    }

    // 3.3 isCoreFigure / isPublisherImage
    let isPublisherImage, isCoreFigure
    if (visionAvailable) {
      isPublisherImage = img.isPublisherImage === true
      isCoreFigure = img.isCoreFigure === true
    } else {
      isPublisherImage = ['cover', 'logo', 'publisher'].includes(figureType)
      const ocrText = _ocrTextOf(img)
      const hasContent = ocrText.length > 10 || (extData.description || '').length > 10
      isCoreFigure = !isPublisherImage && (figureType !== 'unknown' || hasContent)
    }

    // 3.4 sectionHint: vision 优先 → figPages fallback
    let sectionHint = img.sectionHint ?? null
    if (!sectionHint && figureNo && figPages[figureNo]) {
      const firstPage = figPages[figureNo][0]
      if (firstPage && img.page === firstPage) {
        sectionHint = `Page ${firstPage}`
      }
    }

    // 3.5 semanticTitle
    const semanticTitle = (extData.caption || extData.description || _ocrTextOf(img) || '')
      .split(/[.\n]/)[0]
      .slice(0, 80) || null

    // 3.6 anchor: 直接读 vision model 输出
    const anchor = (img.anchorParagraphIndex != null && figureNo)
      ? { paragraphIndex: img.anchorParagraphIndex, text: img.anchorText || null }
      : null

    return {
      id: img.imageId ?? img.id,
      imageId: img.imageId ?? img.id,
      rawId: img.id,
      src: img.src || img.imageUrl || img.image_url,
      page: img.page_number || img.page,
      figureNo,
      figureNoSource,
      figureType,
      isCoreFigure,
      isPublisherImage,
      isSupportingFigure: img.isSupportingFigure === true,
      caption: extData.caption || null,
      description: extData.description || null,
      ocrText: _ocrTextOf(img),
      semanticTitle,
      sectionHint,
      anchor,
      confidence: img.visionConfidence ?? ext.confidence ?? 0.5,
      visionModel: img.visionModelUsed ?? null,
      visualSummary: img.visualSummary ?? null,
    }
  })

  // ── L1 inference fallback: 仅当 vision 不可用时启用 ──
  // 给没有真实 figureNo 但 isCoreFigure 的图按 page 顺序兜底分配
  if (!images.some(img => img.figureNo != null || img.figureType != null)) {
    const knownFigNos = new Set()
    for (const fig of result) {
      if (fig.figureNo) {
        const m = fig.figureNo.match(/\d+/)
        if (m) knownFigNos.add(parseInt(m[0], 10))
      }
    }
    const coreFigList = result
      .filter(f => f.isCoreFigure)
      .sort((a, b) => {
        const pa = a.page || 0
        const pb = b.page || 0
        if (pa !== pb) return pa - pb
        return 0
      })
    const unassigned = coreFigList.filter(f => !f.figureNo)
    let nextFigNo = 1
    for (const fig of unassigned) {
      while (knownFigNos.has(nextFigNo)) nextFigNo++
      fig.figureNo = `Fig. ${nextFigNo}`
      fig.figureNoSource = 'inferred'
      knownFigNos.add(nextFigNo)
      nextFigNo++
    }
  }

  return result
}

/**
 * Helper: 兼容 normalizer 后的 ocrText 字段和原始 ocr_text 字段
 */
function _ocrTextOf(img) {
  return img?.ocrText || img?.ocr_text || ''
}

/**
 * v28 step 4: 旧 _extractFigureNo / _inferFigureTypeV2 重命名为 *Legacy，作为 Graceful Degradation
 *
 * 使用场景（_buildFigureRegistry 检测到 vision 字段全 null 时调用）：
 * - 老 PDF 数据（vision model 还未跑过）
 * - OCR-only 数据（没调 vision_service）
 * - vision 调用失败的图
 *
 * 设计原则：
 * - 主路径 100% 用后端 vision 输出（已上线 v28 step 1-3）
 * - 旧路径仅作向后兼容，新代码不要调用
 * - 不要扩展 Legacy 路径（已废弃），新论文走主路径
 */

/**
 * 从多字段提取 figureNo（Legacy，仅 Graceful Degradation 用）
 * 优先级: caption → text → description → content_text → ocr_text → page + order
 */
function _extractFigureNoLegacy(img, ext) {
  const extData = ext.data || {}

  const captionSources = [
    extData.caption,
    extData.title,
    extData.figure_no,
  ]
  for (const s of captionSources) {
    if (!s) continue
    const m = String(s).match(/\b(?:Fig\.?|Figure|Scheme|Table|图|表)\s*(\d{1,3}[a-z]?)\b/i)
    if (m) return m[0]
  }

  const textSources = [
    extData.text,
    extData.content,
    ext.content_text,
  ]
  for (const s of textSources) {
    if (!s) continue
    const m = String(s).match(/\b(?:Fig\.?|Figure|Scheme|Table)\s*(\d{1,3}[a-z]?)\b/i)
    if (m) return m[0]
  }

  const ocr = _ocrTextOf(img)
  if (ocr) {
    const m = ocr.match(/\b(?:Fig\.?|Figure|Scheme|Table)\s*(\d{1,3}[a-z]?)\b/i)
    if (m) return m[0]
  }

  return null
}

/**
 * Legacy figureType 推断（仅 Graceful Degradation 用）
 */
function _inferFigureTypeV2Legacy(img, ext) {
  const extData = ext.data || {}
  const ocr = _ocrTextOf(img).toLowerCase()
  const caption = String(extData.caption || '').toLowerCase()
  const description = String(extData.description || '').toLowerCase()
  const text = String(extData.text || '').toLowerCase()
  const allText = `${caption} ${description} ${text} ${ocr}`.slice(0, 2000)
  const imageUrl = String(img.src || img.imageUrl || img.image_url || '').toLowerCase()

  if (/elsevier|springer|wiley|copyright|©|all\s+rights\s+reserved|published\s+by|journal\s+of|contents|editorial\s+board|issn|isbn|doi\.org|sciencedirect/.test(allText)) {
    return 'publisher'
  }
  if (/cover|homepage/.test(allText)) return 'cover'
  if (/logo|watermark/.test(allText) || /logo/.test(imageUrl)) return 'logo'

  const pageNum = img.page_number || img.page
  if (pageNum === 1 && (!ocr || ocr.length < 50) && !description) {
    return 'cover'
  }

  const w = img.width || 0
  const h = img.height || 0
  if (w && h && (w < 60 || h < 60)) return 'logo'

  if (ext.kind === 'chart' ||
      /图表|热力图|柱状图|折线图|散点图|曲线图|条形图|饼图|分布图/.test(description) ||
      /\bchart\b|\bgraph\b|\bplot\b|\bcurve\b|\bheatmap\b|\bbar\s*chart\b|\bline\s*chart\b|\bscatter\b|\bhistogram\b/i.test(allText)) {
    return 'chart'
  }

  if (/^scheme\s*\d/i.test(caption) || /机制|示意|流程图|scheme|mechanism/.test(allText)) {
    return 'scheme'
  }

  if (/实验装置|experimental|setup|apparatus|设备/.test(allText)) {
    return 'experimental_setup'
  }

  if (/molecular|simulation|dft|分子/.test(allText)) {
    return 'molecular_simulation'
  }

  const hasFigNo = /\b(?:Fig\.?|Figure|Scheme|Table)\s*\d/i.test(allText)
  if (hasFigNo) return 'figure'

  if (ocr && ocr.length > 100) return 'figure'

  if (description && description.length > 30) return 'figure'

  return 'unknown'
}

/**
 * 扫描正文，识别每个 figureNo 出现的 page
 * 返回 { 'Fig. 1': [pages...], ... }
 */
function _scanFigurePages(content) {
  if (!content) return {}
  const result = {}
  // 简化：用 [PAGE:N] 标记分割
  const pageBlocks = String(content).split(/\[PAGE:\s*(\d+)\s*\]/i)
  for (let i = 1; i < pageBlocks.length; i += 2) {
    const page = parseInt(pageBlocks[i], 10)
    const text = pageBlocks[i + 1] || ''
    const figRefs = text.matchAll(/\b(?:Fig\.?|Figure|Scheme|Table)\s*(\d{1,3}[a-z]?)\b/gi)
    for (const m of figRefs) {
      const key = m[0]
      if (!result[key]) result[key] = []
      if (!result[key].includes(page)) result[key].push(page)
    }
  }
  return result
}

/**
 * 智能正文内嵌图锚定 (v27 升级版 - 段落级)
 *
 * 不再按"section 一次性插入所有引用图"，改为按"段落首次引用"锚定：
 *   - 每张图插入到正文里 FIRST 出现其图号的 paragraph 后面
 *   - 同一个 paragraph 可以锚定多张图（如果同时引用 Fig. 1 和 Fig. 2）
 *
 * 多级匹配策略：
 *   L1: 精确图号匹配 (Fig. 2 ↔ 正文 "Fig. 2")
 *   L2: caption 语义匹配 (caption keywords ∩ paragraph keywords)
 *   L3: sectionHint 辅助匹配 (后端提供)
 *   L4: 低置信度放弃内嵌
 *
 * 返回格式: { paragraphId → [figures] }
 *   paragraphId 格式: `${sectionId}__p${paragraphIndex}`
 *
 * 严格规则：
 * - 同一张图在整个 paper 只内嵌 1 次（first-reference-wins）
 * - isCoreFigure = false 的图（cover/logo/publisher）永远不内嵌
 * - 没有 figureNo 的图也不内嵌（不能机械按数组顺序）
 */
function _buildInlineFigureAnchors(sections, figureRegistry) {
  const anchors = {}  // paragraphId → [figure]
  if (!figureRegistry?.length || !sections?.length) return anchors

  // 1. 建立 figureNo → figure 映射（只包含 isCoreFigure + 有 figureNo）
  //    v28 step 13: 当多个图共用 figureNo（OCR 重复识别，如两张图都是 "Fig. 1"），
  //    保留 page 最小的作为 figureByNo 命中（视觉上 reader 滚到 page=1 看到第一张 "Fig. 1"）
  const figureByNo = {}
  for (const fig of figureRegistry) {
    if (!fig.isCoreFigure || !fig.figureNo) continue
    const key = fig.figureNo.toLowerCase()
    const existing = figureByNo[key]
    if (!existing || (fig.page || 0) < (existing.page || 0)) {
      figureByNo[key] = fig
      figureByNo[key.replace(/\s+/g, '')] = fig
    }
  }

  const placedFigures = new Set()  // 全局已放置

  // v28 step 28: 同一 paragraphId 内多张 fig 按 page 升序排
  //    之前 L1 收集 matched.push(fig) 顺序由 matchAll 决定, 与 page 无关
  //    现在最后按 page 排
  const sortByPage = (a, b) => (a.page || 9999) - (b.page || 9999)

  // 2. L1: 段落级图号精确匹配
  for (const section of sections) {
    if (!section.blocks) continue
    section.blocks.forEach((block, idx) => {
      if (block.type !== 'paragraph') return
      const text = block.content || ''
      const pid = `${section.id}__p${idx}`
      const figRefs = [...text.matchAll(/\b(?:Fig\.?|Figure|Scheme|Table|图|表)\s*(\d{1,3}[a-z]?)\b/gi)]
      const matched = []
      for (const m of figRefs) {
        const key = m[0].toLowerCase()
        const fig = figureByNo[key]
        if (!fig) continue
        if (placedFigures.has(fig.id)) continue
        matched.push(fig)
        placedFigures.add(fig.id)
      }
      if (matched.length > 0) {
        // v28 step 28: 同一段内 fig 按 page 升序排
        anchors[pid] = matched.slice().sort(sortByPage)
      }
    })
  }

  // 3. L2: caption 语义匹配 (Jaccard) - 处理 L1 未匹配且有 caption 的图
  //    阈值降到 0.05（v28 step 9：vision model 经常给空 caption，但 L1 已能捕获大部分，
  //    留 L2 兜底任何长文本图描述）
  const unmatchedFigures = figureRegistry.filter(
    f => f.isCoreFigure && !placedFigures.has(f.id)
  )
  if (unmatchedFigures.length > 0 && sections.length > 0) {
    const paragraphTokens = []
    for (const section of sections) {
      if (!section.blocks) continue
      section.blocks.forEach((block, idx) => {
        if (block.type !== 'paragraph') return
        paragraphTokens.push({
          pid: `${section.id}__p${idx}`,
          page: block.page || null,  // 段落所在页码
          tokens: _tokenize(block.content || ''),
        })
      })
    }

    for (const fig of unmatchedFigures) {
      const figTokens = _tokenize(fig.caption || fig.semanticTitle || '')
      // 没有 caption/semanticTitle 但有 page → 跳过 L2，交给 L3 按 page 插入
      if (figTokens.length === 0) continue

      let bestMatch = null
      let bestScore = 0
      for (const pt of paragraphTokens) {
        if (anchors[pt.pid]?.some(f => f.id === fig.id)) continue
        const score = _jaccard(figTokens, pt.tokens)
        if (score > bestScore) {
          bestScore = score
          bestMatch = pt
        }
      }

      // 阈值 0.05：极宽松，仅防完全无关的文本
      if (bestMatch && bestScore >= 0.05) {
        if (!anchors[bestMatch.pid]) anchors[bestMatch.pid] = []
        anchors[bestMatch.pid].push(fig)
        placedFigures.add(fig.id)
      }
    }
  }

  // 4. L3: 按 page 顺序 + 段落均匀分配（处理 vision model 没识别 figureNo 的图）
  //    改进（v28 step 12）：
  //    - 同 page 多张图分别插入不同段落（避免塞同一段）
  //    - 跳过 preamble 段（preamble 是元信息，不应插图）
  //    - 「该 page 内均匀分配 + 跨 page 时分配到 page 距离最近的段」
  const remainingFigures = figureRegistry.filter(
    f => f.isCoreFigure && !placedFigures.has(f.id) && f.page
  )
  if (remainingFigures.length > 0) {
    // 按 (page, id) 排序 — 稳定
    remainingFigures.sort((a, b) => {
      const dp = (a.page || 0) - (b.page || 0)
      return dp !== 0 ? dp : (a.id || 0) - (b.id || 0)
    })

    // 收集所有 paragraph block（跳过 preamble/highlights/abstract 等元信息 section）
    // v28 step 29: 加 references/acknowledgments/conclusion
    //    references: PaperSectionRenderer v-if="!isReferences" 不渲染 inline
    //    acknowledgments: 致谢段不该有正文图
    //    conclusion: 让 Fig. N 优先回到 results 段
    //    introduction: 段内 block.page=null=0，会被 fallback 误选
    const SKIP_SECTIONS = new Set(['preamble', 'highlights', 'keywords', 'abstract', 'article_info', 'references', 'acknowledgments', 'conclusion', 'introduction'])
    const allParagraphs = []  // [{pid, page}]
    const paragraphsByPage = {}
    for (const section of sections) {
      if (SKIP_SECTIONS.has(section.type)) continue
      if (!section.blocks) continue
      section.blocks.forEach((block, idx) => {
        if (block.type !== 'paragraph') return
        // v28 step 29c: 保留 page=0 段落进 allParagraphs（fallback 时按 page 排序优先选 page>=1）
        const pid = `${section.id}__p${idx}`
        const p = block.page || 0
        allParagraphs.push({ pid, page: p })
        if (p) {
          if (!paragraphsByPage[p]) paragraphsByPage[p] = []
          paragraphsByPage[p].push({ pid, page: p })
        }
      })
    }
    if (allParagraphs.length === 0) {
      return anchors
    }

    const sortedPages = Object.keys(paragraphsByPage).map(Number).sort((a, b) => a - b)

    for (const fig of remainingFigures) {
      // 找该 page 或 page 距离最近的段落
      let candidates = paragraphsByPage[fig.page]

      if (!candidates?.length) {
        // 找最近的 page
        let closestPage = null
        let minDist = Infinity
        for (const p of sortedPages) {
          const dist = Math.abs(p - fig.page)
          if (dist < minDist) {
            minDist = dist
            closestPage = p
          }
        }
        if (closestPage != null) candidates = paragraphsByPage[closestPage]
      }

      if (!candidates?.length) {
        // 极端 fallback：找第一个有 page 的段落
        if (allParagraphs[0]) candidates = [allParagraphs[0]]
        else continue
      }

      // v28 step 19: 每个 paragraph 最多 1 张图（之前均匀分配会塞 4 张图连发）
      //   优先选还没分配图的 paragraph
      //   跨 page 时：找 page 距离最近的"未占位"段落
      let target = null
      for (const p of candidates) {
        if (!anchors[p.pid] || anchors[p.pid].length === 0) {
          target = p
          break
        }
      }
      if (!target) {
        // 该 page 候选段落全被占 → 跳到下一个 page 的未占位段落
        const figPageIdx = sortedPages.indexOf(fig.page)
        for (let off = 1; off < sortedPages.length && !target; off++) {
          for (const dir of [1, -1]) {
            const idx = figPageIdx + dir * off
            if (idx < 0 || idx >= sortedPages.length) continue
            const nearbyPage = sortedPages[idx]
            const nearbyParas = paragraphsByPage[nearbyPage] || []
            for (const p of nearbyParas) {
              if (!anchors[p.pid] || anchors[p.pid].length === 0) {
                target = p
                break
              }
            }
            if (target) break
          }
        }
        if (!target) continue  // 真没位置了，放弃
      }

      if (!anchors[target.pid]) anchors[target.pid] = []
      anchors[target.pid].push(fig)
      placedFigures.add(fig.id)
    }
  }

  // v28 step 28: 完全重写 inline figure 分配
  //    不再依赖 L1 first-reference 匹配 (vision model 经常给错位 figureNo)
  //    改为: 按 page 升序遍历 fig, 给每张 fig 分配到 page >= fig.page 的最早未占用 paragraph
  //    跳过 preamble/highlights/abstract 等元信息 section
  // v28 step 29: 加 references/acknowledgments/conclusion（user 报告 Fig. 8 漏显示 - 分配到 references 段）
  // v28 step 29b: 加 introduction（Introduction 段没 page_marker 继承，block.page=null=0，
  //   fallback 选 page=0 段（Introduction）导致 Fig. 8 落到 Introduction 段第 1 位）
  // v28 step 29c: 保留 page=0 段落进 allParagraphs，但 fallback 时按 page 排序优先选 page>=1 的段
  //   之前 1885 处用 if (!block.page) return 跳过 page=0 段落 → 8 张 fig 时 Fig. 8 找不到段落 → DOM 只 7 张
  const SKIP_SECTIONS = new Set(['preamble', 'highlights', 'keywords', 'abstract', 'article_info', 'references', 'acknowledgments', 'conclusion', 'introduction'])
  const allParagraphs = []  // [{pid, page, idx}]
  for (const section of sections) {
    if (SKIP_SECTIONS.has(section.type)) continue
    if (!section.blocks) continue
    section.blocks.forEach((block, idx) => {
      if (block.type !== 'paragraph') return
      allParagraphs.push({
        pid: `${section.id}__p${idx}`,
        page: block.page || 0,  // page=0 表示无 page 信息，分配优先级最低
      })
    })
  }
  if (allParagraphs.length === 0) return anchors

  // 收集所有 core figs 按 page 升序, 同 page 按 id 升序
  const allCoreFigs = figureRegistry
    .filter(f => f.isCoreFigure && f.page)
    .sort((a, b) => (a.page || 0) - (b.page || 0) || (a.id || 0) - (b.id || 0))

  // 简化策略: 收集所有 fig, 然后给每张 fig 分配到 page >= fig.page 的最早未占用 paragraph
  const newAnchors = {}
  const usedPids = new Set()
  for (const fig of allCoreFigs) {
    // v28 step 29d 改: 允许同一 paragraph 复用（多张 fig 共用一段）
    //    之前: usedPids 检查让 Fig. 8 永远找不到段落（所有 page>=1 段都被前 7 张占用）
    //    现在: 移除 usedPids 概念，每张 fig 独立按 page closest 选段落
    //    同一段多张图在 DOM 上是堆叠（acceptable for paper reader）
    let bestPara = null
    let bestDelta = Infinity
    for (const p of allParagraphs) {
      // 优先 page >= 1 段（真实正文段），page=0 段优先级最低
      const realDelta = Math.abs((p.page || 0) - (fig.page || 0))
      const delta = (p.page || 0) === 0 ? realDelta + 1000 : realDelta
      if (delta < bestDelta) {
        bestPara = p
        bestDelta = delta
      }
    }
    if (!bestPara) continue  // 实在没位置

    if (!newAnchors[bestPara.pid]) newAnchors[bestPara.pid] = []
    newAnchors[bestPara.pid].push(fig)
    // v28 step 29d: 不再 usedPids.add(bestPara.pid) —— 允许同段多张 fig
  }

  return newAnchors
}

/**
 * 兼容旧 API: 把 paragraph anchors 合并到 section 级
 * 注意: 实际渲染应使用 inlineFigureAnchors (paragraph 级) 而非 inlineFigureMap (section 级)
 */
function _buildInlineFigureMap(sections, figureRegistry, content) {
  const paragraphAnchors = _buildInlineFigureAnchors(sections, figureRegistry)
  const map = {}
  for (const [pid, figures] of Object.entries(paragraphAnchors)) {
    const sectionId = pid.split('__')[0]
    if (!map[sectionId]) map[sectionId] = []
    map[sectionId].push(...figures)
  }
  return map
}

/**
 * 文本 → 去停用词 + 长度过滤的关键词数组
 */
function _tokenize(text) {
  if (!text) return []
  return String(text)
    .toLowerCase()
    .replace(/[^\w一-龥]+/g, ' ')
    .split(/\s+/)
    .filter(t => t.length > 2 && !STOPWORDS.has(t))
}

const STOPWORDS = new Set([
  'the', 'and', 'for', 'with', 'that', 'this', 'from', 'are', 'was', 'were',
  'has', 'have', 'had', 'been', 'will', 'would', 'could', 'should', 'may',
  'can', 'does', 'did', 'not', 'but', 'all', 'any', 'one', 'two', 'three',
  'into', 'than', 'then', 'more', 'most', 'some', 'such', 'only', 'also',
  'fig', 'figure', 'scheme', 'table', 'shown', 'show', 'shows', 'see',
  '的', '了', '和', '与', '或', '在', '是', '为', '有', '与', '及',
])

/**
 * Jaccard 相似度: |A ∩ B| / |A ∪ B|
 */
function _jaccard(a, b) {
  if (!a.length || !b.length) return 0
  const setA = new Set(a)
  const setB = new Set(b)
  let inter = 0
  for (const t of setA) if (setB.has(t)) inter++
  const union = setA.size + setB.size - inter
  return union === 0 ? 0 : inter / union
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


// ============================================================
// v28 step 109.37: 关键词中英翻译
// ============================================================
//
// 原文 PDF 的 Keywords 段通常是英文（Elsevier 期刊标准格式）：
//   Keywords:
//   Micro-nano bubbles
//   Hydrogen peroxide
//   Toluene oxidation
//   Active species
//   Interfacial mass transfer
//
// 但数据库 tags 字段经常被中文标注（运维录入 / LLM 抽取）。
// 用户要求关键词也用英文显示，所以：
//   1. 优先直接从原文 content 抽 "Keywords:" 后英文列表（原文权威）
//   2. 兜底把中文 tags 通过映射表翻译成英文
//   3. 已经是英文的关键词不动（保持原样）
//
// ============================================================

// 关键词中文 → 英文 映射表（按学科领域扩展：水处理 / 高级氧化 / 微纳米气泡）
const KEYWORD_ZH_TO_EN = {
  // 微纳米气泡领域
  '微纳米气泡': 'Micro-nanobubbles',
  '微纳米气泡技术': 'Micro-nanobubble technology',
  '纳米气泡': 'Nanobubbles',
  '微气泡': 'Microbubbles',
  '超细气泡': 'Ultrafine bubbles',
  '臭氧微纳米气泡': 'Ozone micro-nanobubbles',

  // 氧化剂
  '臭氧': 'Ozone',
  '过氧化氢': 'Hydrogen peroxide',
  '羟基自由基': 'Hydroxyl radical',
  '超氧自由基': 'Superoxide radical',
  '超氧阴离子': 'Superoxide anion',
  '单线态氧': 'Singlet oxygen',
  '活性氧物种': 'Reactive oxygen species',
  '活性氧': 'Reactive oxygen species',
  '活性物种': 'Reactive species',
  '过硫酸盐': 'Persulfate',
  '高锰酸钾': 'Permanganate',

  // 工艺与机理
  '高级氧化': 'Advanced oxidation',
  '高级氧化工艺': 'Advanced oxidation processes',
  '高级氧化技术': 'Advanced oxidation technology',
  '臭氧氧化': 'Ozonation',
  '催化臭氧氧化': 'Catalytic ozonation',
  '湿式氧化': 'Wet air oxidation',
  '芬顿': 'Fenton',
  '光催化': 'Photocatalysis',
  '电催化': 'Electrocatalysis',
  '无催化剂': 'Catalyst-free',
  '催化剂': 'Catalyst',
  '催化': 'Catalysis',
  '氧化': 'Oxidation',
  '降解': 'Degradation',
  '矿化': 'Mineralization',

  // 反应物
  '甲苯': 'Toluene',
  '甲苯氧化': 'Toluene oxidation',
  '苯': 'Benzene',
  '酚': 'Phenol',
  '挥发性有机物': 'Volatile organic compounds',
  '挥发性有机化合物': 'Volatile organic compounds',
  'VOCs': 'Volatile organic compounds',
  '有机污染物': 'Organic pollutants',
  '污染物': 'Pollutants',

  // 物理化学
  '传质': 'Mass transfer',
  '气液传质': 'Gas-liquid mass transfer',
  '气液界面': 'Gas-liquid interface',
  '界面': 'Interface',
  '界面反应': 'Interfacial reaction',
  '界面效应': 'Interfacial effect',

  // 应用领域
  '水处理': 'Water treatment',
  '废水处理': 'Wastewater treatment',
  '污水处理': 'Wastewater treatment',
  '饮用水处理': 'Drinking water treatment',
  '地下水修复': 'Groundwater remediation',
  '环境修复': 'Environmental remediation',

  // 通用
  '动力学': 'Kinetics',
  '反应动力学': 'Reaction kinetics',
  '机理': 'Mechanism',
  '反应机理': 'Reaction mechanism',
  '反应路径': 'Reaction pathway',
  '密度泛函理论': 'Density functional theory',
  'DFT计算': 'DFT calculation',
  '分子动力学': 'Molecular dynamics',
  '自由基': 'Radical',
  '中间体': 'Intermediate',
  '液相': 'Liquid phase',
  '气相': 'Gas phase',
  '水溶液': 'Aqueous solution',
  '水相': 'Aqueous phase',
  '转化率': 'Conversion',
  '选择性': 'Selectivity',
  '稳定性': 'Stability',
  '经济分析': 'Economic analysis',
}

// 检测是否含中文（CJK Unified Ideographs）
function _hasChineseChars(text) {
  if (!text) return false
  return /[一-鿿]/.test(text)
}

/**
 * 把单个关键词翻译成英文（如果它是中文）
 * - 已经是英文 / 数字 / 公式 → 原样返回
 * - 完全匹配映射表 → 翻译
 * - 子串匹配（如 "微纳米气泡技术" 含 "微纳米气泡"）→ 翻译成 "Micro-nanobubble technology"
 *   （即在映射表最长 key 命中时优先用最长 key 的翻译，否则通用翻译）
 * - 都不命中 → 原样返回
 *
 * @param {string} kw
 * @returns {string}
 */
function _translateKeywordToEnglish(kw) {
  if (!kw || typeof kw !== 'string') return kw
  const trimmed = kw.trim()
  if (!trimmed) return trimmed
  // 已经是英文 / 不含中文 → 原样
  if (!_hasChineseChars(trimmed)) return trimmed

  // 1. 完全匹配
  if (KEYWORD_ZH_TO_EN[trimmed]) {
    return KEYWORD_ZH_TO_EN[trimmed]
  }

  // 2. 子串匹配：按 key 长度倒序，优先用更长的 key 匹配（避免 "微纳米气泡" 抢匹配 "微纳米气泡技术"）
  const keys = Object.keys(KEYWORD_ZH_TO_EN).sort((a, b) => b.length - a.length)
  for (const k of keys) {
    if (trimmed.includes(k)) {
      // 整词翻译 + 保留余下部分（如 "过氧化氢氧化" → "Hydrogen peroxide oxidation"）
      const remainder = trimmed.replace(k, '').trim()
      const translated = KEYWORD_ZH_TO_EN[k]
      if (!remainder) return translated
      // 余下部分递归翻译（处理复合关键词）
      const remainderTranslated = _translateKeywordToEnglish(remainder)
      // 如果余下部分翻译成功（不是原样返回），组合；否则保留原文
      if (remainderTranslated !== remainder) {
        return `${translated} ${remainderTranslated}`
      }
      return `${translated} ${remainder}`
    }
  }

  // 3. 不匹配：原样返回
  return trimmed
}

/**
 * 把关键词数组批量翻译
 * - 去重（保留首次出现的翻译结果）
 * - 过滤空字符串
 *
 * @param {Array<string>} keywords
 * @returns {Array<string>}
 */
function _translateKeywordsToEnglish(keywords) {
  if (!Array.isArray(keywords)) return []
  const seen = new Set()
  const result = []
  for (const kw of keywords) {
    if (!kw || typeof kw !== 'string') continue
    const translated = _translateKeywordToEnglish(kw)
    if (!translated) continue
    // 去重：标准化小写比较
    const key = translated.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    result.push(translated)
  }
  return result
}

// 导出供单元测试 + 调试用
const translateKeywordToEnglish = _translateKeywordToEnglish
const translateKeywordsToEnglish = _translateKeywordsToEnglish
const extractAuthorsAndJournal = _extractAuthorsAndJournal
export { KEYWORD_ZH_TO_EN }


// ============================================================
// v28 step 109.38: 作者 + 期刊 + 机构 提取
// ============================================================
//
// PDF 原文典型格式（Elsevier）：
//   Tianzhi Wang a, Hangjia Zhao a, Yongtao Li a, Ziyue Jiang b, ...
//   ,
//   Fawei Lin a,*
//   a School of Environmental Science and Engineering, Tianjin University/...
//   b College of energy environment and safety engineering, China Jiliang University, ...
//   c State Scientific Institution, Institute of General and Inorganic Chemistry of ...
//
// 期刊头（页眉反复出现，常见 Elsevier）：
//   T. Wang et al.
//   Journal of Hazardous Materials 513 (2026) 142456
//
// 提取策略：
// 1. 作者行：1 个或多个 "Name [a-z]" 用逗号分隔（可能含 * 对应通讯作者）
// 2. 机构行：以小写字母 + 空格开头的段落（OCR 可能跨行）
// 3. 期刊头：含 "Journal of" + 卷期号 + DOI 标识
//
// 返回结构：
//   {
//     authors: [{name, affiliation, isCorresponding}],
//     affiliations: [{id, name}],
//     journal: {name, volume, year, articleId},
//     doi: '10.1016/j.jhazmat.2026.142456'
//   }

// 期刊白名单（按需扩展）+ 通用正则
const KNOWN_JOURNALS = [
  'Journal of Hazardous Materials',
  'Chemical Engineering Journal',
  'Water Research',
  'Environmental Science & Technology',
  'Environmental Science and Technology',
  'Science of the Total Environment',
  'Separation and Purification Technology',
  'Chemosphere',
  'Applied Catalysis B: Environmental',
  'Chemical Engineering Science',
  'Journal of Cleaner Production',
  'Bioresource Technology',
  'Journal of Water Process Engineering',
  'Process Safety and Environmental Protection',
  'Journal of Environmental Chemical Engineering',
  'Environmental Pollution',
]

/**
 * 从原文 content 抽作者行 + 机构行 + 期刊头
 * 容错：
 *   - 作者行可能跨页（OCR 软换行）
 *   - 机构行可能多个 \n 连接
 *   - 期刊头只在第一页 + 后续页眉出现（取第一个）
 *
 * @param {string} content
 * @returns {{
 *   authors: Array<{name:string, affiliation:string, isCorresponding:boolean}>,
 *   affiliations: Array<{id:string, name:string}>,
 *   journal: {name:string|null, volume:string|null, year:string|null, articleId:string|null, fullCitation:string|null},
 *   doi: string|null
 * }}
 */
function _extractAuthorsAndJournal(content) {
  const empty = {
    authors: [],
    affiliations: [],
    journal: { name: null, volume: null, year: null, articleId: null, fullCitation: null },
    doi: null,
  }
  if (!content) return empty

  // === 1. 期刊头提取（多模式） ===
  let journalInfo = { name: null, volume: null, year: null, articleId: null, fullCitation: null }
  // 模式 A: 已知期刊名（优先匹配，更可靠）
  for (const jName of KNOWN_JOURNALS) {
    const esc = jName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    // 期刊名 + 卷 + 年份 + 文章号
    const re = new RegExp(`(${esc})(?:\\s+(\\d{2,4}))(?:\\s*\\((\\d{4})\\))?\\s+(\\d{4,8})?`)
    const m = content.match(re)
    if (m) {
      journalInfo = {
        name: jName,
        volume: m[2] || null,
        year: m[3] || null,
        articleId: m[4] || null,
        fullCitation: [jName, m[2], m[3] ? `(${m[3]})` : '', m[4]].filter(Boolean).join(' '),
      }
      break
    }
  }
  // 模式 B: 通用（Journal of XXX / Letters in XXX / Reviews of XXX）
  if (!journalInfo.name) {
    // 通用正则：JOURNAL_KEYWORD + in/of + 名 + 卷(1-4 位) + 年(4位) + 文章号
    const re = /((?:Journal|Reviews?|Letters|Advances|Proceedings)\s+(?:of|in|on)\s+[A-Z][A-Za-z&'\- ]+?)\s+(\d{1,4})\s*\((\d{4})\)\s*(\d{1,8})/
    const m = content.match(re)
    if (m) {
      journalInfo = {
        name: m[1].trim(),
        volume: m[2],
        year: m[3],
        articleId: m[4],
        fullCitation: `${m[1].trim()} ${m[2]} (${m[3]}) ${m[4]}`,
      }
    }
  }

  // === 2. DOI 提取 ===
  let doi = null
  const mDoi = content.match(/(?:https?:\/\/(?:dx\.)?doi\.org\/|doi\.org\/|\bDOI\s*[:：]\s*)(10\.\d{4,9}\/[-._;()\/:A-Z0-9]+)/i)
  if (mDoi) doi = mDoi[1]

  // === 3. 作者 + 机构提取 ===
  //   策略：找 content 中第一个 author 模式（"Name Name [a-z]"），从那开始
  //   抽 authors 直到遇到非 author 模式（机构关键词 "School/University/..."）
  //   然后抽 affiliations 直到 HIGHLIGHTS / ARTICLE INFO / ABSTRACT 等元数据
  const authors = []
  const affiliations = []

  try {
    // 步骤 3.1：定位 author block 起点 + 终点
    //   起点：第一个 author pattern
    //   终点：第一个机构关键词或元数据标记

    // author pattern 起点：
    //   优先匹配带 aff marker 的（"CapitalName CapitalName [a-z]"），这通常是 author 行
    //   兜底匹配无 aff 的（用于单作者论文），但放在后面避免误吸 title
    //   按行扫描，避免 title 误吸（title 通常较短且不含 [a-z] aff marker）
    const TITLE_BLOCK_KEYWORDS = /\b(?:Title|Paper|Article|Abstract|Introduction|Conclusion|Background|Overview|Review|Study|Keywords?|Highlights|ARTICLE|ABSTRACT|HIGHLIGHTS|Keywords)\b/i

    // 按行扫描：找到第一个"作者行"
    // 1) 优先匹配带 aff 的行
    // 2) 检查该行不含 title 关键词
    // 3) 检查该行至少 2 个 "CapitalName" token
    const lines = content.split('\n')
    let startIdx = -1
    for (let i = 0; i < Math.min(lines.length, 50); i++) {
      const line = lines[i].trim()
      if (!line) continue
      // 跳过 markdown blockquote (>) 和 image markdown (![]) — 这些是图表说明/图片 alt，不是作者
      if (line.startsWith('>') || line.startsWith('!')) continue
      // 含 title 关键词 → 跳过
      if (TITLE_BLOCK_KEYWORDS.test(line)) continue
      // 含 aff marker 的 author 行（最稳的识别）
      if (/[A-Z][a-zà-ÿ'-]+\s+[A-Z][a-zà-ÿ'-]+\s+[a-z]\b/.test(line)) {
        startIdx = content.indexOf(line)
        break
      }
      // 兜底：无 aff 的 author 行（单作者）
      //   要求：①非首行 ②只匹配 2 个 CapitalName（防止误匹配图表描述）
      if (i > 0 && /^[A-Z][a-zà-ÿ'-]+\s+[A-Z][a-zà-ÿ'-]+\s*$/.test(line)) {
        startIdx = content.indexOf(line)
        break
      }
    }
    if (startIdx < 0) {
      return { authors, affiliations, journal: journalInfo, doi }
    }

    // 终点：找第一个机构关键词或元数据标记
    //   元数据标记：HIGHLIGHTS / A B S T R A C T (OCR) / ARTICLE INFO / [PAGE:
    //   机构关键词：School / College / University / Institute 等（小写字母开头）
    const endMarkers = [
      /\n\s*(?:H\s*I\s*G\s*H\s*L\s*I\s*G\s*H\s*T\s*S|A\s*R\s*T\s*I\s*C\s*L\s*E|ARTICLE\s+INFO|Highlights|A\s*B\s*S\s+T\s*R\s*A\s*C\s*T|ABSTRACT|Keywords|关键词|\[\s*PAGE)/i,
      // 也匹配机构关键词（lowercase + School/University 等），用于分隔
      // 但这是 STRICT 匹配，避免误伤（OCR 里 School/University 一定紧跟 lowercase 字母）
    ]
    let endIdx = content.length
    for (const re of endMarkers) {
      const m = content.match(re)
      if (m && m.index > startIdx && m.index < endIdx) endIdx = m.index
    }

    // author + affiliation 块（不限定长短）
    const block = content.slice(startIdx, endIdx)

    // 步骤 3.2：合并软换行 + 清理
    const cleaned = block.replace(/\n+/g, ' ').replace(/\s+/g, ' ').trim()

    // 步骤 3.3：抽 authors
    //   模式：Name(s) + 空格 + [a-z] + 可选 * (通讯作者)
    //   终止：name 含机构关键词 OR name 前一个词是 "of/the/and/for" 等介词
    const INSTITUTION_KEYWORDS = /(?:School|College|Institute|Academy|Department|State\s+Scientific|Faculty|Key\s+Lab|Laboratory|Hospital|Center\s+for|Center\s+of|Tianjin\s+University|China\s+Jiliang)/
    const GENERIC_PREPOSITION = /^(?:of|the|for|and|in|on|at|by|with|via|from|to|de|la|le|is|are|has|have)$/i
    // 放宽：支持无 affiliation marker 的 author（仅 Name Name）
    //   同时支持 "Fawei Lin a,*" 这种行尾 * 标记
    //   用 lookahead 检查 match 末尾 8 字符内是否有 *
    const authorRegex = /([A-Z][a-zà-ÿ'-]+(?:\s+[A-Z][a-zà-ÿ'-]+){1,3})(?:\s+([a-z]))?\s*,?(\*?)(?=\s|,|$)/g
    let mAuth
    while ((mAuth = authorRegex.exec(cleaned)) !== null) {
      const name = mAuth[1].trim()
      const aff = mAuth[2] || null
      const isCorresponding = mAuth[3] === '*'
      // 要求至少有 affiliation marker 或者连续多个无 aff 的 author（单作者论文）
      if (!aff && authors.length > 0) {
        break
      }
      // 1. name 含机构关键词 → 停止
      if (INSTITUTION_KEYWORDS.test(name)) break
      // 1.5. name 任意词是 title 关键词 → 停止（说明把 title 误当 author）
      const TITLE_KEYWORDS = /\b(?:Title|Paper|Article|Abstract|Introduction|Conclusion|Background|Overview|Review|Study)\b/i
      if (TITLE_KEYWORDS.test(name)) continue
      // 2. 前一个词是介词 → 这是机构名一部分
      const contextBefore = cleaned.slice(Math.max(0, mAuth.index - 30), mAuth.index)
      const lastWordMatch = contextBefore.match(/\b([a-zA-Z]+)\s*$/)
      if (lastWordMatch && GENERIC_PREPOSITION.test(lastWordMatch[1])) continue
      authors.push({
        name,
        affiliation: aff || '?',
        isCorresponding,
      })
    }

    // 步骤 3.4：抽 affiliations（在同一 block 内）
    //   模式：[a-z] + 空格 + 机构关键词 + 内容（到下一个机构 marker 或元数据标记前）
    //   找到所有 "a School of..." / "b College of..." / "c State..."
    //   不要求结尾 "."，因为 OCR 可能跨多行
    // 简化版：只匹配到第一个逗号或元数据标记前
const affRegex = /([a-z])\s+(School\s+of[^,]+|College\s+of[^,]+|Institute\s+of[^,]+|Academy\s+of[^,]+|Department\s+of[^,]+|State\s+[^,]+|Faculty\s+of[^,]+|Research\s+of[^,]+|Laboratory\s+of[^,]+|Hospital\s+[^,]+|University\s+of[^,]+|[A-Z][a-z]+\s+University[^,]+)/g
    let mAff
    // 限制最大机构数为 authors 中实际用到的 aff 数量 + 1（避免误匹配）
    const maxAffs = (authors.length ? new Set(authors.map(a => a.affiliation)).size : 10)
    while ((mAff = affRegex.exec(cleaned)) !== null) {
      if (affiliations.length >= maxAffs) break
      const id = mAff[1]
      const name = mAff[2].trim().replace(/\s+/g, ' ')
      if (!affiliations.find(a => a.id === id)) {
        affiliations.push({ id, name })
      }
    }
  } catch (e) {
    if (typeof console !== 'undefined') console.warn('[extractAuthorsAndJournal] error:', e)
  }

  return {
    authors,
    affiliations,
    journal: journalInfo,
    doi,
  }
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
function matchFiguresWithCaptions(figures, extractions, content) {
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

  // 3. 给每个 figure 分配 caption + figureNo
  //    === v26 回归修复 ===
  //    之前版本对所有图片按 idx+1 机械分配 "Fig. N"，导致 Elsevier logo 也被叫 Fig. 1。
  //    现在按图类型分级：
  //    - cover / logo / publisher / unknown: figureNo = null（不进正文）
  //    - 有真实 caption/OCR 含图号: 用真实图号（Fig. 5）
  //    - 否则: 在 isCoreFigure 子数组内按顺序分配 Fig. 1, Fig. 2, ...
  let coreCounter = 0
  return figures.map((fig, idx) => {
    const figIdx = idx + 1
    let caption = captionsByFigureId[fig.imageId || fig.id] || null
    if (!caption && captionsByFigIdx[figIdx]) {
      caption = captionsByFigIdx[figIdx]
    }

    // 判断是否核心图（默认 true，旧代码兼容性）
    const figureType = fig.figureType || null
    const isPublisherImage = !!fig.isPublisherImage
    const isCoreFigure = fig.isCoreFigure !== undefined ? !!fig.isCoreFigure : true
    const isCoverLike = isPublisherImage
      || ['cover', 'logo', 'publisher', 'unknown'].includes(figureType)

    let figureNo = null
    if (isCoverLike) {
      // 封面/logo/publisher/unknown 不进正文，figureNo = null
      figureNo = null
    } else {
      // 尝试从 caption 提取真实图号
      const capText = caption || fig.ocrText || ''
      const m = capText.match(/\b(?:Fig\.?|Figure|Scheme|Table)\s*(\d{1,3}[a-z]?)\b/i)
      if (m) {
        // 还原成 "Fig. N" 形式
        const prefix = m[0].match(/Fig\.?|Figure|Scheme|Table/i)?.[0] || 'Fig.'
        figureNo = `${prefix} ${m[1]}`
      } else {
        // 否则按核心图子数组顺序分配
        coreCounter += 1
        figureNo = `Fig. ${coreCounter}`
      }
    }

    return {
      ...fig,
      caption,
      figureNo,
      // 同时回填分类字段，方便下游使用
      figureType: figureType || (isCoverLike ? 'unknown' : 'figure'),
      isCoreFigure: !isCoverLike,
      isPublisherImage,
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
function classifyImageKind(image) {
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
function buildAnchorTree(sections, options = {}) {
  if (!Array.isArray(sections)) return { sections: [], modules: [] }
  const { moduleCounts = {} } = options

  // v28 step 96: 子章节继承父级 type
  //   场景：OCR 把 "2. Materials and methods"（type=methods）后的子章节
  //   "2.3. Experimental" / "2.4. Statistical analysis" 识别为 normal（typeLabelMap 无）
  //   → 右侧导航显示 "2.3. Experimental" 没 "材料与方法 ·" 前缀，看起来像丢失父级
  //   修复：扫描 sections 数组，遇到 normal + level >= 2 时，向上找最近的 methods/results/discussion 等父 type 并继承
  const INHERITABLE_TYPES = new Set(['methods', 'results', 'discussion', 'introduction', 'conclusion'])
  const sectionAnchors = sections
    .filter(s => s && s.title)
    .map((s, idx, arr) => {
      let displayType = s.type
      if ((s.type === 'normal' || !s.type) && (s.level || 1) >= 2) {
        // 向上查找最近的 INHERITABLE_TYPES 父级
        for (let i = idx - 1; i >= 0; i--) {
          const parent = arr[i]
          if (parent && INHERITABLE_TYPES.has(parent.type)) {
            displayType = parent.type
            break
          }
          // 遇到更高 level 的章节（继续向上）
          if (parent && parent.level && parent.level < (s.level || 1)) break
        }
      }
      return {
        id: s.id,
        title: s.title,
        type: displayType,
        level: s.level || 1,
        anchor: `section-${s.id}`,
      }
    })

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

/**
 * v28 step 20 + 21: 数字 → Unicode 上角标字符
 * "12" → "¹²"（用户原话：'[12] 这样的文献引用序号要用上角标'）
 * v28 step 21: 整个 [N] 包含方括号也变上角标（标准格式 [⁵,⁶] 而非 [⁵,⁶]）
 */
function _toSuperscript(s) {
  if (!s) return ''
  const map = {
    '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
    '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
    '-': '⁻', '+': '⁺', ',': '͵', ' ': ' ', '–': '–',
    '[': '⁽', ']': '⁾',  // v28 step 21: 方括号也转上角标
  }
  return String(s).split('').map(c => map[c] || c).join('')
}

function autoLinkContent(text) {
  if (!text) return ''
  let escaped = _escapeHtml(text)

  // v28 step 20 + 21: 引用序号 [12] / [12, 15] / [12-15] → 整个上角标 Unicode
  //   v28 step 21 改进：方括号 [ ] 也转上角标 (⁽ ⁾)
  //   限制：仅匹配 [N] / [N,M] / [N-M] 格式，数字 1-4 位（避免误伤 [12.5] 等）
  //   必须在 DOI 规则前处理（[12] 也可能被误判为 DOI 部分）
  escaped = escaped.replace(
    /\[(\d{1,4}(?:\s*[,–-]\s*\d{1,4})*)\]/g,
    (m, nums) => _toSuperscript(`[${nums}]`)
  )

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

// ---- 本段对外导出（供下游段 import，勿删）----
export { matchFiguresWithCaptions }
export { classifyImageKind }
export { buildAnchorTree }
export { autoLinkContent }
export { _buildFigureRegistry }
export { _buildInlineFigureAnchors }
export { _buildInlineFigureMap }
export { _detectKeywordsFromContent }
export { _extractAuthorsAndJournal }
export { _translateKeywordsToEnglish }
// 三个转发别名（原 L2952-2954 `export const X = _X`）：对外公开 API 面的一部分，
// 测试直接 import 它们。声明处与底层定义处相隔约 113 行，搬迁时最易配错。
export { translateKeywordToEnglish, translateKeywordsToEnglish, extractAuthorsAndJournal }
