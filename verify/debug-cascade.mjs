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

  await page.goto(`${BASE_URL}/settings`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1000)
  const oceanSwatch = page.locator('.theme-swatch').filter({ hasText: '海蓝' }).first()
  if (await oceanSwatch.isVisible().catch(() => false)) {
    await oceanSwatch.click()
    await page.waitForTimeout(500)
  }

  await page.goto(`${BASE_URL}/members`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(2000)

  // Use CDP to get all matched rules via CSS.getMatchedStylesForNode
  const client = await page.context().newCDPSession(page)
  await client.send('DOM.enable')
  await client.send('CSS.enable')

  const btnHandle = await page.locator('.el-button--primary.is-plain').first().elementHandle()
  const { root } = await client.send('DOM.getDocument', { depth: -1 })

  // Find the node by querying
  const { nodeId } = await client.send('DOM.querySelector', {
    nodeId: root.nodeId,
    selector: '.el-button--primary.is-plain'
  })

  if (!nodeId) {
    console.log('No node found')
    await browser.close()
    return
  }

  const matched = await client.send('CSS.getMatchedStylesForNode', { nodeId })
  console.log('=== Matched rules (color-related only) ===')

  for (const m of matched.matchedCSSRules || []) {
    const rule = m.rule
    const sel = rule.selectorList?.text || rule.selectorList?.selectors?.map(s => s.text).join(', ')
    const props = rule.style.cssProperties || []
    const colorProps = props.filter(p => /color|background/i.test(p.name))
    if (colorProps.length > 0) {
      const specificity = m.matchingSelectors?.map(idx => {
        const sel = rule.selectorList.selectors[idx]
        return sel.text + ' (specificity: ' + (sel.specificity || '?') + ')'
      }).join(', ')
      console.log('\n[Rule] sheet:', rule.styleSheetId, 'origin:', rule.origin)
      console.log('  selector:', sel)
      console.log('  matched selectors:', specificity)
      for (const p of colorProps) {
        console.log('  ', p.name, ':', p.value, p.disabled ? '(disabled)' : '', p.implicit ? '(implicit)' : '')
      }
    }
  }

  console.log('\n=== Inherited rules (color only) ===')
  for (const inh of matched.inherited || []) {
    for (const m of inh.matchedCSSRules || []) {
      const rule = m.rule
      const props = rule.style.cssProperties || []
      const colorProps = props.filter(p => /color|background/i.test(p.name))
      if (colorProps.length > 0) {
        const sel = rule.selectorList?.text
        console.log('\n[Inherited] selector:', sel)
        for (const p of colorProps) {
          console.log('  ', p.name, ':', p.value)
        }
      }
    }
  }

  await browser.close()
}

run().catch(e => { console.error('FATAL:', e); process.exit(1) })