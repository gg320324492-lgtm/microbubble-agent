// QA 库条目识别（_tryExtractQA / _cleanQAAnswer / _buildQAPaperDetail）。
import { _isChineseHeavy } from './constants'


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
function _tryExtractQA(content) {
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
function _cleanQAAnswer(answer) {
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
function _buildQAPaperDetail(raw, question, answer, extra) {
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

// ---- 本段对外导出（供下游段 import，勿删）----
// _cleanText / _tryExtractQA / _cleanQAAnswer / _buildQAPaperDetail 均为段内实现，
// 但 normalize 段要调后三者，故必须跨段导出。
// 注意：这三个符号在拆分前带 export 是"为防 Vite/Rollup tree-shake"（见原 L285 注释），
// 而**外部消费者（8 处 import + 测试）零使用** —— 本次拆分把它们从公共 API 面收回，
// 仅保留 normalize 段所需的跨段引用。
export { _cleanText, _tryExtractQA, _cleanQAAnswer, _buildQAPaperDetail }
