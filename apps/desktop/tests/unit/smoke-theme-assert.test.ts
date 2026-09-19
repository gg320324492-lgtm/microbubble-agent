// V1 smoke 主题断言 — CSS 级联判定（通过/失败两态）
//
// 核心：断言的是「级联后真正生效的那条声明」，不是"文本里出现过品牌色"。
// 失败态用例直接复刻 M7 的真实缺陷（:root 是伪类 0,1,0，与 [data-theme] 同级 → 后加载者胜）。
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  BRAND_PRIMARY,
  assertCssVariable,
  collectDeclarations,
  compareSpecificity,
  specificity,
  winningDeclaration
} from '../../scripts/lib/css-assert.mjs'

/** EP 自身 :root 的默认主色（模拟 element-plus/dist/index.css） */
const EP_DEFAULT = ':root{--el-color-primary:#409eff;--el-color-primary-light-9:#ecf5ff}'

describe('CSS 特异性计算', () => {
  it(':root 是伪类 → (0,1,0)，不是元素级', () => {
    expect(specificity(':root')).toEqual([0, 1, 0])
  })

  it('[data-theme] 与 :root 同级；加 :root 前缀后升到 (0,2,0)', () => {
    expect(specificity("[data-theme='paper']")).toEqual([0, 1, 0])
    expect(specificity(":root[data-theme='paper']")).toEqual([0, 2, 0])
    expect(compareSpecificity(specificity(":root[data-theme='paper']"), specificity(':root'))).toBe(1)
    expect(compareSpecificity(specificity("[data-theme='paper']"), specificity(':root'))).toBe(0)
  })
})

describe('主题令牌断言 — 通过态', () => {
  it(':root[data-theme=paper] 压过 EP :root（特异性更高，与加载顺序无关）', () => {
    // 覆盖文件先加载、EP 后加载——靠特异性取胜
    const res = assertCssVariable([`:root[data-theme='paper']{--el-color-primary:${BRAND_PRIMARY}}`, EP_DEFAULT], '--el-color-primary', BRAND_PRIMARY)
    expect(res.ok, res.reason ?? '').toBe(true)
    expect(res.winner?.selector).toBe(":root[data-theme='paper']")
  })

  it('真实源码 theme-paper.css + 模拟 EP 默认蓝 → 断言通过', () => {
    const css = readFileSync(resolve(__dirname, '../../src/renderer/src/assets/theme-paper.css'), 'utf8')
    const res = assertCssVariable([css, EP_DEFAULT], '--el-color-primary', BRAND_PRIMARY)
    expect(res.ok, res.reason ?? '').toBe(true)
    expect(res.winner?.value.toLowerCase()).toBe(BRAND_PRIMARY)
  })
})

describe('主题令牌断言 — 失败态（复刻 M7 真实缺陷）', () => {
  it('裸 [data-theme=paper] 与 EP :root 同级且 EP 后加载 → 被压掉，断言失败', () => {
    const res = assertCssVariable([`[data-theme='paper']{--el-color-primary:${BRAND_PRIMARY}}`, EP_DEFAULT], '--el-color-primary', BRAND_PRIMARY)
    expect(res.ok).toBe(false)
    expect(res.reason).toContain('#409eff')
    expect(res.winner?.selector).toBe(':root')
  })

  it('完全缺失该声明 → 失败并给出可读原因', () => {
    const res = assertCssVariable(['body{color:#333}'], '--el-color-primary', BRAND_PRIMARY)
    expect(res.ok).toBe(false)
    expect(res.winner).toBeNull()
    expect(res.reason).toContain('未找到')
  })

  it('值写错（仍是 EP 默认蓝）→ 失败', () => {
    const res = assertCssVariable([`:root[data-theme='paper']{--el-color-primary:#409eff}`], '--el-color-primary', BRAND_PRIMARY)
    expect(res.ok).toBe(false)
    expect(res.reason).toContain('#409eff')
  })
})

describe('声明收集与取胜规则', () => {
  it('注释必须剥离：注释里提到的声明不得被当成真声明（真实产物踩到过）', () => {
    // 共享令牌包注释里就写着「EP 自己的 :root{--el-color-primary:#409eff}」这类说明文字
    const css = `/* 说明：EP 自己的 :root { --el-color-primary: #409eff } */\n:root[data-theme='paper']{--el-color-primary:${BRAND_PRIMARY}}`
    const decls = collectDeclarations(css, '--el-color-primary')
    expect(decls.length).toBe(1)
    expect(decls[0].selector).toBe(":root[data-theme='paper']")
    // 注释文本也不得污染特异性统计
    expect(specificity(decls[0].selector)).toEqual([0, 2, 0])
    expect(assertCssVariable([css], '--el-color-primary', BRAND_PRIMARY).ok).toBe(true)
  })

  it('多条声明按文档序收集；同级取靠后者', () => {
    const css = `a{--x:1}\n:root{--x:2}\n:root{--x:3}`
    const decls = collectDeclarations(css, '--x')
    expect(decls.map((d) => d.value)).toEqual(['1', '2', '3'])
    expect(winningDeclaration(decls)?.value).toBe('3')
  })

  it('跨多份 CSS 时文档序连续（模拟多个 <link>）', () => {
    const decls = [...collectDeclarations('a{--y:first}', '--y', 0), ...collectDeclarations('a{--y:second}', '--y', 1)]
    expect(winningDeclaration(decls)?.value).toBe('second')
  })
})
