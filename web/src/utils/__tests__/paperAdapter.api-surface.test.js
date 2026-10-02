/**
 * S3.8 paperAdapter 拆分 —— API 面冻结护栏
 *
 * 背景: paperAdapter.js(5633 行) 拆成 paper/ 六文件后, 三类破坏**测试抓不住**:
 *   ① barrel/具名导出漏转发  -> 运行时 undefined, 而 176 用例只覆盖被调用的符号
 *   ② _idCounter 分裂成两份 -> id 碰撞, 无任何断言检查 id 值
 *   ③ 9 条带 /g 的模块级正则被复制 -> 两份 lastIndex 各自漂移
 * 本文件是这三类里唯一能被断言兜住的部分。拆分过程中只允许一处放宽(见下)。
 */
import { describe, it, expect } from 'vitest'
import * as PA from '../paper'
import paperDefault from '../paper'

const SRC = '1. Introduction\nBody text.\n\n2. Methods\nMore.\n\n3. Results\nMore still.'
const toN = (id) => parseInt(String(id).slice(2), 36)   // 's_1a' -> 55

describe('S3.8 冻结 — 具名导出集合', () => {
  it('20 个具名导出（拆分前 23，QA 三后门收窄为段内私有）', () => {
    const names = Object.keys(PA).filter((k) => k !== 'default').sort()
    expect(names).toEqual([
      'KEYWORD_ZH_TO_EN',
      'autoLinkContent', 'buildAnchorTree', 'classifyImageKind', 'classifySectionType',
      'cleanContent', 'extractAuthorsAndJournal', 'extractFigureMarkers',
      'extractPageMarkers', 'extractTableMarkers', 'insertSectionBreaks',
      'matchFiguresWithCaptions', 'normalizeDoiText', 'normalizeGraphData',
      'normalizePaperData', 'parsePaperSections', 'removeFrontMatter',
      'splitReferences', 'translateKeywordToEnglish', 'translateKeywordsToEnglish',
    ])
    expect(names).toHaveLength(20)
    // QA 三后门已从公开面收回（外部消费者零使用），但 normalize 段仍可内部调用
    for (const gone of ['_tryExtractQA', '_cleanQAAnswer', '_buildQAPaperDetail']) {
      expect(names).not.toContain(gone)
    }
  })

  it('default 导出 12 键，且与具名导出同源（barrel 不能各造一份）', () => {
    const keys = Object.keys(paperDefault).sort()
    expect(keys).toHaveLength(12)
    for (const k of keys) expect(paperDefault[k]).toBe(PA[k])
  })
})

describe('S3.8 冻结 — 签名与返回结构', () => {
  it('关键函数 arity 不变', () => {
    expect(PA.parsePaperSections.length).toBe(1)
    expect(PA.matchFiguresWithCaptions.length).toBe(3)
    expect(PA.buildAnchorTree.length).toBe(1)
  })
  it('parsePaperSections 每 section 有 id/title/level', () => {
    const secs = PA.parsePaperSections(SRC)
    expect(secs.length).toBeGreaterThan(0)
    for (const s of secs) {
      expect(typeof s.id).toBe('string')
      expect(typeof s.level).toBe('number')
    }
  })
  it('normalizePaperData 顶层字段存在', () => {
    const r = PA.normalizePaperData({ title: 'T', content: SRC }, {})
    expect(Array.isArray(r.sections)).toBe(true)
    expect(r).toHaveProperty('figures')
  })
})

describe('S3.8 冻结 — _idCounter 单例（抓计数器分裂）', () => {
  it('同实例连续调用：id 唯一且严格单调', () => {
    const a = PA.parsePaperSections(SRC).map((s) => s.id)
    const b = PA.parsePaperSections(SRC).map((s) => s.id)
    const all = [...a, ...b]
    expect(new Set(all).size).toBe(all.length)
    expect(toN(b[0])).toBeGreaterThan(toN(a[a.length - 1]))
  })

  it('跨模块实例产出仍全局唯一 —— 坏拆分（各自持一份 _idCounter）转红', async () => {
    // 用 ?dup= 让 Vite 返回独立模块实例。共享 idCounter.js 时两实例共一份计数器 -> 绿；
    // 各自持有 -> id 从 s_1 重新开始 -> 碰撞 -> 红。
    const dup = await import('../paper/sections.js?dup=s38idcounter')
    const a = PA.parsePaperSections(SRC).map((s) => s.id)
    const b = dup.parsePaperSections(SRC).map((s) => s.id)
    const all = [...a, ...b]
    expect(new Set(all).size).toBe(all.length)
    expect(toN(b[0])).toBeGreaterThan(toN(a[a.length - 1]))
  })

  it('normalizePaperData 与 parsePaperSections 共用同一计数器', () => {
    const a = PA.parsePaperSections(SRC).map((s) => s.id)
    const b = PA.normalizePaperData({ title: 'T', content: SRC }, {}).sections.map((s) => s.id)
    expect(new Set([...a, ...b]).size).toBe(a.length + b.length)
    expect(toN(b[0])).toBeGreaterThan(toN(a[a.length - 1]))
  })
})
