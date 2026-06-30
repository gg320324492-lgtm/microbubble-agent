import { chromium } from 'playwright'

const BASE_URL = 'http://localhost:3000'
const TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzgyODAyNzMzLCJ0eXBlIjoiYWNjZXNzIn0.TKpYyHXrEhsdNjR_I13Slu2U2LIiRXkjpoBRQVAgwBw'

async function run() {
  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await context.newPage()

  await page.addInitScript((token) => {
    localStorage.setItem('access_token', token)
  }, TOKEN)

  // Set ocean theme
  await page.goto(`${BASE_URL}/settings`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1000)
  const oceanSwatch = page.locator('.theme-swatch').filter({ hasText: '海蓝' }).first()
  if (await oceanSwatch.isVisible().catch(() => false)) {
    await oceanSwatch.click()
    await page.waitForTimeout(500)
  }

  // Go to members
  await page.goto(`${BASE_URL}/members`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(2000)

  // Use CDP to get all matching CSS rules for the first plain primary button
  const client = await page.context().newCDPSession(page)
  await client.send('DOM.enable')
  await client.send('CSS.enable')

  // Find the first 录入声纹 button
  const btnHandle = await page.locator('.el-button--primary.is-plain').first().elementHandle()
  const nodeId = await client.send('DOM.requestNode', {
    objectId: await btnHandle.evaluateHandle(el => el).then(h => h.toString())
  }).catch(() => null)

  // Use simpler approach: use window.getMatchedCSSRules (not standard, may not work)
  // Instead just dump all data-accent=ocean CSSRules
  const debug = await page.evaluate(() => {
    const btn = document.querySelector('.el-button--primary.is-plain')
    if (!btn) return { error: 'No button found' }
    const cs = getComputedStyle(btn)
    const matches = []
    // Walk through all stylesheets to find rules matching this element
    for (const sheet of document.styleSheets) {
      try {
        const rules = sheet.cssRules || sheet.rules
        if (!rules) continue
        for (const rule of rules) {
          if (rule.selectorText && rule.selectorText.includes('is-plain') &&
              rule.selectorText.includes('primary')) {
            // Try to match
            let matched = false
            try {
              matched = btn.matches(rule.selectorText)
            } catch (e) { matched = false }
            if (matched) {
              matches.push({
                sheet: sheet.href || 'inline',
                selector: rule.selectorText,
                textColor: rule.style.getPropertyValue('--el-button-text-color') || rule.style.color,
                cssText: rule.cssText.slice(0, 200)
              })
            }
          }
        }
      } catch (e) {
        // CORS-blocked stylesheet
      }
    }
    return {
      btnColor: cs.color,
      btnTextColor: cs.getPropertyValue('--el-button-text-color'),
      btnBg: cs.backgroundColor,
      dataAccent: document.documentElement.dataset.accent,
      matches
    }
  })

  console.log(JSON.stringify(debug, null, 2))
  await browser.close()
}

run().catch(e => { console.error('FATAL:', e); process.exit(1) })