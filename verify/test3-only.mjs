import { chromium } from 'playwright'
const BASE_URL = 'http://localhost:3000'
const TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzgyODAyNzMzLCJ0eXBlIjoiYWNjZXNzIn0.TKpYyHXrEhsdNjR_I13Slu2U2LIiRXkjpoBRQVAgwBw'

const browser = await chromium.launch({ headless: true })
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const page = await ctx.newPage()
await page.addInitScript(t => localStorage.setItem('access_token', t), TOKEN)

await page.goto(`${BASE_URL}/settings`, { waitUntil: 'networkidle' })
await page.waitForTimeout(1500)
const sw = page.locator('.theme-swatch').filter({ hasText: '海蓝' }).first()
const v = await sw.isVisible().catch(() => false)
console.log('Swatch visible:', v)
if (v) {
  await sw.click()
  await page.waitForTimeout(2000)
}
const accent = await page.evaluate(() => document.documentElement.dataset.accent)
console.log('After click accent:', accent)

await page.goto(`${BASE_URL}/members`, { waitUntil: 'networkidle' })
await page.waitForTimeout(2500)
const accent2 = await page.evaluate(() => document.documentElement.dataset.accent)
console.log('On members accent:', accent2)

const data = await page.evaluate(() => {
  const btn = document.querySelector('.el-button--primary.is-plain')
  if (!btn) return { error: 'no button' }
  const cs = getComputedStyle(btn)
  return {
    text: btn.textContent.trim().slice(0, 20),
    bg: cs.backgroundColor,
    color: cs.color,
    elColorPrimary: getComputedStyle(document.documentElement).getPropertyValue('--el-color-primary'),
    elColorPrimaryLight9: getComputedStyle(document.documentElement).getPropertyValue('--el-color-primary-light-9'),
  }
})
console.log('Button:', JSON.stringify(data, null, 2))
await browser.close()
