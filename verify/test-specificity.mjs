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
  const root = document.documentElement
  const cs = getComputedStyle(root)
  return {
    dataAccent: root.dataset.accent,
    elColorPrimary: cs.getPropertyValue('--el-color-primary'),
    colorPrimary: cs.getPropertyValue('--color-primary'),
    elColorWhite: cs.getPropertyValue('--el-color-white'),
    // Calculate specificity for the rules setting --el-color-primary
    matchedRules: []
  }
})

// Check what rules set --el-color-primary on :root vs [data-accent=ocean]
const client = await page.context().newCDPSession(page)
await client.send('DOM.enable')
await client.send('CSS.enable')
const { root } = await client.send('DOM.getDocument', { depth: -1 })
const { nodeId } = await client.send('DOM.querySelector', { nodeId: root.nodeId, selector: 'html' })
const matched = await client.send('CSS.getMatchedStylesForNode', { nodeId })
const rulesForElPrimary = []
for (const m of matched.matchedCSSRules || []) {
  const rule = m.rule
  const props = rule.style.cssProperties || []
  const elPrimary = props.find(p => p.name === '--el-color-primary')
  if (elPrimary) {
    const sel = rule.selectorList?.text
    rulesForElPrimary.push({ selector: sel, value: elPrimary.value, origin: rule.origin })
  }
}
console.log('--el-color-primary on <html>:', result.elColorPrimary)
console.log('--color-primary on <html>:', result.colorPrimary)
console.log('--el-color-white on <html>:', result.elColorWhite)
console.log('Rules setting --el-color-primary on <html>:')
console.log(JSON.stringify(rulesForElPrimary, null, 2))
await browser.close()
