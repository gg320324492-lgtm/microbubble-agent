import { chromium } from 'playwright'
const browser = await chromium.launch({ headless: true })
const ctx = await browser.newContext()
const page = await ctx.newPage()
await page.goto('http://localhost:3000/settings', { waitUntil: 'networkidle' })
await page.waitForTimeout(1500)

const rules = await page.evaluate(() => {
  const results = []
  for (const sheet of document.styleSheets) {
    try {
      const cssRules = sheet.cssRules || sheet.rules
      if (!cssRules) continue
      for (const rule of cssRules) {
        if (rule.selectorText && (rule.selectorText.includes('data-accent="orange"') || rule.selectorText === ':root')) {
          const elPrimary = rule.style?.getPropertyValue('--el-color-primary')
          if (elPrimary) {
            results.push({
              sheet: sheet.href?.split('/').slice(-2).join('/') || 'inline',
              selector: rule.selectorText,
              value: elPrimary,
            })
          }
        }
      }
    } catch (e) {}
  }
  return results
})
console.log(JSON.stringify(rules, null, 2))
await browser.close()
