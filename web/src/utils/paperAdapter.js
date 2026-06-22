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

// v28 step 10: 引入化学式格式化器，让 paperAdapter 内部就处理 Unicode 上下标
import { formatScientificText } from './chemFormat'

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
  { type: 'results', regex: /^\s*(\d+(\.\d+)*\.?\s+)?(results?(\s+and\s+(?:discussion|analysis))?|结果(与讨论|和分析)?|实验结果|结果与讨论)\s*[:：]?\s*$/i },
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
// - 用 lookforward 而非消费：不吞掉标题第一个字符
const NUMBERED_SECTION_RE = /^\s*(\d{1,2}(\.\d{1,2}){0,3})\.?\s+(?=[A-Z一-龥])/

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
  // PDF 页码标记（多种格式）
  // v28 fix: 完整保留 [PAGE:N] 标记，让 cleanContent 后续的 extractPageMarkers 提取
  // （任何形式的删除 [PAGE:N] 都会让 pageMarkers=0 → sections 解析失败 → 正文压成 1 段）
  //
  // 历史教训:
  //   - \bPAGE\s*[:：]\s*\d+\b 会匹配 [PAGE:1] 的中间 PAGE:1 部分
  //     （[ 是 non-word, P 是 word, 构成 \b 边界）→ 替换后 [PAGE:1] 变 []
  //   - ([A-Z]\.\s*[A-Z][a-z]+...)\s+\d+\s*\[PAGE:\s*\d+\s*\] 会把
  //     'T. Wang et al. 3 [PAGE:4]' 整段删除（PDF 上下文丢失）
  // === v26 回归修复新增（执行顺序很重要） ===
  // 1) 中文图注（含 JSON 或纯页码）必须先剥，贪婪匹配整段 "图（P8，{...}）"
  //    若后剥则 JSON 正则先吃掉 {...}，留下孤儿 "图（P8，）" 无法再匹配
  /图\s*[（(]\s*[Pp]?\d+\s*(?:[,，]?\s*\{[^）)]*\})?\s*[）)]/g,
  // 2) "图表说明（P4）" / "图表描述" 等纯文本中文图注
  /图表(?:说明|描述|caption)\s*[（(]\s*[Pp]?\d+\s*[）)]/gi,
  // 3) "Figure caption (P4)" / "Caption (P4)" 英文变体
  /(?:Figure|Table|Caption)\s+caption\s*[（(]\s*[Pp]?\d+\s*[）)]/gi,
  // 4) 多模态 OCR 块标记
  /MULTIMODAL_INLINED[^\n]*/gi,
  /OCR_TEXT[^\n]*/gi,
  // 5) JSON 残留（孤立的 {category:..., kind:..., ...}）—— 放在中文图注之后，避免抢匹配
  /\{\s*['"`]?(?:category|kind|type|model|source|confidence|page_number)['"`]?\s*:\s*['"`]?[^}]{0,200}['"`]?\s*,?\s*\}/gi,
  // 6) agent/minio 内网图片 URL（即使在正文中也不应直接显示）
  /https?:\/\/(?:agent\.)?mnb-lab\.cn\/minio\/[^\s<>"'\)]+/gi,
  /https?:\/\/localhost:\d+\/minio\/[^\s<>"'\)]+/gi,
  // v28 step 90: orphan PDF 页码（OCR 把页码插入英文段落开头）
  //   例："during\n\n15 disinfection." → "during disinfection."（保留空格）
  //   必须在 step 5.1b 软连字符合并（line 716）之后跑，否则空格被吃
  //   这里只剥 [PAGE:N] 占位符变种（[PAGE:15]），单数字 15 由 step 5.1b 之后单独 regex 处理
  // v28 step 82: Elsevier PDF header 元信息（Reference / DOI / PII / To appear in 等）
  //   这些通常以 `Reference:\nCEJ 171737` / `DOI:\nhttps://...` / `PII:\nS1385-...` 形式出现
  //   必须按整行剥，避免干扰正文引用识别
  /^\s*PII\s*[：:]\s*\S+\s*$/gim,
  /^\s*DOI\s*[：:]\s*https?:\/\/\S+\s*$/gim,
  /^\s*Reference\s*[：:]\s*[A-Z]{2,5}\s+\d+\s*$/gim,
  /^\s*Received\s+date\s*[：:][^\n]*$/gim,
  /^\s*Revised\s+date\s*[：:][^\n]*$/gim,
  /^\s*Accepted\s+date\s*[：:][^\n]*$/gim,
  /^\s*To\s+appear\s+in\s*[：:]?\s*$/gim,
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

  // v28 step 76: PDF Header 元信息块（CEJ Article ID + 接受日期 + 引用格式）
  //   "CEJ 171737 To appear in: ..." "P2 Please cite this article as: ..."
  //   "To appear in:" / "Received date:" / "Revised date:" / "Accepted date:"
  //   "Please cite this article as:" / "This is a PDF of an article that has undergone"
  //   "Please also note that, during the production process" / "Journal Pre-proof"
  /\b[A-Z]{2,5}\s+\d{3,7}\s+To appear in:[^\n]*(\n(?!\n)[^\n]*){0,5}/gim,
  /\b(?:Received|Revised|Accepted)\s+date:\s*\d{1,2}[\s\S]{0,100}\d{4}[^\n]*/gi,
  /Please cite this article as:[^\n]*\n[^\n]*doi\.org\/[^\s]+[^\n]*/gi,
  /This is a PDF of an article that has undergone[\s\S]{0,800}?about\/policies-and-standards\/sharing[^\n]*/gi,
  /Please also note that, during the production process[\s\S]{0,300}?pertain\.[^\n]*/gi,
  /As such, this version is no longer the Accepted Manuscript[\s\S]{0,300}?this version\./gi,
  /As such, this version is no longer the Accepted Manuscript[\s\S]{0,300}?early visibility of the article\.?/gi,
  /Journal Pre-proof\s*Journal Pre-proof/gi,
  /^\s*Journal Pre-proof\s*$/gim,
  // v28 step 89: 剥除独立行的页码范围标记（P28-29 / P33-39 / P12 等）
  //   Elsevier Pre-proof PDF 在每段末尾插入 "P28-29" 这种 phantom 行，
  //   混入正文中间（如 "...intrinsic tolerance mechanism\nP28-29\nand improving..."）
  //   必须早剥除，否则 parsePaperSections 把它当 paragraph 内容
  /^\s*P\d{1,3}(?:-\d{1,3})?\s*$/gim,
  // DOI 单独一行（bare DOI 行）
  /^\s*10\.\d{4,9}\/[^\s]+\s*$/gim,
  // v28 step 17: 作者署名 + 页码行（"T. Wang et al.                                                                                      6"）
  //    PDF 渲染时页脚会重复作者名 + 大量空白 + 当前页码
  //    这种行后面紧跟 OCR 错位的图片 alt 文本（"such ![ as radical..."），
  //    把整行剥除能消除 80% 的字符乱
  //
  // 严格限制：只匹配整行只有「作者名 et al. + 数字（页码）+ 大量空白」
  // 不能含 [PAGE: (否则会把 [PAGE:4] 也吃掉，v28 article 9 字 bug 教训)
  /^[A-Z]\.\s*[A-Z][a-z]+\s+et\s+al\.\s+\d{1,3}\s*$/gim,
  /^[A-Z]\.\s*[A-Z][a-z]+\s+et\s+al\.\s*$/gim,
  // 单页码行（孤立数字 + 大量空白，但 [PAGE:N] 格式保留 —— [PAGE:N] 含 `:` 不匹配 \d{1,3}）
  /^\s*\d{1,3}\s*$/gm,
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

/**
 * v26.1: 专门剥除多模态 chart 描述块
 *
 * OCR 经常把多模态图描述输出为 JSON 结构：
 *   { "category": "mixed", "text": "(a) ... (b) ... coupling and electron transfer between toluene..."}
 *
 * 但 OCR 经常漏闭合 },导致结构化块溢出到正文中。
 *
 * 终止条件（任一）：
 * - 英文学术句末: . [大写字母开头的单词] [小写单词]
 * - markdown 图片语法: ![
 * - 段落分隔: 


 * - 字符串末尾
 *
 * 起始条件（必须全部满足）：
 * - { "category"|"kind": "<以下类型之一>"
 * - 类型白名单: mixed|chart|figure|formula|table|image_block|extraction|graph|plot|spectrum|figure_block
 */
function _stripMultimodalBlocks(text) {
  if (!text) return text
  // 直接正则字面量（避免 RegExp constructor 的反斜杠转义陷阱）
  //
  // 匹配 { "category|kind": "<类型>" 起始的多模态 chart 描述块。
  // 容忍 { 和 key 之间的空格（OCR 经常漏压缩）
  //
  // 关键纪律（重要）：**禁止**用 $ 作为终止符 —— 否则在没有真实边界的输入上
  //   非贪婪 + $ lookahead 会贪婪扩展到字符串末尾，吃掉正文。
  //   必须强制要求真实终止符（\. 学句末 / !\[ 图片 / \n\n 段落分隔）
  //
  // 限长 800 字符（多模态块典型 100-400 字符，余量足够）
  const re = /\{\s*['"]?(?:category|kind)['"]?\s*:\s*['"](?:mixed|chart|figure|formula|table|image_block|extraction|graph|plot|spectrum|figure_block)['"][^}]{0,800}?(?=\.\s+[A-Z][a-z]+\s+[a-z]|\s*!\[|\n\s*\n)/gi
  return text.replace(re, '')
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
  return cn > 30
}


// ============================================================================
// v28 step 71: QA 库条目识别 + 内容清理
// 早期 LLM 自动入库的 [拓展-XXX] 全部是 `## 问题\n...\n## 回答\n...` 格式
// 这些不该走 markdown 解析（会产生一堆碎 paragraph），而应渲染为 Q&A 卡片
// ============================================================================

/**
 * 检测内容是否是 QA 库格式（"## 问题 ... ## 回答 ..."）
 * 返回 {question, answer} 或 null
 */
// v28 step 71 + 72: 导出保证 Vite/Rollup 不会 tree-shake 掉（async chunk 加载时引用）
export function _tryExtractQA(content) {
  if (!content || !content.trim()) return null
  // 严格匹配开头的 ## 问题 / ## 回答 块
  const m = content.match(
    /^##\s*问题\s*\n+([\s\S]+?)\n+##\s*回答\s*\n+([\s\S]+?)(?:\n+---+\n*|\s*)$/
  )
  if (!m) return null
  const question = m[1].trim()
  const answer = m[2].trim()
  if (!question || !answer) return null
  // 必须中文（避免误判英文论文）
  if (!_isChineseHeavy(content)) return null
  return { question, answer }
}

/**
 * 清理 QA 回答里的常见 LLM 噪声：
 * - "王老师，您好！" 客套话
 * - 末尾 "如果...我可以继续为您搜索..." 自生成话
 * - "## 📋 xxx" emoji 装饰标题（保留但去除装饰）
 * - 重复的"## 总结"段落（去掉冗余）
 */
export function _cleanQAAnswer(answer) {
  if (!answer) return ''
  let out = answer

  // 1. 去掉开头客套话（"X老师您好"、"您好！"、"您好：" 等）
  out = out.replace(/^(.{0,8}老师[，,：:]?\s*)?您?[好您好][呀啊]?[！!。,\s]*?(?=根据|基于|关于|微|以下|我|对于)/u, '')

  // 2. 去掉末尾 LLM 自生成话（"如果...我可以..."、"希望对您有帮助"）
  const cutMarkers = [
    /如果您想进一步探讨[\s\S]*$/u,
    /如果您需要[\s\S]*$/u,
    /希望对您[\s\S]*$/u,
    /我可以继续[\s\S]*$/u,
    /如您[\s\S]*?我(?:们)?可以[\s\S]*$/u,
  ]
  for (const re of cutMarkers) {
    out = out.replace(re, '')
  }

  // 3. 去掉 ## 总结 / ## 结论 / ## 小结 冗余收尾（保留正文，让小标题继续）
  // 不删除，避免破坏结构

  // 4. 清理 emoji 装饰：## 📋 xxx → ## xxx
  out = out.replace(/^##\s+([📋📌🔍💡⚙️📊🎯🏷️📝✅🔥⭐])\s*/gm, '## ')

  // 5. 清理 "我为您" / "我帮您" 等 LLM 痕迹开头
  out = out.replace(/^(我[为帮]您[一-龥]{0,20}[，,\s]*)+/u, '')

  return out.trim()
}


/**
 * v28 step 71: 为 QA 库条目构造简化的 PaperDetail
 *
 * 跳过常规的 paper section 解析，直接返回：
 * - 1 个 section (type='qa')
 * - 2 个 block: {type: 'qa_question', content} + {type: 'qa_answer', content}
 *
 * PaperBlockRenderer 用专门的 Q&A 卡片样式渲染
 */
export function _buildQAPaperDetail(raw, question, answer, extra) {
  // 计算摘要：answer 前 150 字符（去 ## 标题前缀）
  const summary = (raw.summary || '')
    || answer.replace(/^#+\s*[^\n]*\n+/gm, '').slice(0, 200).trim()

  return {
    id: raw.id,
    title: raw.title,
    summary,
    section: 'qa',
    sections: [
      {
        id: 'qa-section',
        type: 'qa',
        title: '问答',
        blocks: [
          { type: 'qa_question', content: question, page: null },
          { type: 'qa_answer', content: answer, page: null },
        ],
      },
    ],
    // QA 库无关键词/实体/引用
    references: [],
    keywords: [],
    keyConcepts: [],
    relatedTopics: [],
    entities: [],
    images: extra.images || [],
    extractions: extra.extractions || [],
    inlineFigureAnchors: {},
    figureRegistry: [],
    pageMarkers: [],
    figureMarkers: [],
    raw,
    extra,
    _status: 'success',
  }
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
export function removeFrontMatter(content) {
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

  if (!isElsevierPreProof) {
    // 普通论文 front matter（含独立 Abstract section）— 不剥离，让原解析器处理
    return { cleaned: result, abstract: null, keywords: [], frontMatter: '', hasFrontMatter: false }
  }

  // 2. v28 step 82: 从 Elsevier front matter 抽出 Abstract + Keywords
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
  const kwMatch = frontMatter.match(/Keywords?\s*[：:]?\s*([^\n]+(?:\n[^\n]+)*?)(?=\n\s*(?:\d+\.\s*(?:Introduction|引言)|1\.|$))/i)
  if (kwMatch) {
    keywords = kwMatch[1]
      .replace(/[；;]/g, ',')  // 中英文分号统一
      .split(/[,，]/)
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
export function cleanContent(text, options = {}) {
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
        const text = paraBuf.join('\n').trim()
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
export function splitReferences(content) {
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

export function autoLinkContent(text) {
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
 *     categories: [{name}] }
 *
 * @param {Object} rawGraphData - 后端返回的图谱数据
 * @returns {Object} ECharts 兼容的图谱数据
 */
export function normalizeGraphData(rawGraphData) {
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
    const id = String(n.id || n.node_id || n.name || n.label || n.title || n.text || `node-${Math.random()}`)
    const name = n.name || n.label || n.title || n.text || id
    const value = Number(n.value ?? n.weight ?? n.score ?? n.count ?? 1)
    const category = n.category || n.type || n.group || 'default'
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

  // 5. categories
  const categorySet = new Set(nodes.map(n => n.category).filter(Boolean))
  const categories = [...categorySet].map(name => ({ name }))

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
  if (content && !keywords.length) {
    const detectedKw = _detectKeywordsFromContent(content)
    if (detectedKw.length) keywords = detectedKw
  }

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


/**
 * 把 section 列表的 type 字段标准化为前端的视图分类
 */
export function classifySectionType(section) {
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

  // ── 1. 按 vision 输出的 blocks 顺序遍历，构建 sections
  //    遇到 heading 块就开新 section，否则累积到当前 section
  const sections = []
  let currentSection = null
  let currentBlocks = []
  let pageMarkers = []
  let figureMarkers = []
  let inlineFigureAnchors = {}
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

  const startSection = (type, title, level) => {
    if (currentSection) {
      // flush 当前 section
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
  }

  const flushCurrent = () => {
    if (currentSection) {
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

  for (const page of pages) {
    const pageNum = page.page_number
    const blocks = (page.blocks || []).slice().sort((a, b) => (a.order || 0) - (b.order || 0))
    for (const b of blocks) {
      if (b.type === 'page_header' || b.type === 'page_footer') {
        // 跳过页眉页脚
        continue
      }
      if (b.type === 'heading') {
        const level = b.level || 1
        const title = (b.text || '').trim()
        if (!title) continue
        // 用 _matchSectionTitle 判定 type（识别 Introduction/Methods/Results 等关键词）
        const matched = _matchSectionTitle(title)
        let secType
        let secLevel
        if (matched) {
          secType = matched.type
          secLevel = matched.level || level
        } else if (level === 1) {
          // level=1 且不匹配任何 SECTION_KEYWORDS → preamble（论文主标题/期刊名）
          secType = 'preamble'
          secLevel = 1
        } else {
          // 其他情况 → normal
          secType = 'normal'
          secLevel = level
        }
        startSection(secType, title, secLevel)
      } else if (b.type === 'paragraph') {
        const text = (b.text || '').trim()
        if (!text) continue
        // 没开 section 就先开一个 preamble
        if (!currentSection) startSection('preamble', '前言', 1)
        currentBlocks.push({
          type: 'paragraph',
          content: text,
          page: pageNum,
          indexInSection: currentBlocks.length,
        })
        pidCounter++
      } else if (b.type === 'image') {
        // 关联到 knowledge_images 表的图
        const imgIndex = b.image_index || 0
        const img = imageByGlobalIndex[imgIndex]
        if (!currentSection) startSection('normal', '未命名', 2)
        // 把 image 关联到当前 section 最后一个 paragraph
        const pidKey = `${currentSection.id}__p${currentBlocks.length - 1}`
        if (!inlineFigureAnchors[pidKey]) inlineFigureAnchors[pidKey] = []
        if (img) {
          inlineFigureAnchors[pidKey].push(img)
          figureRegistry.push({
            id: img.id,
            page: pageNum,
            figureNo: img.figureNo || b.figure_no || null,
            figureType: img.figureType || null,
            caption: b.caption || null,
            isCoreFigure: img.isCoreFigure !== false,
            isPublisherImage: !!img.isPublisherImage,
            visualSummary: img.visualSummary || null,
            sectionHint: img.sectionHint || null,
            anchorText: img.anchorText || null,
          })
        } else {
          // 没关联到图，登记一个空 fig（保留 caption 用于显示）
          figureRegistry.push({
            id: `vision-page${pageNum}-img${imgIndex}`,
            page: pageNum,
            figureNo: b.figure_no || null,
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
        currentBlocks.push({
          type: 'image_anchor',
          page: pageNum,
          image_index: imgIndex,
          caption: b.caption || null,
          figure_no: b.figure_no || null,
        })
      } else if (b.type === 'table') {
        const caption = b.caption || null
        const headers = b.headers || []
        const rows = b.rows || []
        const tableMd = [
          '| ' + headers.join(' | ') + ' |',
          '| ' + headers.map(() => '---').join(' | ') + ' |',
          ...rows.map(r => '| ' + r.join(' | ') + ' |'),
        ].join('\n')
        if (!currentSection) startSection('normal', '未命名', 2)
        currentBlocks.push({
          type: 'table',
          content: tableMd,
          page: pageNum,
          caption,
        })
      } else if (b.type === 'formula') {
        if (!currentSection) startSection('normal', '未命名', 2)
        currentBlocks.push({
          type: 'formula',
          content: b.latex || '',
          page: pageNum,
        })
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
  const paperFigures = figureRegistry.map(f => ({
    id: f.id,
    imageId: typeof f.id === 'string' && f.id.startsWith('fig-') ? f.id.slice(4) : null,
    page: f.page,
    figureNo: f.figureNo,
    figureType: f.figureType,
    caption: f.caption,
    isCoreFigure: f.isCoreFigure,
    isPublisherImage: f.isPublisherImage,
    visualSummary: f.visualSummary,
    sectionHint: f.sectionHint,
    anchorText: f.anchorText,
    // src 从 images 找
    src: (() => {
      const img = images.find(i => i.id === f.imageId)
      return img?.src || img?.imageUrl || null
    })(),
  }))

  // ── 4. 检测 abstract（从第一页或 preamble 段）
  let abstract = raw.summary || null
  let keywords = Array.isArray(raw.tags) ? raw.tags.slice() : []
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

  return {
    id: raw.id,
    title: raw.title,
    summary: raw.summary || '',
    abstract,
    keywords,
    sections,
    figures: paperFigures,
    figureRegistry: figureRegistry,
    pageMarkers,
    figureMarkers,
    inlineFigureAnchors,
    inlineFigureMap: {},
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
