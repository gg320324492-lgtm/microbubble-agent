import { chromium } from 'playwright'
const browser = await chromium.launch({ headless: true })
const ctx = await browser.newContext()
const page = await ctx.newPage()

await page.goto('http://localhost:3000/settings', { waitUntil: 'networkidle' })
await page.waitForTimeout(500)
const sw = page.locator('.theme-swatch').filter({ hasText: '海蓝' }).first()
if (await sw.isVisible().catch(() => false)) { await sw.click(); await page.waitForTimeout(300) }

await page.goto('http://localhost:3000/members', { waitUntil: 'networkidle' })
await page.waitForTimeout(1500)

const result = await page.evaluate(() => {
  const html = document.documentElement
  const body = document.body
  return {
    htmlAccent: html.dataset.accent,
    htmlTheme: html.dataset.theme,
    bodyAccent: body.dataset.accent,
    bodyTheme: body.dataset.theme,
    htmlElColorPrimary: getComputedStyle(html).getPropertyValue('--el-color-primary'),
    bodyElColorPrimary: getComputedStyle(body).getPropertyValue('--el-color-primary'),
  }
})
console.log(JSON.stringify(result, null, 2))
await browser.close()
