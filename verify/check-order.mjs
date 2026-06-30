import { chromium } from 'playwright'
const BASE = 'http://localhost:3000'
const TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzgyODAyNzMzLCJ0eXBlIjoiYWNjZXNzIn0.TKpYyHXrEhsdNjR_I13Slu2U2LIiRXkjpoBRQVAgwBw'
const browser = await chromium.launch({ headless: true })
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const page = await ctx.newPage()
await page.addInitScript(t => localStorage.setItem('access_token', t), TOKEN)
await page.goto(`${BASE}/settings`, { waitUntil: 'networkidle' })
await page.waitForTimeout(500)
const sw = page.locator('.theme-swatch').filter({ hasText: '海蓝' }).first()
if (await sw.isVisible().catch(() => false)) { await sw.click(); await page.waitForTimeout(300) }
await page.goto(`${BASE}/members`, { waitUntil: 'networkidle' })
await page.waitForTimeout(1500)
const order = await page.evaluate(() => {
  const results = []
  for (const sheet of document.styleSheets) {
    try {
      const rules = sheet.cssRules || sheet.rules
      if (!rules) continue
      for (const rule of rules) {
        if (rule.selectorText === ':root' || rule.selectorText?.includes('data-accent="ocean"')) {
          const elPrimary = rule.style?.getPropertyValue('--el-color-primary') || ''
          const colorPrimary = rule.style?.getPropertyValue('--color-primary') || ''
          const text = rule.cssText.slice(0, 100)
          if (elPrimary || colorPrimary) {
            results.push({ sheet: sheet.href?.split('/').slice(-2).join('/') || 'inline', text, elPrimary, colorPrimary })
          }
        }
      }
    } catch (e) {}
  }
  return results
})
console.log(JSON.stringify(order, null, 2))
await browser.close()
