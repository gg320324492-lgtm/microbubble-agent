// 文本清洗与占位符抽取：cleanContent / front matter / DOI / page|figure|table 标记。
import {
  SECTION_KEYWORDS, NUMBERED_SECTION_RE, PAGE_MARKER_RES,
  FIGURE_MARKER_RE, TABLE_MARKER_RE, URL_RE, SPACED_TITLE_RE,
  HTML_ATTR_RES, INTERNAL_MARKER_RES, FOOTER_PATTERNS, IMG_EXT_RE,
  _stripMultimodalBlocks,
} from './constants'

function normalizeDoiText(text) {
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
function insertSectionBreaks(text) {
  if (!text) return ''
  let result = String(text)

  // 处理 字符间隔的标题（OCR 字符全大写带空格）
  // "H I G H L I G H T S" → "HIGHLIGHTS"（独立成行）
  result = result.replace(/\b([A-Z])\s+([A-Z])\s+([A-Z])\s+([A-Z](?:\s+[A-Z])+)\b/g, (m) => {
    return '\n' + m.replace(/\s+/g, '') + '\n'
  })

  // 多个标题合并（HIGHLIGHTSGRAPHICALABSTRACTARTICLEINFO）→ 拆成多行
  // 用大写英文单词做拆分点
  // v28 step 82 修复：原 regex 用 /gi 大小写不敏感，会把 "1. Introduction" 中的 "Introduction" 也匹配
  //   然后插入 \n 导致 "1. \nIntroduction\n"，破坏章节标题
  // 修复：要求标题要么全大写（HIGHLIGHTS），要么前面是空格/行首/标点（独立标题）
  //   但绝不能作为其他单词的一部分被匹配
  const mergedTitleRe = /(?<![A-Za-z])(HIGHLIGHTS|GRAPHICAL\s+ABSTRACT|ARTICLE\s+INFO(?:RMATION)?|KEYWORDS|ABSTRACT|INTRODUCTION|MATERIALS\s+AND\s+METHODS|RESULTS?\s+AND\s+DISCUSSION|CONCLUSIONS?|REFERENCES|ACKNOWLEDGEMENTS|GRAPHICALABSTRACT|ARTICLEINFO)(?![A-Za-z])/g
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
function removeFrontMatter(content) {
  if (!content) return { cleaned: '', abstract: null, keywords: [], frontMatter: '', hasFrontMatter: false }

  let result = String(content)

  // 1. 找第一个 Introduction / 引言 位置（正文从此开始）
  //    容忍前置 (?:^|\n)\s* 和可选编号 (\d+(\.\d+)*\.?\s+)?
  const introMatch = result.match(/(?:^|\n)\s*(\d+(\.\d+)*\.?\s+)?(Introduction|引言|前言|绪论)\b/i)
  const introIdx = introMatch ? introMatch.index : -1

  if (introIdx < 0) {
    // 没找到 Introduction 起点，原样返回
    return { cleaned: result, abstract: null, keywords: [], frontMatter: '', hasFrontMatter: false }
  }

  const frontMatter = result.slice(0, introIdx)
  const body = result.slice(introIdx)

  // v28 step 82: 仅在 front matter 含 Elsevier PDF 元信息时才触发剥离
  //   启发式检测：① PII/DOI/Reference 标识 ② "To appear in" ③ "Please note that Elsevier" 等 boilerplate
  //   ④ Received date / Revised date 等
  //   否则（普通 PDF，Abstract 是独立章节）返回原内容，让 parsePaperSections 处理
  const isElsevierPreProof = /PII\s*[：:]|DOI\s*[：:]\s*https?:\/\/|Reference\s*[：:]\s*[A-Z]{2,5}\s+\d+|To appear in|Please\s+(?:also\s+)?note\s+that\s+Elsevier|Received\s+date\s*[：:]|Revised\s+date\s*[：:]|Accepted\s+date\s*[：:]|©\s*\d{4}\s+Published by\s+Elsevier|This is a PDF of an article/i.test(frontMatter)

  if (!isElsevierPreProof && !/^\s*Abstract\s*[：:]/im.test(frontMatter)) {
    // 普通论文 front matter（无 Abstract 段）— 不剥离，让原解析器处理
    return { cleaned: result, abstract: null, keywords: [], frontMatter: '', hasFrontMatter: false }
  }

  // 2. v28 step 82: 从 front matter 抽出 Abstract + Keywords
  //    Elsevier PDF 的 abstract 段通常以 "Abstract：" / "Abstract:" / "ABSTRACT" 开头
  //    keywords 段以 "Keywords:" / "关键词" / "Key words" 开头
  let abstract = null
  let keywords = []

  // 抽取 Abstract（关键词终止符 + Introduction 终止符）
  const abstractMatch = frontMatter.match(/Abstract\s*[：:]\s*([\s\S]*?)(?=\n\s*(?:Keywords?|关键词|关键字|Key\s*words?|\d+\.\s*(?:Introduction|引言|前言))|$)/i)
  if (abstractMatch) {
    abstract = abstractMatch[1]
      // 修复单词换行bug: "the\noverall" → "the overall" (而非 "theoverall")
      .replace(/([A-Za-z一-龥])\s*\n\s*([A-Za-z一-龥])/g, '$1 $2')
      // 合并多行空白
      .replace(/\s+/g, ' ')
      .replace(/\s+([,.;:!?])/g, '$1')
      .trim()
  }

  // 抽取 Keywords
  // v28 step 109.37: 之前只按 ,， 拆，OCR 把每个关键词放一行时（如 Elsevier 期刊）会被合并成一个字符串
  //   改为按 ,，;\n 任一符号拆（支持逗号/分号/换行分隔）
  //   lookahead 增加 [PAGE:N] 终止符（OCR 内容普遍含此标记）
  const kwMatch = frontMatter.match(/Keywords?\s*[：:]?\s*([^\n]+(?:\n[^\n]+)*?)(?=\n\s*(?:\d+\.\s*(?:Introduction|引言)|1\.|\[PAGE:|$))/i)
  if (kwMatch) {
    keywords = kwMatch[1]
      .replace(/[；;]/g, ',')  // 中英文分号统一
      .split(/[,，\n]+/)
      .map(k => k.trim())
      .filter(Boolean)
  }

  return {
    cleaned: body.trim(),
    abstract: abstract || null,
    keywords,
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
function cleanContent(text, options = {}) {
  if (!text) return { content: '', extractedImages: [] }
  const extractedImages = []
  const { stripImageUrls = true, isMarkdown = false } = options

  let result = String(text)

  // -1. 优先剥除 PDF 页码标记（多种格式：行中、行尾、独立行）
  //      "T. Wang et al. 3 [PAGE:4]" → "T. Wang et al."
  //      "Vol 513 (2026) 142456 [PAGE:5]" → "Vol 513 (2026) 142456"
  // 关键：用 \n 替代空格，保留行边界（防止章节标题被合并到前一/后行）
  // v28 fix: 完整保留 [PAGE:N] 标记, 让后续 extractPageMarkers 提取
  // (任何形式的删除 [PAGE:N] 都会让 pageMarkers=0, 然后 sections 解析丢分页,
  //  正文被压成 preamble 空 sections, 用户看到 9 字符)
  // 只处理无方括号的 "PAGE:3" 形式 (line 4):
  result = result.replace(/\s+PAGE:\s*\d+\b/gi, ' ')

  // 0. 先剥除 LLM blockquote 图描述（> 📊 **图表说明（Px）**\n> ... 整段）
  //    这些是 inline 进正文的图注描述，不应作为正文段落
  //    保留为 figure caption 候选
  // v28 step 90: 扩展 regex 匹配**通用中文图注 blockquote**（"该图由..."/"下图展示了..."/"图 X 显示..."）
  //   之前只匹配 "图表说明"/"Figure caption" 等 LLM 风格前缀，OCR 原生中文图注（"该图由..."）漏判
  //   修复：加入 (?:该图|下图|图\s*\d|图表|示意图) 等中文图注常见开头
  const captionBlocks = []
  result = result.replace(/^[ \t]*>[ \t]*((?:📊|📈|📉|🖼|🧪|⚗|🔬|🔍|💠)?[ \t]*[*_]*\s*(?:图表说明|Figure\s+caption|Table\s+caption|Caption|图表描述|Figure description|该图|下图|示意图|图表)[^]*?)(?=\n[ \t]*[^>]|\n\n|$)/gim, (m, captionText) => {
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

  // 1.5 v28 step 16: 整段剥除「图（PN，...alt 含嵌套 []/JSON 漏闭合...）（url）」型 inline image 标记
  //     根因：PDF 提取把多模态图注以 ![(图（P1，...（含 OCR 嵌套方括号 + JSON）...）](minio_url) 形式污染进 content
  //     旧 markdown 提取正则 `!\[([^\]]*)\]\(([^)\s]+)\)` 失败 —— alt 包含 `]` 和 ASCII `)` (如 "(a) (b)") 都截断匹配
  //     INTERNAL_MARKER_RES 第 5 条也匹配不上（alt 内的 ASCII `)` 打断）
  //     修法：先用一个超宽松贪婪规则，匹配 `图（PN，` 起始的整段（跨多行、含任意字符）直到下一行的 `](http...)`
  //     把这段作为 inline image 标记整段删除（不再尝试从中提取 url —— 后端已经有正式 images 记录）
  result = result.replace(
    /图\s*[（(]\s*[Pp]?\d+\s*[，,][^]*?]\(\s*https?:\/\/[^\s)]+\s*\)/g,
    ''
  )
  // 兜底：如果上面规则没匹配（url 不在 `]()` 内），再剥一次「图（PN，...」到行尾
  result = result.replace(/图\s*[（(]\s*[Pp]?\d+\s*[，,][^]*?(?=\n\n|\n\[PAGE|\n[1-9]\.\s+\w)/g, '')

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

  // 3.5 v26.1: 多模态 chart 描述块（OCR 漏闭合 }）—— 必须在 INTERNAL_MARKER_RES 之前
  result = _stripMultimodalBlocks(result)

  // 3.6 v28 step 101: OCR phantom 页码 + 段首单词 inline 合并
  //   "B. cereus\n\n3\n\n(Grutsch" → "B. cereus 3 (Grutsch"（保留 3 作为 inline 页码）
  //   "MNBs\n\ncapable of completely" → "MNBs capable of completely"（段首小写合并）
  //   必须在 INTERNAL_MARKER_RES 之前：否则 line 205 /^\s*\d{1,3}\s*$/gm 直接删 3
  //   触发条件：上一行末尾是小写字母/右括号/方括号（不是句末标点 . ! ?）
  //            + \n\n + 单数字/单词 + 单空格/\n\n + 后跟小写字母/左括号
  //   排除真段落边界：
  //     - "here.\n\nThe" → lookbehind 是 . 不是小写 → 不匹配 ✓
  //     - "paragraphs.\n\nMoreover," → lookbehind 是 . → 不匹配 ✓
  //   中文段落不触发（lookbehind/lookahead 是英文字母）
  //   两模式分开：数字模式必须后跟左括号（避免与 step 90 orphan 页码删除冲突）
  //
  // v28 step 101 修复：去掉 `if (!/[一-龥]/.test(result))` 整篇中文守卫
  //   根因：v28 系列 PDF 都是中英混排（含中文 Abstract + 英文 Methods），整篇 result
  //   命中中文 → 守卫 false → 整篇英文段落 phantom 也不合并 → 用户看不到效果
  //   正确守卫应该在 lookbehind/lookahead（已限定英文），不再需要整篇判断
  // 模式 A1: phantom 数字 + 左括号（reference 引用 inline, v40 原始严格双空行）
  //   "cereus\n\n3\n\n(Grutsch" → "cereus 3 (Grutsch"
  //   数字后必须紧跟 '(' 才合并，避免误伤 step 90 orphan 数字删除
  // v28 step 101 第五次修复（v45）：A1 + A2 之前都跑在 step 99 OCR watermark 合并之前
  //   但生产 input 'B. cereus\n[PAGE:4]Journal Pre-proof\nJournal Pre-proof\n \n3\n\n(Grutsch'
  //   中 'Journal Pre-proof' 隔开 cereus 和 3，A2 不匹配
  //   解决：把 A1 + A2 移到 step 99 之后，确保 input 已经合并 watermark
  result = result.replace(
    /([a-z)\]])\s*\n\s*\n\s*(\d{1,3})\s*(?:\n\s*\n|\s)(?=\()/g,
    '$1 $2 '
  )
  // 模式 B: phantom 单词（OCR 段首小写）
  //   "MNBs\n\ncapable of" → "MNBs capable of"
  //   "both\n\nmechanistic complementarity" → "both mechanistic complementarity"
  //   上限 20 字符：OCR 段首单词一般是常见词（capable=7, mechanistic=11），20 留余量
  const beforeB = result
  result = result.replace(
    /([a-z)\]])\s*\n\s*\n\s*([a-z]{1,20})\s+(?=[a-z(])/g,
    '$1 $2 '
  )

  // 4. 系统内部标记
  for (const re of INTERNAL_MARKER_RES) {
    result = result.replace(re, '')
  }

  // 5. DOI 规范化
  result = normalizeDoiText(result)

  // 5.1 v28 step 75 + step 82: PDF 软连字符 + 行尾强制换行 → 合并
  //   根因：PDF 提取把 "disin-fection" 拆成 "disin­\n        fection"，'-­' 是不可见 soft hyphen
  //   解法：先去掉所有 soft hyphen（U+00AD），再合并 "字母 + 强制换行 + 字母"
  // v28 step 82 修复：单词逐行 OCR bug（"Please\nalso\nnote" 应变 "Please already note" 而非 "Pleasealsonote"）
  //   关键区分：① 单词内换行（如 "disin­\n        fection"）：行末是单词一部分，前面有空格缩进 → 合并
  //              ② 单词间换行（如 "Please\nalso\nnote"）：前后都是单短词 → 加空格
  //   关键保护：上一行是多词行（如 "1 Introduction"）→ 不要合并（保持段落边界）
  result = result.replace(/­/g, '')
  // 5.1a 单词逐行 OCR：找连续的单短词行合并（不与多词行粘连）
  //   用 split + reduce 实现，能正确处理连续单词（"Please already\nnote" → "Please already note"）
  //   容忍单词末尾标点（"that," / "during." / "the:" 等仍是单词 OCR 的一部分）
  //   排除纯数字 + 标点（"1." / "2," 这种章节编号前缀不应当作单词）
  {
    const lines = result.split('\n')
    const out = []
    let runBuffer = ''  // 当前正在累积的单短词行 run
    const flushRun = () => {
      if (runBuffer) {
        out.push(runBuffer)
        runBuffer = ''
      }
    }
    const isSingleShortWord = (s) => {
      const t = s.trim()
      // 必须以字母/中文开头（排除纯数字）
      return t.length > 0 && t.length <= 22
        && /^[A-Za-z一-龥][A-Za-z一-龥\-'’]*[,.!?;:]?$/.test(t)
    }
    for (const line of lines) {
      if (isSingleShortWord(line)) {
        runBuffer = runBuffer ? `${runBuffer} ${line.trim()}` : line.trim()
      } else {
        flushRun()
        out.push(line)
      }
    }
    flushRun()
    result = out.join('\n')
  }
  // 5.1b 合并单词内换行（必须有前导空格缩进表明是续行）
  //   "disin\n        fection" → "disinfection"  (有缩进)
  //   "Chemicals\nToluene" → 保持换行 (无缩进，是独立段落)
  result = result.replace(/([a-zA-Z一-龥])\n[ \t]+([a-zA-Z一-龥])/g, '$1$2')
  // v28 step 95: OCR 把英文单词从中间断行（无缩进）
  //   "bacterial\ndisinfection process" → "bacterial disinfection process"
  //   触发条件：上一行末尾小写 + 下一行开头小写（区别于独立段落的"句末标点 + 大写开头"）
  //   仅在英文段落（非中文论文）应用，避免误合并中文段落
  //   v28 step 101 撤掉（'\n\n' 版本）—— 通用规则破坏太多现有 fixture
  //   phantom 页码（如 'B. cereus\n\n3 (Grutsch'）保留，UI 仍可读
  if (!/[一-龥]/.test(result)) {
    result = result.replace(/([a-z])\n([a-z])/g, '$1 $2')
  }
  // 5.1c 合并"编号. + 标题"被 step 5.1a 拆开的章节标题（"1.\nIntroduction" → "1. Introduction"）
  result = result.replace(/^(\d+(?:\.\d+)*\.)\n^([A-Z])/gm, '$1 $2')

  // v28 step 90: orphan PDF 页码（OCR 把页码插入英文段落开头）
  //   例："during\n\n15 disinfection." → "during disinfection."（保留空格）
  //   必须放在 step 5.1b 之后（否则空格被 line 716 软连字符合并吃掉）
  //   触发条件：行首 1-3 位数字 + 空格 + 小写单词（避免误伤 "5 patients" 真句子开头）
  //   用 lookbehind 限定前一行是英文（避免列表项 "1. xxx" 误判）
  result = result.replace(/(?<=[a-z])\n\s*\d{1,3}\s+(?=[a-z]{3,})/g, ' ')

  // 5.2 v28 step 75: HTML 实体 → Unicode 下标/上标
  //   <sub>3</sub> → ₃, <sup>-</sup> → ⁻, <sub>2</sub> → ₂ 等
  const SUB_MAP = {'0':'₀','1':'₁','2':'₂','3':'₃','4':'₄','5':'₅','6':'₆','7':'₇','8':'₈','9':'₉',
                   '+':'₊','-':'₋','=':'₌','(':'₍',')':'₎','a':'ₐ','e':'ₑ','h':'ₕ','i':'ᵢ','j':'ⱼ','k':'ₖ','l':'ₗ','m':'ₘ','n':'ₙ','o':'ₒ','p':'ₚ','r':'ᵣ','s':'ₛ','t':'ₜ','u':'ᵤ','v':'ᵥ','x':'ₓ'}
  const SUP_MAP = {'0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹',
                   '+':'⁺','-':'⁻','=':'⁼','(':'⁽',')':'⁾','a':'ᵃ','b':'ᵇ','c':'ᶜ','d':'ᵈ','e':'ᵉ','f':'ᶠ','g':'ᵍ','h':'ʰ','i':'ⁱ','j':'ʲ','k':'ᵏ','l':'ˡ','m':'ᵐ','n':'ⁿ','o':'ᵒ','p':'ᵖ','r':'ʳ','s':'ˢ','t':'ᵗ','u':'ᵘ','v':'ᵛ','w':'ʷ','x':'ˣ','y':'ʸ','z':'ᶻ'}
  // <sub>X</sub> → Unicode sub
  result = result.replace(/<sub>([^<]*?)<\/sub>/g, (m, content) => {
    return content.split('').map(c => SUB_MAP[c] || c).join('')
  })
  // <sup>X</sup> → Unicode sup
  result = result.replace(/<sup>([^<]*?)<\/sup>/g, (m, content) => {
    return content.split('').map(c => SUP_MAP[c] || c).join('')
  })

  // 5.3 v28 step 75: 去除 PDF 重复引用括号 ⁽¹⁾⁽²⁾ 等保留，但 ⁽¹͵¹²͵¹⁴͵¹⁵⁾ 这种连号 PDF 软连字符分隔，合并
  //   "⁽¹͵¹²͵¹⁴⁾" → "⁽¹⁻²⁻¹⁴⁾" 或直接保留（不强改）
  //   只清理 ⁽͵ 这种孤立 soft hyphen
  result = result.replace(/⁽͵/g, '⁽').replace(/͵⁾/g, '⁾').replace(/͵/g, ',')

  // 5.4 v28 step 75 + step 82: 章节编号与标题同行
  //   "4.2\n内容一：..." → "4.2 内容一：..."
  //   数字编号 + 换行 + 中文标题 → 数字编号 + 空格 + 中文
  // v28 step 82: 表格行号 + 内容同行（必须在 step 5.4 之前执行，避免破坏 3 行结构）
  //   模式 1："1\nIndividual MNBs treatment\nMNBs" → "1 Individual MNBs treatment MNBs"（3 行结构）
  //   仅匹配短文本（≤80 字符）的单数字行（避免与段落首行编号冲突）
  //   第三行允许多种模式：纯缩写（MNBs）/ 大写开头单词（UV）/ 单词+数字（UV0.5）
  result = result.replace(/^(\d{1,2})\s*\n\s*([A-Z][^\n]{1,80}?)\s*\n\s*([A-Za-z][A-Za-z0-9.\-/]{0,15})\s*$/gm, '$1 $2 $3')
  // v28 step 82: 表格行号 + 内容同行（2 行结构）
  //   模式 2："2\nUV irradiation for 0.5 min in combination with MNBs treatment MNBs/UV0.5"
  //         → "2 UV irradiation for 0.5 min in combination with MNBs treatment MNBs/UV0.5"
  //   紧跟在 Tab. N. 描述后的单数字行 + 内容（无第 3 行）
  //   必须 ≥20 字符的内容避免误匹配段落首行编号
  result = result.replace(/^(\d{1,2})\s*\n\s*([A-Z][^\n]{20,150}?)\s*$/gm, '$1 $2')
  // 然后跑章节编号同行（5.4）
  //   v28 step 100 修复：\s* 不能吃 \n\n（否则会把 "2.2\n\n正文" 合并成 "2.2 正文"）
  //   改成 [ \t]*（仅水平空白，不吃换行）
  result = result.replace(/^(\d+(?:\.\d+)*)[ \t]*\n([^\n])/gm, '$1 $2')
  // v28 step 100: OCR 把章节号单独成行（"1\n\n正文"），合并到正文开头
  //   "1\n\nEnsuring the safety..." → "1. Ensuring the safety..."
  //   "2.2\n\n正文" → "2.2. 正文"
  result = result.replace(/^(\d+(?:\.\d+)*)[ \t]*\n[ \t]*\n[ \t]*([A-Z])/gm, '$1. $2')
  // v28 step 101 撤掉（太激进误删年份/章节号），保留 fixture 实际行为
  //   用户需自行接受 `cereus 3 (Grutsch` 的 `3` OCR phantom 残留（无害）

  // v28 step 85 强制保险：如果前面 regex 没生效（生产部署某些边缘 case），
  // 这里用最宽松的 regex 把"数字紧贴大写字母"的位置强制加空格。
  // 例："1Individual" → "1 Individual"，"2.2Preparation" → "2.2 Preparation"
  // 排除版本号（"v1.5a" → 保留，无空格，因为小写 'a'）
  // 模式：行首/空格 + 数字（带或不带小数） + 大写字母 → 加空格
  result = result.replace(/(\s|^)(\d+(?:\.\d+)*)([A-Z])/g, (m, ws, num, letter) => {
    return ws + num + ' ' + letter
  })

  // v28 step 89: OCR 把章节标题与正文黏在一行（如 "4.2 The mechanism of continuous
  //   sterilization by UV-enhanced MNB water Our findings reveal that..."）。
  //   标题是 Title Case（每个词首字母大写），正文是 Sentence case（仅句首大写）。
  //   边界信号：标题末尾小写字符 → 空白 → 正文首大写字母开头。
  //   例："MNB water Our findings" → "MNB water\n\nOur findings"
  //   限制：仅在 numbered section（level >= 2）后应用，避免误伤普通段落。
  //   模式：^\d+(\.\d+)+ + 标题（[A-Z].*?[a-z]）+ 空白 + lookahead 大写
  result = result.replace(
    /^(\d+(?:\.\d+)+\s+[A-Z].*?[a-z])\s+(?=[A-Z][a-z]+\s)/gm,
    '$1\n\n'
  )

  // v28 step 81: PDF 提取的页码标记 P2/P4-6/P7-8 紧跟在英文章节标题后面
  //   "IntroductionP4-6Ensuring..." → "Introduction\n\nP4-6\n\nEnsuring..."
  //   "Materials and methodsP7-82.1 Test system..." → "Materials and methods\n\nP7-8\n\n2.1 Test system..."
  //   1. 英文单词 + P + 数字 + 数字/换行 + 内容 → 英文单词 \n\n P数字 \n\n 内容
  //   2. 章节标题 + 数字 + "." + 内容（sub-section）→ 章节标题 \n\n 数字. 内容
  result = result.replace(
    /([A-Za-z][a-z]+(?: [a-z]+)*)P(\d+(?:-\d+)?)([^\n])/g,
    '$1\n\nP$2\n\n$3'
  )
  // 紧跟数字 + . + 标题：保留 . 作为 markdown heading 标记
  result = result.replace(
    /^(\d+\.\d+)\s+([A-Z][a-zA-Z\s]{2,})$/gm,
    '$1 $2'
  )

  // 5.5 v28 step 75: 期刊元信息块剥离（Corresponding author / Contents lists / E-mail / Received）
  //   这些是论文 header / footer 元信息，不属于正文内容
  result = result.replace(/Corresponding author at:[^\n]*\n[^\n]*E-mail address:[^\n]*\n?/gi, '')
  result = result.replace(/Contents lists available at[^\n]*\n[^\n]*journal homepage:[^\n]*\n?/gi, '')
  result = result.replace(/Received \d{1,2}\s+\w+\s+\d{4}[;\s]*/gi, '')
  result = result.replace(/\d{4}[-\s]Elsevier[^\n]*\n[^\n]*\n?/gi, '')

  // 5.6 v28 step 76 + step 82: Elsevier "CEJ 171737" / "P2 Please cite this article" 块
  //   这些是 PDF header 的 article id + citation 块，应该完全剥除
  result = result.replace(/\b[A-Z]{2,5}\s+\d{3,7}\s+To appear in:[\s\S]{0,400}?/gi, '')
  result = result.replace(/\bP\d+\s+Please cite this article as:[\s\S]{0,400}?(?:doi\.org\/[^\s]+|10\.\d{4,9}\/[^\s]+)/gi, '')
  // "This is a PDF of an article..." 到 "early visibility" 整段
  result = result.replace(/This is a PDF of an article that has undergone[\s\S]{0,1500}?early visibility of the article\.?/gi, '')
  // v28 step 82: 兼容 "Please note that"（无 also）和 "Please also note that"（有 also）两种开头
  //   + 兼容单词逐行 OCR（"Please\nalso\nnote" 在 step 5.1a 已合并为 "Please also note"）
  //   + "early visibility" 终止符或 "pertain." 终止符
  result = result.replace(/Please\s+(?:also\s+)?note\s+that\s*,?\s+during\s+the\s+production\s+process[\s\S]{0,800}?(?:pertain\.|early visibility)/gi, '')
  // "Please note that Elsevier's sharing policy..." 到 "Published Journal Article applies to this version" 段
  result = result.replace(/Please\s+note\s+that\s+Elsevier[\s\S]{0,600}?sharing#?\d?-?[Pp]ublished-[Jj]ournal-[Aa]rticle\.?/gi, '')
  // "As such, this version is no longer the Accepted Manuscript"
  result = result.replace(/As such, this version is no longer the Accepted Manuscript[\s\S]{0,400}?early visibility of the article\.?/gi, '')
  // v28 step 82: 版权行剥离（Elsevier/Springer/Wiley 等）
  result = result.replace(/©\s*\d{4}\s+(?:Published by|Elsevier|Springer|Wiley|American Chemical Society|IOP Publishing|Royal Society of Chemistry|IEEE)\s+(?:B\.V\.|Ltd\.|Inc\.|Chemical Society|Publishing)?[\s\S]{0,200}?(?:\n|$)/gi, '')
  result = result.replace(/Copyright\s+(?:©|\(c\))\s*\d{4}[\s\S]{0,200}?(?:\n|$)/gi, '')
  // 重复的 Journal Pre-proof
  result = result.replace(/(Journal Pre-proof[\s\n]*){2,}/gi, 'Journal Pre-proof\n')
  result = result.replace(/^\s*Journal Pre-proof\s*$/gim, '')
  // v28 step 100: 清理 [PAGE:N] + Journal Pre-proof 紧贴模式（消除边界冲突）
  //   例: '[PAGE:2]Journal Pre-proof\n1\n正文' → '[PAGE:2]\n1\n正文'（让 PAGE:N 后强制换行）
  result = result.replace(/(\[PAGE:\s*\d+\s*\])\s*Journal Pre-proof/g, '$1\nJournal Pre-proof')
  // v28 step 99: OCR 工具把 'Journal Pre-proof N' 水印错误插入到英文段落中间
  //   例 1: '... a MNB\nJournal Pre-proof generator (RuiDe...' → '... a MNB generator (RuiDe...'
  //   例 2: '... B. cereusJournal Pre-proof\n3 (Grutsch...' → '... B. cereus\n3 (Grutsch...'
  //   例 3: '...MNB/UV technology.\nJournal Pre-proof\n7 Fig. 1...' → '...MNB/UV technology.\n7 Fig. 1...'
  //   触发条件: 后面是数字（页码）/ 小写字母 / 大写字母开头（章节标题/正文）
  //   替换为空格，让前后内容正确合并
  result = result.replace(/(\S)\s*\n?\s*Journal Pre-proof\s*\n?\s*(\S)/g, '$1 $2')

  // 模式 A2: cereus 后接 [PAGE:N] page marker 再接 phantom 数字（v45 移到 step 99 之后）
  //   "cereus\n[PAGE:4] 3 (Grutsch" → "cereus 3 (Grutsch"
  //   "cereus\n[PAGE:4]\n 3 (Grutsch" → "cereus 3 (Grutsch"
  //   必须跑在 step 99 OCR watermark 合并之后（否则 Journal Pre-proof 隔开 cereus 和 3）
  //   必须含 [PAGE:N] 标记（不像 v42 用 [ \t\n]* 容忍任何空白）
  //   避免 'Pre-proof' 后 \n\n3 误匹配（v43 A1 双空行要求已排除）
  result = result.replace(
    /([a-z)\]])\s*\n\s*\[PAGE:\s*\d+\s*\][ \t\n]*\s*(\d{1,3})\s+(?=\()/g,
    '$1 $2 '
  )

  // 5.7 v28 step 76 + step 82: 参考文献标识统一
  //   "Reference\n参考文献（共 1 条）\n展开全部 ▾" → 统一为 References 章节
  result = result.replace(/参考文献[（(]共\s*\d+\s*条[）)]\s*\n?/g, '')
  result = result.replace(/展开全部\s*[▾▼]+\s*\n?/g, '')
  // v28 step 82: 严格限定 — 只在独立行的 References 标题才转换（避免误伤 front matter 的 "Reference: CEJ 171737"）
  //   markdown 模式加 ## 前缀（让 parsePaperSections 当 heading 处理），plain text 模式不加
  if (isMarkdown) {
    result = result.replace(/^\s*References?\s*$\n?/gim, '## References\n')
  }
  // 兜底：剥离 front matter 中的 "Reference: <id>" 元数据（Elsevier 期刊文章 ID）
  result = result.replace(/^\s*Reference\s*[：:]\s*[A-Z]{2,5}[\s\d]+\s*$/gim, '')

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
function extractPageMarkers(content) {
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
function extractFigureMarkers(content) {
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
function extractTableMarkers(content) {
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
  let trimmed = text.trim()
  if (!trimmed || trimmed.length > 120) return null

  // v28 fix: 先剥除行首 [PAGE:N] 标记（OCR 内容常粘在标题前）
  // 例: "[PAGE:6]3.4. Anti-interference ..." → "3.4. Anti-interference ..."
  // 否则 NUMBERED_SECTION_RE 匹配失败 → 3.4 章节被跳过（3.3 直接跳到 3.5）
  trimmed = trimmed.replace(/^\[PAGE:\s*\d+\s*\]\s*/, '')

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
  // v28 fix: 末尾是 "-" 或 "of"/"the"/"a" 等英文小写残词 → 标记 continued，
  //   让 _parsePlainTextSections 把下一行合并到标题末尾
  //   例: "3.3. Influence ... O3-" → 下一行 "MNBs system" 合并 → 完整标题
  // v28 step 89: continued 仅在 stripped 长度 ≤ 40 时用 lowercase 短词判定（更严格）。
  //   长标题（如 "4.2 The mechanism of continuous sterilization by UV-enhanced MNB water"，
  //   70 字符）末尾 "water" 是 Title Case 标题结尾（不是断字），不应触发合并下一行，
  //   否则 OCR 黏在标题后的正文 "Our findings..." 被错误合并进 title
  let continued = false
  if (stripped.endsWith('-')) {
    continued = true
  } else if (stripped.length <= 40) {
    // 短标题末尾是否英文单词残段（小写字母结尾、不在句末标点）
    const lastWord = stripped.split(/\s+/).pop() || ''
    if (/^[a-z]{1,5}$/.test(lastWord) && !/[.!?]$/.test(stripped)) {
      // 短小写单词结尾且整句无终止标点 → 可能是断字
      continued = true
    }
  }

  if (numbered) {
    // v28 step 87 修复：单数字 level=1 的"编号行"极容易误吃表格行（OCR 把表格行号
    //   "1\nIndividual MNBs treatment" 已合并成 "1 Individual MNBs treatment"，但
    //   NUMBERED_SECTION_RE 也会匹配 "7 Fig. 1." 把页码+图注当章节标题）。
    //   强约束：level=1 时 stripped 必须**包含** SECTION_KEYWORDS 关键词
    //   （Introduction/Methods/Results/Discussion/Conclusion 等），否则拒绝。
    //   level >= 2（如 2.2 / 3.4.1）保留原行为 — 这些是小章节标题，几乎不与表格行冲突。
    if (level === 1) {
      const isSectionHeading = SECTION_KEYWORDS.some((kw) => kw.regex.test(stripped))
      if (!isSectionHeading) return null
    }
    return { type: 'normal', level, continued }
  }

  // 中文编号：一、二、三、
  if (cnNumbered) {
    // 同上：中文单编号也要求 stripped 命中 SECTION_KEYWORDS（中文关键词）
    const isSectionHeading = SECTION_KEYWORDS.some((kw) => kw.regex.test(stripped))
    if (!isSectionHeading) return null
    return { type: 'normal', level: 1, continued }
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

// ---- 本段对外导出（供下游段 import，勿删）----
export { cleanContent }
export { removeFrontMatter }
export { extractPageMarkers }
export { extractFigureMarkers }
export { extractTableMarkers }
export { _matchSectionTitle }
