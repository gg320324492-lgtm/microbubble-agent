import { chromium } from 'playwright'
const browser = await chromium.launch({ headless: true })
const ctx = await browser.newContext()
const page = await ctx.newPage()
await page.goto('http://localhost:3000/settings', { waitUntil: 'networkidle' })
await page.waitForTimeout(1500)

// Switch to ocean
const sw = page.locator('.theme-swatch').filter({ hasText: '海蓝' }).first()
if (await sw.isVisible().catch(() => false)) { await sw.click(); await page.waitForTimeout(2000) }

await page.goto('http://localhost:3000/members', { waitUntil: 'networkidle' })
await page.waitForTimeout(2500)

const result = await page.evaluate(() => {
  const html = document.documentElement
  const body = document.body
  const btn = document.querySelector('.el-button--primary.is-plain')
  return {
    htmlElPrimary: getComputedStyle(html).getPropertyValue('--el-color-primary'),
    bodyElPrimary: getComputedStyle(body).getPropertyValue('--el-color-primary'),
    btn: btn ? {
      text: btn.textContent.trim().slice(0, 20),
      color: getComputedStyle(btn).color,
      bg: getComputedStyle(btn).backgroundColor,
      elPrimary: getComputedStyle(btn).getPropertyValue('--el-color-primary'),
      elTextColor: getComputedStyle(btn).getPropertyValue('--el-button-text-color'),
    } : null,
  }
})
console.log(JSON.stringify(result, null, 2))
await browser.close()
