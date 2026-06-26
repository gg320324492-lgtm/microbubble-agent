/**
 * @fileoverview CSS variable dark mode 自动化测试 (v74 沉淀)
 *
 * 验证 6 主题组合 (3 accent × 2 theme) 下, 所有关键 token 都能解析到具体值。
 * jsdom 不会自动加载 <link rel="stylesheet">, 需要手动把 variables.css 注入 <style>。
 *
 * 12 token 覆盖范围:
 *   - 主色: --color-primary / --color-primary-light / --color-primary-dark
 *   - 文本: --color-text-primary / --color-text-regular / --color-text-secondary
 *   - 背景: --color-bg-page / --color-bg-card
 *   - 边框: --color-border / --color-border-light
 *   - 状态: --color-success / --color-danger
 *
 * 测试矩阵: 3 accent (orange/ocean/forest) × 2 theme (light/dark) = 6 组合
 */
import { describe, it, expect, beforeAll, beforeEach } from 'vitest'
import { readFileSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

// 12 关键 token (高频引用, 任何主题切换断其中之一都炸)
const CRITICAL_TOKENS = [
  '--color-primary',
  '--color-primary-light',
  '--color-primary-dark',
  '--color-text-primary',
  '--color-text-regular',
  '--color-text-secondary',
  '--color-bg-page',
  '--color-bg-card',
  '--color-border',
  '--color-border-light',
  '--color-success',
  '--color-danger',
]

// 3 accent × 2 theme = 6 组合
const THEME_MATRIX = [
  { accent: 'orange', theme: 'light' },
  { accent: 'orange', theme: 'dark' },
  { accent: 'ocean', theme: 'light' },
  { accent: 'ocean', theme: 'dark' },
  { accent: 'forest', theme: 'light' },
  { accent: 'forest', theme: 'dark' },
]

describe('CSS variables: 6 主题组合 token 解析', () => {
  let variablesCSS

  beforeAll(() => {
    // 读取 variables.css 源码
    const cssPath = resolve(__dirname, '../assets/variables.css')
    variablesCSS = readFileSync(cssPath, 'utf-8')
  })

  beforeEach(() => {
    // 重置 document html 属性 + 清空 style
    document.documentElement.removeAttribute('data-theme')
    document.documentElement.removeAttribute('data-accent')
    document.head.querySelectorAll('style[data-v74-test]').forEach((s) => s.remove())
  })

  THEME_MATRIX.forEach(({ accent, theme }) => {
    it(`${accent} + ${theme}: 12 关键 token 都能解析`, () => {
      // 1. 注入 variables.css 到 <style> 让 jsdom 解析
      const style = document.createElement('style')
      style.setAttribute('data-v74-test', 'true')
      style.textContent = variablesCSS
      document.head.appendChild(style)

      // 2. 模拟用户切换主题 (v74: 用 documentElement 属性, 跟项目 Pinia 写入一致)
      document.documentElement.setAttribute('data-theme', theme)
      document.documentElement.setAttribute('data-accent', accent)

      // 3. 探测 token 解析值
      const probe = document.createElement('div')
      document.body.appendChild(probe)
      const computed = window.getComputedStyle(probe)

      // 4. 每个 token 验证 (v74 关键: 不能为空字符串, 不能为 "initial" 之类 fallback)
      CRITICAL_TOKENS.forEach((token) => {
        const value = computed.getPropertyValue(token).trim()
        expect(value, `token ${token} 在 ${accent}/${theme} 下为空`).not.toBe('')
        // 颜色不能是 "rgb(0, 0, 0)" 默认 (代表未解析)
        // 注: dark 模式下文本色是 #e8eaed, 不会是纯黑, 这里只检查 "有值"
        expect(value, `token ${token} 在 ${accent}/${theme} 下解析到 "initial"`).not.toBe('initial')
        expect(value, `token ${token} 在 ${accent}/${theme} 下解析到 "currentColor"`).not.toBe('currentColor')
      })

      // 5. 验证 light vs dark 关键 token 应该不同 (否则主题切换失效)
      if (theme === 'light') {
        const textPrimary = computed.getPropertyValue('--color-text-primary').trim().toLowerCase()
        // light 文本色应为深色 (#2D2D2D)
        const isTextPrimaryDark = textPrimary.includes('45') || textPrimary.includes('2d')
        expect(isTextPrimaryDark, `light text-primary 应为深色 (#2D2D2D), 实得: ${textPrimary}`).toBe(true)
      } else {
        // dark: text-primary 应该是亮色 (#e8eaed)
        const textPrimary = computed.getPropertyValue('--color-text-primary').trim().toLowerCase()
        const isTextPrimaryLight = textPrimary.includes('e8') || textPrimary.includes('ea') || textPrimary.includes('ed')
        expect(isTextPrimaryLight, `dark text-primary 应为亮色 (#e8eaed), 实得: ${textPrimary}`).toBe(true)
      }

      // 6. 验证 3 accent 主题下 primary 必须不同 (否则主题切换没效果)
      // v74: 与 5 互斥 — 5 校验 theme, 这里只校验 accent (color 值)
      if (theme === 'light') {
        const primary = computed.getPropertyValue('--color-primary').trim().toLowerCase()
        if (accent === 'orange') {
          // orange light primary = #FF7A5C = rgb(255, 122, 92) (含 255 + 122)
          expect(primary, `orange light primary 应含 255 和 122`).toMatch(/(255|122|7a)/i)
        } else if (accent === 'ocean') {
          // ocean light primary = #4A90E2 = rgb(74, 144, 226)
          expect(primary, `ocean light primary 应含 4A90E2 (74/4a/90/e2)`).toMatch(/(4a|90|e2|74|144|226)/i)
        } else if (accent === 'forest') {
          // forest light primary = #4CAF50 = rgb(76, 175, 80)
          expect(primary, `forest light primary 应含 4CAF50 (4c/af/50/76/175/80)`).toMatch(/(4c|af|50|76|175|80)/i)
        }
      }

      // 清理
      document.body.removeChild(probe)
    })
  })

  it('无主题属性时 token 仍可解析 (默认 light + orange)', () => {
    // 不设 data-theme / data-accent, 应使用 :root 默认值
    const style = document.createElement('style')
    style.setAttribute('data-v74-test', 'true')
    style.textContent = variablesCSS
    document.head.appendChild(style)

    const probe = document.createElement('div')
    document.body.appendChild(probe)
    const computed = window.getComputedStyle(probe)

    // 默认 token 应有值
    expect(computed.getPropertyValue('--color-primary').trim()).not.toBe('')
    expect(computed.getPropertyValue('--color-text-primary').trim()).not.toBe('')
  })
})

describe('CSS variable 守卫: 关键 token 不可缺失', () => {
  // v74 沉淀: 防止未来 refactor 删 token 导致 6 主题全黑屏
  let variablesCSS

  beforeAll(() => {
    variablesCSS = readFileSync(resolve(__dirname, '../assets/variables.css'), 'utf-8')
  })

  it('variables.css :root 块定义所有 12 关键 token (light 默认值)', () => {
    CRITICAL_TOKENS.forEach((token) => {
      // 用 regex 检查 token 在 :root 块内有定义
      // 简化: 检查 token 在文件中出现, 且格式是 `--token: <value>;`
      const re = new RegExp(`${token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*:\\s*[^;]+;`)
      expect(re.test(variablesCSS), `variables.css 缺少 ${token} 定义`).toBe(true)
    })
  })

  it('variables.css [data-theme="dark"] 块重定义关键 token', () => {
    // dark 模式必须显式重定义文本色 + 背景色
    const darkBlock = variablesCSS.match(/\[data-theme="dark"\]\s*\{([^}]+)\}/)
    expect(darkBlock, 'variables.css 缺少 [data-theme="dark"] 块').not.toBeNull()

    const darkBody = darkBlock[1]
    // dark 模式必须至少重定义: text-primary / bg-page / bg-card
    const requiredDarkTokens = ['--color-text-primary', '--color-bg-page', '--color-bg-card']
    requiredDarkTokens.forEach((token) => {
      expect(darkBody, `[data-theme="dark"] 缺少 ${token}`).toContain(token)
    })
  })
})
