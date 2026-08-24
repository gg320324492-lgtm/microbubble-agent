// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const rendererRoot = resolve(__dirname, '../../src/renderer/src')
const readOrEmpty = (path: string): string => (existsSync(path) ? readFileSync(path, 'utf8') : '')
const tokens = readOrEmpty(resolve(rendererRoot, 'styles/research-design-tokens.css'))
const tokensWithoutComments = tokens.replace(/\/\*[\s\S]*?\*\//g, '')
const tokenRoot = tokensWithoutComments.match(/^\s*:root\s*\{([^}]*)\}/s)?.[1] ?? ''
const globalStyles = readOrEmpty(resolve(rendererRoot, 'styles/research-global.css'))
const motion = readOrEmpty(resolve(rendererRoot, 'styles/research-motion.css'))
const main = readOrEmpty(resolve(rendererRoot, 'main.ts'))
const app = readOrEmpty(resolve(rendererRoot, 'App.vue'))

const escapeRegExp = (value: string): string => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const expectDeclaration = (source: string, name: string, value: string): void => {
  expect(source).toMatch(new RegExp(`${escapeRegExp(name)}\\s*:\\s*${escapeRegExp(value)}\\s*;`))
}

const COLOR_TOKENS = [
  ['--research-primary-50', 'var(--research-teal-50)'],
  ['--research-primary-100', 'var(--research-teal-100)'],
  ['--research-primary-500', 'var(--research-teal-700)'],
  ['--research-primary-600', '#0c665f'],
  ['--research-ai-50', 'var(--research-coral-50)'],
  ['--research-ai-100', 'var(--research-coral-100)'],
  ['--research-ai-500', 'var(--research-coral-500)'],
  ['--research-ai-600', '#d95d46'],
  ['--research-success-50', 'var(--research-teal-50)'],
  ['--research-success-500', 'var(--research-teal-700)'],
  ['--research-warning-50', 'var(--research-amber-50)'],
  ['--research-warning-500', 'var(--research-amber-500)'],
  ['--research-danger-50', 'var(--research-red-50)'],
  ['--research-danger-500', 'var(--research-red-600)'],
  ['--research-bg-main', 'var(--research-mist-50)'],
  ['--research-bg-card', 'var(--research-paper-0)'],
  ['--research-bg-panel', 'var(--research-mist-100)'],
  ['--research-text-primary', 'var(--research-graphite-950)'],
  ['--research-text-secondary', '#66757b'],
  ['--research-text-muted', '#849197'],
  ['--research-border-subtle', '#dce5e1'],
  ['--research-border-strong', '#b9c9c5']
] as const

const TYPOGRAPHY_TOKENS = [
  ['--research-font-sans', 'var(--research-font-ui)'],
  ['--research-font-serif', 'var(--research-font-paper)'],
  ['--research-font-mono', 'var(--research-font-scientific)'],
  ['--research-text-xs', '11px'],
  ['--research-text-sm', '12px'],
  ['--research-text-body', '14px'],
  ['--research-text-card-title', '15px'],
  ['--research-text-section-title', '18px'],
  ['--research-text-page-title', '24px'],
  ['--research-line-height-body', '1.65']
] as const

const SPACING_TOKENS = [
  ['--research-space-1', '4px'],
  ['--research-space-2', '8px'],
  ['--research-space-3', '12px'],
  ['--research-space-4', '16px'],
  ['--research-space-5', '20px'],
  ['--research-space-6', '24px'],
  ['--research-space-7', '28px'],
  ['--research-space-8', '32px'],
  ['--research-space-10', '40px'],
  ['--research-space-12', '48px']
] as const

const RADIUS_TOKENS = [
  ['--research-radius-input', 'var(--research-radius-sm)'],
  ['--research-radius-button', 'var(--research-radius-sm)'],
  ['--research-radius-card', 'var(--research-radius-md)'],
  ['--research-radius-panel', 'var(--research-radius-lg)'],
  ['--research-radius-large', '24px'],
  ['--research-radius-pill', '999px']
] as const

const SHADOW_TOKENS = [
  ['--research-shadow-soft', 'var(--research-shadow-surface)'],
  ['--research-shadow-medium', '0 12px 30px rgb(23 33 41 / 10%)'],
  ['--research-shadow-floating', '0 20px 48px rgb(23 33 41 / 14%)'],
  ['--research-shadow-focus-primary', '0 0 0 3px rgb(14 118 110 / 25%)'],
  ['--research-shadow-focus-ai', '0 0 0 3px rgb(239 114 86 / 25%)'],
  ['--research-shadow-inset', 'inset 0 1px 0 rgb(255 255 255 / 72%)']
] as const

const LAYOUT_TOKENS = [
  ['--research-sidebar-width', '232px'],
  ['--research-sidebar-collapsed-width', '76px'],
  ['--research-header-height', '64px'],
  ['--research-page-gutter', '24px'],
  ['--research-grid-gap', '16px'],
  ['--research-z-header', '30']
] as const

const MOTION_TOKENS = [
  ['--research-duration-fast', '160ms'],
  ['--research-duration-normal', '240ms'],
  ['--research-duration-slow', '320ms'],
  ['--research-ease-standard', 'cubic-bezier(.2,.8,.2,1)'],
  ['--research-ease-emphasized', 'cubic-bezier(.16,1,.3,1)'],
  ['--research-ease-linear', 'linear']
] as const

describe('科研设计令牌：颜色矩阵', () => {
  it.each(COLOR_TOKENS)('%s 使用批准的语义色 %s', (name, value) => {
    expectDeclaration(tokenRoot, name, value)
  })
})

describe('科研设计令牌：排版矩阵', () => {
  it.each(TYPOGRAPHY_TOKENS)('%s 定义为 %s', (name, value) => {
    expectDeclaration(tokenRoot, name, value)
  })
})

describe('科研设计令牌：四像素空间矩阵', () => {
  it.each(SPACING_TOKENS)('%s 定义为 %s', (name, value) => {
    expectDeclaration(tokenRoot, name, value)
  })
})

describe('科研设计令牌：形状矩阵', () => {
  it.each(RADIUS_TOKENS)('%s 定义为 %s', (name, value) => {
    expectDeclaration(tokenRoot, name, value)
  })
})

describe('科研设计令牌：阴影层级矩阵', () => {
  it.each(SHADOW_TOKENS)('%s 定义为 %s', (name, value) => {
    expectDeclaration(tokenRoot, name, value)
  })
})

describe('科研设计令牌：桌面布局矩阵', () => {
  it.each(LAYOUT_TOKENS)('%s 定义为 %s，并提供宽屏密度规则', (name, value) => {
    expectDeclaration(tokenRoot, name, value)
    expect(tokens).toContain('@media (min-width: 1720px)')
  })
})

describe('科研设计令牌：动效节奏矩阵', () => {
  it.each(MOTION_TOKENS)('%s 定义为 %s', (name, value) => {
    expectDeclaration(tokenRoot, name, value)
  })
})

describe('科研全局工作面与减少动态效果', () => {
  it('从 renderer 入口按令牌、全局、动效顺序加载三份样式', () => {
    const imports = [
      "import './styles/research-design-tokens.css'",
      "import './styles/research-global.css'",
      "import './styles/research-motion.css'"
    ]
    imports.forEach((statement) => expect(main).toContain(statement))
    expect(imports.map((statement) => main.indexOf(statement))).toEqual(
      [...imports].map((statement) => main.indexOf(statement)).sort((a, b) => a - b)
    )
  })

  it('保留 main/plain 布局分流并以 route.fullPath 驱动页面过渡', () => {
    expect(app).toContain("layout === 'main'")
    expect(app).toContain('<Transition name="research-page" mode="out-in">')
    expect(app).toContain(':key="route.fullPath"')
    expect(app).not.toContain('color-scheme: dark')
  })

  it('统一 body、root 与应用根节点的浅色工作面和盒模型', () => {
    expect(globalStyles).toMatch(/\*\s*,\s*\*::before\s*,\s*\*::after\s*\{[^}]*box-sizing:\s*border-box/s)
    expect(globalStyles).toMatch(/html\s*,\s*body\s*,\s*#app\s*\{[^}]*min-height:\s*100%/s)
    expect(globalStyles).toMatch(/body\s*\{[^}]*background:\s*var\(--research-bg-main\)[^}]*font-family:\s*var\(--research-font-sans\)/s)
  })

  it('为键盘焦点提供高对比、非位移式的可见轮廓', () => {
    expect(globalStyles).toMatch(/:focus-visible\s*\{[^}]*outline:\s*2px solid var\(--research-primary-500\)[^}]*outline-offset:\s*2px/s)
  })

  it('为文字选择与滚动条提供一致的科学蓝语义反馈', () => {
    expect(globalStyles).toMatch(/::selection\s*\{[^}]*background:\s*var\(--research-primary-100\)/s)
    expect(globalStyles).toContain('scrollbar-color: var(--research-border-strong) transparent')
    expect(globalStyles).toMatch(/::-webkit-scrollbar-thumb\s*\{[^}]*background:\s*var\(--research-border-strong\)/s)
  })

  it('页面、交互卡片和 Agent 运行态具备动效且 reduced-motion 实质归零', () => {
    expect(motion).toContain('.research-page-enter-active')
    expect(motion).toContain('.research-card-interactive')
    expect(motion).toContain('.research-agent-running')
    expect(motion).toMatch(/\.research-agent-running::before\s*\{[^}]*display:\s*inline-block[^}]*width:\s*8px[^}]*height:\s*8px/s)
    expect(motion).toMatch(/\.research-agent-running::before\s*\{[^}]*margin-inline-end:\s*var\(--research-space-2\)[^}]*vertical-align:\s*middle/s)
    expect(motion).toContain('box-shadow: 0 0 0 0 var(--research-ai-glow-base)')
    expect(motion).toContain('box-shadow: 0 0 0 0 var(--research-ai-glow-soft)')
    expect(motion).toContain('box-shadow: 0 0 0 7px var(--research-ai-glow-transparent)')
    expect(motion).not.toContain('rgb(118 84 216')
    expect(motion).toContain('@media (prefers-reduced-motion: reduce)')
    expect(motion).toMatch(/prefers-reduced-motion:\s*reduce[\s\S]*animation-duration:\s*0\.01ms\s*!important/s)
    expect(motion).toMatch(/prefers-reduced-motion:\s*reduce[\s\S]*animation-delay:\s*0ms\s*!important/s)
    expect(motion).toMatch(/prefers-reduced-motion:\s*reduce[\s\S]*transition-duration:\s*0\.01ms\s*!important/s)
    expect(motion).toMatch(/prefers-reduced-motion:\s*reduce[\s\S]*transform:\s*none\s*!important/s)
  })
})
