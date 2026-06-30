import { chromium } from 'playwright'
const browser = await chromium.launch({ headless: true })
const ctx = await browser.newContext()
const page = await ctx.newPage()
const TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzgyODAyNzMzLCJ0eXBlIjoiYWNjZXNzIn0.TKpYyHXrEhsdNjR_I13Slu2U2LIiRXkjpoBRQVAgwBw'
await page.addInitScript(t => localStorage.setItem('access_token', t), TOKEN)

await page.goto('http://localhost:3000/settings', { waitUntil: 'networkidle' })
await page.waitForTimeout(1500)
const sw = page.locator('.theme-swatch').filter({ hasText: '海蓝' }).first()
if (await sw.isVisible().catch(() => false)) { await sw.click(); await page.waitForTimeout(2000) }

await page.goto('http://localhost:3000/members', { waitUntil: 'networkidle' })
await page.waitForTimeout(3000)

const result = await page.evaluate(() => {
  const btn = document.querySelector('.el-button--primary.is-plain')
  if (!btn) return { error: 'no btn' }
  const cs = getComputedStyle(btn)
  return {
    text: btn.textContent.trim().slice(0, 20),
    color: cs.color,
    bg: cs.backgroundColor,
  }
})
console.log(JSON.stringify(result, null, 2))
await browser.close()
