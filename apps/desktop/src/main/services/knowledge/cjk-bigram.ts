// CJK bigram 预切词 — FTS5 中文检索的选型方案（M2-1 探针定案）。
// unicode61 tokenizer 把连续 CJK 串当成一个 token，2 字词永远搜不到；trigram tokenizer
// 规定 <3 字符 token 不命中，2 字中文词同样搜不到。故在应用层做重叠 bigram 预切：
// 「中文检索」→ 「中文 文检 检索」，查询侧同一切分后作 phrase 匹配，2 字词即单 token 精确命中。
// 非 CJK 段按空白拆词并小写化。纯函数，双运行时（node:sqlite / better-sqlite3）行为一致。

const CJK_RUN = /[\u4e00-\u9fff]+|[^\u4e00-\u9fff]+/g
const IS_CJK = /^[\u4e00-\u9fff]+$/

/** 文本入库/更新前：转成 FTS 索引用的切词文本 */
export function segmentForIndex(text: string): string {
  return segment(text).join(' ')
}

/** 查询侧：同一切分，返回 phrase 匹配串（如 "中文 文检 检索"）；无有效 token 返回 null */
export function matchPhraseFor(query: string): string | null {
  const tokens = segment(query)
  if (tokens.length === 0) return null
  return `"${tokens.join(' ')}"`
}

function segment(text: string): string[] {
  const tokens: string[] = []
  for (const chunk of text.match(CJK_RUN) ?? []) {
    if (IS_CJK.test(chunk)) {
      if (chunk.length === 1) {
        tokens.push(chunk)
      } else {
        for (let i = 0; i < chunk.length - 1; i++) tokens.push(chunk.slice(i, i + 2))
      }
    } else {
      for (const word of chunk.split(/\s+/)) {
        const clean = word.toLowerCase()
        // 丢掉不含任何字母/数字的纯符号 token（FTS 侧本就无法命中）
        if (clean && /[\p{L}\p{N}]/u.test(clean)) tokens.push(clean)
      }
    }
  }
  return tokens
}
