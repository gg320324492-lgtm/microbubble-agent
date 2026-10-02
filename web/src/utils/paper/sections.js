// 章节解析与段落处理：parsePaperSections / 段落拆分 / OCR 行合并。
import { REFERENCE_ENTRY_RE, _genId } from './constants'
import { _matchSectionTitle } from './content'
import { _cleanText } from './qa'

function parsePaperSections(content, options = {}) {
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

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const trimmed = line.trim()

    // v28 step 42: Markdown 表格检测（在 _parseMarkdownSections 也加，
    //   因为 formatted_content 走 parsePaperSections 路径，没表格检测就不会输出 table block）
    if (trimmed.startsWith('|') && trimmed.endsWith('|') && i + 1 < lines.length) {
      const nextLine = lines[i + 1].trim()
      if (/^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$/.test(nextLine)) {
        // 收集表头 + 分隔 + 所有数据行
        const tableLines = [line]
        let j = i + 1
        while (j < lines.length) {
          const cur = lines[j].trim()
          if (cur.startsWith('|') && cur.endsWith('|')) {
            tableLines.push(lines[j])
            j++
          } else if (cur === '') {
            break
          } else {
            break
          }
        }
        // 表格前可能累积了 paragraphBuf，先 flush
        flushParagraph()
        if (!current) current = { id: 'preamble', title: '前言', type: 'preamble', blocks: [] }
        current.blocks.push({
          type: 'table',
          content: tableLines.join('\n'),
        })
        i = j - 1
        continue
      }
    }

    const headingMatch = /^(#{1,4})\s+(.+)$/.exec(line)
    if (headingMatch) {
      pushCurrent()
      const level = headingMatch[1].length
      const title = headingMatch[2].trim()
      const matched = _matchSectionTitle(title)
      // v28 step 104: H1（论文主标题，level=1）必须归类为 preamble
      //   旧逻辑：H1 title 不匹配任何 SECTION_KEYWORDS → type='normal'
      //   后果：preamble 段被 SKIP_SECTIONS 跳过过滤 → 8 张图 L3/L4 fallback 全塞到 preamble 段
      //   （用户报告："图片都挤到最前面了，而且都连在一起了"）
      //   修复：H1（level=1）无条件归类为 preamble（论文主标题永远不是 Introduction/Methods 等章节）
      const sectionType = (level === 1)
        ? 'preamble'
        : (matched?.type || 'normal')
      current = {
        id: _genId('s'),
        title,
        level,
        type: sectionType,
        blocks: [],
      }
      continue
    }
    // v28 step 103: 空行 = 段落分隔符（Markdown 规范）
    //   LLM reformat 输出的 formatted_content 用 `\n\n` 分段（如 "Table 1.\n\n(1) To investigate..."）
    //   旧逻辑只在 line.trim() 真值时 push paragraphBuf，遇到空行不 flush，
    //   导致后续内容累积到同一 paragraph，最后 join('\n') 丢失段落边界
    if (!trimmed) {
      if (!current) {
        // preamble 阶段空行：忽略（preamble 最终会合并成单个 block）
      } else {
        flushParagraph()  // 当前段落结束，开始下一段
      }
      continue
    }
    // 第一个标题之前累积为 preamble
    if (!current) {
      preambleBuf.push(line)
    } else {
      paragraphBuf.push(line)
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
  // v28 fix: 先按 \n\n 分段（PDF OCR 输出保留段间空行，是最自然的段落边界）
  // 然后在每个段内再切 [PAGE:N] 标记 — 这样一段对应 PDF 一段
  // v28 step 12 改进：先确保 [PAGE:N] 前后有换行符（OCR 有时把 PAGE 行黏在文字后）
  //    否则 split(/\n\s*\n+/) 会把 [PAGE:N] 吞进前后 paragraph，page 信息丢失
  content = content
    .replace(/([^\n])(\[PAGE:\s*\d+\s*\])/g, '$1\n$2')
    .replace(/(\[PAGE:\s*\d+\s*\])([^\n])/g, '$1\n$2')

  const paragraphs = content.split(/\n\s*\n+/)

  // 保留 [PAGE:N] 独立成行（不再合并到前一行末尾）
  const lines = []
  for (const para of paragraphs) {
    const paraLines = para.split('\n')
    for (const l of paraLines) {
      lines.push(l)
    }
    lines.push('')  // 段间用空行分隔
  }

  const sections = []
  let current = null
  let buffer = []
  let preamble = []

  const pushCurrent = () => {
    if (!current) return
    if (buffer.length) {
      // v28 step 12: 把 buffer 按 [PAGE:N] / [FIGURE:N] 行切分成多个 block
      //    之前 buffer.join('\n') 把所有行当 paragraph 文本，丢失 [PAGE:N] 信息
      //    现在识别特殊行，提取为独立 block，paragraph 用 \n 拼剩余行
      let currentPage = null
      let paraBuf = []
      const flushPara = () => {
        if (!paraBuf.length) return
        const text = _mergeOCRSoftLineBreaks(paraBuf.join('\n').trim())
        if (text) {
          current.blocks.push({
            type: 'paragraph',
            content: text,
            page: currentPage,
          })
        }
        paraBuf = []
      }
      for (const line of buffer) {
        const trimmed = line.trim()
        const pageMatch = /^\s*\[PAGE:\s*(\d+)\s*\]\s*$/i.exec(trimmed)
        if (pageMatch) {
          flushPara()
          currentPage = parseInt(pageMatch[1], 10)
          current.blocks.push({
            type: 'page_marker',
            content: currentPage,
            page: currentPage,
          })
          continue
        }
        const figMatch = /^\s*\[FIGURE:([\d.a-zA-Z]+)\]\s*$/i.exec(trimmed)
        if (figMatch) {
          flushPara()
          current.blocks.push({
            type: 'figure_marker',
            content: figMatch[1],
            page: currentPage,
          })
          continue
        }
        paraBuf.push(line)
      }
      flushPara()
      buffer = []
    }
    // 即使 blocks 为空也保留 section（让所有识别到的标题都进 sections 数组）
    sections.push(current)
  }

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i]
    // 跳过空行（已被用作段间分隔）
    if (!line.trim()) continue
    const trimmed = line.trim()
    const match = _matchSectionTitle(trimmed)

    // v28 step 89 修复：OCR 把章节标题与正文压成一行（无换行分隔），
    //   trimmed 长度可能超 100。如果 trimmed 匹配 numbered section regex
    //   （如 "4.2 The mechanism..."），仍识别为标题，但需要找到"标题/正文"边界。
    //   放宽上限 100 → 250。超过 250 视为长正文，不当标题。
    if (match && trimmed.length < 250 && i + 1 < lines.length) {
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
        // v28 fix: 标题末尾断字（如 "3.3. ... O3-"）→ 把下一非空行合并到标题末尾
        // match.continued 标志来自 _matchSectionTitle
        let titleText = trimmed.replace(/[:：]\s*$/, '')
        // v28 step 89: OCR 把章节标题与正文压成一行 → 在标题结束后切分正文
        //   模式：numbered section（\d+(\.\d+)+）+ 标题词 + ". " + 大写句子开头
        //   把 ". <大写>" 之前的部分当标题，后续当正文
        // v28 step 102 修复：必须严格守卫切分点
        //   1. title 必须以章节关键词结尾（Materials/Methods/Results/Discussion 等）—— 否则 OCR
        //      把标题里的「B. Cereus」缩写误当成"标题/正文"边界（如 ID 17：「2.1 Test system for the
        //      inactivation of B. Cereus in water using MNBs combined with UV」被切成
        //      title="2.1 Test system for the inactivation of B" + body="Cereus in water..."）
        //   2. 即使切分成功，body 首字母大写词不能是单字母缩写（如 Fig/Eq/Section 等）
        if (match.type === 'normal' && match.level >= 2 && trimmed.length > 80) {
          const splitMatch = /^(\d+(?:\.\d+)*\s+[A-Z][^.]*?)\.\s+([A-Z][a-zA-Z]+.*)$/m.exec(trimmed)
          if (splitMatch) {
            const candidateTitle = splitMatch[1].trim()
            const candidateBody = splitMatch[2].trim()
            // 守卫 1：title 必须以已知章节关键词结尾（避免 B./Dr./Mr./Mr. 等缩写误切）
            const titleEndsWithKw = /(?:system|methods?|results?|discussion|conclusions?|introduction|study|studies|analysis|experiment|investigation|evaluation|comparison|tests?|setup|design|approach|preparation|extraction|characterization|application|model(?:ing)?|simulation)\.?$/i.test(candidateTitle)
            // 守卫 2：切分点前不能是 1-3 字母英文缩写（看 candidateTitle 末 3 字符是不是缩写）
            const lastWord = candidateTitle.split(/\s+/).pop() || ''
            const isAbbrevBeforeDot = /^[A-Z]\.?$|^[A-Z][a-z]{0,2}\.?$/.test(lastWord)
            if (titleEndsWithKw && !isAbbrevBeforeDot) {
              titleText = candidateTitle
              const bodyText = candidateBody
              // 把正文作为下一行内容追加到 buffer（在 pushCurrent 之后）
              // 实际：把正文塞回 lines 让后续循环处理
              // 简化：直接在 sections[新section].blocks 里加 paragraph
              // 下一轮 pushCurrent() 才会执行，所以正文需要延迟处理
              // 这里改用 lines.splice 在 lines 中插入 bodyText 作为 i+1 行
              lines.splice(i + 1, 0, bodyText)
            }
          }
        }
        if (match.continued) {
          for (let j = i + 1; j < lines.length; j++) {
            const nl = lines[j]
            if (!nl.trim()) continue
            const nlTrimmed = nl.trim()
            // 合并下一行（去掉末尾换行，保留单词）
            titleText = titleText.trimEnd() + ' ' + nlTrimmed
            // 把下一行的内容也跳过（不让它进入 buffer）
            i = j  // for 循环 i+=1 后会到 j+1
            break
          }
          // 重新评估合并后的标题是否仍 continued（最多合并 2 行）
          if (titleText.endsWith('-') || /^[a-z]{1,5}$/.test(titleText.split(/\s+/).pop() || '')) {
            for (let j = i + 1; j < lines.length; j++) {
              const nl = lines[j]
              if (!nl.trim()) continue
              titleText = titleText.trimEnd() + ' ' + nl.trim()
              i = j
              break
            }
          }
          // 合并后再 strip 一次 [PAGE:N] 前缀（可能跨行）
          titleText = titleText.replace(/\[PAGE:\s*\d+\s*\]\s*/g, '').trim()
        }
        current = {
          id: _genId('s'),
          title: titleText,
          level: match.level,
          type: normalizedType,
          blocks: [],
        }
        continue
      }
    }

    if (current) {
      buffer.push(line)
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
 *
 * v28 step 20: 之前只按 \n 切行 + 匹配 [N]，但 LLM 重排经常把多条 ref 合并到
 * 同一个 paragraph block（用空格或合并行），按 \n 切不出多行 → 只显示 3 条。
 * 修法：双策略 —— 先按 \n 切（旧逻辑），再按 `[N]` 切剩余块。
 *   1. [N] 整段单独一行 → 切出来
 *   2. 多个 [N] [M] [K] 挤在一行 → 按 [N] 切
 *   3. 完全无 [N] 的 [55] (14), 9691-9710 格式 → 用 REFERENCE_ENTRY_RE 兜底
 */
function splitReferences(content) {
  if (!content) return []
  const entries = []
  const seen = new Set()

  const add = (raw) => {
    const t = String(raw).replace(/\s+/g, ' ').trim()
    // 去前导 [N] 序号（[1] 1. 2. 等都去掉）
    const cleaned = t.replace(/^\s*(\[\d+\]|\d+\.)\s*/, '').trim()
    if (cleaned.length < 10) return
    // dedupe
    if (seen.has(cleaned)) return
    seen.add(cleaned)
    entries.push(cleaned)
  }

  // 策略 1: 按 \n 切分（旧逻辑）
  const lines = content.split('\n')
  let buffer = []
  for (const line of lines) {
    if (REFERENCE_ENTRY_RE.test(line)) {
      if (buffer.length) {
        add(buffer.join('\n').trim())
        buffer = []
      }
    }
    if (line.trim()) buffer.push(line)
  }
  if (buffer.length) add(buffer.join('\n').trim())

  // 策略 2: 按 [N] 切分剩余未匹配内容（v28 step 20 修 LLM 重排后多 ref 挤一行）
  //   例: "[4] Author X... [5] Author Y... [6] Author Z..."
  //   用 /\[(\d+)\]\s+/ 切成多段
  const unconsumed = content
  // 已消费的段落排除
  for (const line of lines) {
    if (REFERENCE_ENTRY_RE.test(line)) continue
    if (line.match(/^\s*\[\d+\]/)) {
      // 整行 [N] 开头但上面没被 REFERENCE_ENTRY_RE 匹配（可能是 [55] (14) 格式）
      add(line)
    }
  }
  // 用 [N] 边界切分整个 content
  const re = /\[(\d+)\]\s+([^\[]*?)(?=\[\d+\]|$)/g
  let m
  while ((m = re.exec(content)) !== null) {
    const tail = m[2].trim()
    if (tail.length >= 10) add(`[${m[1]}] ${tail}`)
  }

  // v28 step 88 修复：策略 3 — OCR 把所有 ref 压成一段（无 [N] 编号，无换行）。
  //   用 "Lastname F M, Lastname F M, ... et al." 模式识别新 ref 开始，在前面插入换行。
  //   模式：大写开头的单词（作者姓） + 1-2 个大写字母（缩写） + 逗号，
  //         紧跟在 `.` `]` `(` `)` 之一后（避免误伤标题内的 "Photolysis of phenol"）
  //   例："...409-418. Aslan M M, Crofcheck C, Tao D, et al. Evaluation..."
  //     → "...409-418.\nAslan M M, Crofcheck C, Tao D, et al. Evaluation..."
  if (entries.length <= 1) {
    let raw = entries.length === 1 ? entries[0] : content
    // 先剥除 Elsevier "Journal Pre-proof N" / "P33-39" 水印（OCR 工具插入的 phantom text）
    // 这些水印打断 ref 切分（"Sewage Journal Pre-proof 35 [D]" → 误判 Yang J. ref 结束）
    raw = raw.replace(/\bJournal\s+Pre-proof\s+\d+\b/gi, ' ')
    raw = raw.replace(/\bP\d{1,3}-\d{1,3}\b/g, ' ')
    // 跳过开头 boilerplate（"References P33-39 参考文献（共 1 条）展开全部 ▾" 等）
    // 用第一个 "作者 + 缩写 + 逗号" 模式位置开始切分
    // v28 step 88 修复：单作者 ref 开头（如 "Yang J. Title"）也要识别
    //   → 用 |\.\s+ 兼容 "Yang J. Title" 和 "Yang J, Author"
    const refStartMarker = /\b[A-Z][a-zÀ-ſ]+\s+[A-Z](?:\s*[A-Z])?(?:,\s|\.\s+[A-Z])/
    const startMatch = refStartMarker.exec(raw)
    const refBody = startMatch ? raw.slice(startMatch.index) : raw
    // 在新 ref 作者模式前插入换行（紧跟 ". " 或 "] " 或 ") "）
    // 注意：必须 lookbehind 限定是 ref 末尾，避免误伤 "Photochemistry and Photobiology A: Chemistry"
    //   (中间也含 "A: Chemistry" 类似 "Author A: Title" 模式)
    const split = refBody.replace(
      /([\.\]:\)])\s+(?=[A-Z][a-zÀ-ſ]+\s+[A-Z](?:\s*[A-Z])?(?:,\s*&?\s*[A-Z])?(?:\s+[A-Z][a-zÀ-ſ]+)?,\s)/g,
      '$1\n'
    )
    // 单作者 ref 切分：例如 "Yang J. Influencing Factors... [D]. Harbin Institute... 2013."
    //   切分点 1：". 卷: 页码. " 后跟 "Lastname F. 大写"（单作者 . Title 模式）
    //   例："...64(21): 2199-2206. Yang J. Influencing..." → "...2199-2206.\nYang J. Influencing..."
    const afterVolPages = split.replace(
      /(\d+[\-:]\d+[\-:]\d+|\d+\(\d+\)[\-:]\d+(?:[\-:]\d+)?)\.\s+(?=[A-Z][a-zÀ-ſ]+\s+[A-Z](?:\s*[A-Z])?\.\s+[A-Z])/g,
      '$1.\n'
    )
    // 单作者 ref 切分点 2：". 年. " 后跟 "Lastname F. 大写"
    //   例："... 2013. Yang S, Wang Y..." 已经被策略 A 切分 → 不需要
    //   例："... 2013. Zhang Y. Application..." → "...2013.\nZhang Y. Application..."
    const afterYear = afterVolPages.replace(
      /(\b\d{4}\.)\s+(?=[A-Z][a-zÀ-ſ]+\s+[A-Z](?:\s*[A-Z])?\.\s+[A-Z])/g,
      '$1\n'
    )
    const finalSplit = afterYear
    if (finalSplit.includes('\n')) {
      // 按换行切分，每条作为独立 reference
      const newLines = finalSplit.split('\n').map((l) => l.trim()).filter(Boolean)
      const seenNew = new Set()
      const newEntries = []
      for (const line of newLines) {
        const cleaned = line.replace(/\s+/g, ' ').trim()
        if (cleaned.length < 30) continue
        // 跳过纯 boilerplate
        if (/^(References?|参考文献|Bibliography|P\d+-\d+|展开全部|共\s*\d+\s*条)/i.test(cleaned)) continue
        if (seenNew.has(cleaned)) continue
        seenNew.add(cleaned)
        newEntries.push(cleaned)
      }
      // v28 step 88: 切分得到 ≥2 条新 entries → 用新的完全替换 entries
      // 旧 entries[0] 是 raw 整段，切分后 line 是它的子串但不是重复（只是 prefix）
      if (newEntries.length >= 2) {
        entries.length = 0
        entries.push(...newEntries)
      }
    }
  }

  return entries
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

    // v28 step 38: Markdown 表格检测
    //   特征：当前行以 | 开头 + 下一行是 |---|---|... 分隔行
    //   处理：把连续 N 行收集成表格 block（type='table'），保留 markdown 源码让前端渲染
    if (trimmed.startsWith('|') && trimmed.endsWith('|') && i + 1 < lines.length) {
      const nextLine = lines[i + 1].trim()
      // 分隔行匹配 |---|---| 或 |:---|---:| 等对齐符
      if (/^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$/.test(nextLine)) {
        flushParagraph()
        // 收集表头 + 分隔 + 所有数据行
        const tableLines = [line]
        let j = i + 1
        while (j < lines.length) {
          const cur = lines[j].trim()
          if (cur.startsWith('|') && cur.endsWith('|')) {
            tableLines.push(lines[j])
            j++
          } else if (cur === '') {
            // 空行 = 表格结束（但允许后跟空行 + 表格后是其他段落）
            break
          } else {
            // 非表格行，停止
            break
          }
        }
        blocks.push({
          type: 'table',
          content: tableLines.join('\n'),
          page: currentPage,
        })
        i = j - 1  // for 循环会 i++，所以 -1
        continue
      }
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
 * v28 step 11: 把过长的 paragraph block 拆成多个 paragraph
 *
 * PDF 文档的软换行（每行 ~70 字符）让 paragraph block 实际包含整个章节的连续文本
 * 用户期望"按原文段落分段"，需要在 . 句末 + 后续大写字母开头的位置断句
 *
 * 算法:
 * 1. 跳过 < 200 字符的 block（不需要拆）
 * 2. 逐句扫描（以 . ! ? 结尾为句末）
 * 3. 检测句末后跟"段起标志"：
 *    - 下一句首词是大写字母开头
 *    - 且不是延续词（The/This/It/However/Moreover...）
 *    - 且不是 Fig. N. / Table N. 这种图标题
 *    - 且不是 T. Wang et al. 这种页脚
 *    - 累积距离 > 300 字符（避免句内分隔）
 * 4. 在段起处拆 block，分配同样的 page
 */
const PARAGRAPH_CONTINUE_WORDS = new Set([
  'The', 'This', 'It', 'These', 'Those', 'That', 'In', 'To', 'We', 'As',
  'However', 'Furthermore', 'Moreover', 'For', 'While', 'Where', 'Although',
  'Since', 'Because', 'When', 'After', 'Before', 'Or', 'And', 'But', 'So',
  'Yet', 'If', 'By', 'From', 'With', 'At', 'On', 'Through', 'Here', 'There',
  'Thus', 'Therefore', 'Overall', 'Additionally', 'Indeed', 'Such',
])

// 元数据/页脚行（不视为段起）
const PARAGRAPH_FOOTER_RE = /^(?:T\.|Fig\.|Table|Scheme|Journal|Available|Received|Revised|Accepted|E-?mail|Tel\.|Copyright|©|\[PAGE)/
// 图标题 "Fig. N. ..." 整段都是 caption，不分段
const FIG_CAPTION_START_RE = /^(?:Fig\.|Figure|Scheme|Table)\s+\d+/

function _isParagraphStart(prevLine, nextLine, cumCharsSinceLastBreak) {
  if (!prevLine || !nextLine) return false
  if (!/\.\s*$/.test(prevLine.trim())) return false
  const next = nextLine.trim()
  if (!next) return false
  if (!/^[A-Z]/.test(next)) return false
  // 过滤元信息 / 页脚
  if (PARAGRAPH_FOOTER_RE.test(next)) return false
  // 图标题（Fig. 1. xxx）整段是 caption，不拆
  if (FIG_CAPTION_START_RE.test(next)) return false
  // 过滤延续词
  const firstWord = next.split(/\s+/)[0].replace(/[^A-Za-z]/g, '')
  if (PARAGRAPH_CONTINUE_WORDS.has(firstWord)) return false
  // 累积字符 > 300 才视为真正段起（避免句内分隔）
  if (cumCharsSinceLastBreak < 300) return false
  return true
}

function _splitLongParagraph(block, maxChars = 1000) {
  if (!block?.content) return [block]
  const text = block.content
  if (text.length < 500) return [block]  // 不长就不拆

  const lines = text.split('\n')
  const segments = []
  let currentBuf = []
  let cumChars = 0
  let lastSentenceEndLineIdx = -1  // 最近一个以 . 结尾的 line 在 lines 数组中的 idx
  const flush = () => {
    if (!currentBuf.length) return
    const segText = currentBuf.join('\n').trim()
    if (segText) {
      segments.push(segText)
    }
    currentBuf = []
    cumChars = 0
    lastSentenceEndLineIdx = -1
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const trimmed = line.trim()

    currentBuf.push(line)
    cumChars += line.length

    // 记录最后一个以 . 结尾的行在 lines 数组中的 idx
    if (/[.!?]\s*$/.test(trimmed)) {
      lastSentenceEndLineIdx = i
    }

    // 仅在 lastSentenceEndLineIdx 行紧邻的下一行（即 i === lastSentenceEndLineIdx）
    // 才检查段起。这样避免累积多行后回溯到很早的句末位置做段起判断
    if (
      i + 1 < lines.length &&
      lastSentenceEndLineIdx === i &&  // 当前行就是最近句末行
      cumChars >= 300
    ) {
      const prevLine = line
      const nextLine = lines[i + 1]
      if (_isParagraphStart(prevLine, nextLine, cumChars)) {
        flush()
      }
    }

    // v28 step 13 + 15: 下一行是图标题（Fig. N. / Table N.）时独立成段
    //    例: "...non-mass transfer-limited processes,\nFig. 3. Effects of ..."
    //    上行末尾是逗号不是句末，但 Fig. 3. 是独立图标题，应独立成段
    //
    // 修复 (v28 step 15): 之前用 /^(?:Fig|Figure|Scheme|Table)\.?\s*\d/i 太宽松，
    //    会把正文里 "Fig. 5e summarizes the proposed mechanism" 误判为图 caption 拆段。
    //    新规则：必须是「Fig. N. (大写描述)」这种 caption 格式才算图标题。
    //    - 数字 N 必须是纯数字（1-3 位），不含字母子号（5e / 5a 不是 caption）
    //    - 数字后必须是 `.` + 空格 + 大写字母（描述开头）
    if (i + 1 < lines.length && cumChars >= 200) {
      const nextLine = lines[i + 1].trim()
      if (/^(?:Fig|Figure|Scheme|Table)\.?\s+\d{1,3}\.\s+[A-Z][a-zA-Z]/.test(nextLine)) {
        flush()
      }
    }
  }
  flush()

  // 合并太小的 segment 到前一个（避免出现 50 字独立段）
  const merged = []
  for (const seg of segments) {
    if (merged.length && seg.length < 100) {
      merged[merged.length - 1] += '\n' + seg
    } else {
      merged.push(seg)
    }
  }

  return merged.map((text, i) => ({
    type: 'paragraph',
    content: text,
    page: block.page,
    indexInSection: i,
  }))
}

function _splitOversizedParagraphs(sections) {
  for (const section of sections) {
    if (!section.blocks) continue
    const newBlocks = []
    for (const block of section.blocks) {
      if (block.type !== 'paragraph') {
        newBlocks.push(block)
        continue
      }
      const split = _splitLongParagraph(block)
      newBlocks.push(...split)
    }
    section.blocks = newBlocks
  }
  return sections
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
function _mergeOCRSoftLineBreaks(text) {
  if (!text) return text
  // v28 step 109.1: OCR 软换行合并（vision 输出 paragraph 保留了 PDF 软换行）
  //   软换行特征：
  //     1. 上一行末尾是 `\\w`（非标点） + 下一行开头是小写字母 → 直接合并（无空格，PDF 单词被截断）
  //     2. 上一行末尾是 `-\\n` + 下一行开头是字母 → 合并（去 `-`，典型 hyphenated word 断行）
  //     3. 上一行末尾是 `\\w,` 或 `\\w)` → 改成空格（同一段内的标点切分）
  //   真段落边界（保留 \\n\\n）：
  //     - 上一行末尾是 `.`/`?`/`!` + 下一行是大写字母 → 段落边界
  //     - 列表项（如 `•` / `-` 开头） → 保留 \\n
  //     - 空行（\\n\\n） → 保留
  let result = text

  // 1. hyphenated word 断行：`word-\\nword` → `wordword`
  result = result.replace(/([A-Za-z])-\s*\n\s*([a-z])/g, '$1$2')

  // 2. 单词被换行截断（上一行末尾是 \\w + 下一行是小写）：直接合并
  //    例: "micro-\\nnano" → "micronano", "dis-\\ninfection" → "disinfection"
  //    例: "Micro-\\nnano bubbles" → "Micronano bubbles"（OCR 把 Micro-nano 截断成两行）
  result = result.replace(/([A-Za-z])\s*\n\s*([a-z])/g, '$1 $2')

  // 3. 列表项保留 \\n：• - * 开头 → 保留换行（但合并为 list item 之间空行）
  //    这里不再额外处理，因为 list item 之间通常是 \\n\\n 已经是段落边界

  // 4. 多余 \\n\\n + 单词 + \\n + 单词 合并（OCR 段中段间偶然 \\n\\n）
  //    真实段落边界特征：上一行末尾是句末标点 + 下一行是大写字母
  //    这里不做强制合并，保留 \\n\\n 让 paperAdapter 自行识别

  return result
}

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
    /Corresponding\s+author/i,
    /E-?mail\s+address/i,
    /E-?mail\s*[:：]\s*\S+@\S+/i,
    /Tel\.?\s*[:：]/i,
    /ScienceDirect/i,
    /journal\s+homepage/i,
    /Contents?\s+lists?\s+available/i,
    /Received\s+(?:in\s+revised\s+form\s+)?\d/i,
    /Revised\s+\d/i,
    /Accepted\s+\d/i,
    /Available\s+online\s+\d/i,
    /©\s*\d{4}/i,
    /Copyright/i,
    /\[PAGE:\d+\]/i,
    /https?:\/\/(?:dx\.)?doi\.org\//i,
    /DOI\s*[:：]\s*10\./i,
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

/**
 * 英文论文正文中文污染过滤
 *
 * 如果一行中中文字符占比 > 50%，且不是章节标题 / 关键词 / 图表标记，
 * 则视为 OCR 中文解说残留，整行删除。
 *
 * 保留：少量中文专有名词（如作者单位里的"天津"）在元信息区，
 * 但正文段落不应出现大段中文。
 */
/**
 * 中文污染过滤（v27.2 多规则版）
 *
 * 5 条规则共同判断某行/某段是否应该被删除：
 *   1. block 来源判断 (in quote / OCR caption / JSON-like)
 *   2. 中文字符占比 (>40% 且 >3 个中文字符)
 *   3. 中文关键词检测 (图/表/说明/分子模拟图/OCR 解释等)
 *   4. JSON-like 结构检测 ({ "category": / { "text": 等)
 *   5. ASCII 噪声检测 (大量特殊符号 / 控制字符 / 无正常英文词)
 *
 * 返回清洗后的 text
 */
function _cleanChineseFromEnglish(text) {
  if (!text) return ''

  // 先按 \n\n 拆段（多行段落），分别判断
  // 这样能避免"一段文字里只有一行是中文"被漏判
  const lines = String(text).split('\n')
  const keepLines = []

  // 关键词白名单（保留这些中文章节标题）
  const CN_TITLE_KEEP = /^(摘要|关键词|引言|结论|参考文献|致谢|材料与方法|实验方法|结果与讨论|实验结果|前言|背景|讨论|方法|附录|Abstract|Keywords|Introduction|Conclusion|References|Acknowledgments|Methods|Results|Discussion)\b/

  // 强删关键词（中文图注/OCR 解释/LLM 输出等）
  const CN_POLLUTION_KEYWORDS = /(图表说明|图表描述|图（[Pp]?[0-9]|图\s\(P?[0-9]|Figure description|Figure caption|分子模拟图|图片说明|图片描述|识别文字|识别结果|OCR\s*文本|OCR\s*识别|识别说明|分析结果|可视化|图表分析|图表解读|Table description|Table caption|图谱说明|图谱描述|系统提示|用户提示|Assistant|User)/

  // JSON-like 结构检测（含 "category": / "text": / "kind": 等键）
  const JSON_LIKE_RE = /\{\s*["'](?:category|kind|type|text|description|model|source|confidence)["']\s*:/

  // 异常字符检测（含 \x00 等控制字符，或大量重复特殊符号）
  const NOISE_RE = /[\x00-\x08\x0B-\x1F\x7F]/

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const trimmed = line.trim()

    // 空行保留
    if (!trimmed) {
      keepLines.push(line)
      continue
    }

    // 规则 1: 强删 — 包含明显的中文污染关键词（无论占比）
    if (CN_POLLUTION_KEYWORDS.test(trimmed)) {
      continue  // 删除
    }

    // 规则 2: 强删 — JSON-like 结构（OCR extractions 输出）
    if (JSON_LIKE_RE.test(trimmed)) {
      continue
    }

    // 规则 3: 强删 — 控制字符污染
    if (NOISE_RE.test(line)) {
      continue
    }

    // 规则 4: 中文字符占比（>40% 且 ≥3 个中文字符）
    const cnChars = (trimmed.match(/[一-鿿]/g) || []).length
    const totalChars = trimmed.length
    const cnRatio = cnChars / Math.max(1, totalChars)

    if (cnRatio > 0.4 && cnChars >= 3) {
      // 豁免：中文章节标题（摘要/引言/结论等）
      if (CN_TITLE_KEEP.test(trimmed)) {
        keepLines.push(line)
        continue
      }
      // 豁免：blockquote（已在 cleanContent 剥除）
      if (/^[>＞]/.test(trimmed)) continue
      // 其他高中文占比行 → 删除
      continue
    }

    // 规则 5: 段落级判断 — 如果当前行有中文且前后 2 行也是中文，整段都删
    //   （避免一段文字只有一行中文被保留导致段落碎片化）
    if (cnChars > 0 && cnRatio > 0.2) {
      // 看前后 2 行是否也是中文
      const prevLine = i > 0 ? lines[i - 1].trim() : ''
      const nextLine = i < lines.length - 1 ? lines[i + 1].trim() : ''
      const prevCn = (prevLine.match(/[一-鿿]/g) || []).length
      const nextCn = (nextLine.match(/[一-鿿]/g) || []).length
      const prevRatio = prevCn / Math.max(1, prevLine.length)
      const nextRatio = nextCn / Math.max(1, nextLine.length)
      if (prevRatio > 0.4 || nextRatio > 0.4) {
        // 前后行也是中文 → 整段都是中文，删除当前行
        continue
      }
    }

    // 保留
    keepLines.push(line)
  }

  return keepLines.join('\n').replace(/\n{3,}/g, '\n\n').trim()
}

/**
 * 段落级深度清洗（v27.2 新增）
 *
 * 处理 _cleanChineseFromEnglish 行级清洗无法捕捉的情况：
 * - 一段文字里既有英文又有中文图表说明混合
 * - 多模态 extraction 输出混入正文段
 *
 * 启发式：如果一段含 OCR/JSON/中文图注特征，整段删除
 */
function _cleanParagraphHeavy(text) {
  if (!text) return ''
  const paragraphs = String(text).split(/\n\n+/)
  const kept = []
  for (const p of paragraphs) {
    const trimmed = p.trim()
    if (!trimmed) continue

    // 段落级 JSON-like 检测（多模态 OCR 输出混入）
    if (/^\s*\{[\s\S]*"(?:category|kind|text|description|model)[\s\S]*\}\s*$/.test(trimmed)) {
      continue  // 整段是 JSON
    }

    // 段落级 OCR caption 检测（开头是 "图（" 或 "图表说明"）
    if (/^\s*(?:图（[Pp]?\d|图表说明|图表描述|Figure description|Table description)/.test(trimmed)) {
      continue
    }

    kept.push(p)
  }
  return kept.join('\n\n').trim()
}

/**
 * 构建正文内嵌图映射
 *
 * 扫描每个 section 的 blocks，找到 "Fig. N" / "Figure N" / "图 N" 引用，
 * 返回 { sectionId: [figure, ...] } 映射。
 * 每张图只在首次出现的 section 内嵌一次。
 */
/**
 * Figure Registry：建立统一的图片元数据索引
 *
 * 每张图片整理为：
 * {
 *   id, src, page, figureNo, figureType,
 *   isCoreFigure, isPublisherImage,
 *   caption, ocrText, semanticTitle, sectionHint, confidence
 * }
 *
 * figureType 候选：
 *   graphical_abstract / scheme / figure / chart / table /
 *   mechanism / experimental_setup / molecular_simulation /
 *   cover / logo / publisher / unknown
 *
 * isCoreFigure = true 的图片才允许正文内嵌
 * isPublisherImage = true 的图片只能在文末"出版信息"区
 */

// ---- 本段对外导出（供下游段 import，勿删）----
export { parsePaperSections }
export { splitReferences }
export { _buildContentBlocks }
export { _splitOversizedParagraphs }
export { _mergeOCRSoftLineBreaks }
export { _detectAbstractFromContent }
export { _stripPublicationInfo }
export { _cleanChineseFromEnglish }
export { _cleanParagraphHeavy }
