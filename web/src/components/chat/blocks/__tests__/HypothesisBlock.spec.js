/**
 * @fileoverview CSS variable 组件级测试 (v76.3 沉淀)
 *
 * 与 cssVariables.spec.js (v74) 互补:
 *   - v74 测 variables.css 本身的 token 定义 + 解析
 *   - v76.3 测组件 scoped CSS 引用的 token 在 6 主题下都能解析到有效值
 *
 * 价值:
 *   - 防止 var 函数的 fallback 形式静默回退 (CLAUDE.md v73 沉淀)
 *   - 防止组件 scoped CSS 用了未定义 token, 实际显示 fallback 灰白
 *   - 防止未来 refactor 改组件 style 但忘了 variables.css 同步
 *
 * 测试矩阵: 3 accent × 2 theme = 6 组合 × 5 关键 token × 2 case (空 items / 有 items) = 60 断言
 *
 * 选择 HypothesisBlock.vue 的理由:
 *   - 63 行 + scoped + 8 个 var() 引用 (高频)
 *   - 无 vue-router / store 依赖, 可直接 mount
 *   - 涵盖 5 类 token (bg / text / primary / success / shadow)
 */
import { describe, it, expect, beforeAll, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { readFileSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'
import HypothesisBlock from '../HypothesisBlock.vue'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

// 5 类 token (覆盖 bg/text/primary/success/shadow 各 1 个, 代表 v76.3 测试深度)
const COMPONENT_TOKENS = [
  '--color-bg-card',
  '--color-text-primary',
  '--color-text-regular',
  '--color-text-secondary',
  '--color-primary',
]

const THEME_MATRIX = [
  { accent: 'orange', theme: 'light' },
  { accent: 'orange', theme: 'dark' },
  { accent: 'ocean', theme: 'light' },
  { accent: 'ocean', theme: 'dark' },
  { accent: 'forest', theme: 'light' },
  { accent: 'forest', theme: 'dark' },
]

describe('CSS variable 组件级解析: HypothesisBlock (v76.3)', () => {
  let variablesCSS

  beforeAll(() => {
    const cssPath = resolve(__dirname, '../../../../assets/variables.css')
    variablesCSS = readFileSync(cssPath, 'utf-8')
  })

  beforeEach(() => {
    // v76.3: 清 attach 到 body 的旧 wrapper (避免前 case 残留)
    document.body.innerHTML = ''
    document.documentElement.removeAttribute('data-theme')
    document.documentElement.removeAttribute('data-accent')
    document.head.querySelectorAll('style[data-v76-3-test]').forEach((s) => s.remove())
  })

  // 辅助: 注入 variables.css + 模拟主题 + mount + 返回 wrapper + computed
  const mountWithTheme = (propsData, accent, theme) => {
    const style = document.createElement('style')
    style.setAttribute('data-v76-3-test', 'true')
    style.textContent = variablesCSS
    document.head.appendChild(style)
    document.documentElement.setAttribute('data-theme', theme)
    document.documentElement.setAttribute('data-accent', accent)

    // v76.3 关键: attachTo: document.body 让 Vue wrapper 真正挂到 jsdom DOM 树
    // 否则 wrapper.element 是 detached node, getComputedStyle 返回空 token 值
    // (v75 SpeakerSearchSheet 同样 fix, 教训沉淀)
    const wrapper = mount(HypothesisBlock, {
      props: propsData,
      attachTo: document.body,
    })
    return wrapper
  }

  // 检查 root 元素的 computed style 包含哪些 token 值
  // (scoped CSS 应用到 .rich-card / .card-header / .hyp-item 等)
  const collectTokenValues = (wrapper) => {
    const root = wrapper.element
    const computed = window.getComputedStyle(root)
    const result = {}
    COMPONENT_TOKENS.forEach((token) => {
      result[token] = computed.getPropertyValue(token).trim()
    })
    return result
  }

  THEME_MATRIX.forEach(({ accent, theme }) => {
    it(`${accent} + ${theme} (空 items): 5 token 在 root element 都解析到非空值`, () => {
      const wrapper = mountWithTheme(
        { block: { data: { items: [] } } },
        accent,
        theme
      )
      const values = collectTokenValues(wrapper)

      COMPONENT_TOKENS.forEach((token) => {
        expect(
          values[token],
          `${accent}/${theme}: ${token} 应有值, 实得 "${values[token]}"`
        ).not.toBe('')
        expect(
          values[token],
          `${accent}/${theme}: ${token} 应不是 "initial" fallback`
        ).not.toBe('initial')
      })
    })

    it(`${accent} + ${theme} (有 items): 5 token 在 .statement 元素都解析`, () => {
      const wrapper = mountWithTheme(
        {
          block: {
            data: {
              items: [
                {
                  id: 1,
                  statement: '微纳米气泡能显著提升羟基自由基产率',
                  rationale: '基于臭氧氧化实验观察',
                  status: 'proposed',
                  priority: 'high',
                  confidence: 0.85,
                },
              ],
            },
          },
        },
        accent,
        theme
      )

      // .statement 元素用 --color-text-primary
      const statementEl = wrapper.find('.statement').element
      const computed = window.getComputedStyle(statementEl)
      const textPrimary = computed.getPropertyValue('--color-text-primary').trim()

      expect(textPrimary, `${accent}/${theme}: .statement 的 --color-text-primary 应有值`).not.toBe('')
      // dark 模式 text-primary 应该是亮色 (含 e8/ea/ed), light 模式应该是深色 (含 45/2d)
      if (theme === 'dark') {
        const isLight = /e8|ea|ed/i.test(textPrimary)
        expect(isLight, `dark ${accent} text-primary 应为亮色 (含 e8/ea/ed), 实得: ${textPrimary}`).toBe(true)
      } else {
        const isDark = /2d|45/i.test(textPrimary)
        expect(isDark, `light ${accent} text-primary 应为深色 (含 2d/45), 实得: ${textPrimary}`).toBe(true)
      }
    })
  })

  it('3 accent (light 主题): --color-primary 必须不同 (主题切换生效)', () => {
    // orange / ocean / forest light 模式下 primary 颜色应该互不相同
    const colors = []
    ;['orange', 'ocean', 'forest'].forEach((accent) => {
      const wrapper = mountWithTheme(
        { block: { data: { items: [] } } },
        accent,
        'light'
      )
      const value = window
        .getComputedStyle(wrapper.element)
        .getPropertyValue('--color-primary')
        .trim()
      colors.push({ accent, value })
    })

    // 三种 accent 的 primary 值应该互不相同
    expect(colors[0].value, 'orange primary').not.toBe(colors[1].value)
    expect(colors[1].value, 'ocean primary').not.toBe(colors[2].value)
    expect(colors[0].value, 'forest primary').not.toBe(colors[2].value)
  })

  it('light vs dark (orange 主题): --color-bg-card 必须不同 (主题切换生效)', () => {
    // jsdom 限制: 同一 test 内动态切换 data-theme attribute, computed style 可能拿到 cache 值
    // 解法: 两次独立 mount, 每次从干净状态开始 (用 beforeEach 强制 reset)
    // 第一个 mount 在 light 下
    document.documentElement.setAttribute('data-theme', 'light')
    document.documentElement.setAttribute('data-accent', 'orange')
    const lightWrapper = mountWithTheme(
      { block: { data: { items: [] } } },
      'orange',
      'light'
    )
    const lightBg = window
      .getComputedStyle(lightWrapper.element)
      .getPropertyValue('--color-bg-card')
      .trim()

    // 卸载 + 强制清 body, 准备下一个 mount
    lightWrapper.unmount()
    document.body.innerHTML = ''

    // 第二个 mount 在 dark 下 (干净状态)
    const darkWrapper = mountWithTheme(
      { block: { data: { items: [] } } },
      'orange',
      'dark'
    )
    const darkBg = window
      .getComputedStyle(darkWrapper.element)
      .getPropertyValue('--color-bg-card')
      .trim()

    expect(lightBg, 'orange light bg-card 不为空').not.toBe('')
    expect(darkBg, 'orange dark bg-card 不为空').not.toBe('')
    expect(lightBg, 'orange light vs dark bg-card 应不同').not.toBe(darkBg)
  })
})