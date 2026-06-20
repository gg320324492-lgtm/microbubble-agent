/**
 * 数学公式渲染 - KaTeX 动态加载
 *
 * v28 step 41 改进: 从 MathJax v3 切换到 KaTeX
 * - KaTeX 更小 (~270KB vs MathJax 1MB+)
 * - 自带 CSS (katex.min.css 内置字体 + 样式)
 * - auto-render 扩展自动扫描整页 $..$ / $$..$$
 * - 同步渲染（不等异步），不闪源码
 *
 * 用法：
 *   import '@/utils/mathFormat'  // 自动启动 KaTeX auto-render
 */

const KATEX_CDN_CSS = 'https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css'
const KATEX_CDN_JS = 'https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js'
const KATEX_AUTO_RENDER_JS = 'https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js'

let katexReady = null

function loadKaTeX() {
  if (katexReady) return katexReady

  katexReady = new Promise((resolve, reject) => {
    if (typeof window === 'undefined') return reject(new Error('SSR not supported'))

    if (window.katex && window.renderMathInElement) {
      resolve(window.katex)
      return
    }

    // 1. 注入 CSS
    if (!document.querySelector(`link[href*="katex.min.css"]`)) {
      const link = document.createElement('link')
      link.rel = 'stylesheet'
      link.href = KATEX_CDN_CSS
      link.crossOrigin = 'anonymous'
      document.head.appendChild(link)
    }

    // 2. 加载 katex.min.js
    const katexScript = document.createElement('script')
    katexScript.src = KATEX_CDN_JS
    katexScript.defer = true
    katexScript.crossOrigin = 'anonymous'
    katexScript.onload = () => {
      // 3. 加载 auto-render 扩展
      const arScript = document.createElement('script')
      arScript.src = KATEX_AUTO_RENDER_JS
      arScript.defer = true
      arScript.crossOrigin = 'anonymous'
      arScript.onload = () => {
        console.log('[mathFormat] KaTeX loaded')
        resolve(window.katex)
      }
      arScript.onerror = () => reject(new Error('Failed to load KaTeX auto-render'))
      document.head.appendChild(arScript)
    }
    katexScript.onerror = () => reject(new Error('Failed to load KaTeX core'))
    document.head.appendChild(katexScript)
  })

  return katexReady
}

/**
 * 检测文本是否包含数学公式
 */
export function hasMath(text) {
  if (!text) return false
  return /\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|\$[^\$\n]+\$|\\\([\s\S]+?\\\)/.test(text)
}

/**
 * 触发 KaTeX auto-render 扫描指定 DOM 区域
 *
 * KaTeX auto-render 默认扫描整页，我们指定 target 限定范围以提升性能
 *
 * v28 step 41: KaTeX renderMathInElement 默认识别 $..$ / $$..$$ / \(..\) / \[..\]
 */
export async function typesetMathJax(target) {
  try {
    const katex = await loadKaTeX()
    const elements = target
      ? (Array.isArray(target) ? target : [target])
      : [document.body]
    for (const el of elements) {
      if (window.renderMathInElement) {
        window.renderMathInElement(el, {
          delimiters: [
            { left: '$$', right: '$$', display: true },
            { left: '$', right: '$', display: false },
            { left: '\\[', right: '\\]', display: true },
            { left: '\\(', right: '\\)', display: false },
          ],
          throwOnError: false,  // 单个公式错误不阻塞其他
          // KaTeX 输出 .katex 元素，含完整样式
        })
      }
    }
    console.log('[mathFormat] KaTeX typeset complete, elements:', elements.length)
  } catch (e) {
    console.warn('[mathFormat] typeset failed (公式会保持源码):', e.message)
  }
}

/**
 * 同步兼容版本 - 不渲染（公式段保持源码）
 *
 * PaperBlockRenderer 调用此函数避免 SSR 报错，实际公式由 typesetMathJax 异步渲染
 */
export function renderMathInText(text) {
  return text  // 不处理，原样返回；KaTeX auto-render 后处理
}
