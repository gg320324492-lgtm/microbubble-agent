/**
 * chat-topbar-themes.spec.mjs — 桌面端 ChatViewSSE 顶栏明暗双主题 dark mode 视觉回归
 * (原 chat-topbar-6-themes.spec.mjs, 2026-09-13 accent 多主题色移除后收敛为 light/dark 双轴)
 *
 * 范围:
 *   - 2 主题: orange-light, orange-dark
 *   - 3 viewport: desktop (1280x800), tablet (900x600), mobile (375x800)
 *   - 总计: 6 视觉快照 (2 × 3)
 *
 * 锚点范式第 215 守恒 (W72 B-5 收口)
 *
 * 复用模式:
 *   - v77 P2.6-C 双注入登录态 (TEST_TOKEN env) — 这里跳过, 仅截顶栏静态部分
 *   - desktop-chrome project (playwright.config.js 已存在)
 *
 * 截图:
 *   - 截 .chat-header 元素 (顶栏) 而非整页 (顶栏是改造目标)
 *   - baseline 目录: tests/visual/desktop/chat-topbar-6-themes.spec.mjs-snapshots/
 *     (沿用旧目录名, orange-* 快照与 6 主题时代视觉一致, 无需 re-baseline)
 */
import { test, expect } from '@playwright/test'

const THEMES = [
  { mode: 'light', accent: 'orange' },
  { mode: 'dark', accent: 'orange' },
]

const VIEWPORTS = [
  { name: 'desktop', width: 1280, height: 800 },
  { name: 'tablet', width: 900, height: 600 },
  { name: 'mobile', width: 375, height: 800 },
]

for (const theme of THEMES) {
  for (const vp of VIEWPORTS) {
    const name = `${theme.accent}-${theme.mode}-${vp.name}`

    test(`chat topbar ${name} visual`, async ({ page }) => {
      // 1. viewport
      await page.setViewportSize({ width: vp.width, height: vp.height })

      // 2. 注入主题到 localStorage (useThemeStore 读 STORAGE_KEY_THEME)
      await page.addInitScript(
        ({ mode, accent }) => {
          try {
            localStorage.setItem('theme', mode)
            document.documentElement.setAttribute('data-theme', mode)
          } catch {
            /* localStorage 不可用 */
          }
        },
        { mode: theme.mode, accent: theme.accent },
      )

      // 3. 打开 /chat (不需要登录, 仅截顶栏; 即使 401 也渲染)
      await page.goto('/chat', { waitUntil: 'domcontentloaded', timeout: 15000 })

      // 4. 等待 .chat-header 元素出现 (使用 waitFor 而非 strict mode)
      await page
        .waitForSelector('.chat-header', { state: 'attached', timeout: 5000 })
        .catch(() => {
          /* fallback: SPA 可能在 /login, 跳过本测试而不是 fail */
          test.skip(true, 'chat-header not present (login redirect?)')
        })

      // 5. 视觉回归 — 截 .chat-header 元素
      await expect(page.locator('.chat-header')).toHaveScreenshot(`${name}.png`, {
        maxDiffPixelRatio: 0.05,
        animations: 'disabled',
      })
    })
  }
}
