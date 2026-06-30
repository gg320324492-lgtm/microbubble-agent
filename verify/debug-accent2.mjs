import { chromium } from 'playwright'
const browser = await chromium.launch({ headless: true })
const ctx = await browser.newContext()
const page = await ctx.newPage()

const TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzgyODAyNzMzLCJ0eXBlIjoiYWNjZXNzIn0.TKpYyHXrEhsdNjR_I13Slu2U2LIiRXkjpoBRQVAgwBw'
await page.addInitScript(t => localStorage.setItem('access_token', t), TOKEN)

await page.goto('http://localhost:3000/settings', { waitUntil: 'networkidle' })
await page.waitForTimeout(1500)
console.log('Before click - accent:', await page.evaluate(() => document.documentElement.dataset.accent))
console.log('Swatch visible:', await page.locator('.theme-swatch').filter({ hasText: '海蓝' }).first().isVisible().catch(() => false))

await page.locator('.theme-swatch').filter({ hasText: '海蓝' }).first().click()
await page.waitForTimeout(2000)

console.log('After click - accent:', await page.evaluate(() => document.documentElement.dataset.accent))
console.log('After click - localStorage accent:', await page.evaluate(() => localStorage.getItem('accent')))

// Now go to members
await page.goto('http://localhost:3000/members', { waitUntil: 'networkidle' })
await page.waitForTimeout(1500)
console.log('On members - accent:', await page.evaluate(() => document.documentElement.dataset.accent))

// Get the first plain primary button
const btnData = await page.evaluate(() => {
  const btn = document.querySelector('.el-button--primary.is-plain')
  if (!btn) return { error: 'no button' }
  const cs = getComputedStyle(btn)
  return {
    text: btn.textContent.trim().slice(0, 20),
    bg: cs.backgroundColor,
    color: cs.color,
    elColorPrimary: getComputedStyle(document.documentElement).getPropertyValue('--el-color-primary'),
  }
})
console.log('Button:', JSON.stringify(btnData, null, 2))

await browser.close()
