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

// 2026-10-05 S3.12: 补 BASE_URL 常量。
//   本 spec 此前只 goto 相对路径 '/chat', 从没需要它; 新增 cookie 注入后需要
//   绝对 URL 才能取 hostname 设 cookie domain。
//   同目录另两个 spec (desktop_drive_comments / mobile_drive_comments) 已有此常量。
const BASE_URL = process.env.BASE_URL || 'http://localhost:3000'

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

    // ⚠️ 显式给用例 90s: 本用例要访问**两次** /chat(预热 + 截图),
    //   默认 30s 不够 —— 实测真 CI 上第二次 goto 报
    //   `page.goto: Test timeout of 30000ms exceeded`。
    //   这不是"放宽超时掩盖问题": 第一次 goto 已通过断言证明预热生效,
    //   超时纯粹是两次导航的**累加耗时**。
    test.setTimeout(90_000)

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

      // 2b. 2026-10-05 S3.12: 注入登录态 (双注入: cookie + localStorage)
      //
      //   实测: 本 spec 此前 **6 个用例全部 test.skip**, 一个基线都没产出过。
      //   根因不是 "SPA 偶尔落在 /login", 而是**必然**落在 /login:
      //     router/index.js:284 的守卫是
      //       if (to.meta.requiresAuth && !token) next('/login')
      //     /chat 的 meta 有 requiresAuth, 而本 spec **只注入了 cookie**
      //     (见上方 addInitScript 只写 theme, 从未写 access_token)。
      //     守卫读的是 localStorage.getItem('access_token') —— cookie 不算数。
      //     ⇒ 100% 重定向 /login, .chat-header 永远不存在 → 永远 skip。
      //
      //   同目录另两个 spec (desktop/mobile_drive_comments) 用的是**双注入**,
      //   本 spec 是唯一漏 localStorage 的那个 —— 这就是它从未产出基线的原因。
      const token = process.env.TEST_TOKEN || 'mock-token'
      await page.context().addCookies([{
        name: 'access_token',
        value: token,
        domain: new URL(BASE_URL).hostname,
        path: '/',
      }])
      await page.addInitScript((tk) => {
        localStorage.setItem('access_token', tk)
      }, token)

      // 3. 预热 + 打开 /chat
      //
      //   ⚠️ 2026-10-05 S3.15: 这里也必须**预热**, 与 visual-regression.spec.mjs 同因。
      //
      //   实测 (真 CI run 37249439461): 本spec 4 个用例全报
      //     `.chat-header 缺失但既不在 /login、viewport 也 >= 768
      //       —— 当前 URL=http://localhost:3000/chat`
      //   URL 正确、登录态正常, 但元素 15s 没出现 ⇒ 与 S3.14 那 6 处**同一个根因**:
      //     vite 首次请求异步 chunk 时触发依赖优化, 对已加载模块返回
      //     `504 (Outdated Optimize Dep)` → 动态 import 失败 → 组件不挂载。
      //   本机 vite 已预热过所以从不复现, CI 冷启动必然命中。
      //
      //   预热为什么用 `waitForFunction` 断言而不是固定 sleep:
      //     固定 sleep 本身是新的 flaky 源(慢机器不够/快机器白等);
      //     条件式等待快慢都正确。预热失败只 warn 不阻塞 ——
      //     第一次访问本来就可能撞 504, 那正是预热要解决的。
      // ⚠️ 这里**不传** timeout, 用 Playwright 默认值 —— 与 visual-regression.spec.mjs 一致。
      //
      // 实测踩坑 (真 CI run 37252532972): 我原先给两次 goto 都写了
      // `timeout: 30000`, 结果第二次 goto 报
      //     Error: page.goto: Test timeout of 30000ms exceeded.
      //   at chat-topbar-6-themes.spec.mjs:112
      // 注意是 **Test timeout**(整个用例 30s 上限), 不是 goto 自己的 30s ——
      // 预热(第一次 goto + waitForFunction + 500ms)已吃掉大部分预算,
      // 第二次 goto 必然撞上用例级上限。
      //
      // 为什么 visual-regression.spec.mjs 同样两次 goto 却没事:
      //   它**没写** timeout, 走 Playwright 默认(30s, 但用例级上限也是 30s,
      //   实测 9 个用例都过了)。差别在于本 spec 的预热更重
      //   (waitForFunction 最多等 20s)。
      //
      // 修法: 预热的 waitForFunction 上限从 20s 降到 10s, 并给整个用例
      // 一个明确的上限 —— 两次 goto 的总耗时必须显式算进去, 而不是靠默认值。
      await page.goto('/chat', { waitUntil: 'domcontentloaded' })
      await page
        .waitForFunction(
          () => (document.querySelector('#app')?.innerHTML.length ?? 0) > 500,
          null,
          { timeout: 10_000 },
        )
        .catch(() => console.warn('[visual] chat 预热未达标(不阻塞)'))
      await page.waitForTimeout(500)

      // 第二次访问才是截图那次 —— 此时 vite 转换缓存已就绪
      await page.goto('/chat', { waitUntil: 'networkidle' })

      // 4. 等待 .chat-header 元素出现。
      //
      //   ⚠️ 这里**不再** test.skip —— 跳过会让失败静默, 而这道门禁的价值
      //   全在"真出问题时红"。实测登录态修好后该元素稳定出现;
      //   万一不出现, 应该**报错**(说明 UI 真回归了), 而不是安静跳过。
      //   (2026-10-05: 原注释写 "fallback: SPA 可能在 /login, 跳过本测试而不是 fail"
      //    —— 正是这个 fallback 让本 spec 长期 0 基线且无人察觉。)
      const header = page.locator('.chat-header')
      const headerCount = await header.count()
      if (headerCount === 0) {
        // 2026-10-05 S3.12: 区分"为什么没有" —— 两种病因的处理完全不同, 混为一谈
        // 会让真正的 UI 回归被当成环境问题静默掉。
        //
        //   病因 A: 落在 /login  → 登录态失效, 属于**环境问题, 应重试**
        //   病因 B: 落在 /chat 但组件是 MobileChatView → viewport < 768 时
        //           router/index.js:51 的 resolveMobileComponent 会把 /chat
        //           解析成 chat/MobileChatView, 而 MobileChatView **没有**
        //           .chat-header 这个类。此时**无论怎么注入登录态都不会出现**。
        //
        //   实测: viewport mobile (375x800) 恒定命中病因 B —— 这个 spec 是
        //   *桌面端*顶栏回归, 它的 "mobile" 只是"窄一点的桌面视口",
        //   而非移动端组件栈。把这两个 viewport 算进来是历史遗留的口径错误。
        //
        //   ⚠️ 这里**用 test.skip(true, 原因) 而不是静默 catch**:
        //   skip 会出现在 Playwright 报告里 (可被 --forbid-only / CI 复核),
        //   而原来的 `.catch(() => test.skip(...))` 把"登录态坏了"和
        //   "这个 viewport 本就不适用"混成同一个静默出口。
        const url = page.url()
        test.skip(
          url.endsWith('/login'),
          `登录态失效: 被重定向到 ${url} (环境问题, 应重试而不是跳过)`,
        )
        test.skip(
          vp.width < 768,
          `viewport ${vp.width}px < 768 ⇒ router 解析成 MobileChatView, ` +
            `该组件无 .chat-header。此 viewport 不适用于**桌面端**顶栏回归 ` +
            `(口径错误, 非回归)。如需覆盖移动端顶栏, 应另建 spec 断言 ` +
            `MobileChatView 自己的顶栏类名。`,
        )
        // 其余情况 = 真的 UI 回归了, 必须报红
        throw new Error(
          `.chat-header 缺失但既不在 /login、viewport 也 >= 768 —— ` +
            `当前 URL=${url}。这是真实 UI 回归 (顶栏元素消失), 必须报红。`,
        )
      }
      await header.first().waitFor({ state: 'attached', timeout: 15000 })

      // 5. 视觉回归 — 截 .chat-header 元素
      //
      //   ⚠️ maxDiffPixelRatio 从 0.05 收紧到 0.002 (与门禁其余 spec 同口径)。
      //   0.05 比别人松 25 倍, 属"调阈值换绿" —— 顶栏改个颜色/间距都能过。
      //   收紧前已先治因 (字体锁 + 时钟冻结, 见 docker/visual-regression/),
      //   实测该元素在钉死环境下同环境连跑两次字节一致, 故收紧是安全的。
      await expect(page.locator('.chat-header')).toHaveScreenshot(`${name}.png`, {
        maxDiffPixelRatio: 0.002,
        animations: 'disabled',
      })
    })
  }
}
