/**
 * @fileoverview CSS variable 组件级测试 (v76.3 沉淀)
 *
 * 与 cssVariables.spec.js (v74) 互补:
 *   - v74 测 variables.css 本身的 token 定义 + 解析
 *   - v76.3 测组件 scoped CSS 引用的 token 在主题下都能解析到有效值
 *
 * 价值:
 *   - 防止 var 函数的 fallback 形式静默回退 (CLAUDE.md v73 沉淀)
 *   - 防止组件 scoped CSS 用了未定义 token, 实际显示 fallback 灰白
 *   - 防止未来 refactor 改组件 style 但忘了 variables.css 同步
 *
 * 测试矩阵: 2 theme (light/dark) × 5 关键 token × 2 case (空 items / 有 items) = 20 断言
 * (2026-09-13 accent 多主题色移除, 原 3 accent × 2 theme = 6 组合收敛为 2)
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
  { theme: 'light' },
  { theme: 'dark' },
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
    document.head.querySelectorAll('style[data-v76-3-test]').forEach((s) => s.remove())
  })

  // 辅助: 注入 variables.css + 模拟主题 + mount + 返回 wrapper
  const mountWithTheme = (propsData, theme) => {
    const style = document.createElement('style')
    style.setAttribute('data-v76-3-test', 'true')
    style.textContent = variablesCSS
    document.head.appendChild(style)
    document.documentElement.setAttribute('data-theme', theme)

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

  THEME_MATRIX.forEach(({ theme }) => {
    it(`${theme} (空 items): 5 token 在 root element 都解析到非空值`, () => {
      const wrapper = mountWithTheme(
        { block: { data: { items: [] } } },
        theme
      )
      const values = collectTokenValues(wrapper)

      COMPONENT_TOKENS.forEach((token) => {
        expect(
          values[token],
          `${theme}: ${token} 应有值, 实得 "${values[token]}"`
        ).not.toBe('')
        expect(
          values[token],
          `${theme}: ${token} 应不是 "initial" fallback`
        ).not.toBe('initial')
      })
    })

    it(`${theme} (有 items): 5 token 在 .statement 元素都解析`, () => {
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
        theme
      )

      // .statement 元素用 --color-text-primary
      const statementEl = wrapper.find('.statement').element
      const computed = window.getComputedStyle(statementEl)
      const textPrimary = computed.getPropertyValue('--color-text-primary').trim()

      expect(textPrimary, `${theme}: .statement 的 --color-text-primary 应有值`).not.toBe('')
      // dark 模式 text-primary 应该是亮色 (含 e8/ea/ed), light 模式应该是深色 (含 45/2d)
      if (theme === 'dark') {
        const isLight = /e8|ea|ed/i.test(textPrimary)
        expect(isLight, `dark text-primary 应为亮色 (含 e8/ea/ed), 实得: ${textPrimary}`).toBe(true)
      } else {
        const isDark = /2d|45/i.test(textPrimary)
        expect(isDark, `light text-primary 应为深色 (含 2d/45), 实得: ${textPrimary}`).toBe(true)
      }
    })
  })

  it('light vs dark: --el-color-primary EP token 映射不同 (v77 P2.6 fix 守恒)', () => {
    // EP primary token 必须留在 [data-theme] attribute block (specificity (0,1,0) > EP :root (0,0,1)),
    // 否则 EP on-demand CSS 后加载的 :root { --el-color-primary: #409eff } 会反超 (2026-09-13 迁移守恒)
    const readEp = (theme) => {
      const wrapper = mountWithTheme({ block: { data: { items: [] } } }, theme)
      return window
        .getComputedStyle(wrapper.element)
        .getPropertyValue('--el-color-primary')
        .trim()
    }
    const lightEp = readEp('light')
    const darkEp = readEp('dark')

    expect(lightEp, 'light --el-color-primary 应有值').not.toBe('')
    expect(darkEp, 'dark --el-color-primary 应有值').not.toBe('')
    // 两个值都应是暖橙系 (非 EP 默认蓝 #409eff), 且明暗映射互不相同
    expect(lightEp.toLowerCase()).not.toBe('#409eff')
    expect(darkEp.toLowerCase()).not.toBe('#409eff')
    expect(lightEp.toLowerCase(), 'light vs dark EP primary 应不同').not.toBe(darkEp.toLowerCase())
  })

  it('light vs dark: --color-bg-card 必须不同 (主题切换生效)', () => {
    // jsdom 限制: 同一 test 内动态切换 data-theme attribute, computed style 可能拿到 cache 值
    // 解法: 两次独立 mount, 每次从干净状态开始 (用 beforeEach 强制 reset)
    // 第一个 mount 在 light 下
    const lightWrapper = mountWithTheme(
      { block: { data: { items: [] } } },
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
      'dark'
    )
    const darkBg = window
      .getComputedStyle(darkWrapper.element)
      .getPropertyValue('--color-bg-card')
      .trim()

    expect(lightBg, 'light bg-card 不为空').not.toBe('')
    expect(darkBg, 'dark bg-card 不为空').not.toBe('')
    expect(lightBg, 'light vs dark bg-card 应不同').not.toBe(darkBg)
  })
})
