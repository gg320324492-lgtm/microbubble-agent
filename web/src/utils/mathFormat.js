/**
 * 数学公式渲染工具 - 动态加载 MathJax v3 (CDN)
 *
 * v28 step 36 改进:
 * 之前 import mathjax-full 直接打包到 KnowledgeDetailView chunk (1.9MB, 下载慢)。
 * 改为运行时从 CDN 动态加载 MathJax v3 bundle，避免打包膨胀。
 *
 * 渲染策略:
 * 1. 同步阶段: 把文本里的 $..$ / $$..$$ 替换为 <span class="math math-inline">..</span>
 *    和 <div class="math math-display">..</div>（MathJax 默认 selector）
 * 2. 异步阶段: MathJax CDN 加载完后调 MathJax.typesetPromise() 渲染所有 .math 元素
 *
 * 支持:
 * - 行内: $...$ 或 \(...\)
 * - 块级: $$...$$ 或 \[...\]
 * - 完整 TeX/AMS/MathML/物理/化学
 */

const MATHJAX_CDN_URL = 'https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js'
// 国内备用 CDN: https://cdn.bootcdn.net/ajax/libs/mathjax/3.2.2/es5/tex-mml-chtml.js

let mathjaxReady = null
let mathjaxLoadFailed = false

function loadMathJax() {
  if (mathjaxReady) return mathjaxReady
  if (mathjaxLoadFailed) return Promise.reject(new Error('MathJax load previously failed'))

  mathjaxReady = new Promise((resolve, reject) => {
    if (typeof window === 'undefined') return reject(new Error('SSR not supported'))

    if (window.MathJax && window.MathJax.typesetPromise) {
      resolve(window.MathJax)
      return
    }

    // 配置 MathJax v3（自动 typeset 整页）
    window.MathJax = {
      tex: {
        inlineMath: [['$', '$'], ['\\(', '\\)']],
        displayMath: [['$$', '$$'], ['\\[', '\\]']],
        processEscapes: true,
        packages: { '[+]': ['ams', 'noerrors', 'noundefined', 'physics', 'color', 'mhchem'] },
      },
      svg: {
        fontCache: 'none',
      },
      startup: {
        typeset: true,  // 自动 typeset 整页（v28 step 37）
      },
      options: {
        renderActions: {
          addMenu: [0, '', ''],
        },
      },
    }

    const script = document.createElement('script')
    script.src = MATHJAX_CDN_URL
    script.async = true
    script.onload = () => {
      // MathJax v3 加载完后调 typesetPromise 渲染所有 .math 元素
      if (window.MathJax && window.MathJax.startup && window.MathJax.startup.promise) {
        window.MathJax.startup.promise.then(() => {
          console.log('[mathFormat] MathJax ready')
          resolve(window.MathJax)
        }).catch(reject)
      } else {
        // 老版本 fallback
        setTimeout(() => {
          if (window.MathJax && window.MathJax.typesetPromise) {
            resolve(window.MathJax)
          } else {
            reject(new Error('MathJax did not initialize'))
          }
        }, 500)
      }
    }
    script.onerror = () => {
      mathjaxLoadFailed = true
      reject(new Error('Failed to load MathJax from CDN: ' + MATHJAX_CDN_URL))
    }
    document.head.appendChild(script)
  })

  return mathjaxReady
}

/**
 * 检测文本是否包含数学公式
 */
export function hasMath(text) {
  if (!text) return false
  return /\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|\$[^\$\n]+\$|\\\([\s\S]+?\\\)/.test(text)
}

/**
 * 转义 HTML 特殊字符（但保留 .math 标签）
 */
function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

/**
 * 同步渲染: 把 $..$ 和 $$..$$ 替换为 MathJax 标准 <span>/<div> 标签
 *
 * 公式段会立即显示源码（因为 MathJax 还没加载完，渲染是异步的）
 * 用户体验: 公式短暂显示源码 → 50ms 后渲染为 SVG
 */
export function renderMathInText(text) {
  if (!text) return ''
  if (!hasMath(text)) return escapeHtml(text)

  // 1. 先 escape 全文（保护 XSS）
  let result = escapeHtml(text)

  // 2. 在 escaped 文本里找出公式段（escape 不会破坏 $ 符号）
  // 用占位符机制防止公式段被 escape 错乱
  const placeholders = []
  const regex = /(\$\$[\s\S]+?\$\$)|(\$[^\$\n]+\$)|(\\\[[\s\S]+?\\\])|(\\\([\s\S]+?\\\))/g

  result = result.replace(regex, (match) => {
    const idx = placeholders.length
    placeholders.push(match)
    // 用占位符数组索引恢复原文，再包成 MathJax 标准标签
    return ` MATH_PH_${idx} `
  })

  // 3. 占位符替换为 MathJax 标签（unescape 公式段，让 MathJax 处理）
  for (let i = 0; i < placeholders.length; i++) {
    const latex = placeholders[i]
    const isBlock = latex.startsWith('$$') || latex.startsWith('\\[')
    const tag = isBlock ? 'div' : 'span'
    const className = isBlock ? 'math math-display' : 'math math-inline'
    // 注意：这里不重新 escape 公式段，因为 MathJax 要识别 LaTeX 源码
    // 安全前提: 内容来自受信任的 paper content（DB 存储），不是用户输入
    result = result.replace(` MATH_PH_${i} `, `<${tag} class="${className}">${latex}</${tag}>`)
  }

  return result
}

/**
 * 手动触发 MathJax typeset（在 MathJax 加载完后调用）
 *
 * PaperBlockRenderer 在 onMounted / nextTick 时调此函数。
 * 这样公式段显示源码 → MathJax 加载完成 → typeset → SVG 替换源码。
 */
export async function typesetMathJax(target) {
  try {
    const mathjax = await loadMathJax()
    // typesetPromise 接受 DOM 元素或 CSS selector
    const elements = target
      ? (Array.isArray(target) ? target : [target])
      : Array.from(document.querySelectorAll('.math'))
    if (elements.length === 0) return
    await mathjax.typesetPromise(elements)
    console.log('[mathFormat] Typeset complete, elements:', elements.length)
  } catch (e) {
    console.warn('[mathFormat] typeset failed (公式会保持源码):', e.message)
  }
}

/**
 * 重置 MathJax 状态（用于路由切换或重渲染）
 */
export function resetMathJax() {
  mathjaxReady = null
  mathjaxLoadFailed = false
}
