// 常量与共享单例：模块级正则、_idCounter/_genId 单例、转义与文本工具。
// ⚠️ 本文件是 9 条带 /g 模块级正则的唯一持有者 —— 禁止在任何其它文件复制，
//    复制会导致两份 lastIndex 各自漂移，替换结果随机不一致。
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

// ---- 本段对外导出（供下游段 import，勿删）----
export { _isChineseHeavy }
export { _genId }
export { _escapeHtml }
export { _stripMultimodalBlocks }
export { SECTION_KEYWORDS }
export { NUMBERED_SECTION_RE }
export { PAGE_MARKER_RES }
export { FIGURE_MARKER_RE }
export { TABLE_MARKER_RE }
export { URL_RE }
export { SPACED_TITLE_RE }
export { HTML_ATTR_RES }
export { INTERNAL_MARKER_RES }
export { FOOTER_PATTERNS }
export { REFERENCE_ENTRY_RE }
export { EMAIL_RE }
export { DOI_DUP_RE }
export { DOI_DUP_NOPROTO_RE }
export { IMG_EXT_RE }
