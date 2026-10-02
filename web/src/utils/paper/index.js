// paperAdapter 聚合入口（S3.8 拆分产物）
//
// ⚠️ 这里**刻意不用 `export *`** —— 那会把 31 个段内符号（正则表、_genId、
//    各段私有 helper）一并暴露，等于在"拆文件"的名义下**扩大**了公开 API 面。
//    拆分前 paperAdapter.js 只有 23 个具名 + 1 个 default(12 键)，拆完必须还是这些。
//    下方 23 个具名 + 12 键 default 由 S3.8 冻结断言逐个锁住。
import { normalizePaperData, normalizeGraphData, classifySectionType } from './normalize'
import { parsePaperSections, splitReferences } from './sections'
import {
  cleanContent, removeFrontMatter, extractPageMarkers,
  extractFigureMarkers, extractTableMarkers, normalizeDoiText,
  insertSectionBreaks,
} from './content'
import {
  matchFiguresWithCaptions, classifyImageKind, buildAnchorTree, autoLinkContent,
} from './figures'
import {
  translateKeywordToEnglish, translateKeywordsToEnglish, extractAuthorsAndJournal,
  KEYWORD_ZH_TO_EN,
} from './figures'
// 三个 QA 后门：拆分前带 export 仅为防 tree-shake，外部消费者零使用。
// 拆分后仅 normalize 段需要它们 —— 已在其内部 import，此处**不再转发**，
// 公开面由 23 收窄到 20（与 S3.8 冻结断言一致）。

export {
  normalizePaperData, normalizeGraphData, classifySectionType,
  parsePaperSections, splitReferences,
  cleanContent, removeFrontMatter, extractPageMarkers,
  extractFigureMarkers, extractTableMarkers, normalizeDoiText, insertSectionBreaks,
  matchFiguresWithCaptions, classifyImageKind, buildAnchorTree, autoLinkContent,
  translateKeywordToEnglish, translateKeywordsToEnglish, extractAuthorsAndJournal,
  KEYWORD_ZH_TO_EN,
}

// default 与拆分前逐字一致（12 键），每个键与同名具名导出是**同一函数对象引用**
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
