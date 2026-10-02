/**
 * S3.8 paperAdapter 拆分 —— API 面冻结护栏
 *
 * 背景: paperAdapter.js(5633 行) 拆成 paper/ 六文件后, 三类破坏**测试抓不住**:
 *   ① barrel/具名导出漏转发  -> 运行时 undefined, 而 176 用例只覆盖被调用的符号
 *   ② _idCounter 分裂成两份 -> id 碰撞, 无任何断言检查 id 值
 *   ③ 带 /g 的模块级正则被复制 -> 两份 lastIndex 各自漂移
 * ①② 由运行时会话断言兜住; ③ 与"复制成两份"只能靠**结构唯一性**断言(见文件末段)。
 * ⚠️ 有一条曾经伪装成 ② 的护栏、实为恒绿, 已于 2026-10-02 复检删除 —— 原因见末段注释。
 */
import { describe, it, expect } from 'vitest'
import { readFileSync, readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join, dirname } from 'node:path'
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

  it('normalizePaperData 与 parsePaperSections 共用同一计数器', () => {
    const a = PA.parsePaperSections(SRC).map((s) => s.id)
    const b = PA.normalizePaperData({ title: 'T', content: SRC }, {}).sections.map((s) => s.id)
    expect(new Set([...a, ...b]).size).toBe(a.length + b.length)
    expect(toN(b[0])).toBeGreaterThan(toN(a[a.length - 1]))
  })
})

// ⚠️ 下面这组是**结构性**断言, 不是运行时断言。
//
// 2026-10-02 复检推翻了一条旧断言: 它用 `import('../paper/sections.js?dup=x')` 造"第二个
// 模块实例"来证明坏拆分会转红。复检官实测 (?dup= 副本产出 s_4,s_5,s_6, **接着共享计数器
// 继续发号**) —— Vite 的 ?dup= 查询串**不复制 ./constants 里那个模块实例**, 于是
// unique===total 与 first>last 两条都恒成立, **该用例在任何拆分形态下都是绿的,
// 包括计数器真分裂成两份的坏拆分**。一道恒绿的断言比没有断言更糟: 它挂着"坏拆分转红"的
// 注释, 让读的人以为有护栏。
//
// 真正的 FM2(把 _idCounter / 带 g 正则复制成两份) 无法用运行时手段可靠构造 —— 造出一个
// 真正独立的实例必然意味着 module registry 被重置, 那时好坏拆分都会红, 断言就退化成
// 恒红。故改为直接锁**声明唯一性**: 同一模块图内出现第二份声明就是复制, 出现即红。
describe('S3.8 冻结 — 结构唯一性（抓"复制成两份"）', () => {
  // 注意: 不能写 `new URL('../paper/', import.meta.url)` —— Vite 会把这个字面量形态
  // 当成 asset URL 做静态改写, 运行时拿到的不再是 URL, 直接抛
  // "The URL must be of scheme file"。故走 dirname(fileURLToPath(...))。
  const dir = join(dirname(fileURLToPath(import.meta.url)), '..', 'paper')
  const jsFiles = readdirSync(dir).filter((f) => f.endsWith('.js'))
  const read = (f) => readFileSync(join(dir, f), 'utf8')

  it('paper/ 目录非空（防止上面的过滤悄悄返回空数组而恒绿）', () => {
    expect(jsFiles.length).toBeGreaterThan(0)
  })

  it('_idCounter 只在 constants.js 声明一次', () => {
    const declaredIn = jsFiles.filter((f) => /^let _idCounter\s*=/m.test(read(f)))
    expect(declaredIn).toEqual(['constants.js'])
  })

  it('_genId 不在第二个文件里另有一份实现（防绕过计数器直接复制函数）', () => {
    const definedIn = jsFiles.filter((f) => /^function _genId\b/m.test(read(f)))
    expect(definedIn).toEqual(['constants.js'])
  })

  it('带 g 的模块级正则不跨文件重名（lastIndex 各漂一份 = FM2）', () => {
    // ⚠️ 结尾**没有分号**: 源文件这些字面量写成 `/.../g` 收尾（分号可选）。
    //   第一版按 `/flags;` 匹配, 对全部 7 个文件命中 0 条 —— 断言恒绿, 等于没写。
    //   这里 `;?` 可选, 并且下面那条精确计数的自检会挡住同类退化。
    const declRe = /^const\s+(\w+)\s*=\s*\/.+?\/[gimsuy]*\s*;?\s*$/
    const hasG = /\/[gimsuy]*g[gimsuy]*\s*;?\s*$/
    const seen = new Map()
    for (const f of jsFiles) {
      for (const line of read(f).split('\n')) {
        const m = declRe.exec(line)
        if (!m || !hasG.test(line)) continue
        if (!seen.has(m[1])) seen.set(m[1], [])
        seen.get(m[1]).push(f)
      }
    }
    // 自检: 若将来文件写法再变导致一条都匹配不上, 这里先红, 而不是静默恒绿
    expect(seen.size).toBeGreaterThanOrEqual(8)
    const dup = [...seen.entries()].filter(([, fs]) => fs.length > 1).map(([n, fs]) => `${n}@${fs.join('+')}`)
    expect(dup).toEqual([])
  })

  it('（自检）当前应恰好有 8 条带 g 正则在 constants.js + affRegex 独有', () => {
    const declRe = /^const\s+(\w+)\s*=\s*\/.+?\/[gimsuy]*\s*;?\s*$/
    const hasG = /\/[gimsuy]*g[gimsuy]*\s*;?\s*$/
    const byFile = {}
    for (const f of jsFiles) {
      byFile[f] = read(f).split('\n').filter((l) => declRe.test(l) && hasG.test(l)).length
    }
    // constants 8 条；figures 仅 affRegex 1 条；其余段 0 条（函数内正则不跨文件, 不算）
    expect(byFile).toEqual({
      'index.js': 0, 'qa.js': 0, 'sections.js': 0, 'content.js': 0, 'normalize.js': 0,
      'constants.js': 8, 'figures.js': 1,
    })
  })
})
