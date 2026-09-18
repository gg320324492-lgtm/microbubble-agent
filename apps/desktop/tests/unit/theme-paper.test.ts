// M7 UI 换新 — 宣纸令牌层与 Element Plus 覆盖的静态契约（全部离线，读源码文本断言）
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const APP = resolve(__dirname, '../..')
const RENDERER = join(APP, 'src/renderer/src')
const read = (p: string) => readFileSync(p, 'utf8')

const themeCss = read(join(RENDERER, 'assets/theme-paper.css'))
const appCss = read(join(RENDERER, 'assets/app.css'))
const mainTs = read(join(RENDERER, 'main.ts'))

/** 取出某个块内某令牌的值 */
function tokenIn(css: string, name: string): string | null {
  const m = new RegExp(`--${name}\\s*:\\s*([^;]+);`).exec(css)
  return m ? m[1].trim() : null
}

describe('宣纸令牌 — 关键取值（paper 设计稿为唯一源头）', () => {
  it('主色系为靛墨蓝 #3e5c76 及其浅/深阶、弱底', () => {
    expect(tokenIn(themeCss, 'color-primary')).toBe('#3e5c76')
    expect(tokenIn(themeCss, 'color-primary-bg')).toBe('#e7edf3')
    expect(tokenIn(themeCss, 'color-primary-rgb')).toBe('62, 92, 118')
    // 珊瑚橙旧值不得再出现在令牌定义里
    expect(themeCss).not.toMatch(/--color-primary:\s*#FF7A5C/i)
  })

  it('背景三级为米色纸感（bg / panel / card）', () => {
    expect(tokenIn(themeCss, 'color-bg-page')).toBe('#f3eddf') // 纸底
    expect(tokenIn(themeCss, 'color-bg-warm')).toBe('#f9f5ec') // 面板
    expect(tokenIn(themeCss, 'color-bg-card')).toBe('#fffdf7') // 卡片
  })

  it('边框两级 / 文本两级 / 圆角基准 10px / 纸感阴影', () => {
    expect(tokenIn(themeCss, 'color-border')).toBe('#e4d9c3')
    expect(tokenIn(themeCss, 'color-border-dark')).toBe('#d8cbb0')
    expect(tokenIn(themeCss, 'color-text-primary')).toBe('#33302a')
    expect(tokenIn(themeCss, 'color-text-secondary')).toBe('#8d8574')
    expect(tokenIn(themeCss, 'radius-md')).toBe('10px')
    expect(tokenIn(themeCss, 'shadow-sm')).toBe('0 1px 4px rgba(90, 70, 30, 0.1)')
  })

  it('语义色 ok/warn/danger 均为宣纸调（非 EP 默认色）', () => {
    expect(tokenIn(themeCss, 'color-success')).toBe('#4a7c59')
    expect(tokenIn(themeCss, 'color-warning')).toBe('#9a7b4f')
    expect(tokenIn(themeCss, 'color-danger')).toBe('#a4504a')
  })

  it('衬线标题字体栈（Georgia + 宋体回退），并在 app.css 作用于 h1/h2/h3', () => {
    const stack = tokenIn(themeCss, 'wb-head-font')
    expect(stack).toContain('Georgia')
    expect(stack).toMatch(/Songti SC|STSong|SimSun/)
    expect(stack).toContain('serif')
    // 正文保持无衬线
    expect(appCss).toMatch(/font-family:\s*var\(--wb-head-font\)/)
    expect(appCss).toMatch(/h1,\s*\n\s*h2,\s*\n\s*h3,/)
  })

  it('main.ts 在 <html> 上写 data-theme=paper，且令牌层在共享令牌之后加载', () => {
    expect(mainTs).toContain("document.documentElement.dataset.theme = 'paper'")
    const iShared = mainTs.indexOf('@mb/design-tokens/variables.css')
    const iPaper = mainTs.indexOf('./assets/theme-paper.css')
    expect(iShared).toBeGreaterThanOrEqual(0)
    expect(iPaper).toBeGreaterThan(iShared)
  })
})

describe('Element Plus 覆盖 — 独立文件 + 变量映射齐备', () => {
  it('EP 映射集中在 [data-theme=paper] 块（specificity 高于 EP 自身 :root）', () => {
    expect(themeCss).toMatch(/\[data-theme='paper'\]\s*\{/)
    const block = themeCss.slice(themeCss.indexOf("[data-theme='paper']"))
    expect(block).toContain('--el-color-primary: #3e5c76')
  })

  it('覆盖工单要求的变量族：主色系/圆角/字号/文本/背景/填充', () => {
    for (const token of [
      '--el-color-primary',
      '--el-color-primary-light-3',
      '--el-color-primary-light-9',
      '--el-color-primary-dark-2',
      '--el-border-radius-base',
      '--el-border-radius-small',
      '--el-font-size-base',
      '--el-text-color-primary',
      '--el-text-color-regular',
      '--el-bg-color',
      '--el-fill-color',
      '--el-fill-color-light'
    ]) {
      expect(themeCss, `缺少 ${token}`).toContain(token)
    }
  })

  it('组件级微调覆盖 button/input/dialog/messagebox/table/switch/progress/tag', () => {
    for (const sel of [
      '.el-button--primary',
      '.el-input__wrapper',
      '.el-dialog',
      '.el-message-box',
      '.el-table',
      '.el-switch',
      '.el-progress-bar__inner',
      '.el-tag'
    ]) {
      expect(themeCss, `缺少组件微调 ${sel}`).toContain(sel)
    }
  })

  it('EP 覆盖不散落：视图/组件文件内不得出现 --el-color-primary 赋值', () => {
    const offenders: string[] = []
    const walk = (dir: string) => {
      for (const e of readdirSync(dir)) {
        const p = join(dir, e)
        if (statSync(p).isDirectory()) {
          walk(p)
          continue
        }
        if (!/\.(vue|css)$/.test(e)) continue
        const rel = p.replace(/\\/g, '/')
        if (rel.endsWith('assets/theme-paper.css')) continue
        if (/--el-color-primary\s*:/.test(read(p))) offenders.push(rel)
      }
    }
    walk(join(RENDERER, 'views'))
    walk(join(RENDERER, 'components'))
    expect(offenders).toEqual([])
  })
})

describe('珊瑚橙残留 — 全仓源码检索清零', () => {
  it('src/ 下不得出现珊瑚橙旧主色值（含 rgba 三元组）', () => {
    const coral = [
      '#ff7a5c',
      '#ff9d85',
      '#e85a3a',
      '#fff0ed',
      '#ffb347',
      '#fff8ed',
      '#c24730',
      '#a55e32',
      '#ffe4dc',
      '#fff8f5',
      '#fdf6ec',
      '255, 122, 92',
      '255,122,92',
      '255, 157, 133',
      '255, 179, 71'
    ]
    const hits: string[] = []
    const walk = (dir: string) => {
      for (const e of readdirSync(dir)) {
        const p = join(dir, e)
        if (statSync(p).isDirectory()) {
          walk(p)
          continue
        }
        if (!/\.(vue|ts|css)$/.test(e)) continue
        const text = read(p).toLowerCase()
        for (const c of coral) {
          if (text.includes(c)) hits.push(`${p.replace(/\\/g, '/')} ← ${c}`)
        }
      }
    }
    walk(join(APP, 'src'))
    expect(hits).toEqual([])
  })

  it('滚动条与状态栏 LED 均改走令牌（不再硬编码暖色/EP 色）', () => {
    expect(appCss).toContain('rgba(var(--color-primary-rgb), 0.26)')
    const statusBar = read(join(RENDERER, 'layouts/StatusBar.vue'))
    expect(statusBar).toContain('background: var(--color-success)')
    expect(statusBar).toContain('background: var(--color-danger)')
    expect(statusBar).not.toContain('#67c23a')
    expect(statusBar).not.toContain('#f56c6c')
  })
})
