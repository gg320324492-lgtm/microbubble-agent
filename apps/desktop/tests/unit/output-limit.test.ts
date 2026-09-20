// M8-1 §1 工具输出预算 — 字节边界 / 策略比例 / 续读提示（全部离线纯函数）
import { describe, expect, it } from 'vitest'
import {
  GREP_CONTENT_MAX_BYTES,
  HEAD_TAIL_HEAD_RATIO,
  READ_TEXT_MAX_BYTES,
  buildContinuationNotice,
  fitUtf8Prefix,
  fitUtf8Suffix,
  limitHeadTailLines,
  limitPrefixLines,
  splitLines,
  takeWholeLinesFromEnd,
  takeWholeLinesFromStart,
  utf8ByteLength
} from '@main/agent/tools/output-limit'

const notice = (ctx: { returnedBodyLines: number; originalBytes: number }): string =>
  buildContinuationNotice({
    originalBytes: ctx.originalBytes,
    maxBytes: READ_TEXT_MAX_BYTES,
    strategy: 'prefix_lines',
    returnedBodyLines: ctx.returnedBodyLines
  })

describe('utf8ByteLength — 按字节而非字符计数', () => {
  it('中文一字 3 字节、emoji 4 字节、ASCII 1 字节', () => {
    expect(utf8ByteLength('abc')).toBe(3)
    expect(utf8ByteLength('中文')).toBe(6)
    expect(utf8ByteLength('😀')).toBe(4)
    expect(utf8ByteLength('')).toBe(0)
    // 关键：字符数 ≠ 字节数（这正是原实现 subarray 会切出乱码的原因）
    expect(utf8ByteLength('中文中文')).toBe(12)
    expect('中文中文'.length).toBe(4)
  })
})

describe('fitUtf8Prefix / Suffix — 绝不在多字节字符中间切断', () => {
  it('前缀：按码点回退，结果永远是合法 UTF-8 且不超预算', () => {
    const text = '中文中文中文' // 18 字节
    for (const budget of [0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 17]) {
      const out = fitUtf8Prefix(text, budget)
      expect(utf8ByteLength(out)).toBeLessThanOrEqual(budget)
      // 不出现替换字符（U+FFFD）即证明没有切断码点
      expect(out).not.toContain('\uFFFD')
      expect([...out].every((c) => text.includes(c))).toBe(true)
    }
    expect(fitUtf8Prefix('中文', 2)).toBe('') // 2 字节放不下一个字 → 空
    expect(fitUtf8Prefix('中文', 3)).toBe('中')
    expect(fitUtf8Prefix('中文', 5)).toBe('中')
    expect(fitUtf8Prefix('中文', 6)).toBe('中文')
  })

  it('后缀：同样不切断码点，且取的是尾部', () => {
    const text = '中文中文'
    expect(fitUtf8Suffix(text, 6)).toBe('中文')
    expect(fitUtf8Suffix(text, 7)).toBe('中文')
    expect(fitUtf8Suffix(text, 2)).toBe('')
    const out = fitUtf8Suffix('a中文', 4)
    expect(utf8ByteLength(out)).toBeLessThanOrEqual(4)
    expect(out).not.toContain('\uFFFD')
  })

  it('预算恰好等于内容字节 → 原样返回（不截断）', () => {
    expect(fitUtf8Prefix('中文', 6)).toBe('中文')
    expect(fitUtf8Suffix('中文', 6)).toBe('中文')
  })
})

describe('prefix_lines 策略（read_file）', () => {
  it('未超预算 → 原样返回且标记未截断', () => {
    const text = '第一行\n第二行'
    const r = limitPrefixLines(text, { maxBytes: READ_TEXT_MAX_BYTES, notice })
    expect(r.truncated).toBe(false)
    expect(r.text).toBe(text)
    expect(r.returnedBodyLines).toBe(2)
  })

  it('超预算 → 逐行装入，结果（含提示）不超预算，且给出 nextOffset', () => {
    const lines = Array.from({ length: 5000 }, (_, i) => `第${i + 1}行 ${'x'.repeat(30)}`)
    const text = lines.join('\n')
    const r = limitPrefixLines(text, { maxBytes: READ_TEXT_MAX_BYTES, notice })
    expect(r.truncated).toBe(true)
    expect(utf8ByteLength(r.text)).toBeLessThanOrEqual(READ_TEXT_MAX_BYTES)
    expect(r.returnedBodyLines).toBeGreaterThan(0)
    expect(r.returnedBodyLines).toBeLessThan(lines.length)
    expect(r.truncation?.nextOffset).toBe(r.returnedBodyLines + 1)
    expect(r.truncation?.originalBytes).toBe(utf8ByteLength(text))
    expect(r.truncation?.maxBytes).toBe(READ_TEXT_MAX_BYTES)
    // 正文里出现的行都是完整的（整行装入）
    const body = r.text.split('\n\n[已截断：')[0]!.split('\n')
    for (const line of body) expect(lines).toContain(line)
  })

  it('多字节内容逐行装入也不切断码点', () => {
    const lines = Array.from({ length: 3000 }, (_, i) => `第${i}行：中文内容中文内容`)
    const r = limitPrefixLines(lines.join('\n'), { maxBytes: 4096, notice })
    expect(utf8ByteLength(r.text)).toBeLessThanOrEqual(4096)
    expect(r.text).not.toContain('\uFFFD')
  })

  it('超长行（单行超预算）→ 回退返回该行前段，而非空内容', () => {
    const text = 'a'.repeat(100 * 1024)
    const r = limitPrefixLines(text, {
      maxBytes: 4096,
      notice,
      oversizedNotice: ({ originalBytes }) =>
        buildContinuationNotice({
          originalBytes,
          maxBytes: 4096,
          strategy: 'prefix_lines',
          returnedBodyLines: 0,
          oversizedLine: true
        })
    })
    expect(r.truncated).toBe(true)
    const body = r.text.split('\n\n[已截断：')[0]!
    expect(body.length).toBeGreaterThan(1024)
    expect(utf8ByteLength(r.text)).toBeLessThanOrEqual(4096)
    expect(r.text).toContain('超长行')
  })
})

describe('head_tail_lines 策略（grep）', () => {
  const headTailNotice = (ctx: {
    returnedBodyLines: number
    originalBytes: number
    omittedLines: number
    retainedHeadLines: number
    retainedTailLines: number
  }): string =>
    buildContinuationNotice({
      originalBytes: ctx.originalBytes,
      maxBytes: GREP_CONTENT_MAX_BYTES,
      strategy: 'head_tail_lines',
      returnedBodyLines: ctx.returnedBodyLines,
      omittedLines: ctx.omittedLines,
      retainedHeadLines: ctx.retainedHeadLines,
      retainedTailLines: ctx.retainedTailLines
    })

  it('未超预算 → 原样；超预算 → 头尾保留且总字节不超预算', () => {
    const small = 'a:1\nb:2'
    expect(limitHeadTailLines(small, { maxBytes: GREP_CONTENT_MAX_BYTES, notice: headTailNotice }).truncated).toBe(false)

    const lines = Array.from({ length: 3000 }, (_, i) => `file.ts:${i + 1}:${'y'.repeat(20)}`)
    const r = limitHeadTailLines(lines.join('\n'), { maxBytes: GREP_CONTENT_MAX_BYTES, notice: headTailNotice })
    expect(r.truncated).toBe(true)
    expect(utf8ByteLength(r.text)).toBeLessThanOrEqual(GREP_CONTENT_MAX_BYTES)
    expect(r.text).toContain('已保留开头')
    expect(r.text).toContain('中间省略约')
  })

  it('头尾预算比例约 45/55（按**字节**断言；行数会受行长影响，不作依据）', () => {
    // 等长行：每行 20 字节，便于把「字节比例」与「行数比例」对齐
    const lines = Array.from({ length: 4000 }, (_, i) => `line-${String(i).padStart(4, '0')}${'z'.repeat(10)}`)
    const r = limitHeadTailLines(lines.join('\n'), { maxBytes: 4096, notice: headTailNotice })
    const m = /已保留开头 (\d+) 行与结尾 (\d+) 行/.exec(r.text)
    expect(m).not.toBeNull()
    const headLines = Number(m![1])
    const tailLines = Number(m![2])
    expect(headLines).toBeGreaterThan(0)
    expect(tailLines).toBeGreaterThan(0)

    // 结构：head \n\n [提示] \n\n tail —— 头尾要分别从提示的两侧取
    const noticeStart = r.text.indexOf('\n\n[已截断：')
    const headPart = r.text.slice(0, noticeStart)
    const noticeEnd = r.text.indexOf(']', noticeStart)
    const tailPart = r.text.slice(noticeEnd + 1).replace(/^\n\n/, '')
    expect(headPart.split('\n').length).toBe(headLines)
    expect(tailPart.split('\n').length).toBe(tailLines)
    const headBytes = utf8ByteLength(headPart)
    const tailBytes = utf8ByteLength(tailPart)
    const headShare = headBytes / (headBytes + tailBytes)
    // 头段应约占正文的 45%（整行取整会有小幅偏差，故给 ±10% 容差）
    expect(headShare).toBeGreaterThan(HEAD_TAIL_HEAD_RATIO - 0.1)
    expect(headShare).toBeLessThan(HEAD_TAIL_HEAD_RATIO + 0.1)
  })

  it('保留的是首尾两段（首行与末行都在结果里）', () => {
    const lines = Array.from({ length: 2000 }, (_, i) => `line-${i}`)
    const r = limitHeadTailLines(lines.join('\n'), { maxBytes: 2048, notice: headTailNotice })
    expect(r.text.startsWith('line-0')).toBe(true)
    expect(r.text.trimEnd().endsWith(`line-${lines.length - 1}`)).toBe(true)
  })
})

describe('续读提示 — 结构化且可执行', () => {
  it('prefix 提示含原始字节、上限、已返回行数与下一步参数', () => {
    const n = buildContinuationNotice({
      originalBytes: 99999,
      maxBytes: 24576,
      strategy: 'prefix_lines',
      returnedBodyLines: 120,
      nextOffset: 121
    })
    expect(n).toContain('原始 99999 字节')
    expect(n).toContain('24576')
    expect(n).toContain('前 120 行')
    expect(n).toContain('offset=121')
    expect(n.startsWith('[已截断：')).toBe(true)
    expect(n.endsWith(']')).toBe(true)
  })

  it('head_tail 提示含头尾行数与省略行数，并给出下一步建议', () => {
    const n = buildContinuationNotice({
      originalBytes: 50000,
      maxBytes: 16384,
      strategy: 'head_tail_lines',
      returnedBodyLines: 40,
      omittedLines: 300,
      retainedHeadLines: 18,
      retainedTailLines: 22
    })
    expect(n).toContain('开头 18 行')
    expect(n).toContain('结尾 22 行')
    expect(n).toContain('省略约 300 行')
    expect(n).toContain('缩小搜索范围')
  })

  it('可自定义 resumeCall（read_file 传入带路径与参数的完整调用）', () => {
    const n = buildContinuationNotice({
      originalBytes: 100000,
      maxBytes: 24576,
      strategy: 'prefix_lines',
      returnedBodyLines: 10,
      resumeCall: 'read_file(path="docs/a.md", offset=11, length=2000)'
    })
    expect(n).toContain('read_file(path="docs/a.md", offset=11, length=2000)')
  })

  it('超长行分支给出可操作建议（改用 grep 定位）', () => {
    const n = buildContinuationNotice({
      originalBytes: 100000,
      maxBytes: 24576,
      strategy: 'prefix_lines',
      returnedBodyLines: 0,
      oversizedLine: true
    })
    expect(n).toContain('超长行')
    expect(n).toContain('grep')
  })
})

describe('行切分与整行装入工具', () => {
  it('splitLines 去掉尾部空行', () => {
    expect(splitLines('a\nb\n\n\n')).toEqual(['a', 'b'])
    expect(splitLines('')).toEqual([])
    expect(splitLines('\n\n')).toEqual([])
  })

  it('takeWholeLinesFromStart/End 不切行且不超预算', () => {
    const lines = ['aa', 'bb', 'cc']
    expect(takeWholeLinesFromStart(lines, 2)).toEqual({ text: 'aa', count: 1 })
    expect(takeWholeLinesFromStart(lines, 5)).toEqual({ text: 'aa\nbb', count: 2 })
    expect(takeWholeLinesFromEnd(lines, 2)).toEqual({ text: 'cc', count: 1 })
    expect(takeWholeLinesFromEnd(lines, 5)).toEqual({ text: 'bb\ncc', count: 2 })
    expect(takeWholeLinesFromStart(lines, 0).count).toBe(0)
  })
})
